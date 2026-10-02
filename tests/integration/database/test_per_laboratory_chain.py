# ruff: noqa: PLR2004
"""Desbloqueio por laboratório entre atividades por laboratório (US3)."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from pivma.core.database.models import FormInstance, ProcessInstance
from pivma.core.process_engine import _unblock_laboratory  # noqa: PLC2701
from tests.factories.laboratory_run_factory import (
    activity,
    complete_chain,
    complete_lab,
    frozen_lab_process,
    runs_by_lab,
    tasks_of,
)


async def _forms(session, run_id):
    return (
        await session.scalars(
            select(FormInstance).where(FormInstance.activity_run_id == run_id)
        )
    ).all()


@pytest.mark.asyncio
async def test_lab_a_receipt_unblocks_only_lab_a_upload(session):
    ctx = await frozen_lab_process(session)

    await complete_lab(session, ctx, 'receipt', 0)

    runs = await runs_by_lab(session, ctx.process_id, 'upload')
    lab_a = runs[ctx.labs[0].id]
    assert lab_a.status == 'IN_PROGRESS'
    assert [t.status for t in await tasks_of(session, lab_a.id)] == ['READY']
    assert len(await _forms(session, lab_a.id)) == 1
    for lab in ctx.labs[1:]:
        assert runs[lab.id].status == 'BLOCKED'
        assert await tasks_of(session, runs[lab.id].id) == []


@pytest.mark.asyncio
async def test_unblocking_keeps_the_same_run(session):
    ctx = await frozen_lab_process(session)
    before = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[0].id
    ]
    before_id, before_number = before.id, before.run_number

    await complete_lab(session, ctx, 'receipt', 0)

    after = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[0].id
    ]
    assert (after.id, after.run_number) == (before_id, before_number)


@pytest.mark.asyncio
async def test_custody_waits_for_every_lab_dependency(session):
    ctx = await frozen_lab_process(session)

    await complete_lab(session, ctx, 'receipt', 0)

    runs = await runs_by_lab(session, ctx.process_id, 'material_return')
    assert runs[ctx.labs[0].id].status == 'BLOCKED'


@pytest.mark.asyncio
async def test_custody_opens_for_lab_a_without_waiting_others(session):
    ctx = await frozen_lab_process(session)

    await complete_chain(session, ctx, 0)

    runs = await runs_by_lab(session, ctx.process_id, 'material_return')
    assert runs[ctx.labs[0].id].status == 'IN_PROGRESS'
    assert {runs[lab.id].status for lab in ctx.labs[1:]} == {'BLOCKED'}


@pytest.mark.asyncio
async def test_unblock_is_idempotent(session):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', 0)
    process = await session.get(ProcessInstance, ctx.process_id)
    receipt = await activity(session, ctx.process_id, 'receipt')

    await _unblock_laboratory(
        session, process, receipt, ctx.labs[0].id, ctx.selector.id
    )
    await session.commit()

    run = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[0].id
    ]
    assert len(await tasks_of(session, run.id)) == 1
    assert len(await _forms(session, run.id)) == 1


@pytest.mark.asyncio
async def test_due_date_counts_from_unblock(session):
    ctx = await frozen_lab_process(session)
    created = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[0].id
    ]
    created.started_at -= timedelta(days=10)
    blocked_since = created.started_at
    await session.commit()

    await complete_lab(session, ctx, 'receipt', 0)

    run = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[0].id
    ]
    task = (await tasks_of(session, run.id))[0]
    assert run.started_at > blocked_since + timedelta(days=9)
    assert task.due_date == run.started_at + timedelta(hours=48)
