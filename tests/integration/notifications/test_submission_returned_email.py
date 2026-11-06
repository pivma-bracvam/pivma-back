"""Spec 046 (US2) — e-mail ao proponente quando a submissão é devolvida."""

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Assignment,
    AuditEvent,
    EvaluationRun,
    Notification,
    Task,
)
from pivma.core.process_engine import open_return_review
from pivma.notifications.channels import (
    FakeEmailChannel,
    PermanentDeliveryError,
)
from pivma.notifications.crypto import decrypt_payload
from pivma.notifications.worker import process_next
from tests.ai_eval_helpers import NON_COMPLIANT_STATEMENT
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_return_review import (
    KEY,
    ORIGIN,
    VALUES,
    _ai_return,
    _choose,
    _created_process,
    _review_runs,
    _triage_decides_return,
    _triage_return,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.user_factory import UserFactory

EMAIL_KIND = 'submission_returned_email'
SECRET_JUSTIFICATION = 'Justificativa sigilosa da triagem.'
SECRET_REVIEW = 'Parecer sigiloso do campo.'


async def _emails(session):
    return list(
        await session.scalars(
            select(Notification)
            .where(Notification.kind == EMAIL_KIND)
            .order_by(Notification.requested_at)
            .execution_options(populate_existing=True)
        )
    )


async def _deliver(session, settings, channel=None):
    channel = channel or FakeEmailChannel()
    while await process_next(session, channel, settings):
        pass
    return channel


def _retry(client, admin, run_id):
    authenticate(client, admin)
    return client.post(
        f'/admin/pre-evaluations/{run_id}/retry', headers=ORIGIN
    )


async def _events(session, pid, event_type):
    return list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == pid,
                AuditEvent.event_type == event_type,
            )
        )
    )


async def _submitted(client, session):
    """Processo enviado, ainda sem decisão da triagem."""
    proponent, pid = await _created_process(client, session)
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return proponent, pid


async def _participant(session, pid, role_key):
    user = UserFactory()
    session.add(user)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(pid), user=user, role_key=role_key
    )
    return user


@pytest.mark.asyncio
async def test_triage_return_enqueues_one_email_with_subject_and_process(
    client, session, bracvam_user, return_email_settings
):
    del return_email_settings
    proponent, pid, _ = await _triage_return(client, session, bracvam_user)

    [email] = await _emails(session)
    [review_run] = await _review_runs(session, pid)

    assert email.status == 'pending'
    assert email.recipient == proponent.email
    assert email.subject_type == KEY
    assert email.subject_id == review_run.id
    assert email.process_instance_id == UUID(pid)


@pytest.mark.asyncio
async def test_negative_ai_return_enqueues_email(
    client, session, ai_eval_admin, fake_provider, return_email_settings
):
    del fake_provider, return_email_settings
    proponent, _, _ = await _ai_return(client, session, ai_eval_admin)

    [email] = await _emails(session)

    assert email.recipient == proponent.email


@pytest.mark.asyncio
async def test_failed_ai_return_enqueues_email_with_same_origin(
    client, session, ai_eval_admin, fake_provider, return_email_settings
):
    del fake_provider
    await _ai_return(client, session, ai_eval_admin, failed=True)

    [email] = await _emails(session)
    payload = decrypt_payload(
        email.payload_encrypted,
        return_email_settings.NOTIFICATION_ENCRYPTION_KEY,
    )

    assert payload['source'] == 'AI_PRE_EVALUATION'
    assert set(payload) == {
        'process_code',
        'process_title',
        'source',
        'due_date',
    }


@pytest.mark.asyncio
async def test_each_active_proponent_gets_own_email(
    client, session, bracvam_user, return_email_settings
):
    del return_email_settings
    proponent, pid = await _submitted(client, session)
    second = await _participant(session, pid, 'proponent')

    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})

    recipients = [e.recipient for e in await _emails(session)]
    assert sorted(recipients) == sorted([proponent.email, second.email])


