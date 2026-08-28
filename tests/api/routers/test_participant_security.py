from http import HTTPStatus
from uuid import uuid4

import pytest

from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    PROCESS_PARTICIPANTS_MANAGE,
    RBAC_ASSIGNMENTS_MANAGE,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories import AssignmentFactory
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


async def create_process(session):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.flush()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.flush()
    process = ProcessInstanceFactory(template_version=version)
    session.add(process)
    await session.commit()
    await session.refresh(process)
    return process


async def grant_permission(session, user, code):
    permission = Permission(code=code, description=code)
    profile = AccessProfile(name=f'Profile {code}', description='profile')
    session.add_all([permission, profile])
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        ),
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()


def create_participant(client, process_id, user_id, role_key):
    return client.post(
        f'/processes/{process_id}/participants',
        headers=ORIGIN,
        json={'user_id': str(user_id), 'role_key': role_key},
    )


def revoke_participant(client, process_id, assignment_id):
    return client.delete(
        f'/processes/{process_id}/participants/{assignment_id}',
        headers=ORIGIN,
    )


@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('get', f'/processes/{uuid4()}/participants'),
        ('post', f'/processes/{uuid4()}/participants'),
        ('delete', f'/processes/{uuid4()}/participants/{uuid4()}'),
        ('post', f'/processes/{uuid4()}/participants/{uuid4()}/conflicts'),
        ('get', f'/processes/{uuid4()}/participants/history'),
    ],
)
def test_participant_routes_require_authentication(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_outsider_receives_403_listing_known_process(
    session, client, user
):
    process = await create_process(session)
    authenticate(client, user)

    response = client.get(f'/processes/{process.id}/participants')
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_outsider_receives_same_403_for_known_and_unknown_process(
    session, client, user
):
    process = await create_process(session)
    authenticate(client, user)

    known = client.get(f'/processes/{process.id}/participants')
    unknown = client.get(f'/processes/{uuid4()}/participants')
    assert known.status_code == unknown.status_code == HTTPStatus.FORBIDDEN
    assert known.json() == unknown.json() == {'detail': 'Forbidden'}


@pytest.mark.asyncio
async def test_outsider_receives_same_403_for_history_known_and_unknown(
    session, client, user
):
    process = await create_process(session)
    authenticate(client, user)

    known = client.get(f'/processes/{process.id}/participants/history')
    unknown = client.get(f'/processes/{uuid4()}/participants/history')
    assert known.status_code == unknown.status_code == HTTPStatus.FORBIDDEN
    assert known.json() == unknown.json() == {'detail': 'Forbidden'}


@pytest.mark.asyncio
async def test_group_manager_of_other_process_receives_403_when_designating(
    session, client, user, other_user
):
    own_process = await create_process(session)
    target_process = await create_process(session)
    manager_assignment = AssignmentFactory(
        process=own_process, user=user, assigner=user, role_key='group_manager'
    )
    session.add(manager_assignment)
    await session.commit()
    authenticate(client, user)

    response = create_participant(
        client, target_process.id, other_user.id, 'study_manager'
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['assign', 'revoke', 'declare'])
async def test_mutation_without_trusted_origin_returns_403(
    session, client, user, other_user, mutation
):
    await grant_permission(session, user, PROCESS_PARTICIPANTS_MANAGE)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    if mutation == 'assign':
        response = client.post(
            f'/processes/{process.id}/participants',
            json={'user_id': str(user.id), 'role_key': 'statistician'},
        )
    elif mutation == 'revoke':
        response = client.delete(
            f'/processes/{process.id}/participants/{created["id"]}'
        )
    else:
        authenticate(client, other_user)
        response = client.post(
            f'/processes/{process.id}/participants/{created["id"]}/conflicts',
            json={'has_conflict': True, 'justification': 'Justificativa'},
        )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Invalid origin'}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'permission_code',
    [RBAC_ASSIGNMENTS_MANAGE, INSTITUTIONAL_AFFILIATIONS_MANAGE],
)
@pytest.mark.parametrize('operation', ['assign', 'revoke'])
async def test_unrelated_permissions_do_not_grant_participant_management(
    session, client, user, permission_code, operation
):
    target = UserFactory()
    session.add(target)
    await grant_permission(session, user, permission_code)
    process = await create_process(session)
    authenticate(client, user)

    if operation == 'assign':
        response = create_participant(
            client, process.id, target.id, 'study_manager'
        )
    else:
        assignment = AssignmentFactory(
            process=process,
            user=target,
            assigner=target,
            role_key='study_manager',
        )
        session.add(assignment)
        await session.commit()
        response = revoke_participant(client, process.id, assignment.id)

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_group_manager_of_other_process_receives_403_when_revoking(
    session, client, user, other_user
):
    own_process = await create_process(session)
    target_process = await create_process(session)
    manager_assignment = AssignmentFactory(
        process=own_process, user=user, assigner=user, role_key='group_manager'
    )
    target_assignment = AssignmentFactory(
        process=target_process,
        user=other_user,
        assigner=other_user,
        role_key='study_manager',
    )
    session.add_all([manager_assignment, target_assignment])
    await session.commit()
    authenticate(client, user)

    response = revoke_participant(
        client, target_process.id, target_assignment.id
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
