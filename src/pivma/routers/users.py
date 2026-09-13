from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    USERS_MANAGE,
    USERS_READ,
    active_profiles_for_users,
)
from pivma.core.database import get_session
from pivma.core.database.models import AccessProfile, User, UserAccessProfile
from pivma.core.security import hash_password
from pivma.dependencies import (
    TrustedOrigin,
    require_permission,
)
from pivma.schemas import (
    AdminUser,
    AdminUserPage,
    ProfileSummary,
    UserPublic,
    UserSchema,
    UserUpdate,
)

router = APIRouter(prefix='/users', tags=['users'])
Session = Annotated[AsyncSession, Depends(get_session)]
UserListingReader = Annotated[User, Depends(require_permission(USERS_READ))]
UserManager = Annotated[User, Depends(require_permission(USERS_MANAGE))]


async def find_conflict(
    session: AsyncSession,
    user: UserSchema | UserUpdate,
    *,
    exclude_user_id: UUID | None = None,
):
    for column, value, message in (
        (User.username, user.username, 'Username already exists'),
        (User.email, user.email, 'Email already exists'),
    ):
        if value is None:
            continue
        predicates = [
            func.lower(column) == func.lower(value),
            User.deleted_at.is_(None),
        ]
        if exclude_user_id is not None:
            predicates.append(User.id != exclude_user_id)
        if await session.scalar(select(User.id).where(*predicates)):
            return message
    return None


async def prepare_user_changes(payload: UserUpdate) -> dict[str, str]:
    changes = payload.model_dump(exclude_unset=True)
    password = changes.pop('password', None)
    if password is not None:
        changes['password_hash'] = await run_in_threadpool(
            hash_password, password
        )
    return changes


async def persist_user(
    session: AsyncSession, user: UserSchema, password_hash: str
) -> User:
    db_user = User(
        email=user.email,
        username=user.username,
        password_hash=password_hash,
        full_name=user.full_name,
    )
    session.add(db_user)
    await session.flush()
    await session.refresh(db_user)
    await session.commit()
    return db_user


@router.get(
    '',
    operation_id='listUsers',
    response_model=AdminUserPage,
    openapi_extra={'x-required-permission': USERS_READ},
    responses={
        HTTPStatus.UNAUTHORIZED: {
            'description': (
                'Sessão ausente, inválida, vencida ou ligada a conta inativa.'
            ),
        },
        HTTPStatus.FORBIDDEN: {
            'description': (
                'A conta não possui users.read. A resposta não contém '
                'itens, contagem ou indicação de correspondência.'
            ),
        },
    },
)
async def list_users(  # noqa: PLR0913, PLR0917
    session: Session,
    actor: UserListingReader,
    search: Annotated[str | None, Query()] = None,
    active: Annotated[bool, Query()] = True,
    profile_id: Annotated[UUID | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    del actor
    predicates = [
        User.deleted_at.is_(None) if active else User.deleted_at.is_not(None)
    ]
    search_term = search.strip() if search is not None else ''
    if search_term:
        predicates.append(
            or_(
                User.username.icontains(search_term, autoescape=True),
                User.email.icontains(search_term, autoescape=True),
            )
        )
    if profile_id is not None:
        predicates.append(
            select(UserAccessProfile.id)
            .join(
                AccessProfile,
                AccessProfile.id == UserAccessProfile.profile_id,
            )
            .where(
                UserAccessProfile.user_id == User.id,
                UserAccessProfile.profile_id == profile_id,
                UserAccessProfile.deleted_at.is_(None),
                AccessProfile.deleted_at.is_(None),
            )
            .exists()
        )
    users = list(
        await session.scalars(
            select(User)
            .where(*predicates)
            .order_by(func.lower(User.username).asc(), User.id.asc())
            .offset(offset)
            .limit(limit)
            # `active=false` lista contas inativas por desenho; ignora o
            # filtro global de soft-delete (Spec 022), que do contrário
            # esconderia essas mesmas contas por padrão.
            .execution_options(skip_soft_delete_filter=True)
        )
    )
    profiles_by_user = await active_profiles_for_users(
        session, [user.id for user in users]
    )
    return AdminUserPage(
        offset=offset,
        limit=limit,
        items=[
            AdminUser(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                active=user.deleted_at is None,
                profiles=[
                    ProfileSummary(
                        id=profile.id, name=profile.name, active=True
                    )
                    for profile in profiles_by_user.get(user.id, [])
                ],
            )
            for user in users
        ],
    )


@router.post('', status_code=HTTPStatus.CREATED, response_model=UserPublic)
async def create_user(user: UserSchema, session: Session):
    conflict = await find_conflict(session, user)
    if conflict:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=conflict,
        )

    try:
        password_hash = await run_in_threadpool(hash_password, user.password)
        db_user = await persist_user(session, user, password_hash)
    except IntegrityError:
        await session.rollback()
        conflict = await find_conflict(session, user)
        if conflict:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=conflict,
            ) from None
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        ) from None

    return db_user


@router.patch(
    '/{user_id}',
    operation_id='updateUser',
    response_model=UserPublic,
    openapi_extra={'x-required-permission': USERS_MANAGE},
    responses={
        HTTPStatus.UNAUTHORIZED: {
            'description': (
                'Sessão ausente, inválida, vencida ou ligada a conta inativa.'
            ),
        },
        HTTPStatus.FORBIDDEN: {
            'description': (
                'A conta não possui users.manage ou a origem não é confiável.'
            ),
        },
        HTTPStatus.NOT_FOUND: {
            'description': 'O UUID não identifica uma conta existente.',
        },
        HTTPStatus.CONFLICT: {
            'description': 'Username ou e-mail já pertence a uma conta ativa.',
        },
    },
)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    session: Session,
    actor: UserManager,
    _: TrustedOrigin,
):
    item = await session.get(User, user_id)
    if item is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='User not found'
        )
    conflict = await find_conflict(session, payload, exclude_user_id=item.id)
    if conflict:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=conflict,
        )

    try:
        changes = await prepare_user_changes(payload)
        for field, value in changes.items():
            setattr(item, field, value)
        item.set_update_audit(actor.id)
        await session.commit()
        await session.refresh(item)
    except IntegrityError:
        await session.rollback()
        conflict = await find_conflict(
            session, payload, exclude_user_id=item.id
        )
        if conflict:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=conflict,
            ) from None
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        ) from None

    return item
