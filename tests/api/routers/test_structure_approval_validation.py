"""Validação do pedido de decisão da homologação (Spec 042).

Um teste por linha de data-model.md ("Regras de validação da decisão").
Cada recusa confere também que nada mudou.
"""

from http import HTTPStatus

import pytest
import pytest_asyncio

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.structure_approval_factory import (
    decide,
    snapshot,
    structure_process,
)

POINT = {'activity_key': 'assign_sponsor', 'reason': 'Patrocinador errado.'}


@pytest_asyncio.fixture
async def ctx(client, session, bracvam_user):
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)
    ctx.before = await snapshot(session, ctx.process_id)
    return ctx


async def _assert_refused(session, ctx, response, status, code):
    assert response.status_code == status, response.text
    assert response.json()['detail']['code'] == code
    assert await snapshot(session, ctx.process_id) == ctx.before


def _body(**overrides):
    return {
        'outcome': 'REJECTED',
        'justification': 'Equipe incompleta.',
        'rejected_points': [POINT],
        **overrides,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'body',
    [
        pytest.param(_body(outcome='NEEDS_REVISION'), id='outcome'),
        pytest.param(_body(justification='Ok'), id='short_justification'),
        pytest.param(_body(outcome='APPROVED'), id='approved_with_points'),
        pytest.param(
            _body(outcome='APPROVED', rejected_points=[]),
            id='approved_with_empty_points',
        ),
        pytest.param(
            _body(rejected_points=None), id='rejected_without_points'
        ),
        pytest.param(
            _body(rejected_points=[]), id='rejected_with_empty_points'
        ),
        pytest.param(
            _body(rejected_points=[POINT, POINT]), id='repeated_point'
        ),
        pytest.param(
            _body(rejected_points=[{**POINT, 'reason': 'No'}]),
            id='short_reason',
        ),
        pytest.param(_body(extra='campo'), id='extra_field'),
        pytest.param(
            _body(rejected_points=[{**POINT, 'extra': 'campo'}]),
            id='extra_point_field',
        ),
    ],
)
async def test_invalid_body_is_refused_with_validation_error(
    client, session, ctx, body
):
    response = decide(client, ctx.process_id, **body)

    await _assert_refused(
        session,
        ctx,
        response,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        'validation_error',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'activity_key',
    ['triage_evaluation', 'structure_approval', 'chave_inexistente'],
)
async def test_key_outside_the_points_is_refused_with_invalid_point(
    client, session, ctx, activity_key
):
    response = decide(
        client,
        ctx.process_id,
        **_body(rejected_points=[{**POINT, 'activity_key': activity_key}]),
    )

    await _assert_refused(
        session,
        ctx,
        response,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        'invalid_point',
    )
