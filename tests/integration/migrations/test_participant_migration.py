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

PERMISSION_ID = '00000000-0000-0000-0000-000000000107'
ADMIN_PROFILE_ID = '00000000-0000-0000-0000-000000000009'


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _seed_process_graph(connection):
    user_id = uuid4()
    template_id = uuid4()
    version_id = uuid4()
    process_id = uuid4()
    phase_id = uuid4()
    activity_id = uuid4()
    run_id = uuid4()
    task_id = uuid4()
    proponent_assignment_id = uuid4()
    manager_assignment_id = uuid4()
    event_id = uuid4()
    code = str(process_id).replace('-', '')[:32]

    await connection.execute(
        sa.text(
            'INSERT INTO users (id, username, email, password_hash) '
            'VALUES (:id, :username, :email, :password_hash)'
        ),
        {
            'id': user_id,
            'username': f'legacy-{user_id.hex[:12]}',
            'email': f'{user_id.hex[:12]}@example.com',
            'password_hash': 'legacy-hash',
        },
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_templates (id, key, name, is_active) '
            "VALUES (:id, :key, 'Template legado', true)"
        ),
        {'id': template_id, 'key': f'legacy-{template_id.hex[:12]}'},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_template_versions '
            '(id, template_id, version_number, definition_payload, '
            'is_published) '
            "VALUES (:id, :template_id, 1, '{}'::jsonb, true)"
        ),
        {'id': version_id, 'template_id': template_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_instances '
            '(id, template_version_id, code, title, status) '
            "VALUES (:id, :version_id, :code, 'Processo legado', "
            "'SUBMISSION')"
        ),
        {'id': process_id, 'version_id': version_id, 'code': code},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO phases '
            '(id, process_instance_id, key, name, order_index) '
            "VALUES (:id, :process_id, 'phase', 'Fase legada', 1)"
        ),
        {'id': phase_id, 'process_id': process_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO activity_instances '
            '(id, process_instance_id, phase_id, key, name, order_index) '
            "VALUES (:id, :process_id, :phase_id, 'activity', "
            "'Atividade legada', 1)"
        ),
        {'id': activity_id, 'process_id': process_id, 'phase_id': phase_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO activity_runs '
            '(id, activity_instance_id, run_number) '
            'VALUES (:id, :activity_id, 1)'
        ),
        {'id': run_id, 'activity_id': activity_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO tasks '
            '(id, activity_run_id, title, assigned_role) '
            "VALUES (:id, :run_id, 'Tarefa legada', 'PROPONENT')"
        ),
        {'id': task_id, 'run_id': run_id},
    )
    await connection.execute(
        sa.text(
            'INSERT INTO assignments '
            '(id, process_instance_id, user_id, role_key, assigned_by) '
            "VALUES (:id, :process_id, :user_id, 'PROPONENT', :user_id)"
        ),
        {
            'id': proponent_assignment_id,
            'process_id': process_id,
            'user_id': user_id,
        },
    )
    await connection.execute(
        sa.text(
            'INSERT INTO assignments '
            '(id, process_instance_id, user_id, role_key, assigned_by) '
            "VALUES (:id, :process_id, :user_id, 'group_manager', :user_id)"
        ),
        {
            'id': manager_assignment_id,
            'process_id': process_id,
            'user_id': user_id,
        },
    )
    await connection.execute(
        sa.text(
            'INSERT INTO audit_events '
            '(id, process_instance_id, event_type, user_id) '
            "VALUES (:id, :process_id, 'PROCESS_CREATED', :user_id)"
        ),
        {'id': event_id, 'process_id': process_id, 'user_id': user_id},
    )

    return {
        'user_id': user_id,
        'process_id': process_id,
        'task_id': task_id,
        'proponent_assignment_id': proponent_assignment_id,
        'manager_assignment_id': manager_assignment_id,
        'event_id': event_id,
    }


@pytest.mark.asyncio
async def test_upgrade_adds_optional_laboratory_column(migration_database):
    await run_migration('5e31a8c7d204')
    await run_migration('head')
    async with migration_database.connect() as connection:
        columns = {
            row.column_name: row.is_nullable
            for row in (
                await connection.execute(
                    sa.text(
                        'SELECT column_name, is_nullable '
                        'FROM information_schema.columns '
                        "WHERE table_name = 'assignments'"
                    )
                )
            ).mappings()
        }
    assert columns.get('laboratory_id') == 'YES'


@pytest.mark.asyncio
async def test_upgrade_adds_laboratory_fk_without_cascade(migration_database):
    await run_migration('5e31a8c7d204')
    await run_migration('head')
    async with migration_database.connect() as connection:
        row = (
            await connection.execute(
                sa.text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conname = 'fk_assignments_laboratory_id'"
                )
            )
        ).mappings().one()
    assert row['confdeltype'] == 'a'


@pytest.mark.asyncio
async def test_upgrade_creates_conflict_declarations_table(
    migration_database,
):
    await run_migration('5e31a8c7d204')
    await run_migration('head')
    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    'SELECT tablename FROM pg_tables '
                    "WHERE schemaname = 'public'"
                )
            )
        )
    assert 'conflict_interest_declarations' in tables


@pytest.mark.asyncio
async def test_upgrade_creates_latest_declaration_index(migration_database):
    await run_migration('5e31a8c7d204')
    await run_migration('head')
    async with migration_database.connect() as connection:
        indexes = set(
            await connection.scalars(
                sa.text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'conflict_interest_declarations'"
                )
            )
        )
    assert 'ix_conflict_declarations_assignment_time' in indexes


