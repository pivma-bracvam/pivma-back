"""Processo de envio de notificações (Spec 036, research R1, R2, R5, R7).

Executado à parte da API: ``python -m pivma.notifications.worker``. Busca um
envio pendente e vencido por vez com ``FOR UPDATE SKIP LOCKED``, envia pelo
canal configurado e grava o resultado antes de liberar a linha. Dois
processos nunca pegam a mesma linha.

Limite conhecido (R2): se o processo cair depois que o servidor SMTP aceitou
a mensagem e antes do commit, a linha volta a pendente e a mensagem pode
sair de novo.

Nada do conteúdo do envio vai para log nem para `error_detail` (FR-010).
"""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import Notification
from pivma.core.logging import get_operational_logger, setup_logging
from pivma.core.settings import Settings, get_settings
from pivma.notifications.channels import (
    DeliveryError,
    EmailChannel,
    OutgoingEmail,
    PermanentDeliveryError,
    get_email_channel,
)
from pivma.notifications.crypto import PayloadDecryptError, decrypt_payload
from pivma.notifications.renderers import get_renderer
from pivma.notifications.service import (
    FAILED,
    PENDING,
    SENT,
    audit_event,
    finish,
    retry_delay,
)


def _log(notification: Notification, event: str) -> None:
    get_operational_logger().info(
        event,
        notification_id=str(notification.id),
        kind=notification.kind,
        status=notification.status,
        attempts=notification.attempts,
        error_code=notification.error_code,
    )


async def _claim(session: AsyncSession, now: datetime) -> Notification | None:
    return await session.scalar(
        select(Notification)
        .where(
            Notification.status == PENDING,
            Notification.next_attempt_at <= now,
        )
        .order_by(Notification.next_attempt_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def _fail(
    notification: Notification, now: datetime, code: str, detail: str = ''
) -> None:
    finish(notification, FAILED, now=now, error_code=code, error_detail=detail)


async def _deliver(
    notification: Notification,
    channel: EmailChannel,
    settings: Settings,
    now: datetime,
) -> None:
    try:
        payload = decrypt_payload(
            notification.payload_encrypted,
            settings.NOTIFICATION_ENCRYPTION_KEY,
        )
    except PayloadDecryptError:
        _fail(notification, now, 'decrypt', 'Conteúdo não decifra.')
        return

    subject, text, html = get_renderer(notification.kind)(payload)
    notification.attempts += 1
    notification.last_attempt_at = now
    try:
        await channel.send(
            OutgoingEmail(
                to=notification.recipient,
                subject=subject,
                text=text,
                html=html,
            )
        )
    except DeliveryError as exc:
        notification.error_detail = exc.detail[:500]
        if isinstance(exc, PermanentDeliveryError):
            _fail(notification, now, exc.code)
        elif notification.attempts >= settings.NOTIFICATION_MAX_ATTEMPTS:
            _fail(notification, now, 'max_attempts')
        else:
            notification.error_code = exc.code
            notification.next_attempt_at = now + retry_delay(
                notification.attempts, settings
            )
        return
    finish(notification, SENT, now=now)


async def process_next(
    session: AsyncSession,
    channel: EmailChannel,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> bool:
    """Processa no máximo um envio vencido e comita. Devolve se havia um."""
    current = now if now is not None else datetime.utcnow()
    notification = await _claim(session, current)
    if notification is None:
        await session.commit()
        return False

    if (
        notification.expires_at is not None
        and notification.expires_at <= current
    ):
        _fail(notification, current, 'expired', 'Prazo do envio vencido.')
    else:
        await _deliver(notification, channel, settings, current)

    if notification.status in {SENT, FAILED}:
        event_type = (
            'NOTIFICATION_SENT'
            if notification.status == SENT
            else 'NOTIFICATION_FAILED'
        )
        event = audit_event(notification, event_type, None)
        if event is not None:
            session.add(event)
    _log(notification, 'notification_processed')
    await session.commit()
    return True


async def run_forever(settings: Settings) -> None:  # pragma: no cover
    from pivma.core.database import engine  # noqa: PLC0415

    channel = get_email_channel(settings)
    logger = get_operational_logger()
    if channel is None:
        logger.warning('notification_worker_without_channel')
    logger.info('notification_worker_started')
    while True:
        try:
            if channel is not None:
                async with AsyncSession(
                    engine, expire_on_commit=False
                ) as session:
                    while await process_next(session, channel, settings):
                        pass
        except (DBAPIError, OSError) as exc:
            # Banco ainda subindo ou fora do ar: tenta de novo no próximo
            # ciclo, sem derrubar o processo.
            logger.warning(
                'notification_worker_db_unavailable', error=type(exc).__name__
            )
        await asyncio.sleep(settings.NOTIFICATION_POLL_SECONDS)


def main() -> None:  # pragma: no cover
    setup_logging()
    asyncio.run(run_forever(get_settings()))


if __name__ == '__main__':  # pragma: no cover
    main()
