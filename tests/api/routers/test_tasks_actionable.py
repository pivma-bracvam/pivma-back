"""Spec 032, US1 - `can_act` e o filtro `actionable` em `GET /tasks`.

"Pode agir" usa a regra de `require_activity_access(..., 'edit')`: cargo com
concessão de editar a atividade e nenhum conflito de interesse vigente no
processo.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import ActivityInstance, ActivityRun, Task
from pivma.core.process_engine import (
    AuthorizationError,
    NotFoundError,
    require_activity_access,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
    grant_cargo,
)
from tests.factories.task_listing_factory import add_task, listing_process
from tests.factories.user_factory import UserFactory


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _list(client, **params):
    response = client.get('/tasks', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _can_act_by_id(body):
    return {item['id']: item['can_act'] for item in body['data']}


async def _board(session):
    """3 processos aguardando triagem e 2 com submissão aberta."""
    proponent = await _user(session)
    triages = []
    for _ in range(3):
        process = await listing_process(session, proponent=proponent)
        triages.append(await add_task(session, process, 'triage_evaluation'))
    submissions = []
    for _ in range(2):
        process = await listing_process(session, proponent=proponent)
        submissions.append(
            await add_task(session, process, 'proposal_submission')
        )
    return proponent, triages, submissions


@pytest.mark.asyncio
async def test_bracvam_actionable_returns_only_triage(
    client, session, bracvam_user
):
    _, triages, _ = await _board(session)

    authenticate(client, bracvam_user)
    body = _list(client, actionable='true')

    assert _can_act_by_id(body) == {str(t.id): True for t in triages}
    assert body['filters_applied']['actionable'] is True


@pytest.mark.asyncio
async def test_bracvam_full_list_flags_can_act(client, session, bracvam_user):
    _, triages, submissions = await _board(session)

    authenticate(client, bracvam_user)
    body = _list(client)

    assert _can_act_by_id(body) == {
        **{str(t.id): True for t in triages},
        **{str(t.id): False for t in submissions},
    }


@pytest.mark.asyncio
async def test_proponent_actionable_returns_own_submission(client, session):
    proponent, _, submissions = await _board(session)

    authenticate(client, proponent)
    body = _list(client, actionable='true')

    assert _can_act_by_id(body) == {str(t.id): True for t in submissions}


@pytest.mark.asyncio
async def test_admin_sees_triage_but_cannot_act(
    client, session, ai_eval_admin
):
    _, triages, _ = await _board(session)

    authenticate(client, ai_eval_admin)
    full = _can_act_by_id(_list(client))
    actionable = _list(client, actionable='true')['data']

    assert all(full[str(t.id)] is False for t in triages)
    assert actionable == []


@pytest.mark.asyncio
async def test_conflict_removes_can_act(client, session, bracvam_user):
    proponent = await _user(session)
    conflicted = await listing_process(session, proponent=proponent)
    clean = await listing_process(session, proponent=proponent)
    conflicted_triage = await add_task(
        session, conflicted, 'triage_evaluation'
    )
    clean_triage = await add_task(session, clean, 'triage_evaluation')
    # O conflito é declarado numa atribuição do processo; o BraCVAM precisa
    # de uma atribuição ali para poder declarar.
    assignment = await grant_cargo(
        session,
        process_id=conflicted.id,
        user=bracvam_user,
        role_key='group_manager',
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    authenticate(client, bracvam_user)
    full = _can_act_by_id(_list(client))
    actionable = _can_act_by_id(_list(client, actionable='true'))

    assert full[str(conflicted_triage.id)] is False
    assert full[str(clean_triage.id)] is True
    assert actionable == {str(clean_triage.id): True}


@pytest.mark.asyncio
async def test_process_cargo_grants_can_act(client, session, bracvam_user):
    proponent = await _user(session)
    selector = await _user(session)
    process = await listing_process(session, proponent=proponent)
    task = await add_task(session, process, 'sample_definition')
    await grant_cargo(
        session,
        process_id=process.id,
        user=selector,
        role_key='sample_selection_group',
    )

    authenticate(client, selector)
    as_selector = _can_act_by_id(_list(client))
    authenticate(client, bracvam_user)
    as_bracvam = _can_act_by_id(_list(client))

    assert as_selector == {str(task.id): True}
    assert as_bracvam == {str(task.id): False}


@pytest.mark.asyncio
async def test_actionable_total_counts_only_actionable(
    client, session, bracvam_user
):
    await _board(session)

    authenticate(client, bracvam_user)
    body = _list(client, actionable='true', per_page=1)

    assert len(body['data']) == 1
    assert body['pagination']['total_items'] == 3  # noqa: PLR2004


async def _activity_of(session, task_id):
    return await session.scalar(
        select(ActivityInstance)
        .join(
            ActivityRun,
            ActivityRun.activity_instance_id == ActivityInstance.id,
        )
        .join(Task, Task.activity_run_id == ActivityRun.id)
        .where(Task.id == task_id)
    )


@pytest.mark.asyncio
async def test_can_act_agrees_with_activity_authorization(
    client, session, bracvam_user, ai_eval_admin
):
    proponent, _, _ = await _board(session)

    for user in (bracvam_user, ai_eval_admin, proponent):
        authenticate(client, user)
        for item in _list(client)['data']:
            activity = await _activity_of(session, item['id'])
            try:
                await require_activity_access(
                    session, user.id, activity, 'edit'
                )
                allowed = True
            except AuthorizationError, NotFoundError:
                allowed = False
            assert item['can_act'] is allowed, (user.id, item['activity_key'])
