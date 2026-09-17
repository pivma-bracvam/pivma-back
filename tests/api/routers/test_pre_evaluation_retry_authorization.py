# ruff: noqa: PLR2004
"""Autorização de `POST /admin/pre-evaluations/{run_id}/retry` (Issue #39).

Cobre só a camada de autorização (`require_admin`) — a lógica de retry em
si já é coberta em
`tests/integration/ai/test_process_retirement_pre_evaluation.py`.
Um `run_id` inexistente é suficiente: se a autorização barrar, a resposta é
403 antes mesmo de a rota consultar o banco; se passar, a resposta vira 404
(rota alcançada, execução não encontrada) — as duas são distinguíveis sem
precisar fabricar uma `EvaluationRun` real.
"""

from http import HTTPStatus
from uuid import uuid4

import pytest

from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}


@pytest.mark.asyncio
async def test_retry_forbidden_for_rbac_read_only_user(client, session):
    """Issue #39: `rbac.read` não deve autorizar reprocessamento de IA."""
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

    res = client.post(
        f'/admin/pre-evaluations/{uuid4()}/retry', headers=TRUSTED_ORIGIN
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_retry_reaches_handler_for_administrator(client, session):
    """Administrador oficial passa na autorização (chega à rota; a resposta

    é 404 porque o `run_id` é inexistente, não porque foi barrado).
    """
    admin = UserFactory()
    session.add(admin)
    profile = AccessProfile(
        system_key=ADMINISTRATOR_SYSTEM_KEY,
        name='Administrador',
        description='Administrador de teste',
    )
    session.add(profile)
    await session.flush()
    session.add(UserAccessProfile(user_id=admin.id, profile_id=profile.id))
    await session.commit()
    authenticate(client, admin)

    res = client.post(
        f'/admin/pre-evaluations/{uuid4()}/retry', headers=TRUSTED_ORIGIN
    )
    assert res.status_code == HTTPStatus.NOT_FOUND
