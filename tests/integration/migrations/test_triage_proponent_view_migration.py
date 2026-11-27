# ruff: noqa: F401, F811, I001
"""Migração da Spec 049: o proponente vê a triagem dos processos antigos."""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import ActivityInstance
from pivma.core.process_engine import activity_view_clause
from tests.integration.migrations.test_process_lifecycle_migration import (
    _insert,
    _seed_template,
)
from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'b7d3e9a1c5f2'
REVISION = 'e2f4a6c8b0d1'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _seed_process(connection, *, triage_view=()):
    """Processo antigo com triagem, submissão e o proponente designado."""
    version_id = await _seed_template(connection)
    process_id, phase_id, user_id = uuid4(), uuid4(), uuid4()
    await _insert(
        connection,
        'users',
        id=user_id,
        username=f'proponente_{user_id.hex[:8]}',
        email=f'{user_id.hex[:8]}@example.com',
        password_hash='legacy-value',
        full_name='Proponente',
    )
    await _insert(
        connection,
        'process_instances',
        id=process_id,
        template_version_id=version_id,
        code=f'VAL-{process_id.hex[:12]}',
        title='Legado',
        status='OPEN',
    )
    await _insert(
        connection,
        'phases',
        id=phase_id,
        process_instance_id=process_id,
        key='phase_1_submission_triage',
        name='Fase 1',
        order_index=1,
        status='IN_PROGRESS',
    )
    activities = {}
    for key, view, edit in (
        ('proposal_submission', [], ['proponent']),
        ('triage_evaluation', list(triage_view), ['bracvam']),
    ):
        activities[key] = uuid4()
        await _insert(
            connection,
            'activity_instances',
            id=activities[key],
            process_instance_id=process_id,
            phase_id=phase_id,
            key=key,
            name=key,
            order_index=1,
            status='IN_PROGRESS',
            activity_type='form',
            view_roles=view,
            edit_roles=edit,
        )
    await _insert(
        connection,
        'assignments',
        id=uuid4(),
        process_instance_id=process_id,
        user_id=user_id,
        assigned_by=user_id,
        role_key='proponent',
    )
    return user_id, activities


async def _roles(engine, activity_id):
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                sa.text(
                    'SELECT view_roles, edit_roles FROM activity_instances '
                    'WHERE id = :id'
                ),
                {'id': activity_id},
            )
        ).one()
    return row.view_roles, row.edit_roles


async def _seeded(engine, **kwargs):
    await run_migration(PREVIOUS)
    async with engine.begin() as connection:
        return await _seed_process(connection, **kwargs)


@pytest.mark.asyncio
async def test_upgrade_grants_view_and_keeps_edit(migration_database):
    _, activities = await _seeded(migration_database)

    await run_migration(REVISION)

    view, edit = await _roles(
        migration_database, activities['triage_evaluation']
    )
    assert view == ['proponent']
    assert edit == ['bracvam']


@pytest.mark.asyncio
async def test_upgrade_does_not_duplicate_existing_grant(migration_database):
    _, activities = await _seeded(
        migration_database, triage_view=('proponent', 'sponsor')
    )

    await run_migration(REVISION)

    view, _ = await _roles(migration_database, activities['triage_evaluation'])
    assert view == ['proponent', 'sponsor']


@pytest.mark.asyncio
async def test_upgrade_downgrade_upgrade_keeps_one_grant(migration_database):
    _, activities = await _seeded(migration_database)

    await run_migration(REVISION)
    await run_downgrade(PREVIOUS)
    await run_migration(REVISION)

    view, _ = await _roles(migration_database, activities['triage_evaluation'])
    assert view.count('proponent') == 1


@pytest.mark.asyncio
async def test_upgrade_leaves_other_activities_unchanged(migration_database):
    _, activities = await _seeded(migration_database)

    await run_migration(REVISION)

    view, edit = await _roles(
        migration_database, activities['proposal_submission']
    )
    assert view == []
    assert edit == ['proponent']


@pytest.mark.asyncio
async def test_downgrade_removes_grant(migration_database):
    _, activities = await _seeded(migration_database)
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    view, edit = await _roles(
        migration_database, activities['triage_evaluation']
    )
    assert 'proponent' not in view
    assert edit == ['bracvam']


async def _visible_activities(engine, user_id):
    async with AsyncSession(engine) as session:
        clause = await activity_view_clause(session, user_id)
        return set(
            await session.scalars(select(ActivityInstance.key).where(clause))
        )


@pytest.mark.asyncio
async def test_upgrade_puts_triage_in_proponent_task_filter(
    migration_database,
):
    """US1, cenário 8: o mesmo filtro de `GET /tasks`."""
    user_id, _ = await _seeded(migration_database)
    assert 'triage_evaluation' not in await _visible_activities(
        migration_database, user_id
    )

    await run_migration(REVISION)

    assert 'triage_evaluation' in await _visible_activities(
        migration_database, user_id
    )
