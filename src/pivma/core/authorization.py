from collections.abc import Iterable, Sequence
from uuid import UUID

from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Assignment,
    ConflictInterestDeclaration,
    Institution,
    Laboratory,
    Permission,
    User,
    UserAccessProfile,
    UserInstitutionalAffiliation,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

RBAC_READ = "rbac.read"
RBAC_PROFILES_MANAGE = "rbac.profiles.manage"
RBAC_ASSIGNMENTS_MANAGE = "rbac.assignments.manage"
USERS_READ = "users.read"
USERS_MANAGE = "users.manage"
INSTITUTIONAL_READ = "institutional.read"
INSTITUTIONAL_CATALOGS_MANAGE = "institutional.catalogs.manage"
INSTITUTIONAL_AFFILIATIONS_MANAGE = "institutional.affiliations.manage"
PROCESS_PARTICIPANTS_MANAGE = "process.participants.manage"
ADMINISTRATIVE_PERMISSIONS = frozenset({
    RBAC_READ,
    RBAC_PROFILES_MANAGE,
    RBAC_ASSIGNMENTS_MANAGE,
})
ADMINISTRATOR_SYSTEM_KEY = "administrator"
LABORATORY_ROLE_KEYS = frozenset({
    "lead_laboratory",
    "participating_laboratory",
})
GROUP_MANAGER_ROLE_KEY = "group_manager"


async def effective_permission_codes(session: AsyncSession, user_id: UUID) -> list[str]:
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
        .join(UserAccessProfile, UserAccessProfile.profile_id == AccessProfile.id)
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


async def has_permission(session: AsyncSession, user_id: UUID, code: str) -> bool:
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
    profiles_by_user = await active_profiles_for_users(session, [user_id])
    return profiles_by_user.get(user_id, [])


async def active_profiles_for_users(
    session: AsyncSession, user_ids: Sequence[UUID]
) -> dict[UUID, list[AccessProfile]]:
    if not user_ids:
        return {}

    result = await session.execute(
        select(UserAccessProfile.user_id, AccessProfile)
        .select_from(UserAccessProfile)
        .join(
            AccessProfile,
            AccessProfile.id == UserAccessProfile.profile_id,
        )
        .where(
            UserAccessProfile.user_id.in_(user_ids),
            UserAccessProfile.deleted_at.is_(None),
            AccessProfile.deleted_at.is_(None),
        )
        .order_by(
            UserAccessProfile.user_id,
            AccessProfile.name,
            AccessProfile.id,
        )
    )
    profiles_by_user = {user_id: [] for user_id in user_ids}
    for user_id, profile in result:
        profiles_by_user[user_id].append(profile)
    return profiles_by_user


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
        raise ValueError("Permission not found")
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
        .join(Permission, Permission.id == AccessProfilePermission.permission_id)
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
        raise ValueError("At least one administrator must remain")


# ==========================================
# PROCESS PARTICIPANT AUTHORIZATION
# ==========================================


async def has_active_laboratory_affiliation(
    session: AsyncSession, user_id: UUID, laboratory_id: UUID
) -> bool:
    result = await session.scalar(
        select(UserInstitutionalAffiliation.id)
        .join(User, User.id == UserInstitutionalAffiliation.user_id)
        .join(
            Institution,
            Institution.id == UserInstitutionalAffiliation.institution_id,
        )
        .where(
            UserInstitutionalAffiliation.user_id == user_id,
            UserInstitutionalAffiliation.laboratory_id == laboratory_id,
            UserInstitutionalAffiliation.deleted_at.is_(None),
            User.deleted_at.is_(None),
            Institution.deleted_at.is_(None),
        )
    )
    return result is not None


