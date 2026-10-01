"""Pedido e cancelamento de envios (Spec 036).

Contrato em `contracts/notifications-module.md` da spec.

`enqueue_notification` só adiciona a linha à sessão de quem chama: o envio
existe se, e somente se, a transação da operação de negócio for confirmada
(FR-002). Quem envia é `pivma.notifications.worker`.
"""

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import AuditEvent, Notification
from pivma.core.settings import Settings
from pivma.notifications.channels import email_channel_available
from pivma.notifications.crypto import encrypt_payload
from pivma.notifications.renderers import get_renderer

PENDING = 'pending'
SENT = 'sent'
FAILED = 'failed'
CANCELLED = 'cancelled'

Subject = tuple[str, UUID]


class ChannelUnavailableError(Exception):
    """O canal pedido não está configurado nesta implantação (FR-019)."""


def retry_delay(attempt: int, settings: Settings) -> timedelta:
    """Intervalo antes da próxima tentativa, depois da tentativa `attempt`."""
    seconds = settings.NOTIFICATION_RETRY_BASE_SECONDS * 2 ** (attempt - 1)
    return timedelta(
        seconds=min(seconds, settings.NOTIFICATION_RETRY_MAX_SECONDS)
    )


async def enqueue_notification(  # noqa: PLR0913
    session: AsyncSession,
    settings: Settings,
    *,
    kind: str,
    channel: Literal['email'],
    recipient: str,
    payload: dict[str, Any],
    actor_id: UUID | None,
    subject: Subject | None = None,
    process_instance_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> Notification:
    """Registra um envio na sessão. Não comita."""
    get_renderer(kind)
    if channel != 'email' or not email_channel_available(settings):
        raise ChannelUnavailableError(
            'O envio por e-mail não está configurado.'
        )

    now = datetime.utcnow()
    notification = Notification(
        kind=kind,
        channel=channel,
        recipient=recipient,
        next_attempt_at=now,
        requested_at=now,
        payload_encrypted=encrypt_payload(
            payload, settings.NOTIFICATION_ENCRYPTION_KEY
        ),
        subject_type=subject[0] if subject else None,
        subject_id=subject[1] if subject else None,
        process_instance_id=process_instance_id,
        expires_at=expires_at,
    )
    notification.set_creation_audit(actor_id)
    session.add(notification)
    return notification


def finish(
    notification: Notification,
    status: str,
    *,
    now: datetime,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Leva o envio a um estado final e apaga o conteúdo (FR-009)."""
    notification.status = status
    notification.finished_at = now
    notification.payload_encrypted = None
    if status == SENT:
        notification.sent_at = now
    if error_code is not None:
        notification.error_code = error_code
    if error_detail is not None:
        notification.error_detail = error_detail[:500]


def audit_event(
    notification: Notification, event_type: str, user_id: UUID | None
) -> AuditEvent | None:
    """Evento da trilha, sem destinatário nem conteúdo (R11).

    `AuditEvent` exige processo: envio sem processo não gera evento.
    """
    if notification.process_instance_id is None:
        return None
    return AuditEvent(
        process_instance_id=notification.process_instance_id,
        user_id=user_id,
        event_type=event_type,
        context_data={
            'notification_id': str(notification.id),
            'kind': notification.kind,
            'channel': notification.channel,
            'subject_type': notification.subject_type,
            'subject_id': (
                str(notification.subject_id)
                if notification.subject_id
                else None
            ),
            'attempts': notification.attempts,
            'error_code': notification.error_code,
        },
    )


async def cancel_pending_notifications(
    session: AsyncSession,
    *,
    subject: Subject,
    reason: str,
    actor_id: UUID | None,
) -> int:
    """Cancela os envios ainda pendentes de um objeto. Não comita."""
    pending = (
        await session.scalars(
            select(Notification)
            .where(
                Notification.subject_type == subject[0],
                Notification.subject_id == subject[1],
                Notification.status == PENDING,
            )
            .with_for_update()
        )
    ).all()
    now = datetime.utcnow()
    for notification in pending:
        finish(notification, CANCELLED, now=now, error_code=reason)
        notification.set_update_audit(actor_id)
        event = audit_event(notification, 'NOTIFICATION_CANCELLED', actor_id)
        if event is not None:
            session.add(event)
    return len(pending)


async def latest_by_subject(
    session: AsyncSession, subject_type: str, subject_ids: list[UUID]
) -> dict[UUID, Notification]:
    """Envio mais recente de cada objeto, numa consulta só (R10)."""
    if not subject_ids:
        return {}
    rows = (
        await session.scalars(
            select(Notification)
            .where(
                Notification.subject_type == subject_type,
                Notification.subject_id.in_(subject_ids),
            )
            .distinct(Notification.subject_id)
            .order_by(
                Notification.subject_id, Notification.requested_at.desc()
            )
        )
    ).all()
    return {row.subject_id: row for row in rows}
