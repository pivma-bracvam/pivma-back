# ruff: noqa: F401, F811, I001
"""Migração da Spec 014 — perfil BraCVAM + permissão triage.review."""

import pytest
import pytest_asyncio

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '8b701d7bfeae'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_bracvam_profile_and_triage_permission_upgrade_downgrade(
    migration_database,
):
    await run_migration('d3f9a1c47b28')
    await run_downgrade(PREVIOUS)
    await run_migration('head')
