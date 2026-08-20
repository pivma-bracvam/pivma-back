from http import HTTPStatus
from time import perf_counter

import pytest_asyncio

from pivma.core.authorization import ADMINISTRATIVE_PERMISSIONS
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}
MAX_ACCEPTANCE_SECONDS = 120


@pytest_asyncio.fixture
async def timed_administrator(session, user):
    permissions = [
        Permission(code=code, description=code)
        for code in sorted(ADMINISTRATIVE_PERMISSIONS)
    ]
    profile = AccessProfile(
        system_key='administrator',
        name='Administrador',
        description='RBAC administrator',
    )
    session.add_all([profile, *permissions])
    await session.flush()
    session.add_all([
        *[
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
            for permission in permissions
        ],
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()
    return user


def test_timed_profile_permission_and_assignment_flow(
    client, timed_administrator, other_user
):
    token = create_access_token(
        timed_administrator.id, Settings().JWT_SECRET_KEY
    )
    client.cookies.set('access_token', token)

    started_at = perf_counter()
    created = client.post(
        '/rbac/profiles',
        headers=TRUSTED_ORIGIN,
        json={
            'name': 'Timed acceptance profile',
            'description': 'Profile used by the timed acceptance flow',
        },
    )
    assert created.status_code == HTTPStatus.CREATED
    profile_id = created.json()['id']

    composed = client.patch(
        f'/rbac/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
        json={'permission_codes': ['rbac.read']},
    )
    assert composed.status_code == HTTPStatus.OK

    assigned = client.post(
        f'/rbac/users/{other_user.id}/profiles/{profile_id}',
        headers=TRUSTED_ORIGIN,
    )
    assert assigned.status_code == HTTPStatus.CREATED
    elapsed_seconds = perf_counter() - started_at

    assert elapsed_seconds <= MAX_ACCEPTANCE_SECONDS
    print(f'RBAC_TIMED_ACCEPTANCE_SECONDS={elapsed_seconds:.6f}')
