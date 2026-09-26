# ruff: noqa: PLR2004
"""Revisão do retorno ao proponente (Spec 030, US4)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    DirectReviewRequest,
    ProcessInstance,
    Task,
)
from tests.activity_state import activity_status, in_triage
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import grant_cargo
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
KEY = 'submission_return_review'
VALUES = {'method_title': 'Ensaio RhCE para irritação'}


def _review_url(pid):
    return f'/processes/{pid}/return-review'


def _choose(client, pid, choice, justification=None, headers=ORIGIN):
    return client.post(
        _review_url(pid),
        json={'choice': choice, 'justification': justification},
        headers=headers,
    )


async def _review_runs(session, pid):
    return list(
        await session.scalars(
            select(ActivityRun)
            .join(ActivityInstance)
            .where(
                ActivityInstance.process_instance_id == pid,
                ActivityInstance.key == KEY,
            )
            .order_by(ActivityRun.run_number)
            .execution_options(populate_existing=True)
        )
    )


async def _review_tasks(session, pid):
    return list(
        await session.scalars(
            select(Task)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(
                ActivityInstance.process_instance_id == pid,
                ActivityInstance.key == KEY,
            )
            .execution_options(populate_existing=True)
        )
    )


async def _submission_run_count(session, pid):
    return len(
        list(
            await session.scalars(
                select(ActivityRun.id)
                .join(ActivityInstance)
                .where(
                    ActivityInstance.process_instance_id == pid,
                    ActivityInstance.key == 'proposal_submission',
                )
            )
        )
    )


async def _created_process(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Processo 1'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return proponent, response.json()['id']


async def _triage_return(client, session, bracvam_user, *, justification=None):
    proponent, pid = await _created_process(client, session)
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    authenticate(client, bracvam_user)
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': justification or 'Incluir histórico.',
        },
        headers=ORIGIN,
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    authenticate(client, proponent)
    return proponent, pid, decision.json()


async def _ai_return(client, session, ai_eval_admin, *, failed=False):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    if failed:
        await svc._mark_failed(session, run_id)
    else:
        await svc._execute(session, run_id)
    authenticate(client, proponent)
    return proponent, result['process_id'], run_id


# --- Abertura -------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_process_has_blocked_return_review_without_run(
    client, session
):
    _, pid = await _created_process(client, session)

    assert await activity_status(session, pid, KEY) == 'BLOCKED'
    assert await _review_runs(session, pid) == []
    assert await _review_tasks(session, pid) == []


@pytest.mark.asyncio
async def test_triage_needs_revision_opens_return_review(
    client, session, bracvam_user
):
    _, pid, decision = await _triage_return(client, session, bracvam_user)

    runs = await _review_runs(session, pid)
    tasks = await _review_tasks(session, pid)
    assert [r.status for r in runs] == ['IN_PROGRESS']
    assert [(t.status, t.assigned_role) for t in tasks] == [
        ('READY', 'proponent')
    ]
    assert decision['return_review_run'] == 1
    assert 'next_activity_run' not in decision
    assert await _submission_run_count(session, pid) == 1


@pytest.mark.asyncio
async def test_triage_rejection_does_not_open_return_review(
    client, session, bracvam_user
):
    _, pid = await _created_process(client, session)
    client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
    )
    authenticate(client, bracvam_user)
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'REJECTED', 'justification': 'Fora do escopo.'},
        headers=ORIGIN,
    )

    assert response.json()['return_review_run'] is None
    assert await _review_runs(session, pid) == []


@pytest.mark.asyncio
async def test_triage_approval_does_not_open_return_review(
    client, session, bracvam_user
):
    _, pid = await _created_process(client, session)
    client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
    )
    authenticate(client, bracvam_user)
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers=ORIGIN,
    )

    assert response.json()['return_review_run'] is None
    assert await _review_runs(session, pid) == []


@pytest.mark.asyncio
async def test_return_review_opened_event_is_audited(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == pid,
            AuditEvent.event_type == 'RETURN_REVIEW_OPENED',
        )
    )
    assert event is not None
    assert event.context_data['source'] == 'TRIAGE'


# --- Leitura --------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_return_review_from_triage_shows_decision(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(
        client, session, bracvam_user, justification='Faltam controles.'
    )

    response = client.get(_review_url(pid))

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body['source'] == 'TRIAGE'
    assert body['run_number'] == 1
    assert body['triage_decision']['outcome'] == 'NEEDS_REVISION'
    assert body['triage_decision']['justification'] == 'Faltam controles.'
    assert body['ai_pre_evaluation'] is None
    assert body['available_choices'] == ['REVISE', 'WITHDRAW']


@pytest.mark.asyncio
async def test_get_return_review_from_ai_shows_pre_evaluation(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(client, session, ai_eval_admin)

    body = client.get(_review_url(pid)).json()

    assert body['source'] == 'AI_PRE_EVALUATION'
    assert body['ai_pre_evaluation']['run_id'] == str(run_id)
    assert body['triage_decision'] is None
    assert 'CONTEST_AI' in body['available_choices']


@pytest.mark.asyncio
async def test_get_return_review_404_when_none_open(client, session):
    _, pid = await _created_process(client, session)

    assert client.get(_review_url(pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_return_review_404_for_sponsor(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    sponsor = UserFactory()
    session.add(sponsor)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(pid), user=sponsor, role_key='sponsor'
    )
    authenticate(client, sponsor)

    assert client.get(_review_url(pid)).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_return_review_200_for_bracvam_and_admin(
    client, session, bracvam_user, ai_eval_admin
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    for user in (bracvam_user, ai_eval_admin):
        authenticate(client, user)
        assert client.get(_review_url(pid)).status_code == HTTPStatus.OK


# --- Escolhas -------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_opens_new_submission_draft_with_previous_values(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'REVISE')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['submission_run'] == 2
    assert response.json()['process_status'] == 'OPEN'
    form = client.get(
        f'/processes/{pid}/activities/proposal_submission/form'
    ).json()
    assert form['is_submitted'] is False
    assert form['values']['method_title'] == VALUES['method_title']
    assert [r.status for r in await _review_runs(session, pid)] == [
        'COMPLETED'
    ]
    assert await activity_status(session, pid, KEY) == 'BLOCKED'


@pytest.mark.asyncio
async def test_contest_ai_moves_to_triage(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(client, session, ai_eval_admin)

    response = _choose(client, pid, 'CONTEST_AI', 'Discordo da IA.')

    assert response.status_code == HTTPStatus.OK, response.text
    assert await in_triage(session, pid)
    request = await session.scalar(
        select(DirectReviewRequest).where(
            DirectReviewRequest.evaluation_run_id == run_id
        )
    )
    assert request is not None


@pytest.mark.asyncio
async def test_contest_ai_rejected_for_triage_source(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'CONTEST_AI')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_withdraw_closes_process(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'WITHDRAW', 'Vamos reformular o método.')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['process_status'] == 'CLOSED'
    process = await session.get(ProcessInstance, pid, populate_existing=True)
    assert process.status == 'CLOSED'
    assert process.closure_reason
    pending = [
        t
        for t in await session.scalars(
            select(Task)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == pid)
            .execution_options(populate_existing=True)
        )
        if t.status not in {'COMPLETED', 'CANCELLED'}
    ]
    assert pending == []


@pytest.mark.asyncio
async def test_choice_is_audited(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    _choose(client, pid, 'REVISE', 'Vou ajustar.')

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == pid,
            AuditEvent.event_type == 'RETURN_REVIEW_DECIDED',
        )
    )
    assert event.context_data == {
        'choice': 'REVISE',
        'source': 'TRIAGE',
        'justification': 'Vou ajustar.',
        'run_number': 1,
    }


@pytest.mark.asyncio
async def test_bracvam_cannot_choose(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    authenticate(client, bracvam_user)

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_cannot_choose(
    client, session, bracvam_user, ai_eval_admin
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    authenticate(client, ai_eval_admin)

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_sponsor_choice_is_404(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    sponsor = UserFactory()
    session.add(sponsor)
    await session.commit()
    await grant_cargo(
        session, process_id=UUID(pid), user=sponsor, role_key='sponsor'
    )
    authenticate(client, sponsor)

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_second_choice_is_conflict(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.OK

    response = _choose(client, pid, 'WITHDRAW')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_choice_on_closed_process_is_conflict(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)
    process = await session.get(ProcessInstance, pid)
    process.status = 'CANCELLED'
    await session.commit()

    assert _choose(client, pid, 'REVISE').status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_choice_requires_trusted_origin(client, session, bracvam_user):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = _choose(client, pid, 'REVISE', headers={})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_submission_locked_while_return_review_open(
    client, session, bracvam_user
):
    _, pid, _ = await _triage_return(client, session, bracvam_user)

    response = client.put(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
    )

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_admin_retry_cancels_open_return_review(
    client, session, ai_eval_admin, fake_provider
):
    del fake_provider
    _, pid, run_id = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )
    assert [r.status for r in await _review_runs(session, pid)] == [
        'IN_PROGRESS'
    ]
    authenticate(client, ai_eval_admin)

    response = client.post(
        f'/admin/pre-evaluations/{run_id}/retry', headers=ORIGIN
    )

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    assert [r.status for r in await _review_runs(session, pid)] == [
        'CANCELLED'
    ]
    assert [t.status for t in await _review_tasks(session, pid)] == [
        'CANCELLED'
    ]
    assert await activity_status(session, pid, KEY) == 'BLOCKED'
