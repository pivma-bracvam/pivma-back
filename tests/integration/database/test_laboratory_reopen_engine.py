# ruff: noqa: PLR2004
"""Reabertura da execução de um laboratório e cascata (Spec 036, US5)."""

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    ActivityRun,
    Artifact,
    AuditEvent,
    BlindSampleCode,
    FormField,
    FormInstance,
    FormValue,
)
from pivma.core.process_engine import ConflictError
from tests.factories.laboratory_run_factory import (
    activity,
    all_labs_done,
    complete_lab,
    complete_statistics,
    frozen_lab_process,
    reopen,
    runs_by_lab,
    tasks_of,
    waive,
)
from tests.factories.sample_factory import add_participating_lab

LAB_B = 1


async def _run(session, ctx, key, index):
    return (await runs_by_lab(session, ctx.process_id, key))[
        ctx.labs[index].id
    ]


async def _runs_of_lab(session, ctx, key, index):
    act = await activity(session, ctx.process_id, key)
    return list(
        await session.scalars(
            select(ActivityRun)
            .where(
                ActivityRun.activity_instance_id == act.id,
                ActivityRun.laboratory_id == ctx.labs[index].id,
            )
            .order_by(ActivityRun.run_number)
            .execution_options(populate_existing=True)
        )
    )


async def _fill_upload(session, ctx, index, tmp_path):
    """Grava valores, anexo em disco e submissão na execução do upload."""
    run = await _run(session, ctx, 'upload', index)
    form = await session.scalar(
        select(FormInstance).where(FormInstance.activity_run_id == run.id)
    )
    fields = {
        f.field_key: f
        for f in await session.scalars(
            select(FormField).where(
                FormField.form_template_id == form.form_template_id
            )
        )
    }
    path = tmp_path / 'raw.csv'
    path.write_bytes(b'placa,valor\n1,0.42\n')
    artifact = Artifact(
        process_instance_id=ctx.process_id,
        activity_run_id=run.id,
        key='attachment',
        name='raw.csv',
        file_path=str(path),
        file_size=path.stat().st_size,
    )
    session.add(artifact)
    await session.flush()
    session.add_all([
        FormValue(
            form_instance_id=form.id,
            form_field_id=fields['result_note'].id,
            text_value='Viabilidade 42%',
        ),
        FormValue(
            form_instance_id=form.id,
            form_field_id=fields['raw_data'].id,
            file_attachment_id=artifact.id,
        ),
    ])
    form.is_submitted = True
    await session.commit()
    return run, form, artifact, path


async def _snapshot(session, run, form, artifact):
    values = sorted(
        (v.id, v.text_value, v.file_attachment_id, v.deleted_at)
        for v in await session.scalars(
            select(FormValue)
            .where(FormValue.form_instance_id == form.id)
            .execution_options(populate_existing=True)
        )
    )
    form_row = await session.scalar(
        select(FormInstance)
        .where(FormInstance.id == form.id)
        .execution_options(populate_existing=True)
    )
    art = await session.scalar(
        select(Artifact)
        .where(Artifact.id == artifact.id)
        .execution_options(populate_existing=True)
    )
    events = sorted(
        (e.id, e.event_type)
        for e in await session.scalars(
            select(AuditEvent).where(AuditEvent.activity_run_id == run.id)
        )
    )
    return (
        values,
        form_row.is_submitted,
        (art.file_path, art.file_size, art.deleted_at),
        events,
    )


@pytest.mark.asyncio
async def test_reopen_supersedes_and_opens_next_run(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)

    new_run, _ = await reopen(session, ctx, 'upload', LAB_B)

    runs = await _runs_of_lab(session, ctx, 'upload', LAB_B)
    assert [(r.run_number, r.status) for r in runs] == [
        (1, 'SUPERSEDED'),
        (2, 'IN_PROGRESS'),
    ]
    assert new_run.id == runs[1].id
    assert [t.status for t in await tasks_of(session, runs[1].id)] == ['READY']


@pytest.mark.asyncio
async def test_reopen_preserves_superseded_run_data(session, tmp_path):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', LAB_B)
    run, form, artifact, path = await _fill_upload(
        session, ctx, LAB_B, tmp_path
    )
    await complete_lab(session, ctx, 'upload', LAB_B)
    before = await _snapshot(session, run, form, artifact)

    await reopen(session, ctx, 'upload', LAB_B)

    assert await _snapshot(session, run, form, artifact) == before
    assert path.read_bytes() == b'placa,valor\n1,0.42\n'


