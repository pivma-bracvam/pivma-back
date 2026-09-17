# ruff: noqa: F401, F811, I001

import pytest
import pytest_asyncio

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_user_management_permission_migration_upgrade_and_downgrade(
    migration_database,
):
    await run_migration('8c5e7a1b9d02')
    await run_downgrade('7b4f5d6e8a90')
    await run_migration('head')
