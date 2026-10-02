"""Estados terminais de execução no cancelamento do processo (Spec 036, R14).

Execuções concluídas, canceladas, dispensadas e substituídas não mudam quando
o processo é cancelado ou excluído; só as em andamento ou bloqueadas viram
`CANCELLED` (FR-039, SC-010).
"""

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    ProcessInstance,
    Task,
)
from pivma.core.process_engine import (
    _cancel_pending_children,  # noqa: PLC2701
    delete_process,
)
from tests.factories.sample_factory import sample_process

TERMINAL = ('COMPLETED', 'CANCELLED', 'WAIVED', 'SUPERSEDED')


async def _runs_with_statuses(session, ctx, statuses):
    act = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == ctx.process_id,
            ActivityInstance.key == 'sample_definition',
        )
    )
    runs = {}
    for number, status in enumerate(statuses, start=2):
        run = ActivityRun(
            activity_instance_id=act.id, run_number=number, status=status
        )
        session.add(run)
        runs[status] = run
    await session.commit()
    return runs


async def _reload(session, run):
    return await session.scalar(
        select(ActivityRun)
        .where(ActivityRun.id == run.id)
        .execution_options(populate_existing=True)
    )


@pytest.mark.asyncio
async def test_cancel_children_keeps_terminal_runs(session):
    ctx = await sample_process(session, lab_count=1)
    runs = await _runs_with_statuses(session, ctx, TERMINAL)
    process = await session.get(ProcessInstance, ctx.process_id)

    counts = await _cancel_pending_children(session, process, ctx.creator.id)
    await session.commit()

    for status, run in runs.items():
        assert (await _reload(session, run)).status == status
    # Só a execução inicial (IN_PROGRESS) de `sample_definition` foi
    # cancelada.
    assert counts['activity_runs'] == 1


@pytest.mark.asyncio
async def test_delete_process_keeps_terminal_runs(session, bracvam_user):
    ctx = await sample_process(session, lab_count=1)
    runs = await _runs_with_statuses(session, ctx, TERMINAL)

    await delete_process(session, ctx.process_id, bracvam_user.id)

    for status, run in runs.items():
        assert (await _reload(session, run)).status == status


@pytest.mark.asyncio
async def test_delete_process_cancels_open_and_blocked_runs(
    session, bracvam_user
):
    ctx = await sample_process(session, lab_count=1)
    blocked = (await _runs_with_statuses(session, ctx, ('BLOCKED',)))[
        'BLOCKED'
    ]
    open_run = await session.scalar(
        select(ActivityRun)
        .join(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == ctx.process_id,
            ActivityRun.run_number == 1,
        )
    )

    await delete_process(session, ctx.process_id, bracvam_user.id)

    assert (await _reload(session, open_run)).status == 'CANCELLED'
    assert (await _reload(session, blocked)).status == 'CANCELLED'
    open_tasks = (
        await session.scalars(
            select(Task)
            .where(Task.activity_run_id == open_run.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    assert open_tasks
    assert {task.status for task in open_tasks} == {'CANCELLED'}
