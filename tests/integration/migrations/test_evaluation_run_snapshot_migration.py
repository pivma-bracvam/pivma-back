# ruff: noqa: F401, F811, I001
"""Migração da Spec 014 — coluna evaluated_content_snapshot."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = "d3f9a1c47b28"
COLUMN = "evaluated_content_snapshot"


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _columns(connection):
    return set(
        await connection.scalars(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'evaluation_runs'"
            )
        )
    )


@pytest.mark.asyncio
async def test_snapshot_column_upgrade_and_downgrade(migration_database):
    await run_migration("head")
    async with migration_database.connect() as connection:
        assert COLUMN in await _columns(connection)

    await run_downgrade(PREVIOUS)
    async with migration_database.connect() as connection:
        cols = await _columns(connection)
        assert COLUMN not in cols
        # A tabela e as demais colunas continuam de pé.
        assert {"id", "process_instance_id", "status"} <= cols
