# ruff: noqa: F401, F811, I001
"""Migração da Spec 039: tabela de tokens de redefinição de senha."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '5af69c71be3c'
REVISION = '6fe19f1c95e9'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _fetch(engine, query):
    async with engine.connect() as connection:
        return (await connection.execute(sa.text(query))).all()


@pytest.mark.asyncio
async def test_upgrade_creates_password_reset_tokens_table(
    migration_database,
):
    await run_migration(REVISION)

    rows = await _fetch(
        migration_database,
        'SELECT column_name FROM information_schema.columns '
        "WHERE table_name = 'password_reset_tokens'",
    )
    assert {row.column_name for row in rows} == {
        'id',
        'user_id',
        'token_hash',
        'expires_at',
        'used_at',
        'created_at',
        'updated_at',
        'deleted_at',
        'created_by',
        'updated_by',
        'deleted_by',
    }


async def _indexdefs(engine):
    rows = await _fetch(
        engine,
        'SELECT indexname, indexdef FROM pg_indexes '
        "WHERE tablename = 'password_reset_tokens'",
    )
    return {row.indexname: row.indexdef for row in rows}


@pytest.mark.asyncio
async def test_upgrade_creates_unique_token_hash_index(migration_database):
    await run_migration(REVISION)

    indexdef = (await _indexdefs(migration_database))[
        'uq_password_reset_tokens_token_hash'
    ]
    assert indexdef.startswith('CREATE UNIQUE INDEX')
    assert '(token_hash)' in indexdef


@pytest.mark.asyncio
async def test_upgrade_creates_user_id_index(migration_database):
    await run_migration(REVISION)

    indexdef = (await _indexdefs(migration_database))[
        'ix_password_reset_tokens_user_id'
    ]
    assert '(user_id)' in indexdef


@pytest.mark.asyncio
async def test_downgrade_drops_password_reset_tokens_table(
    migration_database,
):
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    rows = await _fetch(
        migration_database,
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename = 'password_reset_tokens'",
    )
    assert rows == []
