# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_participant_router import create_participant
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.structure_approval_factory import runs
from tests.factories.submission_factory import submission_values
from tests.factories.user_factory import UserFactory

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}


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
        headers=TRUSTED_ORIGIN,
    )
    process_id = resp.json()['id']

    # 2. Save Draft
    client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': submission_values('Rascunho Timeline')},
        headers=TRUSTED_ORIGIN,
    )

    # 3. Submit Form
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                **submission_values(),
                'method_title': 'Método Timeline',
                'endpoint_target': 'phototoxicity',
                'scientific_justification': 'Justificativa para timeline.',
                'pre_validation_evidence': (
                    'Evidências prévias de repetibilidade.'
                ),
                'study_protocol_file': 'protocolo.pdf',
            }
        },
        headers=TRUSTED_ORIGIN,
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
    assert len(timeline_data['data']) >= 4

    event_types = [e['event_type'] for e in timeline_data['data']]
    assert event_types == [
        'PROCESS_CREATED',
        # O BraCVAM gere participantes e vê a designação do proponente.
        'PARTICIPANT_ASSIGNED',
        'FORM_DRAFT_SAVED',
        'SUBMISSION_SUBMITTED',
        # Issue #22 (US3): desbloqueio da triagem pelo motor genérico
        # passa a registrar evento, como qualquer outra atividade
        # dependente — antes, `_unblock_triage_activity` não emitia nada.
        'ACTIVITY_UNBLOCKED',
        'FIELD_REVIEWED',
        'TRIAGE_APPROVED',
        # Spec 031: a aprovação abre a Fase 2 também no template 1
        # (Patrocinador e Grupo Gestor).
        'ACTIVITY_UNBLOCKED',
        'ACTIVITY_UNBLOCKED',
    ]


@pytest.mark.asyncio
async def test_timeline_hides_events_of_activities_without_view_after_triage(
    client, session, bracvam_user
):
    """Spec 030 (FR-021): eventos de `assign_sponsor` não chegam ao
    proponente, que não tem visão dessa atividade."""
    await bootstrap_all_templates(session)
    proponente = UserFactory()
    sponsor = UserFactory()
    session.add_all([proponente, sponsor])
    await session.commit()

    authenticate(client, proponente)
    process_id = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Timeline'},
        headers=TRUSTED_ORIGIN,
    ).json()['id']
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': submission_values('Método')},
        headers=TRUSTED_ORIGIN,
    )
    authenticate(client, bracvam_user)
    decision = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
        headers=TRUSTED_ORIGIN,
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    designated = create_participant(client, process_id, sponsor.id, 'sponsor')
    assert designated.status_code == HTTPStatus.CREATED, designated.text

    sponsor_run_ids = {
        str(run.id)
        for run in await runs(session, process_id, 'assign_sponsor')
    }
    bracvam_events = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    ).json()['data']
    assert {e['activity_run_id'] for e in bracvam_events} & sponsor_run_ids

    authenticate(client, proponente)
    proponent_events = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    ).json()['data']
    assert not {e['activity_run_id'] for e in proponent_events} & (
        sponsor_run_ids
    )
    assert any(
        e['event_type'] == 'SUBMISSION_SUBMITTED' for e in (proponent_events)
    )
