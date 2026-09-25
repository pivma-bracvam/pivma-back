"""Spec 024 - Task.due_date derivado do SLA declarado da atividade.

Cobre FR-001/FR-002/FR-003 no motor de processos, nos pontos que criam uma
`Task` hoje: `_init_first_activity` (primeira atividade),
`_open_new_submission_run` (caminho legado, anterior à Spec 017, que resolve
`proposal_submission` pela chave em vez do motor genérico de dependências) e
`_activate_activity` (motor genérico — desde a Issue #22, também usado para
`triage_evaluation`, que antes tinha um caminho bespoke próprio). Usa o
método oficial `validated_method_dossier` (Spec 011/017), que já declara
`sla_hours` em `proposal_submission` (168h) e `triage_evaluation` (72h) e tem
uma Fase 2 de atribuição de cargo (Spec 028, ex. `assign_sponsor`) sem
`sla_hours`.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    ProcessTemplate,
    ProcessTemplateVersion,
    Task,
)
from pivma.core.process_engine import (
    execute_triage_decision,
    instantiate_process,
    submit_proposal_form,
)
from tests.conftest import _make_rbac_user
from tests.factories.user_factory import UserFactory


async def _make_bracvam(session):
    """Triador com perfil BraCVAM: só ele edita a triagem (Spec 030)."""
    return await _make_rbac_user(
        session, system_key='bracvam', name='BraCVAM', codes=()
    )


SUBMISSION_VALUES = {
    'method_title': 'Método com roteiro de duas fases',
    'terminology_notes': (
        'Conceito descrito com nomenclatura atual e detalhamento '
        'suficiente para avaliação.'
    ),
}


async def _instantiate(session, title):
    ptv = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'validated_method_dossier')
        )
    ).scalar_one()
    user = UserFactory()
    session.add(user)
    await session.commit()
    triador = await _make_bracvam(session)
    process = await instantiate_process(session, ptv, title, user.id)
    return process, user, triador


async def _task_for(
    session, process_id, activity_key
) -> tuple[ActivityRun, Task]:
    act = (
        await session.execute(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process_id,
                ActivityInstance.key == activity_key,
            )
        )
    ).scalar_one()
    run = (
        (
            await session.execute(
                select(ActivityRun)
                .where(ActivityRun.activity_instance_id == act.id)
                .order_by(ActivityRun.run_number.desc())
            )
        )
        .scalars()
        .first()
    )
    task = (
        await session.execute(
            select(Task).where(Task.activity_run_id == run.id)
        )
    ).scalar_one()
    return run, task


@pytest.mark.asyncio
async def test_first_activity_due_date_uses_run_start_plus_sla(session):
    await bootstrap_all_templates(session)
    process, _user, _triador = await _instantiate(
        session, 'Instância - primeira atividade'
    )

    run, task = await _task_for(session, process.id, 'proposal_submission')

    assert task.due_date == run.started_at + timedelta(hours=168)


@pytest.mark.asyncio
async def test_triage_evaluation_gets_own_due_date(
    session,
):
    """`triage_evaluation` é desbloqueada por `_activate_activity` (motor

    genérico de dependências) desde a Issue #22 — `due_date` precisa valer
    aqui como em qualquer outra atividade dependente.
    """
    await bootstrap_all_templates(session)
    process, user, _triador = await _instantiate(
        session, 'Instância - triagem desbloqueada'
    )

    await submit_proposal_form(
        session,
        process.id,
        'proposal_submission',
        SUBMISSION_VALUES,
        user.id,
    )

    submission_run, submission_task = await _task_for(
        session, process.id, 'proposal_submission'
    )
    triage_run, triage_task = await _task_for(
        session, process.id, 'triage_evaluation'
    )

    assert triage_task.due_date == triage_run.started_at + timedelta(hours=72)
    assert triage_run.started_at != submission_run.started_at
    assert triage_task.due_date != submission_task.due_date


@pytest.mark.asyncio
async def test_role_assignment_activity_activated_by_triage_has_no_due_date(
    session,
):
    """`assign_sponsor` não declara `sla_hours` — sem prazo, mesmo

    desbloqueada pelo motor genérico (`_activate_activity`, via aprovação de
    triagem) (FR-002).
    """
    await bootstrap_all_templates(session)
    process, user, triador = await _instantiate(
        session, 'Instância - fase 2 sem prazo'
    )

    await submit_proposal_form(
        session,
        process.id,
        'proposal_submission',
        SUBMISSION_VALUES,
        user.id,
    )
    await execute_triage_decision(
        session, process.id, 'APPROVED', 'Aprovado.', triador.id
    )

    _run, task = await _task_for(session, process.id, 'assign_sponsor')

    assert task.due_date is None


@pytest.mark.asyncio
async def test_reopened_submission_run_gets_its_own_due_date(session):
    """Retrabalho (`NEEDS_REVISION`) reabre `proposal_submission` via

    `_open_new_submission_run` — o novo ciclo ganha seu próprio `due_date`,
    a partir do seu próprio início, não herdado do ciclo anterior (Edge
    Case de retrabalho, spec.md).
    """
    await bootstrap_all_templates(session)
    process, user, triador = await _instantiate(
        session, 'Instância - retrabalho da submissão'
    )

    await submit_proposal_form(
        session,
        process.id,
        'proposal_submission',
        SUBMISSION_VALUES,
        user.id,
    )
    first_run, first_task = await _task_for(
        session, process.id, 'proposal_submission'
    )

    await execute_triage_decision(
        session, process.id, 'NEEDS_REVISION', 'Faltam detalhes.', triador.id
    )
    second_run, second_task = await _task_for(
        session, process.id, 'proposal_submission'
    )

    assert second_run.run_number == first_run.run_number + 1
    assert second_task.due_date == second_run.started_at + timedelta(hours=168)
    assert second_run.started_at != first_run.started_at
    assert second_task.due_date != first_task.due_date
