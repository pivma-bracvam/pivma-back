"""O processo expõe só o ciclo de vida (Spec 030, US1)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import AuditEvent
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

FLOW_STATUSES = {'SUBMISSION', 'AI_PRE_EVALUATION', 'TRIAGE', 'PLANNING'}
VALUES = {'method_title': 'Ensaio RhCE para irritação'}


async def _proponent(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    client.headers['Origin'] = 'https://testserver'
    authenticate(client, user)
    return user


def _create(client, title='Processo 1'):
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': title},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _submit(client, pid):
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _decide(client, pid, outcome):
    return client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': outcome, 'justification': 'Justificativa.'},
    )


@pytest.mark.asyncio
async def test_create_process_returns_open(client, session):
    await _proponent(client, session)

    assert _create(client)['status'] == 'OPEN'


@pytest.mark.asyncio
async def test_process_stays_open_after_submission(client, session):
    await _proponent(client, session)
    pid = _create(client)['id']

    _submit(client, pid)

    assert client.get(f'/processes/{pid}').json()['status'] == 'OPEN'


@pytest.mark.asyncio
async def test_triage_approval_response_reports_open(
    client, session, bracvam_user
):
    await _proponent(client, session)
    pid = _create(client)['id']
    _submit(client, pid)
    authenticate(client, bracvam_user)

    body = _decide(client, pid, 'APPROVED').json()

    assert body['process_status'] == 'OPEN'
    assert 'new_process_status' not in body
    assert body['next_activity_run'] is None


@pytest.mark.asyncio
async def test_triage_rejection_closes_process(client, session, bracvam_user):
    await _proponent(client, session)
    pid = _create(client)['id']
    _submit(client, pid)
    authenticate(client, bracvam_user)

    response = _decide(client, pid, 'REJECTED')

    assert response.json()['process_status'] == 'CLOSED'
    assert client.get(f'/processes/{pid}').json()['status'] == 'CLOSED'


@pytest.mark.asyncio
async def test_list_filters_by_lifecycle(client, session, bracvam_user):
    await _proponent(client, session)
    open_pid = _create(client, 'Aberto')['id']
    closed_pid = _create(client, 'Fechado')['id']
    _submit(client, closed_pid)
    authenticate(client, bracvam_user)
    _decide(client, closed_pid, 'REJECTED')

    items = client.get(
        '/processes', params={'status': 'CLOSED', 'size': 100}
    ).json()['items']

    ids = {item['id'] for item in items}
    assert closed_pid in ids
    assert open_pid not in ids


@pytest.mark.asyncio
async def test_list_rejects_flow_status_filter(client, session):
    await _proponent(client, session)

    response = client.get('/processes', params={'status': 'TRIAGE'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_triage_decision_before_submission_is_conflict(
    client, session, bracvam_user
):
    await _proponent(client, session)
    pid = _create(client)['id']
    authenticate(client, bracvam_user)

    response = _decide(client, pid, 'APPROVED')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_submission_update_after_submit_is_conflict(client, session):
    await _proponent(client, session)
    pid = _create(client)['id']
    _submit(client, pid)

    response = client.patch(f'/processes/{pid}', json={'title': 'Novo'})

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_no_response_contains_flow_status(client, session, bracvam_user):
    await _proponent(client, session)
    created = _create(client)
    pid = created['id']
    bodies = [created, client.get(f'/processes/{pid}').json()]
    bodies += client.get('/processes', params={'size': 100}).json()['items']
    _submit(client, pid)
    bodies.append(client.get(f'/processes/{pid}').json())
    authenticate(client, bracvam_user)
    bodies.append(_decide(client, pid, 'APPROVED').json())
    bodies.append(client.get(f'/processes/{pid}').json())

    for body in bodies:
        for key in ('status', 'process_status'):
            assert body.get(key) not in FLOW_STATUSES, body


@pytest.mark.asyncio
async def test_delete_and_archive_audit_record_lifecycle_statuses(
    client, session, bracvam_user
):
    await _proponent(client, session)
    pid = _create(client)['id']

    assert client.delete(f'/processes/{pid}').status_code == (
        HTTPStatus.NO_CONTENT
    )
    authenticate(client, bracvam_user)
    archived = client.patch(f'/processes/{pid}/archive')
    assert archived.status_code == HTTPStatus.OK, archived.text

    events = {
        event.event_type: event.context_data
        for event in await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == pid,
                AuditEvent.event_type.in_([
                    'PROCESS_DELETED',
                    'PROCESS_ARCHIVED',
                ]),
            )
        )
    }
    assert events['PROCESS_DELETED']['previous_status'] == 'OPEN'
    assert events['PROCESS_DELETED']['result_status'] == 'CANCELLED'
    assert events['PROCESS_ARCHIVED']['previous_status'] == 'CANCELLED'
    assert events['PROCESS_ARCHIVED']['result_status'] == 'ARCHIVED'
