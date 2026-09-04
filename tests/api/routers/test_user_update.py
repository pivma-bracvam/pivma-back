from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
import yaml

from pivma.core.authorization import USERS_MANAGE, USERS_READ
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings

ORIGIN = {'Origin': 'https://testserver'}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


async def grant_permission(session, user, code):
    profile = AccessProfile(
        system_key=None,
        name=f'User {code} manager {user.id}',
        description=f'Grants {code}',
    )
    session.add(profile)
    await session.flush()
    permission = Permission(code=code, description=f'Permission {code}')
    session.add(permission)
    await session.flush()
    session.add_all(
        [
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            ),
            UserAccessProfile(user_id=user.id, profile_id=profile.id),
        ]
    )
    await session.commit()


@pytest_asyncio.fixture
async def user_manager(session, user):
    await grant_permission(session, user, USERS_MANAGE)
    return user


@pytest.mark.asyncio
async def test_update_user_fills_legacy_full_name(
    client, session, user_manager, other_user
):
    authenticate(client, user_manager)

    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': '  Maria Silva  '},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'id': str(other_user.id),
        'username': other_user.username,
        'email': other_user.email,
        'full_name': 'Maria Silva',
    }
    await session.refresh(other_user)
    assert other_user.full_name == 'Maria Silva'


@pytest.mark.asyncio
async def test_update_user_replaces_existing_full_name(
    client, session, user_manager, other_user
):
    other_user.full_name = 'Old Name'
    await session.commit()
    authenticate(client, user_manager)

    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': 'New Name'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['full_name'] == 'New Name'


@pytest.mark.asyncio
async def test_update_user_records_update_audit(
    client, session, user_manager, other_user
):
    authenticate(client, user_manager)

    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': 'Audited Name'},
    )

    assert response.status_code == HTTPStatus.OK
    await session.refresh(other_user)
    assert other_user.updated_at is not None
    assert other_user.updated_by == user_manager.id


@pytest.mark.asyncio
async def test_update_user_preserves_non_name_fields(
    client, session, user_manager, other_user
):
    original = (
        other_user.username,
        other_user.email,
        other_user.password_hash,
        other_user.deleted_at,
    )
    authenticate(client, user_manager)

    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': 'Only Name'},
    )

    assert response.status_code == HTTPStatus.OK
    await session.refresh(other_user)
    assert (
        other_user.username,
        other_user.email,
        other_user.password_hash,
        other_user.deleted_at,
    ) == original


def test_update_user_requires_authentication(client, other_user):
    response = client.patch(
        f'/users/{other_user.id}', headers=ORIGIN, json={'full_name': 'Name'}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_update_user_requires_users_manage(
    client, session, user, other_user
):
    initial_full_name = other_user.full_name
    authenticate(client, user)
    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': 'Not Allowed'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    await session.refresh(other_user)
    assert other_user.full_name == initial_full_name


def test_update_user_requires_trusted_origin(client, user_manager, other_user):
    authenticate(client, user_manager)
    response = client.patch(
        f'/users/{other_user.id}',
        headers={'Origin': 'https://evil.example'},
        json={'full_name': 'Not Trusted'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_update_user_returns_not_found_for_unknown_uuid(client, user_manager):
    authenticate(client, user_manager)
    response = client.patch(
        f'/users/{uuid4()}', headers=ORIGIN, json={'full_name': 'Unknown'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    'full_name', ['', '   ', 'a' * 256, None]
)
def test_update_user_rejects_invalid_full_name(
    client, user_manager, other_user, full_name
):
    authenticate(client, user_manager)
    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': full_name},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_requires_full_name(client, user_manager, other_user):
    authenticate(client, user_manager)
    response = client.patch(
        f'/users/{other_user.id}', headers=ORIGIN, json={}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_rejects_extra_fields(client, user_manager, other_user):
    authenticate(client, user_manager)
    response = client.patch(
        f'/users/{other_user.id}',
        headers=ORIGIN,
        json={'full_name': 'Valid Name', 'email': 'changed@example.com'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_update_user_openapi_matches_contract(client):
    generated = client.get('/openapi.json').json()
    contract = yaml.safe_load(
        Path('specs/008-admin-user-update/contracts/users.openapi.yaml').read_text(
            encoding='utf-8'
        )
    )
    generated_operation = generated['paths']['/users/{user_id}']['patch']
    contract_operation = contract['paths']['/users/{user_id}']['patch']

    assert generated_operation['operationId'] == contract_operation[
        'operationId'
    ]
    assert (
        generated_operation['x-required-permission']
        == contract_operation['x-required-permission']
    )
    assert generated_operation['requestBody']['required'] is True
    assert generated_operation['requestBody']['content']['application/json'][
        'schema'
    ] == {'$ref': '#/components/schemas/UserUpdate'}
    assert generated['components']['schemas']['UserUpdate']['required'] == [
        'full_name'
    ]
    assert set(generated_operation['responses']) == {
        '200', '401', '403', '404', '422'
    }


@pytest.mark.asyncio
async def test_updated_full_name_is_visible_in_auth_and_listing(
    client, session, user_manager
):
    await grant_permission(session, user_manager, USERS_READ)
    authenticate(client, user_manager)

    changed = client.patch(
        f'/users/{user_manager.id}',
        headers=ORIGIN,
        json={'full_name': 'Administrator Name'},
    )

    assert changed.status_code == HTTPStatus.OK
    current = client.get('/auth/me')
    listing = client.get('/users')

    assert current.status_code == HTTPStatus.OK
    assert current.json()['full_name'] == 'Administrator Name'
    assert current.json()['user']['full_name'] == 'Administrator Name'
    listed = next(
        item
        for item in listing.json()['items']
        if item['id'] == str(user_manager.id)
    )
    assert listed['full_name'] == 'Administrator Name'
