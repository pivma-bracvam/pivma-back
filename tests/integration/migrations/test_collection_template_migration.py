# ruff: noqa: F401, F811, I001
"""Migração da Spec 041: catálogo de templates de coleta."""

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.bootstrap_system import (
    sync_canonical_permissions,
    sync_canonical_profiles,
    sync_profile_permissions,
)

from tests.integration.migrations.test_sample_receipt_migration import (
    _columns,
    _tables,
)
from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'b7c3e1f2a9d4'
REVISION = 'e8a4c2f61b37'
TABLES = {'collection_templates', 'collection_template_columns'}
CHECKS = {
    'ck_collection_templates_min_experiments',
    'ck_collection_templates_min_replicates',
    'ck_collection_template_columns_type',
    'ck_collection_template_columns_position',
}
PARTIAL_INDEXES = (
    'uq_collection_template_columns_key_active',
    'uq_collection_template_columns_position_active',
)
PERMISSION_ID = '00000000-0000-0000-0000-00000000010e'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _insert_process(connection):
    """Um processo anterior à migração, em SQL puro."""
    await connection.execute(
        sa.text(
            'INSERT INTO process_templates (id, key, name, is_active) '
            "VALUES ('00000000-0000-0000-0000-0000000000a1', 'legacy', "
            "'Legacy', true)"
        )
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_template_versions '
            '(id, template_id, version_number, definition_payload, '
            'is_published) '
            "VALUES ('00000000-0000-0000-0000-0000000000a2', "
            "'00000000-0000-0000-0000-0000000000a1', 1, '{}'::jsonb, true)"
        )
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_instances '
            '(id, template_version_id, code, title, status) '
            "VALUES ('00000000-0000-0000-0000-0000000000a3', "
            "'00000000-0000-0000-0000-0000000000a2', 'VAL-LEGACY', "
            "'Legacy', 'OPEN')"
        )
    )


@pytest.mark.asyncio
async def test_upgrade_creates_tables_checks_and_partial_indexes(
    migration_database,
):
    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        tables = await _tables(connection)
        checks = set(
            await connection.scalars(
                sa.text(
                    'SELECT conname FROM pg_constraint '
                    "WHERE contype = 'c' AND conname = ANY(:names)"
                ),
                {'names': list(CHECKS)},
            )
        )
        indexdefs = {
            row.indexname: row.indexdef
            for row in await connection.execute(
                sa.text(
                    'SELECT indexname, indexdef FROM pg_indexes '
                    'WHERE indexname = ANY(:names)'
                ),
                {'names': list(PARTIAL_INDEXES)},
            )
        }
    assert TABLES <= tables
    assert checks == CHECKS
    assert set(indexdefs) == set(PARTIAL_INDEXES)
    for indexdef in indexdefs.values():
        assert 'UNIQUE' in indexdef
        assert 'WHERE (deleted_at IS NULL)' in indexdef


@pytest.mark.asyncio
async def test_upgrade_adds_nullable_indexed_link_on_processes(
    migration_database,
):
    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        nullable = await connection.scalar(
            sa.text(
                'SELECT is_nullable FROM information_schema.columns '
                "WHERE table_name = 'process_instances' "
                "AND column_name = 'collection_template_id'"
            )
        )
        foreign_table = await connection.scalar(
            sa.text(
                'SELECT ccu.table_name '
                'FROM information_schema.key_column_usage kcu '
                'JOIN information_schema.constraint_column_usage ccu '
                'ON ccu.constraint_name = kcu.constraint_name '
                "WHERE kcu.table_name = 'process_instances' "
                "AND kcu.column_name = 'collection_template_id'"
            )
        )
        index = await connection.scalar(
            sa.text(
                'SELECT indexdef FROM pg_indexes WHERE indexname = '
                "'ix_process_instances_collection_template_id'"
            )
        )
    assert nullable == 'YES'
    assert foreign_table == 'collection_templates'
    assert '(collection_template_id)' in index


@pytest.mark.asyncio
async def test_upgrade_inserts_permission_without_profile_composition(
    migration_database,
):
    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        permission_id = await connection.scalar(
            sa.text(
                'SELECT id::text FROM permissions '
                "WHERE code = 'collection_templates.manage'"
            )
        )
        compositions = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions '
                'WHERE permission_id = :id'
            ),
            {'id': PERMISSION_ID},
        )
    assert permission_id == PERMISSION_ID
    assert compositions == 0


@pytest.mark.asyncio
async def test_upgrade_leaves_existing_process_without_link(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        await _insert_process(connection)

    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        link = await connection.scalar(
            sa.text(
                'SELECT collection_template_id FROM process_instances '
                "WHERE code = 'VAL-LEGACY'"
            )
        )
    assert link is None


@pytest.mark.asyncio
async def test_downgrade_removes_tables_link_and_permission(
    migration_database,
):
    await run_migration(REVISION)

    # Production bootstrap composes the new permission onto Admin and BraCVAM.
    # The downgrade must remove those FK rows before deleting the permission.
    async with AsyncSession(migration_database) as session:
        profiles = await sync_canonical_profiles(session)
        permissions = await sync_canonical_permissions(session)
        await sync_profile_permissions(session, profiles, permissions)
        await session.commit()

    async with migration_database.connect() as connection:
        compositions = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions '
                'WHERE permission_id = :permission_id'
            ),
            {'permission_id': PERMISSION_ID},
        )
    assert compositions > 0

    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        tables = await _tables(connection)
        process_columns = await _columns(connection, 'process_instances')
        permission = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM permissions '
                "WHERE code = 'collection_templates.manage'"
            )
        )
        compositions = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions '
                'WHERE permission_id = :permission_id'
            ),
            {'permission_id': PERMISSION_ID},
        )
    assert not TABLES & tables
    assert 'collection_template_id' not in process_columns
    assert permission == 0
    assert compositions == 0
