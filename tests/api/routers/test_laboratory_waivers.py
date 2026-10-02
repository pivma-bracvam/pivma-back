"""Rota de dispensa de laboratório (Spec 036, US4)."""

from datetime import datetime
from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    Assignment,
    LaboratoryWaiver,
    ProcessInstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import frozen_lab_process
from tests.factories.sample_factory import add_participating_lab
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
REASON = 'Quebra irreversível da leitora de placas.'


def _post(
    client, ctx, laboratory_id, *, reason=REASON, phase='phase_execution'
):
    body = {'laboratory_id': str(laboratory_id)}
    if reason is not None:
        body['reason'] = reason
    return client.post(
        f'/processes/{ctx.process_id}/phases/{phase}/laboratory-waivers',
        json=body,
        headers=ORIGIN,
    )


async def _waiver_count(session):
    return await session.scalar(
        select(func.count()).select_from(LaboratoryWaiver)
    )


def _assert_code(resp, status, code):
    assert resp.status_code == status
    assert resp.json()['detail']['code'] == code


@pytest.mark.asyncio
async def test_group_manager_waives_lab(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, ctx.labs[2].id)

    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['process_id'] == str(ctx.process_id)
    assert body['phase'] == {'key': 'phase_execution', 'order': 2}
    assert body['laboratory']['id'] == str(ctx.labs[2].id)
    assert body['reason'] == REASON
    assert body['waived_by']['id'] == str(ctx.group_manager.id)
    assert body['waived_activity_keys'] == ['receipt', 'upload']


@pytest.mark.asyncio
async def test_bracvam_waives_lab(client, session, bracvam_user):
    ctx = await frozen_lab_process(session)
    authenticate(client, bracvam_user)

    assert _post(client, ctx, ctx.labs[2].id).status_code == HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_admin_waives_lab(client, session, ai_eval_admin):
    ctx = await frozen_lab_process(session)
    authenticate(client, ai_eval_admin)

    assert _post(client, ctx, ctx.labs[2].id).status_code == HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_lab_user_cannot_waive(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.lab_users[0])

    resp = _post(client, ctx, ctx.labs[2].id)

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert await _waiver_count(session) == 0


@pytest.mark.asyncio
async def test_statistician_cannot_waive(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.statistician)

    assert _post(client, ctx, ctx.labs[2].id).status_code == (
        HTTPStatus.FORBIDDEN
    )


@pytest.mark.asyncio
async def test_proponent_cannot_waive(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.creator)

    assert _post(client, ctx, ctx.labs[2].id).status_code == (
        HTTPStatus.FORBIDDEN
    )


@pytest.mark.asyncio
async def test_revoked_group_manager_cannot_waive(client, session):
    ctx = await frozen_lab_process(session)
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.user_id == ctx.group_manager.id,
        )
    )
    assignment.revoked_at = datetime.utcnow()
    # Mantém o processo visível para cair no 403, não no 404.
    session.add(
        Assignment(
            process_instance_id=ctx.process_id,
            user_id=ctx.group_manager.id,
            assigned_by=ctx.group_manager.id,
            role_key='collaborator',
        )
    )
    await session.commit()
    authenticate(client, ctx.group_manager)

    assert _post(client, ctx, ctx.labs[2].id).status_code == (
        HTTPStatus.FORBIDDEN
    )


@pytest.mark.asyncio
async def test_outsider_gets_not_found(client, session):
    ctx = await frozen_lab_process(session)
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    assert _post(client, ctx, ctx.labs[2].id).status_code == (
        HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_anonymous_gets_unauthorized(client, session):
    ctx = await frozen_lab_process(session)

    assert _post(client, ctx, ctx.labs[2].id).status_code == (
        HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_waiver_before_freeze_is_refused(client, session):
    ctx = await frozen_lab_process(session, freeze=False)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, ctx.labs[2].id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'sample_definition_not_frozen')
    assert resp.json()['detail']['message'] == (
        'Não é permitido registrar dispensa de ensaio antes do congelamento '
        'e expedição das amostras.'
    )
    assert await _waiver_count(session) == 0


@pytest.mark.asyncio
async def test_missing_reason_is_rejected(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, ctx.labs[2].id, reason=None)

    _assert_code(resp, HTTPStatus.UNPROCESSABLE_ENTITY, 'validation_error')


@pytest.mark.asyncio
async def test_blank_reason_is_rejected(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, ctx.labs[2].id, reason='   ')

    _assert_code(resp, HTTPStatus.UNPROCESSABLE_ENTITY, 'validation_error')


@pytest.mark.asyncio
async def test_lab_outside_frozen_set_is_rejected(client, session):
    ctx = await frozen_lab_process(session)
    late = await add_participating_lab(session, ctx.process_id)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, late.laboratory.id)

    _assert_code(
        resp, HTTPStatus.UNPROCESSABLE_ENTITY, 'laboratory_not_frozen'
    )


@pytest.mark.asyncio
async def test_unknown_phase_is_not_found(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, ctx.labs[2].id, phase='phase_unknown')

    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_second_waiver_is_conflict(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)
    assert _post(client, ctx, ctx.labs[2].id).status_code == HTTPStatus.CREATED

    resp = _post(client, ctx, ctx.labs[2].id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'already_waived')


@pytest.mark.asyncio
async def test_closed_process_refuses_waiver(client, session):
    ctx = await frozen_lab_process(session)
    process = await session.get(ProcessInstance, ctx.process_id)
    process.status = 'CLOSED'
    await session.commit()
    authenticate(client, ctx.group_manager)

    resp = _post(client, ctx, ctx.labs[2].id)

    _assert_code(resp, HTTPStatus.CONFLICT, 'invalid_transition')


@pytest.mark.asyncio
async def test_waiver_cannot_be_deleted(client, session):
    ctx = await frozen_lab_process(session)
    authenticate(client, ctx.group_manager)

    resp = client.delete(
        f'/processes/{ctx.process_id}/phases/phase_execution/'
        'laboratory-waivers',
        headers=ORIGIN,
    )

    assert resp.status_code == HTTPStatus.METHOD_NOT_ALLOWED
