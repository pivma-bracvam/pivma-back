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
            'template_key': 'pre_validated_method',
            'title': 'Processo de timeline',
        },
        headers=ORIGIN,
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
    event_types = {e['event_type'] for e in timeline.json()['data']}
    assert 'PARTICIPANT_ASSIGNED' in event_types


@pytest.mark.asyncio
async def test_non_proponent_participant_cannot_read_submission_timeline(
    session, client
):
    """Spec 030: o participante vê o cabeçalho e a timeline do processo,

    mas nenhum evento da submissão, cuja atividade só o proponente vê.
    """
    (
        manager,
        _outsider,
        participant,
        process_id,
    ) = await setup_process_with_participants(session, client)

    authenticate(client, participant)
    timeline = client.get(f'/processes/{process_id}/timeline')
    assert timeline.status_code == HTTPStatus.OK
    assert all(
        event['activity_run_id'] is None for event in timeline.json()['data']
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
    assert timeline.status_code == HTTPStatus.NOT_FOUND


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
    assert timeline.status_code == HTTPStatus.NOT_FOUND


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
    events = timeline.json()['data']
    assert events[0]['id'] == str(lower_id_event.id)
    assert events[1]['id'] == str(higher_id_event.id)


# --- Spec 049, US3: eventos de convite ficam com quem gerencia ----------

INVITE_EVENTS = {
    'INVITE_CREATED',
    'INVITE_RESENT',
    'INVITE_REVOKED',
    'INVITE_ACCEPTED',
}


def _timeline(client, process_id, **params):
    response = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100, **params}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response


def _types(response):
    return [e['event_type'] for e in response.json()['data']]


async def _invite_flow(client, session, bracvam_user):
    """Convites criado, reenviado, revogado e aceito por dois laboratórios."""
    from tests.api.routers.test_invite_acceptance import (  # noqa: PLC0415
        accept_invite_req,
    )
    from tests.api.routers.test_invites_router import (  # noqa: PLC0415
        create_invite,
        resend_invite_req,
        revoke_invite_req,
    )
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        _process_in_planning_phase,
        create_active_laboratory_affiliation,
    )
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        create_participant as designate,
    )

    process_id, proponent = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    gestor = UserFactory()
    member_a = UserFactory(email='lab.a@exemplo.org')
    member_b = UserFactory(email='lab.b@exemplo.org')
    session.add_all([gestor, member_a, member_b])
    await session.commit()
    lab_a, _ = await create_active_laboratory_affiliation(session, member_a)
    lab_b, _ = await create_active_laboratory_affiliation(session, member_b)

    authenticate(client, bracvam_user)
    assert (
        designate(client, process_id, gestor.id, 'group_manager').status_code
        == HTTPStatus.CREATED
    )
    revoked = create_invite(
        client, process_id, 'revogado@exemplo.org', 'adhoc_evaluator'
    )
    assert revoked.status_code == HTTPStatus.CREATED, revoked.text
    assert (
        resend_invite_req(client, process_id, revoked.json()['id']).status_code
        == HTTPStatus.OK
    )
    assert (
        revoke_invite_req(client, process_id, revoked.json()['id']).status_code
        == HTTPStatus.OK
    )
    tokens = {}
    for member, lab in ((member_a, lab_a), (member_b, lab_b)):
        created = create_invite(
            client,
            process_id,
            member.email,
            'participating_laboratory',
            laboratory_id=lab.id,
        )
        assert created.status_code == HTTPStatus.CREATED, created.text
        tokens[member.id] = created.json()['token']
    for member in (member_a, member_b):
        authenticate(client, member)
        accepted = accept_invite_req(client, tokens[member.id])
        assert accepted.status_code == HTTPStatus.OK, accepted.text
    return process_id, proponent, member_a, member_b


@pytest.mark.asyncio
async def test_participant_manager_sees_every_invite_event(
    session, client, bracvam_user
):
    process_id, *_ = await _invite_flow(client, session, bracvam_user)
    authenticate(client, bracvam_user)

    events = _timeline(client, process_id).json()['data']

    assert INVITE_EVENTS <= {e['event_type'] for e in events}
    created = [e for e in events if e['event_type'] == 'INVITE_CREATED']
    assert 'revogado@exemplo.org' in {
        e['context_data']['email'] for e in created
    }
    assert all(
        e['user_id'] is not None
        for e in events
        if e['event_type'] in INVITE_EVENTS
    )


