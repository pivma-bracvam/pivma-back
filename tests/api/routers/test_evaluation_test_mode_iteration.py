# ruff: noqa: PLR2004
"""API — iteração no modo de teste antes da publicação (Spec 013, US6)."""

import pytest

from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate

SAMPLE = 'Documento de exemplo com metodologia e criterios de aceitacao.'


async def _draft(client) -> str:
    definition_id = client.post(
        '/ai-evaluations',
        json={
            'name': 'Iteração de teste',
            'mode': 'simple',
            'objective': 'Verificar completude.',
        },
        headers=TRUSTED_ORIGIN,
    ).json()['id']
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={
            'criteria': [
                {
                    'order_index': 0,
                    'statement': 'Deve conter metodologia',
                    'check_type': 'conformity',
                    'severity': 'medium',
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    return definition_id


@pytest.mark.asyncio
async def test_iterate_test_then_publish_clears_warning(
    client, ai_eval_admin, fake_provider
):
    del fake_provider
    authenticate(client, ai_eval_admin)
    definition_id = await _draft(client)

    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/test',
        json={'sample_content': SAMPLE},
        headers=TRUSTED_ORIGIN,
    )
    # ajusta um critério e testa de novo
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={
            'criteria': [
                {
                    'order_index': 0,
                    'statement': 'Deve conter metodologia e referencias',
                    'check_type': 'conformity',
                    'severity': 'high',
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/test',
        json={'sample_content': SAMPLE},
        headers=TRUSTED_ORIGIN,
    )

    version = client.get(f'/ai-evaluations/{definition_id}/versions/1').json()
    assert version['test_run_count'] == 2

    publish = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    assert publish.json()['test_warning'] is False


@pytest.mark.asyncio
async def test_publish_without_testing_warns(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)
    definition_id = await _draft(client)

    publish = client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    assert publish.json()['test_warning'] is True
