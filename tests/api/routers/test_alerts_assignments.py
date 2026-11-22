"""Alerts de designação (Spec 047, US4).

As designações passam pela API pública; os alerts são lidos do banco.
"""

from http import HTTPStatus

import pytest

from pivma.core import alert_service
from tests.api.routers.test_invite_acceptance import accept_invite_req
from tests.api.routers.test_invites_router import create_invite
from tests.api.routers.test_lab_designation_validity import (
    end_affiliation,
    recreate_affiliation,
    world,  # noqa: F401 (fixture)
)
from tests.api.routers.test_participant_router import (
    _process_in_planning_phase,
    authenticate,
    create_active_laboratory_affiliation,
    create_participant,
    revoke_participant,
)
from tests.factories.alert_factory import alerts_for
from tests.factories.user_factory import UserFactory

CREATED = alert_service.ASSIGNMENT_CREATED
REVOKED = alert_service.ASSIGNMENT_REVOKED
CHANGED = alert_service.ASSIGNMENT_EFFECTIVENESS_CHANGED
ASSIGNMENT_PARAMS = {
    'process_code',
    'process_title',
    'role_key',
    'laboratory_name',
}


async def _person(session, **fields):
    user = UserFactory(**fields)
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_direct_designation_alerts_the_designated_person(
    client, session, bracvam_user
):
    """FR-010; FR-006: quem designa não recebe."""
    process_id, _ = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    statistician = await _person(session)
    authenticate(client, bracvam_user)

    response = create_participant(
        client, process_id, statistician.id, 'statistician'
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    [alert] = await alerts_for(session, statistician, CREATED)
    assert set(alert.params) == ASSIGNMENT_PARAMS
    assert alert.params['role_key'] == 'statistician'
    assert alert.params['laboratory_name'] is None
    assert alert.target_type == alert_service.TARGET_PROCESS
    assert await alerts_for(session, bracvam_user, CREATED) == []


@pytest.mark.asyncio
async def test_laboratory_designation_carries_laboratory_name(
    client, session, bracvam_user
):
    process_id, _ = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    lab_person = await _person(session)
    laboratory, _ = await create_active_laboratory_affiliation(
        session, lab_person
    )
    authenticate(client, bracvam_user)

    response = create_participant(
        client,
        process_id,
        lab_person.id,
        'participating_laboratory',
        laboratory.id,
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    [alert] = await alerts_for(session, lab_person, CREATED)
    assert alert.params['laboratory_name'] == laboratory.name


@pytest.mark.asyncio
async def test_revocation_alerts_the_designated_person(
    client, session, bracvam_user
):
    process_id, _ = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    sponsor = await _person(session)
    authenticate(client, bracvam_user)
    created = create_participant(client, process_id, sponsor.id, 'sponsor')

    response = revoke_participant(client, process_id, created.json()['id'])

    assert response.status_code == HTTPStatus.NO_CONTENT, response.text
    [alert] = await alerts_for(session, sponsor, REVOKED)
    assert set(alert.params) == ASSIGNMENT_PARAMS
    assert alert.params['role_key'] == 'sponsor'


@pytest.mark.asyncio
async def test_invite_acceptance_gives_no_designation_alert(
    client, session, bracvam_user
):
    """US4, cenário 2: quem aceita fez a ação."""
    process_id, _ = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, bracvam_user)
    token = create_invite(
        client, process_id, 'novo@exemplo.org', 'sponsor'
    ).json()['token']
    invited = await _person(session, email='novo@exemplo.org')
    authenticate(client, invited)

    response = accept_invite_req(client, token)

    assert response.status_code == HTTPStatus.OK, response.text
    assert await alerts_for(session, invited, CREATED) == []


@pytest.mark.asyncio
async def test_ended_affiliation_alerts_lost_effectiveness(
    client,
    session,
    world,  # noqa: F811
):
    end_affiliation(client, world)

    [alert] = await alerts_for(session, world.lab_user, CHANGED)
    assert alert.params['effective'] is False
    assert alert.params['laboratory_name'] == world.laboratory.name
    assert set(alert.params) == {*ASSIGNMENT_PARAMS, 'effective'}


@pytest.mark.asyncio
async def test_recreated_affiliation_alerts_restored_effectiveness(
    client,
    session,
    world,  # noqa: F811
):
    end_affiliation(client, world)

    recreate_affiliation(client, world)

    changes = await alerts_for(session, world.lab_user, CHANGED)
    assert sorted(a.params['effective'] for a in changes) == [False, True]
