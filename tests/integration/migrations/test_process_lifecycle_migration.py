# ruff: noqa: F401, F811, I001
"""Migração da Spec 030 (1ª revisão): ciclo de vida e concessões."""

from uuid import uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.process_engine import execute_triage_decision
from tests.integration.migrations.test_secure_user_registration import (
    migration_database as secure_migration_database,
    run_downgrade,
    run_migration,
)

PREVIOUS = '1b1772b71863'
REVISION = '3c9a1f2d7e40'
RETURN_REVIEW_REVISION = '7e21b4c0a9d3'
ALL_OLD_STATUSES = (
    'SUBMISSION',
    'AI_PRE_EVALUATION',
    'TRIAGE',
    'PLANNING',
    'CLOSED',
    'CANCELLED',
    'ARCHIVED',
)


@pytest_asyncio.fixture
async def migration_database(secure_migration_database):
    return secure_migration_database


async def _insert(connection, table, **values):
    columns = ', '.join(values)
    params = ', '.join(f':{name}' for name in values)
    await connection.execute(
        sa.text(f'INSERT INTO {table} ({columns}) VALUES ({params})'),
        values,
    )


async def _seed_template(connection):
    template_id, version_id = uuid4(), uuid4()
    await _insert(
        connection,
        'process_templates',
        id=template_id,
        key=f'legacy_{template_id.hex[:8]}',
        name='Legacy',
        is_active=True,
    )
    await connection.execute(
        sa.text(
            'INSERT INTO process_template_versions '
            '(id, template_id, version_number, definition_payload, '
            'is_published) VALUES (:id, :template_id, 1, :payload, true)'
        ),
        {
            'id': version_id,
            'template_id': template_id,
            'payload': (
                '{"phases": [{"key": "phase_2", "activities": '
                '[{"key": "assign_statistician", '
                '"assigned_role": "group_manager"}]}]}'
            ),
        },
    )
    return version_id


async def _seed_process(  # noqa: PLR0913
    connection,
    version_id,
    *,
    status,
    triage_status='BLOCKED',
    phase_status='IN_PROGRESS',
    ai_pending=False,
):
    """Processo com fase 1, submissão, triagem e uma atividade legada."""
    process_id, phase_id = uuid4(), uuid4()
    await _insert(
        connection,
        'process_instances',
        id=process_id,
        template_version_id=version_id,
        code=f'VAL-{process_id.hex[:12]}',
        title='Legacy',
        status=status,
    )
    await _insert(
        connection,
        'phases',
        id=phase_id,
        process_instance_id=process_id,
        key='phase_1_submission_triage',
        name='Fase 1',
        order_index=1,
        status=phase_status,
    )
    activities = {}
    for key, act_status in (
        ('proposal_submission', 'COMPLETED'),
        ('triage_evaluation', triage_status),
        ('assign_statistician', 'BLOCKED'),
        ('legacy_unknown', 'IN_PROGRESS'),
    ):
        activity_id = uuid4()
        activities[key] = activity_id
        await _insert(
            connection,
            'activity_instances',
            id=activity_id,
            process_instance_id=process_id,
            phase_id=phase_id,
            key=key,
            name=key,
            order_index=1,
            status=act_status,
            activity_type='form',
        )
    submission_run = uuid4()
    await _insert(
        connection,
        'activity_runs',
        id=submission_run,
        activity_instance_id=activities['proposal_submission'],
        run_number=1,
        status='COMPLETED',
    )
    if triage_status == 'IN_PROGRESS':
        triage_run = uuid4()
        await _insert(
            connection,
            'activity_runs',
            id=triage_run,
            activity_instance_id=activities['triage_evaluation'],
            run_number=1,
            status='IN_PROGRESS',
        )
        await _insert(
            connection,
            'tasks',
            id=uuid4(),
            activity_run_id=triage_run,
            title='Triagem',
            assigned_role='bracvam',
            status='READY',
        )
    legacy_run = uuid4()
    await _insert(
        connection,
        'activity_runs',
        id=legacy_run,
        activity_instance_id=activities['legacy_unknown'],
        run_number=1,
        status='IN_PROGRESS',
    )
    await _insert(
        connection,
        'tasks',
        id=uuid4(),
        activity_run_id=legacy_run,
        title='Legada',
        assigned_role='sponsor',
        status='READY',
    )
    if ai_pending:
        form_template_id, form_instance_id = uuid4(), uuid4()
        await _insert(
            connection,
            'form_templates',
            id=form_template_id,
            key=f'form_{form_template_id.hex[:8]}',
            name='Form',
            version=1,
        )
        await _insert(
            connection,
            'form_instances',
            id=form_instance_id,
            form_template_id=form_template_id,
            activity_run_id=submission_run,
            is_submitted=True,
        )
        await _insert(
            connection,
            'evaluation_runs',
            id=uuid4(),
            process_instance_id=process_id,
            activity_run_id=submission_run,
            form_instance_id=form_instance_id,
            correlation_id=uuid4(),
            status='in_progress',
            real_cost=0,
        )
    return process_id, activities


