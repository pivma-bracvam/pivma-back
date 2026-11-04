"""Testes focados do perfil do usuário (Spec 045).

`user` e `other_user` (conftest) são contas comuns, sem perfil global.
"""

from datetime import datetime
from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio

from pivma import app
from pivma.core.authorization import USERS_READ
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Assignment,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.institutional_factory import (
    InstitutionFactory,
    LaboratoryFactory,
)
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)
from tests.factories.rbac_factory import AccessProfileFactory

PROFILE_KEYS = {
    'id',
    'full_name',
    'email',
    'active',
    'created_at',
    'global_profiles',
}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


@pytest_asyncio.fixture
async def profile_reader(session, user):
    """Conta com um perfil não canônico que só tem `users.read`."""
    permission = Permission(code=USERS_READ, description=USERS_READ)
    profile = AccessProfile(
        system_key=None, name='Leitor de perfis', description='users.read'
    )
    session.add_all([permission, profile])
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        ),
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()
    return user


async def grant_global_profile(
    session, user, *, created_at, deleted_at=None, profile=None
):
    if profile is None:
        profile = AccessProfileFactory()
        session.add(profile)
        await session.flush()
    assignment = UserAccessProfile(user_id=user.id, profile_id=profile.id)
    assignment.created_at = created_at
    assignment.deleted_at = deleted_at
    session.add(assignment)
    await session.commit()
    return profile


async def create_process(session, **overrides):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.flush()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.flush()
    process = ProcessInstanceFactory(template_version=version, **overrides)
    session.add(process)
    await session.commit()
    return process


async def designate(  # noqa: PLR0913
    session,
    process,
    user,
    *,
    role_key='proponent',
    assigned_at=datetime(2026, 10, 1),
    revoked_at=None,
    deleted_at=None,
    laboratory=None,
):
    assignment = Assignment(
        process_instance_id=process.id,
        user_id=user.id,
        assigned_by=user.id,
        role_key=role_key,
        assigned_at=assigned_at,
        revoked_at=revoked_at,
        laboratory_id=None if laboratory is None else laboratory.id,
    )
    assignment.deleted_at = deleted_at
    session.add(assignment)
    await session.commit()
    return assignment


def process_ids(response):
    return [item['process']['id'] for item in response.json()['data']]


def role_ids(item):
    return [role['id'] for role in item['roles']]


def error_code(response):
    return response.json()['detail']['code']


# ---------------------------------------------------------------- US1


def test_profile_has_only_public_account_fields(client, user):
    authenticate(client, user)

    response = client.get(f'/users/{user.id}')

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()) == PROFILE_KEYS


def test_member_reads_own_profile(client, user):
    authenticate(client, user)

    response = client.get(f'/users/{user.id}')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == str(user.id)
    assert response.json()['email'] == user.email
    assert response.json()['full_name'] == user.full_name
    assert response.json()['active'] is True


@pytest.mark.asyncio
async def test_global_profiles_follow_assignment_date_then_id(
    client, session, user
):
    later = datetime(2026, 10, 3)
    tied = [
        await grant_global_profile(session, user, created_at=later)
        for _ in range(2)
    ]
    earliest = await grant_global_profile(
        session, user, created_at=datetime(2026, 10, 1)
    )
    authenticate(client, user)

    response = client.get(f'/users/{user.id}')

    expected = [earliest.id, *sorted(profile.id for profile in tied)]
    assert [item['id'] for item in response.json()['global_profiles']] == [
        str(profile_id) for profile_id in expected
    ]


@pytest.mark.asyncio
async def test_deleted_global_assignment_is_hidden(client, session, user):
    await grant_global_profile(
        session,
        user,
        created_at=datetime(2026, 10, 1),
        deleted_at=datetime(2026, 10, 2),
    )
    authenticate(client, user)

    response = client.get(f'/users/{user.id}')

    assert response.json()['global_profiles'] == []


