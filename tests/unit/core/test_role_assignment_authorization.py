"""`can_manage_role_assignment`: só `process.participants.manage` (Admin e
BraCVAM) designa os cargos da Fase 2 (reunião de feedback, 2026-11-18;
substitui a FR-003 da Spec 028).
"""

import pytest

from pivma.core.authorization import (
    PROCESS_PARTICIPANTS_MANAGE,
    can_manage_role_assignment,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from tests.factories.participant_factory import AssignmentFactory
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)
from tests.factories.user_factory import UserFactory

THE_8_ROLES = (
    'sponsor',
    'group_manager',
    'sample_selection_group',
    'lead_laboratory',
    'participating_laboratory',
    'statistician',
    'collaborator',
    'adhoc_evaluator',
)


async def _make_process(session):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.commit()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.commit()
    process = ProcessInstanceFactory(template_version=version)
    session.add(process)
    await session.commit()
    return process


async def _grant_global_permission(session, user):
    permission = Permission(
        code=PROCESS_PARTICIPANTS_MANAGE,
        description=PROCESS_PARTICIPANTS_MANAGE,
    )
    profile = AccessProfile(
        name=f'Role assignment admin {user.id}', description='admin'
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


@pytest.mark.asyncio
@pytest.mark.parametrize('role_key', THE_8_ROLES)
async def test_global_permission_authorizes_every_role(session, role_key):
    """U-A01: permissão global autoriza qualquer um dos 8 papéis."""
    user = UserFactory()
    session.add(user)
    await session.commit()
    process = await _make_process(session)
    await _grant_global_permission(session, user)

    assert await can_manage_role_assignment(
        session, user.id, process.id, role_key
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('process_role', ['group_manager', 'proponent'])
@pytest.mark.parametrize('role_key', THE_8_ROLES)
async def test_process_role_without_permission_is_denied(
    session, process_role, role_key
):
    """Grupo Gestor e Proponente efetivos não designam nenhum dos 8 papéis:
    só o BraCVAM e o Admin designam (reunião de feedback, 2026-11-18).
    """
    user = UserFactory()
    session.add(user)
    await session.commit()
    process = await _make_process(session)
    session.add(
        AssignmentFactory(process=process, user=user, role_key=process_role)
    )
    await session.commit()

    assert not await can_manage_role_assignment(
        session, user.id, process.id, role_key
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('role_key', THE_8_ROLES)
async def test_user_without_any_authorization_is_denied(session, role_key):
    """U-A04: sem a permissão, negado para os 8 papéis."""
    user = UserFactory()
    session.add(user)
    await session.commit()
    process = await _make_process(session)

    assert not await can_manage_role_assignment(
        session, user.id, process.id, role_key
    )
