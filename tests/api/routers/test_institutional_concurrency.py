import asyncio
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
)
from pivma.core.database import get_session
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Institution,
    InstitutionalChange,
    Permission,
    User,
    UserAccessProfile,
    UserInstitutionalAffiliation,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings


def run_concurrently(client: TestClient, requests):
    barrier = Barrier(2)

    def run(request):
        barrier.wait()
        return request(client)

    with ThreadPoolExecutor(2) as executor:
        return list(executor.map(run, requests))


async def setup_actor(engine, permission_code: str) -> tuple[UUID, UUID, UUID]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        suffix = uuid4().hex
        actor = User(
            username=f'institutional-actor-{suffix}',
            email=f'institutional-actor-{suffix}@test.com',
            password_hash='unused',
            full_name=f'Institutional Actor {suffix}',
        )
        permission = Permission(
            code=permission_code,
            description='Concurrent catalog management',
        )
        profile = AccessProfile(name=f'Institutional {suffix}', description='')
        session.add_all([actor, permission, profile])
        await session.flush()
        session.add_all([
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            ),
            UserAccessProfile(user_id=actor.id, profile_id=profile.id),
        ])
        await session.commit()
        return actor.id, profile.id, permission.id


async def cleanup(
    engine,
    actor_id: UUID,
    profile_id: UUID,
    permission_id: UUID,
    target: tuple[UUID, UUID] | None = None,
):
    target_user_id = target[0] if target is not None else None
    institution_id = target[1] if target is not None else None
    async with AsyncSession(engine) as session:
        await session.execute(
            delete(InstitutionalChange).where(
                InstitutionalChange.created_by == actor_id
            )
        )
        await session.execute(
            delete(UserInstitutionalAffiliation).where(
                UserInstitutionalAffiliation.user_id.in_(
                    [actor_id, target_user_id]
                    if target_user_id is not None
                    else [actor_id]
                )
            )
        )
        if institution_id is not None:
            await session.execute(
                delete(Institution).where(Institution.id == institution_id)
            )
        await session.execute(
            delete(Institution).where(Institution.created_by == actor_id)
        )
        await session.execute(
            delete(UserAccessProfile).where(
                UserAccessProfile.user_id == actor_id
            )
        )
        await session.execute(
            delete(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == profile_id
            )
        )
        await session.execute(
            delete(AccessProfile).where(AccessProfile.id == profile_id)
        )
        await session.execute(
            delete(Permission).where(Permission.id == permission_id)
        )
        await session.execute(
            delete(User).where(
                User.id.in_(
                    [actor_id, target_user_id]
                    if target_user_id is not None
                    else [actor_id]
                )
            )
        )
        await session.commit()


def test_concurrent_equivalent_institution_names_create_one_active_record(
    engine,
):
    actor_id, profile_id, permission_id = asyncio.run(
        setup_actor(engine, INSTITUTIONAL_CATALOGS_MANAGE)
    )
    name = f'Institution {uuid4().hex}'

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = independent_session
    try:
        headers = {
            'Cookie': 'access_token='
            + create_access_token(actor_id, Settings().JWT_SECRET_KEY),
            'Origin': 'https://testserver',
        }
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                (
                    lambda current: current.post(
                        '/institutional/institutions',
                        headers=headers,
                        json={'name': name},
                    ),
                    lambda current: current.post(
                        '/institutional/institutions',
                        headers=headers,
                        json={'name': name.swapcase()},
                    ),
                ),
            )
        assert sorted(item.status_code for item in responses) == [
            HTTPStatus.CREATED,
            HTTPStatus.CONFLICT,
        ]

        async def count_active():
            async with AsyncSession(engine) as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(Institution)
                    .where(
                        func.lower(Institution.name) == name.lower(),
                        Institution.deleted_at.is_(None),
                    )
                )

        assert asyncio.run(count_active()) == 1
    finally:
        app.dependency_overrides.clear()
        asyncio.run(cleanup(engine, actor_id, profile_id, permission_id))


def test_concurrent_equivalent_affiliations_create_one_active_record(engine):
    actor_id, profile_id, permission_id = asyncio.run(
        setup_actor(engine, INSTITUTIONAL_AFFILIATIONS_MANAGE)
    )

    async def setup_target():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            suffix = uuid4().hex
            target = User(
                username=f'institutional-target-{suffix}',
                email=f'institutional-target-{suffix}@test.com',
                password_hash='unused',
                full_name=f'Institutional Target {suffix}',
            )
            institution = Institution(name=f'Institution {suffix}')
            session.add_all([target, institution])
            await session.commit()
            return target.id, institution.id

    target_id, institution_id = asyncio.run(setup_target())

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = independent_session
    try:
        headers = {
            'Cookie': 'access_token='
            + create_access_token(actor_id, Settings().JWT_SECRET_KEY),
            'Origin': 'https://testserver',
        }
        path = f'/institutional/users/{target_id}/affiliations'
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                (
                    lambda current: current.post(
                        path,
                        headers=headers,
                        json={'institution_id': str(institution_id)},
                    ),
                    lambda current: current.post(
                        path,
                        headers=headers,
                        json={'institution_id': str(institution_id)},
                    ),
                ),
            )
        assert sorted(item.status_code for item in responses) == [
            HTTPStatus.CREATED,
            HTTPStatus.CONFLICT,
        ]
    finally:
        app.dependency_overrides.clear()
        asyncio.run(
            cleanup(
                engine,
                actor_id,
                profile_id,
                permission_id,
                (target_id, institution_id),
            )
        )
