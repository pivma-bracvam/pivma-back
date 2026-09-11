"""Spec 018 - cargo global (Padrão/Admin/BraCVAM).

`has_platform_wide_access` é o único ponto que decide se um usuário enxerga
a plataforma inteira, independente de qualquer atribuição por processo.
"""

import pytest

from pivma.core.authorization import (
    ADMINISTRATOR_SYSTEM_KEY,
    BRACVAM_SYSTEM_KEY,
    has_platform_wide_access,
)
from tests.factories.rbac_factory import (
    AccessProfileFactory,
    UserAccessProfileFactory,
)
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_administrator_profile_has_platform_wide_access(session):
    user = UserFactory()
    profile = AccessProfileFactory(system_key=ADMINISTRATOR_SYSTEM_KEY)
    session.add_all([user, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=user, profile=profile))
    await session.commit()

    assert await has_platform_wide_access(session, user.id) is True


@pytest.mark.asyncio
async def test_bracvam_profile_has_platform_wide_access(session):
    user = UserFactory()
    profile = AccessProfileFactory(system_key=BRACVAM_SYSTEM_KEY)
    session.add_all([user, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=user, profile=profile))
    await session.commit()

    assert await has_platform_wide_access(session, user.id) is True


@pytest.mark.asyncio
async def test_user_without_global_profile_has_no_platform_wide_access(
    session,
):
    user = UserFactory()
    session.add(user)
    await session.commit()

    assert await has_platform_wide_access(session, user.id) is False


@pytest.mark.asyncio
async def test_other_profile_has_no_platform_wide_access(session):
    user = UserFactory()
    profile = AccessProfileFactory(system_key='study_manager')
    session.add_all([user, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=user, profile=profile))
    await session.commit()

    assert await has_platform_wide_access(session, user.id) is False
