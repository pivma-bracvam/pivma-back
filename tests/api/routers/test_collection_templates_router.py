"""Catálogo de templates de coleta: criação, consulta, listagem, arquivo,
alteração e exclusão de coluna (Spec 041, US1, US2 e US5)."""

import io
from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio
from openpyxl import load_workbook

from pivma.core.collection_template_service import (
    CSV_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
)
from pivma.core.database.models import CollectionTemplateColumn
from tests.factories.collection_template_factory import (
    ORIGIN,
    add_column,
    authenticate,
    catalog_manager,
    create_template,
    read_template,
)

FIXED = ['codigo_amostra', 'experimento', 'replica']


@pytest_asyncio.fixture
async def manager(session, client):
    user = await catalog_manager(session)
    authenticate(client, user)
    return user


def _fields(response):
    return {
        (field['field'], field['code'])
        for field in response.json()['detail']['fields']
    }


def _new_template(client, **overrides) -> dict:
    response = create_template(client, **overrides)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _new_column(client, template_id, **overrides) -> dict:
    response = add_column(client, template_id, **overrides)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _download(client, template_id, file_format):
    return client.get(
        f'/collection-templates/{template_id}/file',
        params={'format': file_format},
    )


# --- US1: criar, consultar e listar ---


@pytest.mark.asyncio
async def test_create_template_starts_unlocked_and_without_columns(
    client, manager
):
    """US1, cenário 1."""
    response = create_template(client, name='Ensaio de citotoxicidade')

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body['name'] == 'Ensaio de citotoxicidade'
    assert body['columns'] == []
    assert body['locked'] is False
    assert body['created_by'] == str(manager.id)


@pytest.mark.asyncio
async def test_column_without_position_goes_after_the_last_active(
    client, session, manager
):
    """US1, cenário 2; FR-008."""
    template = _new_template(client)

    first = _new_column(client, template['id'])
    second = _new_column(client, template['id'])

    assert first['position'] == 1
    assert second['position'] == 2  # noqa: PLR2004
    # A resposta não expõe a autoria da coluna; a trilha fica no banco
    # (constituição II).
    row = await session.get(CollectionTemplateColumn, first['id'])
    assert row.created_by == manager.id


@pytest.mark.asyncio
async def test_column_fills_a_gap_between_positions(client, manager):
    """US1, cenário 7."""
    template = _new_template(client)
    _new_column(client, template['id'], key='primeira', position=1)
    _new_column(client, template['id'], key='quinta', position=5)

    response = add_column(client, template['id'], key='segunda', position=2)

    assert response.status_code == HTTPStatus.CREATED, response.text
    columns = read_template(client, template['id'])['columns']
    assert [(c['key'], c['position']) for c in columns] == [
        ('primeira', 1),
        ('segunda', 2),
        ('quinta', 5),
    ]


@pytest.mark.asyncio
async def test_read_template_returns_minimums_and_full_columns(
    client, manager
):
    """US1, cenário 3."""
    template = _new_template(
        client,
        name='Ensaio',
        description='Leitura',
        min_experiments=3,
        min_replicates=2,
    )
    column = _new_column(
        client,
        template['id'],
        key='turbidez',
        label='Turbidez',
        type='select',
        required=True,
        options=['baixa', 'alta'],
    )

    body = read_template(client, template['id'])

    assert body['name'] == 'Ensaio'
    assert body['description'] == 'Leitura'
    assert body['min_experiments'] == 3  # noqa: PLR2004
    assert body['min_replicates'] == 2  # noqa: PLR2004
    assert body['locked'] is False
    assert body['columns'] == [
        {
            'id': column['id'],
            'key': 'turbidez',
            'label': 'Turbidez',
            'type': 'select',
            'required': True,
            'options': ['baixa', 'alta'],
            'position': 1,
        }
    ]


@pytest.mark.asyncio
async def test_read_unknown_template_is_not_found(client, manager):
    response = client.get(f'/collection-templates/{uuid4()}')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_add_column_to_unknown_template_is_not_found(client, manager):
    response = add_column(client, uuid4())

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_list_uses_standard_envelope_without_columns(client, manager):
    """US1, cenário 8."""
    template = _new_template(client)
    _new_column(client, template['id'])

    response = client.get('/collection-templates')

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert set(body) == {'data', 'pagination', 'filters_applied', 'sort'}
    assert body['filters_applied'] == {}
    assert body['sort'] == {'by': 'name', 'order': 'asc'}
    [item] = body['data']
    assert item['id'] == template['id']
    assert item['locked'] is False
    assert 'columns' not in item


