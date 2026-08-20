"""Assign the seeded Administrator profile to one existing active account."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY
from pivma.core.database.models import (
    AccessProfile,
    RbacChange,
    User,
    UserAccessProfile,
)
from pivma.core.settings import Settings


async def bootstrap_administrator(
    session: AsyncSession, user_id: UUID
) -> None:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user is None:
        raise ValueError('Active user not found')
    profile = await session.scalar(
        select(AccessProfile)
        .where(
            AccessProfile.system_key == ADMINISTRATOR_SYSTEM_KEY,
            AccessProfile.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if profile is None:
        raise ValueError(
            'Administrator profile not found; run migrations first'
        )
    existing = await session.scalar(
        select(UserAccessProfile).where(
            UserAccessProfile.profile_id == profile.id,
            UserAccessProfile.deleted_at.is_(None),
        )
    )
    if existing is not None:
        if existing.user_id == user_id:
            return
        raise ValueError('Another account already has Administrator')
    assignment = UserAccessProfile(user_id=user_id, profile_id=profile.id)
    session.add(assignment)
    await session.flush()
    session.add(
        RbacChange(
            action='bootstrap.admin_assigned',
            target_type='assignment',
            target_id=assignment.id,
        )
    )


async def _run(user_id: UUID) -> None:
    engine = create_async_engine(Settings().DATABASE_URL)
    try:
        async with AsyncSession(engine) as session:
            try:
                async with session.begin():
                    await bootstrap_administrator(session, user_id)
            except ValueError:
                raise
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id', required=True, type=UUID)
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.user_id))
    except ValueError as exc:
        parser.exit(1, f'RBAC bootstrap failed: {exc}\n')


if __name__ == '__main__':  # pragma: no cover
    main()
