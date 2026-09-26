"""Fases e atividades guardam a posição no fluxo, com paralelismo
(Spec 030, US5).

Nenhum endpoint expõe fases: o processo expõe só o ciclo de vida. O estado
de fase e atividade é lido no banco; pela API, o usuário acompanha as
tarefas das atividades que pode ver.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    sync_template_from_dict,
)
from pivma.core.database.models import ActivityInstance, Phase
from pivma.core.process_engine import instantiate_process
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import grant_cargo
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
PARALLEL_TEMPLATE = {
    'process_template': {
        'key': 'parallel_probe',
        'name': 'Atividades em paralelo',
        'version': 1,
    },
    'phases': [
        {
            'key': 'phase_execution',
            'name': 'Execução',
            'order_index': 1,
            'activities': [
                {
                    'key': 'statistics_plan',
                    'name': 'Plano estatístico',
                    'order_index': 1,
                    'assigned_role': 'statistician',
                    'activity_type': 'task',
                    'dependencies': [],
                },
                {
                    'key': 'peer_review',
                    'name': 'Revisão por pares',
                    'order_index': 2,
                    'assigned_role': 'peer_reviewer',
                    'activity_type': 'task',
                    'dependencies': [],
                },
            ],
        }
    ],
    'forms': [],
}


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _parallel_process(session):
    _, version, _ = await sync_template_from_dict(session, PARALLEL_TEMPLATE)
    creator = await _user(session)
    process = await instantiate_process(
        session, version, 'Processo paralelo', creator.id
    )
    return process.id


def _task_titles(client, process_id):
    response = client.get('/tasks', params={'process_id': str(process_id)})
    assert response.status_code == HTTPStatus.OK, response.text
    return {task['title'] for task in response.json()}


@pytest.mark.asyncio
async def test_phase1_completed_after_triage_approval(
    client, session, bracvam_user
):
    await bootstrap_all_templates(session)
    proponent = await _user(session)
    authenticate(client, proponent)
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Processo 1'},
    ).json()['id']
    client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Método'}},
    )
    authenticate(client, bracvam_user)
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers=ORIGIN,
    )
    assert decision.status_code == HTTPStatus.OK, decision.text

    phase_1 = await session.scalar(
        select(Phase)
        .where(Phase.process_instance_id == pid, Phase.order_index == 1)
        .execution_options(populate_existing=True)
    )
    assert phase_1.status == 'COMPLETED'
    assert client.get(f'/processes/{pid}').json()['status'] == 'OPEN'


@pytest.mark.asyncio
async def test_parallel_activities_both_in_progress_for_user_with_both_grants(
    client, session
):
    process_id = await _parallel_process(session)
    both = await _user(session)
    for role_key in ('statistician', 'peer_reviewer'):
        await grant_cargo(
            session, process_id=process_id, user=both, role_key=role_key
        )
    authenticate(client, both)

    assert _task_titles(client, process_id) == {
        'Preencher Plano estatístico',
        'Preencher Revisão por pares',
    }
    statuses = {
        act.key: act.status
        for act in await session.scalars(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process_id
            )
        )
    }
    assert statuses == {
        'statistics_plan': 'IN_PROGRESS',
        'peer_review': 'IN_PROGRESS',
    }


@pytest.mark.asyncio
async def test_parallel_activities_filtered_by_grant(client, session):
    process_id = await _parallel_process(session)
    statistician = await _user(session)
    await grant_cargo(
        session,
        process_id=process_id,
        user=statistician,
        role_key='statistician',
    )
    authenticate(client, statistician)

    assert _task_titles(client, process_id) == {'Preencher Plano estatístico'}
