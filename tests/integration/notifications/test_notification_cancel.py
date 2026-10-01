"""Spec 036 — cancelamento de envios pendentes por objeto (research R6)."""

from uuid import uuid4

import pytest

from pivma.notifications.channels import PermanentDeliveryError
from pivma.notifications.service import (
    cancel_pending_notifications,
    enqueue_notification,
)
from pivma.notifications.worker import process_next


async def _enqueue(session, settings, kind, subject):
    notification = await enqueue_notification(
        session,
        settings,
        kind=kind,
        channel='email',
        recipient='ana@exemplo.org',
        payload={'subject': 'Olá', 'body': 'x'},
        actor_id=None,
        subject=subject,
    )
    await session.commit()
    return notification


@pytest.mark.asyncio
async def test_cancel_only_affects_pending_notifications_of_the_subject(
    session, notification_settings, fake_email_channel, echo_kind
):
    target = ('role_assignment_invite', uuid4())
    other = ('role_assignment_invite', uuid4())
    finished = await _enqueue(session, notification_settings, echo_kind, target)
    fake_email_channel.failures.append(
        PermanentDeliveryError('smtp_permanent', '550')
    )
    await process_next(session, fake_email_channel, notification_settings)
    pending = await _enqueue(session, notification_settings, echo_kind, target)
    untouched = await _enqueue(session, notification_settings, echo_kind, other)

    cancelled = await cancel_pending_notifications(
        session, subject=target, reason='cancelled_resent', actor_id=None
    )
    await session.commit()

    assert cancelled == 1
    for item in (finished, pending, untouched):
        await session.refresh(item)
    assert pending.status == 'cancelled'
    assert pending.error_code == 'cancelled_resent'
    assert pending.payload_encrypted is None
    assert pending.finished_at is not None
    assert finished.status == 'failed'
    assert finished.error_code == 'smtp_permanent'
    assert untouched.status == 'pending'
    assert untouched.payload_encrypted is not None
