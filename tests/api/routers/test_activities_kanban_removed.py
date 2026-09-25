"""Spec 029 - remoção de `GET /activities/kanban` (FR-007).

Regressão: a rota do Kanban de pendências (Spec 018) não pode voltar, nem
no roteamento nem no contrato OpenAPI publicado.
"""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_kanban_route_returns_404_for_authenticated_user(
    client, session
):
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.get('/activities/kanban')

    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_kanban_route_returns_404_without_authentication(client):
    resp = client.get('/activities/kanban')

    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_openapi_does_not_expose_kanban_path_or_activities_tag(client):
    spec = client.get('/openapi.json').json()

    assert not any(path.startswith('/activities') for path in spec['paths'])
    operation_tags = {
        tag
        for operations in spec['paths'].values()
        for operation in operations.values()
        for tag in operation.get('tags', [])
    }
    assert 'Activities' not in operation_tags


def test_openapi_does_not_expose_kanban_schemas(client):
    spec = client.get('/openapi.json').json()

    schemas = spec.get('components', {}).get('schemas', {})
    assert not [name for name in schemas if name.startswith('Kanban')]
