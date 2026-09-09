"""Utilitários comuns e helpers assíncronos para scripts de carga."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY
from pivma.core.database.models import (
    AccessProfile,
    RbacChange,
    User,
    UserAccessProfile,
)
from pivma.core.security import hash_password
from pivma.core.settings import Settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(Settings().DATABASE_URL)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def get_or_create_user(
    session: AsyncSession,
    username: str,
    email: str,
    full_name: str,
    password: str,
) -> tuple[User, bool]:
    """Obtém ou cria um usuário de teste de forma idempotente."""
    stmt = select(User).where(
        func.lower(User.username) == username.lower(),
        User.deleted_at.is_(None),
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user, False

    pwd_hash = hash_password(password)
    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        password_hash=pwd_hash,
    )
    session.add(new_user)
    await session.flush()
    return new_user, True


async def ensure_admin_profile(
    session: AsyncSession, user_id: UUID
) -> UserAccessProfile | None:
    """Garante que o usuário informado possua o perfil Administrador."""
    profile_stmt = select(AccessProfile).where(
        AccessProfile.system_key == ADMINISTRATOR_SYSTEM_KEY,
        AccessProfile.deleted_at.is_(None),
    )
    profile = (await session.execute(profile_stmt)).scalar_one_or_none()
    if profile is None:
        return None

    assign_stmt = select(UserAccessProfile).where(
        UserAccessProfile.user_id == user_id,
        UserAccessProfile.profile_id == profile.id,
        UserAccessProfile.deleted_at.is_(None),
    )
    assignment = (await session.execute(assign_stmt)).scalar_one_or_none()
    if assignment is not None:
        return assignment

    new_assign = UserAccessProfile(user_id=user_id, profile_id=profile.id)
    new_assign.set_creation_audit(user_id)
    session.add(new_assign)
    await session.flush()

    change = RbacChange(
        action='bootstrap.admin_assigned',
        target_type='assignment',
        target_id=new_assign.id,
    )
    change.set_creation_audit(user_id)
    session.add(change)
    return new_assign


async def ensure_profile_by_name(
    session: AsyncSession, user_id: UUID, profile_name: str
) -> UserAccessProfile | None:
    """Associa um usuário a um perfil existente pelo nome."""
    profile_stmt = select(AccessProfile).where(
        func.lower(AccessProfile.name) == profile_name.lower(),
        AccessProfile.deleted_at.is_(None),
    )
    profile = (await session.execute(profile_stmt)).scalar_one_or_none()
    if profile is None:
        return None

    assign_stmt = select(UserAccessProfile).where(
        UserAccessProfile.user_id == user_id,
        UserAccessProfile.profile_id == profile.id,
        UserAccessProfile.deleted_at.is_(None),
    )
    assignment = (await session.execute(assign_stmt)).scalar_one_or_none()
    if assignment is not None:
        return assignment

    new_assign = UserAccessProfile(user_id=user_id, profile_id=profile.id)
    new_assign.set_creation_audit(user_id)
    session.add(new_assign)
    await session.flush()
    return new_assign
