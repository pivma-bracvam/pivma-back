# ruff: noqa: PLR2004
"""Efeitos da dispensa de um laboratório (Spec 036, US4)."""

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    AuditEvent,
    BlindSampleCode,
    LaboratoryWaiver,
)
from tests.factories.laboratory_run_factory import (
    activity,
    complete_chain,
    complete_lab,
    complete_statistics,
    frozen_lab_process,
    runs_by_lab,
    tasks_of,
    waive,
)


async def _status(session, ctx, key, index):
    runs = await runs_by_lab(session, ctx.process_id, key)
    return runs[ctx.labs[index].id].status


async def _waived_events(session, ctx):
    return list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == ctx.process_id,
                AuditEvent.event_type == 'LABORATORY_WAIVED',
            )
        )
    )


@pytest.mark.asyncio
async def test_waiving_pending_lab_completes_activity(session):
    ctx = await frozen_lab_process(session)
    await complete_chain(session, ctx, 0)
    await complete_chain(session, ctx, 1)

    await waive(session, ctx, 2)

    assert await _status(session, ctx, 'receipt', 2) == 'WAIVED'
    assert await _status(session, ctx, 'upload', 2) == 'WAIVED'
    upload = await activity(session, ctx.process_id, 'upload')
    statistics = await activity(session, ctx.process_id, 'statistics')
    assert upload.status == 'COMPLETED'
    assert statistics.status == 'IN_PROGRESS'
    waivers = (await session.scalars(select(LaboratoryWaiver))).all()
    assert [(w.laboratory_id, w.reason) for w in waivers] == [
        (ctx.labs[2].id, 'Equipamento quebrado.')
    ]


@pytest.mark.asyncio
async def test_waived_runs_have_cancelled_tasks(session):
    ctx = await frozen_lab_process(session)

    await waive(session, ctx, 2)

    for key in ('receipt', 'upload'):
        run = (await runs_by_lab(session, ctx.process_id, key))[ctx.labs[2].id]
        assert [t.status for t in await tasks_of(session, run.id)] == [
            'CANCELLED'
        ]


@pytest.mark.asyncio
async def test_custody_opens_for_waived_lab(session):
    ctx = await frozen_lab_process(session)

    await waive(session, ctx, 2)

    run = (await runs_by_lab(session, ctx.process_id, 'material_return'))[
        ctx.labs[2].id
    ]
    assert run.status == 'IN_PROGRESS'
    assert [t.status for t in await tasks_of(session, run.id)] == ['READY']


@pytest.mark.asyncio
async def test_custody_waits_for_the_waived_lab_return(session):
    ctx = await frozen_lab_process(session)
    for index in (0, 1):
        await complete_chain(
            session, ctx, index, ('receipt', 'upload', 'material_return')
        )
    await waive(session, ctx, 2)

    material_return = await activity(
        session, ctx.process_id, 'material_return'
    )
    assert material_return.status == 'IN_PROGRESS'

    await complete_lab(session, ctx, 'material_return', 2)

    material_return = await activity(
        session, ctx.process_id, 'material_return'
    )
    assert material_return.status == 'COMPLETED'


@pytest.mark.asyncio
async def test_completed_run_survives_waiver(session):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', 2)
    run = (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        ctx.labs[2].id
    ]
    completed_events = {
        e.id
        for e in await session.scalars(
            select(AuditEvent).where(AuditEvent.activity_run_id == run.id)
        )
    }

    await waive(session, ctx, 2)

    assert await _status(session, ctx, 'receipt', 2) == 'COMPLETED'
    assert [t.status for t in await tasks_of(session, run.id)] == ['COMPLETED']
    after = {
        e.id
        for e in await session.scalars(
            select(AuditEvent).where(
                AuditEvent.activity_run_id == run.id,
                AuditEvent.event_type != 'LABORATORY_WAIVED',
            )
        )
    }
    assert after == completed_events


@pytest.mark.asyncio
async def test_later_activation_creates_waived_run_for_waived_lab(session):
    ctx = await frozen_lab_process(session)
    await complete_chain(session, ctx, 0)
    await complete_chain(session, ctx, 1)
    await waive(session, ctx, 2)

    await complete_statistics(session, ctx)

    runs = await runs_by_lab(session, ctx.process_id, 'lab_feedback')
    assert runs[ctx.labs[2].id].status == 'WAIVED'
    assert [
        t.status for t in await tasks_of(session, runs[ctx.labs[2].id].id)
    ] == ['CANCELLED']
    assert {runs[lab.id].status for lab in ctx.labs[:2]} == {'IN_PROGRESS'}


@pytest.mark.asyncio
async def test_waiving_every_lab_moves_the_study_forward(session):
    ctx = await frozen_lab_process(session)

    for index in range(3):
        await waive(session, ctx, index)

    for key in ('receipt', 'upload'):
        assert (await activity(session, ctx.process_id, key)).status == (
            'COMPLETED'
        )
    statistics = await activity(session, ctx.process_id, 'statistics')
    assert statistics.status == 'IN_PROGRESS'
    for index in range(3):
        assert (
            await _status(session, ctx, 'material_return', index)
            == 'IN_PROGRESS'
        )


@pytest.mark.asyncio
async def test_waiver_records_one_event_per_waived_run(session):
    ctx = await frozen_lab_process(session)

    await waive(session, ctx, 2, reason='Contaminação da linhagem.')

    runs = {
        key: (await runs_by_lab(session, ctx.process_id, key))[ctx.labs[2].id]
        for key in ('receipt', 'upload')
    }
    events = await _waived_events(session, ctx)
    assert {e.activity_run_id for e in events} == {
        run.id for run in runs.values()
    }
    for event in events:
        assert event.context_data['phase_key'] == 'phase_execution'
        assert event.context_data['laboratory_id'] == str(ctx.labs[2].id)
        assert event.context_data['reason'] == 'Contaminação da linhagem.'
    assert {e.context_data['activity_key'] for e in events} == {
        'receipt',
        'upload',
    }


@pytest.mark.asyncio
async def test_waiver_without_changed_run_records_single_event(session):
    ctx = await frozen_lab_process(session)
    await complete_chain(session, ctx, 0)

    _, waived_keys = await waive(session, ctx, 0)

    events = await _waived_events(session, ctx)
    assert len(events) == 1
    assert events[0].activity_run_id is None
    assert waived_keys == []


@pytest.mark.asyncio
async def test_waiver_does_not_touch_blind_codes(session):
    ctx = await frozen_lab_process(session)

    async def codes():
        return sorted(
            (c.id, c.code, c.laboratory_id, c.deleted_at)
            for c in await session.scalars(
                select(BlindSampleCode)
                .where(BlindSampleCode.process_instance_id == ctx.process_id)
                .execution_options(populate_existing=True)
            )
        )

    before = await codes()

    await waive(session, ctx, 2)

    assert await codes() == before
