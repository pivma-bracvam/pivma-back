# ruff: noqa: F401, F811, I001
"""Migração da Spec 043: ordem dos tipos e sequência anual do código."""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_sample_receipt_migration import (
    _columns,
)
from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'a3d5f7b9c1e2'
REVISION = 'c4e6a8b0d2f1'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _insert_template(connection):
    template_id = uuid4()
    await connection.execute(
        sa.text(
            'INSERT INTO process_templates (id, key, name, is_active) '
            "VALUES (:id, :key, 'Legado', true)"
        ),
        {'id': template_id, 'key': f'legacy-{template_id.hex[:12]}'},
    )
    return template_id


@pytest.mark.asyncio
async def test_upgrade_adds_nullable_display_order_and_keeps_templates(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        template_id = await _insert_template(connection)

    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        column = (
            await connection.execute(
                sa.text(
                    'SELECT data_type, is_nullable '
                    'FROM information_schema.columns '
                    "WHERE table_name = 'process_templates' "
                    "AND column_name = 'display_order'"
                )
            )
        ).one()
        display_order = await connection.scalar(
            sa.text(
                'SELECT display_order FROM process_templates WHERE id = :id'
            ),
            {'id': template_id},
        )
    assert column.data_type == 'integer'
    assert column.is_nullable == 'YES'
    assert display_order is None


@pytest.mark.asyncio
async def test_upgrade_creates_process_code_sequences(migration_database):
    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        columns = await _columns(connection, 'process_code_sequences')
        primary_key = await connection.scalars(
            sa.text(
                'SELECT kcu.column_name '
                'FROM information_schema.table_constraints tc '
                'JOIN information_schema.key_column_usage kcu '
                'ON kcu.constraint_name = tc.constraint_name '
                "WHERE tc.table_name = 'process_code_sequences' "
                "AND tc.constraint_type = 'PRIMARY KEY'"
            )
        )
        last_value_nullable = await connection.scalar(
            sa.text(
                'SELECT is_nullable FROM information_schema.columns '
                "WHERE table_name = 'process_code_sequences' "
                "AND column_name = 'last_value'"
            )
        )
    assert columns == {
        'year',
        'last_value',
        'created_at',
        'updated_at',
        'deleted_at',
        'created_by',
        'updated_by',
        'deleted_by',
    }
    assert primary_key.all() == ['year']
    assert last_value_nullable == 'NO'


@pytest.mark.asyncio
async def test_downgrade_drops_table_and_column_and_keeps_templates(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        template_id = await _insert_template(connection)
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        columns = await _columns(connection, 'process_templates')
        sequences_table = await connection.scalar(
            sa.text("SELECT to_regclass('process_code_sequences')")
        )
        kept = await connection.scalar(
            sa.text('SELECT count(*) FROM process_templates WHERE id = :id'),
            {'id': template_id},
        )
    assert 'display_order' not in columns
    assert sequences_table is None
    assert kept == 1
