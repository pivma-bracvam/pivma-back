"""Spec 018 - correção de visibilidade em `GET /tasks`.

Antes desta spec, `GET /tasks` não tinha filtro de visibilidade algum:
qualquer usuário autenticado listava as tarefas de todos os processos da
plataforma (research.md, achado A1).
"""

from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import grant_cargo
from tests.factories.user_factory import UserFactory


async def _create_process(client, *, template_key='pre_validated_method'):
    resp = client.post(
        '/processes',
        json={'template_key': template_key, 'title': 'Processo de teste'},
    )
    assert resp.status_code == HTTPStatus.CREATED
    return resp.json()['id']


@pytest.mark.asyncio
async def test_outsider_does_not_see_other_users_tasks(client, session):
    await bootstrap_all_templates(session)
    owner = UserFactory()
    outsider = UserFactory()
    session.add_all([owner, outsider])
    await session.commit()

    authenticate(client, owner)
    process_id = await _create_process(client)

    authenticate(client, outsider)
    resp = client.get('/tasks', params={'process_id': process_id})
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []

    resp_all = client.get('/tasks')
    assert resp_all.status_code == HTTPStatus.OK
    assert process_id not in {t['process_id'] for t in resp_all.json()}


@pytest.mark.asyncio
async def test_task_detail_denied_to_outsider(client, session):
    await bootstrap_all_templates(session)
    owner = UserFactory()
    outsider = UserFactory()
    session.add_all([owner, outsider])
    await session.commit()

    authenticate(client, owner)
    await _create_process(client)
    own_task_id = client.get('/tasks').json()[0]['id']

    authenticate(client, outsider)
    resp = client.get(f'/tasks/{own_task_id}')
    assert resp.status_code == HTTPStatus.NOT_FOUND


# Spec 030 — tarefas filtradas pela concessão de ver da atividade.


async def _submitted_process_with_sponsor(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    sponsor = UserFactory()
    session.add_all([proponent, sponsor])
    await session.commit()
    authenticate(client, proponent)
    process_id = await _create_process(client)
    await grant_cargo(
        session, process_id=UUID(process_id), user=sponsor, role_key='sponsor'
    )
    return proponent, sponsor, process_id


def _submit(client, process_id):
    resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Título'}},
    )
    assert resp.status_code == HTTPStatus.OK, resp.text


@pytest.mark.asyncio
async def test_task_list_hides_tasks_of_activities_without_view(
    client, session
):
    _, sponsor, process_id = await _submitted_process_with_sponsor(
        client, session
    )

    authenticate(client, sponsor)
    resp = client.get('/tasks', params={'process_id': process_id})

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []


@pytest.mark.asyncio
async def test_task_list_shows_triage_task_to_bracvam_not_to_proponent(
    client, session, bracvam_user
):
    proponent, _, process_id = await _submitted_process_with_sponsor(
        client, session
    )
    _submit(client, process_id)

    roles = {
        t['assigned_role']
        for t in client.get('/tasks', params={'process_id': process_id}).json()
    }
    assert roles == {'proponent'}

    authenticate(client, bracvam_user)
    roles = {
        t['assigned_role']
        for t in client.get('/tasks', params={'process_id': process_id}).json()
    }
    assert roles == {'proponent', 'bracvam'}


@pytest.mark.asyncio
async def test_task_detail_404_without_view(client, session, bracvam_user):
    proponent, _, process_id = await _submitted_process_with_sponsor(
        client, session
    )
    _submit(client, process_id)
    authenticate(client, bracvam_user)
    triage_task_id = next(
        t['id']
        for t in client.get('/tasks', params={'process_id': process_id}).json()
        if t['assigned_role'] == 'bracvam'
    )

    authenticate(client, proponent)
    resp = client.get(f'/tasks/{triage_task_id}')

    assert resp.status_code == HTTPStatus.NOT_FOUND
