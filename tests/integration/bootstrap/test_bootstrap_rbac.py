from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from pivma.bootstrap_rbac import bootstrap_administrator
from pivma.core.database.models import (
    AccessProfile,
    RbacChange,
    UserAccessProfile,
)


@pytest_asyncio.fixture
async def administrator_profile(session):
    profile = AccessProfile(
        system_key='administrator',
        name='Administrador',
        description='RBAC administrator',
    )
    session.add(profile)
    await session.commit()
    return profile


@pytest.mark.asyncio
async def test_bootstrap_assigns_once_and_records_anonymous_change(
    session, user, administrator_profile
):
    await bootstrap_administrator(session, user.id)
    await session.commit()
    await bootstrap_administrator(session, user.id)
    await session.commit()

    assignments = list(
        await session.scalars(
            select(UserAccessProfile).where(
                UserAccessProfile.profile_id == administrator_profile.id
            )
        )
    )
    changes = list(await session.scalars(select(RbacChange)))
    assert len(assignments) == 1
    assert len(changes) == 1
    assert changes[0].created_by is None


@pytest.mark.asyncio
async def test_bootstrap_rejects_missing_user(session, administrator_profile):
    with pytest.raises(ValueError, match='Active user not found'):
        await bootstrap_administrator(session, uuid4())
