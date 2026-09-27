"""Spec 033, US1 (3c) - participantes, histórico e convites no envelope."""

from http import HTTPStatus

import pytest
import pytest_asyncio

from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from tests.api.routers.test_rbac_router import authenticate
from tests.conftest import _make_rbac_user
from tests.factories.invite_factory import InviteFactory
from tests.factories.participant_factory import grant_cargo
from tests.factories.task_listing_factory import listing_process
from tests.factories.user_factory import UserFactory

ENVELOPE_KEYS = {'data', 'pagination', 'filters_applied', 'sort'}


def _get(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _invite(process, creator, role_key='statistician'):
    invite = InviteFactory(process=process, role_key=role_key)
    invite.set_creation_audit(creator.id)
    return invite


@pytest_asyncio.fixture
async def manager(session):
    return await _make_rbac_user(
        session,
        system_key=None,
        name='Gestor de participantes',
        codes=(PROCESS_PARTICIPANTS_MANAGE,),
    )


async def _process_with_members(session, count):
    """Processo do proponente com `count` membros além dele."""
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    members = []
    for role in ('group_manager', 'statistician', 'collaborator')[:count]:
        member = await _user(session)
        await grant_cargo(
            session, process_id=process.id, user=member, role_key=role
        )
        members.append(member)
    return process, proponent, members


@pytest.mark.asyncio
async def test_participants_envelope(client, session, manager):
    process, _, _ = await _process_with_members(session, 2)

    authenticate(client, manager)
    body = _get(client, f'/processes/{process.id}/participants')

    assert set(body) == ENVELOPE_KEYS
    assert body['pagination']['total_items'] == 3  # noqa: PLR2004
    assert body['sort'] == {'by': 'assigned_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_participants_self_scope_total(client, session):
    process, _, members = await _process_with_members(session, 3)

    # O estatístico não gere participantes: vê só a própria designação.
    authenticate(client, members[1])
    body = _get(client, f'/processes/{process.id}/participants')

    assert body['pagination']['total_items'] == 1
    assert len(body['data']) == 1


@pytest.mark.asyncio
async def test_participant_history_second_page(client, session, manager):
    process, _, _ = await _process_with_members(session, 2)

    authenticate(client, manager)
    body = _get(
        client,
        f'/processes/{process.id}/participants/history',
        page=2,
        per_page=2,
    )

    assert len(body['data']) == 1
    assert body['pagination']['total_items'] == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_invites_envelope(client, session, manager):
    process, proponent, _ = await _process_with_members(session, 0)
    session.add(_invite(process, proponent))
    await session.commit()

    authenticate(client, manager)
    body = _get(client, f'/processes/{process.id}/participants/invites')

    assert set(body) == ENVELOPE_KEYS
    assert len(body['data']) == 1
    assert body['sort'] == {'by': 'created_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_invites_total_counts_only_manageable(client, session):
    process, proponent, _ = await _process_with_members(session, 0)
    # O proponente gere só `sponsor` e `group_manager` (Spec 028, FR-003).
    session.add_all([
        _invite(process, proponent, 'sponsor'),
        _invite(process, proponent, 'group_manager'),
        _invite(process, proponent, 'statistician'),
        _invite(process, proponent, 'statistician'),
    ])
    await session.commit()

    authenticate(client, proponent)
    body = _get(
        client, f'/processes/{process.id}/participants/invites', per_page=1
    )

    assert body['pagination']['total_items'] == 2  # noqa: PLR2004
    assert body['pagination']['total_pages'] == 2  # noqa: PLR2004


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'path',
    [
        '/processes/{pid}/participants',
        '/processes/{pid}/participants/history',
        '/processes/{pid}/participants/invites',
    ],
)
async def test_participant_lists_reject_per_page_above_100(
    client, session, manager, path
):
    process, _, _ = await _process_with_members(session, 0)

    authenticate(client, manager)
    response = client.get(
        path.format(pid=process.id), params={'per_page': 101}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
