import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.authorization import (
    RBAC_ASSIGNMENTS_MANAGE,
    RBAC_PROFILES_MANAGE,
    RBAC_READ,
)
from pivma.core.database import get_session
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    RbacChange,
    User,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings


@dataclass
class ConcurrentScenario:
    actor_id: UUID
    user_ids: set[UUID]
    profile_ids: set[UUID]
    permission_ids: set[UUID]


def new_user(label: str) -> User:
    suffix = uuid4().hex
    return User(
        username=f'{label}-{suffix}',
        email=f'{label}-{suffix}@test.com',
        password_hash='unused-in-token-authentication',
    )


async def authorize_actor(
    session: AsyncSession, permission_codes: set[str]
) -> tuple[User, AccessProfile, list[Permission]]:
    actor = new_user('concurrent-actor')
    actor_profile = AccessProfile(
        system_key=None,
        name=f'Concurrent actor {uuid4().hex}',
        description='Authorizes one concurrency scenario',
    )
    permissions = [
        Permission(code=code, description=code) for code in permission_codes
    ]
    session.add_all([actor, actor_profile, *permissions])
    await session.flush()
    session.add_all([
        *[
            AccessProfilePermission(
                profile_id=actor_profile.id,
                permission_id=permission.id,
            )
            for permission in permissions
        ],
        UserAccessProfile(user_id=actor.id, profile_id=actor_profile.id),
    ])
    return actor, actor_profile, permissions


async def cleanup_scenario(engine, scenario: ConcurrentScenario) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            delete(RbacChange).where(
                or_(
                    RbacChange.created_by.in_(scenario.user_ids),
                    RbacChange.target_id.in_(scenario.profile_ids),
                )
            )
        )
        await session.execute(
            delete(UserAccessProfile).where(
                or_(
                    UserAccessProfile.user_id.in_(scenario.user_ids),
                    UserAccessProfile.profile_id.in_(scenario.profile_ids),
                )
            )
        )
        await session.execute(
            delete(AccessProfilePermission).where(
                AccessProfilePermission.profile_id.in_(scenario.profile_ids)
            )
        )
        await session.execute(
            delete(AccessProfile).where(
                AccessProfile.id.in_(scenario.profile_ids)
            )
        )
        await session.execute(
            delete(Permission).where(
                Permission.id.in_(scenario.permission_ids)
            )
        )
        await session.execute(
            delete(User).where(User.id.in_(scenario.user_ids))
        )
        await session.commit()


def run_concurrently(client: TestClient, requests):
    barrier = Barrier(2)

    def run(request):
        barrier.wait()
        return request(client)

    with ThreadPoolExecutor(2) as executor:
        return list(executor.map(run, requests))


def test_concurrent_equivalent_profile_names_create_one_active_profile(engine):
    profile_name = f'Concurrent profile {uuid4().hex}'

    async def setup():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            actor, actor_profile, permissions = await authorize_actor(
                session, {RBAC_PROFILES_MANAGE}
            )
            await session.commit()
            return ConcurrentScenario(
                actor_id=actor.id,
                user_ids={actor.id},
                profile_ids={actor_profile.id},
                permission_ids={item.id for item in permissions},
            )

    scenario = asyncio.run(setup())

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    headers = {
        'Cookie': 'access_token='
        + create_access_token(scenario.actor_id, Settings().JWT_SECRET_KEY),
        'Origin': 'https://testserver',
    }
    payloads = (
        {'name': profile_name, 'description': 'First equivalent name'},
        {
            'name': profile_name.swapcase(),
            'description': 'Second equivalent name',
        },
    )
    app.dependency_overrides[get_session] = independent_session
    try:
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                tuple(
                    lambda active_client, payload=payload: active_client.post(
                        '/rbac/profiles', json=payload, headers=headers
                    )
                    for payload in payloads
                ),
            )

        assert sorted(response.status_code for response in responses) == [
            HTTPStatus.CREATED,
            HTTPStatus.CONFLICT,
        ]

        async def count_active_profiles():
            async with AsyncSession(engine) as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(AccessProfile)
                    .where(
                        func.lower(AccessProfile.name) == profile_name.lower(),
                        AccessProfile.deleted_at.is_(None),
                    )
                )

        assert asyncio.run(count_active_profiles()) == 1
    finally:
        app.dependency_overrides.clear()

        async def include_created_profile():
            async with AsyncSession(engine) as session:
                created_ids = set(
                    await session.scalars(
                        select(AccessProfile.id).where(
                            func.lower(AccessProfile.name)
                            == profile_name.lower()
                        )
                    )
                )
            scenario.profile_ids.update(created_ids)

        asyncio.run(include_created_profile())
        asyncio.run(cleanup_scenario(engine, scenario))


