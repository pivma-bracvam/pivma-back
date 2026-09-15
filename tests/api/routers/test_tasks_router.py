from datetime import datetime, timedelta
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
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo para Teste de Tarefas',
        },
    )
    process_id = resp.json()['id']

    # 2. List all tasks
    tasks_resp = client.get('/tasks')
    assert tasks_resp.status_code == HTTPStatus.OK
    tasks = tasks_resp.json()
    assert len(tasks) >= 1

    prop_task = next(
        t
        for t in tasks
        if t['process_id'] == process_id and t['assigned_role'] == 'proponent'
    )
    assert prop_task['status'] == 'READY'

    # 3. Filter tasks by role
    prop_filter_resp = client.get('/tasks?role=proponent')
    assert prop_filter_resp.status_code == HTTPStatus.OK
    filtered = prop_filter_resp.json()
    assert filtered
    assert all(t['assigned_role'] == 'proponent' for t in filtered)

    # 4. Get task detail
    task_detail_resp = client.get(f'/tasks/{prop_task["id"]}')
    assert task_detail_resp.status_code == HTTPStatus.OK
    task_detail = task_detail_resp.json()
    assert task_detail['activity_key'] == 'proposal_submission'
    assert not task_detail['is_blocked']


@pytest.mark.asyncio
async def test_task_listing_reflects_normalized_proponent_assigned_role(
    client, session
):
    """`assigned_role` sai normalizado ('proponent', não 'PROPONENT') desde

    a instanciação (Spec 018, research.md D5).
    """
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo para papel legado da tarefa',
        },
    )
    process_id = resp.json()['id']

    tasks_resp = client.get('/tasks')
    assert tasks_resp.status_code == HTTPStatus.OK
    prop_task = next(
        t
        for t in tasks_resp.json()
        if t['process_id'] == process_id and t['assigned_role'] == 'proponent'
    )
    assert prop_task['assigned_role'] == 'proponent'


@pytest.mark.asyncio
async def test_task_due_date_is_populated_from_template_sla(client, session):
    """Spec 024 - `due_date` deixa de ser sempre nulo em `GET /tasks` e

    passa a existir em `GET /tasks/{id}` (contracts/tasks-due-date.md).
    `pre_validated_method.proposal_submission` declara `sla_hours=168`.
    """
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo para Teste de Prazo',
        },
    )
    process_id = resp.json()['id']

    before = datetime.utcnow()

    tasks_resp = client.get('/tasks', params={'process_id': process_id})
    assert tasks_resp.status_code == HTTPStatus.OK
    prop_task = next(
        t
        for t in tasks_resp.json()
        if t['assigned_role'] == 'proponent'
    )
    assert prop_task['due_date'] is not None
    list_due_date = datetime.fromisoformat(prop_task['due_date'])

    # Tolerância generosa em torno de `sla_hours=168` — o teste não controla
    # `run_started_at` diretamente, só o momento em que a request foi feita.
    assert (
        before + timedelta(hours=168) - timedelta(minutes=1)
        <= list_due_date
        <= before + timedelta(hours=168) + timedelta(minutes=1)
    )

    detail_resp = client.get(f'/tasks/{prop_task["id"]}')
    assert detail_resp.status_code == HTTPStatus.OK
    detail_due_date = detail_resp.json()['due_date']
    assert detail_due_date is not None
    # `GET /tasks` e `GET /tasks/{id}` não podem divergir para a mesma
    # tarefa (FR-003 aplicado ao par de endpoints).
    assert datetime.fromisoformat(detail_due_date) == list_due_date
