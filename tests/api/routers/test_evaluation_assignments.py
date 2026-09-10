"""API — associação de avaliações a alvos de formulário (Spec 013, US1)."""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate

TEMPLATE_KEY = 'submission_pre_validated_v1'
AI_FIELD = 'scientific_justification'


async def _published_definition(client) -> str:
    resp = client.post(
        '/ai-evaluations',
        json={
            'name': 'Verificação da justificativa científica',
            'mode': 'simple',
            'objective': 'Avaliar a justificativa científica.',
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
                    'statement': 'Deve citar dados comparativos',
                    'check_type': 'conformity',
                    'severity': 'high',
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    client.post(
        f'/ai-evaluations/{definition_id}/versions/1/publish',
        headers=TRUSTED_ORIGIN,
    )
    return definition_id


async def _draft_only_definition(client) -> str:
    resp = client.post(
        '/ai-evaluations',
        json={
            'name': 'Avaliação sem publicação',
            'mode': 'simple',
            'objective': 'Objetivo qualquer.',
        },
        headers=TRUSTED_ORIGIN,
    )
    return resp.json()['id']


@pytest.mark.asyncio
async def test_put_replaces_assignment_list(client, ai_eval_admin, session):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _published_definition(client)

    resp = client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': [AI_FIELD],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert len(data['assignments']) == 1
    assert data['assignments'][0]['effective_version_number'] == 1

    cleared = client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={'assignments': []},
        headers=TRUSTED_ORIGIN,
    )
    assert cleared.json()['assignments'] == []


@pytest.mark.asyncio
async def test_unknown_field_key_is_rejected(client, ai_eval_admin, session):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _published_definition(client)

    resp = client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': ['campo_inexistente'],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_definition_without_published_version_is_rejected(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _draft_only_definition(client)

    resp = client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': [AI_FIELD],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_proponent_cannot_manage_assignments(client, user, session):
    await bootstrap_all_templates(session)
    authenticate(client, user)

    resp = client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={'assignments': []},
        headers=TRUSTED_ORIGIN,
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_evaluable_fields_lists_ai_fields(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _published_definition(client)
    client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': [AI_FIELD],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )

    resp = client.get(f'/form-templates/{TEMPLATE_KEY}/evaluable-fields')
    assert resp.status_code == HTTPStatus.OK
    fields = {f['field_key']: f for f in resp.json()['fields']}
    assert AI_FIELD in fields
    assert len(fields[AI_FIELD]['assignments']) == 1


@pytest.mark.asyncio
async def test_removing_field_prunes_its_assignments(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    definition_id = await _published_definition(client)
    client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': [AI_FIELD],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )

    detail = client.get(
        f'/processes/templates/pre_validated_method/forms/{TEMPLATE_KEY}'
    ).json()
    kept_fields = [
        f for f in detail['fields'] if f['field_key'] != AI_FIELD
    ]
    edit = client.put(
        f'/processes/templates/pre_validated_method/forms/{TEMPLATE_KEY}',
        json={'fields': kept_fields},
    )
    assert edit.status_code == HTTPStatus.OK

    remaining = client.get(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments'
    ).json()
    assert remaining['assignments'] == []

    # E o template volta a aceitar novas associações (sem órfã travando o PUT).
    other_field = kept_fields[0]['field_key']
    redo = client.put(
        f'/form-templates/{TEMPLATE_KEY}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': [other_field],
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )
    assert redo.status_code == HTTPStatus.OK
    assert redo.json()['assignments'][0]['field_keys'] == [other_field]