@pytest.mark.asyncio
async def test_revoked_proponent_gets_no_email(
    client, session, bracvam_user, return_email_settings
):
    del return_email_settings
    proponent, pid = await _submitted(client, session)
    assignment = await session.scalar(
        select(Assignment).where(Assignment.process_instance_id == pid)
    )
    assignment.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()

    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})

    assert await _emails(session) == []
    assert [r.status for r in await _review_runs(session, pid)] == [
        'IN_PROGRESS'
    ]


@pytest.mark.asyncio
async def test_deleted_account_gets_no_email(
    client, session, bracvam_user, return_email_settings
):
    del return_email_settings
    proponent, pid = await _submitted(client, session)
    second = await _participant(session, pid, 'proponent')
    second.deleted_at = datetime(2026, 8, 12)
    await session.commit()

    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})

    assert [e.recipient for e in await _emails(session)] == [proponent.email]


@pytest.mark.asyncio
async def test_other_roles_get_no_email(
    client, session, bracvam_user, return_email_settings
):
    del return_email_settings
    proponent, pid = await _submitted(client, session)
    await _participant(session, pid, 'sponsor')

    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})

    assert [e.recipient for e in await _emails(session)] == [proponent.email]


@pytest.mark.asyncio
async def test_delivered_email_hides_justification_reviews_and_reviewer(
    client, session, bracvam_user, return_email_settings
):
    await _triage_return(
        client,
        session,
        bracvam_user,
        justification=SECRET_JUSTIFICATION,
        reviews={'method_title': SECRET_REVIEW},
    )

    channel = await _deliver(session, return_email_settings)

    [message] = channel.sent
    for content in (message.subject, message.text, message.html):
        assert SECRET_JUSTIFICATION not in content
        assert SECRET_REVIEW not in content
        assert bracvam_user.full_name not in content


@pytest.mark.parametrize('failed', [False, True], ids=['negative', 'failure'])
@pytest.mark.asyncio
async def test_delivered_email_hides_ai_result(  # noqa: PLR0913, PLR0917
    client,
    session,
    ai_eval_admin,
    fake_provider,
    return_email_settings,
    failed,
):
    del fake_provider
    await _ai_return(client, session, ai_eval_admin, failed=failed)

    channel = await _deliver(session, return_email_settings)

    [message] = channel.sent
    for content in (message.subject, message.text, message.html):
        assert NON_COMPLIANT_STATEMENT not in content
        assert 'falha' not in content.lower()


@pytest.mark.asyncio
async def test_return_completes_without_email_channel(
    client, session, bracvam_user, no_email_channel
):
    del no_email_channel
    _, pid, decision = await _triage_return(client, session, bracvam_user)

    tasks = await session.scalars(
        select(Task.status)
        .join(ActivityRun)
        .join(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == pid,
            ActivityInstance.key == KEY,
        )
    )

    assert decision['return_review_run'] == 1
    assert list(tasks) == ['READY']
    assert (
        await session.scalar(select(func.count()).select_from(Notification))
        == 0
    )


@pytest.mark.asyncio
async def test_rollback_of_return_discards_email(
    client, session, return_email_settings
):
    del return_email_settings
    proponent, pid = await _submitted(client, session)
    user_id = proponent.id

    await open_return_review(
        session, UUID(pid), source='TRIAGE', user_id=user_id
    )
    await session.flush()
    assert len(await _emails(session)) == 1

    await session.rollback()

    assert await _emails(session) == []


