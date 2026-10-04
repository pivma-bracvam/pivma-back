"""Decisão do Grupo de Seleção sobre a inconformidade (Spec 040, US7)."""

import json
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import (
    AuditEvent,
    BlindSampleCode,
    LaboratoryWaiver,
    ProcessInstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_sample_nonconformity_router import (
    nc_url,
    resolution_runs,
)
from tests.api.routers.test_sample_receipt_router import (
    ORIGIN,
    lab_ready,
    register,
    vials_url,
)
from tests.factories.laboratory_run_factory import runs_by_lab
from tests.factories.sample_receipt_factory import codes_of


async def with_problem(session, client, *, broken=(0,), **kwargs):
    """Lab 0 registra em ordem os frascos fora de `broken`, e o resto
    avariado; o Grupo de Seleção fica autenticado."""
    ctx = await lab_ready(session, client, **kwargs)
    for index, code in enumerate(ctx.codes):
        state = 'damaged' if index in broken else 'intact'
        register(client, ctx.process_id, code, package_state=state)
    authenticate(client, ctx.selector)
    ctx.items = client.get(nc_url(ctx.process_id)).json()['data']
    return ctx


def decide(client, ctx, item, decision, justification='Avaliado.'):
    return client.post(
        nc_url(ctx.process_id, f'/{item["id"]}/decision'),
        json={'decision': decision, 'justification': justification},
        headers=ORIGIN,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'body',
    [
        {'decision': 'resend'},
        {'decision': 'resend', 'justification': '   '},
        {'decision': 'trocar', 'justification': 'x'},
    ],
)
async def test_invalid_decision_body_returns_422(session, client, body):
    ctx = await with_problem(session, client)

    response = client.post(
        nc_url(ctx.process_id, f'/{ctx.items[0]["id"]}/decision'),
        json=body,
        headers=ORIGIN,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    item = client.get(nc_url(ctx.process_id)).json()['data'][0]
    assert item['status'] == 'OPEN'


@pytest.mark.asyncio
async def test_accept_with_caveat_completes_lab_run(session, client):
    ctx = await with_problem(session, client)

    response = decide(client, ctx, ctx.items[0], 'accept_with_caveat')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['decision'] == 'accept_with_caveat'
    runs = await runs_by_lab(session, ctx.process_id, 'sample_receipt')
    assert runs[ctx.labs[0].id].status == 'COMPLETED'
    authenticate(client, ctx.lab_users[0])
    statuses = {
        v['code']: v['status']
        for v in client.get(vials_url(ctx.process_id)).json()['data']
    }
    assert statuses[ctx.codes[0]] == 'accepted_with_caveat'


@pytest.mark.asyncio
async def test_resend_swaps_code_and_debits_reserve(session, client):
    ctx = await with_problem(session, client, reserve=2)

    response = decide(client, ctx, ctx.items[0], 'resend')

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body['substance']['reserve_vials_count'] == 1
    new_code = body['replacement_code']
    new = await session.scalar(
        select(BlindSampleCode).where(BlindSampleCode.code == new_code)
    )
    old = await session.scalar(
        select(BlindSampleCode)
        .where(BlindSampleCode.code == ctx.codes[0])
        .execution_options(skip_soft_delete_filter=True)
    )
    assert old.deleted_at is not None
    assert new.replaces_code_id == old.id
    assert (new.substance_id, new.laboratory_id) == (
        old.substance_id,
        old.laboratory_id,
    )
    runs = await runs_by_lab(session, ctx.process_id, 'sample_receipt')
    assert runs[ctx.labs[0].id].status == 'IN_PROGRESS'
    authenticate(client, ctx.lab_users[0])
    statuses = {
        v['code']: v['status']
        for v in client.get(vials_url(ctx.process_id)).json()['data']
    }
    assert statuses[new_code] == 'pending'
    assert statuses[ctx.codes[0]] == 'replaced'


@pytest.mark.asyncio
async def test_resend_without_reserve_returns_409(session, client):
    ctx = await with_problem(session, client, reserve=0)

    response = decide(client, ctx, ctx.items[0], 'resend')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'no_reserve_vials'
    assert await codes_of(session, ctx, 0) == ctx.codes
    item = client.get(nc_url(ctx.process_id)).json()['data'][0]
    assert item['status'] == 'OPEN'


@pytest.mark.asyncio
async def test_lab_list_never_links_new_and_old_code(session, client):
    ctx = await with_problem(session, client)
    decide(client, ctx, ctx.items[0], 'resend', 'Segredo do Grupo.')

    authenticate(client, ctx.lab_users[0])
    text = json.dumps(client.get(vials_url(ctx.process_id)).json())

    for word in ('replaces', 'replacement', 'justification', 'Segredo'):
        assert word not in text


@pytest.mark.asyncio
async def test_disqualify_waives_lab_and_closes_its_other_items(
    session, client
):
    ctx = await with_problem(session, client, broken=(0, 1))
    first, second = ctx.items

    response = decide(client, ctx, first, 'disqualify', 'Lote inutilizado.')

    assert response.status_code == HTTPStatus.OK, response.text
    runs = await runs_by_lab(session, ctx.process_id, 'sample_receipt')
    assert runs[ctx.labs[0].id].status == 'WAIVED'
    assert runs[ctx.labs[1].id].status == 'IN_PROGRESS'
    waiver = await session.scalar(select(LaboratoryWaiver))
    assert waiver.reason == 'Lote inutilizado.'
    items = {
        i['id']: i for i in client.get(nc_url(ctx.process_id)).json()['data']
    }
    assert items[second['id']]['decision'] == 'disqualify'
    assert items[second['id']]['status'] == 'RESOLVED'


@pytest.mark.asyncio
async def test_disqualify_already_waived_lab_only_closes_items(
    session, client
):
    ctx = await with_problem(session, client)
    authenticate(client, ctx.group_manager)
    client.post(
        f'/processes/{ctx.process_id}/phases/phase_3_validation_execution/'
        'laboratory-waivers',
        json={'laboratory_id': str(ctx.labs[0].id), 'reason': 'Quebra.'},
        headers=ORIGIN,
    )
    authenticate(client, ctx.selector)

    response = decide(client, ctx, ctx.items[0], 'disqualify')

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['status'] == 'RESOLVED'


@pytest.mark.asyncio
async def test_deciding_twice_returns_409(session, client):
    ctx = await with_problem(session, client)
    decide(client, ctx, ctx.items[0], 'accept_with_caveat')

    response = decide(client, ctx, ctx.items[0], 'resend')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'already_decided'


@pytest.mark.asyncio
async def test_nonconformity_of_other_process_returns_404(session, client):
    ctx = await with_problem(session, client)
    other = await with_problem(session, client)

    response = decide(client, other, ctx.items[0], 'accept_with_caveat')

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_last_decision_closes_resolution_and_new_problem_reopens(
    session, client
):
    ctx = await with_problem(session, client, broken=(0,))
    decide(client, ctx, ctx.items[0], 'resend')
    runs = await resolution_runs(session, ctx.process_id)
    assert [r.status for r in runs] == ['COMPLETED']

    authenticate(client, ctx.lab_users[0])
    (new_code,) = set(await codes_of(session, ctx, 0)) - set(ctx.codes)
    register(client, ctx.process_id, new_code, package_state='violated')

    runs = await resolution_runs(session, ctx.process_id)
    assert [(r.run_number, r.status) for r in runs] == [
        (1, 'COMPLETED'),
        (2, 'IN_PROGRESS'),
    ]


@pytest.mark.asyncio
async def test_decision_denied_to_other_roles(session, client, bracvam_user):
    ctx = await with_problem(session, client)

    expected = [
        (ctx.lab_users[0], HTTPStatus.NOT_FOUND),
        (ctx.group_manager, HTTPStatus.NOT_FOUND),
        (bracvam_user, HTTPStatus.FORBIDDEN),
    ]
    for user, status in expected:
        authenticate(client, user)
        response = decide(client, ctx, ctx.items[0], 'accept_with_caveat')
        assert response.status_code == status


@pytest.mark.asyncio
async def test_decision_events_carry_no_justification_or_code(session, client):
    ctx = await with_problem(session, client)
    response = decide(client, ctx, ctx.items[0], 'resend', 'Texto sigiloso.')
    new_code = response.json()['replacement_code']

    events = list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.process_instance_id == ctx.process_id,
                AuditEvent.event_type.in_([
                    'SAMPLE_NONCONFORMITY_RESOLVED',
                    'SAMPLE_VIAL_RESENT',
                ]),
            )
        )
    )

    assert {e.event_type for e in events} == {
        'SAMPLE_NONCONFORMITY_RESOLVED',
        'SAMPLE_VIAL_RESENT',
    }
    text = json.dumps([e.context_data for e in events])
    for secret in ('Texto sigiloso.', new_code, ctx.codes[0]):
        assert secret not in text


