"""Spec 033, US2 - participantes e convites com referências resumidas."""

import json
from contextlib import contextmanager
from http import HTTPStatus

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.engine import Engine

from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from pivma.core.database.models import User
from tests.api.routers.test_invites_router import create_invite
from tests.api.routers.test_participant_router import (
    ORIGIN,
    _process_in_planning_phase,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.conftest import _make_rbac_user
from tests.factories.invite_factory import InviteFactory
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import (
    assign_lab,
    lab_user,
    new_laboratory,
)
from tests.factories.task_listing_factory import listing_process
from tests.factories.user_factory import UserFactory

USER_REF_KEYS = {'id', 'username', 'full_name'}


async def _user(session, **kwargs):
    user = UserFactory(**kwargs)
    session.add(user)
    await session.commit()
    return user


@pytest_asyncio.fixture
async def manager(session):
    return await _make_rbac_user(
        session,
        system_key=None,
        name='Gestor de participantes',
        codes=(PROCESS_PARTICIPANTS_MANAGE,),
    )


def _participants(client, process_id):
    response = client.get(f'/processes/{process_id}/participants')
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()['data']


async def _process_with_lab(session):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    laboratory = await new_laboratory(session)
    assignment = await assign_lab(session, process.id, laboratory)
    return process, proponent, laboratory, assignment


@pytest.mark.asyncio
async def test_participant_item_has_user_and_laboratory_refs(
    client, session, manager
):
    process, _, laboratory, assignment = await _process_with_lab(session)

    authenticate(client, manager)
    item = next(
        i
        for i in _participants(client, process.id)
        if i['id'] == str(assignment.id)
    )

    assert set(item['user']) == USER_REF_KEYS
    assert item['user']['id'] == str(assignment.user_id)
    assert item['laboratory']['id'] == str(laboratory.id)
    assert item['laboratory']['institution']['id'] == str(
        laboratory.institution_id
    )
    assert item['process'] == {
        'id': str(process.id),
        'code': process.code,
        'title': process.title,
    }
    assert not {'user_id', 'laboratory_id', 'process_id'} & set(item)


@pytest.mark.asyncio
async def test_participant_without_laboratory_has_null_laboratory(
    client, session, manager
):
    process, _, _, _ = await _process_with_lab(session)
    member = await _user(session)
    assignment = await grant_cargo(
        session, process_id=process.id, user=member, role_key='group_manager'
    )

    authenticate(client, manager)
    item = next(
        i
        for i in _participants(client, process.id)
        if i['id'] == str(assignment.id)
    )

    assert item['laboratory'] is None
    assert item['user']['full_name'] == member.full_name


@pytest.mark.asyncio
async def test_participant_refs_never_include_email(client, session, manager):
    process, proponent, _, assignment = await _process_with_lab(session)

    authenticate(client, manager)
    response = client.get(f'/processes/{process.id}/participants')

    blob = json.dumps(response.json())
    assert proponent.email not in blob
    lab_member = await session.get(User, assignment.user_id)
    assert lab_member.email not in blob


@pytest.mark.asyncio
async def test_create_participant_response_has_refs(client, session, manager):
    process, _, _, _ = await _process_with_lab(session)
    laboratory = await new_laboratory(session)
    member = await lab_user(session, laboratory)

    authenticate(client, manager)
    response = client.post(
        f'/processes/{process.id}/participants',
        headers=ORIGIN,
        json={
            'user_id': str(member.id),
            'role_key': 'participating_laboratory',
            'laboratory_id': str(laboratory.id),
        },
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body['user']['id'] == str(member.id)
    assert body['laboratory']['id'] == str(laboratory.id)


@pytest.mark.asyncio
async def test_history_items_use_refs(client, session, manager):
    process, _, laboratory, assignment = await _process_with_lab(session)

    authenticate(client, manager)
    response = client.get(f'/processes/{process.id}/participants/history')

    item = next(
        i['assignment']
        for i in response.json()['data']
        if i['assignment']['id'] == str(assignment.id)
    )
    assert set(item['user']) == USER_REF_KEYS
    assert item['laboratory']['id'] == str(laboratory.id)


@pytest.mark.asyncio
async def test_self_scope_still_sees_only_own_assignment(client, session):
    process, _, _, assignment = await _process_with_lab(session)
    lab_member = await session.get(User, assignment.user_id)

    authenticate(client, lab_member)
    items = _participants(client, process.id)

    assert [item['id'] for item in items] == [str(assignment.id)]


@pytest.mark.asyncio
async def test_invite_item_has_laboratory_ref(client, session, manager):
    process, proponent, laboratory, _ = await _process_with_lab(session)
    invite = InviteFactory(
        process=process,
        laboratory=laboratory,
        role_key='participating_laboratory',
    )
    invite.set_creation_audit(proponent.id)
    session.add(invite)
    await session.commit()

    authenticate(client, manager)
    response = client.get(f'/processes/{process.id}/participants/invites')

    [item] = response.json()['data']
    assert item['laboratory']['institution']['id'] == str(
        laboratory.institution_id
    )
    assert item['process']['id'] == str(process.id)
    assert not {'laboratory_id', 'process_id'} & set(item)


@pytest.mark.asyncio
async def test_invite_accept_response_has_refs(client, session, bracvam_user):
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    token = create_invite(
        client, process_id, 'aceite@exemplo.org', 'sponsor'
    ).json()['token']
    invitee = await _user(session, email='aceite@exemplo.org')

    authenticate(client, invitee)
    response = client.post(f'/invites/{token}/accept', headers=ORIGIN)

    assert response.status_code == HTTPStatus.OK, response.text
    invite = response.json()['invite']
    assert invite['process']['id'] == process_id
    assert invite['laboratory'] is None


@contextmanager
def _count_selects():
    statements = []

    def _record(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    event.listen(Engine, 'before_cursor_execute', _record)
    try:
        yield statements
    finally:
        event.remove(Engine, 'before_cursor_execute', _record)


@pytest.mark.asyncio
async def test_participant_list_queries_do_not_grow_with_items(
    client, session, manager
):
    small, _, _, _ = await _process_with_lab(session)
    large, _, _, _ = await _process_with_lab(session)
    for _ in range(9):
        await assign_lab(session, large.id, await new_laboratory(session))

    authenticate(client, manager)
    with _count_selects() as small_selects:
        _participants(client, small.id)
    with _count_selects() as large_selects:
        _participants(client, large.id)

    assert len(large_selects) == len(small_selects)
