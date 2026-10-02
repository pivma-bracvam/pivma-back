from datetime import UTC, datetime
from http import HTTPStatus
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import and_, any_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import aliased, selectinload

from pivma.core.authorization import (
    current_conflict_clause,
    global_cargos,
    laboratory_member_clause,
    laboratory_run_visibility_clause,
    process_cargos_scope,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Assignment,
    EvaluationRun,
    Phase,
    Task,
)
from pivma.core.errors import http_error
from pivma.core.listing import build_pagination
from pivma.core.process_engine import (
    NotFoundError,
    activity_view_clause,
    process_visibility_clause,
    require_activity_access,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    PhaseRef,
    ProcessRef,
    SortApplied,
    TaskDetail,
    TaskFacets,
    TaskFiltersApplied,
    TaskListResponse,
    TaskListSummary,
    TaskStatus,
    TaskSummary,
)

router = APIRouter(prefix='/tasks', tags=['Tasks'])


_SORT_COLUMNS = {'due_date': Task.due_date, 'created_at': Task.created_at}


def _current_run_clause():
    """Só a execução de maior número de cada atividade (Spec 032, R3)."""
    newer = aliased(ActivityRun)
    return ActivityRun.run_number == (
        select(func.max(newer.run_number))
        .where(
            newer.activity_instance_id == ActivityRun.activity_instance_id,
            newer.deleted_at.is_(None),
        )
        .scalar_subquery()
    )


async def _can_act_clause(session, user_id):
    """O usuário pode agir na atividade da tarefa (Spec 032, R1).

    Mesma regra de `require_activity_access(..., 'edit')`: algum cargo do
    usuário (atribuição ativa no processo ou cargo global) está em
    `edit_roles`, e ele não tem conflito de interesse vigente no processo.
    Na execução de um laboratório, a designação tem de ser por esse
    laboratório (Spec 036, R8).
    """
    by_role = exists(
        process_cargos_scope(user_id).where(
            Assignment.process_instance_id
            == ActivityInstance.process_instance_id,
            Assignment.role_key == any_(ActivityInstance.edit_roles),
        )
    )
    by_assignment = or_(
        and_(ActivityRun.laboratory_id.is_(None), by_role),
        and_(
            ActivityRun.laboratory_id.is_not(None),
            laboratory_member_clause(user_id),
        ),
    )
    cargos = await global_cargos(session, user_id)
    granted = (
        or_(
            ActivityInstance.edit_roles.overlap(array(sorted(cargos))),
            by_assignment,
        )
        if cargos
        else by_assignment
    )
    return and_(granted, ~current_conflict_clause(user_id))


async def _facets(session, filtered_ids) -> TaskFacets:
    """Contagens sobre todo o conjunto filtrado, sem paginação (R5)."""

    async def count_by(column):
        rows = await session.execute(
            select(column, func.count())
            .select_from(Task)
            .join(Task.activity_run)
            .join(ActivityRun.activity_instance)
            .join(filtered_ids, filtered_ids.c.id == Task.id)
            .group_by(column)
        )
        return dict(rows.all())

    return TaskFacets(
        activity_key=await count_by(ActivityInstance.key),
        status=await count_by(Task.status),
    )


