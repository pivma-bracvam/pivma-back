from http import HTTPStatus
from uuid import uuid4

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
from pivma.core.sse_broadcaster import broadcaster
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
async def test_admin_logs_allowed_for_administrator(client, session):
    admin = await make_admin_user(session)
    authenticate(client, admin)

    res = client.get('/admin/logs/operational', headers=TRUSTED_ORIGIN)
    assert res.status_code == HTTPStatus.OK
    assert isinstance(res.json(), list)

    res_ai = client.get('/admin/logs/ai', headers=TRUSTED_ORIGIN)
    assert res_ai.status_code == HTTPStatus.OK
    assert isinstance(res_ai.json(), list)


@pytest.mark.asyncio
async def test_sse_operational_and_ai_broadcaster():
    broadcaster.broadcast_operational({
        'event_id': str(uuid4()),
        'operation_type': 'TEST_OP',
        'status': 'SUCCESS',
    })
    broadcaster.broadcast_ai_step({
        'step_name': 'context_extraction',
        'step_order': 1,
        'status': 'SUCCESS',
    })

    gen_op = broadcaster.subscribe_operational()
    first_op = await anext(gen_op)
    assert ': connected' in first_op

    broadcaster.broadcast_operational({'msg': 'hello_op'})
    msg_op = await anext(gen_op)
    assert msg_op.startswith('data: ')
    assert 'hello_op' in msg_op

    gen_ai = broadcaster.subscribe_ai()
    first_ai = await anext(gen_ai)
    assert ': connected' in first_ai

    broadcaster.broadcast_ai_step({'msg': 'hello_ai'})
    msg_ai = await anext(gen_ai)
    assert msg_ai.startswith('data: ')
    assert 'hello_ai' in msg_ai
