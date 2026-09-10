# ruff: noqa: F401, F811, I001
"""Migração da Spec 014 — perfil BraCVAM + permissão triage.review."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = "8b701d7bfeae"


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_bracvam_profile_and_triage_permission_upgrade_downgrade(
    migration_database,
):
    await run_migration("head")

    async with migration_database.connect() as connection:
        rows = set(
            await connection.execute(
                sa.text(
                    "SELECT ap.system_key, p.code "
                    "FROM access_profile_permissions apx "
                    "JOIN permissions p ON p.id = apx.permission_id "
                    "JOIN access_profiles ap ON ap.id = apx.profile_id "
                    "WHERE p.code = 'triage.review' "
                    "OR ap.system_key = 'bracvam'"
                )
            )
        )
        bracvam_desc = await connection.scalar(
            sa.text(
                "SELECT description FROM access_profiles "
                "WHERE system_key = 'bracvam'"
            )
        )

    assert rows == {
        ("bracvam", "triage.review"),
        ("bracvam", "ai_evaluations.read"),
        ("bracvam", "ai_evaluations.manage"),
        ("administrator", "triage.review"),
    }
    assert bracvam_desc is not None

    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        bracvam_profiles = await connection.scalar(
            sa.text(
                "SELECT count(*) FROM access_profiles "
                "WHERE system_key = 'bracvam'"
            )
        )
        triage_perms = await connection.scalar(
            sa.text(
                "SELECT count(*) FROM permissions WHERE code = 'triage.review'"
            )
        )
        orphan_comps = await connection.scalar(
            sa.text(
                "SELECT count(*) FROM access_profile_permissions apx "
                "LEFT JOIN permissions p ON p.id = apx.permission_id "
                "LEFT JOIN access_profiles ap ON ap.id = apx.profile_id "
                "WHERE p.id IS NULL OR ap.id IS NULL"
            )
        )

    assert (bracvam_profiles, triage_perms, orphan_comps) == (0, 0, 0)