def test_concurrent_duplicate_assignment_creates_one_active_link(engine):
    async def setup():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            actor, actor_profile, permissions = await authorize_actor(
                session, {RBAC_ASSIGNMENTS_MANAGE}
            )
            target_user = new_user('concurrent-target')
            target_profile = AccessProfile(
                system_key=None,
                name=f'Concurrent assignment {uuid4().hex}',
                description='Target of concurrent assignments',
            )
            session.add_all([target_user, target_profile])
            await session.commit()
            return (
                ConcurrentScenario(
                    actor_id=actor.id,
                    user_ids={actor.id, target_user.id},
                    profile_ids={actor_profile.id, target_profile.id},
                    permission_ids={item.id for item in permissions},
                ),
                target_user.id,
                target_profile.id,
            )

    scenario, target_user_id, target_profile_id = asyncio.run(setup())

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    headers = {
        'Cookie': 'access_token='
        + create_access_token(scenario.actor_id, Settings().JWT_SECRET_KEY),
        'Origin': 'https://testserver',
    }
    path = f'/rbac/users/{target_user_id}/profiles/{target_profile_id}'
    app.dependency_overrides[get_session] = independent_session
    try:
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                (
                    lambda active_client: active_client.post(
                        path, headers=headers
                    ),
                    lambda active_client: active_client.post(
                        path, headers=headers
                    ),
                ),
            )

        assert sorted(response.status_code for response in responses) == [
            HTTPStatus.CREATED,
            HTTPStatus.CONFLICT,
        ]

        async def count_active_assignments():
            async with AsyncSession(engine) as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(UserAccessProfile)
                    .where(
                        UserAccessProfile.user_id == target_user_id,
                        UserAccessProfile.profile_id == target_profile_id,
                        UserAccessProfile.deleted_at.is_(None),
                    )
                )

        assert asyncio.run(count_active_assignments()) == 1
    finally:
        app.dependency_overrides.clear()
        asyncio.run(cleanup_scenario(engine, scenario))


def test_concurrent_revocations_preserve_one_effective_administrator(engine):
    async def setup():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            actor, actor_profile, permissions = await authorize_actor(
                session, {RBAC_ASSIGNMENTS_MANAGE}
            )
            administrator = AccessProfile(
                system_key='administrator',
                name=f'Administrator {uuid4().hex}',
                description='Protected administrator profile',
            )
            administrators = [
                new_user(f'administrator-{index}') for index in range(2)
            ]
            administrative_permissions = [
                Permission(code=code, description=code)
                for code in {RBAC_READ, RBAC_PROFILES_MANAGE}
            ]
            session.add_all([
                administrator,
                *administrators,
                *administrative_permissions,
            ])
            await session.flush()
            session.add_all([
                *[
                    AccessProfilePermission(
                        profile_id=administrator.id,
                        permission_id=permission.id,
                    )
                    for permission in [
                        *permissions,
                        *administrative_permissions,
                    ]
                ],
                *[
                    UserAccessProfile(
                        user_id=user.id,
                        profile_id=administrator.id,
                    )
                    for user in administrators
                ],
            ])
            await session.commit()
            return (
                ConcurrentScenario(
                    actor_id=actor.id,
                    user_ids={actor.id, *(user.id for user in administrators)},
                    profile_ids={actor_profile.id, administrator.id},
                    permission_ids={
                        *(item.id for item in permissions),
                        *(item.id for item in administrative_permissions),
                    },
                ),
                administrator.id,
                [user.id for user in administrators],
            )

    scenario, administrator_id, administrator_ids = asyncio.run(setup())

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    headers = {
        'Cookie': 'access_token='
        + create_access_token(scenario.actor_id, Settings().JWT_SECRET_KEY),
        'Origin': 'https://testserver',
    }
    app.dependency_overrides[get_session] = independent_session
    try:
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                tuple(
                    lambda active_client, user_id=user_id: (
                        active_client.delete(
                            f'/rbac/users/{user_id}/profiles/{administrator_id}',
                            headers=headers,
                        )
                    )
                    for user_id in administrator_ids
                ),
            )

        assert sorted(response.status_code for response in responses) == [
            HTTPStatus.NO_CONTENT,
            HTTPStatus.CONFLICT,
        ]

        async def count_active_administrators():
            async with AsyncSession(engine) as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(UserAccessProfile)
                    .where(
                        UserAccessProfile.user_id.in_(administrator_ids),
                        UserAccessProfile.profile_id == administrator_id,
                        UserAccessProfile.deleted_at.is_(None),
                    )
                )

        assert asyncio.run(count_active_administrators()) == 1
    finally:
        app.dependency_overrides.clear()
        asyncio.run(cleanup_scenario(engine, scenario))