@pytest.mark.asyncio
async def test_list_orders_by_name_ignoring_case_then_id(client, manager):
    beta = _new_template(client, name='beta')
    upper = _new_template(client, name='Alfa')
    lower = _new_template(client, name='alfa')

    body = client.get('/collection-templates').json()

    alfa_ids = sorted([upper['id'], lower['id']])
    assert [item['id'] for item in body['data']] == [*alfa_ids, beta['id']]


@pytest.mark.asyncio
async def test_list_paginates(client, manager):
    for name in ('A', 'B', 'C'):
        _new_template(client, name=name)

    body = client.get(
        '/collection-templates', params={'per_page': 2, 'page': 2}
    ).json()

    assert [item['name'] for item in body['data']] == ['C']
    assert body['pagination'] == {
        'page': 2,
        'per_page': 2,
        'total_items': 3,
        'total_pages': 2,
        'has_next': False,
        'has_prev': True,
    }


@pytest.mark.asyncio
async def test_create_template_rejects_unknown_field(client, manager):
    response = create_template(client, color='azul')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'
    assert _fields(response) == {('color', 'extra_forbidden')}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('name', 'code'),
    [('', 'string_too_short'), ('a' * 256, 'string_too_long')],
)
async def test_create_template_rejects_name_length(
    client, manager, name, code
):
    response = create_template(client, name=name)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('name', code)}
    assert client.get('/collection-templates').json()['data'] == []


@pytest.mark.asyncio
async def test_create_template_accepts_name_with_255_characters(
    client, manager
):
    response = create_template(client, name='a' * 255)

    assert response.status_code == HTTPStatus.CREATED, response.text


# --- US1: arquivo-modelo ---


@pytest.mark.asyncio
async def test_csv_file_has_only_technical_keys_in_header(client, manager):
    """US1, cenário 4; FR-016; Edge Cases (rótulo com `;`, aspas e acento)."""
    template = _new_template(client)
    _new_column(
        client, template['id'], key='viabilidade', label='Viab.; "(%)" ção'
    )
    _new_column(client, template['id'], key='lote')

    response = _download(client, template['id'], 'csv')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.headers['content-type'] == CSV_MEDIA_TYPE
    assert response.headers['content-disposition'] == (
        f'attachment; filename="template-coleta-{template["id"]}.csv"'
    )
    assert response.content.decode('utf-8-sig').splitlines() == [
        'codigo_amostra;experimento;replica;viabilidade;lote'
    ]


@pytest.mark.asyncio
async def test_xlsx_file_has_header_in_first_row(client, manager):
    """US1, cenário 5."""
    template = _new_template(client)
    _new_column(client, template['id'], key='viabilidade')

    response = _download(client, template['id'], 'xlsx')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.headers['content-type'] == XLSX_MEDIA_TYPE
    assert response.headers['content-disposition'] == (
        f'attachment; filename="template-coleta-{template["id"]}.xlsx"'
    )
    sheet = load_workbook(io.BytesIO(response.content))['resultados']
    assert [cell.value for cell in sheet[1]] == [*FIXED, 'viabilidade']


@pytest.mark.asyncio
async def test_file_of_template_without_columns_has_fixed_columns(
    client, manager
):
    """US1, cenário 6."""
    template = _new_template(client)

    response = _download(client, template['id'], 'csv')

    assert response.content.decode('utf-8-sig').splitlines() == [
        ';'.join(FIXED)
    ]


@pytest.mark.asyncio
async def test_file_rejects_unknown_format(client, manager):
    template = _new_template(client)

    response = _download(client, template['id'], 'pdf')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('format', 'literal_error')}


@pytest.mark.asyncio
async def test_file_requires_format(client, manager):
    template = _new_template(client)

    response = client.get(f'/collection-templates/{template["id"]}/file')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {('format', 'missing')}


@pytest.mark.asyncio
async def test_file_of_unknown_template_is_not_found(client, manager):
    response = _download(client, uuid4(), 'csv')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


# --- US2: alterações aceitas ---


