# ruff: noqa: F401, F811, I001
"""Migração da Issue #39 — permissão form_templates.manage."""

import pytest
import pytest_asyncio

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '6ca4dd19c8fb'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_form_templates_manage_permission_upgrade_and_downgrade(
    migration_database,
):
    await run_migration('fa506675d3f9')
    await run_downgrade(PREVIOUS)
    await run_migration('head')
