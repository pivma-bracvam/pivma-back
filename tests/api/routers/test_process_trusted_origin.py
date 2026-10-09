"""Proteção de origem nas escritas de processos e de formulários de
atividade (constituição III).

Com o cookie de sessão, toda escrita exige `Origin` confiável. O token
Bearer não é anexado pelo navegador e dispensa a checagem.
"""

from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import ProcessInstance
from tests.factories.collection_template_factory import authenticate

UNTRUSTED = {'Origin': 'https://evil.test'}
ROUTES = [
    ('put', '/processes/templates/pre_validated_method/forms/submission'),
    ('post', '/processes'),
    ('delete', '/processes/{id}'),
    ('patch', '/processes/{id}/archive'),
    ('put', '/processes/{id}'),
    ('patch', '/processes/{id}'),
    ('put', '/processes/{id}/activities/submission/form'),
    ('post', '/processes/{id}/activities/submission/form'),
]
CREATE_BODY = {
    'template_key': 'pre_validated_method',
    'title': 'Validação de citotoxicidade',
}


@pytest_asyncio.fixture
async def templates(session):
    await bootstrap_all_templates(session)


async def _process_count(session):
    return await session.scalar(
        select(func.count()).select_from(ProcessInstance)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('headers', [{}, UNTRUSTED], ids=['sem', 'estranha'])
@pytest.mark.parametrize(('method', 'path'), ROUTES)
async def test_cookie_write_requires_trusted_origin(
    client, user, method, path, headers
):
    authenticate(client, user)

    response = client.request(
        method, path.format(id=uuid4()), headers=headers, json={}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'invalid_origin'


@pytest.mark.asyncio
@pytest.mark.usefixtures('templates')
async def test_refused_origin_creates_no_process(client, session, user):
    authenticate(client, user)

    response = client.post('/processes', headers=UNTRUSTED, json=CREATE_BODY)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert await _process_count(session) == 0


@pytest.mark.asyncio
@pytest.mark.usefixtures('templates')
async def test_bearer_creates_process_without_origin(
    client, session, auth_token
):
    response = client.post(
        '/processes',
        headers={'Authorization': f'Bearer {auth_token}'},
        json=CREATE_BODY,
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert await _process_count(session) == 1
