"""Criação de designação compartilhada entre designação direta (Spec 006) e
aceite de convite (Spec 028).

Extraído do que antes vivia só em ``routers/process_participants.py`` para
que o aceite de convite (``invite_service.accept_invite``) crie a
``Assignment`` pelo mesmo caminho, sem duplicar validação (research.md,
Fase 4, T063) — nenhuma regra nova aqui, só reaproveito.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    LABORATORY_ROLE_KEYS,
    effective_assignment_ids,
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
    IMMUTABLE_PROCESS_STATUSES,
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
        raise ConflictError('Usuário inativo.', code='inactive_entity')

    if role_key in LABORATORY_ROLE_KEYS:
        laboratory = await session.get(Laboratory, laboratory_id)
        if laboratory is None:
            raise NotFoundError('Laboratório não encontrado.')
        if laboratory.deleted_at is not None:
            raise ConflictError('Laboratório inativo.', code='inactive_entity')
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
            'usuário e papel.',
            code='duplicate',
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


EFFECTIVENESS_LOST = 'PARTICIPANT_EFFECTIVENESS_LOST'
EFFECTIVENESS_RESTORED = 'PARTICIPANT_EFFECTIVENESS_RESTORED'


@dataclass(frozen=True)
class LaboratoryDesignationSnapshot:
    """Designações laboratoriais candidatas e quais valiam antes da ação."""

    assignment_ids: list[UUID]
    effective_before: set[UUID]


async def snapshot_laboratory_designations(
    session: AsyncSession,
    *,
    laboratory_ids: Iterable[UUID],
    user_id: UUID | None = None,
) -> LaboratoryDesignationSnapshot:
    """Trava e registra a efetividade antes de uma ação institucional.

    Candidatas: designações ativas de cargo laboratorial dos laboratórios
    informados (e do usuário, se informado) em processos em andamento, não
    excluídos e fora dos status terminais (Spec 035, FR-008a). A trava
    serializa ações simultâneas sobre as mesmas designações, para que a
    segunda leia o estado já confirmado pela primeira (research R4).
    """
    laboratory_ids = list(laboratory_ids)
    if not laboratory_ids:
        return LaboratoryDesignationSnapshot([], set())
    stmt = (
        select(Assignment.id)
        .join(
            ProcessInstance,
            ProcessInstance.id == Assignment.process_instance_id,
        )
        .where(
            Assignment.role_key.in_(sorted(LABORATORY_ROLE_KEYS)),
            Assignment.laboratory_id.in_(laboratory_ids),
            Assignment.revoked_at.is_(None),
            Assignment.deleted_at.is_(None),
            ProcessInstance.deleted_at.is_(None),
            ProcessInstance.status.not_in(sorted(IMMUTABLE_PROCESS_STATUSES)),
        )
        .order_by(Assignment.id)
        .with_for_update(of=Assignment)
    )
    if user_id is not None:
        stmt = stmt.where(Assignment.user_id == user_id)
    assignment_ids = list(await session.scalars(stmt))
    return LaboratoryDesignationSnapshot(
        assignment_ids,
        await effective_assignment_ids(session, assignment_ids),
    )


async def record_laboratory_validity_changes(
    session: AsyncSession,
    snapshot: LaboratoryDesignationSnapshot,
    *,
    actor_id: UUID,
    reason: str,
) -> None:
    """Grava um evento por designação cuja efetividade mudou na ação.

    Compara com o `snapshot` depois do `flush` da ação: quem deixou de valer
    recebe `PARTICIPANT_EFFECTIVENESS_LOST`, quem voltou a valer
    `PARTICIPANT_EFFECTIVENESS_RESTORED` (Spec 035, FR-008 a FR-012a). Não
    comita: o evento vai na mesma transação da ação (FR-011).
    """
    if not snapshot.assignment_ids:
        return
    await session.flush()
    effective_after = await effective_assignment_ids(
        session, snapshot.assignment_ids
    )
    changes = {
        **dict.fromkeys(
            snapshot.effective_before - effective_after, EFFECTIVENESS_LOST
        ),
        **dict.fromkeys(
            effective_after - snapshot.effective_before,
            EFFECTIVENESS_RESTORED,
        ),
    }
    if not changes:
        return
    assignments = await session.scalars(
        select(Assignment)
        .where(Assignment.id.in_(changes))
        .order_by(Assignment.id)
    )
    for assignment in assignments:
        session.add(
            AuditEvent(
                process_instance_id=assignment.process_instance_id,
                user_id=actor_id,
                event_type=changes[assignment.id],
                context_data={
                    **_assignment_event_context(
                        assignment, result='success', source='institutional'
                    ),
                    'reason': reason,
                },
            )
        )
