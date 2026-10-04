"""Frasco fora de ordem abre inconformidade (Spec 040, US6)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import ActivityRun, Task
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_sample_receipt_router import (
    lab_ready,
    register,
)
from tests.factories.laboratory_run_factory import activity, runs_by_lab
from tests.factories.sample_receipt_factory import codes_of


def nc_url(process_id, suffix=''):
    return f'/processes/{process_id}/sample-receipt/nonconformities{suffix}'


async def resolution_runs(session, process_id):
    act = await activity(session, process_id, 'sample_receipt_resolution')
    return list(
        await session.scalars(
            select(ActivityRun)
            .where(ActivityRun.activity_instance_id == act.id)
            .order_by(ActivityRun.run_number)
            .execution_options(populate_existing=True)
        )
    )


@pytest.mark.asyncio
async def test_warm_vial_returns_success_with_nonconformity(session, client):
    ctx = await lab_ready(session, client)

    response = register(
        client, ctx.process_id, ctx.codes[0], temperature_celsius=21.0
    )

    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body['conforming'] is False
    assert body['deviations'] == ['temperature_out_of_range']
    assert body['laboratory_receipt_status'] == 'awaiting_decision'
    assert body['vial']['status'] == 'awaiting_decision'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('overrides', 'deviations'),
    [
        ({'package_state': 'damaged'}, ['package_damaged']),
        ({'package_state': 'violated'}, ['package_violated']),
        (
            {'package_state': 'damaged', 'temperature_celsius': 21.0},
            ['temperature_out_of_range', 'package_damaged'],
        ),
    ],
)
async def test_package_state_gives_its_deviation(
    session, client, overrides, deviations
):
    ctx = await lab_ready(session, client)

    response = register(client, ctx.process_id, ctx.codes[0], **overrides)

    assert response.json()['deviations'] == deviations


@pytest.mark.asyncio
async def test_lab_run_stays_open_with_pending_decision(session, client):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], package_state='damaged')

    response = register(client, ctx.process_id, ctx.codes[1])

    assert response.json()['laboratory_receipt_status'] == 'awaiting_decision'
    runs = await runs_by_lab(session, ctx.process_id, 'sample_receipt')
    assert runs[ctx.labs[0].id].status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_first_nonconformity_opens_one_task_for_selection_group(
    session, client
):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], package_state='damaged')
    authenticate(client, ctx.lab_users[1])
    other = (await codes_of(session, ctx, 1))[0]
    register(client, ctx.process_id, other, package_state='damaged')

    runs = await resolution_runs(session, ctx.process_id)
    tasks = list(
        await session.scalars(
            select(Task).where(Task.activity_run_id == runs[0].id)
        )
    )
    act = await activity(session, ctx.process_id, 'sample_receipt_resolution')

    assert [r.status for r in runs] == ['IN_PROGRESS']
    assert [(t.status, t.assigned_role) for t in tasks] == [
        ('READY', 'sample_selection_group')
    ]
    assert act.status == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_selection_group_lists_nonconformity_details(session, client):
    ctx = await lab_ready(session, client)
    register(
        client,
        ctx.process_id,
        ctx.codes[0],
        temperature_celsius=21.0,
        notes='Gelo derretido.',
    )
    authenticate(client, ctx.selector)

    response = client.get(nc_url(ctx.process_id))

    assert response.status_code == HTTPStatus.OK, response.text
    item = response.json()['data'][0]
    assert item['status'] == 'OPEN'
    assert item['code'] == ctx.codes[0]
    assert item['laboratory']['id'] == str(ctx.labs[0].id)
    assert item['substance']['cas_number'] in {
        s['cas_number'] for s in ctx.substances
    }
    assert item['expected_temperature'] == {
        'regime': 'refrigerated',
        'min': 2.0,
        'max': 8.0,
    }
    assert item['receipt']['notes'] == 'Gelo derretido.'
    assert item['deviations'] == ['temperature_out_of_range']
    assert item['decision'] is None


@pytest.mark.asyncio
async def test_nonconformity_list_filters_and_paginates(session, client):
    ctx = await lab_ready(session, client)
    for code in ctx.codes:
        register(client, ctx.process_id, code, package_state='damaged')
    authenticate(client, ctx.selector)
    first = client.get(nc_url(ctx.process_id)).json()['data'][0]
    client.post(
        nc_url(ctx.process_id, f'/{first["id"]}/decision'),
        json={'decision': 'accept_with_caveat', 'justification': 'Ok.'},
        headers={'Origin': 'https://testserver'},
    )

    opened = client.get(nc_url(ctx.process_id), params={'status': 'open'})
    resolved = client.get(
        nc_url(ctx.process_id), params={'status': 'resolved'}
    )
    page = client.get(nc_url(ctx.process_id), params={'per_page': 1})

    assert [i['status'] for i in opened.json()['data']] == ['OPEN']
    assert [i['id'] for i in resolved.json()['data']] == [first['id']]
    assert resolved.json()['filters_applied'] == {'status': 'resolved'}
    assert page.json()['pagination']['total_items'] == 2  # noqa: PLR2004
    assert len(page.json()['data']) == 1


@pytest.mark.asyncio
async def test_nonconformity_list_denied_to_other_roles(
    session, client, bracvam_user
):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], package_state='damaged')

    expected = [
        (ctx.lab_users[0], HTTPStatus.NOT_FOUND),
        (ctx.group_manager, HTTPStatus.NOT_FOUND),
        (bracvam_user, HTTPStatus.FORBIDDEN),
    ]
    for user, status in expected:
        authenticate(client, user)
        assert client.get(nc_url(ctx.process_id)).status_code == status


@pytest.mark.asyncio
async def test_nonconformity_carries_alert_text(session, client):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], package_state='violated')
    authenticate(client, ctx.selector)

    item = client.get(nc_url(ctx.process_id)).json()['data'][0]

    assert item['alert'] == (
        f'Alerta de Recebimento: o laboratório {ctx.labs[0].name} '
        f'registrou desvio físico no frasco {ctx.codes[0]}.'
    )
