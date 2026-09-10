# ruff: noqa: PLR2004
"""API — configuração de avaliações por IA (Spec 013, US1)."""

from http import HTTPStatus

import pytest

from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate

CREATE_BODY = {
    'name': 'Verificação de estrutura de POP',
    'mode': 'simple',
    'objective': 'Verificar se o POP permite reprodução do método.',
}


def _criteria_payload():
    return [
        {
            'order_index': 0,
            'statement': 'Deve possuir identificação e versão',
            'check_type': 'presence',
            'severity': 'low',
        },
        {
            'order_index': 1,
            'statement': 'O procedimento deve permitir reprodução',
            'check_type': 'quality',
            'severity': 'critical',
        },
    ]


async def _create(client) -> str:
    resp = client.post(
        '/ai-evaluations', json=CREATE_BODY, headers=TRUSTED_ORIGIN
    )
    assert resp.status_code == HTTPStatus.CREATED
    return resp.json()['id']


@pytest.mark.asyncio
async def test_create_suggest_patch_publish_flow(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)
    definition_id = await _create(client)

    suggest = client.post(
        '/ai-evaluations/suggest-criteria',
        json={'objective': CREATE_BODY['objective'], 'target_type': 'field'},
        headers=TRUSTED_ORIGIN,
    )
    assert suggest.status_code == HTTPStatus.OK
    assert suggest.json()['suggestions']

    patch = client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={'criteria': _criteria_payload()},
        headers=TRUSTED_ORIGIN,
    )
    assert patch.status_code == HTTPStatus.OK
    assert len(patch.json()['criteria']) == 2

    publish = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    assert publish.status_code == HTTPStatus.OK
    body = publish.json()
    assert body['status'] == 'published'
    assert body['test_warning'] is True


@pytest.mark.asyncio
async def test_patch_published_version_returns_conflict(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)
    definition_id = await _create(client)
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={'criteria': _criteria_payload()},
        headers=TRUSTED_ORIGIN,
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )

    resp = client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={'objective': 'nova redação'},
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_create_new_version_clones_latest_as_draft(
    client, ai_eval_admin
):
    authenticate(client, ai_eval_admin)
    definition_id = await _create(client)
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={'criteria': _criteria_payload()},
        headers=TRUSTED_ORIGIN,
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )

    resp = client.post(
        f'/ai-evaluations/{definition_id}/versions', headers=TRUSTED_ORIGIN
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body['version_number'] == 2
    assert body['status'] == 'draft'
    assert len(body['criteria']) == 2

    dup = client.post(
        f'/ai-evaluations/{definition_id}/versions', headers=TRUSTED_ORIGIN
    )
    assert dup.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_publish_without_criteria_returns_unprocessable(
    client, ai_eval_admin
):
    authenticate(client, ai_eval_admin)
    definition_id = await _create(client)

    resp = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_non_bracvam_user_cannot_create(client, user):
    authenticate(client, user)
    resp = client.post(
        '/ai-evaluations', json=CREATE_BODY, headers=TRUSTED_ORIGIN
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = client.get('/ai-evaluations')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED
