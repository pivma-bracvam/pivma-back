"""Corridas reais sobre as amostras cegas (Spec 031, research R6).

Como em `test_process_retirement_concurrency.py`, os dados precisam estar
commitados para duas conexões independentes, então os testes não usam a
fixture `session` e apagam o que criaram ao final.
"""

import asyncio
from contextlib import asynccontextmanager

import pytest
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from pivma.core import sample_service
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    BlindSampleCode,
    StudySubstance,
)
from pivma.core.process_engine import ConflictError
from tests.factories.sample_factory import (
    VALID_CAS,
    sample_process,
    substance_payload,
)

PROCESS_TABLES = (
    'audit_events',
    'blind_sample_codes',
    'study_substances',
    'artifacts',
    'assignments',
)


async def _purge(engine: AsyncEngine, ctx) -> None:
    process_id = ctx.process_id
    users = [ctx.creator.id, ctx.selector.id, *(u.id for u in ctx.lab_users)]
    labs = [lab.id for lab in ctx.labs]
    async with engine.begin() as conn:
        for table in PROCESS_TABLES:
            await conn.execute(
                sa.text(f'DELETE FROM {table} WHERE process_instance_id = :p'),
                {'p': process_id},
            )
        runs = (
            'SELECT r.id FROM activity_runs r JOIN activity_instances a '
            'ON a.id = r.activity_instance_id WHERE a.process_instance_id = :p'
        )
        acts = (
            'SELECT id FROM activity_instances WHERE process_instance_id = :p'
        )
        await conn.execute(
            sa.text(f'DELETE FROM tasks WHERE activity_run_id IN ({runs})'),
            {'p': process_id},
        )
        await conn.execute(
            sa.text(
                'DELETE FROM activity_runs '
                f'WHERE activity_instance_id IN ({acts})'
            ),
            {'p': process_id},
        )
        await conn.execute(
            sa.text(
                'DELETE FROM activity_dependencies '
                f'WHERE dependent_activity_id IN ({acts})'
            ),
            {'p': process_id},
        )
        for table in ('activity_instances', 'phases'):
            await conn.execute(
                sa.text(f'DELETE FROM {table} WHERE process_instance_id = :p'),
                {'p': process_id},
            )
        await conn.execute(
            sa.text(
                'DELETE FROM process_instances WHERE id = :p RETURNING '
                'template_version_id'
            ),
            {'p': process_id},
        )
        await conn.execute(
            sa.text(
                'DELETE FROM process_template_versions WHERE template_id IN '
                "(SELECT id FROM process_templates WHERE key = 'sample_probe')"
            )
        )
        await conn.execute(
            sa.text("DELETE FROM process_templates WHERE key = 'sample_probe'")
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
async def committed_sample_process(engine: AsyncEngine, *, lab_count=2):
    async with AsyncSession(engine, expire_on_commit=False) as setup:
        ctx = await sample_process(setup, lab_count=lab_count)
    try:
        yield ctx
    finally:
        await _purge(engine, ctx)


async def _in_new_session(engine, func_, *args):
    async with AsyncSession(engine, expire_on_commit=False) as sess:
        return await func_(sess, *args)


@pytest.mark.asyncio
async def test_concurrent_creates_with_same_cas_accept_only_one(engine):
    async with committed_sample_process(engine) as ctx:
        data = substance_payload()

        results = await asyncio.gather(
            _in_new_session(
                engine,
                sample_service.create_substance,
                ctx.process_id,
                ctx.selector.id,
                data,
            ),
            _in_new_session(
                engine,
                sample_service.create_substance,
                ctx.process_id,
                ctx.selector.id,
                data,
            ),
            return_exceptions=True,
        )

        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 1
        assert isinstance(failures[0], ConflictError)
        assert failures[0].code == 'duplicate_cas'
        async with AsyncSession(engine) as check:
            active = await check.scalar(
                select(func.count())
                .select_from(StudySubstance)
                .where(
                    StudySubstance.process_instance_id == ctx.process_id,
                    StudySubstance.deleted_at.is_(None),
                )
            )
        assert active == 1


async def _substance_with_sds(engine, ctx, cas):
    """Substância pronta para a conclusão (SDS gravada direto no banco)."""
    async with AsyncSession(engine, expire_on_commit=False) as setup:
        await sample_service.create_substance(
            setup,
            ctx.process_id,
            ctx.selector.id,
            substance_payload(cas_number=cas),
        )
        run = await setup.scalar(
            select(ActivityRun)
            .join(
                ActivityInstance,
                ActivityInstance.id == ActivityRun.activity_instance_id,
            )
            .where(ActivityInstance.process_instance_id == ctx.process_id)
        )
        artifact = Artifact(
            process_instance_id=ctx.process_id,
            activity_run_id=run.id,
            key='sample_sds',
            name='sds.pdf',
        )
        setup.add(artifact)
        await setup.flush()
        substance = await setup.scalar(
            select(StudySubstance).where(
                StudySubstance.process_instance_id == ctx.process_id,
                StudySubstance.cas_number == cas,
            )
        )
        substance.sds_artifact_id = artifact.id
        await setup.commit()


@pytest.mark.asyncio
async def test_create_concurrent_with_complete_never_adds_codes_after_freeze(
    engine,
):
    async with committed_sample_process(engine) as ctx:
        await _substance_with_sds(engine, ctx, VALID_CAS[0])

        create, complete = await asyncio.gather(
            _in_new_session(
                engine,
                sample_service.create_substance,
                ctx.process_id,
                ctx.selector.id,
                substance_payload(cas_number=VALID_CAS[1]),
            ),
            _in_new_session(
                engine,
                sample_service.complete_sample_definition,
                ctx.process_id,
                ctx.selector.id,
            ),
            return_exceptions=True,
        )

        async with AsyncSession(engine) as check:
            substances = list(
                await check.scalars(
                    select(StudySubstance).where(
                        StudySubstance.process_instance_id == ctx.process_id,
                        StudySubstance.deleted_at.is_(None),
                    )
                )
            )
            codes = list(
                await check.scalars(
                    select(BlindSampleCode).where(
                        BlindSampleCode.process_instance_id == ctx.process_id,
                        BlindSampleCode.deleted_at.is_(None),
                    )
                )
            )
        if isinstance(create, Exception):
            # A conclusão venceu: o cadastro chegou com o conjunto congelado.
            assert isinstance(create, ConflictError)
            assert create.code == 'invalid_transition'
            assert not isinstance(complete, Exception)
            assert len(substances) == 1
        else:
            # O cadastro venceu: a conclusão parou na SDS que faltava.
            assert isinstance(complete, Exception)
            assert complete.code == 'missing_sds'
            assert len(substances) == 2  # noqa: PLR2004
        assert len(codes) == len(substances) * len(ctx.labs)


@pytest.mark.asyncio
async def test_concurrent_completions_generate_codes_once(engine):
    async with committed_sample_process(engine) as ctx:
        await _substance_with_sds(engine, ctx, VALID_CAS[0])

        results = await asyncio.gather(
            *(
                _in_new_session(
                    engine,
                    sample_service.complete_sample_definition,
                    ctx.process_id,
                    ctx.selector.id,
                )
                for _ in range(2)
            ),
            return_exceptions=True,
        )

        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 1
        assert isinstance(failures[0], ConflictError)
        async with AsyncSession(engine) as check:
            pairs = list(
                (
                    await check.execute(
                        select(
                            BlindSampleCode.substance_id,
                            BlindSampleCode.laboratory_id,
                        ).where(
                            BlindSampleCode.process_instance_id
                            == ctx.process_id,
                            BlindSampleCode.deleted_at.is_(None),
                        )
                    )
                ).all()
            )
        assert len(pairs) == len(set(pairs)) == len(ctx.labs)
