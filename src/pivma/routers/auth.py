from http import HTTPStatus

from fastapi import (
    APIRouter,
    HTTPException,
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
from pivma.schemas import (
    AccessScope,
    CurrentUserAccess,
    CurrentUserResponse,
    LoginCredentials,
    ProfileSummary,
    UserIdentity,
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
        **identity.model_dump(),
        user=identity,
        access=CurrentUserAccess(
            profiles=[
                ProfileSummary(id=profile.id, name=profile.name, active=True)
                for profile in profiles
            ],
            global_permissions=await effective_permission_codes(
                session, current_user.id
            ),
            scopes=scopes,
        ),
    )


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
