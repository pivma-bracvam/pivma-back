from http import HTTPStatus

from fastapi import (
    APIRouter,
    HTTPException,
    Response,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import User
from pivma.core.security import (
    ACCESS_TOKEN_TTL,
    DUMMY_PASSWORD_HASH,
    create_access_token,
    verify_password,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    SettingsDependency,
    TrustedOrigin,
)
from pivma.schemas import LoginCredentials, UserIdentity

router = APIRouter(prefix='/auth', tags=['auth'])


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
    response: Response,
    current_user: CurrentUser,
    origin: TrustedOrigin,
):
    del current_user, origin
    response.delete_cookie(
        key='access_token',
        path='/',
        httponly=True,
        secure=True,
        samesite='strict',
    )
