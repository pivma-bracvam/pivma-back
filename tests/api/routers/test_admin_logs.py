from http import HTTPStatus

import pytest

from pivma.core.authorization import (
    ADMINISTRATIVE_PERMISSIONS,
    ADMINISTRATOR_SYSTEM_KEY,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}


async def make_admin_user(session):
    user = UserFactory()
    session.add(user)
    await session.flush()

    permissions = [
        Permission(code=code, description=f'Permission {code}')
        for code in sorted(ADMINISTRATIVE_PERMISSIONS)
    ]
    profile = AccessProfile(
        system_key=ADMINISTRATOR_SYSTEM_KEY,
        name='Administrador',
        description='Admin Profile',
    )
    session.add_all([*permissions, profile])
    await session.flush()

    session.add_all(
        [
            AccessProfilePermission(profile_id=profile.id, permission_id=p.id)
            for p in permissions
        ]
        + [UserAccessProfile(user_id=user.id, profile_id=profile.id)]
    )
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_admin_logs_forbidden_for_regular_user(client, session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    res = client.get('/admin/logs/operational', headers=TRUSTED_ORIGIN)
    assert res.status_code == HTTPStatus.FORBIDDEN

    res_ai = client.get('/admin/logs/ai', headers=TRUSTED_ORIGIN)
    assert res_ai.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_logs_forbidden_for_rbac_read_only_user(client, session):
    """Issue #39: `rbac.read` é permissão de leitura do RBAC, não prova de

    administrador — não deve autorizar acesso a logs administrativos.
    """
    user = UserFactory()
    session.add(user)
    profile = AccessProfile(
        system_key=None,
        name='Consulta RBAC',
        description='Perfil de teste com rbac.read apenas',
    )
    session.add(profile)
    await session.flush()
    permission = Permission(code='rbac.read', description='Read RBAC')
    session.add(permission)
    await session.flush()
    session.add(
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        )
    )
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile.id))
    await session.commit()
    authenticate(client, user)

    res = client.get('/admin/logs/operational', headers=TRUSTED_ORIGIN)
    assert res.status_code == HTTPStatus.FORBIDDEN

    res_ai = client.get('/admin/logs/ai', headers=TRUSTED_ORIGIN)
    assert res_ai.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_admin_logs_allowed_for_administrator(client, session):
    admin = await make_admin_user(session)
    authenticate(client, admin)

    res = client.get('/admin/logs/operational', headers=TRUSTED_ORIGIN)
    assert res.status_code == HTTPStatus.OK
    assert isinstance(res.json(), list)

    res_ai = client.get('/admin/logs/ai', headers=TRUSTED_ORIGIN)
    assert res_ai.status_code == HTTPStatus.OK
    assert isinstance(res_ai.json(), list)


@pytest.mark.parametrize(
    'path',
    ['/admin/logs/operational/stream', '/admin/logs/ai/stream'],
)
def test_removed_log_stream_endpoints_return_not_found(client, path):
    response = client.get(path, headers=TRUSTED_ORIGIN)

    assert response.status_code == HTTPStatus.NOT_FOUND
