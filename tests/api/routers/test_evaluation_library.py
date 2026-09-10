# ruff: noqa: PLR2004
"""API — listagem da biblioteca de avaliações (Spec 013, US5)."""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate

CRITERIA = [
    {
        'order_index': 0,
        'statement': 'Deve apresentar metodologia detalhada',
        'check_type': 'quality',
        'severity': 'high',
    }
]


async def _create_published(client, name: str) -> str:
    definition_id = client.post(
        '/ai-evaluations',
        json={'name': name, 'mode': 'simple', 'objective': 'Objetivo.'},
        headers=TRUSTED_ORIGIN,
    ).json()['id']
    client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={'criteria': CRITERIA},
        headers=TRUSTED_ORIGIN,
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    return definition_id


@pytest.mark.asyncio
async def test_list_shows_version_status_and_counts(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _create_published(client, 'Verificação de POP')
    _d = client.post(
        '/ai-evaluations',
        json={
            'name': 'Rascunho ainda',
            'mode': 'simple',
            'objective': 'Objetivo em rascunho.',
        },
        headers=TRUSTED_ORIGIN,
    )
    print('DRAFT POST', _d.status_code, _d.text[:300])
    client.put(
        '/form-templates/submission_pre_validated_v1/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'form',
                    'field_keys': [],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )

    _r = client.get('/ai-evaluations')
    print('LIST', _r.status_code, _r.json())
    body = _r.json()
    by_name = {item['name']: item for item in body['items']}

    published = by_name['Verificação de POP']
    assert published['latest_version']['status'] == 'published'
    assert published['published_versions'] == 1
    assert published['assignments_count'] == 1

    draft = by_name['Rascunho ainda']
    assert draft['latest_version']['status'] == 'draft'
    assert draft['published_versions'] == 0
    assert draft['assignments_count'] == 0


@pytest.mark.asyncio
async def test_assignment_defaults_to_latest_published_version(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _create_published(client, 'Duas versões')
    # cria e publica a v2
    client.post(
        f'/ai-evaluations/{definition_id}/versions', headers=TRUSTED_ORIGIN
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/2/publish',
        headers=TRUSTED_ORIGIN,
    )

    resp = client.put(
        '/form-templates/submission_pre_validated_v1/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'form',
                    'field_keys': [],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['assignments'][0]['effective_version_number'] == 2
