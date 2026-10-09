"""Template de coleta escolhido na criação do processo (Spec 041, US4)."""

from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from pivma import app
from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import ProcessInstance
from tests.factories.collection_template_factory import (
    ORIGIN,
    authenticate,
    catalog_manager,
    collection_template,
    linked_process,
)


@pytest_asyncio.fixture
async def templates(session):
    await bootstrap_all_templates(session)


@pytest_asyncio.fixture
async def manager(session, templates):
    return await catalog_manager(session)


@pytest_asyncio.fixture
async def template(session, manager):
    return await collection_template(session, manager)


def _create(client, **fields):
    return client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Validação de citotoxicidade',
            **fields,
        }, headers=ORIGIN,
    )


async def _process_count(session):
    return await session.scalar(
        select(func.count()).select_from(ProcessInstance)
    )


def _created_event(client, process_id):
    events = client.get(f'/processes/{process_id}/timeline').json()['data']
    return next(e for e in events if e['event_type'] == 'PROCESS_CREATED')


@pytest.mark.asyncio
async def test_manager_creates_process_with_template(
    client, manager, template
):
    """US4, cenário 1."""
    authenticate(client, manager)

    response = _create(client, collection_template_id=str(template.id))

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()['collection_template_id'] == str(template.id)


@pytest.mark.asyncio
async def test_read_and_list_show_the_link(client, manager, template):
    """FR-023."""
    authenticate(client, manager)
    linked = _create(client, collection_template_id=str(template.id)).json()
    unlinked = _create(client).json()

    read_linked = client.get(f'/processes/{linked["id"]}').json()
    read_unlinked = client.get(f'/processes/{unlinked["id"]}').json()
    listed = {
        item['id']: item['collection_template_id']
        for item in client.get('/processes').json()['data']
    }

    assert read_linked['collection_template_id'] == str(template.id)
    assert read_unlinked['collection_template_id'] is None
    assert listed == {
        linked['id']: str(template.id),
        unlinked['id']: None,
    }


@pytest.mark.asyncio
async def test_user_creates_process_without_template(client, user, templates):
    """US4, cenário 2."""
    authenticate(client, user)

    response = _create(client)

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()['collection_template_id'] is None


@pytest.mark.asyncio
async def test_unknown_template_is_not_found(client, session, manager):
    """US4, cenário 3."""
    authenticate(client, manager)
    before = await _process_count(session)

    response = _create(client, collection_template_id=str(uuid4()))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'
    assert await _process_count(session) == before


@pytest.mark.asyncio
async def test_user_without_permission_cannot_link_template(
    client, session, user, template
):
    """US4, cenário 4."""
    authenticate(client, user)
    before = await _process_count(session)

    response = _create(client, collection_template_id=str(template.id))

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'
    assert await _process_count(session) == before


@pytest.mark.asyncio
async def test_permission_is_checked_before_template_existence(
    client, user, templates
):
    """Research R10: o 403 não revela quais templates existem."""
    authenticate(client, user)

    response = _create(client, collection_template_id=str(uuid4()))

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'


@pytest.mark.asyncio
async def test_process_created_event_carries_the_link(
    client, manager, template
):
    """FR-024."""
    authenticate(client, manager)
    linked = _create(client, collection_template_id=str(template.id)).json()
    unlinked = _create(client).json()

    linked_event = _created_event(client, linked['id'])
    unlinked_event = _created_event(client, unlinked['id'])

    assert linked_event['context_data']['collection_template_id'] == str(
        template.id
    )
    assert 'collection_template_id' not in unlinked_event['context_data']


@pytest.mark.asyncio
async def test_locked_template_is_still_accepted_on_new_process(
    client, session, manager, template
):
    """US3, cenário 6."""
    await linked_process(session, template.id, complete_definition=True)
    authenticate(client, manager)

    response = _create(client, collection_template_id=str(template.id))

    assert response.status_code == HTTPStatus.CREATED, response.text


def test_only_process_creation_accepts_the_link():
    """US4, cenário 5; FR-025: nenhuma rota de processo altera o vínculo."""
    spec = app.openapi()
    schemas = spec['components']['schemas']
    accepting = set()
    for path, operations in spec['paths'].items():
        if not path.startswith('/processes'):
            continue
        for method, operation in operations.items():
            content = operation.get('requestBody', {}).get('content', {})
            for media in content.values():
                ref = media['schema'].get('$ref', '')
                properties = schemas.get(ref.rsplit('/', 1)[-1], {}).get(
                    'properties', {}
                )
                if 'collection_template_id' in properties:
                    accepting.add((method, path))

    assert accepting == {('post', '/processes')}
