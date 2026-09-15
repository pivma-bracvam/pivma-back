"""Spec 024 - Task.due_date derivado do SLA declarado da atividade.

Cobre FR-001/FR-002/FR-003 no motor de processos, nos quatro pontos que
criam uma `Task` hoje: `_init_first_activity` (primeira atividade),
`_unblock_triage_activity` e `_open_new_submission_run` (caminhos legados,
anteriores à Spec 017, que resolvem `proposal_submission`/`triage_evaluation`
pela chave em vez do motor genérico de dependências) e `_activate_activity`
(motor genérico, hoje só acionado após aprovação de triagem). Usa o método
oficial `validated_method_dossier` (Spec 011/017), que já declara
`sla_hours` em `proposal_submission` (168h) e `triage_evaluation` (72h) e tem
uma Fase 2 de exemplo (`planning_preview`) sem `sla_hours`.
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
from tests.factories.user_factory import UserFactory

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
    triador = UserFactory()
    session.add(triador)
    await session.commit()
    process = await instantiate_process(session, ptv, title, user.id)
    return process, user, triador


async def _task_for(session, process_id, activity_key) -> tuple[
    ActivityRun, Task
]:
    act = (
        await session.execute(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process_id,
                ActivityInstance.key == activity_key,
            )
        )
    ).scalar_one()
    run = (
        await session.execute(
            select(ActivityRun)
            .where(ActivityRun.activity_instance_id == act.id)
            .order_by(ActivityRun.run_number.desc())
        )
    ).scalars().first()
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
async def test_triage_evaluation_gets_own_due_date_via_legacy_unblock(
    session,
):
    """`triage_evaluation` é desbloqueada por `_unblock_triage_activity`

    (caminho legado hardcoded, anterior ao motor genérico de dependências da
    Spec 017) — não por `_activate_activity`. `due_date` precisa valer nos
    dois caminhos.
    """
    await bootstrap_all_templates(session)
    process, user, _triador = await _instantiate(
        session, 'Instância - triagem desbloqueada'
    )

    await submit_proposal_form(
        session, process.id, 'proposal_submission', SUBMISSION_VALUES,
        user.id,
    )

    submission_run, submission_task = await _task_for(
        session, process.id, 'proposal_submission'
    )
    triage_run, triage_task = await _task_for(
        session, process.id, 'triage_evaluation'
    )

    assert triage_task.due_date == triage_run.started_at + timedelta(
        hours=72
    )
    assert triage_run.started_at != submission_run.started_at
    assert triage_task.due_date != submission_task.due_date


@pytest.mark.asyncio
async def test_planning_preview_activated_by_triage_approval_has_no_due_date(
    session,
):
    """`planning_preview` não declara `sla_hours` — sem prazo, mesmo

    desbloqueada pelo motor genérico (`_activate_activity`, via aprovação de
    triagem) (FR-002).
    """
    await bootstrap_all_templates(session)
    process, user, triador = await _instantiate(
        session, 'Instância - fase 2 sem prazo'
    )

    await submit_proposal_form(
        session, process.id, 'proposal_submission', SUBMISSION_VALUES,
        user.id,
    )
    await execute_triage_decision(
        session, process.id, 'APPROVED', 'Aprovado.', triador.id
    )

    _run, task = await _task_for(session, process.id, 'planning_preview')

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
        session, process.id, 'proposal_submission', SUBMISSION_VALUES,
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
    assert second_task.due_date == second_run.started_at + timedelta(
        hours=168
    )
    assert second_run.started_at != first_run.started_at
    assert second_task.due_date != first_task.due_date
