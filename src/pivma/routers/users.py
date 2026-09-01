from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import USERS_READ
from pivma.core.database import get_session
from pivma.core.database.models import AccessProfile, User, UserAccessProfile
from pivma.core.security import hash_password
from pivma.dependencies import require_permission
from pivma.schemas import (
    AdminUser,
    AdminUserPage,
    UserPublic,
    UserSchema,
)

router = APIRouter(prefix='/users', tags=['users'])
Session = Annotated[AsyncSession, Depends(get_session)]
UserListingReader = Annotated[User, Depends(require_permission(USERS_READ))]


async def find_conflict(session: AsyncSession, user: UserSchema):
    username_exists = await session.scalar(
        select(User.id).where(
            func.lower(User.username) == func.lower(user.username),
            User.deleted_at.is_(None),
        )
    )
    if username_exists:
        return 'Username already exists'

    email_exists = await session.scalar(
        select(User.id).where(
            func.lower(User.email) == func.lower(user.email),
            User.deleted_at.is_(None),
        )
    )
    if email_exists:
        return 'Email already exists'
    return None


async def persist_user(
    session: AsyncSession, user: UserSchema, password_hash: str
) -> User:
    db_user = User(
        email=user.email,
        username=user.username,
        password_hash=password_hash,
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
        )
    )
    return AdminUserPage(
        offset=offset,
        limit=limit,
        items=[
            AdminUser(
                id=user.id,
                username=user.username,
                email=user.email,
                active=user.deleted_at is None,
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
