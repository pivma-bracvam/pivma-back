"""Spec 044, US1 - processos de tipo aposentado na listagem e no detalhe."""

from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import ProcessInstance
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.retired_template_factory import (
    RETIRED_KEY,
    RETIRED_NAME,
    deploy_without_retiring_type,
    seed_retiring_type,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}


@pytest_asyncio.fixture
async def retired_process(client, session):
    """Processo do proponente cujo tipo saiu de uso, com a versão do tipo."""
    await bootstrap_all_templates(session)
    version = await seed_retiring_type(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    response = client.post(
        '/processes',
        json={'template_key': RETIRED_KEY, 'title': 'Prova antiga'},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    await deploy_without_retiring_type(session)
    return response.json()['id'], version


def _expected_template(version):
    return {'key': RETIRED_KEY, 'name': RETIRED_NAME, 'version': version}


@pytest.mark.asyncio
async def test_list_returns_retired_template_ref(client, retired_process):
    process_id, version = retired_process

    response = client.get('/processes')

    assert response.status_code == HTTPStatus.OK, response.text
    items = {item['id']: item for item in response.json()['data']}
    assert items[process_id]['template'] == _expected_template(version)


@pytest.mark.asyncio
async def test_detail_returns_retired_template_ref(client, retired_process):
    process_id, version = retired_process

    response = client.get(f'/processes/{process_id}')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['template'] == _expected_template(version)


@pytest.mark.asyncio
async def test_other_proponent_cannot_see_retired_type_process(
    client, session, retired_process
):
    process_id, _ = retired_process
    other = UserFactory()
    session.add(other)
    await session.commit()
    authenticate(client, other)

    listed = client.get('/processes')
    detail = client.get(f'/processes/{process_id}')

    assert listed.status_code == HTTPStatus.OK, listed.text
    assert listed.json()['data'] == []
    assert detail.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_deleted_process_of_retired_type_stays_hidden(
    client, session, retired_process
):
    process_id, _ = retired_process
    process = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == UUID(process_id))
    )
    process.deleted_at = datetime.now(UTC)
    await session.commit()

    listed = client.get('/processes')
    detail = client.get(f'/processes/{process_id}')

    assert listed.status_code == HTTPStatus.OK, listed.text
    assert listed.json()['data'] == []
    assert detail.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_retired_type_stays_unavailable_for_new_submissions(
    client, retired_process
):
    templates = client.get('/processes/templates')
    created = client.post(
        '/processes',
        json={'template_key': RETIRED_KEY, 'title': 'Nova'},
        headers=ORIGIN,
    )

    assert RETIRED_KEY not in {t['key'] for t in templates.json()['data']}
    assert created.status_code == HTTPStatus.NOT_FOUND
