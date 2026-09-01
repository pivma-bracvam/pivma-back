import logging
from http import HTTPStatus

import pytest
import pytest_asyncio
from sqlalchemy import select

from pivma.core.authorization import ADMINISTRATIVE_PERMISSIONS, USERS_READ
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    RbacChange,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


async def grant_permission(session, user, code):
    permission = Permission(code=code, description=f'Permission {code}')
    profile = AccessProfile(
        system_key=None,
        name=f'Profile for {code}',
        description=f'Grants only {code}',
    )
    session.add_all([permission, profile])
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        ),
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()


@pytest_asyncio.fixture
async def users_read_user(session, user):
    await grant_permission(session, user, USERS_READ)
    return user


@pytest_asyncio.fixture
async def administrative_permission_user(request, session, user):
    await grant_permission(session, user, request.param)
    return user


def test_list_users_requires_authentication(client):
    response = client.get('/users')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}
    assert 'items' not in response.json()


def test_list_users_requires_users_read(client, user):
    authenticate(client, user)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Forbidden'}
    assert 'items' not in response.json()


@pytest.mark.parametrize(
    'administrative_permission_user',
    sorted(ADMINISTRATIVE_PERMISSIONS),
    indirect=True,
)
def test_rbac_administrative_permissions_do_not_grant_user_listing(
    client, administrative_permission_user
):
    authenticate(client, administrative_permission_user)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Forbidden'}


def test_users_read_allows_user_listing(client, users_read_user):
    authenticate(client, users_read_user)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.OK


def test_denied_user_listing_emits_operational_log(client, user, caplog):
    authenticate(client, user)
    logging.getLogger('pivma.dependencies').disabled = False

    with caplog.at_level(logging.WARNING, logger='pivma.dependencies'):
        response = client.get('/users')

    assert response.status_code == HTTPStatus.FORBIDDEN
    records = [
        record
        for record in caplog.records
        if record.name == 'pivma.dependencies'
        and record.message.startswith('rbac.permission_denied')
    ]
    assert len(records) == 1
    assert 'permission=users.read' in records[0].message


@pytest.mark.asyncio
async def test_denied_user_listing_does_not_create_rbac_change(
    client, session, user
):
    authenticate(client, user)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert list(await session.scalars(select(RbacChange))) == []


@pytest.mark.asyncio
async def test_authorized_user_listing_does_not_create_rbac_change(
    client, session, users_read_user
):
    authenticate(client, users_read_user)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.OK
    assert list(await session.scalars(select(RbacChange))) == []
