# ruff: noqa: F401, F811, I001
"""Migração da Spec 042: pontos reprovados na decisão (research R5)."""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_sample_receipt_migration import (
    _columns,
)
from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'e8a4c2f61b37'
REVISION = 'a3d5f7b9c1e2'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _insert_triage_decision(connection):
    """Uma decisão de triagem anterior à migração, em SQL puro."""
    ids = {
        name: uuid4()
        for name in (
            'user',
            'template',
            'version',
            'process',
            'phase',
            'activity',
            'run',
            'decision',
        )
    }
    statements = (
        'INSERT INTO users (id, username, email, password_hash, full_name) '
        "VALUES (:user, :username, :email, 'legacy-hash', 'Legado')",
        'INSERT INTO process_templates (id, key, name, is_active) '
        "VALUES (:template, :username, 'Legado', true)",
        'INSERT INTO process_template_versions '
        '(id, template_id, version_number, definition_payload, is_published) '
        "VALUES (:version, :template, 1, '{}'::jsonb, true)",
        'INSERT INTO process_instances '
        '(id, template_version_id, code, title, status) '
        "VALUES (:process, :version, :username, 'Legado', 'OPEN')",
        'INSERT INTO phases (id, process_instance_id, key, name, order_index) '
        "VALUES (:phase, :process, 'phase', 'Fase', 1)",
        'INSERT INTO activity_instances '
        '(id, process_instance_id, phase_id, key, name, order_index, '
        'view_roles, edit_roles) '
        "VALUES (:activity, :process, :phase, 'triage_evaluation', "
        "'Triagem', 1, '{bracvam}', '{bracvam}')",
        'INSERT INTO activity_runs (id, activity_instance_id, run_number) '
        'VALUES (:run, :activity, 1)',
        'INSERT INTO decisions '
        '(id, process_instance_id, activity_run_id, decision_type, outcome, '
        'justification, decided_by) '
        "VALUES (:decision, :process, :run, 'TRIAGE_INITIAL_DECISION', "
        "'APPROVED', 'Aderente.', :user)",
    )
    params = {
        **ids,
        'username': f'legacy-{ids["user"].hex[:12]}',
        'email': f'{ids["user"].hex[:12]}@example.com',
    }
    for statement in statements:
        await connection.execute(sa.text(statement), params)
    return ids['decision']


@pytest.mark.asyncio
async def test_upgrade_adds_nullable_jsonb_column(migration_database):
    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        column = (
            await connection.execute(
                sa.text(
                    'SELECT data_type, is_nullable '
                    'FROM information_schema.columns '
                    "WHERE table_name = 'decisions' "
                    "AND column_name = 'rejected_points'"
                )
            )
        ).one()
    assert column.data_type == 'jsonb'
    assert column.is_nullable == 'YES'


@pytest.mark.asyncio
async def test_upgrade_leaves_existing_decision_without_points(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        decision_id = await _insert_triage_decision(connection)

    await run_migration(REVISION)

    async with migration_database.connect() as connection:
        points = await connection.scalar(
            sa.text('SELECT rejected_points FROM decisions WHERE id = :id'),
            {'id': decision_id},
        )
    assert points is None


@pytest.mark.asyncio
async def test_downgrade_drops_column_and_keeps_decisions(migration_database):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        decision_id = await _insert_triage_decision(connection)
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)

    async with migration_database.connect() as connection:
        columns = await _columns(connection, 'decisions')
        kept = await connection.scalar(
            sa.text('SELECT count(*) FROM decisions WHERE id = :id'),
            {'id': decision_id},
        )
    assert 'rejected_points' not in columns
    assert kept == 1
