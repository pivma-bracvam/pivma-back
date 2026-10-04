# ruff: noqa: F401, F811, I001
"""Migração da Spec 040 (FR-047): orientação ao laboratório na decisão."""

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

PREVIOUS = '9d4e2b7a1c30'
REVISION = 'b7c3e1f2a9d4'
TABLE = 'sample_receipt_nonconformities'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_upgrade_adds_nullable_lab_guidance(migration_database):
    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        nullable = await connection.scalar(
            sa.text(
                'SELECT is_nullable FROM information_schema.columns '
                'WHERE table_name = :table AND column_name = :column'
            ),
            {'table': TABLE, 'column': 'lab_guidance'},
        )
    assert nullable == 'YES'


@pytest.mark.asyncio
async def test_downgrade_removes_lab_guidance(migration_database):
    await run_migration(REVISION)
    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        columns = await _columns(connection, TABLE)
    assert 'lab_guidance' not in columns
