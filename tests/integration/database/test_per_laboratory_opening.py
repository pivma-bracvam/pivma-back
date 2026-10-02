# ruff: noqa: PLR2004
"""Ativação, conclusão e regra de conclusão por laboratório (Spec 036, US1)."""

from datetime import datetime

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    Assignment,
    AuditEvent,
    BlindSampleCode,
    FormInstance,
    ProcessInstance,
)
from pivma.core.process_engine import (
    ConflictError,
    _advance_dependent_activities,  # noqa: PLC2701
    _complete_activity_run,  # noqa: PLC2701
    complete_laboratory_run,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    activity,
    complete_chain,
    complete_lab,
    complete_statistics,
    frozen_lab_process,
    runs_by_lab,
    tasks_of,
)
from tests.factories.sample_factory import add_participating_lab


async def _events(session, process_id, event_type):
    return list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == process_id,
                AuditEvent.event_type == event_type,
            )
        )
    )


@pytest.mark.asyncio
async def test_instantiation_copies_execution_scope_and_custody(session):
    ctx = await frozen_lab_process(session, freeze=False)

    receipt = await activity(session, ctx.process_id, 'receipt')
    material_return = await activity(
        session, ctx.process_id, 'material_return'
    )
    statistics = await activity(session, ctx.process_id, 'statistics')

    assert (receipt.execution_scope, receipt.is_custody) == (
        'per_laboratory',
        False,
    )
    assert (material_return.execution_scope, material_return.is_custody) == (
        'per_laboratory',
        True,
    )
    assert (statistics.execution_scope, statistics.is_custody) == (
        'process',
        False,
    )


@pytest.mark.asyncio
async def test_freeze_activates_receipt_with_one_open_run_per_laboratory(
    session,
):
    ctx = await frozen_lab_process(session)

    runs = await runs_by_lab(session, ctx.process_id, 'receipt')

    assert set(runs) == {lab.id for lab in ctx.labs}
    for run in runs.values():
        assert (run.status, run.run_number) == ('IN_PROGRESS', 1)
        tasks = await tasks_of(session, run.id)
        assert [task.status for task in tasks] == ['READY']
    receipt = await activity(session, ctx.process_id, 'receipt')
    assert receipt.status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_freeze_activates_chained_activities_with_blocked_runs(session):
    ctx = await frozen_lab_process(session)

    for key in ('upload', 'material_return'):
        act = await activity(session, ctx.process_id, key)
        runs = await runs_by_lab(session, ctx.process_id, key)
        assert act.status == 'IN_PROGRESS'
        assert set(runs) == {lab.id for lab in ctx.labs}
        for run in runs.values():
            assert run.status == 'BLOCKED'
            assert await tasks_of(session, run.id) == []
            forms = (
                await session.scalars(
                    select(FormInstance).where(
                        FormInstance.activity_run_id == run.id
                    )
                )
            ).all()
            assert forms == []
    statistics = await activity(session, ctx.process_id, 'statistics')
    assert statistics.status == 'BLOCKED'
    assert await runs_by_lab(session, ctx.process_id, 'statistics') == {}


@pytest.mark.asyncio
async def test_laboratory_designated_after_freeze_gets_no_run(session):
    ctx = await frozen_lab_process(session)

    late = await add_participating_lab(session, ctx.process_id)

    for key in ('receipt', 'upload', 'material_return'):
        runs = await runs_by_lab(session, ctx.process_id, key)
        assert late.laboratory.id not in runs


@pytest.mark.asyncio
async def test_laboratory_revoked_after_freeze_gets_run_in_later_activation(
    session,
):
    ctx = await frozen_lab_process(session)
    for index in range(3):
        await complete_chain(session, ctx, index)
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.laboratory_id == ctx.labs[0].id,
        )
    )
    assignment.revoked_at = datetime.utcnow()
    await session.commit()

    await complete_statistics(session, ctx)

    runs = await runs_by_lab(session, ctx.process_id, 'lab_feedback')
    assert set(runs) == {lab.id for lab in ctx.labs}
    assert runs[ctx.labs[0].id].status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_unblocked_upload_run_has_its_own_form_instance(session):
    ctx = await frozen_lab_process(session)

    await complete_lab(session, ctx, 'receipt', 0)

    run = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[0].id
    ]
    forms = (
        await session.scalars(
            select(FormInstance).where(FormInstance.activity_run_id == run.id)
        )
    ).all()
    assert len(forms) == 1
    assert forms[0].is_submitted is False


@pytest.mark.asyncio
async def test_completing_lab_a_changes_only_lab_a(session):
    ctx = await frozen_lab_process(session)

    await complete_lab(session, ctx, 'receipt', 0)

    runs = await runs_by_lab(session, ctx.process_id, 'receipt')
    lab_a, lab_b, lab_c = (runs[lab.id] for lab in ctx.labs)
    assert lab_a.status == 'COMPLETED'
    assert [t.status for t in await tasks_of(session, lab_a.id)] == [
        'COMPLETED'
    ]
    for run in (lab_b, lab_c):
        assert run.status == 'IN_PROGRESS'
        assert [t.status for t in await tasks_of(session, run.id)] == ['READY']
    receipt = await activity(session, ctx.process_id, 'receipt')
    assert receipt.status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_activity_does_not_complete_against_blocked_labs(session):
    ctx = await frozen_lab_process(session)

    await complete_chain(session, ctx, 0)

    runs = await runs_by_lab(session, ctx.process_id, 'upload')
    assert runs[ctx.labs[0].id].status == 'COMPLETED'
    assert {runs[lab.id].status for lab in ctx.labs[1:]} == {'BLOCKED'}
    upload = await activity(session, ctx.process_id, 'upload')
    assert upload.status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_single_activity_waits_while_a_lab_is_pending(session):
    ctx = await frozen_lab_process(session)

    await complete_chain(session, ctx, 0)
    await complete_chain(session, ctx, 1)

    upload = await activity(session, ctx.process_id, 'upload')
    statistics = await activity(session, ctx.process_id, 'statistics')
    assert upload.status == 'IN_PROGRESS'
    assert statistics.status == 'BLOCKED'
    assert await runs_by_lab(session, ctx.process_id, 'statistics') == {}


