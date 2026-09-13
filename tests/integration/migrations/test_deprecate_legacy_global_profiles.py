# ruff: noqa: F401, F811, I001
"""Migração da Spec 023 — descontinuação dos perfis globais sem função."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '617f10506acc'
MANAGEMENT_GROUP_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000002')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
BRACVAM_PROFILE_ID = UUID('00000000-0000-0000-0000-00000000000a')
DEPRECATED_SYSTEM_KEYS = (
    'management_group',
    'study_manager',
    'participating_laboratory',
    'ad_hoc_evaluator',
    'reviewer',
    'specialist',
    'statistical_analyst',
    'proponent',
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


@pytest.mark.asyncio
async def test_deprecated_profiles_and_assignments_are_soft_deleted(
    migration_database,
):
    await run_migration(PREVIOUS)

    user_id = uuid4()
    async with migration_database.begin() as connection:
        await connection.execute(
            sa.text(
                'INSERT INTO users '
                '(id, username, email, password_hash, full_name) '
                'VALUES '
                '(:id, :username, :email, :password_hash, :full_name)'
            ),
            {
                'id': user_id,
                'username': 'legacy-management-group-user',
                'email': 'legacy-management-group-user@test.com',
                'password_hash': 'legacy-value',
                'full_name': 'Legacy Management Group User',
            },
        )
        await connection.execute(
            sa.text(
                'INSERT INTO user_access_profiles (id, user_id, profile_id) '
                'VALUES (:id, :user_id, :profile_id)'
            ),
            {
                'id': uuid4(),
                'user_id': user_id,
                'profile_id': MANAGEMENT_GROUP_PROFILE_ID,
            },
        )

    await run_migration('head')

    async with migration_database.connect() as connection:
        deprecated_deleted_at = await connection.execute(
            sa.text(
                'SELECT system_key, deleted_at FROM access_profiles '
                'WHERE system_key = ANY(:keys)'
            ),
            {'keys': list(DEPRECATED_SYSTEM_KEYS)},
        )
        deprecated_rows = deprecated_deleted_at.all()
        assignment_deleted_at = await connection.scalar(
            sa.text(
                'SELECT deleted_at FROM user_access_profiles '
                'WHERE user_id = :user_id AND profile_id = :profile_id'
            ),
            {'user_id': user_id, 'profile_id': MANAGEMENT_GROUP_PROFILE_ID},
        )
        platform_wide_deleted_at = await connection.execute(
            sa.text(
                'SELECT system_key, deleted_at FROM access_profiles '
                "WHERE system_key IN ('administrator', 'bracvam')"
            )
        )

    assert len(deprecated_rows) == len(DEPRECATED_SYSTEM_KEYS)
    assert all(row.deleted_at is not None for row in deprecated_rows)
    assert assignment_deleted_at is not None
    assert {
        row.system_key: row.deleted_at is None
        for row in platform_wide_deleted_at
    } == {'administrator': True, 'bracvam': True}

    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        restored = await connection.execute(
            sa.text(
                'SELECT system_key, deleted_at FROM access_profiles '
                'WHERE system_key = ANY(:keys)'
            ),
            {'keys': list(DEPRECATED_SYSTEM_KEYS)},
        )
        restored_rows = restored.all()
        assignment_restored = await connection.scalar(
            sa.text(
                'SELECT deleted_at FROM user_access_profiles '
                'WHERE user_id = :user_id AND profile_id = :profile_id'
            ),
            {'user_id': user_id, 'profile_id': MANAGEMENT_GROUP_PROFILE_ID},
        )

    assert all(row.deleted_at is None for row in restored_rows)
    assert assignment_restored is None
