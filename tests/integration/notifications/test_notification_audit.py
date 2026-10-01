"""Spec 036 — eventos de auditoria dos envios (FR-021, research R11)."""

import pytest
from sqlalchemy import select

from pivma.core.database.models import AuditEvent
from pivma.notifications.channels import PermanentDeliveryError
from pivma.notifications.service import (
    cancel_pending_notifications,
    enqueue_notification,
)
from pivma.notifications.worker import process_next
from tests.integration.database.test_participant_authorization import (
    create_process,
)

RECIPIENT = 'ana@exemplo.org'
SECRET = 'conteudo-secreto-123'


async def _enqueue(session, settings, kind, process_id, subject_id=None):
    notification = await enqueue_notification(
        session,
        settings,
        kind=kind,
        channel='email',
        recipient=RECIPIENT,
        payload={'subject': 'Olá', 'body': SECRET},
        actor_id=None,
        subject=('role_assignment_invite', subject_id or process_id),
        process_instance_id=process_id,
    )
    await session.commit()
    return notification


async def _event(session, notification):
    events = (
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.context_data['notification_id'].astext
                == str(notification.id)
            )
        )
    ).all()
    assert len(events) == 1
    return events[0]


def _assert_safe_context(event, notification):
    assert event.context_data['kind'] == notification.kind
    assert event.context_data['channel'] == 'email'
    assert event.context_data['subject_type'] == 'role_assignment_invite'
    assert event.context_data['subject_id'] == str(notification.subject_id)
    assert RECIPIENT not in repr(event.context_data)
    assert SECRET not in repr(event.context_data)


@pytest.mark.asyncio
async def test_sent_notification_records_audit_event(
    session, notification_settings, fake_email_channel, echo_kind
):
    process = await create_process(session)
    notification = await _enqueue(
        session, notification_settings, echo_kind, process.id
    )

    await process_next(session, fake_email_channel, notification_settings)

    event = await _event(session, notification)
    assert event.event_type == 'NOTIFICATION_SENT'
    assert event.process_instance_id == process.id
    assert event.user_id is None
    assert event.context_data['attempts'] == 1
    _assert_safe_context(event, notification)


@pytest.mark.asyncio
async def test_failed_notification_records_audit_event(
    session, notification_settings, fake_email_channel, echo_kind
):
    process = await create_process(session)
    notification = await _enqueue(
        session, notification_settings, echo_kind, process.id
    )
    fake_email_channel.failures.append(
        PermanentDeliveryError('smtp_permanent', '550')
    )

    await process_next(session, fake_email_channel, notification_settings)

    event = await _event(session, notification)
    assert event.event_type == 'NOTIFICATION_FAILED'
    assert event.context_data['error_code'] == 'smtp_permanent'
    _assert_safe_context(event, notification)


@pytest.mark.asyncio
async def test_cancelled_notification_records_audit_event_with_actor(
    session, notification_settings, echo_kind, user
):
    process = await create_process(session)
    notification = await _enqueue(
        session, notification_settings, echo_kind, process.id
    )

    await cancel_pending_notifications(
        session,
        subject=('role_assignment_invite', process.id),
        reason='cancelled_revoked',
        actor_id=user.id,
    )
    await session.commit()

    event = await _event(session, notification)
    assert event.event_type == 'NOTIFICATION_CANCELLED'
    assert event.user_id == user.id
    assert event.context_data['error_code'] == 'cancelled_revoked'
    _assert_safe_context(event, notification)


@pytest.mark.asyncio
async def test_notification_without_process_records_no_audit_event(
    session, notification_settings, fake_email_channel, echo_kind
):
    before = len((await session.scalars(select(AuditEvent))).all())
    await enqueue_notification(
        session,
        notification_settings,
        kind=echo_kind,
        channel='email',
        recipient=RECIPIENT,
        payload={'subject': 'Olá', 'body': SECRET},
        actor_id=None,
    )
    await session.commit()

    await process_next(session, fake_email_channel, notification_settings)

    after = len((await session.scalars(select(AuditEvent))).all())
    assert after == before
