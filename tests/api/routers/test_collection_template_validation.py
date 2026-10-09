"""Recusas de coluna e de template inválidos (Spec 041, US2).

Toda recusa confere também que as colunas do template não mudaram.
"""

from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio

from pivma.schemas import MAX_INTEGER
from tests.factories.collection_template_factory import (
    ORIGIN,
    add_column,
    authenticate,
    catalog_manager,
    create_template,
    read_template,
)


@pytest_asyncio.fixture
async def template(session, client):
    """Template com a coluna `viabilidade` na posição 1."""
    authenticate(client, await catalog_manager(session))
    created = create_template(client).json()
    response = add_column(client, created['id'], key='viabilidade')
    assert response.status_code == HTTPStatus.CREATED, response.text
    return read_template(client, created['id'])


def _code(response):
    return response.json()['detail']['code']


def _fields(response):
    return {
        (field['field'], field['code'])
        for field in response.json()['detail']['fields']
    }


def _patch_column(client, template, column_id, body):
    return client.patch(
        f'/collection-templates/{template["id"]}/columns/{column_id}',
        headers=ORIGIN,
        json=body,
    )


def _patch_template(client, template_id, body):
    return client.patch(
        f'/collection-templates/{template_id}', headers=ORIGIN, json=body
    )


def _unchanged(client, template):
    return read_template(client, template['id']) == template


# --- Criação de coluna ---


@pytest.mark.asyncio
async def test_duplicate_key_is_rejected(client, template):
    """US2, cenário 1."""
    response = add_column(client, template['id'], key='viabilidade')

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'duplicate_key'
    assert _unchanged(client, template)


