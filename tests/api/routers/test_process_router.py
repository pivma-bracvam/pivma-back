# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_list_and_get_process_templates(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. List templates
    resp = client.get('/processes/templates')
    assert resp.status_code == HTTPStatus.OK
    templates = resp.json()
    assert len(templates) >= 1
    assert any(t['key'] == 'full_validation' for t in templates)

    # 2. Get detail
    resp_detail = client.get('/processes/templates/full_validation')
    assert resp_detail.status_code == HTTPStatus.OK
    detail = resp_detail.json()
    assert detail['key'] == 'full_validation'
    assert 'phases' in detail['definition']


@pytest.mark.asyncio
async def test_create_and_list_process_instances(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # Create process
    create_payload = {
        'template_key': 'full_validation',
        'title': 'Validação de Teste In Vitro',
    }
    resp = client.post('/processes', json=create_payload)
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['code'].startswith('VAL-')
    assert data['status'] == 'SUBMISSION'
    process_id = data['id']

    # Get single process
    resp_get = client.get(f'/processes/{process_id}')
    assert resp_get.status_code == HTTPStatus.OK
    assert resp_get.json()['id'] == process_id

    # List processes
    resp_list = client.get('/processes')
    assert resp_list.status_code == HTTPStatus.OK
    list_data = resp_list.json()
    assert list_data['total'] >= 1
    assert any(p['id'] == process_id for p in list_data['items'])
