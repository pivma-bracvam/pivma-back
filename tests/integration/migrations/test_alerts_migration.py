# ruff: noqa: F401, F811, I001
"""Migração da Spec 047: tabela de alerts."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'c4e6a8b0d2f1'
REVISION = 'b7d3e9a1c5f2'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _scalar(engine, sql):
    async with engine.connect() as connection:
        return await connection.scalar(sa.text(sql))


async def _rows(engine, sql):
    async with engine.connect() as connection:
        return (await connection.execute(sa.text(sql))).all()


@pytest.mark.asyncio
async def test_upgrade_creates_alerts_columns(migration_database):
    await run_migration(REVISION)

    rows = await _rows(
        migration_database,
        'SELECT column_name, is_nullable, data_type '
        'FROM information_schema.columns '
        "WHERE table_name = 'alerts'",
    )
    columns = {
        row.column_name: (row.is_nullable, row.data_type) for row in rows
    }
    assert columns['user_id'][0] == 'NO'
    assert columns['kind'][0] == 'NO'
    assert columns['target_type'][0] == 'NO'
    assert columns['process_instance_id'][0] == 'NO'
    assert columns['target_id'][0] == 'YES'
    assert columns['params'] == ('NO', 'jsonb')
    assert columns['read_at'][0] == 'YES'
    for audit in ('created_at', 'created_by', 'updated_by', 'deleted_at'):
        assert audit in columns


@pytest.mark.asyncio
async def test_upgrade_creates_alerts_foreign_keys(migration_database):
    await run_migration(REVISION)

    rows = await _rows(
        migration_database,
        'SELECT conname, pg_get_constraintdef(oid) AS definition '
        "FROM pg_constraint WHERE conrelid = 'alerts'::regclass "
        "AND contype = 'f'",
    )
    defs = {row.conname: row.definition for row in rows}
    assert 'REFERENCES users(id)' in defs['fk_alerts_user_id']
    assert (
        'REFERENCES process_instances(id)'
        in defs['fk_alerts_process_instance_id']
    )


@pytest.mark.asyncio
async def test_upgrade_creates_target_check_constraint(migration_database):
    await run_migration(REVISION)

    definition = await _scalar(
        migration_database,
        'SELECT pg_get_constraintdef(oid) FROM pg_constraint '
        "WHERE conname = 'ck_alerts_target_id_by_type'",
    )
    assert "target_type)::text = 'process'::text" in definition
    assert 'target_id IS NULL' in definition


@pytest.mark.asyncio
async def test_upgrade_creates_alerts_indexes(migration_database):
    await run_migration(REVISION)

    rows = await _rows(
        migration_database,
        'SELECT indexname, indexdef FROM pg_indexes '
        "WHERE tablename = 'alerts'",
    )
    indexdefs = {row.indexname: row.indexdef for row in rows}
    assert '(user_id, created_at DESC)' in indexdefs['ix_alerts_user_created']
    assert 'WHERE (read_at IS NULL)' in indexdefs['ix_alerts_user_unread']


@pytest.mark.asyncio
async def test_downgrade_drops_alerts_table(migration_database):
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    assert not await _scalar(
        migration_database,
        "SELECT count(*) FROM pg_tables WHERE tablename = 'alerts'",
    )