@pytest.mark.asyncio
async def test_patch_column_changes_label_and_required(
    client, session, manager
):
    """FR-009."""
    template = _new_template(client)
    column = _new_column(client, template['id'], required=False)

    response = client.patch(
        f'/collection-templates/{template["id"]}/columns/{column["id"]}',
        headers=ORIGIN,
        json={'label': 'Novo rótulo', 'required': True},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['label'] == 'Novo rótulo'
    assert response.json()['required'] is True
    # A resposta não expõe a autoria da coluna (constituição II).
    row = await session.get(CollectionTemplateColumn, column['id'])
    assert row.updated_by == manager.id


@pytest.mark.asyncio
async def test_patch_template_changes_name_and_clears_description(
    client, manager
):
    """FR-002."""
    template = _new_template(client, description='Antiga')

    renamed = client.patch(
        f'/collection-templates/{template["id"]}',
        headers=ORIGIN,
        json={'name': 'Novo nome', 'description': 'Nova'},
    )
    cleared = client.patch(
        f'/collection-templates/{template["id"]}',
        headers=ORIGIN,
        json={'description': None},
    )

    assert renamed.status_code == HTTPStatus.OK, renamed.text
    assert renamed.json()['name'] == 'Novo nome'
    assert renamed.json()['description'] == 'Nova'
    assert renamed.json()['updated_by'] == str(manager.id)
    assert cleared.status_code == HTTPStatus.OK, cleared.text
    assert cleared.json()['description'] is None
    assert cleared.json()['name'] == 'Novo nome'


# --- US5: exclusão de coluna ---


def _delete_column(client, template_id, column_id):
    return client.delete(
        f'/collection-templates/{template_id}/columns/{column_id}',
        headers=ORIGIN,
    )


@pytest.mark.asyncio
async def test_deleted_column_leaves_read_and_file(client, manager):
    """US5, cenário 1."""
    template = _new_template(client)
    kept = _new_column(client, template['id'], key='viabilidade')
    removed = _new_column(client, template['id'], key='lote_reagente')

    response = _delete_column(client, template['id'], removed['id'])

    assert response.status_code == HTTPStatus.NO_CONTENT
    columns = read_template(client, template['id'])['columns']
    assert [c['id'] for c in columns] == [kept['id']]
    file = _download(client, template['id'], 'csv')
    assert file.content.decode('utf-8-sig').splitlines() == [
        ';'.join([*FIXED, 'viabilidade'])
    ]


@pytest.mark.asyncio
async def test_deleted_column_keeps_deletion_audit(client, session, manager):
    """FR-010."""
    template = _new_template(client)
    column = _new_column(client, template['id'])

    _delete_column(client, template['id'], column['id'])

    # A API não mostra colunas excluídas; a trilha fica no banco.
    row = await session.get(
        CollectionTemplateColumn,
        column['id'],
        execution_options={'skip_soft_delete_filter': True},
    )
    assert row.deleted_at is not None
    assert row.deleted_by == manager.id


@pytest.mark.asyncio
async def test_deleted_column_frees_key_and_position(client, manager):
    """US5, cenário 2."""
    template = _new_template(client)
    column = _new_column(client, template['id'], key='lote', position=3)
    _delete_column(client, template['id'], column['id'])

    response = add_column(client, template['id'], key='lote', position=3)

    assert response.status_code == HTTPStatus.CREATED, response.text


@pytest.mark.asyncio
async def test_delete_or_patch_unavailable_column_is_not_found(
    client, manager
):
    """US5, cenário 3."""
    template = _new_template(client)
    other = _new_template(client, name='Outro')
    column = _new_column(client, template['id'])
    foreign = _new_column(client, other['id'])
    _delete_column(client, template['id'], column['id'])

    responses = [
        _delete_column(client, template['id'], column['id']),
        _delete_column(client, template['id'], uuid4()),
        _delete_column(client, template['id'], foreign['id']),
        client.patch(
            f'/collection-templates/{template["id"]}/columns/{column["id"]}',
            headers=ORIGIN,
            json={'label': 'Novo'},
        ),
    ]

    assert [r.status_code for r in responses] == [HTTPStatus.NOT_FOUND] * 4
    assert {r.json()['detail']['code'] for r in responses} == {'not_found'}
    assert read_template(client, other['id'])['columns'] == [foreign]
