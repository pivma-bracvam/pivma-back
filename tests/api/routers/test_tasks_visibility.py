"""Spec 018 - correção de visibilidade em `GET /tasks`.

Antes desta spec, `GET /tasks` não tinha filtro de visibilidade algum:
qualquer usuário autenticado listava as tarefas de todos os processos da
plataforma (research.md, achado A1).
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
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
