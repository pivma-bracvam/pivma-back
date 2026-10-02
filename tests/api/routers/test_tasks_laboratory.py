"""`can_act`, laboratório e status da execução em `/tasks` (Spec 036)."""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    all_labs_done,
    complete_lab,
    frozen_lab_process,
    reopen,
    runs_by_lab,
    tasks_of,
    waive,
)


def _receipt_tasks(client, user):
    authenticate(client, user)
    resp = client.get('/tasks', params={'activity_key': 'receipt'})
    assert resp.status_code == HTTPStatus.OK
    return resp.json()['data']


@pytest.mark.asyncio
async def test_group_manager_cannot_act_on_lab_tasks(client, session):
    ctx = await frozen_lab_process(session)

    tasks = _receipt_tasks(client, ctx.group_manager)

    assert len(tasks) == len(ctx.labs)
    assert {task['can_act'] for task in tasks} == {False}


@pytest.mark.asyncio
async def test_lab_user_can_act_on_own_task(client, session):
    ctx = await frozen_lab_process(session)

    tasks = _receipt_tasks(client, ctx.lab_users[0])

    assert [task['can_act'] for task in tasks] == [True]


def _by_lab(tasks):
    return {(task['laboratory'] or {}).get('id'): task for task in tasks}


@pytest.mark.asyncio
async def test_lab_task_carries_laboratory_reference(client, session):
    ctx = await frozen_lab_process(session)

    tasks = _receipt_tasks(client, ctx.group_manager)

    by_lab = _by_lab(tasks)
    assert set(by_lab) == {str(lab.id) for lab in ctx.labs}
    for lab in ctx.labs:
        ref = by_lab[str(lab.id)]['laboratory']
        assert ref['name'] == lab.name
        assert ref['active'] is True
        assert ref['institution']['id'] == str(lab.institution_id)


@pytest.mark.asyncio
async def test_single_activity_task_has_no_laboratory(client, session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    authenticate(client, ctx.statistician)

    resp = client.get('/tasks', params={'activity_key': 'statistics'})

    [task] = resp.json()['data']
    assert task['laboratory'] is None
    assert task['activity_run_status'] == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_run_status_tells_completed_open_and_waived(client, session):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', 0)
    await waive(session, ctx, 2)

    by_lab = _by_lab(_receipt_tasks(client, ctx.group_manager))

    assert [
        by_lab[str(lab.id)]['activity_run_status'] for lab in ctx.labs
    ] == ['COMPLETED', 'IN_PROGRESS', 'WAIVED']


def _upload_tasks(client, user, **params):
    authenticate(client, user)
    resp = client.get('/tasks', params={'activity_key': 'upload', **params})
    assert resp.status_code == HTTPStatus.OK
    return resp.json()['data']


@pytest.mark.asyncio
async def test_current_run_is_latest_per_laboratory(client, session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await reopen(session, ctx, 'upload', 1)

    by_lab = _by_lab(_upload_tasks(client, ctx.group_manager))

    assert {
        lab_id: task['activity_run_number'] for lab_id, task in by_lab.items()
    } == {
        str(ctx.labs[0].id): 1,
        str(ctx.labs[1].id): 2,
        str(ctx.labs[2].id): 1,
    }


@pytest.mark.asyncio
async def test_all_runs_show_superseded_status(client, session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await reopen(session, ctx, 'upload', 1)

    tasks = _upload_tasks(client, ctx.group_manager, current_run='false')

    lab_b = [
        (task['activity_run_number'], task['activity_run_status'])
        for task in tasks
        if task['laboratory']['id'] == str(ctx.labs[1].id)
    ]
    assert sorted(lab_b) == [(1, 'SUPERSEDED'), (2, 'IN_PROGRESS')]


@pytest.mark.asyncio
async def test_blocked_current_run_hides_lab_task(client, session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    await reopen(session, ctx, 'upload', 1)
    authenticate(client, ctx.group_manager)

    resp = client.get('/tasks', params={'activity_key': 'material_return'})

    labs = {task['laboratory']['id'] for task in resp.json()['data']}
    assert labs == {str(ctx.labs[0].id), str(ctx.labs[2].id)}


@pytest.mark.asyncio
async def test_task_detail_carries_laboratory_and_run_status(client, session):
    ctx = await frozen_lab_process(session)
    run = (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        ctx.labs[0].id
    ]
    task = (await tasks_of(session, run.id))[0]
    authenticate(client, ctx.group_manager)

    resp = client.get(f'/tasks/{task.id}')

    body = resp.json()
    assert body['laboratory']['id'] == str(ctx.labs[0].id)
    assert body['activity_run_status'] == 'IN_PROGRESS'
