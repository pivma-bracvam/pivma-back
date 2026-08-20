from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pivma.core.authorization import (
    ADMINISTRATOR_SYSTEM_KEY,
    RBAC_ASSIGNMENTS_MANAGE,
    RBAC_PROFILES_MANAGE,
    RBAC_READ,
    active_profile_permissions,
    active_profiles_for_user,
    effective_permission_codes,
    ensure_administrator_remains,
    replace_profile_permissions,
)
from pivma.core.database.models import (
    AccessProfile,
    Permission,
    RbacChange,
    User,
    UserAccessProfile,
)
from pivma.dependencies import Session, TrustedOrigin, require_permission
from pivma.schemas import (
    PermissionPublic,
    ProfileAssignmentPublic,
    ProfileCreate,
    ProfilePublic,
    ProfileSummary,
    ProfileUpdate,
    RbacChangePage,
    RbacChangePublic,
    UserAccess,
)

router = APIRouter(prefix='/rbac', tags=['rbac'])
MAX_CHANGE_LIMIT = 100
ReadUser = Annotated[User, Depends(require_permission(RBAC_READ))]
ProfileManager = Annotated[
    User, Depends(require_permission(RBAC_PROFILES_MANAGE))
]
AssignmentManager = Annotated[
    User, Depends(require_permission(RBAC_ASSIGNMENTS_MANAGE))
]


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.CONFLICT, detail=detail)


async def profile_public(
    session: Session, profile: AccessProfile
) -> ProfilePublic:
    return ProfilePublic(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        active=profile.deleted_at is None,
        official=profile.system_key is not None,
        permission_codes=await active_profile_permissions(session, profile.id),
        created_by=profile.created_by,
        created_at=profile.created_at,
        updated_by=profile.updated_by,
        updated_at=profile.updated_at,
        deleted_by=profile.deleted_by,
        deleted_at=profile.deleted_at,
    )


def change(
    action: str, target_type: str, target_id: UUID, actor_id: UUID | None
) -> RbacChange:
    item = RbacChange(
        action=action, target_type=target_type, target_id=target_id
    )
    if actor_id is not None:
        item.set_creation_audit(actor_id)
    return item


async def commit_or_conflict(session: Session) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise conflict('Conflicting active RBAC state') from exc


async def flush_or_conflict(session: Session) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise conflict('Conflicting active RBAC state') from exc


@router.get('/permissions', response_model=list[PermissionPublic])
async def list_permissions(session: Session, actor: ReadUser):
    del actor
    return list(
        await session.scalars(select(Permission).order_by(Permission.code))
    )


@router.get('/profiles', response_model=list[ProfilePublic])
async def list_profiles(session: Session, actor: ReadUser):
    del actor
    profiles = list(
        await session.scalars(
            select(AccessProfile).order_by(AccessProfile.name)
        )
    )
    return [await profile_public(session, profile) for profile in profiles]


@router.post(
    '/profiles', status_code=HTTPStatus.CREATED, response_model=ProfilePublic
)
async def create_profile(
    payload: ProfileCreate,
    session: Session,
    actor: ProfileManager,
    origin: TrustedOrigin,
):
    del origin
    official = await session.scalar(
        select(AccessProfile).where(
            AccessProfile.system_key.is_not(None),
            AccessProfile.name.ilike(payload.name),
        )
    )
    if official is not None:
        raise conflict('Official profile name is reserved')
    profile = AccessProfile(
        name=payload.name, description=payload.description, system_key=None
    )
    profile.set_creation_audit(actor.id)
    session.add(profile)
    await flush_or_conflict(session)
    try:
        await replace_profile_permissions(
            session, profile, payload.permission_codes, actor.id
        )
    except ValueError as exc:
        await session.rollback()
        raise conflict(str(exc)) from exc
    session.add(change('profile.created', 'profile', profile.id, actor.id))
    if payload.permission_codes:
        session.add(
            change(
                'profile.permissions_replaced',
                'profile_permissions',
                profile.id,
                actor.id,
            )
        )
    await commit_or_conflict(session)
    await session.refresh(profile)
    return await profile_public(session, profile)


@router.patch('/profiles/{profile_id}', response_model=ProfilePublic)
async def update_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    session: Session,
    actor: ProfileManager,
    origin: TrustedOrigin,
):
    del origin
    profile = await session.scalar(
        select(AccessProfile).where(AccessProfile.id == profile_id)
    )
    if profile is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Profile not found'
        )
    if profile.deleted_at is not None:
        raise conflict('Profile is inactive')
    if payload.name is not None:
        if profile.system_key is not None:
            raise conflict('Official profile name cannot change')
        official = await session.scalar(
            select(AccessProfile.id).where(
                AccessProfile.system_key.is_not(None),
                AccessProfile.name.ilike(payload.name),
            )
        )
        if official is not None:
            raise conflict('Official profile name is reserved')
        profile.name = payload.name
    if payload.description is not None:
        profile.description = payload.description
    if payload.name is not None or payload.description is not None:
        profile.set_update_audit(actor.id)
        session.add(change('profile.updated', 'profile', profile.id, actor.id))
    if payload.permission_codes is not None:
        try:
            await replace_profile_permissions(
                session, profile, payload.permission_codes, actor.id
            )
            await ensure_administrator_remains(session)
        except ValueError as exc:
            await session.rollback()
            raise conflict(str(exc)) from exc
        session.add(
            change(
                'profile.permissions_replaced',
                'profile_permissions',
                profile.id,
                actor.id,
            )
        )
    await commit_or_conflict(session)
    await session.refresh(profile)
    return await profile_public(session, profile)


