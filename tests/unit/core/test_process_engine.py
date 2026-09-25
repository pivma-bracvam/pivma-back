# ruff: noqa: PLR2004, PLR0914, PLR0915

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    FormValue,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    Task,
)
from pivma.core.process_engine import (
    ValidationError,
    _complete_activity_run,  # noqa: PLC2701
    execute_triage_decision,
    get_current_form_instance,
    instantiate_process,
    save_field_reviews,
    save_form_values_draft,
    submit_proposal_form,
)
from tests.conftest import _make_rbac_user
from tests.factories.user_factory import UserFactory


async def _make_bracvam(session):
    """Triador com perfil BraCVAM: só ele edita a triagem (Spec 030)."""
    return await _make_rbac_user(
        session, system_key='bracvam', name='BraCVAM', codes=()
    )


@pytest.mark.asyncio
async def test_full_process_engine_flow_approved(session):
    # 1. Setup template
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    triador = await _make_bracvam(session)

    pt_stmt = (
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(ProcessTemplate.key == 'pre_validated_method')
    )
    ptv = (await session.execute(pt_stmt)).scalar_one()

    # 2. Instantiate Process
    process = await instantiate_process(
        session, ptv, 'Estudo de Irritação Ocular', user.id
    )
    assert process.status == 'OPEN'
    assert process.code.startswith('VAL-')

    # Verify initial activities
    act_stmt = select(ActivityInstance).where(
        ActivityInstance.process_instance_id == process.id
    )
    activities = (await session.execute(act_stmt)).scalars().all()
    act_map = {a.key: a for a in activities}

    assert act_map['proposal_submission'].status == 'IN_PROGRESS'
    assert act_map['triage_evaluation'].status == 'BLOCKED'

    # 3. Save Draft
    draft_vals = {'method_title': 'Método 3T3 NRU'}
    form_inst = await save_form_values_draft(
        session, process.id, 'proposal_submission', draft_vals, user.id
    )
    assert not form_inst.is_submitted

    # 4. Fail Submit without required fields
    with pytest.raises(ValidationError):
        await submit_proposal_form(
            session, process.id, 'proposal_submission', {}, user.id
        )

    # 5. Submit valid form
    full_vals = {'method_title': 'Método 3T3 NRU Completo'}
    sub_act, sub_run, artifact, pre_eval_run = await submit_proposal_form(
        session, process.id, 'proposal_submission', full_vals, user.id
    )

    assert sub_act.status == 'COMPLETED'
    assert sub_run.status == 'COMPLETED'
    assert artifact.key == 'proposal_dossier'
    # Sem avaliações por IA associadas: nenhuma esteira roda (Spec 014).
    assert 'ai_evaluation' not in artifact.metadata_payload
    assert pre_eval_run is None

    # A triagem é liberada; o processo segue OPEN (Spec 030)
    p_refreshed = (
        await session.execute(
            select(ProcessInstance).where(ProcessInstance.id == process.id)
        )
    ).scalar_one()
    assert p_refreshed.status == 'OPEN'

    triage_act = (
        await session.execute(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process.id,
                ActivityInstance.key == 'triage_evaluation',
            )
        )
    ).scalar_one()
    assert triage_act.status == 'IN_PROGRESS'

    # 6. Review fields
    reviews = [
        {'field_key': 'method_title', 'status': 'CONFORME'},
        {
            'field_key': 'scientific_justification',
            'status': 'CONFORME',
            'comments': 'Adequado',
        },
    ]
    await save_field_reviews(session, process.id, reviews, triador.id)

    # 7. Approve Triage
    decision, new_status, next_run = await execute_triage_decision(
        session,
        process.id,
        'APPROVED',
        'Proposta aprovada para planejamento',
        triador.id,
    )
    assert decision.outcome == 'APPROVED'
    assert new_status == 'OPEN'
    assert next_run is None


