from http import HTTPStatus

import pytest
from pivma.bootstrap_process_templates import bootstrap_all_templates

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_list_and_filter_tasks(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. Create process
    resp = client.post(
        "/processes",
        json={
            "template_key": "full_validation",
            "title": "Processo para Teste de Tarefas",
        },
    )
    process_id = resp.json()["id"]

    # 2. List all tasks
    tasks_resp = client.get("/tasks")
    assert tasks_resp.status_code == HTTPStatus.OK
    tasks = tasks_resp.json()
    assert len(tasks) >= 1

    prop_task = next(
        t
        for t in tasks
        if t["process_id"] == process_id and t["assigned_role"] == "PROPONENT"
    )
    assert prop_task["status"] == "READY"

    # 3. Filter tasks by role
    prop_filter_resp = client.get("/tasks?role=PROPONENT")
    assert prop_filter_resp.status_code == HTTPStatus.OK
    filtered = prop_filter_resp.json()
    assert all(t["assigned_role"] == "PROPONENT" for t in filtered)

    # 4. Get task detail
    task_detail_resp = client.get(f"/tasks/{prop_task['id']}")
    assert task_detail_resp.status_code == HTTPStatus.OK
    task_detail = task_detail_resp.json()
    assert task_detail["activity_key"] == "proposal_submission"
    assert not task_detail["is_blocked"]


@pytest.mark.asyncio
async def test_task_listing_preserves_legacy_proponent_assigned_role(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.post(
        "/processes",
        json={
            "template_key": "full_validation",
            "title": "Processo para papel legado da tarefa",
        },
    )
    process_id = resp.json()["id"]

    tasks_resp = client.get("/tasks")
    assert tasks_resp.status_code == HTTPStatus.OK
    prop_task = next(
        t
        for t in tasks_resp.json()
        if t["process_id"] == process_id and t["assigned_role"] == "PROPONENT"
    )
    assert prop_task["assigned_role"] == "PROPONENT"