async def _statuses(connection, process_ids):
    rows = await connection.execute(
        sa.text(
            'SELECT id, status FROM process_instances WHERE id = ANY(:ids)'
        ),
        {'ids': list(process_ids)},
    )
    return dict(rows.all())


async def _seed_all_statuses(migration_database):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        version_id = await _seed_template(connection)
        return {
            status: (
                await _seed_process(connection, version_id, status=status)
            )[0]
            for status in ALL_OLD_STATUSES
        }


@pytest.mark.asyncio
async def test_upgrade_maps_flow_statuses_to_open(migration_database):
    processes = await _seed_all_statuses(migration_database)

    await run_migration(REVISION)
    async with migration_database.connect() as connection:
        statuses = await _statuses(connection, processes.values())

    for old in ('SUBMISSION', 'AI_PRE_EVALUATION', 'TRIAGE', 'PLANNING'):
        assert statuses[processes[old]] == 'OPEN', old


@pytest.mark.asyncio
async def test_upgrade_preserves_terminal_statuses(migration_database):
    processes = await _seed_all_statuses(migration_database)

    await run_migration(REVISION)
    async with migration_database.connect() as connection:
        statuses = await _statuses(connection, processes.values())

    for terminal in ('CLOSED', 'CANCELLED', 'ARCHIVED'):
        assert statuses[processes[terminal]] == terminal


@pytest.mark.asyncio
async def test_upgrade_backfills_activity_access(migration_database):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        version_id = await _seed_template(connection)
        _, activities = await _seed_process(
            connection, version_id, status='TRIAGE'
        )

    await run_migration(REVISION)
    async with migration_database.connect() as connection:
        rows = await connection.execute(
            sa.text(
                'SELECT id, view_roles, edit_roles FROM activity_instances '
                'WHERE id = ANY(:ids)'
            ),
            {'ids': list(activities.values())},
        )
        grants = {row[0]: (row[1], row[2]) for row in rows}

    assert grants[activities['proposal_submission']] == (
        ['admin', 'bracvam', 'proponent'],
        ['proponent'],
    )
    assert grants[activities['triage_evaluation']] == (
        ['admin', 'bracvam'],
        ['bracvam'],
    )
    # Chave fora da matriz: cargo da definição do template.
    assert grants[activities['assign_statistician']] == (
        ['admin', 'bracvam', 'group_manager'],
        ['group_manager'],
    )
    # Chave desconhecida também no template: cargo da tarefa mais recente.
    assert grants[activities['legacy_unknown']] == (
        ['admin', 'bracvam', 'sponsor'],
        ['sponsor'],
    )


@pytest.mark.asyncio
async def test_upgrade_adds_status_check_constraint(migration_database):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        version_id = await _seed_template(connection)
    await run_migration(REVISION)

    with pytest.raises(IntegrityError, match='ck_process_instances_status'):
        async with migration_database.begin() as connection:
            await _insert(
                connection,
                'process_instances',
                id=uuid4(),
                template_version_id=version_id,
                code='VAL-CHECK',
                title='Inválido',
                status='TRIAGE',
            )


