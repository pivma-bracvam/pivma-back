from datetime import datetime
from http import HTTPStatus

import pytest
import pytest_asyncio

from pivma.core.authorization import ADMINISTRATIVE_PERMISSIONS
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    RbacChange,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}


@pytest_asyncio.fixture
async def rbac_administrator(session, user):
    permissions = [
        Permission(code=code, description=f'Permission {code}')
        for code in sorted(ADMINISTRATIVE_PERMISSIONS)
    ]
    profile = AccessProfile(
        system_key='administrator',
        name='Administrador',
        description='RBAC administrator',
    )
    session.add_all([*permissions, profile])
    await session.flush()
    session.add_all(
        [
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
            for permission in permissions
        ]
        + [UserAccessProfile(user_id=user.id, profile_id=profile.id)]
    )
    await session.commit()
    return user


def authenticate(client, user) -> str:
    token = create_access_token(user.id, Settings().JWT_SECRET_KEY)
    client.cookies.set('access_token', token)
    return token


def test_profile_assignment_access_and_change_history_happy_path(
    client, rbac_administrator, other_user
):
    authenticate(client, rbac_administrator)

    create_response = client.post(
        '/rbac/profiles',
        headers=TRUSTED_ORIGIN,
        json={
            'name': 'Research reader',
            'description': 'May inspect RBAC data',
            'permission_codes': ['rbac.read'],
        },
    )
    assert create_response.status_code == HTTPStatus.CREATED
    profile = create_response.json()
    profile_id = profile['id']
    assert profile['permission_codes'] == ['rbac.read']
    assert profile['created_by'] == str(rbac_administrator.id)

    update_response = client.patch(
        f'/rbac/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
        json={'description': 'Updated reader description'},
    )
    assert update_response.status_code == HTTPStatus.OK
    assert (
        update_response.json()['description'] == 'Updated reader description'
    )
    assert update_response.json()['updated_by'] == str(rbac_administrator.id)

    grant_response = client.post(
        f'/rbac/users/{other_user.id}/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
    )
    assert grant_response.status_code == HTTPStatus.CREATED
    assignment = grant_response.json()
    assert assignment['user_id'] == str(other_user.id)
    assert assignment['profile_id'] == profile_id
    assert assignment['created_by'] == str(rbac_administrator.id)

    access_response = client.get(f'/rbac/users/{other_user.id}/access')
    assert access_response.status_code == HTTPStatus.OK
    assert access_response.json() == {
        'user_id': str(other_user.id),
        'profiles': [
            {'id': profile_id, 'name': 'Research reader', 'active': True}
        ],
        'effective_permissions': ['rbac.read'],
    }

    changes_response = client.get('/rbac/changes')
    assert changes_response.status_code == HTTPStatus.OK
    changes = changes_response.json()['items']
    assert {
        'profile.created',
        'profile.updated',
        'profile.permissions_replaced',
        'assignment.granted',
    }.issubset({item['action'] for item in changes})
    assert [(item['occurred_at'], item['id']) for item in changes] == sorted(
        [(item['occurred_at'], item['id']) for item in changes], reverse=True
    )
    for item in changes:
        assert item['actor_user_id'] == str(rbac_administrator.id)
        datetime.fromisoformat(item['occurred_at'])

    revoke_response = client.delete(
        f'/rbac/users/{other_user.id}/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
    )
    assert revoke_response.status_code == HTTPStatus.NO_CONTENT

    deactivate_response = client.delete(
        f'/rbac/profiles/{profile_id}', headers=TRUSTED_ORIGIN
    )
    assert deactivate_response.status_code == HTTPStatus.NO_CONTENT

    final_changes = client.get('/rbac/changes').json()['items']
    assert {
        'profile.deactivated',
        'assignment.revoked',
    }.issubset({item['action'] for item in final_changes})


def test_revocation_takes_effect_on_next_request_with_same_cookie(
    client, rbac_administrator, other_user
):
    authenticate(client, rbac_administrator)
    profile_response = client.post(
        '/rbac/profiles',
        headers=TRUSTED_ORIGIN,
        json={
            'name': 'Temporary reader',
            'description': 'Temporary read access',
            'permission_codes': ['rbac.read'],
        },
    )
    profile_id = profile_response.json()['id']
    grant_response = client.post(
        f'/rbac/users/{other_user.id}/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
    )
    assert grant_response.status_code == HTTPStatus.CREATED

    target_token = authenticate(client, other_user)
    allowed_response = client.get('/rbac/permissions')
    assert allowed_response.status_code == HTTPStatus.OK

    authenticate(client, rbac_administrator)
    revoke_response = client.delete(
        f'/rbac/users/{other_user.id}/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
    )
    assert revoke_response.status_code == HTTPStatus.NO_CONTENT

    client.cookies.set('access_token', target_token)
    denied_response = client.get('/rbac/permissions')
    assert denied_response.status_code == HTTPStatus.FORBIDDEN
    assert denied_response.json() == {'detail': 'Forbidden'}


def test_inactive_profile_takes_effect_on_next_request_with_same_cookie(
    client, rbac_administrator, other_user
):
    authenticate(client, rbac_administrator)
    profile_response = client.post(
        '/rbac/profiles',
        headers=TRUSTED_ORIGIN,
        json={
            'name': 'Expiring reader',
            'description': 'Read access from an active profile',
            'permission_codes': ['rbac.read'],
        },
    )
    profile_id = profile_response.json()['id']
    client.post(
        f'/rbac/users/{other_user.id}/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
    )

    target_token = authenticate(client, other_user)
    assert client.get('/rbac/permissions').status_code == HTTPStatus.OK

    authenticate(client, rbac_administrator)
    deactivate_response = client.delete(
        f'/rbac/profiles/{profile_id}', headers=TRUSTED_ORIGIN
    )
    assert deactivate_response.status_code == HTTPStatus.NO_CONTENT

    client.cookies.set('access_token', target_token)
    denied_response = client.get('/rbac/permissions')
    assert denied_response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_change_history_exposes_bootstrap_with_null_actor(
    client, session, rbac_administrator
):
    bootstrap_change = RbacChange(
        action='bootstrap.admin_assigned',
        target_type='assignment',
        target_id=rbac_administrator.id,
    )
    session.add(bootstrap_change)
    await session.commit()
    await session.refresh(bootstrap_change)
    authenticate(client, rbac_administrator)

    response = client.get('/rbac/changes')

    assert response.status_code == HTTPStatus.OK
    item = next(
        change
        for change in response.json()['items']
        if change['id'] == str(bootstrap_change.id)
    )
    assert item['action'] == 'bootstrap.admin_assigned'
    assert item['target_type'] == 'assignment'
    assert item['actor_user_id'] is None
    datetime.fromisoformat(item['occurred_at'])
