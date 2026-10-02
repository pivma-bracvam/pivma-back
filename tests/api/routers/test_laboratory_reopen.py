"""Rota de reabertura administrativa (Spec 036, US5)."""

from http import HTTPStatus

import pytest

from pivma.core.database.models import ProcessInstance
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    all_labs_done,
    frozen_lab_process,
    runs_by_lab,
    waive,
)
from tests.factories.sample_factory import add_participating_lab
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
REASON = 'Controle positivo fora da faixa na placa 2.'


def _post(client, ctx, key, laboratory_id, reason=REASON):
    return client.post(
        f'/processes/{ctx.process_id}/activities/{key}/laboratories/'
        f'{laboratory_id}/reopen',
        json={'reason': reason},
        headers=ORIGIN,
    )


def _assert_code(resp, status, code):
    assert resp.status_code == status
    assert resp.json()['detail']['code'] == code


async def _done(session):
    ctx = await frozen_lab_process(session)
    await all_labs_done(session, ctx)
    return ctx


@pytest.mark.asyncio
async def test_group_manager_reopens_lab_run(client, session):
    ctx = await _done(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['activity_key'] == 'upload'
    assert body['laboratory']['id'] == str(ctx.labs[1].id)
    assert (body['previous_run_number'], body['run_number']) == (1, 2)
    assert body['activity_status'] == 'IN_PROGRESS'
    assert set(body['reblocked_activity_keys']) == {
        'material_return',
        'statistics',
    }


@pytest.mark.asyncio
async def test_bracvam_reopens_lab_run(client, session, bracvam_user):
    ctx = await _done(session)
    authenticate(client, bracvam_user)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_admin_reopens_lab_run(client, session, ai_eval_admin):
    ctx = await _done(session)
    authenticate(client, ai_eval_admin)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_statistician_cannot_reopen(client, session):
    ctx = await _done(session)
    authenticate(client, ctx.statistician)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.FORBIDDEN
    run = (await runs_by_lab(session, ctx.process_id, 'upload'))[
        ctx.labs[1].id
    ]
    assert (run.run_number, run.status) == (1, 'COMPLETED')


@pytest.mark.asyncio
async def test_lab_user_cannot_reopen_own_run(client, session):
    ctx = await _done(session)
    authenticate(client, ctx.lab_users[1])

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_outsider_gets_not_found(client, session):
    ctx = await _done(session)
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_anonymous_gets_unauthorized(client, session):
    ctx = await _done(session)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_blank_reason_is_rejected(client, session):
    ctx = await _done(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id, reason='  ')

    _assert_code(resp, HTTPStatus.UNPROCESSABLE_ENTITY, 'validation_error')


@pytest.mark.asyncio
async def test_unknown_activity_is_not_found(client, session):
    ctx = await _done(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'unknown', ctx.labs[1].id)

    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_open_run_is_conflict(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'receipt', ctx.labs[1].id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'invalid_transition')


@pytest.mark.asyncio
async def test_lab_without_run_is_conflict(client, session):
    ctx = await _done(session)
    late = await add_participating_lab(session, ctx.process_id)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'upload', late.laboratory.id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'invalid_transition')


@pytest.mark.asyncio
async def test_waived_lab_outside_custody_is_conflict(client, session):
    ctx = await _done(session)
    await waive(session, ctx, 1)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'laboratory_waived')


@pytest.mark.asyncio
async def test_closed_process_refuses_reopen(client, session):
    ctx = await _done(session)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.status = 'CLOSED'
    await session.commit()
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, 'upload', ctx.labs[1].id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'invalid_transition')
