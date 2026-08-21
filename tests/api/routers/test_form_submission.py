# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_form_draft_and_submission_flow(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. Create process
    resp = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Estudo de Irritação Cutânea',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']

    # 2. Get form definition
    form_resp = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert form_resp.status_code == HTTPStatus.OK
    form_data = form_resp.json()
    assert form_data['template_key'] == 'submission_full_validation_v1'
    assert len(form_data['fields']) >= 4
    assert not form_data['is_submitted']

    # 3. Save draft
    draft_payload = {
        'values': {
            'method_title': 'Título em Rascunho',
            'endpoint_target': 'skin_sensitization',
        }
    }
    draft_resp = client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=draft_payload,
    )
    assert draft_resp.status_code == HTTPStatus.OK

    # 4. Check form values after draft
    form_resp_2 = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert form_resp_2.json()['values']['method_title'] == 'Título em Rascunho'

    # 5. Fail formal submit when required fields are missing
    invalid_submit_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=draft_payload,
    )
    assert invalid_submit_resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 6. Formal submit with all required fields
    full_payload = {
        'values': {
            'method_title': 'Método de Ensaio Concluído',
            'endpoint_target': 'skin_sensitization',
            'scientific_justification': 'Fundamentação completa do método.',
            'study_protocol_file': 'protocolo.pdf',
        }
    }
    submit_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=full_payload,
    )
    assert submit_resp.status_code == HTTPStatus.OK
    submit_data = submit_resp.json()
    assert submit_data['status'] == 'COMPLETED'
    assert submit_data['artifact_id'] is not None

    # 7. Check process status changed to TRIAGE
    p_resp = client.get(f'/processes/{process_id}')
    assert p_resp.json()['status'] == 'TRIAGE'

    # 8. Check timeline
    tl_resp = client.get(f'/processes/{process_id}/timeline')
    assert tl_resp.status_code == HTTPStatus.OK
    events = tl_resp.json()['events']
    event_types = [e['event_type'] for e in events]
    assert 'PROCESS_CREATED' in event_types
    assert 'FORM_DRAFT_SAVED' in event_types
    assert 'SUBMISSION_SUBMITTED' in event_types
