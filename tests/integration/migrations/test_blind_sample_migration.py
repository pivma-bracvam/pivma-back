# ruff: noqa: F401, F811, I001
"""Migração da Spec 031: substâncias do estudo e códigos cegos."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '7e21b4c0a9d3'
REVISION = 'cc6c65843305'
TABLES = ('study_substances', 'blind_sample_codes')
PARTIAL_INDEXES = (
    'uq_study_substances_process_cas_active',
    'uq_blind_sample_codes_process_code_active',
    'uq_blind_sample_codes_substance_lab_active',
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _existing_tables(engine):
    async with engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                'SELECT tablename FROM pg_tables '
                "WHERE schemaname = 'public' AND tablename = ANY(:names)"
            ),
            {'names': list(TABLES)},
        )
        return {row.tablename for row in rows}


@pytest.mark.asyncio
async def test_upgrade_creates_sample_tables_and_partial_indexes(
    migration_database,
):
    await run_migration(REVISION)

    assert await _existing_tables(migration_database) == set(TABLES)
    async with migration_database.connect() as connection:
        rows = await connection.execute(
            sa.text(
                'SELECT indexname, indexdef FROM pg_indexes '
                'WHERE indexname = ANY(:names)'
            ),
            {'names': list(PARTIAL_INDEXES)},
        )
        indexdefs = {row.indexname: row.indexdef for row in rows}
    assert set(indexdefs) == set(PARTIAL_INDEXES)
    for indexdef in indexdefs.values():
        assert 'UNIQUE' in indexdef
        assert 'WHERE (deleted_at IS NULL)' in indexdef


@pytest.mark.asyncio
async def test_downgrade_drops_sample_tables(migration_database):
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    assert await _existing_tables(migration_database) == set()
