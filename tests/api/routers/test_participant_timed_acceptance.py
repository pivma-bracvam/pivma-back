from http import HTTPStatus
from time import perf_counter

import pytest

from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories import AssignmentFactory, UserFactory
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)

CYCLE_COUNT = 200
MEASURED_REQUESTS = 20
MAX_SECONDS = 2.0
MIN_SUCCESSFUL = 19


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


async def grant_participants_management(session, user):
    permission = Permission(
        code=PROCESS_PARTICIPANTS_MANAGE,
        description=PROCESS_PARTICIPANTS_MANAGE,
    )
    profile = AccessProfile(
        name=f'Participants admin {user.id}', description='admin'
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


async def seed_cycles(session, process, manager):
    participants = [UserFactory() for _ in range(CYCLE_COUNT)]
    session.add_all(participants)
    await session.flush()
    assignments = [
        AssignmentFactory(
            process=process,
            user=participant,
            assigner=manager,
            role_key='study_manager',
        )
        for participant in participants
    ]
    session.add_all(assignments)
    await session.commit()


def _measure(client, path):
    client.get(path)  # chamada de aquecimento, fora da medição
    timings = []
    for _ in range(MEASURED_REQUESTS):
        started = perf_counter()
        response = client.get(path)
        elapsed = perf_counter() - started
        assert response.status_code == HTTPStatus.OK
        timings.append(elapsed)
    return timings


@pytest.mark.asyncio
async def test_current_listing_meets_two_second_target_after_warmup(
    session, client, user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    await seed_cycles(session, process, user)
    authenticate(client, user)

    timings = _measure(client, f'/processes/{process.id}/participants')
    successful = sum(1 for elapsed in timings if elapsed <= MAX_SECONDS)
    assert successful >= MIN_SUCCESSFUL


@pytest.mark.asyncio
async def test_history_query_meets_two_second_target_after_warmup(
    session, client, user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    await seed_cycles(session, process, user)
    authenticate(client, user)

    timings = _measure(
        client, f'/processes/{process.id}/participants/history?limit=200'
    )
    successful = sum(1 for elapsed in timings if elapsed <= MAX_SECONDS)
    assert successful >= MIN_SUCCESSFUL
