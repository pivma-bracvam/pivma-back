"""`can_act`, laboratório e status da execução em `/tasks` (Spec 036)."""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import frozen_lab_process


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
