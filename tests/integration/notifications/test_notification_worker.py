# ruff: noqa: PLR2004

"""Spec 036 — processo de envio (FR-003 a FR-006, FR-009, FR-010)."""

import asyncio
from datetime import datetime, timedelta

import pytest
import structlog
from cryptography.fernet import Fernet
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import Notification
from pivma.notifications.channels import (
    FakeEmailChannel,
    PermanentDeliveryError,
    TemporaryDeliveryError,
)
from pivma.notifications.crypto import encrypt_payload
from pivma.notifications.service import enqueue_notification
from pivma.notifications.worker import process_next

SECRET = 'conteudo-secreto-123'
PAYLOAD = {'subject': 'Olá', 'body': SECRET}


async def _enqueue(session, settings, kind, **kwargs):
    notification = await enqueue_notification(
        session,
        settings,
        kind=kind,
        channel='email',
        recipient='ana@exemplo.org',
        payload=PAYLOAD,
        actor_id=None,
        **kwargs,
    )
    await session.commit()
    return notification


@pytest.mark.asyncio
async def test_process_next_sends_and_finishes_notification(
    session, notification_settings, fake_email_channel, echo_kind
):
    notification = await _enqueue(session, notification_settings, echo_kind)

    processed = await process_next(
        session, fake_email_channel, notification_settings
    )

    assert processed is True
    [message] = fake_email_channel.sent
    assert message.to == 'ana@exemplo.org'
    assert message.subject == 'Olá'
    assert message.text == f'texto: {SECRET}'
    assert message.html == f'<p>{SECRET}</p>'
    await session.refresh(notification)
    assert notification.status == 'sent'
    assert notification.attempts == 1
    assert notification.sent_at is not None
    assert notification.finished_at is not None
    assert notification.payload_encrypted is None


@pytest.mark.asyncio
async def test_process_next_without_pending_returns_false(
    session, notification_settings, fake_email_channel
):
    assert (
        await process_next(session, fake_email_channel, notification_settings)
        is False
    )


@pytest.mark.asyncio
async def test_temporary_error_postpones_next_attempt(
    session, notification_settings, fake_email_channel, echo_kind
):
    notification = await _enqueue(session, notification_settings, echo_kind)
    fake_email_channel.failures.append(
        TemporaryDeliveryError('connection', 'refused')
    )
    now = datetime.utcnow()

    await process_next(
        session, fake_email_channel, notification_settings, now=now
    )

    await session.refresh(notification)
    assert notification.status == 'pending'
    assert notification.attempts == 1
    assert notification.error_code == 'connection'
    assert notification.next_attempt_at == now + timedelta(seconds=30)
    assert notification.payload_encrypted is not None
    # Antes do novo horário, nada a processar.
    assert (
        await process_next(
            session,
            fake_email_channel,
            notification_settings,
            now=now + timedelta(seconds=29),
        )
        is False
    )
    assert fake_email_channel.sent == []


@pytest.mark.asyncio
async def test_temporary_error_on_last_attempt_fails_with_max_attempts(
    session, notification_settings, fake_email_channel, echo_kind
):
    notification = await _enqueue(session, notification_settings, echo_kind)
    max_attempts = notification_settings.NOTIFICATION_MAX_ATTEMPTS
    fake_email_channel.failures.extend(
        TemporaryDeliveryError('smtp_temporary', '421')
        for _ in range(max_attempts)
    )
    now = datetime.utcnow()

    for attempt in range(max_attempts):
        await process_next(
            session,
            fake_email_channel,
            notification_settings,
            now=now + timedelta(hours=attempt),
        )

    await session.refresh(notification)
    assert notification.status == 'failed'
    assert notification.error_code == 'max_attempts'
    assert notification.attempts == max_attempts
    assert notification.payload_encrypted is None
    assert notification.finished_at is not None


@pytest.mark.asyncio
async def test_permanent_error_fails_on_first_attempt(
    session, notification_settings, fake_email_channel, echo_kind
):
    notification = await _enqueue(session, notification_settings, echo_kind)
    fake_email_channel.failures.append(
        PermanentDeliveryError('smtp_permanent', '550 no such user')
    )

    await process_next(session, fake_email_channel, notification_settings)

    await session.refresh(notification)
    assert notification.status == 'failed'
    assert notification.error_code == 'smtp_permanent'
    assert notification.attempts == 1
    assert notification.payload_encrypted is None


@pytest.mark.asyncio
async def test_expired_notification_fails_without_sending(
    session, notification_settings, fake_email_channel, echo_kind
):
    now = datetime.utcnow()
    notification = await _enqueue(
        session,
        notification_settings,
        echo_kind,
        expires_at=now + timedelta(minutes=1),
    )

    await process_next(
        session,
        fake_email_channel,
        notification_settings,
        now=now + timedelta(minutes=2),
    )

    await session.refresh(notification)
    assert notification.status == 'failed'
    assert notification.error_code == 'expired'
    assert notification.payload_encrypted is None
    assert fake_email_channel.sent == []


@pytest.mark.asyncio
async def test_undecryptable_payload_fails_without_sending(
    session, notification_settings, fake_email_channel, echo_kind
):
    notification = await _enqueue(session, notification_settings, echo_kind)
    other_key = notification_settings.model_copy(
        update={'NOTIFICATION_ENCRYPTION_KEY': Fernet.generate_key().decode()}
    )

    await process_next(session, fake_email_channel, other_key)

    await session.refresh(notification)
    assert notification.status == 'failed'
    assert notification.error_code == 'decrypt'
    assert notification.payload_encrypted is None
    assert fake_email_channel.sent == []


@pytest.mark.asyncio
async def test_concurrent_workers_send_a_notification_only_once(
    engine, notification_settings, echo_kind
):
    """SC-004: duas sessões com conexões próprias e dado já confirmado."""
    channel = FakeEmailChannel(delay=0.3)
    async with AsyncSession(engine, expire_on_commit=False) as setup:
        notification = Notification(
            kind=echo_kind,
            channel='email',
            recipient='ana@exemplo.org',
            payload_encrypted=encrypt_payload(
                PAYLOAD, notification_settings.NOTIFICATION_ENCRYPTION_KEY
            ),
            next_attempt_at=datetime.utcnow(),
        )
        setup.add(notification)
        await setup.commit()
    try:
        async with (
            AsyncSession(engine, expire_on_commit=False) as first,
            AsyncSession(engine, expire_on_commit=False) as second,
        ):
            results = await asyncio.gather(
                process_next(first, channel, notification_settings),
                process_next(second, channel, notification_settings),
            )
        assert sorted(results) == [False, True]
        assert len(channel.sent) == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                delete(Notification).where(Notification.id == notification.id)
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'failure',
    [
        None,
        TemporaryDeliveryError('connection', 'refused'),
        PermanentDeliveryError('smtp_permanent', '550 rejected'),
    ],
    ids=['sent', 'temporary', 'permanent'],
)
async def test_logs_and_error_detail_never_contain_content(  # noqa: PLR0913, PLR0917
    session, notification_settings, fake_email_channel, echo_kind, failure
):
    notification = await _enqueue(session, notification_settings, echo_kind)
    if failure is not None:
        fake_email_channel.failures.append(failure)

    with structlog.testing.capture_logs() as logs:
        await process_next(session, fake_email_channel, notification_settings)

    await session.refresh(notification)
    assert logs, 'o processo de envio deve registrar o resultado'
    assert SECRET not in repr(logs)
    assert SECRET not in (notification.error_detail or '')
