"""Admin/BraCVAM cobrem toda Permission dinamicamente (Spec 023)."""

import pytest
from sqlalchemy import select

from pivma.core.authorization import (
    active_profile_permissions,
    can_manage_process_templates,
    effective_permission_codes,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from tests.factories.rbac_factory import (
    AccessProfileFactory,
    UserAccessProfileFactory,
)


async def _new_permission(session, code: str) -> Permission:
    permission = Permission(code=code, description=code)
    session.add(permission)
    await session.commit()
    return permission


@pytest.mark.asyncio
async def test_administrator_has_permission_never_explicitly_composed(
    session, ai_eval_admin
):
    permission = await _new_permission(session, 'future.feature.manage')

    codes = await effective_permission_codes(session, ai_eval_admin.id)

    assert permission.code in codes


@pytest.mark.asyncio
async def test_bracvam_has_permission_never_explicitly_composed(
    session, bracvam_user
):
    permission = await _new_permission(session, 'future.feature.manage')

    codes = await effective_permission_codes(session, bracvam_user.id)

    assert permission.code in codes


@pytest.mark.asyncio
async def test_custom_profile_keeps_only_composed_permissions(session, user):
    await _new_permission(session, 'unrelated.permission')
    granted = await _new_permission(session, 'granted.permission')
    profile = AccessProfileFactory(name='Perfil de teste')
    session.add(profile)
    await session.flush()
    composition = AccessProfilePermission(
        profile_id=profile.id, permission_id=granted.id
    )
    session.add(composition)
    session.add(UserAccessProfileFactory(user=user, profile=profile))
    await session.commit()

    codes = await effective_permission_codes(session, user.id)

    assert codes == ['granted.permission']


@pytest.mark.asyncio
async def test_administrator_profile_permission_listing_includes_uncomposed(
    session, ai_eval_admin
):
    permission = await _new_permission(session, 'future.listing.manage')
    profile_id = await session.scalar(
        select(UserAccessProfile.profile_id)
        .join(AccessProfile, AccessProfile.id == UserAccessProfile.profile_id)
        .where(
            UserAccessProfile.user_id == ai_eval_admin.id,
            AccessProfile.system_key == 'administrator',
        )
    )

    codes = await active_profile_permissions(
        session, profile_id, system_key='administrator'
    )

    assert permission.code in codes


@pytest.mark.asyncio
async def test_bracvam_user_can_manage_process_templates(
    session, bracvam_user
):
    """`rbac.read` precisa existir para "toda permissão" incluí-la."""
    await _new_permission(session, 'rbac.read')

    assert await can_manage_process_templates(session, bracvam_user.id) is True


@pytest.mark.asyncio
async def test_group_manager_name_no_longer_grants_template_management(
    session, user
):
    profile = AccessProfileFactory(name='Grupo Gestor', system_key=None)
    session.add(profile)
    await session.flush()
    session.add(UserAccessProfileFactory(user=user, profile=profile))
    await session.commit()

    assert await can_manage_process_templates(session, user.id) is False