@pytest.mark.asyncio
async def test_last_lab_completes_activity_and_opens_single_activity(
    session,
):
    ctx = await frozen_lab_process(session)

    for index in range(3):
        await complete_chain(session, ctx, index)

    upload = await activity(session, ctx.process_id, 'upload')
    statistics = await activity(session, ctx.process_id, 'statistics')
    assert upload.status == 'COMPLETED'
    assert statistics.status == 'IN_PROGRESS'
    stat_runs = await runs_by_lab(session, ctx.process_id, 'statistics')
    assert list(stat_runs) == [None]
    assert stat_runs[None].run_number == 1
    unblocked = [
        e
        for e in await _events(session, ctx.process_id, 'ACTIVITY_UNBLOCKED')
        if e.context_data['activity_key'] == 'statistics'
    ]
    assert len(unblocked) == 1


@pytest.mark.asyncio
async def test_activation_without_frozen_laboratories_is_refused(session):
    ctx = await frozen_lab_process(session, freeze=False)
    process_id = ctx.process_id
    process = await session.get(ProcessInstance, process_id)
    sample_act = await activity(session, ctx.process_id, 'sample_definition')
    codes = await session.scalar(
        select(BlindSampleCode).where(
            BlindSampleCode.process_instance_id == ctx.process_id
        )
    )
    assert codes is None
    run = (await runs_by_lab(session, ctx.process_id, 'sample_definition'))[
        None
    ]

    await _complete_activity_run(session, run, sample_act, ctx.selector.id)
    with pytest.raises(ConflictError):
        await _advance_dependent_activities(
            session, process, sample_act, ctx.selector.id
        )
    await session.rollback()

    receipt = await activity(session, process_id, 'receipt')
    assert receipt.status == 'BLOCKED'
    assert await runs_by_lab(session, process_id, 'receipt') == {}


@pytest.mark.asyncio
async def test_completing_completed_run_is_refused(session):
    ctx = await frozen_lab_process(session)
    lab_id = ctx.labs[0].id
    await complete_lab(session, ctx, 'receipt', 0)

    with pytest.raises(ConflictError):
        await complete_lab(session, ctx, 'receipt', 0)
    await session.rollback()

    run = (await runs_by_lab(session, ctx.process_id, 'receipt'))[lab_id]
    assert run.status == 'COMPLETED'


@pytest.mark.asyncio
async def test_completing_blocked_run_is_refused(session):
    ctx = await frozen_lab_process(session)
    lab_id = ctx.labs[0].id

    with pytest.raises(ConflictError):
        await complete_lab(session, ctx, 'upload', 0)
    await session.rollback()

    run = (await runs_by_lab(session, ctx.process_id, 'upload'))[lab_id]
    assert run.status == 'BLOCKED'
    assert await tasks_of(session, run.id) == []


@pytest.mark.asyncio
async def test_completing_in_closed_process_is_refused(session):
    ctx = await frozen_lab_process(session)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.status = 'CLOSED'
    await session.commit()

    with pytest.raises(ConflictError):
        await complete_laboratory_run(
            session,
            ctx.process_id,
            'receipt',
            ctx.labs[0].id,
            ctx.lab_users[0].id,
        )


@pytest.mark.asyncio
async def test_completion_records_laboratory_event(session):
    ctx = await frozen_lab_process(session)

    run = await complete_lab(session, ctx, 'receipt', 0)

    events = await _events(session, ctx.process_id, 'LABORATORY_RUN_COMPLETED')
    assert len(events) == 1
    assert events[0].activity_run_id == run.id
    assert events[0].context_data == {
        'activity_key': 'receipt',
        'laboratory_id': str(ctx.labs[0].id),
        'run_number': 1,
    }


@pytest.mark.asyncio
async def test_activation_event_has_no_run_and_reaches_every_lab(
    session, client
):
    ctx = await frozen_lab_process(session)

    events = [
        e
        for e in await _events(session, ctx.process_id, 'ACTIVITY_UNBLOCKED')
        if e.context_data['activity_key'] == 'receipt'
    ]
    assert len(events) == 1
    assert events[0].activity_run_id is None
    for user in ctx.lab_users:
        authenticate(client, user)
        resp = client.get(
            f'/processes/{ctx.process_id}/timeline', params={'per_page': 100}
        )
        keys = [
            (e['context_data'] or {}).get('activity_key')
            for e in resp.json()['data']
            if e['event_type'] == 'ACTIVITY_UNBLOCKED'
        ]
        assert 'receipt' in keys
