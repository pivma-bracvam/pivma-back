from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Task,
)
from pivma.core.process_engine import (
    NotFoundError,
    activity_view_clause,
    process_visibility_clause,
    require_activity_access,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import TaskDetail, TaskSummary

router = APIRouter(prefix='/tasks', tags=['Tasks'])


@router.get(
    '',
    response_model=list[TaskSummary],
    status_code=HTTPStatus.OK,
)
async def list_tasks(
    session: Session,
    current_user: CurrentUser,
    status: str | None = None,
    role: str | None = None,
    process_id: UUID | None = None,
):
    stmt = (
        select(Task)
        .join(Task.activity_run)
        .join(ActivityRun.activity_instance)
        .join(ActivityInstance.process_instance)
        .where(Task.deleted_at.is_(None))
        .options(
            selectinload(Task.activity_run)
            .selectinload(ActivityRun.activity_instance)
            .selectinload(ActivityInstance.process_instance),
            selectinload(Task.activity_run)
            .selectinload(ActivityRun.activity_instance)
            .selectinload(ActivityInstance.phase),
        )
    )
    # Spec 018 (FR-006/FR-014): sem isto, qualquer usuário autenticado listava
    # as tarefas de todos os processos da plataforma, sem nenhuma restrição.
    visibility = await process_visibility_clause(session, current_user.id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    activity_visibility = await activity_view_clause(session, current_user.id)
    if activity_visibility is not None:
        stmt = stmt.where(activity_visibility)
    if status:
        stmt = stmt.where(Task.status == status)
    if role:
        stmt = stmt.where(Task.assigned_role == role)
    if process_id:
        stmt = stmt.where(ActivityInstance.process_instance_id == process_id)

    res = await session.execute(stmt)
    tasks = res.scalars().all()

    return [_task_summary(t) for t in tasks]


def _task_summary(task: Task) -> TaskSummary:
    run = task.activity_run
    activity = run.activity_instance
    process = activity.process_instance
    return TaskSummary(
        id=task.id,
        process_id=process.id,
        process_code=process.code,
        process_title=process.title,
        activity_key=activity.key,
        activity_run_number=run.run_number,
        phase_key=activity.phase.key,
        phase_order=activity.phase.order_index,
        title=task.title,
        assigned_role=task.assigned_role,
        status=task.status,
        due_date=task.due_date,
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
    t = (await session.execute(stmt)).scalar_one_or_none()
    if not t:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Tarefa não encontrada.'
        )

    act = t.activity_run.activity_instance
    try:
        await require_activity_access(session, current_user.id, act, 'view')
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Tarefa não encontrada.'
        ) from e
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