async def _summary(session, user_id, process_id) -> TaskListSummary:
    """Processos visíveis com pré-avaliação por IA em andamento (R6).

    A pré-avaliação não é tarefa: segue a visibilidade do processo e a
    concessão de ver da atividade de submissão, e só o filtro de processo.
    """
    stmt = (
        select(func.count(func.distinct(EvaluationRun.process_instance_id)))
        .join(ActivityRun, ActivityRun.id == EvaluationRun.activity_run_id)
        .join(ActivityRun.activity_instance)
        .join(ActivityInstance.process_instance)
        .where(
            EvaluationRun.status == 'in_progress',
            EvaluationRun.deleted_at.is_(None),
        )
    )
    visibility = await process_visibility_clause(session, user_id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    activity_visibility = await activity_view_clause(session, user_id)
    if activity_visibility is not None:
        stmt = stmt.where(activity_visibility)
    if process_id:
        stmt = stmt.where(EvaluationRun.process_instance_id == process_id)
    return TaskListSummary(
        ai_pre_evaluation_in_progress=await session.scalar(stmt) or 0
    )


def _order_by(sort_by: str, sort_order: str):
    """Ordem total: o campo escolhido, sem prazo por último nas duas
    direções, e `created_at`/`id` para desempatar (Spec 032, R7)."""
    column = _SORT_COLUMNS[sort_by]
    primary = column.desc() if sort_order == 'desc' else column.asc()
    return (primary.nulls_last(), Task.created_at.asc(), Task.id.asc())


@router.get(
    '',
    response_model=TaskListResponse,
    status_code=HTTPStatus.OK,
)
async def list_tasks(  # noqa: PLR0913, PLR0917
    session: Session,
    current_user: CurrentUser,
    status: list[TaskStatus] = Query([]),
    activity_key: list[str] = Query([]),
    phase_order: int | None = Query(None, ge=1),
    role: str | None = None,
    process_id: UUID | None = None,
    actionable: bool = False,
    current_run: bool = True,
    overdue: bool = False,
    sort_by: Literal['due_date', 'created_at'] = 'due_date',
    sort_order: Literal['asc', 'desc'] = 'asc',
    include: list[Literal['facets', 'summary']] = Query([]),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    filtered = (
        select(Task.id)
        .join(Task.activity_run)
        .join(ActivityRun.activity_instance)
        .join(ActivityInstance.process_instance)
        .join(ActivityInstance.phase)
        .where(Task.deleted_at.is_(None))
    )
    # Spec 018 (FR-006/FR-014): sem isto, qualquer usuário autenticado listava
    # as tarefas de todos os processos da plataforma, sem nenhuma restrição.
    visibility = await process_visibility_clause(session, current_user.id)
    if visibility is not None:
        filtered = filtered.where(visibility)
    activity_visibility = await activity_view_clause(session, current_user.id)
    if activity_visibility is not None:
        filtered = filtered.where(activity_visibility)
    # Spec 036 (R13): tarefa de execução de laboratório só para o próprio
    # laboratório e os gestores do processo.
    laboratory_visibility = await laboratory_run_visibility_clause(
        session, current_user.id
    )
    if laboratory_visibility is not None:
        filtered = filtered.where(laboratory_visibility)
    if status:
        filtered = filtered.where(Task.status.in_(status))
    if activity_key:
        filtered = filtered.where(ActivityInstance.key.in_(activity_key))
    if phase_order is not None:
        filtered = filtered.where(Phase.order_index == phase_order)
    if role:
        filtered = filtered.where(Task.assigned_role == role)
    if process_id:
        filtered = filtered.where(
            ActivityInstance.process_instance_id == process_id
        )
    can_act = await _can_act_clause(session, current_user.id)
    if actionable:
        filtered = filtered.where(can_act)
    if current_run:
        filtered = filtered.where(_current_run_clause())
    if overdue:
        # `due_date` é naive em UTC (Spec 024); "agora" segue o mesmo padrão.
        filtered = filtered.where(
            Task.status == 'READY',
            Task.due_date < datetime.now(UTC).replace(tzinfo=None),
        )

    filtered_ids = filtered.subquery()
    total = await session.scalar(
        select(func.count()).select_from(filtered_ids)
    )
    order = _order_by(sort_by, sort_order)
    page_ids = (
        filtered.order_by(*order).offset((page - 1) * per_page).limit(per_page)
    ).subquery()
    rows = (
        await session.execute(
            select(Task, can_act.label('can_act'))
            .join(Task.activity_run)
            .join(ActivityRun.activity_instance)
            .join(page_ids, page_ids.c.id == Task.id)
            .options(
                selectinload(Task.activity_run)
                .selectinload(ActivityRun.activity_instance)
                .selectinload(ActivityInstance.process_instance),
                selectinload(Task.activity_run)
                .selectinload(ActivityRun.activity_instance)
                .selectinload(ActivityInstance.phase),
            )
            .order_by(*order)
        )
    ).all()

    return TaskListResponse(
        data=[_task_summary(task, can_act=flag) for task, flag in rows],
        pagination=build_pagination(page, per_page, total),
        filters_applied=TaskFiltersApplied(
            status=status,
            activity_key=activity_key,
            phase_order=phase_order,
            process_id=process_id,
            role=role,
            actionable=actionable,
            current_run=current_run,
            overdue=overdue,
        ),
        sort=SortApplied(by=sort_by, order=sort_order),
        facets=(
            await _facets(session, filtered_ids)
            if 'facets' in include
            else None
        ),
        summary=(
            await _summary(session, current_user.id, process_id)
            if 'summary' in include
            else None
        ),
    )


def _task_summary(task: Task, *, can_act: bool) -> TaskSummary:
    run = task.activity_run
    activity = run.activity_instance
    process = activity.process_instance
    return TaskSummary(
        id=task.id,
        process=ProcessRef(
            id=process.id, code=process.code, title=process.title
        ),
        activity_key=activity.key,
        activity_run_number=run.run_number,
        phase=PhaseRef(
            key=activity.phase.key, order=activity.phase.order_index
        ),
        title=task.title,
        assigned_role=task.assigned_role,
        status=task.status,
        due_date=task.due_date,
        can_act=can_act,
    )


@router.get(
    '/{id}',
    response_model=TaskDetail,
    status_code=HTTPStatus.OK,
)
async def get_task_detail(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
):
    stmt = (
        select(Task)
        .join(Task.activity_run)
        .join(ActivityRun.activity_instance)
        .join(ActivityInstance.process_instance)
        .where(Task.id == id, Task.deleted_at.is_(None))
        .options(
            selectinload(Task.activity_run).selectinload(
                ActivityRun.activity_instance
            )
        )
    )
    visibility = await process_visibility_clause(session, current_user.id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    laboratory_visibility = await laboratory_run_visibility_clause(
        session, current_user.id
    )
    if laboratory_visibility is not None:
        stmt = stmt.where(laboratory_visibility)
    t = (await session.execute(stmt)).scalar_one_or_none()
    if not t:
        raise http_error(HTTPStatus.NOT_FOUND, 'Tarefa não encontrada.')

    act = t.activity_run.activity_instance
    try:
        await require_activity_access(session, current_user.id, act, 'view')
    except NotFoundError as e:
        raise http_error(HTTPStatus.NOT_FOUND, 'Tarefa não encontrada.') from e
    is_blocked = act.status == 'BLOCKED'

    return TaskDetail(
        id=t.id,
        process_id=act.process_instance_id,
        activity_key=act.key,
        activity_run_number=t.activity_run.run_number,
        title=t.title,
        status=t.status,
        is_blocked=is_blocked,
        blocked_reason=act.blocked_reason,
        due_date=t.due_date,
    )
