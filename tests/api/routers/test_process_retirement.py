from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    FormInstance,
    Phase,
    ProcessInstance,
    Task,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.process_retirement_factory import ProcessRetirementFactory


def _lifecycle(process_id, action='DELETE_DRAFT', justification='Descartar'):
    return f'/processes/{process_id}/lifecycle', {
        'action': action,
        'justification': justification,
    }


@pytest.mark.asyncio
async def test_owner_can_delete_unsubmitted_draft(client, session, user):
    process = await _create_process(session, user, 'Rascunho para excluir')
    authenticate(client, user)

    url, payload = _lifecycle(process)
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['id'] == str(process)
    assert body['action'] == 'DELETE_DRAFT'
    assert body['deleted'] is True
    assert await session.get(ProcessInstance, process) is None
    assert (
        client.get(f'/processes/{process}').status_code == HTTPStatus.NOT_FOUND
    )
    assert all(
        item['id'] != str(process)
        for item in client.get('/processes').json()['items']
    )
    response = client.post(url, json=payload)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_platform_can_delete_another_users_draft(
    client, session, user, bracvam_user
):
    process = await _create_process(session, user, 'Rascunho alheio')
    authenticate(client, bracvam_user)

    url, payload = _lifecycle(process)
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['deleted'] is True
    assert await session.get(ProcessInstance, process) is None


@pytest.mark.asyncio
async def test_unrelated_proponent_cannot_see_or_delete_draft(
    client, session, user, other_user
):
    process = await _create_process(session, user, 'Rascunho protegido')
    authenticate(client, other_user)

    url, payload = _lifecycle(process)
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_submitted_process_cannot_use_delete_draft(
    client, session, user
):
    process = await _create_submitted_process(
        session, user, status='SUBMISSION'
    )
    authenticate(client, user)

    url, payload = _lifecycle(process)
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_blank_justification_returns_stable_error(client, session, user):
    process = await _create_process(session, user, 'Rascunho com validação')
    authenticate(client, user)

    url, payload = _lifecycle(process, justification='   ')
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail']['code'] == 'invalid_justification'


@pytest.mark.asyncio
async def test_cancel_updates_pending_children_and_audit(
    client, session, user, bracvam_user
):
    process = await _create_submitted_process(
        session, user, status='AI_PRE_EVALUATION'
    )
    phase = await session.scalar(
        select(Phase)
        .where(Phase.process_instance_id == process)
        .order_by(Phase.order_index)
    )
    activity = await session.scalar(
        select(ActivityInstance)
        .where(ActivityInstance.process_instance_id == process)
        .order_by(ActivityInstance.order_index)
    )
    run = await session.scalar(
        select(ActivityRun)
        .where(ActivityRun.activity_instance_id == activity.id)
        .order_by(ActivityRun.run_number)
    )
    task = await session.scalar(
        select(Task).where(Task.activity_run_id == run.id)
    )
    phase.status = 'COMPLETED'
    activity.status = 'COMPLETED'
    run.status = 'COMPLETED'
    run.completed_at = run.started_at
    task.status = 'COMPLETED'
    task.completed_at = run.started_at
    form = await session.scalar(
        select(FormInstance).where(FormInstance.activity_run_id == run.id)
    )
    await session.commit()
    authenticate(client, bracvam_user)

    url, payload = _lifecycle(process, 'CANCEL', 'Interromper validação')
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'CANCELLED'
    assert response.json()['deleted'] is False

    saved = await session.get(ProcessInstance, process)
    assert saved.status == 'CANCELLED'
    assert saved.closed_at is not None
    assert saved.closure_reason == 'Interromper validação'
    phases = list(
        await session.scalars(
            select(Phase).where(Phase.process_instance_id == process)
        )
    )
    activities = list(
        await session.scalars(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process
            )
        )
    )
    runs = list(
        await session.scalars(
            select(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == process)
        )
    )
    tasks = list(
        await session.scalars(
            select(Task)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == process)
        )
    )
    assert all(item.status in {'CANCELLED', 'COMPLETED'} for item in phases)
    assert all(
        item.status in {'CANCELLED', 'COMPLETED'} for item in activities
    )
    assert all(item.status in {'CANCELLED', 'COMPLETED'} for item in runs)
    assert all(item.status in {'CANCELLED', 'COMPLETED'} for item in tasks)
    assert phase.status == 'COMPLETED'
    assert activity.status == 'COMPLETED'
    assert run.status == 'COMPLETED'
    assert task.status == 'COMPLETED'
    assert form.is_submitted is False
    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process,
            AuditEvent.event_type == 'PROCESS_CANCELLED',
        )
    )
    assert event.user_id == bracvam_user.id
    assert event.context_data['justification'] == 'Interromper validação'
    assert event.context_data['cancelled_counts']['tasks'] == sum(
        item.status == 'CANCELLED' for item in tasks
    )


