# ruff: noqa: F401, F811, I001

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PERMISSION_ID = UUID('00000000-0000-0000-0000-000000000108')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
COMPOSITION_ID = UUID('00000000-0000-0000-0000-000000000208')


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _seed_preexisting_records(migration_database):
    await run_migration('6f2c9a1d4e70')
    user_id = uuid4()
    profile_id = uuid4()
    assignment_id = uuid4()
    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO users '
                '(id, username, email, password_hash) '
                'VALUES (:id, :username, :email, :password_hash)'
            ),
            {
                'id': user_id,
                'username': f'legacy-{user_id.hex[:12]}',
                'email': f'{user_id.hex[:12]}@example.com',
                'password_hash': 'legacy-hash',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO access_profiles '
                '(id, system_key, name, description) '
                'VALUES (:id, :system_key, :name, :description)'
            ),
            {
                'id': profile_id,
                'system_key': None,
                'name': f'Legacy profile {profile_id.hex[:12]}',
                'description': 'Legacy profile',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO user_access_profiles '
                '(id, user_id, profile_id) '
                'VALUES (:id, :user_id, :profile_id)'
            ),
            {
                'id': assignment_id,
                'user_id': user_id,
                'profile_id': profile_id,
            },
        )
    await run_migration('head')
    return {
        'user_id': user_id,
        'profile_id': profile_id,
        'assignment_id': assignment_id,
    }


@pytest.mark.asyncio
async def test_upgrade_seeds_users_read_permission(migration_database):
    await run_migration('head')

    async with migration_database.connect() as connection:
        permission = await connection.execute(
            sa.text('SELECT id, code FROM permissions WHERE id = :id'),
            {'id': PERMISSION_ID},
        )
        row = permission.mappings().one()

    assert row == {'id': PERMISSION_ID, 'code': 'users.read'}


@pytest.mark.asyncio
async def test_upgrade_composes_users_read_with_administrator(
    migration_database,
):
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
async def test_upgrade_grants_users_read_to_preexisting_administrator(
    migration_database,
):
    await run_migration('6f2c9a1d4e70')
    user_id = uuid4()
    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO users '
                '(id, username, email, password_hash) '
                'VALUES (:id, :username, :email, :password_hash)'
            ),
            {
                'id': user_id,
                'username': f'admin-{user_id.hex[:12]}',
                'email': f'{user_id.hex[:12]}@example.com',
                'password_hash': 'legacy-hash',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO user_access_profiles '
                '(id, user_id, profile_id) '
                'VALUES (:id, :user_id, :profile_id)'
            ),
            {
                'id': uuid4(),
                'user_id': user_id,
                'profile_id': ADMIN_PROFILE_ID,
            },
        )

    await run_migration('head')
    async with migration_database.connect() as connection:
        permission_count = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM permissions p '
                'JOIN access_profile_permissions app '
                'ON app.permission_id = p.id '
                'JOIN user_access_profiles uap '
                'ON uap.profile_id = app.profile_id '
                'WHERE uap.user_id = :user_id '
                'AND uap.deleted_at IS NULL '
                'AND app.deleted_at IS NULL '
                'AND p.id = :permission_id'
            ),
            {'user_id': user_id, 'permission_id': PERMISSION_ID},
        )

    assert permission_count == 1


@pytest.mark.asyncio
async def test_upgrade_does_not_compose_users_read_with_non_admin_profiles(
    migration_database,
):
    await run_migration('head')

    async with migration_database.connect() as connection:
        composition_count = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions app '
                'JOIN access_profiles ap ON ap.id = app.profile_id '
                'WHERE app.permission_id = :permission_id '
                "AND ap.system_key <> 'administrator'"
            ),
            {'permission_id': PERMISSION_ID},
        )

    assert composition_count == 0


@pytest.mark.asyncio
async def test_downgrade_removes_later_users_read_compositions(
    migration_database,
):
    records = await _seed_preexisting_records(migration_database)
    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO permissions (id, code, description) '
                'VALUES (:id, :code, :description) '
                'ON CONFLICT (id) DO NOTHING'
            ),
            {
                'id': PERMISSION_ID,
                'code': 'users.read',
                'description': 'Consultar contas de usuários.',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO access_profile_permissions '
                '(id, profile_id, permission_id) '
                'VALUES (:id, :profile_id, :permission_id)'
            ),
            {
                'id': uuid4(),
                'profile_id': records['profile_id'],
                'permission_id': PERMISSION_ID,
            },
        )

    await run_downgrade('6f2c9a1d4e70')
    async with migration_database.connect() as connection:
        composition_count = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions '
                'WHERE permission_id = :permission_id'
            ),
            {'permission_id': PERMISSION_ID},
        )

    assert composition_count == 0


@pytest.mark.asyncio
async def test_downgrade_preserves_preexisting_user(migration_database):
    records = await _seed_preexisting_records(migration_database)
    await run_downgrade('6f2c9a1d4e70')

    async with migration_database.connect() as connection:
        user_count = await connection.scalar(
            sa.text('SELECT count(*) FROM users WHERE id = :id'),
            {'id': records['user_id']},
        )

    assert user_count == 1


@pytest.mark.asyncio
async def test_downgrade_preserves_preexisting_profile(migration_database):
    records = await _seed_preexisting_records(migration_database)
    await run_downgrade('6f2c9a1d4e70')

    async with migration_database.connect() as connection:
        profile_count = await connection.scalar(
            sa.text('SELECT count(*) FROM access_profiles WHERE id = :id'),
            {'id': records['profile_id']},
        )

    assert profile_count == 1


@pytest.mark.asyncio
async def test_downgrade_preserves_preexisting_profile_assignment(
    migration_database,
):
    records = await _seed_preexisting_records(migration_database)
    await run_downgrade('6f2c9a1d4e70')

    async with migration_database.connect() as connection:
        assignment_count = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM user_access_profiles WHERE id = :id'
            ),
            {'id': records['assignment_id']},
        )

    assert assignment_count == 1
