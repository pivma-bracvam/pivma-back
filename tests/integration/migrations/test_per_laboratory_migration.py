# ruff: noqa: F401, F811, I001
"""Migração da Spec 036: execução de atividades por laboratório."""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'cc6c65843305'
REVISION = 'b7d3e9a1c204'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _insert_activity_chain(connection):
    """Template, processo, fase, atividade e uma execução, em SQL puro."""
    ids = {name: uuid4() for name in ('tpl', 'ver', 'proc', 'phase', 'act')}
    await connection.execute(
        sa.text(
            'INSERT INTO process_templates (id, key, name, is_active) '
            "VALUES (:id, 'legacy', 'Legacy', true)"
        ),
        {'id': ids['tpl']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_template_versions '
            '(id, template_id, version_number, definition_payload, '
            'is_published) '
            "VALUES (:id, :tpl, 1, '{}'::jsonb, true)"
        ),
        {'id': ids['ver'], 'tpl': ids['tpl']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_instances '
            '(id, template_version_id, code, title, status) '
            "VALUES (:id, :ver, 'VAL-LEGACY', 'Legacy', 'OPEN')"
        ),
        {'id': ids['proc'], 'ver': ids['ver']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO phases '
            '(id, process_instance_id, key, name, order_index, status) '
            "VALUES (:id, :proc, 'p1', 'P1', 1, 'IN_PROGRESS')"
        ),
        {'id': ids['phase'], 'proc': ids['proc']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO activity_instances '
            '(id, process_instance_id, phase_id, key, name, order_index, '
            'status, activity_type, view_roles, edit_roles) '
            "VALUES (:id, :proc, :phase, 'a1', 'A1', 1, 'IN_PROGRESS', "
            "'form', ARRAY['proponent'], ARRAY['proponent'])"
        ),
        {'id': ids['act'], 'proc': ids['proc'], 'phase': ids['phase']},
    )
    await _insert_run(connection, ids['act'], run_number=1)
    return ids


async def _insert_run(connection, act_id, *, run_number, laboratory_id=None):
    columns = 'id, activity_instance_id, run_number, status'
    values = ":id, :act, :run_number, 'IN_PROGRESS'"
    params = {'id': uuid4(), 'act': act_id, 'run_number': run_number}
    if laboratory_id is not None:
        columns += ', laboratory_id'
        values += ', :lab'
        params['lab'] = laboratory_id
    await connection.execute(
        sa.text(f'INSERT INTO activity_runs ({columns}) VALUES ({values})'),
        params,
    )


async def _insert_laboratory(connection):
    institution_id, laboratory_id = uuid4(), uuid4()
    await connection.execute(
        sa.text('INSERT INTO institutions (id, name) VALUES (:id, :name)'),
        {'id': institution_id, 'name': f'Inst {institution_id}'},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO laboratories (id, institution_id, name) '
            'VALUES (:id, :inst, :name)'
        ),
        {
            'id': laboratory_id,
            'inst': institution_id,
            'name': f'Lab {laboratory_id}',
        },
    )
    return laboratory_id


@pytest.mark.asyncio
async def test_upgrade_gives_existing_rows_single_execution_defaults(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        ids = await _insert_activity_chain(connection)

    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        activity = (
            await connection.execute(
                sa.text(
                    'SELECT execution_scope, is_custody '
                    'FROM activity_instances WHERE id = :id'
                ),
                {'id': ids['act']},
            )
        ).one()
        run_laboratories = (
            (
                await connection.execute(
                    sa.text(
                        'SELECT laboratory_id FROM activity_runs '
                        'WHERE activity_instance_id = :id'
                    ),
                    {'id': ids['act']},
                )
            )
            .scalars()
            .all()
        )
    assert activity.execution_scope == 'process'
    assert activity.is_custody is False
    assert run_laboratories == [None]


@pytest.mark.asyncio
async def test_index_rejects_duplicate_run_number_without_laboratory(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        ids = await _insert_activity_chain(connection)
    await run_migration(REVISION)

    with pytest.raises(IntegrityError):
        async with migration_database.begin() as connection:
            await _insert_run(connection, ids['act'], run_number=1)


@pytest.mark.asyncio
async def test_index_accepts_same_run_number_for_different_laboratories(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        ids = await _insert_activity_chain(connection)
    await run_migration(REVISION)

    async with migration_database.begin() as connection:
        lab_a = await _insert_laboratory(connection)
        lab_b = await _insert_laboratory(connection)
        await _insert_run(
            connection, ids['act'], run_number=1, laboratory_id=lab_a
        )
        await _insert_run(
            connection, ids['act'], run_number=1, laboratory_id=lab_b
        )

    async with migration_database.connect() as connection:
        count = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM activity_runs '
                'WHERE activity_instance_id = :id'
            ),
            {'id': ids['act']},
        )
    assert count == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_laboratory_waivers_reject_second_active_row(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        ids = await _insert_activity_chain(connection)
    await run_migration(REVISION)

    async with migration_database.begin() as connection:
        laboratory_id = await _insert_laboratory(connection)
    insert = sa.text(
        'INSERT INTO laboratory_waivers '
        '(id, process_instance_id, phase_id, laboratory_id, reason) '
        "VALUES (:id, :proc, :phase, :lab, 'Equipamento quebrado')"
    )
    params = {
        'proc': ids['proc'],
        'phase': ids['phase'],
        'lab': laboratory_id,
    }
    async with migration_database.begin() as connection:
        await connection.execute(insert, {'id': uuid4(), **params})

    with pytest.raises(IntegrityError):
        async with migration_database.begin() as connection:
            await connection.execute(insert, {'id': uuid4(), **params})


@pytest.mark.asyncio
async def test_downgrade_then_upgrade_restores_schema(migration_database):
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)
    async with migration_database.connect() as connection:
        waivers = await connection.scalar(
            sa.text("SELECT to_regclass('public.laboratory_waivers')")
        )
        lab_column = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM information_schema.columns '
                "WHERE table_name = 'activity_runs' "
                "AND column_name = 'laboratory_id'"
            )
        )
    assert waivers is None
    assert lab_column == 0

    await run_migration(REVISION)
    async with migration_database.connect() as connection:
        waivers = await connection.scalar(
            sa.text("SELECT to_regclass('public.laboratory_waivers')")
        )
        indexdef = await connection.scalar(
            sa.text(
                'SELECT indexdef FROM pg_indexes '
                "WHERE indexname = 'uq_activity_runs_number_active'"
            )
        )
    assert waivers is not None
    assert 'laboratory_id' in indexdef
    assert 'NULLS NOT DISTINCT' in indexdef
