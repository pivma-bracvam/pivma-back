# ruff: noqa: F401, F811, I001

from uuid import UUID

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PERMISSION_ID = UUID('00000000-0000-0000-0000-000000000109')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
COMPOSITION_ID = UUID('00000000-0000-0000-0000-000000000209')


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_upgrade_seeds_users_manage_permission(migration_database):
    await run_migration('7b4f5d6e8a90')
    await run_migration('head')

    async with migration_database.connect() as connection:
        permission = await connection.execute(
            sa.text('SELECT id, code FROM permissions WHERE id = :id'),
            {'id': PERMISSION_ID},
        )
        row = permission.mappings().one()

    assert row == {'id': PERMISSION_ID, 'code': 'users.manage'}


@pytest.mark.asyncio
async def test_upgrade_composes_users_manage_with_administrator(
    migration_database,
):
    await run_migration('7b4f5d6e8a90')
    await run_migration('head')

    async with migration_database.connect() as connection:
        composition = await connection.execute(
            sa.text(
                'SELECT id FROM access_profile_permissions '
                'WHERE id = :id AND profile_id = :profile_id '
                'AND permission_id = :permission_id'
            ),
            {
                'id': COMPOSITION_ID,
                'profile_id': ADMIN_PROFILE_ID,
                'permission_id': PERMISSION_ID,
            },
        )

    assert composition.scalar_one() == COMPOSITION_ID


@pytest.mark.asyncio
async def test_downgrade_removes_users_manage_permission_and_composition(
    migration_database,
):
    await run_migration('head')
    await run_downgrade('7b4f5d6e8a90')

    async with migration_database.connect() as connection:
        permission = await connection.scalar(
            sa.text('SELECT COUNT(*) FROM permissions WHERE id = :id'),
            {'id': PERMISSION_ID},
        )
        composition = await connection.scalar(
            sa.text(
                'SELECT COUNT(*) FROM access_profile_permissions '
                'WHERE id = :id'
            ),
            {'id': COMPOSITION_ID},
        )

    assert permission == 0
    assert composition == 0
