"""Spec 033, US1 (3d) - avaliações e referências de IA no envelope."""

from http import HTTPStatus

import pytest

from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate

ENVELOPE_KEYS = {'data', 'pagination', 'filters_applied', 'sort'}


def _get(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _create_evaluation(client, name):
    response = client.post(
        '/ai-evaluations',
        json={
            'name': name,
            'mode': 'simple',
            'objective': 'Avaliar a justificativa científica submetida.',
        },
        headers=TRUSTED_ORIGIN,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text


@pytest.mark.asyncio
async def test_evaluations_envelope_with_search(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)
    _create_evaluation(client, 'Critério Alfa')
    _create_evaluation(client, 'Outro')

    body = _get(client, '/ai-evaluations', search='Alfa')

    assert set(body) == ENVELOPE_KEYS
    assert [item['name'] for item in body['data']] == ['Critério Alfa']
    assert body['filters_applied'] == {'search': 'Alfa'}
    assert body['sort'] == {'by': 'name', 'order': 'asc'}


@pytest.mark.asyncio
async def test_evaluations_second_page_total(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)
    for name in ('A', 'B', 'C'):
        _create_evaluation(client, f'Avaliação {name}')

    body = _get(client, '/ai-evaluations', page=2, per_page=2)

    assert [item['name'] for item in body['data']] == ['Avaliação C']
    assert body['pagination']['total_items'] == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_references_envelope(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)
    for identifier in ('OECD 442D', 'OECD 439'):
        client.post(
            '/ai-evaluations/references',
            json={
                'identifier': identifier,
                'label': f'Guideline {identifier}',
                'version_label': '2018',
            },
            headers=TRUSTED_ORIGIN,
        )

    body = _get(client, '/ai-evaluations/references')

    assert set(body) == ENVELOPE_KEYS
    assert [item['identifier'] for item in body['data']] == [
        'OECD 439',
        'OECD 442D',
    ]
    assert body['sort'] == {'by': 'identifier', 'order': 'asc'}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'path', ['/ai-evaluations', '/ai-evaluations/references']
)
async def test_ai_lists_reject_per_page_above_100(client, ai_eval_admin, path):
    authenticate(client, ai_eval_admin)

    response = client.get(path, params={'per_page': 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
