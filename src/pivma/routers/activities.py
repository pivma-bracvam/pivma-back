"""Kanban de pendências consolidado (Spec 018, User Stories 1-3).

Endpoint de leitura novo, não facilitador de carga (Constituição Princípio
II): nenhuma tela hoje consegue montar, sem uma consulta por processo, a
visão de todas as atividades — incluindo as ainda não iniciadas, sem
`Task`/`ActivityRun` algum — de todos os métodos visíveis ao usuário atual.
"""

from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pivma.core.authorization import (
    GLOBAL_ACTIVITY_CARGOS,
    can_manage_participants,
)
from pivma.core.database.models import (
    AccessProfile,
    ActivityDependency,
    ActivityInstance,
    ActivityRun,
    Assignment,
    ProcessInstance,
    ProcessTemplateVersion,
    Task,
    User,
    UserAccessProfile,
)
from pivma.core.process_engine import (
    KANBAN_EM_ANDAMENTO,
    KANBAN_EM_ATRASO,
    classify_kanban_column,
    process_visibility_clause,
    utc_now,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    KanbanCardItem,
    KanbanCardProcess,
    KanbanColumn,
    KanbanPage,
)

router = APIRouter(prefix='/activities', tags=['Activities'])

MAX_PAGE_SIZE = 200
_GLOBAL_CARGO_SYSTEM_KEYS = {'admin': 'administrator', 'bracvam': 'bracvam'}


def _latest_run(activity: ActivityInstance) -> ActivityRun | None:
    active_runs = [r for r in activity.runs if r.deleted_at is None]
    if not active_runs:
        return None
    return max(active_runs, key=lambda r: r.run_number)


def _latest_task(run: ActivityRun | None) -> Task | None:
    if run is None:
        return None
    active_tasks = [t for t in run.tasks if t.deleted_at is None]
    return active_tasks[0] if active_tasks else None


def _activity_definition(
    process: ProcessInstance, activity_key: str
) -> dict[str, Any] | None:
    payload = process.template_version.definition_payload or {}
    for phase in payload.get('phases', []):
        for activity in phase.get('activities', []):
            if activity.get('key') == activity_key:
                return activity
    return None


def _resolve_cargo(
    activity: ActivityInstance,
    task: Task | None,
    process: ProcessInstance,
) -> str:
    if task is not None and task.assigned_role:
        return task.assigned_role
    definition = _activity_definition(process, activity.key)
    if definition:
        return definition.get('assigned_role', 'proponent')
    return 'proponent'


