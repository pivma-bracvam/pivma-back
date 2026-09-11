# ruff: noqa: F401, F811, I001
"""Migração da Spec 018 — normalização de `tasks.assigned_role`.

Puramente de dados (nenhum `ALTER TABLE`): confirma que os três valores
legados convergem para o vocabulário compartilhado com `Assignment.role_key`
no upgrade, e que o downgrade reverte simetricamente.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa

from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = 'a29d47c1e935'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _seed_chain(connection):
    """Insere a cadeia mínima de FKs e 3 `tasks` com cargo legado."""
    template_id = uuid4()
    version_id = uuid4()
    process_id = uuid4()
    phase_id = uuid4()
    activity_id = uuid4()
    run_id = uuid4()

    await connection.execute(
        sa.text(
            'INSERT INTO process_templates '
            '(id, key, name, description, is_active, created_at) '
            "VALUES (:id, 'legacy_template', 'Legacy', NULL, true, now())"
        ),
        {'id': template_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_template_versions '
            '(id, template_id, version_number, definition_payload, '
            'is_published, created_at) '
            "VALUES (:id, :template_id, 1, '{}'::jsonb, true, now())"
        ),
        {'id': version_id, 'template_id': template_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_instances '
            '(id, template_version_id, code, title, status, started_at, '
            'closed_at, closure_reason, created_at) '
            "VALUES (:id, :version_id, 'VAL-2026-legacy', 'Legacy', "
            "'TRIAGE', NULL, NULL, NULL, now())"
        ),
        {'id': process_id, 'version_id': version_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO phases '
            '(id, process_instance_id, key, name, order_index, status, '
            'created_at) '
            "VALUES (:id, :process_id, 'phase_1', 'Fase 1', 1, "
            "'IN_PROGRESS', now())"
        ),
        {'id': phase_id, 'process_id': process_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO activity_instances '
            '(id, process_instance_id, phase_id, key, name, order_index, '
            'status, blocked_reason, activity_type, created_at) '
            "VALUES (:id, :process_id, :phase_id, 'act_1', 'Atividade 1', "
            "1, 'IN_PROGRESS', NULL, 'form', now())"
        ),
        {'id': activity_id, 'process_id': process_id, 'phase_id': phase_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO activity_runs '
            '(id, activity_instance_id, run_number, status, started_at, '
            'completed_at, execution_reason, created_at) '
            "VALUES (:id, :activity_id, 1, 'IN_PROGRESS', now(), NULL, "
            'NULL, now())'
        ),
        {'id': run_id, 'activity_id': activity_id},
    )

    task_ids = {role: uuid4() for role in ('PROPONENT', 'TRIAGE_LEAD', 'BRACVAM_ADMIN')}
    for role, task_id in task_ids.items():
        await connection.execute(
            sa.text(
                'INSERT INTO tasks '
                '(id, activity_run_id, title, assigned_role, '
                'assigned_user_id, status, due_date, completed_at, '
                'created_at) '
                "VALUES (:id, :run_id, 'Tarefa', :role, NULL, 'READY', "
                'NULL, NULL, now())'
            ),
            {'id': task_id, 'run_id': run_id, 'role': role},
        )
    return task_ids


async def _assigned_roles(connection, task_ids):
    result = {}
    for role, task_id in task_ids.items():
        value = await connection.scalar(
            sa.text('SELECT assigned_role FROM tasks WHERE id = :id'),
            {'id': task_id},
        )
        result[role] = value
    return result


@pytest.mark.asyncio
async def test_upgrade_normalizes_legacy_assigned_role_values(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        task_ids = await _seed_chain(connection)

    await run_migration('head')
    async with migration_database.connect() as connection:
        normalized = await _assigned_roles(connection, task_ids)

    assert normalized == {
        'PROPONENT': 'proponent',
        'TRIAGE_LEAD': 'bracvam',
        'BRACVAM_ADMIN': 'bracvam',
    }


@pytest.mark.asyncio
async def test_downgrade_reverts_normalized_values(migration_database):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        task_ids = await _seed_chain(connection)
    await run_migration('head')

    await run_downgrade(PREVIOUS)
    async with migration_database.connect() as connection:
        reverted = await _assigned_roles(connection, task_ids)

    # `TRIAGE_LEAD` e `BRACVAM_ADMIN` convergiram para 'bracvam' no upgrade;
    # o downgrade não consegue distinguir a origem, então ambos voltam como
    # 'TRIAGE_LEAD' (research.md D5 / migração, downgrade documentado).
    assert reverted == {
        'PROPONENT': 'PROPONENT',
        'TRIAGE_LEAD': 'TRIAGE_LEAD',
        'BRACVAM_ADMIN': 'TRIAGE_LEAD',
    }