async def is_effective_group_manager(
    session: AsyncSession, user_id: UUID, process_id: UUID
) -> bool:
    result = await session.scalar(
        select(Assignment.id)
        .join(User, User.id == Assignment.user_id)
        .where(
            Assignment.process_instance_id == process_id,
            Assignment.user_id == user_id,
            Assignment.role_key == GROUP_MANAGER_ROLE_KEY,
            Assignment.revoked_at.is_(None),
            Assignment.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )
    return result is not None


async def can_manage_participants(
    session: AsyncSession, user_id: UUID, process_id: UUID
) -> bool:
    if await has_permission(session, user_id, PROCESS_PARTICIPANTS_MANAGE):
        return True
    return await is_effective_group_manager(session, user_id, process_id)


async def participant_read_scope(
    session: AsyncSession, user_id: UUID, process_id: UUID
) -> str | None:
    if await can_manage_participants(session, user_id, process_id):
        return "manager"
    result = await session.scalar(
        select(Assignment.id)
        .where(
            Assignment.process_instance_id == process_id,
            Assignment.user_id == user_id,
        )
        .limit(1)
    )
    return "self" if result is not None else None


async def compute_effectiveness_map(
    session: AsyncSession, assignments: Sequence[Assignment]
) -> dict[UUID, bool]:
    if not assignments:
        return {}

    user_ids = {assignment.user_id for assignment in assignments}
    laboratory_ids = {
        assignment.laboratory_id
        for assignment in assignments
        if assignment.laboratory_id is not None
    }

    active_user_ids = set(
        await session.scalars(
            select(User.id).where(User.id.in_(user_ids), User.deleted_at.is_(None))
        )
    )

    active_laboratory_ids: set[UUID] = set()
    active_affiliation_pairs: set[tuple[UUID, UUID]] = set()
    if laboratory_ids:
        active_laboratory_ids = set(
            await session.scalars(
                select(Laboratory.id).where(
                    Laboratory.id.in_(laboratory_ids),
                    Laboratory.deleted_at.is_(None),
                )
            )
        )
        affiliation_rows = await session.execute(
            select(
                UserInstitutionalAffiliation.user_id,
                UserInstitutionalAffiliation.laboratory_id,
            )
            .join(User, User.id == UserInstitutionalAffiliation.user_id)
            .where(
                UserInstitutionalAffiliation.user_id.in_(user_ids),
                UserInstitutionalAffiliation.laboratory_id.in_(laboratory_ids),
                UserInstitutionalAffiliation.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        )
        active_affiliation_pairs = {
            (row.user_id, row.laboratory_id) for row in affiliation_rows
        }

    effectiveness: dict[UUID, bool] = {}
    for assignment in assignments:
        if assignment.revoked_at is not None or assignment.deleted_at is not None:
            effectiveness[assignment.id] = False
            continue
        if assignment.user_id not in active_user_ids:
            effectiveness[assignment.id] = False
            continue
        if assignment.role_key in LABORATORY_ROLE_KEYS:
            if assignment.laboratory_id not in active_laboratory_ids:
                effectiveness[assignment.id] = False
                continue
            if (
                assignment.user_id,
                assignment.laboratory_id,
            ) not in active_affiliation_pairs:
                effectiveness[assignment.id] = False
                continue
        effectiveness[assignment.id] = True
    return effectiveness


async def latest_declarations_map(
    session: AsyncSession, assignment_ids: Sequence[UUID]
) -> dict[UUID, ConflictInterestDeclaration]:
    if not assignment_ids:
        return {}
    result = await session.scalars(
        select(ConflictInterestDeclaration)
        .where(ConflictInterestDeclaration.assignment_id.in_(assignment_ids))
        .distinct(ConflictInterestDeclaration.assignment_id)
        .order_by(
            ConflictInterestDeclaration.assignment_id,
            ConflictInterestDeclaration.declared_at.desc(),
            ConflictInterestDeclaration.id.desc(),
        )
    )
    return {row.assignment_id: row for row in result}


async def declarations_by_assignment(
    session: AsyncSession, assignment_ids: Sequence[UUID]
) -> dict[UUID, list[ConflictInterestDeclaration]]:
    grouped: dict[UUID, list[ConflictInterestDeclaration]] = {
        assignment_id: [] for assignment_id in assignment_ids
    }
    if not assignment_ids:
        return grouped
    result = await session.scalars(
        select(ConflictInterestDeclaration)
        .where(ConflictInterestDeclaration.assignment_id.in_(assignment_ids))
        .order_by(
            ConflictInterestDeclaration.declared_at.asc(),
            ConflictInterestDeclaration.id.asc(),
        )
    )
    for row in result:
        grouped[row.assignment_id].append(row)
    return grouped


async def has_current_conflict(
    session: AsyncSession, user_id: UUID, process_id: UUID
) -> bool:
    latest = (
        select(
            ConflictInterestDeclaration.assignment_id,
            ConflictInterestDeclaration.has_conflict,
        )
        .join(
            Assignment,
            Assignment.id == ConflictInterestDeclaration.assignment_id,
        )
        .where(
            Assignment.process_instance_id == process_id,
            Assignment.user_id == user_id,
            Assignment.revoked_at.is_(None),
            Assignment.deleted_at.is_(None),
        )
        .distinct(ConflictInterestDeclaration.assignment_id)
        .order_by(
            ConflictInterestDeclaration.assignment_id,
            ConflictInterestDeclaration.declared_at.desc(),
            ConflictInterestDeclaration.id.desc(),
        )
        .subquery()
    )
    count = await session.scalar(
        select(func.count()).select_from(latest).where(latest.c.has_conflict.is_(True))
    )
    return (count or 0) > 0
