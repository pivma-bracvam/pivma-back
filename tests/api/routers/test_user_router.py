import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from threading import Barrier
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.authorization import (
    ADMINISTRATIVE_PERMISSIONS,
    USERS_MANAGE,
    USERS_READ,
)
from pivma.core.database import get_session
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    User,
    UserAccessProfile,
)
from pivma.core.security import create_access_token, verify_password
from pivma.core.settings import Settings
from pivma.routers.users import create_user
from pivma.schemas import UserSchema
from tests.factories.user_factory import UserFactory

VALID_PASSWORD = 'Unique-Passphrase-2026'
FACTORY_PASSWORD = 'Factory-Passphrase-2026'
TRUSTED_ORIGIN = {'Origin': 'https://testserver'}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


async def grant_permissions(session, user, codes, *, system_key=None):
    profile = AccessProfile(
        system_key=system_key,
        name=f'User {user.id} access {uuid4().hex[:8]}',
        description='Test access profile',
    )
    permissions = [
        Permission(code=code, description=f'Permission {code}')
        for code in codes
    ]
    session.add_all([profile, *permissions])
    await session.flush()
    session.add_all([
        *[
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
            for permission in permissions
        ],
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()
    return profile


async def read_user_including_inactive(session, user_id: UUID) -> User | None:
    return await session.scalar(
        select(User)
        .where(User.id == user_id)
        .execution_options(skip_soft_delete_filter=True)
    )


@pytest_asyncio.fixture
async def user_manager(session, user):
    await grant_permissions(
        session,
        user,
        ADMINISTRATIVE_PERMISSIONS | {USERS_MANAGE, USERS_READ},
        system_key='administrator',
    )
    return user


@pytest_asyncio.fixture
async def manager_without_administrator(session, user):
    await grant_permissions(session, user, {USERS_MANAGE})
    return user


@pytest_asyncio.fixture
async def last_administrator(session, other_user):
    await grant_permissions(
        session,
        other_user,
        ADMINISTRATIVE_PERMISSIONS,
        system_key='administrator',
    )
    return other_user


@dataclass
class ConcurrentDeactivation:
    actor_id: UUID
    administrator_ids: list[UUID]
    profile_ids: set[UUID]
    permission_ids: set[UUID]


@pytest.fixture
def concurrent_administrators(engine):
    async def setup():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            actor = UserFactory(
                username=f'deactivation-manager-{uuid4().hex}',
                password_hash='unused-in-token-authentication',
            )
            administrators = [
                UserFactory(
                    username=f'deactivation-admin-{index}-{uuid4().hex}',
                    password_hash='unused-in-token-authentication',
                )
                for index in range(2)
            ]
            manager_profile = AccessProfile(
                system_key=None,
                name=f'Deactivation manager {uuid4().hex}',
                description='Authorizes concurrent deactivation tests',
            )
            administrator_profile = AccessProfile(
                system_key='administrator',
                name=f'Administrator {uuid4().hex}',
                description='Protected administrator profile',
            )
            permissions = [
                Permission(code=code, description=code)
                for code in ADMINISTRATIVE_PERMISSIONS | {USERS_MANAGE}
            ]
            session.add_all([
                actor,
                *administrators,
                manager_profile,
                administrator_profile,
                *permissions,
            ])
            await session.flush()
            manager_permission = next(
                item for item in permissions if item.code == USERS_MANAGE
            )
            admin_permissions = [
                item
                for item in permissions
                if item.code in ADMINISTRATIVE_PERMISSIONS
            ]
            session.add_all([
                AccessProfilePermission(
                    profile_id=manager_profile.id,
                    permission_id=manager_permission.id,
                ),
                *[
                    AccessProfilePermission(
                        profile_id=administrator_profile.id,
                        permission_id=permission.id,
                    )
                    for permission in admin_permissions
                ],
                UserAccessProfile(
                    user_id=actor.id, profile_id=manager_profile.id
                ),
                *[
                    UserAccessProfile(
                        user_id=administrator.id,
                        profile_id=administrator_profile.id,
                    )
                    for administrator in administrators
                ],
            ])
            await session.commit()
            return ConcurrentDeactivation(
                actor_id=actor.id,
                administrator_ids=[user.id for user in administrators],
                profile_ids={manager_profile.id, administrator_profile.id},
                permission_ids={permission.id for permission in permissions},
            )

    scenario = asyncio.run(setup())
    yield scenario

    async def cleanup():
        async with AsyncSession(engine) as session:
            await session.execute(
                delete(UserAccessProfile).where(
                    UserAccessProfile.profile_id.in_(scenario.profile_ids)
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
                delete(User).where(
                    User.id.in_([
                        scenario.actor_id,
                        *scenario.administrator_ids,
                    ])
                )
            )
            await session.commit()

    asyncio.run(cleanup())


@pytest.fixture
def concurrent_deactivation_responses(engine, concurrent_administrators):
    scenario = concurrent_administrators

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    def send_together(client):
        barrier = Barrier(2)

        def deactivate(user_id):
            barrier.wait()
            return client.delete(
                f'/users/{user_id}',
                headers={
                    'Cookie': 'access_token='
                    + create_access_token(
                        scenario.actor_id, Settings().JWT_SECRET_KEY
                    ),
                    **TRUSTED_ORIGIN,
                },
            )

        with ThreadPoolExecutor(2) as executor:
            return list(
                executor.map(deactivate, scenario.administrator_ids)
            )

    app.dependency_overrides[get_session] = independent_session
    try:
        with TestClient(app, base_url='https://testserver') as client:
            yield scenario, send_together(client)
    finally:
        app.dependency_overrides.clear()


def test_create_user(client):
    response = client.post(
        '/users',
        json={
            'username': 'alice',
            'email': 'alice@example.com',
            'full_name': 'Alice Example',
            'password': VALID_PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    assert 'id' in response.json()
    assert response.json()['username'] == 'alice'
    assert response.json()['email'] == 'alice@example.com'
    assert response.json()['full_name'] == 'Alice Example'
    assert 'password' not in response.json()


def test_create_user_requires_full_name(client):
    response = client.post(
        '/users',
        json={
            'username': 'missing-full-name',
            'email': 'missing.full.name@example.com',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_create_user_returns_trimmed_full_name(client):
    response = client.post(
        '/users',
        json={
            'full_name': '  Alice Example  ',
            'username': 'alice-full-name',
            'email': 'alice.full.name@example.com',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['full_name'] == 'Alice Example'


@pytest.mark.asyncio
async def test_create_user_stores_only_argon2id_hash(session):
    user = UserSchema.model_validate({
        'username': 'Secure.User',
        'email': 'Secure.User@Example.COM',
        'full_name': 'Secure User',
        'password': VALID_PASSWORD,
    })

    db_user = await create_user(user, session)

    assert db_user.password_hash.startswith('$argon2id$')
    assert db_user.password_hash != VALID_PASSWORD
    assert verify_password(db_user.password_hash, VALID_PASSWORD)


def test_create_user_already_exists_username(client, user):
    response = client.post(
        '/users',
        json={
            'username': user.username,
            'email': 'different@example.com',
            'full_name': 'Different User',
            'password': VALID_PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_already_exists_email(client, user):
    response = client.post(
        '/users',
        json={
            'username': 'different',
            'email': user.email,
            'full_name': 'Different User',
            'password': VALID_PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Email already exists'}


def test_create_user_rejects_case_insensitive_username(client, user):
    response = client.post(
        '/users',
        json={
            'username': user.username.swapcase(),
            'email': 'available@example.com',
            'full_name': 'Available User',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_rejects_case_insensitive_email(client, user):
    response = client.post(
        '/users',
        json={
            'username': 'available',
            'email': user.email.swapcase(),
            'full_name': 'Available User',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Email already exists'}


def test_create_user_preserves_username_and_email_case_after_trim(client):
    response = client.post(
        '/users',
        json={
            'username': '  Alice.Example  ',
            'email': '  Alice.Example@Example.COM  ',
            'full_name': 'Alice Example',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['username'] == 'Alice.Example'
    assert response.json()['email'] == 'Alice.Example@Example.COM'


def test_create_user_reports_username_before_email(client, user):
    response = client.post(
        '/users',
        json={
            'username': user.username,
            'email': user.email,
            'full_name': 'Duplicate User',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_frees_identifiers_after_deletion(client, deleted_user):
    response = client.post(
        '/users',
        json={
            'username': deleted_user.username.swapcase(),
            'email': 'available-after-delete@example.com',
            'full_name': 'Available User',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['username'] == deleted_user.username.swapcase()


def test_create_user_sanitizes_password_validation_error(client):
    response = client.post(
        '/users',
        json={
            'username': 'invalid-password',
            'email': 'invalid@example.com',
            'full_name': 'Invalid Password User',
            'password': 'secret value',
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {'detail': 'Invalid password'}
    assert 'secret value' not in response.text


@pytest.mark.asyncio
async def test_deactivate_user_returns_204_without_body(
    client, user_manager, other_user
):
    authenticate(client, user_manager)

    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''


@pytest.mark.asyncio
async def test_deactivate_user_sets_deleted_at(
    client, session, user_manager, other_user
):
    authenticate(client, user_manager)

    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    deleted_user = await read_user_including_inactive(session, other_user.id)
    assert deleted_user is not None
    assert deleted_user.deleted_at is not None


@pytest.mark.asyncio
async def test_deactivate_user_sets_deleted_by_actor(
    client, session, user_manager, other_user
):
    authenticate(client, user_manager)

    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    deleted_user = await read_user_including_inactive(session, other_user.id)
    assert deleted_user is not None
    assert deleted_user.deleted_by == user_manager.id


def test_deactivated_user_is_absent_from_default_listing(
    client, user_manager, other_user
):
    authenticate(client, user_manager)
    assert client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    ).status_code == HTTPStatus.NO_CONTENT

    response = client.get('/users')

    assert response.status_code == HTTPStatus.OK
    assert str(other_user.id) not in {
        item['id'] for item in response.json()['items']
    }


def test_deactivated_user_is_in_inactive_listing(
    client, user_manager, other_user
):
    authenticate(client, user_manager)
    assert client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    ).status_code == HTTPStatus.NO_CONTENT

    response = client.get('/users?active=false')

    assert response.status_code == HTTPStatus.OK
    inactive_users = {item['id']: item for item in response.json()['items']}
    assert inactive_users[str(other_user.id)]['active'] is False


@pytest.mark.asyncio
async def test_deactivate_user_requires_authentication_without_mutation(
    client, session, other_user
):
    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    current_user = await read_user_including_inactive(session, other_user.id)
    assert current_user is not None
    assert current_user.deleted_at is None
    assert current_user.deleted_by is None


@pytest.mark.asyncio
async def test_deactivate_user_requires_users_manage_without_mutation(
    client, session, user, other_user
):
    authenticate(client, user)

    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    current_user = await read_user_including_inactive(session, other_user.id)
    assert current_user is not None
    assert current_user.deleted_at is None
    assert current_user.deleted_by is None


@pytest.mark.asyncio
async def test_deactivate_user_requires_trusted_origin_without_mutation(
    client, session, user_manager, other_user
):
    authenticate(client, user_manager)

    response = client.delete(
        f'/users/{other_user.id}',
        headers={'Origin': 'https://untrusted.example'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    current_user = await read_user_including_inactive(session, other_user.id)
    assert current_user is not None
    assert current_user.deleted_at is None
    assert current_user.deleted_by is None


def test_deactivate_user_returns_404_for_unknown_uuid(
    client, user_manager
):
    authenticate(client, user_manager)

    response = client.delete(f'/users/{uuid4()}', headers=TRUSTED_ORIGIN)

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_deactivate_user_returns_404_for_inactive_account_unchanged(
    client, session, user_manager, deleted_user
):
    authenticate(client, user_manager)
    original_deleted_at = deleted_user.deleted_at
    original_deleted_by = deleted_user.deleted_by

    response = client.delete(
        f'/users/{deleted_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    current_user = await read_user_including_inactive(session, deleted_user.id)
    assert current_user is not None
    assert current_user.deleted_at == original_deleted_at
    assert current_user.deleted_by == original_deleted_by


def test_deactivate_user_openapi_matches_contract(client):
    operation = client.get('/openapi.json').json()['paths'][
        '/users/{user_id}'
    ]['delete']

    assert operation['operationId'] == 'deactivateUser'
    assert operation['x-required-permission'] == USERS_MANAGE
    assert {'204', '401', '403', '404', '409'} <= set(
        operation['responses']
    )


@pytest.mark.asyncio
async def test_deactivate_user_rejects_self_deactivation(
    client, session, user_manager
):
    authenticate(client, user_manager)

    response = client.delete(
        f'/users/{user_manager.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.CONFLICT
    current_user = await read_user_including_inactive(session, user_manager.id)
    assert current_user is not None
    assert current_user.deleted_at is None
    assert current_user.deleted_by is None


@pytest.mark.asyncio
async def test_deactivate_user_rejects_last_administrator(
    client, session, manager_without_administrator, last_administrator
):
    last_administrator_id = last_administrator.id
    authenticate(client, manager_without_administrator)

    response = client.delete(
        f'/users/{last_administrator_id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.CONFLICT
    current_admin = await read_user_including_inactive(
        session, last_administrator_id
    )
    assert current_admin is not None
    assert current_admin.deleted_at is None
    assert current_admin.deleted_by is None


@pytest.mark.asyncio
async def test_deactivate_one_of_two_administrators_preserves_the_other(
    client, session, user_manager, other_user
):
    administrator_profile = await session.scalar(
        select(AccessProfile).where(
            AccessProfile.system_key == 'administrator'
        )
    )
    session.add(
        UserAccessProfile(
            user_id=other_user.id, profile_id=administrator_profile.id
        )
    )
    await session.commit()
    authenticate(client, user_manager)

    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    remaining_admin = await read_user_including_inactive(
        session, user_manager.id
    )
    deactivated_admin = await read_user_including_inactive(
        session, other_user.id
    )
    assert remaining_admin is not None
    assert remaining_admin.deleted_at is None
    assert deactivated_admin is not None
    assert deactivated_admin.deleted_at is not None


def test_concurrent_admin_deactivation_returns_one_204_and_one_409(
    concurrent_deactivation_responses,
):
    _, responses = concurrent_deactivation_responses

    assert sorted(response.status_code for response in responses) == [
        HTTPStatus.NO_CONTENT,
        HTTPStatus.CONFLICT,
    ]


@pytest.mark.asyncio
async def test_concurrent_admin_deactivation_preserves_an_active_administrator(
    engine, concurrent_deactivation_responses
):
    scenario, responses = concurrent_deactivation_responses
    assert sorted(response.status_code for response in responses) == [
        HTTPStatus.NO_CONTENT,
        HTTPStatus.CONFLICT,
    ]

    async with AsyncSession(engine) as session:
        active_administrators = list(
            await session.scalars(
                select(User.id)
                .join(UserAccessProfile, UserAccessProfile.user_id == User.id)
                .join(
                    AccessProfile,
                    AccessProfile.id == UserAccessProfile.profile_id,
                )
                .where(
                    User.id.in_(scenario.administrator_ids),
                    User.deleted_at.is_(None),
                    UserAccessProfile.deleted_at.is_(None),
                    AccessProfile.id.in_(scenario.profile_ids),
                    AccessProfile.system_key == 'administrator',
                )
                .execution_options(skip_soft_delete_filter=True)
            )
        )

    assert active_administrators


@pytest.mark.asyncio
async def test_old_token_is_rejected_after_user_deactivation(
    client, user_manager, other_user
):
    previous_token = create_access_token(
        other_user.id, Settings().JWT_SECRET_KEY
    )
    authenticate(client, user_manager)
    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    client.cookies.set('access_token', previous_token)
    protected_response = client.get('/auth/me')

    assert protected_response.status_code == HTTPStatus.UNAUTHORIZED


def test_login_is_rejected_after_user_deactivation(
    client, user_manager, other_user
):
    authenticate(client, user_manager)
    response = client.delete(
        f'/users/{other_user.id}', headers=TRUSTED_ORIGIN
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    login_response = client.post(
        '/auth/login',
        json={
            'identifier': other_user.username,
            'password': FACTORY_PASSWORD,
        },
    )

    assert login_response.status_code == HTTPStatus.UNAUTHORIZED
