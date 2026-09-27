"""A atividade de amostras abre pela Fase 2 (Spec 031, US6).

A triagem é aprovada e os cargos são designados pelo motor
(`participant_service.create_assignment`), o mesmo caminho da designação
direta e do aceite de convite; a Fase 2 fecha cada atribuição na primeira
designação.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.participant_service import create_assignment
from pivma.core.process_engine import (
    _advance_dependent_activities,  # noqa: PLC2701
    _complete_activity_run,  # noqa: PLC2701
    instantiate_process,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import lab_user, new_laboratory
from tests.factories.user_factory import UserFactory

TEMPLATE_KEYS = (
    'pre_validated_method',
    'scope_extension',
    'me_too_validation',
    'validated_method_dossier',
    'proof_of_concept',
)


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _status(session, process_id, key):
    return await session.scalar(
        select(ActivityInstance.status)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == key,
        )
        .execution_options(populate_existing=True)
    )


async def _approved_process(session, template_key):
    """Processo do template com a triagem aprovada (Fase 2 liberada)."""
    await bootstrap_all_templates(session)
    version = await session.scalar(
        select(ProcessTemplateVersion)
        .join(
            ProcessTemplate,
            ProcessTemplate.id == ProcessTemplateVersion.template_id,
        )
        .where(ProcessTemplate.key == template_key)
        .order_by(ProcessTemplateVersion.version_number.desc())
        .limit(1)
    )
    creator = await _user(session)
    process = await instantiate_process(
        session, version, f'Processo {template_key}', creator.id
    )
    for key in ('proposal_submission', 'triage_evaluation'):
        act = await session.scalar(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process.id,
                ActivityInstance.key == key,
            )
        )
        run = await session.scalar(
            select(ActivityRun).where(
                ActivityRun.activity_instance_id == act.id
            )
        )
        if run is None:
            run = ActivityRun(
                activity_instance_id=act.id,
                run_number=1,
                status='IN_PROGRESS',
                execution_reason='Teste',
            )
            session.add(run)
            await session.flush()
        await _complete_activity_run(session, run, act, creator.id)
    await _advance_dependent_activities(session, process, act, creator.id)
    await session.commit()
    return process, creator


async def _assign(session, process, creator, role_key, laboratory=None):
    user = (
        await lab_user(session, laboratory)
        if laboratory
        else await _user(session)
    )
    await create_assignment(
        session,
        await session.get(ProcessInstance, process.id),
        user_id=user.id,
        role_key=role_key,
        laboratory_id=laboratory.id if laboratory else None,
        actor_id=creator.id,
        source='test',
    )
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_phase_2_opens_for_template_01_after_triage_approval(session):
    process, _ = await _approved_process(session, 'pre_validated_method')

    assert await _status(session, process.id, 'assign_sponsor') == (
        'IN_PROGRESS'
    )
    assert await _status(session, process.id, 'assign_group_manager') == (
        'IN_PROGRESS'
    )
    assert await _status(session, process.id, 'sample_definition') == (
        'BLOCKED'
    )


@pytest.mark.asyncio
async def test_sample_activity_stays_blocked_with_only_sample_group_assigned(
    session,
):
    process, creator = await _approved_process(session, 'pre_validated_method')
    await _assign(session, process, creator, 'group_manager')

    await _assign(session, process, creator, 'sample_selection_group')

    assert (
        await _status(session, process.id, 'assign_sample_selection_group')
        == 'COMPLETED'
    )
    assert await _status(session, process.id, 'sample_definition') == (
        'BLOCKED'
    )


@pytest.mark.asyncio
async def test_sample_activity_stays_blocked_with_only_participating_lab_assigned(  # noqa: E501
    session,
):
    process, creator = await _approved_process(session, 'pre_validated_method')
    await _assign(session, process, creator, 'group_manager')

    await _assign(
        session,
        process,
        creator,
        'participating_laboratory',
        await new_laboratory(session),
    )

    assert await _status(session, process.id, 'sample_definition') == (
        'BLOCKED'
    )


@pytest.mark.asyncio
async def test_sample_activity_opens_after_both_assignments(session, client):
    process, creator = await _approved_process(session, 'pre_validated_method')
    await _assign(session, process, creator, 'group_manager')
    selector = await _assign(
        session, process, creator, 'sample_selection_group'
    )
    await _assign(
        session,
        process,
        creator,
        'participating_laboratory',
        await new_laboratory(session),
    )

    assert await _status(session, process.id, 'sample_definition') == (
        'IN_PROGRESS'
    )
    authenticate(client, selector)
    response = client.get('/tasks', params={'process_id': str(process.id)})
    assert response.status_code == HTTPStatus.OK, response.text
    tasks = [
        t
        for t in response.json()['data']
        if t['title'] == 'Definição e Preparação das Amostras'
    ]
    assert len(tasks) == 1
    assert tasks[0]['assigned_role'] == 'sample_selection_group'


@pytest.mark.asyncio
@pytest.mark.parametrize('template_key', TEMPLATE_KEYS)
async def test_sample_activity_opens_for_every_template(session, template_key):
    process, creator = await _approved_process(session, template_key)
    await _assign(session, process, creator, 'group_manager')
    await _assign(session, process, creator, 'sample_selection_group')
    await _assign(
        session,
        process,
        creator,
        'participating_laboratory',
        await new_laboratory(session),
    )

    assert await _status(session, process.id, 'sample_definition') == (
        'IN_PROGRESS'
    )