@pytest.mark.asyncio
async def test_new_run_has_fresh_empty_form(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)

    new_run, _ = await reopen(session, ctx, 'upload', LAB_B)

    forms = (
        await session.scalars(
            select(FormInstance).where(
                FormInstance.activity_run_id == new_run.id
            )
        )
    ).all()
    assert len(forms) == 1
    assert forms[0].is_submitted is False
    values = (
        await session.scalars(
            select(FormValue).where(FormValue.form_instance_id == forms[0].id)
        )
    ).all()
    assert values == []


@pytest.mark.asyncio
async def test_other_labs_are_untouched(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)

    async def state(index):
        runs = await _runs_of_lab(session, ctx, 'upload', index)
        tasks = [
            (t.id, t.status)
            for r in runs
            for t in await tasks_of(session, r.id)
        ]
        return [(r.id, r.run_number, r.status) for r in runs], tasks

    before = [await state(i) for i in (0, 2)]

    await reopen(session, ctx, 'upload', LAB_B)

    assert [await state(i) for i in (0, 2)] == before


@pytest.mark.asyncio
async def test_completed_activity_returns_to_in_progress(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    assert (await activity(session, ctx.process_id, 'upload')).status == (
        'COMPLETED'
    )

    await reopen(session, ctx, 'upload', LAB_B)

    assert (await activity(session, ctx.process_id, 'upload')).status == (
        'IN_PROGRESS'
    )


@pytest.mark.asyncio
async def test_open_single_dependent_is_blocked_and_cancelled(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    stat_run = (await runs_by_lab(session, ctx.process_id, 'statistics'))[None]

    await reopen(session, ctx, 'upload', LAB_B)

    statistics = await activity(session, ctx.process_id, 'statistics')
    assert statistics.status == 'BLOCKED'
    assert statistics.blocked_reason
    run = (await runs_by_lab(session, ctx.process_id, 'statistics'))[None]
    assert (run.id, run.status) == (stat_run.id, 'CANCELLED')
    assert {t.status for t in await tasks_of(session, run.id)} == {'CANCELLED'}


@pytest.mark.asyncio
async def test_completed_single_dependent_reopens_with_next_run(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await complete_statistics(session, ctx)

    await reopen(session, ctx, 'upload', LAB_B)

    statistics = await activity(session, ctx.process_id, 'statistics')
    first = (await runs_by_lab(session, ctx.process_id, 'statistics'))[None]
    assert statistics.status == 'BLOCKED'
    assert (first.run_number, first.status) == (1, 'COMPLETED')

    await complete_lab(session, ctx, 'upload', LAB_B)

    statistics = await activity(session, ctx.process_id, 'statistics')
    second = (await runs_by_lab(session, ctx.process_id, 'statistics'))[None]
    assert statistics.status == 'IN_PROGRESS'
    assert (second.run_number, second.status) == (2, 'IN_PROGRESS')


@pytest.mark.asyncio
async def test_open_lab_chain_is_cancelled_and_replaced(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    others = [await _run(session, ctx, 'material_return', i) for i in (0, 2)]

    await reopen(session, ctx, 'upload', LAB_B)

    runs = await _runs_of_lab(session, ctx, 'material_return', LAB_B)
    assert [(r.run_number, r.status) for r in runs] == [
        (1, 'CANCELLED'),
        (2, 'BLOCKED'),
    ]
    assert await tasks_of(session, runs[1].id) == []
    assert {t.status for t in await tasks_of(session, runs[0].id)} == {
        'CANCELLED'
    }
    for index, before in zip((0, 2), others, strict=True):
        after = await _run(session, ctx, 'material_return', index)
        assert (after.id, after.status) == (before.id, 'IN_PROGRESS')


@pytest.mark.asyncio
async def test_completed_lab_chain_is_superseded_and_reopens(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await complete_lab(session, ctx, 'material_return', LAB_B)

    await reopen(session, ctx, 'upload', LAB_B)

    runs = await _runs_of_lab(session, ctx, 'material_return', LAB_B)
    assert [(r.run_number, r.status) for r in runs] == [
        (1, 'SUPERSEDED'),
        (2, 'BLOCKED'),
    ]

    await complete_lab(session, ctx, 'upload', LAB_B)

    assert (await _run(session, ctx, 'material_return', LAB_B)).status == (
        'IN_PROGRESS'
    )


@pytest.mark.asyncio
async def test_reopening_open_run_is_refused(session):
    ctx = await frozen_lab_process(session)

    with pytest.raises(ConflictError):
        await reopen(session, ctx, 'receipt', LAB_B)


@pytest.mark.asyncio
async def test_reopening_blocked_run_is_refused(session):
    ctx = await frozen_lab_process(session)

    with pytest.raises(ConflictError):
        await reopen(session, ctx, 'material_return', LAB_B)


@pytest.mark.asyncio
async def test_reopening_lab_without_run_is_refused(session):
    from pivma.core.process_engine import (  # noqa: PLC0415
        reopen_laboratory_run,
    )

    ctx = await frozen_lab_process(session)
    late = await add_participating_lab(session, ctx.process_id)

    with pytest.raises(ConflictError):
        await reopen_laboratory_run(
            session,
            ctx.process_id,
            'receipt',
            late.laboratory.id,
            'Motivo.',
            ctx.group_manager.id,
        )


@pytest.mark.asyncio
async def test_reopening_single_activity_is_refused(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)

    with pytest.raises(ConflictError):
        await reopen(session, ctx, 'statistics', LAB_B)


@pytest.mark.asyncio
async def test_reopening_non_custody_run_of_waived_lab_is_refused(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await waive(session, ctx, LAB_B)

    with pytest.raises(ConflictError) as exc:
        await reopen(session, ctx, 'upload', LAB_B)

    assert exc.value.code == 'laboratory_waived'


@pytest.mark.asyncio
async def test_reopening_custody_of_waived_lab_is_accepted(session):
    ctx = await frozen_lab_process(session)
    await waive(session, ctx, LAB_B)
    await complete_lab(session, ctx, 'material_return', LAB_B)

    new_run, _ = await reopen(session, ctx, 'material_return', LAB_B)

    assert (new_run.run_number, new_run.status) == (2, 'IN_PROGRESS')


@pytest.mark.asyncio
async def test_reopen_records_event(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)

    new_run, keys = await reopen(
        session, ctx, 'upload', LAB_B, reason='Placa 2 inválida.'
    )

    events = (
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == ctx.process_id,
                AuditEvent.event_type == 'LABORATORY_RUN_REOPENED',
            )
        )
    ).all()
    assert len(events) == 1
    assert events[0].activity_run_id == new_run.id
    assert events[0].context_data == {
        'activity_key': 'upload',
        'laboratory_id': str(ctx.labs[LAB_B].id),
        'previous_run_number': 1,
        'run_number': 2,
        'reason': 'Placa 2 inválida.',
        'reblocked_activity_keys': keys,
    }
    assert set(keys) == {'material_return', 'statistics'}


@pytest.mark.asyncio
async def test_reopen_does_not_touch_blind_codes(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)

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

    await reopen(session, ctx, 'upload', LAB_B)

    assert await codes() == before


@pytest.mark.asyncio
async def test_reopen_reblocks_lab_activity_behind_single_activity(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await complete_statistics(session, ctx)
    before = {
        i: (await _run(session, ctx, 'lab_feedback', i)).id for i in range(3)
    }

    await reopen(session, ctx, 'upload', LAB_B)

    for index in range(3):
        runs = await _runs_of_lab(session, ctx, 'lab_feedback', index)
        assert [(r.id, r.status) for r in runs][0] == (
            before[index],
            'CANCELLED',
        )
        assert runs[-1].status == 'BLOCKED'


@pytest.mark.asyncio
async def test_lab_activity_unblocks_when_single_dependency_returns(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await complete_statistics(session, ctx)
    await reopen(session, ctx, 'upload', LAB_B)

    await complete_lab(session, ctx, 'upload', LAB_B)
    await complete_statistics(session, ctx)

    for index in range(3):
        run = await _run(session, ctx, 'lab_feedback', index)
        assert (run.run_number, run.status) == (2, 'IN_PROGRESS')
        assert [t.status for t in await tasks_of(session, run.id)] == ['READY']