@router.delete('/profiles/{profile_id}', status_code=HTTPStatus.NO_CONTENT)
async def deactivate_profile(
    profile_id: UUID,
    session: Session,
    actor: ProfileManager,
    origin: TrustedOrigin,
) -> Response:
    del origin
    profile = await session.scalar(
        select(AccessProfile).where(AccessProfile.id == profile_id)
    )
    if profile is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Profile not found'
        )
    if profile.deleted_at is not None:
        raise conflict('Profile is inactive')
    if profile.system_key == ADMINISTRATOR_SYSTEM_KEY:
        raise conflict('Administrator profile cannot be deactivated')
    profile.set_deletion_audit(actor.id)
    await session.flush()
    try:
        await ensure_administrator_remains(session)
    except ValueError as exc:
        await session.rollback()
        raise conflict(str(exc)) from exc
    session.add(change('profile.deactivated', 'profile', profile.id, actor.id))
    await commit_or_conflict(session)
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get('/users/{user_id}/access', response_model=UserAccess)
async def get_user_access(user_id: UUID, session: Session, actor: ReadUser):
    del actor
    user = await session.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='User not found'
        )
    profiles = await active_profiles_for_user(session, user_id)
    return UserAccess(
        user_id=user_id,
        profiles=[
            ProfileSummary(id=item.id, name=item.name, active=True)
            for item in profiles
        ],
        effective_permissions=await effective_permission_codes(
            session, user_id
        ),
    )


@router.post(
    '/users/{user_id}/profiles/{profile_id}',
    status_code=HTTPStatus.CREATED,
    response_model=ProfileAssignmentPublic,
)
async def grant_profile(
    user_id: UUID,
    profile_id: UUID,
    session: Session,
    actor: AssignmentManager,
    origin: TrustedOrigin,
):
    del origin
    user = await session.scalar(select(User).where(User.id == user_id))
    profile = await session.scalar(
        select(AccessProfile).where(AccessProfile.id == profile_id)
    )
    if user is None or profile is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='User or profile not found',
        )
    if user.deleted_at is not None or profile.deleted_at is not None:
        raise conflict('User or profile is inactive')
    assignment = UserAccessProfile(user_id=user_id, profile_id=profile_id)
    assignment.set_creation_audit(actor.id)
    session.add(assignment)
    await flush_or_conflict(session)
    session.add(
        change('assignment.granted', 'assignment', assignment.id, actor.id)
    )
    await commit_or_conflict(session)
    await session.refresh(assignment)
    return ProfileAssignmentPublic(
        id=assignment.id,
        user_id=user_id,
        profile_id=profile_id,
        created_by=assignment.created_by,
        created_at=assignment.created_at,
        active=True,
        deleted_by=assignment.deleted_by,
        deleted_at=assignment.deleted_at,
    )


@router.delete(
    '/users/{user_id}/profiles/{profile_id}', status_code=HTTPStatus.NO_CONTENT
)
async def revoke_profile(
    user_id: UUID,
    profile_id: UUID,
    session: Session,
    actor: AssignmentManager,
    origin: TrustedOrigin,
) -> Response:
    del origin
    assignment = await session.scalar(
        select(UserAccessProfile)
        .where(
            UserAccessProfile.user_id == user_id,
            UserAccessProfile.profile_id == profile_id,
            UserAccessProfile.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if assignment is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Assignment not found'
        )
    assignment.set_deletion_audit(actor.id)
    await session.flush()
    try:
        await ensure_administrator_remains(session)
    except ValueError as exc:
        await session.rollback()
        raise conflict(str(exc)) from exc
    session.add(
        change('assignment.revoked', 'assignment', assignment.id, actor.id)
    )
    await commit_or_conflict(session)
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get('/changes', response_model=RbacChangePage)
async def list_changes(
    session: Session,
    actor: ReadUser,
    offset: int = 0,
    limit: int = 100,
):
    del actor
    if offset < 0 or limit < 1 or limit > MAX_CHANGE_LIMIT:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='Invalid pagination',
        )
    items = list(
        await session.scalars(
            select(RbacChange)
            .order_by(RbacChange.created_at.desc(), RbacChange.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return RbacChangePage(
        offset=offset,
        limit=limit,
        items=[
            RbacChangePublic(
                id=item.id,
                action=item.action,
                target_type=item.target_type,
                target_id=item.target_id,
                actor_user_id=item.created_by,
                occurred_at=item.created_at,
            )
            for item in items
        ],
    )