@pytest.mark.asyncio
async def test_permanent_delivery_failure_keeps_return_open(
    client, session, bracvam_user, return_email_settings
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    channel = FakeEmailChannel(
        failures=[PermanentDeliveryError('smtp_permanent', '550')]
    )

    await _deliver(session, return_email_settings, channel)

    [email] = await _emails(session)
    assert email.status == 'failed'
    assert [r.status for r in await _review_runs(session, pid)] == [
        'IN_PROGRESS'
    ]


@pytest.mark.asyncio
async def test_retry_cancels_pending_email_and_records_event(
    client, session, ai_eval_admin, fake_provider, return_email_settings
):
    del fake_provider, return_email_settings
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )

    response = _retry(client, ai_eval_admin, run_id)

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    [email] = await _emails(session)
    assert email.status == 'cancelled'
    assert email.error_code == 'return_review_cancelled'
    assert email.payload_encrypted is None
    [event] = await _events(session, pid, 'NOTIFICATION_CANCELLED')
    assert event.user_id == ai_eval_admin.id


@pytest.mark.asyncio
async def test_retry_keeps_already_sent_email(
    client, session, ai_eval_admin, fake_provider, return_email_settings
):
    del fake_provider
    _, _, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    await _deliver(session, return_email_settings)

    response = _retry(client, ai_eval_admin, run_id)

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    [email] = await _emails(session)
    assert email.status == 'sent'


@pytest.mark.parametrize('choice', ['REVISE', 'WITHDRAW'])
@pytest.mark.asyncio
async def test_decision_keeps_pending_email(
    client, session, bracvam_user, return_email_settings, choice
):
    del return_email_settings
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    assert _choose(client, pid, choice).status_code == HTTPStatus.OK

    [email] = await _emails(session)
    assert email.status == 'pending'


@pytest.mark.asyncio
async def test_sent_email_records_audit_event_with_subject(
    client, session, bracvam_user, return_email_settings
):
    proponent, pid, _ = await _triage_return(client, session, bracvam_user)
    recipient = proponent.email

    await _deliver(session, return_email_settings)

    [event] = await _events(session, pid, 'NOTIFICATION_SENT')
    assert event.context_data['kind'] == EMAIL_KIND
    assert event.context_data['subject_type'] == KEY
    assert recipient not in str(event.context_data)


@pytest.mark.asyncio
async def test_retry_records_cancellation_with_admin_as_author(
    client, session, ai_eval_admin, fake_provider, no_email_channel
):
    del fake_provider, no_email_channel
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )

    response = _retry(client, ai_eval_admin, run_id)

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    [event] = await _events(session, pid, 'RETURN_REVIEW_CANCELLED')
    [review_run] = await _review_runs(session, pid)
    assert event.user_id == ai_eval_admin.id
    assert event.activity_run_id == review_run.id
    assert event.context_data == {
        'source': 'AI_PRE_EVALUATION',
        'run_number': 1,
    }


@pytest.mark.asyncio
async def test_retry_new_run_keeps_original_creator(
    client, session, ai_eval_admin, fake_provider, no_email_channel
):
    del fake_provider, no_email_channel
    proponent, _, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )

    response = _retry(client, ai_eval_admin, run_id)

    new_run = await session.get(
        EvaluationRun, UUID(response.json()['new_run_id'])
    )
    assert new_run.created_by == proponent.id


@pytest.mark.asyncio
async def test_process_deletion_cancels_pending_email(
    client, session, bracvam_user, return_email_settings
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = client.delete(f'/processes/{pid}', headers=ORIGIN)

    assert response.status_code == HTTPStatus.NO_CONTENT, response.text
    [email] = await _emails(session)
    assert email.status == 'cancelled'
    assert email.error_code == 'return_review_cancelled'
    assert len(await _events(session, pid, 'NOTIFICATION_CANCELLED')) == 1
    channel = await _deliver(session, return_email_settings)
    assert channel.sent == []


@pytest.mark.asyncio
async def test_process_deletion_cancels_email_of_decided_return(
    client, session, bracvam_user, return_email_settings
):
    del return_email_settings
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    response = client.delete(f'/processes/{pid}', headers=ORIGIN)

    assert response.status_code == HTTPStatus.NO_CONTENT, response.text
    [email] = await _emails(session)
    assert email.status == 'cancelled'
