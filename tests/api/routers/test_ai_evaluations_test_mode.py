# ruff: noqa: PLR2004
"""API — modo de teste de avaliações (Spec 013, US1/US6)."""

from http import HTTPStatus

import pytest

from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate

SAMPLE = (
    'POP-001 versao 2. Objetivo: descrever o ensaio. Materiais listados. '
    'Procedimento detalhado com criterios de aceitacao definidos. '
    'Referencias bibliograficas incluidas.'
)


async def _draft_with_criteria(client) -> str:
    resp = client.post(
        '/ai-evaluations',
        json={
            'name': 'Verificação de resumo metodológico',
            'mode': 'simple',
            'objective': 'Verificar completude do resumo.',
        },
        headers=TRUSTED_ORIGIN,
    )
    definition_id = resp.json()['id']
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={
            'criteria': [
                {
                    'order_index': 0,
                    'statement': 'Deve apresentar objetivo e materiais',
                    'check_type': 'conformity',
                    'severity': 'medium',
                },
                {
                    'order_index': 1,
                    'statement': 'Deve definir criterios de aceitacao',
                    'check_type': 'conformity',
                    'severity': 'critical',
                },
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    return definition_id


@pytest.mark.asyncio
async def test_test_run_on_draft_returns_results_and_counts(
    client, ai_eval_admin, fake_provider
):
    del fake_provider
    authenticate(client, ai_eval_admin)
    definition_id = await _draft_with_criteria(client)

    resp = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/test',
        json={'sample_content': SAMPLE},
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert len(body['results']) == 2
    assert body['consolidated_result'] in {'positive', 'negative'}
    assert all('conclusion' in r for r in body['results'])

    version = client.get(f'/ai-evaluations/{definition_id}/versions/1')
    assert version.json()['test_run_count'] == 1


@pytest.mark.asyncio
async def test_publish_after_test_clears_warning(
    client, ai_eval_admin, fake_provider
):
    del fake_provider
    authenticate(client, ai_eval_admin)
    definition_id = await _draft_with_criteria(client)
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/test',
        json={'sample_content': SAMPLE},
        headers=TRUSTED_ORIGIN,
    )

    publish = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    assert publish.json()['test_warning'] is False


@pytest.mark.asyncio
async def test_test_run_on_published_version_returns_conflict(
    client, ai_eval_admin, fake_provider
):
    del fake_provider
    authenticate(client, ai_eval_admin)
    definition_id = await _draft_with_criteria(client)
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )

    resp = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/test',
        json={'sample_content': SAMPLE},
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.CONFLICT
