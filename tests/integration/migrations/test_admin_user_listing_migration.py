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
async def test_admin_user_listing_migration_upgrade_and_downgrade(migration_database):
    await run_migration('7a3e1c9b4d82')
    await run_downgrade('6f2c9a1d4e70')
    await run_migration('head')
