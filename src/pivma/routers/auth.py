from http import HTTPStatus
from typing import Annotated

import jwt
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database import get_session
from pivma.core.database.models import User
from pivma.core.security import (
    ACCESS_TOKEN_TTL,
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    verify_password,
)
from pivma.core.settings import Settings, get_settings
from pivma.schemas import LoginCredentials, UserIdentity

router = APIRouter(prefix='/auth', tags=['auth'])
Session = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail='Not authenticated',
    )


async def find_active_user(
    session: AsyncSession,
    identifier: str,
) -> User | None:
    return await session.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == func.lower(identifier),
                func.lower(User.email) == func.lower(identifier),
            ),
            User.deleted_at.is_(None),
        )
    )


async def get_current_user(
    session: Session,
    settings: SettingsDependency,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    if access_token is None:
        raise not_authenticated()

    try:
        user_id = decode_access_token(
            access_token,
            settings.JWT_SECRET_KEY,
        )
    except jwt.InvalidTokenError:
        raise not_authenticated() from None

    user = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        raise not_authenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    '/login',
    status_code=HTTPStatus.OK,
    response_class=Response,
)
async def login(
    credentials: LoginCredentials,
    response: Response,
    session: Session,
    settings: SettingsDependency,
):
    user = await find_active_user(session, credentials.identifier)
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_is_valid = await run_in_threadpool(
        verify_password,
        password_hash,
        credentials.password,
    )
    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Invalid credentials',
        )

    token = create_access_token(user.id, settings.JWT_SECRET_KEY)
    response.set_cookie(
        key='access_token',
        value=token,
        max_age=int(ACCESS_TOKEN_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite='strict',
        path='/',
    )


@router.get('/me', response_model=UserIdentity)
async def read_current_user(current_user: CurrentUser):
    return current_user


@router.post('/logout', status_code=HTTPStatus.NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    settings: SettingsDependency,
):
    del current_user
    if request.headers.get('Origin') not in settings.AUTH_ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Invalid origin',
        )
    response.delete_cookie(
        key='access_token',
        path='/',
        httponly=True,
        secure=True,
        samesite='strict',
    )
