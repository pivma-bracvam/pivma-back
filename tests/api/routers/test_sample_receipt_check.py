"""Pré-verificação do registro e busca de frascos (Spec 040)."""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    AuditEvent,
    SampleReceipt,
    SampleReceiptNonconformity,
)
from tests.api.routers.test_sample_receipt_router import (
    ORIGIN,
    lab_ready,
    register,
    vials_url,
)
from tests.factories.sample_receipt_factory import codes_of, receipt_payload


def check(client, ctx, code, **overrides):
    return client.post(
        vials_url(ctx.process_id, f'/{code}/check'),
        json=receipt_payload(**overrides),
        headers=ORIGIN,
    )


async def _count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


@pytest.mark.asyncio
async def test_check_in_range_says_conditions_are_fine(session, client):
    ctx = await lab_ready(session, client)

    response = check(client, ctx, ctx.codes[0])

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['conforming'] is True
    assert response.json()['deviations'] == []
    assert 'dentro do padrão' in response.json()['message']


@pytest.mark.asyncio
async def test_check_out_of_range_warns_with_expected_range(session, client):
    ctx = await lab_ready(session, client)

    response = check(
        client,
        ctx,
        ctx.codes[0],
        temperature_celsius=21,
        package_state='damaged',
    )

    body = response.json()
    assert body['conforming'] is False
    assert body['deviations'] == [
        'temperature_out_of_range',
        'package_damaged',
    ]
    assert 'esperado de 2 °C a 8 °C' in body['message']
    assert 'embalagem avariada' in body['message']
    assert 'inconformidade será registrada' in body['message']


@pytest.mark.asyncio
async def test_check_writes_nothing(session, client):
    ctx = await lab_ready(session, client)

    check(client, ctx, ctx.codes[0], temperature_celsius=21)

    assert await _count(session, SampleReceipt) == 0
    assert await _count(session, SampleReceiptNonconformity) == 0
    events = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.event_type.like('SAMPLE_RECEIPT%'))
    )
    assert events == 0
    vial = client.get(vials_url(ctx.process_id)).json()['data'][0]
    assert vial['status'] == 'pending'


@pytest.mark.asyncio
async def test_check_with_missing_fields_returns_422_per_field(
    session, client
):
    ctx = await lab_ready(session, client)

    response = client.post(
        vials_url(ctx.process_id, f'/{ctx.codes[0]}/check'),
        json={'opened_at': receipt_payload()['opened_at']},
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    fields = {f['field'] for f in response.json()['detail']['fields']}
    assert fields == {'temperature_celsius', 'package_state'}


@pytest.mark.asyncio
async def test_check_vial_of_other_lab_returns_404(session, client):
    ctx = await lab_ready(session, client)
    other = (await codes_of(session, ctx, 1))[0]

    assert check(client, ctx, other).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_check_registered_vial_returns_409(session, client):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0])

    response = check(client, ctx, ctx.codes[0])

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'vial_already_registered'


@pytest.mark.asyncio
async def test_vial_list_items_bring_handling_and_range(session, client):
    ctx = await lab_ready(session, client)

    vial = client.get(vials_url(ctx.process_id)).json()['data'][0]

    assert vial['safe_handling_instructions']
    assert vial['lot']
    assert vial['storage_temperature_regime'] == 'refrigerated'
    assert vial['ghs_hazard_pictograms'] == ['GHS07']


@pytest.mark.asyncio
async def test_vial_search_is_case_insensitive_and_own_lab_only(
    session, client
):
    ctx = await lab_ready(session, client)
    other = (await codes_of(session, ctx, 1))[0]

    found = client.get(
        vials_url(ctx.process_id), params={'search': ctx.codes[0].lower()}
    ).json()
    foreign = client.get(
        vials_url(ctx.process_id), params={'search': other}
    ).json()

    assert [v['code'] for v in found['data']] == [ctx.codes[0]]
    assert found['filters_applied'] == {'search': ctx.codes[0].lower()}
    assert foreign['data'] == []
