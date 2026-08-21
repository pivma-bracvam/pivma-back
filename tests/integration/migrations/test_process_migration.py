# ruff: noqa: F401, F811, I001

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_process_migration_creates_and_downgrades_tables(
    migration_database,
):
    await run_migration('head')

    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            )
        )

    expected_tables = {
        'process_templates',
        'process_template_versions',
        'form_templates',
        'form_fields',
        'process_instances',
        'phases',
        'activity_instances',
        'activity_runs',
        'activity_dependencies',
        'tasks',
        'artifacts',
        'form_instances',
        'form_values',
        'field_reviews',
        'decisions',
        'assignments',
        'audit_events',
    }

    assert expected_tables.issubset(tables)

    await run_downgrade('c1e4a9f8b312')
    async with migration_database.connect() as connection:
        downgraded_tables = set(
            await connection.scalars(
                sa.text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            )
        )

    assert not expected_tables.intersection(downgraded_tables)
    assert 'access_profiles' in downgraded_tables
    assert 'users' in downgraded_tables