@pytest.mark.asyncio
async def test_proponent_gets_no_invite_management_events(
    session, client, bracvam_user
):
    process_id, proponent, *_ = await _invite_flow(
        client, session, bracvam_user
    )
    authenticate(client, proponent)

    response = _timeline(client, process_id)

    assert not {'INVITE_CREATED', 'INVITE_RESENT', 'INVITE_REVOKED'} & set(
        _types(response)
    )
    assert 'revogado@exemplo.org' not in response.text
    assert 'lab.a@exemplo.org' not in response.text


@pytest.mark.asyncio
async def test_proponent_gets_no_acceptance_of_someone_else(
    session, client, bracvam_user
):
    process_id, proponent, *_ = await _invite_flow(
        client, session, bracvam_user
    )
    authenticate(client, proponent)

    assert 'INVITE_ACCEPTED' not in _types(_timeline(client, process_id))


@pytest.mark.asyncio
async def test_laboratory_member_sees_only_own_acceptance(
    session, client, bracvam_user
):
    """Isolamento por laboratório (constituição III, RF044)."""
    process_id, _, member_a, member_b = await _invite_flow(
        client, session, bracvam_user
    )
    authenticate(client, member_a)

    response = _timeline(client, process_id)

    invites = [
        e for e in response.json()['data'] if e['event_type'] in INVITE_EVENTS
    ]
    assert [e['event_type'] for e in invites] == ['INVITE_ACCEPTED']
    assert invites[0]['user_id'] == str(member_a.id)
    assert member_b.email not in response.text


@pytest.mark.asyncio
async def test_hidden_invites_do_not_count_nor_skip_pages(
    session, client, bracvam_user
):
    process_id, proponent, *_ = await _invite_flow(
        client, session, bracvam_user
    )
    authenticate(client, proponent)
    visible = _timeline(client, process_id).json()

    pages = [
        _timeline(client, process_id, per_page=1, page=page).json()
        for page in range(1, len(visible['data']) + 1)
    ]

    assert visible['pagination']['total_items'] == len(visible['data'])
    assert [p['data'][0]['id'] for p in pages] == [
        e['id'] for e in visible['data']
    ]


async def _email_invite_accepted(client, session, bracvam_user):
    """Convite por e-mail aceito antes do envio: o envio é cancelado."""
    from tests.api.routers.test_invite_acceptance import (  # noqa: PLC0415
        accept_invite_req,
    )
    from tests.api.routers.test_invites_router import (  # noqa: PLC0415
        create_invite,
    )
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        _process_in_planning_phase,
    )

    process_id, proponent = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    sponsor = UserFactory(email='patrocinador@exemplo.org')
    session.add(sponsor)
    await session.commit()
    authenticate(client, bracvam_user)
    created = create_invite(
        client, process_id, sponsor.email, 'sponsor', channel='email'
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    authenticate(client, sponsor)
    accepted = accept_invite_req(client, created.json()['token'])
    assert accepted.status_code == HTTPStatus.OK, accepted.text
    return process_id, proponent, sponsor, created.json()['id']


@pytest.mark.asyncio
async def test_proponent_gets_no_invite_delivery_events(
    session, client, bracvam_user, email_invite_settings
):
    """Spec 049 (#84): o envio do convite revelaria quem aceitou."""
    del email_invite_settings
    process_id, proponent, sponsor, invite_id = await _email_invite_accepted(
        client, session, bracvam_user
    )
    authenticate(client, proponent)

    response = _timeline(client, process_id)

    assert not any(t.startswith('NOTIFICATION_') for t in _types(response))
    assert str(sponsor.id) not in response.text
    assert invite_id not in response.text


@pytest.mark.asyncio
async def test_participant_manager_sees_cancelled_invite_delivery(
    session, client, bracvam_user, email_invite_settings
):
    del email_invite_settings
    process_id, _, sponsor, invite_id = await _email_invite_accepted(
        client, session, bracvam_user
    )
    authenticate(client, bracvam_user)

    events = _timeline(client, process_id).json()['data']

    [cancelled] = [
        e for e in events if e['event_type'] == 'NOTIFICATION_CANCELLED'
    ]
    assert cancelled['context_data']['subject_id'] == invite_id
    assert cancelled['user_id'] == str(sponsor.id)
