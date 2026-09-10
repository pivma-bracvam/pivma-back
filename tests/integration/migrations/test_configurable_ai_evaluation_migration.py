"""Migração 8b701d7bfeae — configurable_ai_evaluation (Spec 013)."""
# ruff: noqa: F401, F811, I001

from uuid import UUID

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

EXPECTED_PERMISSION_GRANTS = 2

READ_PERMISSION_ID = UUID('00000000-0000-0000-0000-00000000010a')
MANAGE_PERMISSION_ID = UUID('00000000-0000-0000-0000-00000000010b')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')

NEW_TABLES = (
    'evaluation_definitions',
    'evaluation_versions',
    'evaluation_criteria',
    'evaluation_references',
    'evaluation_assignments',
    'evaluation_runs',
    'evaluation_run_items',
    'direct_review_requests',
    'reviewer_feedback',
    'evaluation_test_runs',
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_upgrade_creates_all_new_tables(migration_database):
    await run_migration('head')

    async with migration_database.connect() as connection:
        for table in NEW_TABLES:
            exists = await connection.scalar(
                sa.text('SELECT to_regclass(:name)'), {'name': table}
            )
            assert exists == table


@pytest.mark.asyncio
async def test_upgrade_enforces_single_draft_per_definition(
    migration_database,
):
    await run_migration('head')
    definition_id = UUID('11111111-1111-1111-1111-111111111111')

    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO evaluation_definitions (id, name, slug, mode) '
                "VALUES (:id, 'N', 'slug-a', 'simple')"
            ),
            {'id': definition_id},
        )
        await connection.execute(
            sa.text(
                'INSERT INTO evaluation_versions '
                '(id, definition_id, version_number, objective, status, '
                'test_run_count) VALUES '
                "(gen_random_uuid(), :d, 1, 'o', 'draft', 0)"
            ),
            {'d': definition_id},
        )

    with pytest.raises(IntegrityError):
        async with migration_database.begin() as connection:
            await connection.execute(
                sa.text(
                    'INSERT INTO evaluation_versions '
                    '(id, definition_id, version_number, objective, status, '
                    'test_run_count) VALUES '
                    "(gen_random_uuid(), :d, 2, 'o', 'draft', 0)"
                ),
                {'d': definition_id},
            )


@pytest.mark.asyncio
async def test_upgrade_seeds_ai_evaluation_permissions(migration_database):
    await run_migration('head')

    async with migration_database.connect() as connection:
        codes = await connection.execute(
            sa.text(
                'SELECT code FROM permissions WHERE id IN (:r, :m) '
                'ORDER BY code'
            ),
            {'r': READ_PERMISSION_ID, 'm': MANAGE_PERMISSION_ID},
        )
        grants = await connection.scalar(
            sa.text(
                'SELECT COUNT(*) FROM access_profile_permissions '
                'WHERE permission_id IN (:r, :m)'
            ),
            {'r': READ_PERMISSION_ID, 'm': MANAGE_PERMISSION_ID},
        )

    assert [row[0] for row in codes] == [
        'ai_evaluations.manage',
        'ai_evaluations.read',
    ]
    assert grants == EXPECTED_PERMISSION_GRANTS


@pytest.mark.asyncio
async def test_downgrade_removes_tables_and_permissions(migration_database):
    await run_migration('head')
    await run_downgrade('62eee61a6ad3')

    async with migration_database.connect() as connection:
        for table in NEW_TABLES:
            exists = await connection.scalar(
                sa.text('SELECT to_regclass(:name)'), {'name': table}
            )
            assert exists is None
        permissions = await connection.scalar(
            sa.text('SELECT COUNT(*) FROM permissions WHERE id IN (:r, :m)'),
            {'r': READ_PERMISSION_ID, 'm': MANAGE_PERMISSION_ID},
        )

    assert permissions == 0
