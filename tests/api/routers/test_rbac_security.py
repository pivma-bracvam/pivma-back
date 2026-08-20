import logging
from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    RbacChange,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings


@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('get', '/rbac/permissions'),
        ('get', '/rbac/profiles'),
        ('get', f'/rbac/users/{uuid4()}/access'),
        ('get', '/rbac/changes'),
        ('post', '/rbac/profiles'),
        ('patch', f'/rbac/profiles/{uuid4()}'),
        ('delete', f'/rbac/profiles/{uuid4()}'),
        ('post', f'/rbac/users/{uuid4()}/profiles/{uuid4()}'),
        ('delete', f'/rbac/users/{uuid4()}/profiles/{uuid4()}'),
    ],
)
def test_rbac_routes_require_authentication(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}


@pytest_asyncio.fixture
async def read_user(session, user):
    permission = Permission(code='rbac.read', description='Read RBAC')
    profile = AccessProfile(
        system_key=None, name='Reader', description='Reader'
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
    return user


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


def test_read_permission_allows_catalog(client, read_user):
    authenticate(client, read_user)

    response = client.get('/rbac/permissions')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [
        {'code': 'rbac.read', 'description': 'Read RBAC'}
    ]


@pytest.mark.asyncio
async def test_forbidden_response_does_not_reveal_target_existence(
    client, session, user, other_user, caplog
):
    authenticate(client, user)
    paths = (
        f'/rbac/users/{other_user.id}/access',
        f'/rbac/users/{uuid4()}/access',
    )

    with caplog.at_level(logging.WARNING, logger='pivma.dependencies'):
        responses = [client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [
        HTTPStatus.FORBIDDEN,
        HTTPStatus.FORBIDDEN,
    ]
    assert [response.json() for response in responses] == [
        {'detail': 'Forbidden'},
        {'detail': 'Forbidden'},
    ]
    assert len([
        record
        for record in caplog.records
        if record.name == 'pivma.dependencies'
        and record.message.startswith('rbac.permission_denied')
    ]) == len(paths)
    assert list(await session.scalars(select(RbacChange))) == []


@pytest_asyncio.fixture
async def permission_user(request, session, user):
    code = request.param
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
    return user


@pytest.mark.parametrize('permission_user', ['rbac.read'], indirect=True)
def test_read_permission_does_not_grant_profile_management(
    client, permission_user
):
    authenticate(client, permission_user)

    allowed = client.get('/rbac/permissions')
    denied = client.post(
        '/rbac/profiles',
        headers={'Origin': 'https://testserver'},
        json={
            'name': 'Not allowed',
            'description': 'Requires profile management',
            'permission_codes': [],
        },
    )

    assert allowed.status_code == HTTPStatus.OK
    assert denied.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    'permission_user', ['rbac.profiles.manage'], indirect=True
)
def test_profile_management_does_not_grant_rbac_read(client, permission_user):
    authenticate(client, permission_user)

    allowed = client.post(
        '/rbac/profiles',
        headers={'Origin': 'https://testserver'},
        json={
            'name': 'Managed profile',
            'description': 'Created by the profile manager',
            'permission_codes': [],
        },
    )
    denied = client.get('/rbac/permissions')

    assert allowed.status_code == HTTPStatus.CREATED
    assert denied.status_code == HTTPStatus.FORBIDDEN


@pytest_asyncio.fixture
async def assignment_target(session, other_user):
    profile = AccessProfile(
        system_key=None,
        name='Assignment target',
        description='Profile used to validate assignment management',
    )
    session.add(profile)
    await session.commit()
    return other_user, profile


@pytest.mark.parametrize(
    'permission_user', ['rbac.assignments.manage'], indirect=True
)
def test_assignment_management_does_not_grant_profile_management(
    client, permission_user, assignment_target
):
    target_user, target_profile = assignment_target
    authenticate(client, permission_user)

    allowed = client.post(
        f'/rbac/users/{target_user.id}/profiles/{target_profile.id}',
        headers={'Origin': 'https://testserver'},
    )
    denied = client.post(
        '/rbac/profiles',
        headers={'Origin': 'https://testserver'},
        json={
            'name': 'Not allowed',
            'description': 'Requires profile management',
            'permission_codes': [],
        },
    )

    assert allowed.status_code == HTTPStatus.CREATED
    assert denied.status_code == HTTPStatus.FORBIDDEN


@pytest_asyncio.fixture
async def profile_manager_context(session, other_user):
    permission = Permission(
        code='rbac.profiles.manage', description='Manage profiles'
    )
    manager_profile = AccessProfile(
        system_key=None,
        name='Profile manager',
        description='Grants profile management',
    )
    existing_profile = AccessProfile(
        system_key=None,
        name='Existing profile',
        description='Used to provoke an active-name conflict',
    )
    session.add_all([permission, manager_profile, existing_profile])
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=manager_profile.id, permission_id=permission.id
        ),
        UserAccessProfile(
            user_id=other_user.id, profile_id=manager_profile.id
        ),
    ])
    await session.commit()
    return other_user


@pytest.mark.asyncio
async def test_only_permission_denial_emits_operational_rbac_log(
    client, session, user, profile_manager_context, caplog
):
    client.cookies.clear()

    with caplog.at_level(logging.WARNING, logger='pivma.dependencies'):
        unauthenticated = client.get('/rbac/permissions')

        authenticate(client, user)
        permission_denied = client.get('/rbac/permissions')

        authenticate(client, profile_manager_context)
        invalid_origin = client.post(
            '/rbac/profiles',
            json={
                'name': 'Valid payload',
                'description': 'The request has no trusted Origin',
                'permission_codes': [],
            },
        )
        invalid_payload = client.post(
            '/rbac/profiles',
            headers={'Origin': 'https://testserver'},
            json={},
        )
        conflict = client.post(
            '/rbac/profiles',
            headers={'Origin': 'https://testserver'},
            json={
                'name': 'EXISTING PROFILE',
                'description': 'Conflicts with an active profile name',
                'permission_codes': [],
            },
        )

    assert unauthenticated.status_code == HTTPStatus.UNAUTHORIZED
    assert permission_denied.status_code == HTTPStatus.FORBIDDEN
    assert invalid_origin.status_code == HTTPStatus.FORBIDDEN
    assert invalid_origin.json() == {'detail': 'Invalid origin'}
    assert invalid_payload.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert conflict.status_code == HTTPStatus.CONFLICT

    denial_records = [
        record
        for record in caplog.records
        if record.name == 'pivma.dependencies'
        and record.message.startswith('rbac.permission_denied')
    ]
    assert len(denial_records) == 1
    assert 'permission=rbac.read' in denial_records[0].message
    assert list(await session.scalars(select(RbacChange))) == []
