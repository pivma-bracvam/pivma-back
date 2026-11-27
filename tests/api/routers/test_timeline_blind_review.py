"""O avaliador cego não identifica o proponente nem outro avaliador na
linha do tempo (Spec 049, US4; RF050)."""

from datetime import UTC, datetime
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from pivma.core.database.models import Assignment, AuditEvent
from pivma.routers.processes import _blind_hidden_authors  # noqa: PLC2701
from tests.api.routers.test_participant_router import (
    _process_in_planning_phase,
    authenticate,
    create_active_laboratory_affiliation,
    create_participant,
    revoke_participant,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.user_factory import UserFactory


def _timeline(client, process_id):
    response = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response


def _event(response, event_type):
    [event] = [
        e for e in response.json()['data'] if e['event_type'] == event_type
    ]
    return event


async def _users(session, count):
    users = [UserFactory() for _ in range(count)]
    session.add_all(users)
    await session.commit()
    return users


async def _blind_team(client, session, bracvam_user):
    """Processo na Fase 2 com Grupo Gestor e dois avaliadores ad hoc."""
    process_id, proponent = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    gestor, adhoc_1, adhoc_2 = await _users(session, 3)
    authenticate(client, bracvam_user)
    assignments = {}
    for user, role_key in (
        (gestor, 'group_manager'),
        (adhoc_1, 'adhoc_evaluator'),
        (adhoc_2, 'adhoc_evaluator'),
    ):
        response = create_participant(client, process_id, user.id, role_key)
        assert response.status_code == HTTPStatus.CREATED, response.text
        assignments[user.id] = response.json()['id']
    return SimpleNamespace(
        process_id=process_id,
        proponent=proponent,
        gestor=gestor,
        adhoc_1=adhoc_1,
        adhoc_2=adhoc_2,
        assignments=assignments,
    )


@pytest.mark.asyncio
async def test_adhoc_evaluator_gets_no_proponent_author(
    client, session, bracvam_user
):
    team = await _blind_team(client, session, bracvam_user)
    authenticate(client, team.adhoc_1)

    response = _timeline(client, team.process_id)

    assert _event(response, 'PROCESS_CREATED')['user_id'] is None
    assert str(team.proponent.id) not in response.text


@pytest.mark.asyncio
async def test_peer_reviewer_gets_no_proponent_author(
    client, session, bracvam_user
):
    team = await _blind_team(client, session, bracvam_user)
    [reviewer] = await _users(session, 1)
    await grant_cargo(
        session,
        process_id=team.process_id,
        user=reviewer,
        role_key='peer_reviewer',
    )
    authenticate(client, reviewer)

    response = _timeline(client, team.process_id)

    assert _event(response, 'PROCESS_CREATED')['user_id'] is None
    assert str(team.proponent.id) not in response.text


async def _authored_by(session, process_id, user):
    """Evento do processo, sem execução, com `user` como autor.

    Hoje nenhum evento de autoria de um avaliador chega a outro avaliador;
    o registro direto representa os eventos de avaliação que virão.
    """
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            user_id=user.id,
            event_type='EVALUATION_NOTE',
            context_data={},
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_adhoc_evaluator_gets_no_other_evaluator_id(
    client, session, bracvam_user
):
    team = await _blind_team(client, session, bracvam_user)
    await _authored_by(session, team.process_id, team.adhoc_2)
    authenticate(client, team.adhoc_1)

    response = _timeline(client, team.process_id)

    assert _event(response, 'EVALUATION_NOTE')['user_id'] is None
    assert str(team.adhoc_2.id) not in response.text


@pytest.mark.asyncio
async def test_revoked_evaluator_stays_hidden(client, session, bracvam_user):
    """research R7: a designação revogada continua cegando o autor."""
    team = await _blind_team(client, session, bracvam_user)
    await _authored_by(session, team.process_id, team.adhoc_2)
    authenticate(client, bracvam_user)
    revoked = revoke_participant(
        client, team.process_id, team.assignments[team.adhoc_2.id]
    )
    assert revoked.status_code == HTTPStatus.NO_CONTENT, revoked.text
    authenticate(client, team.adhoc_1)

    response = _timeline(client, team.process_id)

    assert _event(response, 'EVALUATION_NOTE')['user_id'] is None
    assert str(team.adhoc_2.id) not in response.text


@pytest.mark.asyncio
async def test_revoked_proponent_stays_hidden(client, session, bracvam_user):
    """research R7: vale também para a designação de `proponent` revogada."""
    team = await _blind_team(client, session, bracvam_user)
    # A API não revoga a designação do proponente; o registro direto
    # representa a revogação para provar que a consulta inclui revogadas.
    await session.execute(
        update(Assignment)
        .where(
            Assignment.process_instance_id == team.process_id,
            Assignment.role_key == 'proponent',
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    authenticate(client, team.adhoc_1)

    response = _timeline(client, team.process_id)

    assert _event(response, 'PROCESS_CREATED')['user_id'] is None
    assert str(team.proponent.id) not in response.text


@pytest.mark.asyncio
async def test_own_events_keep_own_author(client, session, bracvam_user):
    team = await _blind_team(client, session, bracvam_user)
    await _authored_by(session, team.process_id, team.adhoc_1)
    authenticate(client, team.adhoc_1)

    response = _timeline(client, team.process_id)

    assert _event(response, 'EVALUATION_NOTE')['user_id'] == str(
        team.adhoc_1.id
    )


@pytest.mark.asyncio
async def test_reader_without_role_stays_blind(client, session, bracvam_user):
    """Designação revogada entre a autorização e a resposta: falha fechada."""
    team = await _blind_team(client, session, bracvam_user)
    [revoked] = await _users(session, 1)

    hidden = await _blind_hidden_authors(session, revoked, team.process_id)

    assert {team.proponent.id, team.adhoc_1.id, team.adhoc_2.id} <= hidden


@pytest.mark.asyncio
async def test_adhoc_evaluator_sees_bracvam_author(
    client, session, bracvam_user
):
    team = await _blind_team(client, session, bracvam_user)
    authenticate(client, team.adhoc_1)

    events = _timeline(client, team.process_id).json()['data']

    [own] = [
        e
        for e in events
        if e['event_type'] == 'PARTICIPANT_ASSIGNED'
        and e['context_data']['participant_user_id'] == str(team.adhoc_1.id)
    ]
    assert own['user_id'] == str(bracvam_user.id)


@pytest.mark.asyncio
@pytest.mark.parametrize('role_key', ['sponsor', 'participating_laboratory'])
async def test_roles_without_blind_review_keep_proponent_author(
    client, session, bracvam_user, role_key
):
    team = await _blind_team(client, session, bracvam_user)
    [viewer] = await _users(session, 1)
    laboratory_id = None
    if role_key == 'participating_laboratory':
        laboratory, _ = await create_active_laboratory_affiliation(
            session, viewer
        )
        laboratory_id = laboratory.id
    authenticate(client, bracvam_user)
    designated = create_participant(
        client, team.process_id, viewer.id, role_key, laboratory_id
    )
    assert designated.status_code == HTTPStatus.CREATED, designated.text
    authenticate(client, viewer)

    response = _timeline(client, team.process_id)

    assert _event(response, 'PROCESS_CREATED')['user_id'] == str(
        team.proponent.id
    )
