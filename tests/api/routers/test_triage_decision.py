# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    FormInstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_triage_decision_needs_revision_and_resubmission(
    client, session, bracvam_user
):
    await bootstrap_all_templates(session)
    proponente = UserFactory()
    triador = bracvam_user
    session.add(proponente)
    await session.commit()

    # 1. Proponente submits
    authenticate(client, proponente)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
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
                'pre_validation_evidence': (
                    'Evidências prévias de repetibilidade.'
                ),
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
        headers={'Origin': 'https://testserver'},
    )
    assert dec_resp.status_code == HTTPStatus.OK
    dec_data = dec_resp.json()
    assert dec_data['new_process_status'] == 'SUBMISSION'
    assert dec_data['next_activity_run'] == 2

    submission_activity = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'proposal_submission',
        )
    )
    previous_run = await session.scalar(
        select(ActivityRun).where(
            ActivityRun.activity_instance_id == submission_activity.id,
            ActivityRun.run_number == 1,
        )
    )
    previous_form = await session.scalar(
        select(FormInstance).where(
            FormInstance.activity_run_id == previous_run.id
        )
    )
    assert previous_run.status == 'COMPLETED'
    assert previous_form.is_submitted is True

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
                'pre_validation_evidence': 'Evidências prévias atualizadas.',
                'study_protocol_file': 'protocolo_v2.pdf',
            }
        },
    )
    assert resubmit_resp.status_code == HTTPStatus.OK
    assert resubmit_resp.json()['run_number'] == 2

    dossiers = list(
        await session.scalars(
            select(Artifact).where(
                Artifact.process_instance_id == process_id,
                Artifact.key == 'proposal_dossier',
            )
        )
    )
    dossier = next(
        item
        for item in dossiers
        if item.metadata_payload.get('title') == 'Estudo com Diligência'
    )
    assert dossier is not None
    assert dossier.metadata_payload['values']['method_title'] == 'Título V1'

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
        headers={'Origin': 'https://testserver'},
    )
    assert approve_resp.status_code == HTTPStatus.OK
    assert approve_resp.json()['new_process_status'] == 'PLANNING'
