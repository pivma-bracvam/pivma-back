"""Acesso ao catálogo de templates de coleta (Spec 041, US6; FR-026 a
FR-029). Toda recusa confere também que nada foi gravado."""

from http import HTTPStatus

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from pivma.core.database.models import (
    CollectionTemplate,
    CollectionTemplateColumn,
)
from tests.conftest import _make_rbac_user
from tests.factories.collection_template_factory import (
    ORIGIN,
    authenticate,
    catalog_manager,
    collection_template,
    column_payload,
    create_template,
    grant_catalog_permission,
    template_payload,
)


@pytest_asyncio.fixture
async def manager(session):
    return await catalog_manager(session)


@pytest_asyncio.fixture
async def template(session, manager):
    """Template com uma coluna, criado por quem gere o catálogo."""
    return await collection_template(
        session, manager, columns=[column_payload(label='Original')]
    )


@pytest_asyncio.fixture
async def column(session, template):
    return await session.scalar(
        select(CollectionTemplateColumn).where(
            CollectionTemplateColumn.collection_template_id == template.id
        )
    )


async def _count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


def _forbidden(response):
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'


@pytest.mark.asyncio
async def test_user_cannot_create_template(client, session, user):
    authenticate(client, user)

    _forbidden(create_template(client))
    assert await _count(session, CollectionTemplate) == 0


@pytest.mark.asyncio
async def test_user_cannot_update_template(client, session, user, template):
    authenticate(client, user)

    _forbidden(
        client.patch(
            f'/collection-templates/{template.id}',
            headers=ORIGIN,
            json={'name': 'Outro nome'},
        )
    )
    await session.refresh(template)
    assert template.name == template_payload()['name']


@pytest.mark.asyncio
async def test_user_cannot_add_column(client, session, user, template):
    authenticate(client, user)

    _forbidden(
        client.post(
            f'/collection-templates/{template.id}/columns',
            headers=ORIGIN,
            json=column_payload(),
        )
    )
    assert await _count(session, CollectionTemplateColumn) == 1


@pytest.mark.asyncio
async def test_user_cannot_update_column(
    client, session, user, template, column
):
    authenticate(client, user)

    _forbidden(
        client.patch(
            f'/collection-templates/{template.id}/columns/{column.id}',
            headers=ORIGIN,
            json={'label': 'Novo'},
        )
    )
    await session.refresh(column)
    assert column.label == 'Original'


@pytest.mark.asyncio
async def test_user_cannot_delete_column(
    client, session, user, template, column
):
    authenticate(client, user)

    _forbidden(
        client.delete(
            f'/collection-templates/{template.id}/columns/{column.id}',
            headers=ORIGIN,
        )
    )
    await session.refresh(column)
    assert column.deleted_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'path',
    [
        '/collection-templates',
        '/collection-templates/{id}',
        '/collection-templates/{id}/file?format=csv',
    ],
)
async def test_user_cannot_read_catalog(client, user, template, path):
    """US6, cenário 2."""
    authenticate(client, user)

    _forbidden(client.get(path.format(id=template.id)))


ROUTES = [
    ('get', '/collection-templates'),
    ('post', '/collection-templates'),
    ('get', '/collection-templates/{id}'),
    ('patch', '/collection-templates/{id}'),
    ('post', '/collection-templates/{id}/columns'),
    ('patch', '/collection-templates/{id}/columns/{column_id}'),
    ('delete', '/collection-templates/{id}/columns/{column_id}'),
    ('get', '/collection-templates/{id}/file?format=csv'),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(('method', 'path'), ROUTES)
async def test_route_requires_session(client, template, column, method, path):
    """US6, cenário 3."""
    url = path.format(id=template.id, column_id=column.id)

    response = client.request(method, url, headers=ORIGIN)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail']['code'] == 'not_authenticated'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'path', 'body'),
    [
        ('post', '/collection-templates', template_payload()),
        ('patch', '/collection-templates/{id}', {'name': 'Outro nome'}),
        ('post', '/collection-templates/{id}/columns', column_payload()),
        (
            'patch',
            '/collection-templates/{id}/columns/{column_id}',
            {'label': 'Novo'},
        ),
        ('delete', '/collection-templates/{id}/columns/{column_id}', None),
    ],
)
async def test_write_requires_trusted_origin(  # noqa: PLR0913, PLR0917
    client, session, manager, template, column, method, path, body
):
    """FR-029."""
    authenticate(client, manager)
    url = path.format(id=template.id, column_id=column.id)

    response = client.request(method, url, json=body)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'invalid_origin'
    await session.refresh(template)
    await session.refresh(column)
    assert template.name == template_payload()['name']
    assert template.updated_by is None
    assert column.label == 'Original'
    assert column.deleted_at is None
    assert await _count(session, CollectionTemplate) == 1
    assert await _count(session, CollectionTemplateColumn) == 1


@pytest.mark.asyncio
async def test_form_template_permission_does_not_open_the_catalog(
    client, session
):
    form_editor = await _make_rbac_user(
        session,
        system_key='form_editor',
        name='Editor de formulários',
        codes=('form_templates.manage',),
    )
    authenticate(client, form_editor)

    _forbidden(create_template(client))


@pytest.mark.asyncio
async def test_custom_profile_with_permission_manages_the_catalog(
    client, session, user
):
    """A permissão vale fora de Admin e BraCVAM."""
    await grant_catalog_permission(session, user)
    authenticate(client, user)

    created = create_template(client)
    listed = client.get('/collection-templates')

    assert created.status_code == HTTPStatus.CREATED, created.text
    assert listed.status_code == HTTPStatus.OK, listed.text
    assert [item['id'] for item in listed.json()['data']] == [
        created.json()['id']
    ]
