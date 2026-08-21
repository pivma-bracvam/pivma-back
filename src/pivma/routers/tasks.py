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
            .selectinload(ActivityInstance.process_instance)
        )
    )
    if status:
        stmt = stmt.where(Task.status == status)
    if role:
        stmt = stmt.where(Task.assigned_role == role)
    if process_id:
        stmt = stmt.where(ActivityInstance.process_instance_id == process_id)

    res = await session.execute(stmt)
    tasks = res.scalars().all()

    return [
        TaskSummary(
            id=t.id,
            process_id=t.activity_run.activity_instance.process_instance.id,
            process_code=t.activity_run.activity_instance.process_instance.code,
            title=t.title,
            assigned_role=t.assigned_role,
            status=t.status,
            due_date=t.due_date,
        )
        for t in tasks
    ]


@router.get(
    '/{id}',
    response_model=TaskDetail,
    status_code=HTTPStatus.OK,
)
async def get_task_detail(
    id: UUID,
    session: Session,
    _: CurrentUser,
):
    stmt = (
        select(Task)
        .where(Task.id == id, Task.deleted_at.is_(None))
        .options(
            selectinload(Task.activity_run).selectinload(
                ActivityRun.activity_instance
            )
        )
    )
    t = (await session.execute(stmt)).scalar_one_or_none()
    if not t:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Tarefa não encontrada.'
        )

    act = t.activity_run.activity_instance
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
    )
