from http import HTTPStatus

import pytest
from fastapi import HTTPException

from pivma.core.database.models import AccessProfile, UserAccessProfile
from pivma.routers.rbac import flush_or_conflict


@pytest.mark.asyncio
async def test_flush_conflict_rolls_back_equivalent_active_profile_name(
    session,
):
    session.add(
        AccessProfile(
            system_key=None,
            name='Equivalent profile',
            description='First active profile',
        )
    )
    await session.commit()
    session.add(
        AccessProfile(
            system_key=None,
            name='EQUIVALENT PROFILE',
            description='Conflicting active profile',
        )
    )

    with pytest.raises(HTTPException) as error:
        await flush_or_conflict(session)

    assert error.value.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_flush_conflict_rolls_back_duplicate_active_assignment(
    session, user
):
    profile = AccessProfile(
        system_key=None,
        name='Assignable profile',
        description='Profile for the assignment test',
    )
    session.add(profile)
    await session.commit()
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile.id))
    await session.commit()
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile.id))

    with pytest.raises(HTTPException) as error:
        await flush_or_conflict(session)

    assert error.value.status_code == HTTPStatus.CONFLICT
