# ruff: noqa: F401, F811, I001
"""Migração da Spec 028 — tabela role_assignment_invites."""

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'fa506675d3f9'
TABLE = 'role_assignment_invites'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _columns(connection):
    return set(
        await connection.scalars(
            sa.text(
                'SELECT column_name FROM information_schema.columns '
                'WHERE table_name = :table'
            ),
            {'table': TABLE},
        )
    )


async def _indexes(connection):
    return set(
        await connection.scalars(
            sa.text(
                'SELECT indexname FROM pg_indexes WHERE tablename = :table'
            ),
            {'table': TABLE},
        )
    )


async def _fk_names(connection):
    return set(
        await connection.scalars(
            sa.text(
                "SELECT constraint_name FROM information_schema."
                "table_constraints WHERE table_name = :table "
                "AND constraint_type = 'FOREIGN KEY'"
            ),
            {'table': TABLE},
        )
    )


@pytest.mark.asyncio
async def test_role_assignment_invites_upgrade_creates_table_and_columns(
    migration_database,
):
    """F-M01: o upgrade cria a tabela com as colunas de data-model.md §1."""
    await run_migration('head')
    async with migration_database.connect() as connection:
        columns = await _columns(connection)
        assert columns == {
            'id',
            'process_instance_id',
            'role_key',
            'laboratory_id',
            'email',
            'channel',
            'token_hash',
            'status',
            'expires_at',
            'accepted_at',
            'accepted_by',
            'revoked_at',
            'revoked_by',
            'created_at',
            'updated_at',
            'deleted_at',
            'created_by',
            'updated_by',
            'deleted_by',
        }

    await run_downgrade(PREVIOUS)


@pytest.mark.asyncio
async def test_role_assignment_invites_upgrade_creates_pending_unique_index(
    migration_database,
):
    """F-M02: índice único parcial por (processo, papel, e-mail) pendente."""
    await run_migration('head')
    async with migration_database.connect() as connection:
        indexes = await _indexes(connection)
        assert 'uq_role_assignment_invites_pending' in indexes

    await run_downgrade(PREVIOUS)


@pytest.mark.asyncio
async def test_role_assignment_invites_upgrade_creates_token_hash_unique_index(
    migration_database,
):
    """F-M03: índice único (não parcial) em token_hash."""
    await run_migration('head')
    async with migration_database.connect() as connection:
        indexes = await _indexes(connection)
        assert 'uq_role_assignment_invites_token_hash' in indexes

    await run_downgrade(PREVIOUS)


@pytest.mark.asyncio
async def test_role_assignment_invites_upgrade_creates_foreign_keys(
    migration_database,
):
    """F-M04: FKs de process_instance_id/laboratory_id/accepted_by/revoked_by."""
    await run_migration('head')
    async with migration_database.connect() as connection:
        fks = await _fk_names(connection)
        assert {
            'fk_role_assignment_invites_process_instance_id',
            'fk_role_assignment_invites_laboratory_id',
            'fk_role_assignment_invites_accepted_by',
            'fk_role_assignment_invites_revoked_by',
        } <= fks

    await run_downgrade(PREVIOUS)


@pytest.mark.asyncio
async def test_role_assignment_invites_downgrade_removes_only_this_table(
    migration_database,
):
    """F-M05: downgrade remove só esta tabela; assignments preservada."""
    await run_migration('head')
    await run_downgrade(PREVIOUS)
    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        )
        assert TABLE not in tables
        assert {'assignments', 'activity_instances', 'process_instances'} <= (
            tables
        )
