# ruff: noqa: F401, F811, I001
"""Migração da Spec 023 — simplificação de perfis globais."""

import pytest
import pytest_asyncio

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '617f10506acc'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_deprecate_legacy_global_profiles_upgrade_and_downgrade(
    migration_database,
):
    await run_migration('6ca4dd19c8fb')
    await run_downgrade(PREVIOUS)
    await run_migration('head')