@pytest.mark.asyncio
async def test_assignment_of_deactivated_profile_is_hidden(
    client, session, user
):
    profile = await grant_global_profile(
        session, user, created_at=datetime(2026, 10, 1)
    )
    profile.deleted_at = datetime(2026, 10, 2)
    await session.commit()
    authenticate(client, user)

    response = client.get(f'/users/{user.id}')

    assert response.json()['global_profiles'] == []


@pytest.mark.asyncio
async def test_regranted_profile_shows_once_with_new_date(
    client, session, user
):
    regranted_at = datetime(2026, 10, 5)
    profile = await grant_global_profile(
        session,
        user,
        created_at=datetime(2026, 10, 1),
        deleted_at=datetime(2026, 10, 2),
    )
    await grant_global_profile(
        session, user, created_at=regranted_at, profile=profile
    )
    authenticate(client, user)

    response = client.get(f'/users/{user.id}')

    [item] = response.json()['global_profiles']
    assert item['id'] == str(profile.id)
    assert datetime.fromisoformat(item['assigned_at']) == regranted_at


def test_profile_without_session_is_unauthorized(client, user):
    response = client.get(f'/users/{user.id}')

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_profile_with_deactivated_account_session_is_unauthorized(
    client, deleted_user
):
    authenticate(client, deleted_user)

    response = client.get(f'/users/{deleted_user.id}')

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_member_cannot_read_another_profile(client, user, other_user):
    authenticate(client, user)

    response = client.get(f'/users/{other_user.id}')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert error_code(response) == 'forbidden'
    assert set(response.json()) == {'detail'}
    assert other_user.email not in response.text


def test_profile_with_invalid_user_id_is_validation_error(client, user):
    authenticate(client, user)

    response = client.get('/users/not-a-uuid')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert error_code(response) == 'validation_error'


# ---------------------------------------------------------------- US2

REVOKED_AT = datetime(2026, 10, 9)


def roles_of(client, user, **params):
    authenticate(client, user)
    return client.get(f'/users/{user.id}/process-roles', params=params)


@pytest.mark.asyncio
async def test_roles_in_same_process_share_one_item(client, session, user):
    process = await create_process(session)
    proponent = await designate(session, process, user)
    statistician = await designate(
        session,
        process,
        user,
        role_key='statistician',
        assigned_at=datetime(2026, 10, 2),
    )

    response = roles_of(client, user)

    [item] = response.json()['data']
    assert role_ids(item) == [str(statistician.id), str(proponent.id)]


@pytest.mark.asyncio
async def test_process_role_item_has_only_documented_fields(
    client, session, user
):
    process = await create_process(session)
    await designate(session, process, user)

    response = roles_of(client, user)

    [item] = response.json()['data']
    assert set(item) == {'process', 'roles'}
    assert set(item['process']) == {'id', 'code', 'title', 'status'}
    assert set(item['roles'][0]) == {
        'id',
        'role_key',
        'laboratory',
        'assigned_at',
        'revoked_at',
    }


@pytest.mark.asyncio
async def test_laboratory_role_brings_laboratory_reference(
    client, session, user
):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.flush()
    process = await create_process(session)
    await designate(session, process, user)
    await designate(
        session,
        process,
        user,
        role_key='lead_laboratory',
        assigned_at=datetime(2026, 10, 2),
        laboratory=laboratory,
    )

    response = roles_of(client, user)

    lead, proponent = response.json()['data'][0]['roles']
    assert lead['laboratory'] == {
        'id': str(laboratory.id),
        'name': laboratory.name,
        'active': True,
        'institution': {
            'id': str(institution.id),
            'name': institution.name,
            'active': True,
        },
    }
    assert proponent['laboratory'] is None


@pytest.mark.asyncio
async def test_process_roles_default_to_active_roles(client, session, user):
    process = await create_process(session)
    active = await designate(session, process, user)
    await designate(
        session,
        process,
        user,
        role_key='statistician',
        revoked_at=REVOKED_AT,
    )

    response = roles_of(client, user)

    [item] = response.json()['data']
    assert role_ids(item) == [str(active.id)]
    assert response.json()['filters_applied'] == {'active': True}


