# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    AuditEvent,
    FormInstance,
    Task,
)
from tests.activity_state import back_with_proponent, in_triage
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
    assert dec_data['process_status'] == 'OPEN'
    assert await back_with_proponent(session, process_id)
    assert dec_data['return_review_run'] == 1

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

    # 3. Proponente lê o retorno e escolhe revisar (Spec 030): só então a
    # Run 2 da submissão abre, pré-preenchida.
    authenticate(client, proponente)
    revise = client.post(
        f'/processes/{process_id}/return-review',
        json={'choice': 'REVISE'},
        headers={'Origin': 'https://testserver'},
    )
    assert revise.status_code == HTTPStatus.OK
    assert revise.json()['submission_run'] == 2
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

    # A triagem reabre; o processo segue OPEN (Spec 030)
    p_resp = client.get(f'/processes/{process_id}')
    assert p_resp.json()['status'] == 'OPEN'
    assert await in_triage(session, process_id)

    # 4b. Rodada 2 da triagem tem sua própria run/task (Issue #22: antes, a
    # rodada 1 (já concluída) era reaproveitada e nenhuma pendência nova
    # aparecia para o triador).
    triage_activity = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'triage_evaluation',
        )
    )
    triage_runs = (
        await session.scalars(
            select(ActivityRun)
            .where(ActivityRun.activity_instance_id == triage_activity.id)
            .order_by(ActivityRun.run_number)
        )
    ).all()
    assert [r.run_number for r in triage_runs] == [1, 2]
    first_triage_run, second_triage_run = triage_runs
    assert first_triage_run.status == 'COMPLETED'
    assert second_triage_run.status == 'IN_PROGRESS'
    assert second_triage_run.started_at != first_triage_run.started_at

    first_triage_task = await session.scalar(
        select(Task).where(Task.activity_run_id == first_triage_run.id)
    )
    second_triage_task = await session.scalar(
        select(Task).where(Task.activity_run_id == second_triage_run.id)
    )
    assert first_triage_task.status == 'COMPLETED'
    assert second_triage_task.id != first_triage_task.id
    assert second_triage_task.status == 'READY'
    assert second_triage_task.title == first_triage_task.title

    # 4c. Evento de auditoria do desbloqueio (Issue #22, US3) — antes,
    # `_unblock_triage_activity` não emitia nenhum evento.
    unblock_event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process_id,
            AuditEvent.event_type == 'ACTIVITY_UNBLOCKED',
            AuditEvent.activity_run_id == second_triage_run.id,
        )
    )
    assert unblock_event is not None
    assert unblock_event.context_data['activity_key'] == 'triage_evaluation'

    # 4d. Triador vê a pendência da nova rodada (Issue #22, US1) — antes,
    # esta chamada não retornava a tarefa da rodada 2.
    authenticate(client, triador)
    tasks_resp = client.get(f'/tasks?process_id={process_id}&status=READY')
    assert tasks_resp.status_code == HTTPStatus.OK
    assert any(
        t['id'] == str(second_triage_task.id) for t in tasks_resp.json()
    )

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
    assert approve_resp.json()['process_status'] == 'OPEN'
