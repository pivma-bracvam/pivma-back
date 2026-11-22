"""Alerts: avisos dentro da plataforma (Spec 047).

Contrato em `specs/047-alerts/contracts/alerts-api.md`. Cada gatilho chama
este módulo depois de gravar o próprio `AuditEvent`, na mesma sessão e sem
`commit` (FR-003). A fila de e-mail (`pivma.notifications`) não muda.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    effective_assignment_clause,
    global_cargo_holder_ids,
    task_can_act_clause,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Alert,
    Assignment,
    Laboratory,
    ProcessInstance,
    Task,
    User,
)
from pivma.core.listing import paginate_query

TASK_OPENED = 'task_opened'
SUBMISSION_STATUS_CHANGED = 'submission_status_changed'
STRUCTURE_APPROVED = 'structure_approved'
PROCESS_WITHDRAWN = 'process_withdrawn'
ASSIGNMENT_CREATED = 'assignment_created'
ASSIGNMENT_REVOKED = 'assignment_revoked'
ASSIGNMENT_EFFECTIVENESS_CHANGED = 'assignment_effectiveness_changed'
LABORATORY_RUN_COMPLETED = 'laboratory_run_completed'
LABORATORY_RUN_WAIVED = 'laboratory_run_waived'
SAMPLE_NONCONFORMITY_DECIDED = 'sample_nonconformity_decided'

TARGET_PROCESS = 'process'
TARGET_TASK = 'task'
TARGET_SAMPLE_RECEIPT = 'sample_receipt'


async def add_alerts(  # noqa: PLR0913
    session: AsyncSession,
    *,
    kind: str,
    user_ids: Iterable[UUID],
    process_id: UUID,
    target_type: str,
    params: dict[str, Any],
    actor_id: UUID | None,
    target_id: UUID | None = None,
) -> list[Alert]:
    """Um alert por destinatário com conta ativa, sem o autor. Não comita.

    Um usuário qualificado por mais de um cargo recebe um só (FR-005); quem
    fez a ação não recebe (FR-006); conta desativada não recebe (FR-004).
    """
    recipients = set(user_ids) - {actor_id}
    if not recipients:
        return []
    active = (
        await session.scalars(
            select(User.id)
            .where(User.id.in_(recipients), User.deleted_at.is_(None))
            .order_by(User.id)
        )
    ).all()
    alerts = []
    for user_id in active:
        alert = Alert(
            user_id=user_id,
            kind=kind,
            target_type=target_type,
            process_instance_id=process_id,
            target_id=target_id,
            params=params,
        )
        alert.set_creation_audit(actor_id)
        session.add(alert)
        alerts.append(alert)
    return alerts


def _owned(user_id: UUID):
    return select(Alert).where(
        Alert.user_id == user_id, Alert.deleted_at.is_(None)
    )


async def list_alerts(
    session: AsyncSession,
    user_id: UUID,
    *,
    unread: bool | None,
    page: int,
    per_page: int,
) -> tuple[list[Alert], int]:
    """Página dos alerts do usuário, do mais recente ao mais antigo (R8)."""
    stmt = _owned(user_id)
    if unread is not None:
        stmt = stmt.where(
            Alert.read_at.is_(None) if unread else Alert.read_at.is_not(None)
        )
    return await paginate_query(
        session,
        stmt,
        order_by=(Alert.created_at.desc(), Alert.id.desc()),
        page=page,
        per_page=per_page,
    )


async def unread_count(session: AsyncSession, user_id: UUID) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.user_id == user_id,
            Alert.read_at.is_(None),
            Alert.deleted_at.is_(None),
        )
    )


def _mark_read(user_id: UUID):
    """Só muda o que ainda está não lido: idempotente e sem trava (R9)."""
    return (
        update(Alert)
        .where(
            Alert.user_id == user_id,
            Alert.read_at.is_(None),
            Alert.deleted_at.is_(None),
        )
        .values(
            read_at=datetime.utcnow(),
            updated_at=func.now(),
            updated_by=user_id,
        )
        .execution_options(synchronize_session=False)
    )


async def mark_read(
    session: AsyncSession, user_id: UUID, alert_id: UUID
) -> Alert | None:
    """Marca um alert do usuário. `None` se não existe ou é de outro."""
    await session.execute(_mark_read(user_id).where(Alert.id == alert_id))
    await session.commit()
    return await session.scalar(
        _owned(user_id)
        .where(Alert.id == alert_id)
        .execution_options(populate_existing=True)
    )


async def mark_all_read(session: AsyncSession, user_id: UUID) -> int:
    result = await session.execute(_mark_read(user_id))
    await session.commit()
    return result.rowcount


async def alert_task_opened(
    session: AsyncSession, task: Task, actor_id: UUID | None
) -> list[Alert]:
    """`task_opened` para quem pode agir na tarefa nova (research R3).

    Candidatos: designações ativas no processo e perfis globais cujo cargo
    está em `edit_roles`. Fica quem passa na mesma regra de `can_act` de
    `GET /tasks`, que já trata laboratório e conflito de interesse.
    """
    run = await session.get(ActivityRun, task.activity_run_id)
    act = await session.get(ActivityInstance, run.activity_instance_id)
    process = await session.get(ProcessInstance, act.process_instance_id)
    candidates = set(
        await session.scalars(
            select(Assignment.user_id).where(
                Assignment.process_instance_id == process.id,
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
            )
        )
    ) | await global_cargo_holder_ids(session, act.edit_roles)
    candidates.discard(actor_id)
    recipients = [
        user_id
        for user_id in sorted(candidates)
        if await _can_act(session, task, user_id)
    ]
    params = {
        'process_code': process.code,
        'process_title': process.title,
        'activity_key': act.key,
        'activity_name': act.name,
        'run_number': run.run_number,
        'due_date': task.due_date.isoformat() if task.due_date else None,
    }
    if run.laboratory_id is not None:
        laboratory = await session.get(Laboratory, run.laboratory_id)
        params['laboratory_name'] = laboratory.name
    return await add_alerts(
        session,
        kind=TASK_OPENED,
        user_ids=recipients,
        process_id=process.id,
        target_type=TARGET_TASK,
        target_id=task.id,
        params=params,
        actor_id=actor_id,
    )


async def _can_act(session: AsyncSession, task: Task, user_id: UUID) -> bool:
    clause = await task_can_act_clause(session, user_id)
    return bool(
        await session.scalar(
            select(Task.id)
            .join(Task.activity_run)
            .join(ActivityRun.activity_instance)
            .where(Task.id == task.id, clause)
        )
    )


async def participant_user_ids(  # noqa: PLR0913
    session: AsyncSession,
    process_id: UUID,
    *,
    role_keys: Iterable[str] | None = None,
    exclude_role_keys: Iterable[str] = (),
    laboratory_id: UUID | None = None,
    effective: bool = True,
) -> set[UUID]:
    """Quem tem designação ativa no processo, com os filtros pedidos.

    Com `effective`, cargo laboratorial só conta com vínculo ativo (Spec 035).
    A conta ativa é conferida em `add_alerts`.
    """
    stmt = select(Assignment.user_id).where(
        Assignment.process_instance_id == process_id,
        Assignment.revoked_at.is_(None),
        Assignment.deleted_at.is_(None),
    )
    if role_keys is not None:
        stmt = stmt.where(Assignment.role_key.in_(list(role_keys)))
    excluded = list(exclude_role_keys)
    if excluded:
        stmt = stmt.where(Assignment.role_key.not_in(excluded))
    if laboratory_id is not None:
        stmt = stmt.where(Assignment.laboratory_id == laboratory_id)
    if effective:
        stmt = stmt.where(effective_assignment_clause())
    return set(await session.scalars(stmt))


async def alert_process(  # noqa: PLR0913
    session: AsyncSession,
    *,
    kind: str,
    process: ProcessInstance,
    user_ids: Iterable[UUID],
    actor_id: UUID | None,
    params: dict[str, Any] | None = None,
    target_type: str = TARGET_PROCESS,
    target_id: UUID | None = None,
) -> list[Alert]:
    """Alert com o código e o título do processo, mais `params` (R12)."""
    return await add_alerts(
        session,
        kind=kind,
        user_ids=user_ids,
        process_id=process.id,
        target_type=target_type,
        target_id=target_id,
        params={
            'process_code': process.code,
            'process_title': process.title,
            **(params or {}),
        },
        actor_id=actor_id,
    )


async def alert_assignment(
    session: AsyncSession,
    kind: str,
    assignment: Assignment,
    actor_id: UUID | None,
    params: dict[str, Any] | None = None,
) -> list[Alert]:
    """Alert de designação para o próprio designado (US4)."""
    process = await session.get(
        ProcessInstance, assignment.process_instance_id
    )
    laboratory = (
        await session.get(Laboratory, assignment.laboratory_id)
        if assignment.laboratory_id
        else None
    )
    return await alert_process(
        session,
        kind=kind,
        process=process,
        user_ids=[assignment.user_id],
        actor_id=actor_id,
        params={
            'role_key': assignment.role_key,
            'laboratory_name': laboratory.name if laboratory else None,
            **(params or {}),
        },
    )