@pytest.mark.asyncio
async def test_process_roles_active_false_lists_revoked_roles(
    client, session, user
):
    process = await create_process(session)
    await designate(session, process, user)
    revoked = await designate(
        session,
        process,
        user,
        role_key='statistician',
        revoked_at=REVOKED_AT,
    )

    response = roles_of(client, user, active='false')

    [item] = response.json()['data']
    assert role_ids(item) == [str(revoked.id)]
    assert item['roles'][0]['revoked_at'] is not None
    assert response.json()['filters_applied'] == {'active': False}


@pytest.mark.asyncio
async def test_process_with_only_revoked_roles_is_not_active(
    client, session, user
):
    process = await create_process(session)
    await designate(session, process, user, revoked_at=REVOKED_AT)

    response = roles_of(client, user)

    assert response.json()['data'] == []


@pytest.mark.asyncio
async def test_processes_follow_latest_assignment_then_process_id(
    client, session, user
):
    latest = await create_process(session)
    await designate(session, latest, user, assigned_at=datetime(2026, 10, 1))
    await designate(
        session,
        latest,
        user,
        role_key='statistician',
        assigned_at=datetime(2026, 10, 7),
    )
    middle = await create_process(session)
    await designate(session, middle, user, assigned_at=datetime(2026, 10, 5))
    tied = [await create_process(session) for _ in range(2)]
    for process in tied:
        await designate(
            session, process, user, assigned_at=datetime(2026, 10, 3)
        )

    response = roles_of(client, user)

    expected = [latest.id, middle.id, *sorted(p.id for p in tied)]
    assert process_ids(response) == [str(i) for i in expected]
    assert response.json()['sort'] == {
        'by': 'last_assigned_at',
        'order': 'desc',
    }


@pytest.mark.asyncio
async def test_roles_follow_assignment_date_then_id(client, session, user):
    process = await create_process(session)
    oldest = await designate(session, process, user)
    tied = [
        await designate(
            session,
            process,
            user,
            role_key=role_key,
            assigned_at=datetime(2026, 10, 4),
        )
        for role_key in ('statistician', 'study_manager')
    ]

    response = roles_of(client, user)

    expected = [*sorted(a.id for a in tied), oldest.id]
    assert role_ids(response.json()['data'][0]) == [str(i) for i in expected]


@pytest.mark.asyncio
async def test_process_roles_paginate_by_process(client, session, user):
    processes = [await create_process(session) for _ in range(3)]
    for process in processes:
        await designate(session, process, user)
    await designate(session, processes[0], user, role_key='statistician')

    first = roles_of(client, user, per_page=2)
    second = roles_of(client, user, per_page=2, page=2)

    assert len(first.json()['data']) == 2  # noqa: PLR2004
    assert len(second.json()['data']) == 1
    assert first.json()['pagination']['total_items'] == 3  # noqa: PLR2004
    assert first.json()['pagination']['total_pages'] == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_page_beyond_last_is_empty_with_totals(client, session, user):
    process = await create_process(session)
    await designate(session, process, user)

    response = roles_of(client, user, page=5)

    assert response.json()['data'] == []
    assert response.json()['pagination']['total_items'] == 1


@pytest.mark.parametrize('active', [True, False])
@pytest.mark.asyncio
async def test_deleted_assignment_is_hidden(client, session, user, active):
    process = await create_process(session)
    await designate(
        session,
        process,
        user,
        revoked_at=None if active else REVOKED_AT,
        deleted_at=datetime(2026, 10, 10),
    )

    response = roles_of(client, user, active=active)

    assert response.json()['data'] == []
    assert response.json()['pagination']['total_items'] == 0


@pytest.mark.asyncio
async def test_assignment_of_deleted_process_is_hidden(client, session, user):
    process = await create_process(session)
    await designate(session, process, user)
    process.deleted_at = datetime(2026, 10, 10)
    await session.commit()

    response = roles_of(client, user)

    assert response.json()['data'] == []
    assert response.json()['pagination']['total_items'] == 0