async def _holders_index(
    session: Session, process_ids: set[UUID], cargos: set[str]
) -> dict[tuple[UUID | None, str], set[UUID]]:
    """Pré-carrega, em 2 consultas, quem ocupa cada (processo, cargo).

    Evita N+1 chamando `resolve_activity_holders` uma vez por item — Spec
    018 FR-012 exige que o Kanban permaneça utilizável para centenas de
    processos numa única consulta.
    """
    index: dict[tuple[UUID | None, str], set[UUID]] = {}

    contextual_cargos = cargos - GLOBAL_ACTIVITY_CARGOS
    if contextual_cargos and process_ids:
        rows = await session.execute(
            select(
                Assignment.process_instance_id,
                Assignment.role_key,
                Assignment.user_id,
            ).where(
                Assignment.process_instance_id.in_(process_ids),
                Assignment.role_key.in_(contextual_cargos),
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
            )
        )
        for process_id, role_key, user_id in rows:
            index.setdefault((process_id, role_key), set()).add(user_id)

    global_cargos = cargos & GLOBAL_ACTIVITY_CARGOS
    if global_cargos:
        system_keys = {_GLOBAL_CARGO_SYSTEM_KEYS[c] for c in global_cargos}
        rows = await session.execute(
            select(AccessProfile.system_key, User.id)
            .select_from(UserAccessProfile)
            .join(User, User.id == UserAccessProfile.user_id)
            .join(
                AccessProfile,
                AccessProfile.id == UserAccessProfile.profile_id,
            )
            .where(
                AccessProfile.system_key.in_(system_keys),
                UserAccessProfile.deleted_at.is_(None),
                AccessProfile.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        )
        by_system_key: dict[str, set[UUID]] = {}
        for system_key, user_id in rows:
            by_system_key.setdefault(system_key, set()).add(user_id)
        for cargo in global_cargos:
            index[(None, cargo)] = by_system_key.get(
                _GLOBAL_CARGO_SYSTEM_KEYS[cargo], set()
            )

    return index


def _holders_for(
    index: dict[tuple[UUID | None, str], set[UUID]],
    process_id: UUID,
    cargo: str,
) -> set[UUID]:
    if cargo in GLOBAL_ACTIVITY_CARGOS:
        return index.get((None, cargo), set())
    return index.get((process_id, cargo), set())


@dataclass
class _KanbanContext:
    """Dados pré-calculados, compartilhados por todos os cartões da página."""

    session: Session
    current_user_id: UUID
    holders_index: dict[tuple[UUID | None, str], set[UUID]]
    manager_process_ids: set[UUID]
    now: datetime


async def _blocking_context(
    ctx: _KanbanContext, activity: ActivityInstance, process: ProcessInstance
) -> tuple[str | None, str | None, str | None]:
    if activity.status != 'BLOCKED':
        return None, None, None
    dep_stmt = select(ActivityDependency).where(
        ActivityDependency.dependent_activity_id == activity.id,
        ActivityDependency.deleted_at.is_(None),
        ActivityDependency.required_activity_id.is_not(None),
    )
    dep = (await ctx.session.execute(dep_stmt)).scalars().first()
    if dep is None:
        return None, None, None
    required = await ctx.session.get(
        ActivityInstance, dep.required_activity_id
    )
    if required is None:
        return None, None, None
    req_run = _latest_run(required)
    req_task = _latest_task(req_run)
    cargo = _resolve_cargo(required, req_task, process)
    return required.key, required.status, cargo


async def _build_card(
    ctx: _KanbanContext,
    activity: ActivityInstance,
    process: ProcessInstance,
) -> KanbanCardItem:
    run = _latest_run(activity)
    task = _latest_task(run)
    cargo = _resolve_cargo(activity, task, process)
    definition = _activity_definition(process, activity.key)
    sla_hours = definition.get('sla_hours') if definition else None

    column: KanbanColumn = classify_kanban_column(
        activity_status=activity.status,
        run_started_at=run.started_at if run else None,
        sla_hours=sla_hours,
        now=ctx.now,
    )
    blocking_key, blocking_status, blocking_cargo = await _blocking_context(
        ctx, activity, process
    )

    # `actionable_now`/`cargo_unassigned` só fazem sentido enquanto há uma
    # ação pendente de fato (`EM_ANDAMENTO`/`EM_ATRASO`) — uma atividade
    # `CONCLUIDO` já não é "minha vez" de ninguém, e uma `NAO_INICIADO`
    # ainda não tem pendência para sinalizar cargo sem ocupante.
    is_pending = column in {KANBAN_EM_ANDAMENTO, KANBAN_EM_ATRASO}
    holders = _holders_for(ctx.holders_index, process.id, cargo)
    cargo_unassigned = (
        is_pending and not holders and process.id in ctx.manager_process_ids
    )

    return KanbanCardItem(
        activity_id=activity.id,
        activity_key=activity.key,
        activity_name=activity.name,
        column=column,
        cargo=cargo,
        process=KanbanCardProcess(
            id=process.id,
            code=process.code,
            title=process.title,
            template_key=process.template_version.template.key,
        ),
        blocked_reason=activity.blocked_reason,
        blocking_activity_key=blocking_key,
        blocking_activity_status=blocking_status,
        blocking_activity_cargo=blocking_cargo,
        run_started_at=run.started_at if run else None,
        sla_hours=sla_hours,
        completed_at=run.completed_at if run else None,
        cargo_unassigned=cargo_unassigned,
        actionable_now=is_pending and ctx.current_user_id in holders,
    )


async def _load_visible_activities(
    session: Session, current_user_id: UUID, process_id: UUID | None
) -> list[ActivityInstance]:
    stmt = (
        select(ActivityInstance)
        .join(ActivityInstance.process_instance)
        .where(ActivityInstance.deleted_at.is_(None))
        .options(
            selectinload(ActivityInstance.runs).selectinload(
                ActivityRun.tasks
            ),
            selectinload(ActivityInstance.process_instance)
            .selectinload(ProcessInstance.template_version)
            .selectinload(ProcessTemplateVersion.template),
        )
    )
    visibility = await process_visibility_clause(session, current_user_id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    if process_id is not None:
        stmt = stmt.where(ActivityInstance.process_instance_id == process_id)
    return list((await session.execute(stmt)).scalars().unique().all())


async def _build_context(
    session: Session,
    current_user_id: UUID,
    activities: list[ActivityInstance],
) -> _KanbanContext:
    process_ids = {a.process_instance_id for a in activities}
    cargos = {
        _resolve_cargo(a, _latest_task(_latest_run(a)), a.process_instance)
        for a in activities
    }
    holders_index = await _holders_index(session, process_ids, cargos)
    manager_process_ids = {
        pid
        for pid in process_ids
        if await can_manage_participants(session, current_user_id, pid)
    }
    return _KanbanContext(
        session=session,
        current_user_id=current_user_id,
        holders_index=holders_index,
        manager_process_ids=manager_process_ids,
        now=utc_now(),
    )


def _counts_by_column(cards: list[KanbanCardItem]) -> dict[str, int]:
    counts = {
        'NAO_INICIADO': 0,
        'EM_ANDAMENTO': 0,
        'EM_ATRASO': 0,
        'CONCLUIDO': 0,
    }
    for card in cards:
        counts[card.column] += 1
    return counts


@router.get('/kanban', response_model=KanbanPage, status_code=HTTPStatus.OK)
async def get_kanban(  # noqa: PLR0913, PLR0917 - filtros/paginação da query
    session: Session,
    current_user: CurrentUser,
    column: KanbanColumn | None = None,
    process_id: UUID | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
):
    activities = await _load_visible_activities(
        session, current_user.id, process_id
    )
    ctx = await _build_context(session, current_user.id, activities)
    cards = [
        await _build_card(ctx, activity, activity.process_instance)
        for activity in activities
    ]

    counts_by_column = _counts_by_column(cards)
    if column is not None:
        cards = [c for c in cards if c.column == column]

    total = len(cards)
    start = (page - 1) * size
    page_items = cards[start : start + size]

    return KanbanPage(
        items=page_items,
        total=total,
        page=page,
        size=size,
        counts_by_column=counts_by_column,
    )
