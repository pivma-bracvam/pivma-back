"""Registro de recebimento de frascos (Spec 040, US3)."""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    AuditEvent,
    ProcessInstance,
    Task,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import activity, runs_by_lab
from tests.factories.sample_receipt_factory import (
    codes_of,
    receipt_payload,
    receipt_process,
)

ORIGIN = {'Origin': 'https://testserver'}


def vials_url(process_id, suffix=''):
    return f'/processes/{process_id}/sample-receipt/vials{suffix}'


def register(client, process_id, code, **overrides):
    return client.post(
        vials_url(process_id, f'/{code}'),
        json=receipt_payload(**overrides),
        headers=ORIGIN,
    )


async def lab_ready(session, client, index=0, **kwargs):
    """Recebimento aberto; o usuário do laboratório `index` autenticado."""
    ctx = await receipt_process(session, **kwargs)
    ctx.codes = await codes_of(session, ctx, index)
    authenticate(client, ctx.lab_users[index])
    return ctx


@pytest.mark.asyncio
async def test_conforming_receipt_returns_201_and_received(session, client):
    ctx = await lab_ready(session, client)

    response = register(client, ctx.process_id, ctx.codes[0])

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body['conforming'] is True
    assert body['deviations'] == []
    assert body['vial']['status'] == 'received'
    assert body['vial']['receipt']['temperature_celsius'] == 4.5  # noqa: PLR2004
    assert body['laboratory_receipt_status'] == 'in_progress'


@pytest.mark.asyncio
async def test_last_vial_completes_lab_run_and_task_only(session, client):
    ctx = await lab_ready(session, client)

    for code in ctx.codes:
        response = register(client, ctx.process_id, code)
        assert response.status_code == HTTPStatus.CREATED, response.text

    assert response.json()['laboratory_receipt_status'] == 'completed'
    runs = await runs_by_lab(session, ctx.process_id, 'sample_receipt')
    assert runs[ctx.labs[0].id].status == 'COMPLETED'
    assert runs[ctx.labs[1].id].status == 'IN_PROGRESS'
    task_status = await session.scalar(
        select(Task.status).where(
            Task.activity_run_id == runs[ctx.labs[0].id].id
        )
    )
    assert task_status == 'COMPLETED'
    act = await activity(session, ctx.process_id, 'sample_receipt')
    assert act.status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_second_registration_of_same_vial_returns_409(session, client):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0])

    response = register(
        client, ctx.process_id, ctx.codes[0], temperature_celsius=30
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'vial_already_registered'
    vial = client.get(vials_url(ctx.process_id)).json()['data'][0]
    assert vial['receipt']['temperature_celsius'] == 4.5  # noqa: PLR2004


@pytest.mark.asyncio
@pytest.mark.parametrize('temperature', [2.0, 8.0])
async def test_temperature_on_range_limit_is_conforming(
    session, client, temperature
):
    ctx = await lab_ready(session, client)

    response = register(
        client, ctx.process_id, ctx.codes[0], temperature_celsius=temperature
    )

    assert response.json()['conforming'] is True


@pytest.mark.asyncio
async def test_substance_without_range_accepts_any_temperature(
    session, client
):
    ctx = await lab_ready(
        session,
        client,
        storage_temperature_regime=None,
        storage_temperature_min=None,
        storage_temperature_max=None,
    )

    response = register(
        client, ctx.process_id, ctx.codes[0], temperature_celsius=37.0
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    assert response.json()['conforming'] is True


@pytest.mark.asyncio
async def test_registration_after_waiver_returns_409(session, client):
    ctx = await lab_ready(session, client)
    authenticate(client, ctx.group_manager)
    waived = client.post(
        f'/processes/{ctx.process_id}/phases/phase_3_validation_execution/'
        'laboratory-waivers',
        json={'laboratory_id': str(ctx.labs[0].id), 'reason': 'Quebra.'},
        headers=ORIGIN,
    )
    assert waived.status_code == HTTPStatus.CREATED, waived.text
    authenticate(client, ctx.lab_users[0])

    response = register(client, ctx.process_id, ctx.codes[0])

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_registration_in_archived_process_returns_409(session, client):
    ctx = await lab_ready(session, client)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.status = 'ARCHIVED'
    await session.commit()

    response = register(client, ctx.process_id, ctx.codes[0])

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_vial_list_is_paginated_and_ordered(session, client):
    ctx = await lab_ready(session, client)

    first = client.get(vials_url(ctx.process_id), params={'per_page': 1})
    second = client.get(
        vials_url(ctx.process_id), params={'per_page': 1, 'page': 2}
    )

    assert first.status_code == HTTPStatus.OK
    assert first.json()['pagination']['total_items'] == 2  # noqa: PLR2004
    assert first.json()['sort'] == {'by': 'laboratory', 'order': 'asc'}
    assert [v['code'] for v in first.json()['data']] == ctx.codes[:1]
    assert [v['code'] for v in second.json()['data']] == ctx.codes[1:]


@pytest.mark.asyncio
async def test_registration_event_has_ids_only(session, client):
    ctx = await lab_ready(session, client)
    response = register(client, ctx.process_id, ctx.codes[0])
    receipt_id = response.json()['vial']['receipt']['id']

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == ctx.process_id,
            AuditEvent.event_type == 'SAMPLE_RECEIPT_REGISTERED',
        )
    )

    assert event.context_data['laboratory_id'] == str(ctx.labs[0].id)
    assert event.context_data['receipt_id'] == receipt_id
    assert event.context_data['conforming'] is True
    assert event.context_data['deviations'] == []
    assert 'blind_sample_code_id' in event.context_data
    assert ctx.codes[0] not in str(event.context_data)


@pytest.mark.asyncio
async def test_lab_completion_records_one_completed_event(session, client):
    ctx = await lab_ready(session, client)
    for code in ctx.codes:
        register(client, ctx.process_id, code)

    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.process_instance_id == ctx.process_id,
            AuditEvent.event_type == 'LABORATORY_RUN_COMPLETED',
        )
    )

    assert count == 1
