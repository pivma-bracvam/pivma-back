import pytest

from pivma.core.authorization import effective_permission_codes
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)


@pytest.mark.asyncio
async def test_effective_permissions_union_and_ignore_inactive_records(
    session, user
):
    read = Permission(code='rbac.read', description='Read RBAC')
    manage = Permission(
        code='rbac.profiles.manage', description='Manage profiles'
    )
    first = AccessProfile(
        system_key=None, name='First role', description='First'
    )
    second = AccessProfile(
        system_key=None, name='Second role', description='Second'
    )
    session.add_all([read, manage, first, second])
    await session.flush()
    session.add_all([
        AccessProfilePermission(profile_id=first.id, permission_id=read.id),
        AccessProfilePermission(profile_id=second.id, permission_id=manage.id),
        UserAccessProfile(user_id=user.id, profile_id=first.id),
        UserAccessProfile(user_id=user.id, profile_id=second.id),
    ])
    await session.commit()

    assert await effective_permission_codes(session, user.id) == [
        'rbac.profiles.manage',
        'rbac.read',
    ]

    second.deleted_at = second.created_at
    await session.commit()
    assert await effective_permission_codes(session, user.id) == ['rbac.read']


@pytest.mark.asyncio
async def test_zero_profiles_and_shared_permission_are_distinct(session, user):
    assert await effective_permission_codes(session, user.id) == []

    permission = Permission(code='rbac.read', description='Read RBAC')
    profiles = [
        AccessProfile(
            system_key=None, name=f'Reader {index}', description='Reader'
        )
        for index in range(2)
    ]
    session.add_all([permission, *profiles])
    await session.flush()
    for profile in profiles:
        session.add_all([
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            ),
            UserAccessProfile(user_id=user.id, profile_id=profile.id),
        ])
    await session.commit()

    assert await effective_permission_codes(session, user.id) == ['rbac.read']