@pytest.mark.asyncio
@pytest.mark.parametrize('key', ['codigo_amostra', 'experimento', 'replica'])
async def test_reserved_key_is_rejected(client, template, key):
    """US2, cenário 2."""
    response = add_column(client, template['id'], key=key)

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'reserved_key'
    assert _unchanged(client, template)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'key',
    [
        'Viabilidade',
        '1abc',
        '_abc',
        'com espaco',
        'com-hifen',
        'acao_ç',
        '',
        'a' * 65,
    ],
)
async def test_key_out_of_format_is_rejected(client, template, key):
    """US2, cenário 3."""
    response = add_column(client, template['id'], key=key)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'validation_error'
    assert _fields(response) == {('key', 'string_pattern_mismatch')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_key_with_64_characters_is_accepted(client, template):
    """Limite de FR-006."""
    response = add_column(client, template['id'], key='a' * 64)

    assert response.status_code == HTTPStatus.CREATED, response.text


@pytest.mark.asyncio
async def test_unknown_type_is_rejected(client, template):
    """US2, cenário 4."""
    response = add_column(client, template['id'], type='boolean')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('type', 'literal_error')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
@pytest.mark.parametrize('options', [None, []])
async def test_select_without_options_is_rejected(client, template, options):
    """US2, cenário 5."""
    response = add_column(
        client, template['id'], type='select', options=options
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'invalid_options'
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_options_on_non_select_type_are_rejected(client, template):
    """US2, cenário 6."""
    response = add_column(client, template['id'], type='text', options=['a'])

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'invalid_options'
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_repeated_option_is_rejected(client, template):
    response = add_column(
        client, template['id'], type='select', options=['alta', 'alta']
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'invalid_options'
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_empty_option_is_rejected(client, template):
    response = add_column(client, template['id'], type='select', options=[''])

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('options.0', 'string_too_short')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_taken_position_is_rejected(client, template):
    """US2, cenário 7."""
    response = add_column(client, template['id'], position=1)

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'position_taken'
    assert _unchanged(client, template)


@pytest.mark.asyncio
@pytest.mark.parametrize('position', [0, -1])
async def test_position_below_one_is_rejected(client, template, position):
    """US2, cenário 8."""
    response = add_column(client, template['id'], position=position)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('position', 'greater_than_equal')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_position_above_integer_limit_is_rejected(client, template):
    """Sem o limite, o banco estoura e a API responde 500."""
    response = add_column(client, template['id'], position=MAX_INTEGER + 1)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('position', 'less_than_equal')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_no_automatic_position_after_the_integer_limit(client, template):
    last = add_column(client, template['id'], position=MAX_INTEGER)
    assert last.status_code == HTTPStatus.CREATED, last.text
    before = read_template(client, template['id'])

    response = add_column(client, template['id'])

    assert response.status_code == HTTPStatus.CONFLICT
    assert _code(response) == 'position_limit_reached'
    assert _unchanged(client, before)


@pytest.mark.asyncio
async def test_empty_label_is_rejected(client, template):
    response = add_column(client, template['id'], label='')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('label', 'string_too_short')}
    assert _unchanged(client, template)


# --- Alteração de coluna ---


@pytest_asyncio.fixture
async def select_column(client, template):
    response = add_column(
        client, template['id'], type='select', options=['alta', 'baixa']
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


@pytest.mark.asyncio
async def test_patch_select_to_text_keeping_options_is_rejected(
    client, template, select_column
):
    """US2, cenário 9: a regra vale para o estado resultante."""
    before = read_template(client, template['id'])

    response = _patch_column(
        client, template, select_column['id'], {'type': 'text'}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'invalid_options'
    assert _unchanged(client, before)


@pytest.mark.asyncio
async def test_patch_select_to_text_clearing_options_is_accepted(
    client, template, select_column
):
    """US2, cenário 9."""
    response = _patch_column(
        client,
        template,
        select_column['id'],
        {'type': 'text', 'options': None},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['type'] == 'text'
    assert response.json()['options'] is None


@pytest.mark.asyncio
async def test_patch_column_key_of_another_column_is_rejected(
    client, template, select_column
):
    before = read_template(client, template['id'])

    taken = _patch_column(
        client, template, select_column['id'], {'key': 'viabilidade'}
    )

    assert taken.status_code == HTTPStatus.CONFLICT
    assert _code(taken) == 'duplicate_key'
    assert _unchanged(client, before)
    own = _patch_column(
        client, template, select_column['id'], {'key': select_column['key']}
    )
    assert own.status_code == HTTPStatus.OK, own.text


@pytest.mark.asyncio
async def test_patch_column_position_of_another_column_is_rejected(
    client, template, select_column
):
    before = read_template(client, template['id'])

    taken = _patch_column(
        client, template, select_column['id'], {'position': 1}
    )

    assert taken.status_code == HTTPStatus.CONFLICT
    assert _code(taken) == 'position_taken'
    assert _unchanged(client, before)
    own = _patch_column(client, template, select_column['id'], {'position': 2})
    assert own.status_code == HTTPStatus.OK, own.text


@pytest.mark.asyncio
async def test_patch_column_with_null_key_is_rejected(client, template):
    column_id = template['columns'][0]['id']

    response = _patch_column(client, template, column_id, {'key': None})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'validation_error'
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_patch_unknown_or_foreign_column_is_not_found(client, template):
    other = create_template(client, name='Outro').json()
    column_id = template['columns'][0]['id']

    unknown = _patch_column(client, template, uuid4(), {'label': 'Novo'})
    foreign = _patch_column(client, other, column_id, {'label': 'Novo'})

    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert _code(unknown) == 'not_found'
    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert _code(foreign) == 'not_found'
    assert _unchanged(client, template)


# --- Template ---


@pytest.mark.asyncio
async def test_minimum_below_one_is_rejected(client, template):
    """US2, cenário 10."""
    created = create_template(client, min_experiments=0)
    patched = _patch_template(client, template['id'], {'min_replicates': 0})

    assert created.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(created) == {('min_experiments', 'greater_than_equal')}
    assert patched.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(patched) == {('min_replicates', 'greater_than_equal')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_minimum_above_integer_limit_is_rejected(client, template):
    created = create_template(client, min_experiments=MAX_INTEGER + 1)
    patched = _patch_template(
        client, template['id'], {'min_replicates': MAX_INTEGER + 1}
    )

    assert created.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(created) == {('min_experiments', 'less_than_equal')}
    assert patched.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(patched) == {('min_replicates', 'less_than_equal')}
    assert _unchanged(client, template)


@pytest.mark.asyncio
@pytest.mark.usefixtures('template')
async def test_minimum_at_integer_limit_is_accepted(client):
    response = create_template(
        client, min_experiments=MAX_INTEGER, min_replicates=MAX_INTEGER
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()['min_experiments'] == MAX_INTEGER


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['name', 'min_experiments'])
async def test_patch_template_with_null_field_is_rejected(
    client, template, field
):
    response = _patch_template(client, template['id'], {field: None})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _code(response) == 'validation_error'
    assert _unchanged(client, template)


@pytest.mark.asyncio
async def test_patch_unknown_template_is_not_found(client, template):
    response = _patch_template(client, uuid4(), {'name': 'Novo'})

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert _code(response) == 'not_found'
