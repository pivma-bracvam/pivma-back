from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Institution,
    Laboratory,
    Permission,
    User,
    UserAccessProfile,
    UserInstitutionalAffiliation,
)

RBAC_READ = 'rbac.read'
RBAC_PROFILES_MANAGE = 'rbac.profiles.manage'
RBAC_ASSIGNMENTS_MANAGE = 'rbac.assignments.manage'
INSTITUTIONAL_READ = 'institutional.read'
INSTITUTIONAL_CATALOGS_MANAGE = 'institutional.catalogs.manage'
INSTITUTIONAL_AFFILIATIONS_MANAGE = 'institutional.affiliations.manage'
ADMINISTRATIVE_PERMISSIONS = frozenset({
    RBAC_READ,
    RBAC_PROFILES_MANAGE,
    RBAC_ASSIGNMENTS_MANAGE,
})
ADMINISTRATOR_SYSTEM_KEY = 'administrator'


async def effective_permission_codes(
    session: AsyncSession, user_id: UUID
) -> list[str]:
    result = await session.scalars(
        select(Permission.code)
        .join(
            AccessProfilePermission,
            AccessProfilePermission.permission_id == Permission.id,
        )
        .join(
            AccessProfile,
            AccessProfile.id == AccessProfilePermission.profile_id,
        )
        .join(
            UserAccessProfile, UserAccessProfile.profile_id == AccessProfile.id
        )
        .join(User, User.id == UserAccessProfile.user_id)
        .where(
            User.id == user_id,
            User.deleted_at.is_(None),
            UserAccessProfile.deleted_at.is_(None),
            AccessProfile.deleted_at.is_(None),
            AccessProfilePermission.deleted_at.is_(None),
            Permission.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Permission.code)
    )
    return list(result)


async def has_permission(
    session: AsyncSession, user_id: UUID, code: str
) -> bool:
    return code in await effective_permission_codes(session, user_id)


async def active_profile_permissions(
    session: AsyncSession, profile_id: UUID
) -> list[str]:
    result = await session.scalars(
        select(Permission.code)
        .join(
            AccessProfilePermission,
            AccessProfilePermission.permission_id == Permission.id,
        )
        .where(
            AccessProfilePermission.profile_id == profile_id,
            AccessProfilePermission.deleted_at.is_(None),
            Permission.deleted_at.is_(None),
        )
        .order_by(Permission.code)
    )
    return list(result)


async def active_profiles_for_user(
    session: AsyncSession, user_id: UUID
) -> list[AccessProfile]:
    result = await session.scalars(
        select(AccessProfile)
        .join(
            UserAccessProfile, UserAccessProfile.profile_id == AccessProfile.id
        )
        .where(
            UserAccessProfile.user_id == user_id,
            UserAccessProfile.deleted_at.is_(None),
            AccessProfile.deleted_at.is_(None),
        )
        .order_by(AccessProfile.name)
    )
    return list(result)


async def active_institutional_affiliations(
    session: AsyncSession, user_id: UUID
) -> list[UserInstitutionalAffiliation]:
    result = await session.scalars(
        select(UserInstitutionalAffiliation)
        .join(User, User.id == UserInstitutionalAffiliation.user_id)
        .join(
            Institution,
            Institution.id == UserInstitutionalAffiliation.institution_id,
        )
        .outerjoin(
            Laboratory,
            Laboratory.id == UserInstitutionalAffiliation.laboratory_id,
        )
        .where(
            UserInstitutionalAffiliation.user_id == user_id,
            UserInstitutionalAffiliation.deleted_at.is_(None),
            User.deleted_at.is_(None),
            Institution.deleted_at.is_(None),
            or_(
                UserInstitutionalAffiliation.laboratory_id.is_(None),
                Laboratory.deleted_at.is_(None),
            ),
        )
        .order_by(
            UserInstitutionalAffiliation.created_at.desc(),
            UserInstitutionalAffiliation.id.desc(),
        )
    )
    return list(result)


async def replace_profile_permissions(
    session: AsyncSession,
    profile: AccessProfile,
    permission_codes: Iterable[str],
    actor_id: UUID,
) -> None:
    requested = set(permission_codes)
    permissions = list(
        await session.scalars(
            select(Permission).where(
                Permission.code.in_(requested), Permission.deleted_at.is_(None)
            )
        )
    )
    if len(permissions) != len(requested):
        raise ValueError('Permission not found')
    current = list(
        await session.scalars(
            select(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == profile.id,
                AccessProfilePermission.deleted_at.is_(None),
            )
        )
    )
    wanted_ids = {permission.id for permission in permissions}
    current_ids = {item.permission_id for item in current}
    for item in current:
        if item.permission_id not in wanted_ids:
            item.set_deletion_audit(actor_id)
    for permission in permissions:
        if permission.id not in current_ids:
            item = AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
            item.set_creation_audit(actor_id)
            session.add(item)
    await session.flush()


async def ensure_administrator_remains(session: AsyncSession) -> None:
    """Reject a state without an active account holding all RBAC powers."""
    await session.scalar(
        select(AccessProfile.id)
        .where(AccessProfile.system_key == ADMINISTRATOR_SYSTEM_KEY)
        .with_for_update()
    )
    result = await session.scalars(
        select(UserAccessProfile.user_id)
        .join(User, User.id == UserAccessProfile.user_id)
        .join(AccessProfile, AccessProfile.id == UserAccessProfile.profile_id)
        .join(
            AccessProfilePermission,
            AccessProfilePermission.profile_id == AccessProfile.id,
        )
        .join(
            Permission, Permission.id == AccessProfilePermission.permission_id
        )
        .where(
            User.deleted_at.is_(None),
            UserAccessProfile.deleted_at.is_(None),
            AccessProfile.deleted_at.is_(None),
            AccessProfilePermission.deleted_at.is_(None),
            Permission.deleted_at.is_(None),
            Permission.code.in_(ADMINISTRATIVE_PERMISSIONS),
        )
        .group_by(UserAccessProfile.user_id)
        .having(
            func.count(func.distinct(Permission.code))
            == len(ADMINISTRATIVE_PERMISSIONS)
        )
        .limit(1)
    )
    if result.first() is None:
        raise ValueError('At least one administrator must remain')
