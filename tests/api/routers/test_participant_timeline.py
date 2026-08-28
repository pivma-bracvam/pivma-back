from datetime import datetime, timezone
from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    AuditEvent,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
NEW_EVENT_TYPES = {
    'PARTICIPANT_ASSIGNED',
    'PARTICIPANT_REVOKED',
    'CONFLICT_DECLARED',
}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


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


def create_participant(client, process_id, user_id, role_key):
    return client.post(
        f'/processes/{process_id}/participants',
        headers=ORIGIN,
        json={'user_id': str(user_id), 'role_key': role_key},
    )


async def setup_process_with_participants(session, client):
    manager = UserFactory()
    outsider = UserFactory()
    participant = UserFactory()
    session.add_all([manager, outsider, participant])
    await session.commit()
    await grant_participants_management(session, manager)
    await bootstrap_all_templates(session)

    authenticate(client, manager)
    created = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Processo de timeline',
        },
    )
    process_id = created.json()['id']
    create_participant(client, process_id, participant.id, 'peer_reviewer')

    return manager, outsider, participant, process_id


@pytest.mark.asyncio
async def test_manager_sees_all_new_participant_events(session, client):
    (
        manager,
        _outsider,
        _participant,
        process_id,
    ) = await setup_process_with_participants(session, client)

    authenticate(client, manager)
    timeline = client.get(f'/processes/{process_id}/timeline')
    assert timeline.status_code == HTTPStatus.OK
    event_types = {e['event_type'] for e in timeline.json()['events']}
    assert 'PARTICIPANT_ASSIGNED' in event_types


@pytest.mark.asyncio
async def test_participant_sees_only_own_participant_events(session, client):
    (
        manager,
        _outsider,
        participant,
        process_id,
    ) = await setup_process_with_participants(session, client)

    authenticate(client, participant)
    timeline = client.get(f'/processes/{process_id}/timeline')
    assert timeline.status_code == HTTPStatus.OK
    participant_events = [
        e
        for e in timeline.json()['events']
        if e['event_type'] in NEW_EVENT_TYPES
    ]
    assert len(participant_events) == 1
    assert participant_events[0]['context_data']['participant_user_id'] == str(
        participant.id
    )


@pytest.mark.asyncio
async def test_outsider_does_not_receive_new_participant_events(
    session, client
):
    (
        _manager,
        outsider,
        _participant,
        process_id,
    ) = await setup_process_with_participants(session, client)

    authenticate(client, outsider)
    timeline = client.get(f'/processes/{process_id}/timeline')
    assert timeline.status_code == HTTPStatus.OK
    event_types = {e['event_type'] for e in timeline.json()['events']}
    assert event_types.isdisjoint(NEW_EVENT_TYPES)


@pytest.mark.asyncio
async def test_filtering_new_events_preserves_previous_timeline_events(
    session, client
):
    (
        _manager,
        outsider,
        _participant,
        process_id,
    ) = await setup_process_with_participants(session, client)

    authenticate(client, outsider)
    timeline = client.get(f'/processes/{process_id}/timeline')
    event_types = {e['event_type'] for e in timeline.json()['events']}
    assert 'PROCESS_CREATED' in event_types


@pytest.mark.asyncio
async def test_timeline_orders_tied_events_by_ascending_identifier(
    session, client
):
    (
        manager,
        _outsider,
        _participant,
        process_id,
    ) = await setup_process_with_participants(session, client)

    tie = datetime(2020, 1, 1, tzinfo=timezone.utc)
    lower_id_event = AuditEvent(
        process_instance_id=UUID(process_id),
        event_type='PARTICIPANT_ASSIGNED',
        user_id=manager.id,
        context_data={'participant_user_id': str(manager.id)},
        occurred_at=tie,
    )
    lower_id_event.id = UUID('00000000-0000-0000-0000-000000000001')
    higher_id_event = AuditEvent(
        process_instance_id=UUID(process_id),
        event_type='PARTICIPANT_ASSIGNED',
        user_id=manager.id,
        context_data={'participant_user_id': str(manager.id)},
        occurred_at=tie,
    )
    higher_id_event.id = UUID('00000000-0000-0000-0000-000000000002')
    session.add_all([lower_id_event, higher_id_event])
    await session.commit()

    authenticate(client, manager)
    timeline = client.get(f'/processes/{process_id}/timeline')
    events = timeline.json()['events']
    assert events[0]['id'] == str(lower_id_event.id)
    assert events[1]['id'] == str(higher_id_event.id)
