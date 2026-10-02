from http import HTTPStatus

from fastapi import (
    APIRouter,
    Response,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    active_profiles_for_user,
    compute_effectiveness_map,
    effective_permission_codes,
)
from pivma.core.database.models import (
    Assignment,
    Laboratory,
    ProcessInstance,
    User,
)
from pivma.core.errors import api_error
from pivma.core.password_reset_service import (
    NEUTRAL_MESSAGE,
    request_password_reset,
    reset_password,
)
from pivma.core.security import (
    ACCESS_TOKEN_TTL,
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    SettingsDependency,
    TrustedOrigin,
)
from pivma.schemas import (
    AccessScope,
    CurrentUserAccess,
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginCredentials,
    LoginResponse,
    ProfileRef,
    ResetPasswordRequest,
    SelfUserUpdate,
    UserIdentity,
    UserPublic,
)

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
    response_model=LoginResponse,
    responses={
        HTTPStatus.OK: {
            'headers': {
                'Set-Cookie': {
                    'description': (
                        'Cookie access_token com HttpOnly, Secure, '
                        'SameSite=Strict, Path=/ e Max-Age igual a expires_in.'
                    ),
                    'schema': {'type': 'string'},
                },
                'Cache-Control': {
                    'description': 'Impede o armazenamento do token em cache.',
                    'schema': {'type': 'string', 'const': 'no-store'},
                },
            }
        }
    },
)
async def login(
    credentials: LoginCredentials,
    response: Response,
    session: Session,
    settings: SettingsDependency,
) -> LoginResponse:
    user = await find_active_user(session, credentials.identifier)
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_is_valid = await run_in_threadpool(
        verify_password,
        password_hash,
        credentials.password,
    )
    if user is None or not password_is_valid:
        raise api_error(
            HTTPStatus.UNAUTHORIZED,
            'invalid_credentials',
            'Usuário ou senha inválidos.',
        )

    token = create_access_token(user.id, settings.JWT_SECRET_KEY)
    expires_in = int(ACCESS_TOKEN_TTL.total_seconds())
    response.set_cookie(
        key='access_token',
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=True,
        samesite='strict',
        path='/',
    )
    response.headers['Cache-Control'] = 'no-store'
    return LoginResponse(
        access_token=token, token_type='bearer', expires_in=expires_in
    )


@router.get('/me', response_model=CurrentUserResponse)
async def read_current_user(
    current_user: CurrentUser,
    session: Session,
):
    assignments = list(
        await session.scalars(
            select(Assignment)
            .join(
                ProcessInstance,
                ProcessInstance.id == Assignment.process_instance_id,
            )
            .where(
                Assignment.user_id == current_user.id,
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
                ProcessInstance.deleted_at.is_(None),
            )
        )
    )
    effectiveness = await compute_effectiveness_map(session, assignments)
    laboratories = {}
    laboratory_ids = {
        assignment.laboratory_id
        for assignment in assignments
        if assignment.laboratory_id is not None
    }
    if laboratory_ids:
        laboratories = {
            laboratory.id: laboratory.institution_id
            for laboratory in await session.scalars(
                select(Laboratory).where(Laboratory.id.in_(laboratory_ids))
            )
        }

    grouped_scopes = {}
    for assignment in assignments:
        if not effectiveness.get(assignment.id, False):
            continue
        institution_id = (
            laboratories.get(assignment.laboratory_id)
            if assignment.laboratory_id is not None
            else None
        )
        key = (
            assignment.process_instance_id,
            institution_id,
            assignment.laboratory_id,
        )
        grouped_scopes.setdefault(key, set()).add(assignment.role_key)

    scopes = [
        AccessScope(
            process_id=process_id,
            institution_id=institution_id,
            laboratory_id=laboratory_id,
            roles=sorted(roles),
        )
        for (
            process_id,
            institution_id,
            laboratory_id,
        ), roles in sorted(grouped_scopes.items(), key=lambda item: item[0])
    ]
    profiles = await active_profiles_for_user(session, current_user.id)
    identity = UserIdentity.model_validate(current_user)
    return CurrentUserResponse(
        user=identity,
        access=CurrentUserAccess(
            profiles=[
                ProfileRef(id=profile.id, name=profile.name, active=True)
                for profile in profiles
            ],
            global_permissions=await effective_permission_codes(
                session, current_user.id
            ),
            scopes=scopes,
        ),
    )


@router.patch(
    '/me',
    operation_id='updateCurrentUser',
    response_model=UserPublic,
    responses={
        HTTPStatus.BAD_REQUEST: {
            'description': 'Senha atual incorreta. Nenhum campo é alterado.',
        },
        HTTPStatus.UNAUTHORIZED: {
            'description': (
                'Sessão ausente, inválida, vencida ou ligada a conta inativa.'
            ),
        },
        HTTPStatus.FORBIDDEN: {
            'description': 'A origem da requisição não é confiável.',
        },
    },
)
async def update_current_user(
    payload: SelfUserUpdate,
    current_user: CurrentUser,
    session: Session,
    _: TrustedOrigin,
):
    if payload.new_password is not None:
        password_is_valid = await run_in_threadpool(
            verify_password,
            current_user.password_hash,
            payload.current_password,
        )
        if not password_is_valid:
            raise api_error(
                HTTPStatus.BAD_REQUEST,
                'invalid_current_password',
                'Senha atual incorreta.',
            )
        current_user.password_hash = await run_in_threadpool(
            hash_password, payload.new_password
        )
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    current_user.set_update_audit(current_user.id)
    await session.commit()
    await session.refresh(current_user)
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


@router.post(
    '/forgot-password',
    status_code=HTTPStatus.OK,
    response_model=ForgotPasswordResponse,
    operation_id='forgotPassword',
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: Session,
    settings: SettingsDependency,
) -> ForgotPasswordResponse:
    await request_password_reset(session, settings, payload.email)
    await session.commit()
    return ForgotPasswordResponse(message=NEUTRAL_MESSAGE)


@router.post(
    '/reset-password',
    status_code=HTTPStatus.NO_CONTENT,
    operation_id='resetPassword',
    responses={
        HTTPStatus.BAD_REQUEST: {
            'description': (
                'Token inválido, expirado, usado, substituído ou de conta '
                'inativa.'
            ),
        },
    },
)
async def reset_password_with_token(
    payload: ResetPasswordRequest,
    session: Session,
) -> None:
    # O hash vem antes da validação do token: a transação com o bloqueio
    # fica curta e o tempo não distingue token válido de recusado.
    new_password_hash = await run_in_threadpool(
        hash_password, payload.new_password
    )
    if not await reset_password(session, payload.token, new_password_hash):
        raise api_error(
            HTTPStatus.BAD_REQUEST,
            'invalid_reset_token',
            'Link de redefinição inválido ou expirado.',
        )
    await session.commit()
