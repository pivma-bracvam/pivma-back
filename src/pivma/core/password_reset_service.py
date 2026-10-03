"""Recuperação de senha por token temporário (Spec 039).

O token bruto só existe no link do e-mail; o banco guarda o hash SHA-256.
As funções não comitam: a rota confirma a transação.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import PasswordResetToken, User
from pivma.core.logging import get_operational_logger
from pivma.core.settings import Settings
from pivma.notifications.channels import email_channel_available
from pivma.notifications.renderers import PASSWORD_RESET_EMAIL
from pivma.notifications.service import (
    cancel_pending_notifications,
    enqueue_notification,
)

TOKEN_TTL = timedelta(minutes=30)
SUBJECT_TYPE = 'password_reset'
NEUTRAL_MESSAGE = (
    'Se o e-mail estiver cadastrado, as instruções foram enviadas.'
)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


async def request_password_reset(
    session: AsyncSession, settings: Settings, email: str
) -> None:
    """Emite um token e registra o e-mail, se houver conta ativa."""
    template = settings.PASSWORD_RESET_URL_TEMPLATE
    if not (email_channel_available(settings) and template):
        get_operational_logger().warning('password_reset_unavailable')
        return

    # O bloqueio da conta serializa pedidos simultâneos: no fim, só o
    # último token fica válido (FR-005).
    user = await session.scalar(
        select(User)
        .where(
            func.lower(User.email) == func.lower(email),
            User.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if user is None:
        return

    now = datetime.utcnow()
    await session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.deleted_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(deleted_at=now)
    )
    subject = (SUBJECT_TYPE, user.id)
    await cancel_pending_notifications(
        session, subject=subject, reason='cancelled_resent', actor_id=None
    )

    token = generate_reset_token()
    expires_at = now + TOKEN_TTL
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(token),
            expires_at=expires_at,
        )
    )
    await enqueue_notification(
        session,
        settings,
        kind=PASSWORD_RESET_EMAIL,
        channel='email',
        recipient=user.email,
        payload={
            'reset_url': template.replace('{token}', token),
            'expires_at': expires_at.isoformat(),
        },
        actor_id=None,
        subject=subject,
        expires_at=expires_at,
    )


async def reset_password(
    session: AsyncSession, token: str, new_password_hash: str
) -> bool:
    """Troca a senha se o token for válido. Devolve se trocou."""
    now = datetime.utcnow()
    # Bloqueia primeiro a conta, na mesma ordem de request_password_reset;
    # depois o token garante uso único sob concorrência (FR-014).
    user = await session.scalar(
        select(User)
        .join(PasswordResetToken, User.id == PasswordResetToken.user_id)
        .where(
            PasswordResetToken.token_hash == hash_reset_token(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.deleted_at.is_(None),
            PasswordResetToken.expires_at > now,
            User.deleted_at.is_(None),
        )
        .with_for_update(of=User)
    )
    if user is None:
        return False

    row = await session.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token_hash == hash_reset_token(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.deleted_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )
    if row is None:
        return False

    user.password_hash = new_password_hash
    row.used_at = now
    user.set_update_audit(user.id)
    row.set_update_audit(user.id)
    return True