@pytest.mark.asyncio
async def test_cancel_blocks_form_write(client, session, user, bracvam_user):
    process = await _create_submitted_process(
        session, user, status='AI_PRE_EVALUATION'
    )
    authenticate(client, bracvam_user)
    url, payload = _lifecycle(process, 'CANCEL', 'Parar')
    assert client.post(url, json=payload).status_code == HTTPStatus.OK

    authenticate(client, user)
    response = client.put(
        f'/processes/{process}',
        json={'title': 'Tentativa', 'values': {}},
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'
    form_url = f'/processes/{process}/activities/proposal_submission/form'
    response = client.put(form_url, json={'values': {}})
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'
    response = client.post(form_url, json={'values': {}})
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_owner_cannot_cancel_submitted_process(client, session, user):
    process = await _create_submitted_process(session, user)
    authenticate(client, user)

    url, payload = _lifecycle(
        process, 'CANCEL', 'Sem permissão administrativa'
    )
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'


@pytest.mark.asyncio
async def test_triage_decision_is_blocked_after_cancellation(
    client, session, user, bracvam_user
):
    process = await _create_submitted_process(session, user, status='TRIAGE')
    authenticate(client, bracvam_user)
    url, payload = _lifecycle(process, 'CANCEL', 'Parar triagem')
    assert client.post(url, json=payload).status_code == HTTPStatus.OK

    response = client.post(
        f'/processes/{process}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Não deve avançar'},
        headers={'Origin': 'https://testserver'},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_cancel_terminal_process_is_rejected(
    client, session, user, bracvam_user
):
    closed = await _create_terminal_process(session, user, 'Já encerrado')
    cancelled = await _create_terminal_process(
        session, user, 'Já cancelado', status='CANCELLED'
    )
    authenticate(client, bracvam_user)

    for process in (closed, cancelled):
        url, payload = _lifecycle(process, 'CANCEL', 'Não reabrir')
        response = client.post(url, json=payload)
        assert response.status_code == HTTPStatus.CONFLICT
        assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_archive_closed_process_is_hidden_from_default_list(
    client, session, user, bracvam_user
):
    process = await _create_terminal_process(session, user, 'Processo fechado')
    authenticate(client, bracvam_user)

    url, payload = _lifecycle(process, 'ARCHIVE', 'Guardar histórico')
    response = client.post(url, json=payload)
    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'ARCHIVED'
    assert response.json()['deleted'] is False

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process,
            AuditEvent.event_type == 'PROCESS_ARCHIVED',
        )
    )
    assert event.context_data['previous_status'] == 'CLOSED'
    assert event.context_data['justification'] == 'Guardar histórico'
    assert all(
        item['id'] != process
        for item in client.get('/processes').json()['items']
    )
    archived = client.get('/processes', params={'status': 'ARCHIVED'})
    assert archived.status_code == HTTPStatus.OK
    assert archived.json()['items'][0]['id'] == str(process)
    timeline = client.get(f'/processes/{process}/timeline')
    assert timeline.status_code == HTTPStatus.OK
    assert any(
        item['event_type'] == 'PROCESS_ARCHIVED'
        for item in timeline.json()['events']
    )
    form_url = f'/processes/{process}/activities/proposal_submission/form'
    response = client.put(form_url, json={'values': {}})
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_archive_cancelled_process_and_keep_actions_empty(
    client, session, user, bracvam_user
):
    process = await _create_terminal_process(
        session, user, 'Cancelado para arquivar', status='CANCELLED'
    )
    authenticate(client, bracvam_user)

    url, payload = _lifecycle(process, 'ARCHIVE', 'Guardar cancelado')
    response = client.post(url, json=payload)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'ARCHIVED'
    assert response.json()['available_actions'] == []
    assert (
        client.get(f'/processes/{process}').json()['available_actions'] == []
    )


@pytest.mark.asyncio
async def test_archive_draft_or_active_process_is_rejected(
    client, session, user, bracvam_user
):
    draft = await _create_process(session, user, 'Rascunho não arquivável')
    active = await _create_submitted_process(session, user, status='TRIAGE')
    authenticate(client, bracvam_user)

    for process in (draft, active):
        url, payload = _lifecycle(process, 'ARCHIVE', 'Transição inválida')
        response = client.post(url, json=payload)
        assert response.status_code == HTTPStatus.CONFLICT
        assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_non_platform_cannot_query_archived(
    client, session, user, bracvam_user
):
    process = await _create_terminal_process(
        session, user, 'Histórico privado'
    )
    authenticate(client, bracvam_user)
    url, payload = _lifecycle(process, 'ARCHIVE', 'Arquivar')
    assert client.post(url, json=payload).status_code == HTTPStatus.OK

    authenticate(client, user)
    response = client.get('/processes', params={'status': 'ARCHIVED'})
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'


@pytest.mark.asyncio
async def test_detail_exposes_available_actions(
    client, session, user, bracvam_user
):
    draft = await _create_process(session, user, 'Ações do rascunho')
    authenticate(client, user)
    assert client.get(f'/processes/{draft}').json()['available_actions'] == [
        'DELETE_DRAFT'
    ]

    submitted = await _create_submitted_process(session, user)
    authenticate(client, bracvam_user)
    actions = client.get(f'/processes/{submitted}').json()['available_actions']
    assert actions == ['CANCEL']


async def _create_process(session, owner, title):
    process = await ProcessRetirementFactory(session).draft(owner, title)
    return process.id


async def _create_submitted_process(session, owner, *, status='TRIAGE'):
    process = await ProcessRetirementFactory(session).submitted(
        owner, status=status
    )
    return process.id


async def _create_terminal_process(session, owner, title, *, status='CLOSED'):
    process = await ProcessRetirementFactory(session).terminal(
        owner, title=title, status=status
    )
    return process.id
