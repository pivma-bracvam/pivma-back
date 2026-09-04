# ruff: noqa: F401, F811, I001

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_upgrade_sets_full_name_not_null_and_backfills(
    migration_database,
):
    await run_migration('8c5e7a1b9d02')
    user_id = uuid4()
    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO users '
                '(id, username, email, password_hash, full_name) '
                'VALUES (:id, :username, :email, :password_hash, NULL)'
            ),
            {
                'id': user_id,
                'username': 'legacy-null-name',
                'email': 'legacy-null-name@example.com',
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

    assert column.scalar_one() == 'NO'
    assert full_name == 'legacy-null-name'


@pytest.mark.asyncio
async def test_upgrade_enforces_not_null_constraint(migration_database):
    await run_migration('head')

    with pytest.raises((IntegrityError, DBAPIError)):
        async with migration_database.begin() as connection:
            await connection.execute(
                sa.text(
                    'INSERT INTO users '
                    '(id, username, email, password_hash, full_name) '
                    'VALUES (:id, :username, :email, :password_hash, NULL)'
                ),
                {
                    'id': uuid4(),
                    'username': 'null-user',
                    'email': 'null-user@example.com',
                    'password_hash': 'hash',
                },
            )


@pytest.mark.asyncio
async def test_downgrade_reverts_full_name_to_nullable(migration_database):
    await run_migration('head')
    await run_downgrade('8c5e7a1b9d02')

    async with migration_database.connect() as connection:
        column = await connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'full_name'"
            )
        )

    assert column.scalar_one() == 'YES'
