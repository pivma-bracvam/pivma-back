# ruff: noqa: F401, F811, I001
"""Migração da Spec 036: tabela de notificações."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'cc6c65843305'
REVISION = '6eb1ae208b7d'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _table_exists(engine):
    async with engine.connect() as connection:
        return bool(
            await connection.scalar(
                sa.text(
                    'SELECT count(*) FROM pg_tables '
                    "WHERE schemaname = 'public' "
                    "AND tablename = 'notifications'"
                )
            )
        )


@pytest.mark.asyncio
async def test_upgrade_creates_notifications_table_and_indexes(
    migration_database,
):
    await run_migration(REVISION)

    assert await _table_exists(migration_database)
    async with migration_database.connect() as connection:
        rows = await connection.execute(
            sa.text(
                'SELECT indexname, indexdef FROM pg_indexes '
                "WHERE tablename = 'notifications'"
            )
        )
        indexdefs = {row.indexname: row.indexdef for row in rows}
    assert "WHERE (((status)::text = 'pending'::text) AND (deleted_at IS NULL))" in (
        indexdefs['ix_notifications_pending_due']
    )
    assert '(subject_type, subject_id)' in indexdefs['ix_notifications_subject']


@pytest.mark.asyncio
async def test_downgrade_drops_notifications_table(migration_database):
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    assert not await _table_exists(migration_database)