@pytest.mark.asyncio
async def test_downgrade_rebuilds_flow_status_from_activities(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        version_id = await _seed_template(connection)
        triage, _ = await _seed_process(
            connection,
            version_id,
            status='TRIAGE',
            triage_status='IN_PROGRESS',
        )
        ai, _ = await _seed_process(
            connection, version_id, status='AI_PRE_EVALUATION', ai_pending=True
        )
        planning, _ = await _seed_process(
            connection,
            version_id,
            status='PLANNING',
            triage_status='COMPLETED',
            phase_status='COMPLETED',
        )
        submission, _ = await _seed_process(
            connection, version_id, status='SUBMISSION'
        )
        closed, _ = await _seed_process(
            connection, version_id, status='CLOSED'
        )
    await run_migration(REVISION)

    await run_downgrade(PREVIOUS)
    async with migration_database.connect() as connection:
        statuses = await _statuses(
            connection, [triage, ai, planning, submission, closed]
        )
        columns = {
            row[0]
            for row in await connection.execute(
                sa.text(
                    'SELECT column_name FROM information_schema.columns '
                    "WHERE table_name = 'activity_instances'"
                )
            )
        }

    assert statuses == {
        triage: 'TRIAGE',
        ai: 'AI_PRE_EVALUATION',
        planning: 'PLANNING',
        submission: 'SUBMISSION',
        closed: 'CLOSED',
    }
    assert not {'view_roles', 'edit_roles'} & columns


@pytest.mark.asyncio
async def test_pending_triage_still_decidable_after_upgrade(
    migration_database,
):
    await run_migration(PREVIOUS)
    async with migration_database.begin() as connection:
        version_id = await _seed_template(connection)
        process_id, _ = await _seed_process(
            connection,
            version_id,
            status='TRIAGE',
            triage_status='IN_PROGRESS',
        )
        user_id = uuid4()
        await _insert(
            connection,
            'users',
            id=user_id,
            username='triador',
            email='triador@example.com',
            full_name='Triador',
            password_hash='x',
        )
        profile_id = uuid4()
        await _insert(
            connection,
            'access_profiles',
            id=profile_id,
            system_key='bracvam',
            name='BraCVAM',
            description='BraCVAM',
        )
        await _insert(
            connection,
            'user_access_profiles',
            id=uuid4(),
            user_id=user_id,
            profile_id=profile_id,
        )
    await run_migration(REVISION)

    async with AsyncSession(
        migration_database, expire_on_commit=False
    ) as session:
        decision, status, _ = await execute_triage_decision(
            session, process_id, 'APPROVED', 'Aprovado.', user_id
        )

    assert decision.outcome == 'APPROVED'
    assert status == 'OPEN'


async def _return_reviews(connection, process_ids):
    rows = await connection.execute(
        sa.text(
            'SELECT a.process_instance_id, a.status, a.activity_type, '
            'a.view_roles, a.edit_roles, '
            '(SELECT count(*) FROM activity_runs r '
            ' WHERE r.activity_instance_id = a.id) '
            'FROM activity_instances a '
            "WHERE a.key = 'submission_return_review' "
            'AND a.process_instance_id = ANY(:ids)'
        ),
        {'ids': list(process_ids)},
    )
    return {row[0]: tuple(row[1:]) for row in rows}


@pytest.mark.asyncio
async def test_second_revision_adds_blocked_return_review(migration_database):
    """Cada processo existente ganha a revisão do retorno parada (T128)."""
    processes = await _seed_all_statuses(migration_database)

    await run_migration(RETURN_REVIEW_REVISION)
    async with migration_database.connect() as connection:
        reviews = await _return_reviews(connection, processes.values())

    assert set(reviews) == set(processes.values())
    for review in reviews.values():
        assert review == (
            'BLOCKED',
            'return_review',
            ['admin', 'bracvam', 'proponent'],
            ['proponent'],
            0,
        )

    await run_downgrade(REVISION)
    async with migration_database.connect() as connection:
        assert await _return_reviews(connection, processes.values()) == {}
