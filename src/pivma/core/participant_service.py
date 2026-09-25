"""Criação de designação compartilhada entre designação direta (Spec 006) e
aceite de convite (Spec 028).

Extraído do que antes vivia só em ``routers/process_participants.py`` para
que o aceite de convite (``invite_service.accept_invite``) crie a
``Assignment`` pelo mesmo caminho, sem duplicar validação (research.md,
Fase 4, T063) — nenhuma regra nova aqui, só reaproveito.
"""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    LABORATORY_ROLE_KEYS,
    has_active_laboratory_affiliation,
)
from pivma.core.database.models import (
    Assignment,
    AuditEvent,
    Laboratory,
    ProcessInstance,
    User,
)
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    _maybe_close_role_assignment_activity,  # noqa: PLC2701
)


def _assignment_event_context(
    assignment: Assignment, *, result: str, source: str
) -> dict:
    return {
        'assignment_id': str(assignment.id),
        'participant_user_id': str(assignment.user_id),
        'role_key': assignment.role_key,
        'laboratory_id': (
            str(assignment.laboratory_id)
            if assignment.laboratory_id is not None
            else None
        ),
        'result': result,
        'source': source,
    }


async def create_assignment(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process: ProcessInstance,
    *,
    user_id: UUID,
    role_key: str,
    laboratory_id: UUID | None,
    actor_id: UUID,
    source: str,
) -> Assignment:
    """Cria a designação, o evento de auditoria e fecha a etapa se aplicável.

    Não comita — quem chama decide o limite da transação, igual ao padrão
    já usado pelo restante do motor de processos. Levanta ``NotFoundError``/
    ``ConflictError`` (já usadas pelo resto do projeto, ``process_engine``)
    em vez de ``HTTPException`` porque este módulo é chamado por dois
    routers diferentes (``process_participants`` e ``invites``).
    """
    target_user = await session.get(User, user_id)
    if target_user is None:
        raise NotFoundError('Usuário não encontrado.')
    if target_user.deleted_at is not None:
        raise ConflictError('Usuário inativo.')

    if role_key in LABORATORY_ROLE_KEYS:
        laboratory = await session.get(Laboratory, laboratory_id)
        if laboratory is None:
            raise NotFoundError('Laboratório não encontrado.')
        if laboratory.deleted_at is not None:
            raise ConflictError('Laboratório inativo.')
        if not await has_active_laboratory_affiliation(
            session, user_id, laboratory_id
        ):
            raise ConflictError(
                'Usuário sem vínculo laboratorial vigente com o laboratório.'
            )

    assignment = Assignment(
        process_instance_id=process.id,
        user_id=user_id,
        role_key=role_key,
        assigned_by=actor_id,
        laboratory_id=laboratory_id,
    )
    assignment.set_creation_audit(actor_id)
    session.add(assignment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise ConflictError(
            'Já existe uma designação ativa para este processo, '
            'usuário e papel.'
        ) from None

    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=actor_id,
            event_type='PARTICIPANT_ASSIGNED',
            context_data=_assignment_event_context(
                assignment, result='success', source=source
            ),
        )
    )
    await _maybe_close_role_assignment_activity(
        session, process, role_key, actor_id
    )
    return assignment
