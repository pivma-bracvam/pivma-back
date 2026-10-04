"""Registro incompleto ou inválido é recusado (Spec 040, US4)."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import AuditEvent, SampleReceipt
from tests.api.routers.test_sample_receipt_router import (
    ORIGIN,
    lab_ready,
    vials_url,
)
from tests.factories.sample_receipt_factory import receipt_payload


def _post(client, ctx, payload):
    return client.post(
        vials_url(ctx.process_id, f'/{ctx.codes[0]}'),
        json=payload,
        headers=ORIGIN,
    )


def _fields(response):
    return {f['field'] for f in response.json()['detail']['fields']}


def _without(field):
    payload = receipt_payload()
    del payload[field]
    return payload


@pytest.mark.asyncio
async def test_missing_temperature_returns_422_with_field(session, client):
    ctx = await lab_ready(session, client)

    response = _post(client, ctx, _without('temperature_celsius'))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {'temperature_celsius'}


@pytest.mark.asyncio
async def test_non_numeric_temperature_returns_422_with_field(session, client):
    ctx = await lab_ready(session, client)

    response = _post(client, ctx, receipt_payload(temperature_celsius='abc'))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {'temperature_celsius'}


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', ['missing', 'quebrado'])
async def test_missing_or_unknown_package_state_returns_422(
    session, client, payload
):
    ctx = await lab_ready(session, client)
    body = (
        _without('package_state')
        if payload == 'missing'
        else receipt_payload(package_state=payload)
    )

    response = _post(client, ctx, body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {'package_state'}


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', ['missing', 'future'])
async def test_missing_or_future_opened_at_returns_422(
    session, client, payload
):
    ctx = await lab_ready(session, client)
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    body = (
        _without('opened_at')
        if payload == 'missing'
        else receipt_payload(opened_at=future)
    )

    response = _post(client, ctx, body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _fields(response) == {'opened_at'}


@pytest.mark.asyncio
async def test_refused_registration_writes_nothing(session, client):
    ctx = await lab_ready(session, client)

    _post(client, ctx, _without('temperature_celsius'))

    receipts = await session.scalar(
        select(func.count()).select_from(SampleReceipt)
    )
    events = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.event_type == 'SAMPLE_RECEIPT_REGISTERED')
    )
    assert receipts == 0
    assert events == 0
    vial = client.get(vials_url(ctx.process_id)).json()['data'][0]
    assert vial['status'] == 'pending'
