import logging
from http import HTTPStatus
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import has_permission
from pivma.core.database import get_session
from pivma.core.database.models import User
from pivma.core.security import decode_access_token
from pivma.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)
Session = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED, detail='Not authenticated'
    )


async def get_current_user(
    session: Session,
    settings: SettingsDependency,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User:
    if access_token is None:
        raise not_authenticated()
    try:
        user_id = decode_access_token(access_token, settings.JWT_SECRET_KEY)
    except jwt.InvalidTokenError:
        raise not_authenticated() from None
    user = await session.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user is None:
        raise not_authenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_trusted_origin(
    request: Request, settings: SettingsDependency
) -> None:
    if request.headers.get('Origin') not in settings.AUTH_ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Invalid origin'
        )


TrustedOrigin = Annotated[None, Depends(require_trusted_origin)]


def require_permission(code: str):
    async def dependency(
        request: Request, session: Session, user: CurrentUser
    ) -> User:
        if not await has_permission(session, user.id, code):
            logger.warning(
                'rbac.permission_denied user=%s permission=%s '
                'method=%s path=%s',
                user.id,
                code,
                request.method,
                request.url.path,
            )
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail='Forbidden'
            )
        return user

    return dependency