@pytest.mark.asyncio
async def test_closed_process_is_listed_with_status(client, session, user):
    process = await create_process(session, status='CLOSED')
    await designate(session, process, user)

    response = roles_of(client, user)

    assert response.json()['data'][0]['process']['status'] == 'CLOSED'


@pytest.mark.asyncio
async def test_roles_of_another_person_are_not_listed(
    client, session, user, other_user
):
    process = await create_process(session)
    own = await designate(session, process, user)
    await designate(
        session,
        process,
        other_user,
        role_key='statistician',
        assigned_at=datetime(2026, 10, 2),
    )

    response = roles_of(client, user)

    [item] = response.json()['data']
    assert role_ids(item) == [str(own.id)]


@pytest.mark.parametrize('active', [True, False])
def test_account_without_assignments_has_no_process_roles(
    client, user, active
):
    response = roles_of(client, user, active=active)

    assert response.json()['data'] == []
    assert response.json()['pagination']['total_items'] == 0


def test_process_roles_without_session_is_unauthorized(client, user):
    response = client.get(f'/users/{user.id}/process-roles')

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_member_cannot_read_another_persons_process_roles(
    client, session, user, other_user
):
    process = await create_process(session)
    await designate(session, process, other_user)
    authenticate(client, user)

    response = client.get(f'/users/{other_user.id}/process-roles')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert error_code(response) == 'forbidden'
    assert set(response.json()) == {'detail'}


def test_process_roles_with_invalid_user_id_is_validation_error(client, user):
    authenticate(client, user)

    response = client.get('/users/not-a-uuid/process-roles')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert error_code(response) == 'validation_error'


# ---------------------------------------------------------------- US3


def test_reader_reads_another_profile(client, profile_reader, other_user):
    authenticate(client, profile_reader)

    response = client.get(f'/users/{other_user.id}')

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()) == PROFILE_KEYS
    assert response.json()['id'] == str(other_user.id)


@pytest.mark.asyncio
async def test_reader_reads_all_process_roles_of_another_person(
    client, session, profile_reader, other_user
):
    processes = [await create_process(session) for _ in range(2)]
    for process in processes:
        await designate(session, process, other_user)
    authenticate(client, profile_reader)

    response = client.get(f'/users/{other_user.id}/process-roles')

    assert response.status_code == HTTPStatus.OK
    assert set(process_ids(response)) == {str(p.id) for p in processes}


@pytest.mark.parametrize('suffix', ['', '/process-roles'])
def test_reader_gets_not_found_for_unknown_account(
    client, profile_reader, suffix
):
    authenticate(client, profile_reader)

    response = client.get(f'/users/{uuid4()}{suffix}')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert error_code(response) == 'not_found'


def test_reader_reads_deactivated_account(
    client, profile_reader, deleted_user
):
    authenticate(client, profile_reader)

    response = client.get(f'/users/{deleted_user.id}')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['active'] is False


@pytest.mark.parametrize('suffix', ['', '/process-roles'])
def test_member_cannot_tell_existing_from_unknown_account(
    client, user, other_user, suffix
):
    authenticate(client, user)

    existing = client.get(f'/users/{other_user.id}{suffix}')
    unknown = client.get(f'/users/{uuid4()}{suffix}')

    assert existing.status_code == unknown.status_code == HTTPStatus.FORBIDDEN
    assert existing.json() == unknown.json()


@pytest.mark.parametrize(
    ('path', 'operation_id'),
    [
        ('/users/{user_id}', 'getUserProfile'),
        ('/users/{user_id}/process-roles', 'listUserProcessRoles'),
    ],
)
def test_openapi_documents_profile_routes(path, operation_id):
    operation = app.openapi()['paths'][path]['get']

    assert operation['operationId'] == operation_id
    assert {'401', '403', '404'} <= set(operation['responses'])
