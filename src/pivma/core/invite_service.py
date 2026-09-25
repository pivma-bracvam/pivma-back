"""Convite de designação por link (Spec 028).

Um convite oferece um papel de processo a um e-mail antes de a pessoa
necessariamente ter conta no sistema. O aceite cria uma `Assignment` pelo
mesmo caminho da designação direta (Spec 006) — este módulo nunca duplica
essa regra, só resolve o que é específico do convite: token, expiração,
correspondência de e-mail e o ciclo pending/accepted/revoked de uma única
linha mutável (research.md R1/R2).
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import LABORATORY_ROLE_KEYS
from pivma.core.database.models import (
    AuditEvent,
    Laboratory,
    ProcessInstance,
    RoleAssignmentInvite,
    User,
)
from pivma.core.participant_service import create_assignment
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    _find_role_assignment_activity,  # noqa: PLC2701
    _maybe_close_role_assignment_activity,  # noqa: PLC2701
)

PENDING = 'pending'
ACCEPTED = 'accepted'
REVOKED = 'revoked'


def generate_invite_token() -> str:
    """Token bruto de uso único, devolvido só na criação/reenvio."""
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    """Hash determinístico persistido em `token_hash` — nunca o valor bruto."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def compute_expires_at(hours: int, *, now: datetime | None = None) -> datetime:
    base = now if now is not None else datetime.utcnow()
    return base + timedelta(hours=hours)


def mask_email(email: str) -> str:
    """E-mail mascarado para a pré-visualização pública do convite."""
    local, _, domain = email.partition('@')
    if not domain:
        return email
    if len(local) <= 1:
        masked_local = '*' * len(local)
    else:
        masked_local = local[0] + '*' * (len(local) - 1)
    return f'{masked_local}@{domain}'


def is_expired(
    invite: RoleAssignmentInvite, *, now: datetime | None = None
) -> bool:
    """Expirado é estado derivado — nunca gravado (data-model.md §1)."""
    current = now if now is not None else datetime.utcnow()
    return invite.status == PENDING and invite.expires_at < current


def invite_public_kwargs(invite: RoleAssignmentInvite) -> dict:
    """Campos comuns a `InvitePublic`/`InviteCreatedResponse`.

    Compartilhado entre os dois routers que expõem convites
    (``process_participants`` e ``invites``) para não duplicar a leitura
    dos mesmos 13 campos.
    """
    return {
        'id': invite.id,
        'process_id': invite.process_instance_id,
        'role_key': invite.role_key,
        'laboratory_id': invite.laboratory_id,
        'email': invite.email,
        'channel': invite.channel,
        'status': invite.status,
        'expired': is_expired(invite),
        'expires_at': invite.expires_at,
        'created_by': invite.created_by,
        'created_at': invite.created_at,
        'accepted_at': invite.accepted_at,
        'accepted_by': invite.accepted_by,
        'revoked_at': invite.revoked_at,
        'revoked_by': invite.revoked_by,
    }


async def create_invite(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process: ProcessInstance,
    *,
    email: str,
    role_key: str,
    laboratory_id: UUID | None,
    channel: str,
    actor_id: UUID,
    expiration_hours: int,
) -> tuple[RoleAssignmentInvite, str]:
    """Cria um convite (FR-002 a FR-007). Não comita.

    Retorna o convite e o token bruto — quem chama devolve o token só nesta
    resposta (e na de reenvio); ele nunca é lido de volta do banco.
    """
    if role_key in LABORATORY_ROLE_KEYS:
        laboratory = await session.get(Laboratory, laboratory_id)
        if laboratory is None:
            raise NotFoundError('Laboratório não encontrado.')
        if laboratory.deleted_at is not None:
            raise ConflictError('Laboratório inativo.')

    token = generate_invite_token()
    invite = RoleAssignmentInvite(
        process_instance_id=process.id,
        role_key=role_key,
        email=email,
        token_hash=hash_invite_token(token),
        expires_at=compute_expires_at(expiration_hours),
        laboratory_id=laboratory_id,
        channel=channel,
        status=PENDING,
    )
    invite.set_creation_audit(actor_id)
    session.add(invite)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise ConflictError(
            'Já existe um convite pendente para este processo, '
            'papel e e-mail.'
        ) from None

    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=actor_id,
            event_type='INVITE_CREATED',
            context_data={
                'invite_id': str(invite.id),
                'role_key': role_key,
                'email': email,
                'channel': channel,
            },
        )
    )
    return invite, token


