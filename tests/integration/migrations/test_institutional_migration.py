# ruff: noqa: F401, F811, I001

from uuid import uuid4

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
async def test_institutional_migration_seeds_only_administrator_and_downgrades(
    migration_database,
):
    await run_migration('head')
    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    'SELECT tablename FROM pg_tables '
                    "WHERE schemaname = 'public'"
                )
            )
        )
        affiliations = await connection.scalar(
            sa.text('SELECT count(*) FROM user_institutional_affiliations')
        )

    assert {
        'institutions',
        'laboratories',
        'user_institutional_affiliations',
        'institutional_changes',
    } <= tables
    assert affiliations == 0

    await run_downgrade('1bd1b3d5ddad')
    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    'SELECT tablename FROM pg_tables '
                    "WHERE schemaname = 'public'"
                )
            )
        )
    assert 'users' in tables
    assert 'institutions' not in tables


@pytest.mark.asyncio
async def test_institutional_migration_preserves_user_and_rbac_assignment(
    migration_database,
):
    await run_migration('1bd1b3d5ddad')
    user_id = uuid4()
    profile_id = uuid4()
    assignment_id = uuid4()
    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO users (id, username, email, password_hash) '
                'VALUES (:id, :username, :email, :password_hash)'
            ),
            {
                'id': user_id,
                'username': 'existing-user',
                'email': 'existing-user@example.com',
                'password_hash': 'existing-hash',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO access_profiles (id, system_key, name, description) '
                'VALUES (:id, :system_key, :name, :description)'
            ),
            {
                'id': profile_id,
                'system_key': 'administrator',
                'name': 'Administrador',
                'description': 'Administrador de teste',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO user_access_profiles (id, user_id, profile_id) '
                'VALUES (:id, :user_id, :profile_id)'
            ),
            {
                'id': assignment_id,
                'user_id': user_id,
                'profile_id': profile_id,
            },
        )

    await run_migration('head')

    async with migration_database.connect() as connection:
        preserved_user = (
            await connection.execute(
                sa.text(
                    'SELECT username, email, password_hash FROM users '
                    'WHERE id = :id'
                ),
                {'id': user_id},
            )
        ).mappings().one()
        preserved_assignment = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM user_access_profiles '
                'WHERE id = :assignment_id AND user_id = :user_id '
                'AND profile_id = :profile_id'
            ),
            {
                'assignment_id': assignment_id,
                'user_id': user_id,
                'profile_id': profile_id,
            },
        )

    assert dict(preserved_user) == {
        'username': 'existing-user',
        'email': 'existing-user@example.com',
        'password_hash': 'existing-hash',
    }
    assert preserved_assignment == 1
