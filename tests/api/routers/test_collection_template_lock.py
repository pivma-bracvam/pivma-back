"""Travamento estrutural do template de coleta (Spec 041, US3 e US5).

O template trava quando um processo vinculado conclui a definição das
amostras (FR-017). Toda recusa confere também que nada mudou.
"""

from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio

from pivma.core.process_engine import delete_process
from tests.factories.collection_template_factory import (
    ORIGIN,
    add_column,
    authenticate,
    catalog_manager,
    collection_template,
    column_payload,
    linked_process,
    read_template,
)


@pytest_asyncio.fixture
async def manager(session, client):
    user = await catalog_manager(session)
    authenticate(client, user)
    return user


@pytest_asyncio.fixture
async def template(session, manager):
    """Template com uma coluna `viabilidade`."""
    return await collection_template(
        session, manager, columns=[column_payload(key='viabilidade')]
    )


@pytest_asyncio.fixture
async def locked(session, client, template):
    """O template depois da conclusão das amostras de um processo vinculado."""
    await linked_process(session, template.id, complete_definition=True)
    return read_template(client, template.id)


def _code(response):
    return response.json()['detail']['code']


def _column_url(template_id, column_id):
    return f'/collection-templates/{template_id}/columns/{column_id}'


def _patch_template(client, template_id, body):
    return client.patch(
        f'/collection-templates/{template_id}', headers=ORIGIN, json=body
    )


@pytest.mark.asyncio
async def test_linked_template_before_completion_accepts_changes(
    client, session, template
):
    """US3, cenário 1."""
    await linked_process(session, template.id, complete_definition=False)
    column_id = read_template(client, template.id)['columns'][0]['id']

    added = add_column(client, template.id)
    changed = client.patch(
        _column_url(template.id, column_id),
        headers=ORIGIN,
        json={'label': 'Viabilidade (%)'},
    )

    assert added.status_code == HTTPStatus.CREATED, added.text
    assert changed.status_code == HTTPStatus.OK, changed.text
    assert read_template(client, template.id)['locked'] is False


@pytest.mark.asyncio
async def test_locked_template_rejects_new_column(client, locked):
    """US3, cenário 2."""
    response = add_column(client, locked['id'])

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'template_locked'
    assert read_template(client, locked['id']) == locked


@pytest.mark.asyncio
async def test_locked_template_rejects_column_change(client, locked):
    """US3, cenário 2."""
    column_id = locked['columns'][0]['id']

    response = client.patch(
        _column_url(locked['id'], column_id),
        headers=ORIGIN,
        json={'label': 'Novo'},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'template_locked'
    assert read_template(client, locked['id']) == locked


@pytest.mark.asyncio
async def test_locked_template_rejects_minimum_change(client, locked):
    """US3, cenário 3."""
    response = _patch_template(
        client,
        locked['id'],
        {'min_experiments': locked['min_experiments'] + 1},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'template_locked'
    assert read_template(client, locked['id']) == locked


@pytest.mark.asyncio
async def test_locked_template_accepts_rename_with_same_minimums(
    client, locked
):
    """Research R3: o frontend reenvia os mínimos iguais."""
    response = _patch_template(
        client,
        locked['id'],
        {
            'name': 'Novo nome',
            'min_experiments': locked['min_experiments'],
            'min_replicates': locked['min_replicates'],
        },
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['name'] == 'Novo nome'


@pytest.mark.asyncio
async def test_locked_template_accepts_name_and_description(client, locked):
    """US3, cenário 4."""
    response = _patch_template(
        client, locked['id'], {'name': 'Novo nome', 'description': 'Nova'}
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['description'] == 'Nova'
    assert response.json()['locked'] is True


@pytest.mark.asyncio
async def test_locked_template_is_readable_listed_and_downloadable(
    client, locked
):
    """US3, cenário 5."""
    listed = client.get('/collection-templates').json()['data']
    download = client.get(
        f'/collection-templates/{locked["id"]}/file', params={'format': 'csv'}
    )

    assert locked['locked'] is True
    assert [item['locked'] for item in listed] == [True]
    assert download.status_code == HTTPStatus.OK, download.text


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['CLOSED', 'CANCELLED', 'ARCHIVED'])
async def test_template_stays_locked_after_process_ends(
    client, session, template, status
):
    """US3, cenário 7; FR-017."""
    ctx = await linked_process(session, template.id, complete_definition=True)
    # As transições de ciclo de vida têm testes próprios; o travamento
    # depende só do vínculo e da conclusão, então o status é gravado direto.
    ctx.process.status = status
    await session.commit()

    response = add_column(client, template.id)

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'template_locked'


@pytest.mark.asyncio
async def test_template_stays_locked_after_process_is_deleted(
    client, session, template
):
    """US3, cenário 7; research R2: a exclusão lógica não destrava."""
    ctx = await linked_process(session, template.id, complete_definition=True)
    await delete_process(session, ctx.process_id, ctx.creator.id)

    response = add_column(client, template.id)

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'template_locked'
    assert read_template(client, template.id)['locked'] is True


@pytest.mark.asyncio
async def test_list_marks_only_the_locked_template(
    client, session, manager, locked
):
    free = await collection_template(session, manager)

    listed = {
        item['id']: item['locked']
        for item in client.get('/collection-templates').json()['data']
    }

    assert listed == {locked['id']: True, str(free.id): False}


@pytest.mark.asyncio
async def test_linked_template_before_completion_accepts_column_deletion(
    client, session, template
):
    """US3, cenário 1 (US5)."""
    await linked_process(session, template.id, complete_definition=False)
    column_id = read_template(client, template.id)['columns'][0]['id']

    response = client.delete(
        _column_url(template.id, column_id), headers=ORIGIN
    )

    assert response.status_code == HTTPStatus.NO_CONTENT


@pytest.mark.asyncio
async def test_locked_template_rejects_column_deletion(client, locked):
    """US3, cenário 2 (US5)."""
    column_id = locked['columns'][0]['id']

    response = client.delete(
        _column_url(locked['id'], column_id), headers=ORIGIN
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'template_locked'
    assert read_template(client, locked['id']) == locked


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'body'), [('patch', {'label': 'Novo'}), ('delete', None)]
)
async def test_unknown_column_of_locked_template_is_not_found(
    client, locked, method, body
):
    """A coluna inexistente é 404, mesmo com o template travado."""
    url = _column_url(locked['id'], uuid4())

    response = client.request(method, url, headers=ORIGIN, json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert _code(response) == 'not_found'
    assert read_template(client, locked['id']) == locked
