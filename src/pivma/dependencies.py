import logging
from http import HTTPStatus
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import (
    APIKeyCookie,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.ai.provider import ModelProvider
from pivma.ai.provider import get_model_provider as _build_model_provider
from pivma.core.authorization import has_permission
from pivma.core.database import get_session
from pivma.core.database.models import User
from pivma.core.errors import api_error
from pivma.core.security import decode_access_token
from pivma.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)
Session = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_model_provider(settings: SettingsDependency) -> ModelProvider:
    return _build_model_provider(settings)


ModelProviderDep = Annotated[ModelProvider, Depends(get_model_provider)]
access_token_cookie = APIKeyCookie(
    name='access_token',
    auto_error=False,
)
bearer_token = HTTPBearer(auto_error=False)


def not_authenticated() -> HTTPException:
    return api_error(
        HTTPStatus.UNAUTHORIZED,
        'not_authenticated',
        'Sessão ausente ou expirada.',
    )


async def get_current_user(
    request: Request,
    session: Session,
    settings: SettingsDependency,
    access_token: Annotated[str | None, Security(access_token_cookie)],
    bearer: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_token)
    ],
) -> User:
    if access_token is None:
        if bearer is not None:
            access_token = bearer.credentials
        elif 'token' in request.query_params:
            access_token = request.query_params['token']

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
    request: Request,
    settings: SettingsDependency,
    access_token: Annotated[str | None, Security(access_token_cookie)],
    bearer: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_token)
    ],
) -> None:
    # CSRF depende de credencial anexada pelo navegador, e só o cookie é.
    if access_token is None and bearer is not None:
        return
    if request.headers.get('Origin') not in settings.AUTH_ALLOWED_ORIGINS:
        raise api_error(
            HTTPStatus.FORBIDDEN,
            'invalid_origin',
            'Origem da requisição não confiável.',
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
            raise api_error(
                HTTPStatus.FORBIDDEN,
                'forbidden',
                'Sem permissão para esta ação.',
            )
        return user

    return dependency


async def require_admin(
    request: Request,
    session: Session,
    user: CurrentUser,
) -> User:
    from pivma.core.authorization import (  # noqa: PLC0415
        ADMINISTRATOR_SYSTEM_KEY,
        active_profiles_for_user,
    )

    profiles = await active_profiles_for_user(session, user.id)
    if any(p.system_key == ADMINISTRATOR_SYSTEM_KEY for p in profiles):
        return user
    raise api_error(
        HTTPStatus.FORBIDDEN,
        'admin_only',
        'Acesso restrito a administradores.',
    )


AdminUser = Annotated[User, Depends(require_admin)]
