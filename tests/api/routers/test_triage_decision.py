# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_triage_decision_needs_revision_and_resubmission(
    client, session
):
    await bootstrap_all_templates(session)
    proponente = UserFactory()
    triador = UserFactory()
    session.add_all([proponente, triador])
    await session.commit()

    # 1. Proponente submits
    authenticate(client, proponente)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Estudo com Diligência',
        },
    )
    process_id = resp.json()['id']

    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Título V1',
                'endpoint_target': 'corrosivity',
                'scientific_justification': 'Justificativa inicial.',
                'study_protocol_file': 'protocolo_v1.pdf',
            }
        },
    )

    # 2. Triador issues NEEDS_REVISION
    authenticate(client, triador)
    dec_resp = client.post(
        f'/processes/{process_id}/triage/decision',
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Favor incluir histórico de testes comparativos.',
        },
    )
    assert dec_resp.status_code == HTTPStatus.OK
    dec_data = dec_resp.json()
    assert dec_data['new_process_status'] == 'SUBMISSION'
    assert dec_data['next_activity_run'] == 2

    # 3. Proponente accesses form in Run 2 (pre-populated values)
    authenticate(client, proponente)
    form_resp = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert form_resp.status_code == HTTPStatus.OK
    assert not form_resp.json()['is_submitted']
    assert form_resp.json()['values']['method_title'] == 'Título V1'

    # 4. Proponente adjusts values and re-submits (Run 2)
    resubmit_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Título V2 Corrigido',
                'endpoint_target': 'corrosivity',
                'scientific_justification': 'Justificativa atualizada.',
                'study_protocol_file': 'protocolo_v2.pdf',
            }
        },
    )
    assert resubmit_resp.status_code == HTTPStatus.OK
    assert resubmit_resp.json()['run_number'] == 2

    # Process returns to TRIAGE
    p_resp = client.get(f'/processes/{process_id}')
    assert p_resp.json()['status'] == 'TRIAGE'

    # 5. Triador approves
    authenticate(client, triador)
    approve_resp = client.post(
        f'/processes/{process_id}/triage/decision',
        json={
            'outcome': 'APPROVED',
            'justification': 'Proposta ajustada e aprovada.',
        },
    )
    assert approve_resp.status_code == HTTPStatus.OK
    assert approve_resp.json()['new_process_status'] == 'PLANNING'
