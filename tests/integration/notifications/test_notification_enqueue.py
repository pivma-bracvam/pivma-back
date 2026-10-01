"""Spec 036 — registro do pedido de envio (FR-001, FR-002, FR-007, FR-009)."""

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import Notification
from pivma.core.settings import Settings
from pivma.notifications.service import (
    ChannelUnavailableError,
    enqueue_notification,
)

PAYLOAD = {'subject': 'Olá', 'body': 'conteudo-secreto-123'}


async def _count(session):
    return await session.scalar(select(func.count(Notification.id)))


@pytest.mark.asyncio
async def test_enqueue_then_rollback_leaves_no_notification(
    session, notification_settings, echo_kind
):
    before = await _count(session)

    await enqueue_notification(
        session,
        notification_settings,
        kind=echo_kind,
        channel='email',
        recipient='ana@exemplo.org',
        payload=PAYLOAD,
        actor_id=None,
    )
    await session.rollback()

    assert await _count(session) == before


@pytest.mark.asyncio
async def test_enqueue_then_commit_records_pending_encrypted_notification(
    session, notification_settings, echo_kind
):
    notification = await enqueue_notification(
        session,
        notification_settings,
        kind=echo_kind,
        channel='email',
        recipient='ana@exemplo.org',
        payload=PAYLOAD,
        actor_id=None,
    )
    await session.commit()

    stored = await session.get(Notification, notification.id)
    assert stored.status == 'pending'
    assert stored.attempts == 0
    assert stored.next_attempt_at is not None
    assert stored.recipient == 'ana@exemplo.org'
    assert stored.payload_encrypted
    assert 'conteudo-secreto-123' not in stored.payload_encrypted


@pytest.mark.asyncio
async def test_enqueue_unknown_kind_raises_and_records_nothing(
    session, notification_settings
):
    before = await _count(session)

    with pytest.raises(ValueError, match='kind'):
        await enqueue_notification(
            session,
            notification_settings,
            kind='kind_sem_renderizador',
            channel='email',
            recipient='ana@exemplo.org',
            payload=PAYLOAD,
            actor_id=None,
        )

    assert await _count(session) == before


@pytest.mark.asyncio
async def test_enqueue_without_configured_channel_raises(session, echo_kind):
    settings = Settings(NOTIFICATION_EMAIL_BACKEND=None)

    with pytest.raises(ChannelUnavailableError):
        await enqueue_notification(
            session,
            settings,
            kind=echo_kind,
            channel='email',
            recipient='ana@exemplo.org',
            payload=PAYLOAD,
            actor_id=None,
        )
