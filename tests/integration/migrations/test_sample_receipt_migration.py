# ruff: noqa: F401, F811, I001
"""Migração da Spec 040: recebimento, inconformidades e cadastro ampliado."""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '6fe19f1c95e9'
REVISION = '9d4e2b7a1c30'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _insert_substance(connection):
    """Template, processo e uma substância, em SQL puro."""
    ids = {name: uuid4() for name in ('tpl', 'ver', 'proc', 'substance')}
    await connection.execute(
        sa.text(
            'INSERT INTO process_templates (id, key, name, is_active) '
            "VALUES (:id, 'legacy', 'Legacy', true)"
        ),
        {'id': ids['tpl']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_template_versions '
            '(id, template_id, version_number, definition_payload, '
            'is_published) '
            "VALUES (:id, :tpl, 1, '{}'::jsonb, true)"
        ),
        {'id': ids['ver'], 'tpl': ids['tpl']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_instances '
            '(id, template_version_id, code, title, status) '
            "VALUES (:id, :ver, 'VAL-LEGACY', 'Legacy', 'OPEN')"
        ),
        {'id': ids['proc'], 'ver': ids['ver']},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO study_substances '
            '(id, process_instance_id, chemical_name, cas_number, lot, '
            'safe_handling_instructions) '
            "VALUES (:id, :proc, 'Formaldeído', '50-00-0', 'L1', 'Luvas')"
        ),
        {'id': ids['substance'], 'proc': ids['proc']},
    )
    return ids


async def _columns(connection, table):
    return set(
        (
            await connection.execute(
                sa.text(
                    'SELECT column_name FROM information_schema.columns '
                    'WHERE table_name = :table'
                ),
                {'table': table},
            )
        )
        .scalars()
        .all()
    )


async def _tables(connection):
    return set(
        (
            await connection.execute(
                sa.text(
                    'SELECT tablename FROM pg_tables '
                    "WHERE schemaname = 'public'"
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_upgrade_keeps_existing_substance_with_empty_new_fields(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        ids = await _insert_substance(connection)

    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        row = (
            await connection.execute(
                sa.text(
                    'SELECT reference_classification, '
                    'storage_temperature_regime, reserve_vials_count, '
                    'ghs_hazard_pictograms '
                    'FROM study_substances WHERE id = :id'
                ),
                {'id': ids['substance']},
            )
        ).one()
        tables = await _tables(connection)
        code_columns = await _columns(connection, 'blind_sample_codes')
        index = await connection.scalar(
            sa.text(
                'SELECT indexdef FROM pg_indexes '
                "WHERE indexname = 'uq_sample_receipts_code_active'"
            )
        )
    assert row.reference_classification is None
    assert row.storage_temperature_regime is None
    assert row.reserve_vials_count == 0
    assert row.ghs_hazard_pictograms == []
    assert {'sample_receipts', 'sample_receipt_nonconformities'} <= tables
    assert 'replaces_code_id' in code_columns
    assert 'UNIQUE' in index
    assert 'deleted_at IS NULL' in index


@pytest.mark.asyncio
async def test_downgrade_removes_tables_and_columns(migration_database):
    await run_migration(REVISION)
    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        tables = await _tables(connection)
        substance_columns = await _columns(connection, 'study_substances')
        code_columns = await _columns(connection, 'blind_sample_codes')
    assert 'sample_receipts' not in tables
    assert 'sample_receipt_nonconformities' not in tables
    assert 'reference_classification' not in substance_columns
    assert 'reserve_vials_count' not in substance_columns
    assert 'replaces_code_id' not in code_columns