@pytest.mark.asyncio
async def test_process_engine_flow_diligence_reexecution(session):
    # Setup
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    triador = await _make_bracvam(session)

    ptv = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'pre_validated_method')
        )
    ).scalar_one()

    process = await instantiate_process(
        session, ptv, 'Estudo para Repetição', user.id
    )

    # Submit Run 1
    vals_1 = {
        'method_title': 'Título Inicial',
        'endpoint_target': 'skin_sensitization',
        'scientific_justification': 'Justificativa preliminar',
        'pre_validation_evidence': 'Evidências prévias de repetibilidade.',
        'study_protocol_file': 'protocolo.pdf',
    }
    await submit_proposal_form(
        session, process.id, 'proposal_submission', vals_1, user.id
    )

    # Triador requests revision
    decision, new_status, next_run = await execute_triage_decision(
        session,
        process.id,
        'NEEDS_REVISION',
        'Faltam detalhes sobre reprodutibilidade.',
        triador.id,
    )
    assert decision.outcome == 'NEEDS_REVISION'
    assert new_status == 'OPEN'
    assert next_run == 2

    # Check that Run 1 is COMPLETED and Run 2 is IN_PROGRESS
    act, run_2, form_inst_2, _, _ = await get_current_form_instance(
        session, process.id, 'proposal_submission'
    )
    assert run_2.run_number == 2
    assert run_2.status == 'IN_PROGRESS'
    assert not form_inst_2.is_submitted

    # Check that previous values were cloned into form_inst_2
    fv_stmt = select(FormValue).where(
        FormValue.form_instance_id == form_inst_2.id
    )
    cloned_vals = (await session.execute(fv_stmt)).scalars().all()
    assert len(cloned_vals) > 0


@pytest.mark.asyncio
async def test_process_engine_flow_rejected(session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    triador = await _make_bracvam(session)

    ptv = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'pre_validated_method')
        )
    ).scalar_one()

    process = await instantiate_process(
        session, ptv, 'Estudo Inviável', user.id
    )

    vals = {
        'method_title': 'Método Inviável',
        'endpoint_target': 'phototoxicity',
        'scientific_justification': 'Sem fundamentação científica.',
        'pre_validation_evidence': 'Evidências prévias de repetibilidade.',
        'study_protocol_file': 'protocolo.pdf',
    }
    await submit_proposal_form(
        session, process.id, 'proposal_submission', vals, user.id
    )

    decision, new_status, next_run = await execute_triage_decision(
        session,
        process.id,
        'REJECTED',
        'Método fora do escopo de métodos alternativos.',
        triador.id,
    )
    assert decision.outcome == 'REJECTED'
    assert new_status == 'CLOSED'
    assert next_run is None

    p_refreshed = (
        await session.execute(
            select(ProcessInstance).where(ProcessInstance.id == process.id)
        )
    ).scalar_one()
    assert p_refreshed.status == 'CLOSED'
    assert p_refreshed.closed_at is not None


@pytest.mark.asyncio
async def test_complete_activity_run_marks_run_activity_and_tasks_completed(
    session,
):
    """Teste unitário isolado do helper `_complete_activity_run` (Issue #22,

    FR-009) — chama o helper diretamente, sem passar por
    `submit_proposal_form`/`execute_triage_decision` (cobertos em outros
    testes), só para provar o efeito do helper em si.
    """
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()

    pt_stmt = (
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(ProcessTemplate.key == 'pre_validated_method')
    )
    ptv = (await session.execute(pt_stmt)).scalar_one()
    process = await instantiate_process(
        session, ptv, 'Helper de conclusão isolado', user.id
    )

    act = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process.id,
            ActivityInstance.key == 'proposal_submission',
        )
    )
    run = await session.scalar(
        select(ActivityRun).where(ActivityRun.activity_instance_id == act.id)
    )
    tasks = (
        await session.scalars(
            select(Task).where(Task.activity_run_id == run.id)
        )
    ).all()
    assert run.status == 'IN_PROGRESS'
    assert act.status == 'IN_PROGRESS'
    assert tasks
    assert all(t.status == 'READY' for t in tasks)

    await _complete_activity_run(session, run, act, user.id)

    assert run.status == 'COMPLETED'
    assert run.completed_at is not None
    assert act.status == 'COMPLETED'
    for task in tasks:
        assert task.status == 'COMPLETED'
        assert task.completed_at is not None
