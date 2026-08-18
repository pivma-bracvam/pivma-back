import asyncio
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from pivma.core.database.models import table_registry


@pytest_asyncio.fixture
async def migration_database(engine, monkeypatch):
    url = engine.url.render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL', url)
    async with engine.begin() as connection:
        await connection.execute(sa.text('DROP SCHEMA public CASCADE'))
        await connection.execute(sa.text('CREATE SCHEMA public'))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(sa.text('DROP SCHEMA public CASCADE'))
        await connection.execute(sa.text('CREATE SCHEMA public'))
        await connection.run_sync(table_registry.metadata.create_all)


async def run_migration(revision):
    await asyncio.to_thread(
        command.upgrade, Config('alembic.ini'), revision
    )


async def run_downgrade(revision):
    await asyncio.to_thread(
        command.downgrade, Config('alembic.ini'), revision
    )


async def _insert_user(connection, *, username, email, deleted_at=None):
    await connection.execute(
        sa.text(
            'INSERT INTO users '
            '(id, username, email, password, deleted_at) '
            'VALUES '
            '(:id, :username, :email, :password, :deleted_at)'
        ),
        {
            'id': uuid4(),
            'username': username,
            'email': email,
            'password': 'legacy-value',
            'deleted_at': deleted_at,
        },
    )


@pytest.mark.asyncio
async def test_secure_migration_renames_column_and_creates_ci_indexes(
    migration_database,
):
    await run_migration('head')

    async with migration_database.connect() as connection:
        columns = set(
            await connection.scalars(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users'"
                )
            )
        )
        indexes = set(
            await connection.scalars(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'users'"
                )
            )
        )

    assert 'password_hash' in columns
    assert 'password' not in columns
    assert {'uq_users_username_ci', 'uq_users_email_ci'} <= indexes


@pytest.mark.asyncio
async def test_secure_migration_aborts_for_active_collision(
    migration_database,
):
    await run_migration('b72da3430b3e')
    async with migration_database.begin() as connection:
        await _insert_user(
            connection, username='Collision', email='first@example.com'
        )
        await _insert_user(
            connection, username='collision', email='second@example.com'
        )

    with pytest.raises(RuntimeError, match='identifier collisions'):
        await run_migration('head')


@pytest.mark.asyncio
async def test_secure_migration_ignores_deleted_user_collisions(
    migration_database,
):
    await run_migration('b72da3430b3e')
    async with migration_database.begin() as connection:
        await _insert_user(
            connection,
            username='Collision',
            email='first@example.com',
            deleted_at=datetime(2026, 8, 11),
        )
        await _insert_user(
            connection, username='collision', email='second@example.com'
        )

    await run_migration('head')

    async with migration_database.connect() as connection:
        indexes = set(
            await connection.scalars(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'users'"
                )
            )
        )
    assert {'uq_users_username_ci', 'uq_users_email_ci'} <= indexes


@pytest.mark.asyncio
async def test_secure_migration_downgrades_column_rename(migration_database):
    await run_migration('b72da3430b3e')
    async with migration_database.begin() as connection:
        await _insert_user(
            connection, username='valid-migration', email='valid@example.com'
        )

    await run_migration('head')
    await run_downgrade('b72da3430b3e')

    async with migration_database.connect() as connection:
        columns = set(
            await connection.scalars(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users'"
                )
            )
        )
    assert 'password' in columns
    assert 'password_hash' not in columns
