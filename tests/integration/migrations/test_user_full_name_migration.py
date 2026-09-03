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
async def test_upgrade_adds_nullable_full_name_column(migration_database):
    await run_migration('7a3e1c9b4d82')
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
                'username': 'legacy-full-name',
                'email': 'legacy-full-name@example.com',
                'password_hash': 'legacy-hash',
            },
        )

    await run_migration('head')

    async with migration_database.connect() as connection:
        column = await connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'full_name'"
            )
        )
        full_name = await connection.scalar(
            sa.text('SELECT full_name FROM users WHERE id = :id'),
            {'id': user_id},
        )

    assert column.scalar_one() == 'YES'
    assert full_name == 'legacy-full-name'


@pytest.mark.asyncio
async def test_downgrade_removes_full_name_column(migration_database):
    await run_migration('head')

    await run_downgrade('7a3e1c9b4d82')

    async with migration_database.connect() as connection:
        column_count = await connection.scalar(
            sa.text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'full_name'"
            )
        )

    assert column_count == 0