@pytest.mark.asyncio
async def test_decision_in_archived_process_returns_409(session, client):
    ctx = await with_problem(session, client)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.status = 'ARCHIVED'
    await session.commit()

    response = decide(client, ctx, ctx.items[0], 'accept_with_caveat')

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


def decide_with_guidance(client, ctx, item, decision, guidance):
    return client.post(
        nc_url(ctx.process_id, f'/{item["id"]}/decision'),
        json={
            'decision': decision,
            'justification': 'Segredo do Grupo.',
            'lab_guidance': guidance,
        },
        headers=ORIGIN,
    )


@pytest.mark.asyncio
async def test_guidance_is_saved_and_shown_to_selection_group(session, client):
    ctx = await with_problem(session, client)

    response = decide_with_guidance(
        client, ctx, ctx.items[0], 'accept_with_caveat', '  Use com cautela. '
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['lab_guidance'] == 'Use com cautela.'
    listed = client.get(nc_url(ctx.process_id)).json()['data'][0]
    assert listed['lab_guidance'] == 'Use com cautela.'
    assert listed['justification'] == 'Segredo do Grupo.'


@pytest.mark.asyncio
@pytest.mark.parametrize('guidance', ['', '   ', None])
async def test_blank_or_missing_guidance_counts_as_absent(
    session, client, guidance
):
    ctx = await with_problem(session, client)

    response = decide_with_guidance(
        client, ctx, ctx.items[0], 'accept_with_caveat', guidance
    )

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['lab_guidance'] is None


@pytest.mark.asyncio
async def test_disqualify_applies_guidance_to_all_closed_items(
    session, client
):
    ctx = await with_problem(session, client, broken=(0, 1))

    decide_with_guidance(
        client, ctx, ctx.items[0], 'disqualify', 'Devolva o lote inteiro.'
    )

    items = client.get(nc_url(ctx.process_id)).json()['data']
    assert {i['lab_guidance'] for i in items} == {'Devolva o lote inteiro.'}


@pytest.mark.asyncio
async def test_lab_sees_guidance_on_decided_vial_but_not_justification(
    session, client
):
    ctx = await with_problem(session, client)
    decide_with_guidance(
        client, ctx, ctx.items[0], 'accept_with_caveat', 'Use com cautela.'
    )

    authenticate(client, ctx.lab_users[0])
    body = client.get(vials_url(ctx.process_id)).json()
    vials = {v['code']: v for v in body['data']}

    assert vials[ctx.codes[0]]['lab_guidance'] == 'Use com cautela.'
    assert vials[ctx.codes[1]]['lab_guidance'] is None
    assert 'Segredo' not in json.dumps(body)
