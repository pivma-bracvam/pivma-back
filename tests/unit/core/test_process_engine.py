# ruff: noqa: PLR2004, PLR0914, PLR0915

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    FormValue,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import (
    ValidationError,
    execute_triage_decision,
    get_current_form_instance,
    instantiate_process,
    save_field_reviews,
    save_form_values_draft,
    submit_proposal_form,
)
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_full_process_engine_flow_approved(session):
    # 1. Setup template
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    triador = UserFactory()
    session.add(triador)
    await session.commit()

    pt_stmt = (
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(ProcessTemplate.key == 'full_validation')
    )
    ptv = (await session.execute(pt_stmt)).scalar_one()

    # 2. Instantiate Process
    process = await instantiate_process(
        session, ptv, 'Estudo de Irritação Ocular', user.id
    )
    assert process.status == 'SUBMISSION'
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
    draft_vals = {
        'method_title': 'Método 3T3 NRU',
        'endpoint_target': 'ocular_irritation',
    }
    form_inst = await save_form_values_draft(
        session, process.id, 'proposal_submission', draft_vals, user.id
    )
    assert not form_inst.is_submitted

    # 4. Fail Submit without required fields
    with pytest.raises(ValidationError):
        await submit_proposal_form(
            session, process.id, 'proposal_submission', draft_vals, user.id
        )

    # 5. Submit valid form
    full_vals = {
        'method_title': 'Método 3T3 NRU Completo',
        'endpoint_target': 'ocular_irritation',
        'scientific_justification': 'Justificativa baseada em ensaio celular.',
        'study_protocol_file': 'protocolo.pdf',
    }
    sub_act, sub_run, artifact = await submit_proposal_form(
        session, process.id, 'proposal_submission', full_vals, user.id
    )

    assert sub_act.status == 'COMPLETED'
    assert sub_run.status == 'COMPLETED'
    assert artifact.key == 'proposal_dossier'

    # Verify process moved to TRIAGE and triage unblocked
    p_refreshed = (
        await session.execute(
            select(ProcessInstance).where(ProcessInstance.id == process.id)
        )
    ).scalar_one()
    assert p_refreshed.status == 'TRIAGE'

    triage_act = (
        await session.execute(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process.id,
                ActivityInstance.key == 'triage_evaluation',
            )
        )
    ).scalar_one()
    assert triage_act.status == 'READY'

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
    assert new_status == 'PLANNING'
    assert next_run is None


@pytest.mark.asyncio
async def test_process_engine_flow_diligence_reexecution(session):
    # Setup
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    triador = UserFactory()
    session.add(triador)
    await session.commit()

    ptv = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'full_validation')
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
    assert new_status == 'SUBMISSION'
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
    triador = UserFactory()
    session.add(triador)
    await session.commit()

    ptv = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'full_validation')
        )
    ).scalar_one()

    process = await instantiate_process(
        session, ptv, 'Estudo Inviável', user.id
    )

    vals = {
        'method_title': 'Método Inviável',
        'endpoint_target': 'phototoxicity',
        'scientific_justification': 'Sem fundamentação científica.',
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