async def _role_assignment_activity_is_completed(
    session: AsyncSession, invite: RoleAssignmentInvite
) -> bool:
    """FR-012/FR-013: reenvio e revogação só valem antes do encerramento.

    Um convite pode continuar `pending` mesmo depois que a etapa já fechou
    por outra via — ex. alguém foi designado diretamente antes de este
    convite existir (papel sem titularidade única, FR-019, aceita convite
    "tardio" mesmo já preenchido). `status == 'pending'` sozinho não basta.
    """
    process = await session.get(
        ProcessInstance, invite.process_instance_id
    )
    if process is None:
        return False
    act = await _find_role_assignment_activity(
        session, process, invite.role_key
    )
    return act is not None and act.status == 'COMPLETED'


async def resend_invite(
    session: AsyncSession,
    invite: RoleAssignmentInvite,
    *,
    actor_id: UUID,
    expiration_hours: int,
) -> tuple[RoleAssignmentInvite, str]:
    """Renova token/prazo na mesma linha (FR-012, research.md R2)."""
    if invite.status != PENDING:
        raise ConflictError('Convite não está mais pendente.')
    if await _role_assignment_activity_is_completed(session, invite):
        raise ConflictError(
            'A etapa de atribuição de cargo deste convite já se encerrou.'
        )

    previous_expires_at = invite.expires_at
    token = generate_invite_token()
    invite.token_hash = hash_invite_token(token)
    invite.expires_at = compute_expires_at(expiration_hours)
    invite.set_update_audit(actor_id)

    session.add(
        AuditEvent(
            process_instance_id=invite.process_instance_id,
            user_id=actor_id,
            event_type='INVITE_RESENT',
            context_data={
                'invite_id': str(invite.id),
                'previous_expires_at': previous_expires_at.isoformat(),
                'new_expires_at': invite.expires_at.isoformat(),
            },
        )
    )
    return invite, token


async def revoke_invite(
    session: AsyncSession, invite: RoleAssignmentInvite, *, actor_id: UUID
) -> RoleAssignmentInvite:
    """Marca o convite como revogado (FR-013)."""
    if invite.status != PENDING:
        raise ConflictError('Convite não está mais pendente.')
    if await _role_assignment_activity_is_completed(session, invite):
        raise ConflictError(
            'A etapa de atribuição de cargo deste convite já se encerrou.'
        )

    invite.status = REVOKED
    invite.revoked_at = datetime.utcnow()
    invite.revoked_by = actor_id
    invite.set_update_audit(actor_id)

    session.add(
        AuditEvent(
            process_instance_id=invite.process_instance_id,
            user_id=actor_id,
            event_type='INVITE_REVOKED',
            context_data={
                'invite_id': str(invite.id),
                'role_key': invite.role_key,
            },
        )
    )
    return invite


async def get_invite_by_token(
    session: AsyncSession, token: str
) -> RoleAssignmentInvite | None:
    return await session.scalar(
        select(RoleAssignmentInvite).where(
            RoleAssignmentInvite.token_hash == hash_invite_token(token),
            RoleAssignmentInvite.deleted_at.is_(None),
        )
    )


async def accept_invite(
    session: AsyncSession, invite: RoleAssignmentInvite, current_user: User
) -> tuple[RoleAssignmentInvite, UUID]:
    """Aceita o convite (FR-008/FR-009/FR-010/FR-011). Não comita.

    Retorna o convite atualizado e o id da `Assignment` criada. Levanta
    ``ConflictError`` para estado inválido — a checagem de e-mail (FR-010)
    é responsabilidade do chamador (router), que já sabe traduzir isso para
    403 em vez de 409.
    """
    if invite.status != PENDING:
        raise ConflictError('Convite não está mais pendente.')
    if is_expired(invite):
        raise ConflictError('Convite expirado.')

    process = await session.get(ProcessInstance, invite.process_instance_id)
    if process is None:
        raise NotFoundError('Processo não encontrado.')

    assignment = await create_assignment(
        session,
        process,
        user_id=current_user.id,
        role_key=invite.role_key,
        laboratory_id=invite.laboratory_id,
        actor_id=current_user.id,
        source='invite',
    )

    invite.status = ACCEPTED
    invite.accepted_at = datetime.utcnow()
    invite.accepted_by = current_user.id
    invite.set_update_audit(current_user.id)

    session.add(
        AuditEvent(
            process_instance_id=invite.process_instance_id,
            user_id=current_user.id,
            event_type='INVITE_ACCEPTED',
            context_data={
                'invite_id': str(invite.id),
                'role_key': invite.role_key,
                'assignment_id': str(assignment.id),
            },
        )
    )
    # `create_assignment` já chama `_maybe_close_role_assignment_activity`,
    # mas naquele momento este convite ainda estava `pending` (FR-017) — se
    # ele era o último pendente do papel, é preciso reavaliar agora que
    # acabou de virar `accepted`.
    await _maybe_close_role_assignment_activity(
        session, process, invite.role_key, current_user.id
    )
    return invite, assignment.id
