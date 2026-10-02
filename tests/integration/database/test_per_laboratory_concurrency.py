"""Corridas reais sobre execuções por laboratório (Spec 036, R12).

Como em `test_sample_concurrency.py`, os dados ficam commitados para duas
conexões independentes; o teste apaga o que criou ao final.
"""

import asyncio
from contextlib import asynccontextmanager

import pytest
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from pivma.core import process_engine
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    LaboratoryWaiver,
)
from pivma.core.process_engine import (
    ConflictError,
    complete_laboratory_run,
    waive_laboratory,
)
from tests.factories.laboratory_run_factory import (
    complete_chain,
    complete_lab,
    frozen_lab_process,
)

BY_PROCESS = (
    'audit_events',
    'laboratory_waivers',
    'blind_sample_codes',
    'study_substances',
)
RUNS = (
    'SELECT r.id FROM activity_runs r JOIN activity_instances a '
    'ON a.id = r.activity_instance_id WHERE a.process_instance_id = :p'
)
ACTS = 'SELECT id FROM activity_instances WHERE process_instance_id = :p'


async def _purge(engine: AsyncEngine, ctx) -> None:  # noqa: PLR0914
    p = {'p': ctx.process_id}
    users = [
        ctx.creator.id,
        ctx.selector.id,
        ctx.group_manager.id,
        ctx.statistician.id,
        *(u.id for u in ctx.lab_users),
    ]
    labs = [lab.id for lab in ctx.labs]
    async with engine.begin() as conn:
        for table in BY_PROCESS:
            await conn.execute(
                sa.text(f'DELETE FROM {table} WHERE process_instance_id = :p'),
                p,
            )
        forms = (
            f'SELECT id FROM form_instances WHERE activity_run_id IN ({RUNS})'
        )
        await conn.execute(
            sa.text(
                f'DELETE FROM form_values WHERE form_instance_id IN ({forms})'
            ),
            p,
        )
        for table in ('form_instances', 'tasks'):
            await conn.execute(
                sa.text(
                    f'DELETE FROM {table} WHERE activity_run_id IN ({RUNS})'
                ),
                p,
            )
        await conn.execute(
            sa.text('DELETE FROM artifacts WHERE process_instance_id = :p'), p
        )
        await conn.execute(
            sa.text(
                'DELETE FROM activity_runs '
                f'WHERE activity_instance_id IN ({ACTS})'
            ),
            p,
        )
        await conn.execute(
            sa.text(
                'DELETE FROM activity_dependencies '
                f'WHERE dependent_activity_id IN ({ACTS})'
            ),
            p,
        )
        for table in ('assignments', 'activity_instances', 'phases'):
            await conn.execute(
                sa.text(f'DELETE FROM {table} WHERE process_instance_id = :p'),
                p,
            )
        await conn.execute(
            sa.text('DELETE FROM process_instances WHERE id = :p'), p
        )
        await conn.execute(
            sa.text(
                'DELETE FROM process_template_versions WHERE template_id IN '
                '(SELECT id FROM process_templates '
                "WHERE key = 'lab_run_probe')"
            )
        )
        await conn.execute(
            sa.text(
                "DELETE FROM process_templates WHERE key = 'lab_run_probe'"
            )
        )
        await conn.execute(
            sa.text(
                'DELETE FROM form_fields WHERE form_template_id IN '
                "(SELECT id FROM form_templates WHERE key = 'lab_results_v1')"
            )
        )
        await conn.execute(
            sa.text("DELETE FROM form_templates WHERE key = 'lab_results_v1'")
        )
        await conn.execute(
            sa.text(
                'DELETE FROM user_institutional_affiliations '
                'WHERE user_id = ANY(:u)'
            ),
            {'u': users},
        )
        institutions = await conn.scalars(
            sa.text(
                'DELETE FROM laboratories WHERE id = ANY(:l) RETURNING '
                'institution_id'
            ),
            {'l': labs},
        )
        await conn.execute(
            sa.text('DELETE FROM institutions WHERE id = ANY(:i)'),
            {'i': list(institutions)},
        )
        await conn.execute(
            sa.text('DELETE FROM users WHERE id = ANY(:u)'), {'u': users}
        )


@asynccontextmanager
async def committed_lab_process(engine: AsyncEngine):
    async with AsyncSession(engine, expire_on_commit=False) as setup:
        ctx = await frozen_lab_process(setup)
    try:
        yield ctx
    finally:
        await _purge(engine, ctx)


async def _complete_in_new_session(engine, ctx, index):
    async with AsyncSession(engine, expire_on_commit=False) as sess:
        await complete_laboratory_run(
            sess,
            ctx.process_id,
            'upload',
            ctx.labs[index].id,
            ctx.lab_users[index].id,
        )
        await sess.commit()


@pytest.mark.asyncio
async def test_last_two_labs_completing_together_open_statistics_once(
    engine, monkeypatch
):
    original_refresh = process_engine._refresh_laboratory_activity

    async def slow_refresh(*args, **kwargs):
        # Abre a janela da corrida: cada conclusão confere as execuções dos
        # outros laboratórios e segura a transação aberta antes do commit.
        result = await original_refresh(*args, **kwargs)
        await asyncio.sleep(0.3)
        return result

    async with committed_lab_process(engine) as ctx:
        async with AsyncSession(engine, expire_on_commit=False) as setup:
            await complete_chain(setup, ctx, 0)
            await complete_lab(setup, ctx, 'receipt', 1)
            await complete_lab(setup, ctx, 'receipt', 2)

        monkeypatch.setattr(
            process_engine, '_refresh_laboratory_activity', slow_refresh
        )
        await asyncio.gather(
            _complete_in_new_session(engine, ctx, 1),
            _complete_in_new_session(engine, ctx, 2),
        )

        async with AsyncSession(engine) as check:
            upload_status = await check.scalar(
                select(ActivityInstance.status).where(
                    ActivityInstance.process_instance_id == ctx.process_id,
                    ActivityInstance.key == 'upload',
                )
            )
            statistics_runs = await check.scalar(
                select(func.count())
                .select_from(ActivityRun)
                .join(ActivityInstance)
                .where(
                    ActivityInstance.process_instance_id == ctx.process_id,
                    ActivityInstance.key == 'statistics',
                )
            )
            unblocked = await check.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.process_instance_id == ctx.process_id,
                    AuditEvent.event_type == 'ACTIVITY_UNBLOCKED',
                    AuditEvent.context_data['activity_key'].astext
                    == 'statistics',
                )
            )
        assert upload_status == 'COMPLETED'
        assert statistics_runs == 1
        assert unblocked == 1


async def _waive_in_new_session(engine, ctx):
    async with AsyncSession(engine, expire_on_commit=False) as sess:
        try:
            await waive_laboratory(
                sess,
                ctx.process_id,
                'phase_execution',
                ctx.labs[2].id,
                'Desistência formal.',
                ctx.group_manager.id,
            )
            await sess.commit()
        except ConflictError as exc:
            return exc.code
        return 'ok'


@pytest.mark.asyncio
async def test_concurrent_waivers_of_same_lab_keep_one(engine):
    async with committed_lab_process(engine) as ctx:
        results = await asyncio.gather(
            _waive_in_new_session(engine, ctx),
            _waive_in_new_session(engine, ctx),
        )

        async with AsyncSession(engine) as check:
            waivers = await check.scalar(
                select(func.count())
                .select_from(LaboratoryWaiver)
                .where(LaboratoryWaiver.process_instance_id == ctx.process_id)
            )
        assert sorted(results) == ['already_waived', 'ok']
        assert waivers == 1
