"""Spec 032, US2 - contagens por valor de filtro em `GET /tasks`."""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.task_listing_factory import add_task, listing_process
from tests.factories.user_factory import UserFactory


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _list(client, params):
    response = client.get('/tasks', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


async def _stage_one(session, proponent=None):
    """2 submissões, 3 triagens e 1 revisão de retorno abertas."""
    proponent = proponent or await _user(session)
    for key, count in (
        ('proposal_submission', 2),
        ('triage_evaluation', 3),
        ('submission_return_review', 1),
    ):
        for _ in range(count):
            process = await listing_process(session, proponent=proponent)
            await add_task(session, process, key)
    return proponent


BOARD = [('phase_order', 1), ('status', 'READY'), ('include', 'facets')]


@pytest.mark.asyncio
async def test_facets_count_by_activity_key(client, session, bracvam_user):
    await _stage_one(session)

    authenticate(client, bracvam_user)
    body = _list(client, BOARD)

    assert body['facets']['activity_key'] == {
        'proposal_submission': 2,
        'triage_evaluation': 3,
        'submission_return_review': 1,
    }


@pytest.mark.asyncio
async def test_facets_count_by_status(client, session, bracvam_user):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    await add_task(session, process, 'proposal_submission')
    await add_task(session, process, 'triage_evaluation', status='COMPLETED')
    await add_task(
        session, process, 'submission_return_review', status='COMPLETED'
    )

    authenticate(client, bracvam_user)
    body = _list(client, [('include', 'facets')])

    assert body['facets']['status'] == {'READY': 1, 'COMPLETED': 2}


@pytest.mark.asyncio
async def test_facets_ignore_pagination(client, session, bracvam_user):
    await _stage_one(session)

    authenticate(client, bracvam_user)
    body = _list(client, [*BOARD, ('per_page', 2)])

    assert len(body['data']) == 2  # noqa: PLR2004
    assert sum(body['facets']['activity_key'].values()) == 6  # noqa: PLR2004


@pytest.mark.asyncio
async def test_facets_absent_without_include(client, session, bracvam_user):
    await _stage_one(session)

    authenticate(client, bracvam_user)
    body = _list(client, [('phase_order', 1)])

    assert 'facets' not in body


@pytest.mark.asyncio
async def test_facets_respect_visibility(client, session):
    owner = await _stage_one(session)
    await _stage_one(session)  # outro proponente, invisível para o primeiro

    authenticate(client, owner)
    body = _list(client, [('include', 'facets')])

    # O proponente vê só as próprias submissões e revisões; a triagem é do
    # BraCVAM e não tem concessão de ver para ele.
    assert body['facets']['activity_key'] == {
        'proposal_submission': 2,
        'submission_return_review': 1,
    }


@pytest.mark.asyncio
async def test_facets_respect_current_run(client, session, bracvam_user):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    await add_task(session, process, 'triage_evaluation', status='COMPLETED')
    await add_task(session, process, 'triage_evaluation', run_number=2)

    authenticate(client, bracvam_user)
    current = _list(client, [('include', 'facets')])
    history = _list(client, [('include', 'facets'), ('current_run', 'false')])

    assert current['facets']['activity_key'] == {'triage_evaluation': 1}
    assert history['facets']['activity_key'] == {'triage_evaluation': 2}


@pytest.mark.asyncio
async def test_facets_apply_own_dimension_filter(
    client, session, bracvam_user
):
    await _stage_one(session)

    authenticate(client, bracvam_user)
    body = _list(
        client, [('activity_key', 'triage_evaluation'), ('include', 'facets')]
    )

    assert body['facets']['activity_key'] == {'triage_evaluation': 3}


@pytest.mark.asyncio
async def test_task_list_rejects_unknown_include(client, session):
    authenticate(client, await _user(session))

    response = client.get('/tasks', params={'include': 'meta'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
