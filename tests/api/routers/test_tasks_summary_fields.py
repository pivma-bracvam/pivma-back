"""`GET /tasks` identifica a atividade, a execução e a fase de cada tarefa.

Permite ao frontend montar um quadro por atividade (ex.: kanban da etapa 1
para o BraCVAM) sem uma chamada por tarefa: agrupa por `activity_key`, fica
com a maior `activity_run_number` de cada processo e filtra por
`phase_order`.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
FORM = '/processes/{pid}/activities/proposal_submission/form'


async def _proponent_process(client, session, *, template_key, title):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    response = client.post(
        '/processes', json={'template_key': template_key, 'title': title}
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return proponent, response.json()['id']


def _tasks(client, pid):
    response = client.get('/tasks', params={'process_id': pid})
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest.mark.asyncio
async def test_task_summary_identifies_activity_phase_and_process(
    client, session
):
    _, pid = await _proponent_process(
        client,
        session,
        template_key='pre_validated_method',
        title='Irritação ocular',
    )

    [task] = _tasks(client, pid)

    assert task['activity_key'] == 'proposal_submission'
    assert task['activity_run_number'] == 1
    assert task['phase_key'] == 'phase_1_submission_triage'
    assert task['phase_order'] == 1
    assert task['process_title'] == 'Irritação ocular'


@pytest.mark.asyncio
async def test_task_summary_distinguishes_current_run_after_revision(
    client, session, bracvam_user
):
    proponent, pid = await _proponent_process(
        client, session, template_key='pre_validated_method', title='Processo'
    )
    client.post(FORM.format(pid=pid), json={'values': {'method_title': 'V1'}})
    authenticate(client, bracvam_user)
    client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Ajustar.'},
        headers=ORIGIN,
    )
    authenticate(client, proponent)
    client.post(
        f'/processes/{pid}/return-review',
        json={'choice': 'REVISE'},
        headers=ORIGIN,
    )

    submission = sorted(
        (
            (t['activity_run_number'], t['status'])
            for t in _tasks(client, pid)
            if t['activity_key'] == 'proposal_submission'
        ),
    )

    # A execução 1 ficou concluída e a 2 é a vigente, mesmo com títulos
    # diferentes ("Preencher ..." e "Revisar e Ajustar ...").
    assert submission == [(1, 'COMPLETED'), (2, 'READY')]


@pytest.mark.asyncio
async def test_task_summary_separates_phases_for_bracvam(
    client, session, bracvam_user
):
    _, pid = await _proponent_process(
        client,
        session,
        template_key='validated_method_dossier',
        title='Dossiê',
    )
    client.post(
        FORM.format(pid=pid),
        json={'values': {'method_title': 'Método', 'terminology_notes': 'x'}},
    )
    authenticate(client, bracvam_user)
    client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers=ORIGIN,
    )

    by_phase = {}
    for task in _tasks(client, pid):
        by_phase.setdefault(task['phase_order'], set()).add(
            task['activity_key']
        )

    assert by_phase[1] == {'proposal_submission', 'triage_evaluation'}
    assert {'assign_sponsor', 'assign_group_manager'} <= by_phase[2]