@pytest.mark.asyncio
async def test_upgrade_normalizes_legacy_proponent_role(migration_database):
    await run_migration('5e31a8c7d204')
    async with migration_database.begin() as connection:
        seed = await _seed_process_graph(connection)

    await run_migration('head')
    async with migration_database.connect() as connection:
        role = await connection.scalar(
            sa.text('SELECT role_key FROM assignments WHERE id = :id'),
            {'id': seed['proponent_assignment_id']},
        )
    assert role == 'proponent'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'record_type', ['process', 'task', 'assignment', 'event']
)
async def test_upgrade_preserves_preexisting_records(
    migration_database, record_type
):
    await run_migration('5e31a8c7d204')
    async with migration_database.begin() as connection:
        seed = await _seed_process_graph(connection)

    await run_migration('head')
    async with migration_database.connect() as connection:
        if record_type == 'process':
            count = await connection.scalar(
                sa.text(
                    'SELECT count(*) FROM process_instances WHERE id = :id'
                ),
                {'id': seed['process_id']},
            )
        elif record_type == 'task':
            count = await connection.scalar(
                sa.text('SELECT count(*) FROM tasks WHERE id = :id'),
                {'id': seed['task_id']},
            )
        elif record_type == 'assignment':
            count = await connection.scalar(
                sa.text('SELECT count(*) FROM assignments WHERE id = :id'),
                {'id': seed['manager_assignment_id']},
            )
        else:
            count = await connection.scalar(
                sa.text('SELECT count(*) FROM audit_events WHERE id = :id'),
                {'id': seed['event_id']},
            )
    assert count == 1


@pytest.mark.asyncio
async def test_upgrade_does_not_create_implicit_backfill(migration_database):
    await run_migration('5e31a8c7d204')
    async with migration_database.begin() as connection:
        await _seed_process_graph(connection)

    await run_migration('head')
    async with migration_database.connect() as connection:
        declarations = await connection.scalar(
            sa.text('SELECT count(*) FROM conflict_interest_declarations')
        )
        laboratories = await connection.scalar(
            sa.text('SELECT count(*) FROM laboratories')
        )
    assert (declarations, laboratories) == (0, 0)


@pytest.mark.asyncio
async def test_upgrade_grants_new_permission_only_to_administrator(
    migration_database,
):
    await run_migration('5e31a8c7d204')
    await run_migration('head')
    async with migration_database.connect() as connection:
        permission_code = await connection.scalar(
            sa.text('SELECT code FROM permissions WHERE id = :id'),
            {'id': PERMISSION_ID},
        )
        non_admin_compositions = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions app '
                'JOIN access_profiles ap ON ap.id = app.profile_id '
                'WHERE app.permission_id = :permission_id '
                "AND ap.system_key <> 'administrator'"
            ),
            {'permission_id': PERMISSION_ID},
        )
        admin_composition = await connection.scalar(
            sa.text(
                'SELECT count(*) FROM access_profile_permissions '
                'WHERE permission_id = :permission_id '
                'AND profile_id = :profile_id'
            ),
            {'permission_id': PERMISSION_ID, 'profile_id': ADMIN_PROFILE_ID},
        )
    assert permission_code == 'process.participants.manage'
    assert non_admin_compositions == 0
    assert admin_composition == 1


@pytest.mark.asyncio
async def test_downgrade_removes_only_feature_structures_and_seed(
    migration_database,
):
    await run_migration('5e31a8c7d204')
    await run_migration('head')
    await run_downgrade('5e31a8c7d204')

    async with migration_database.connect() as connection:
        tables = set(
            await connection.scalars(
                sa.text(
                    'SELECT tablename FROM pg_tables '
                    "WHERE schemaname = 'public'"
                )
            )
        )
        columns = set(
            await connection.scalars(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'assignments'"
                )
            )
        )
        permission_count = await connection.scalar(
            sa.text('SELECT count(*) FROM permissions WHERE id = :id'),
            {'id': PERMISSION_ID},
        )
    assert 'conflict_interest_declarations' not in tables
    assert 'laboratory_id' not in columns
    assert permission_count == 0
    assert 'process_instances' in tables
    assert 'users' in tables


@pytest.mark.asyncio
async def test_downgrade_restores_local_proponent_designations(
    migration_database,
):
    await run_migration('5e31a8c7d204')
    async with migration_database.begin() as connection:
        seed = await _seed_process_graph(connection)

    await run_migration('head')
    await run_downgrade('5e31a8c7d204')

    async with migration_database.connect() as connection:
        role = await connection.scalar(
            sa.text('SELECT role_key FROM assignments WHERE id = :id'),
            {'id': seed['proponent_assignment_id']},
        )
    assert role == 'PROPONENT'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'record_type', ['process', 'task', 'assignment', 'event']
)
async def test_downgrade_preserves_preexisting_records(
    migration_database, record_type
):
    await run_migration('5e31a8c7d204')
    async with migration_database.begin() as connection:
        seed = await _seed_process_graph(connection)

    await run_migration('head')
    await run_downgrade('5e31a8c7d204')

    async with migration_database.connect() as connection:
        if record_type == 'process':
            count = await connection.scalar(
                sa.text(
                    'SELECT count(*) FROM process_instances WHERE id = :id'
                ),
                {'id': seed['process_id']},
            )
        elif record_type == 'task':
            count = await connection.scalar(
                sa.text('SELECT count(*) FROM tasks WHERE id = :id'),
                {'id': seed['task_id']},
            )
        elif record_type == 'assignment':
            count = await connection.scalar(
                sa.text('SELECT count(*) FROM assignments WHERE id = :id'),
                {'id': seed['manager_assignment_id']},
            )
        else:
            count = await connection.scalar(
                sa.text('SELECT count(*) FROM audit_events WHERE id = :id'),
                {'id': seed['event_id']},
            )
    assert count == 1
