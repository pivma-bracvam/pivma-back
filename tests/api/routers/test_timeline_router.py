# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_process_timeline_events_recorded_and_ordered(
    client, session, bracvam_user
):
    await bootstrap_all_templates(session)
    proponente = UserFactory()
    triador = bracvam_user
    session.add(proponente)
    await session.commit()

    # 1. Proponente creates process
    authenticate(client, proponente)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo para Teste de Linha do Tempo',
        },
    )
    process_id = resp.json()['id']

    # 2. Save Draft
    client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Rascunho Timeline'}},
    )

    # 3. Submit Form
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Método Timeline',
                'endpoint_target': 'phototoxicity',
                'scientific_justification': 'Justificativa para timeline.',
                'pre_validation_evidence': (
                    'Evidências prévias de repetibilidade.'
                ),
                'study_protocol_file': 'protocolo.pdf',
            }
        },
    )

    # 4. Triador evaluates and approves
    authenticate(client, triador)
    _origin = {'Origin': 'https://testserver'}
    client.post(
        f'/processes/{process_id}/triage/reviews',
        json={
            'reviews': [{'field_key': 'method_title', 'status': 'CONFORME'}]
        },
        headers=_origin,
    )
    client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado com sucesso.'},
        headers=_origin,
    )

    # 5. Query timeline
    tl_resp = client.get(f'/processes/{process_id}/timeline')
    assert tl_resp.status_code == HTTPStatus.OK
    timeline_data = tl_resp.json()
    assert timeline_data['process_id'] == process_id
    assert len(timeline_data['events']) >= 4

    event_types = [e['event_type'] for e in timeline_data['events']]
    assert event_types == [
        'PROCESS_CREATED',
        'FORM_DRAFT_SAVED',
        'SUBMISSION_SUBMITTED',
        # Issue #22 (US3): desbloqueio da triagem pelo motor genérico
        # passa a registrar evento, como qualquer outra atividade
        # dependente — antes, `_unblock_triage_activity` não emitia nada.
        'ACTIVITY_UNBLOCKED',
        'FIELD_REVIEWED',
        'TRIAGE_APPROVED',
    ]
