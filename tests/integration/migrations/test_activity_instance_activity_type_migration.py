# ruff: noqa: F401, F811, I001
"""Migração da Spec 017 — coluna activity_type em activity_instances."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'e5c2f8a41d90'
COLUMN = 'activity_type'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _columns(connection):
    return set(
        await connection.scalars(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'activity_instances'"
            )
        )
    )


@pytest.mark.asyncio
async def test_activity_type_column_upgrade_and_downgrade(migration_database):
    await run_migration('head')
    async with migration_database.connect() as connection:
        assert COLUMN in await _columns(connection)
        nullable, default = (
            await connection.execute(
                sa.text(
                    "SELECT is_nullable, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'activity_instances' "
                    "AND column_name = :col"
                ),
                {'col': COLUMN},
            )
        ).one()
        assert nullable == 'NO'
        assert default is not None
        assert 'form' in default

    await run_downgrade(PREVIOUS)
    async with migration_database.connect() as connection:
        cols = await _columns(connection)
        assert COLUMN not in cols
        # A tabela e as demais colunas continuam de pé.
        assert {'id', 'process_instance_id', 'status'} <= cols
