"""Revisão do retorno ao proponente (Spec 030, US4).

Quando a pré-avaliação por IA ou a triagem devolvem a submissão, o
proponente lê o retorno e escolhe: revisar a submissão, contestar a IA ou
desistir do processo. As três escolhas reaproveitam efeitos que já existiam
(reabrir a submissão, revisão direta e encerramento de pendências).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pivma.core import pre_evaluation_service
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    Decision,
    ProcessInstance,
)
from pivma.core.process_engine import (
    RETURN_REVIEW_KEY,
    RETURN_SOURCE_AI,
    STATUS_CLOSED,
    STATUS_OPEN,
    AccessLevel,
    ConflictError,
    NotFoundError,
    ValidationError,
    _cancel_pending_children,  # noqa: PLC2701
    _open_new_submission_run,  # noqa: PLC2701
    ensure_process_mutable,
    require_activity_access,
    utc_now,
)

CHOICE_REVISE = 'REVISE'
CHOICE_CONTEST_AI = 'CONTEST_AI'
CHOICE_WITHDRAW = 'WITHDRAW'


def available_choices(source: str) -> list[str]:
    if source == RETURN_SOURCE_AI:
        return [CHOICE_REVISE, CHOICE_CONTEST_AI, CHOICE_WITHDRAW]
    return [CHOICE_REVISE, CHOICE_WITHDRAW]


async def _review_activity(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    access: AccessLevel,
) -> ActivityInstance:
    act = await session.scalar(
        select(ActivityInstance)
        .join(
            ProcessInstance,
            ProcessInstance.id == ActivityInstance.process_instance_id,
        )
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == RETURN_REVIEW_KEY,
            ActivityInstance.deleted_at.is_(None),
            ProcessInstance.deleted_at.is_(None),
        )
    )
    if act is None:
        raise NotFoundError('Revisão do retorno não encontrada.')
    await require_activity_access(session, user_id, act, access)
    return act


async def _open_run(
    session: AsyncSession, act: ActivityInstance, *, lock: bool = False
) -> ActivityRun | None:
    stmt = (
        select(ActivityRun)
        .where(
            ActivityRun.activity_instance_id == act.id,
            ActivityRun.status == 'IN_PROGRESS',
            ActivityRun.deleted_at.is_(None),
        )
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
        .options(selectinload(ActivityRun.tasks))
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(stmt)


async def get_open_return_review(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Conteúdo do retorno pendente (FR-037). Exige ver a atividade."""
    act = await _review_activity(session, process_id, user_id, 'view')
    run = await _open_run(session, act)
    if run is None:
        raise NotFoundError('Nenhum retorno pendente neste processo.')

    source = run.execution_reason
    ai_pre_evaluation = None
    triage_decision = None
    if source == RETURN_SOURCE_AI:
        ai_pre_evaluation = await pre_evaluation_service.get_pre_evaluation(
            session, process_id, None
        )
    else:
        decision = await session.scalar(
            select(Decision)
            .where(
                Decision.process_instance_id == process_id,
                Decision.outcome == 'NEEDS_REVISION',
                Decision.deleted_at.is_(None),
            )
            .order_by(Decision.decided_at.desc())
            .limit(1)
        )
        if decision is not None:
            triage_decision = {
                'outcome': decision.outcome,
                'justification': decision.justification,
                'decided_at': decision.decided_at,
            }

    due_dates = [t.due_date for t in run.tasks if t.due_date is not None]
    return {
        'run_number': run.run_number,
        'source': source,
        'opened_at': run.started_at,
        'due_date': min(due_dates) if due_dates else None,
        'available_choices': available_choices(source),
        'ai_pre_evaluation': ai_pre_evaluation,
        'triage_decision': triage_decision,
    }


def _complete_review_run(
    act: ActivityInstance, run: ActivityRun, user_id: UUID
) -> None:
    now = utc_now()
    run.status = 'COMPLETED'
    run.completed_at = now
    run.set_update_audit(user_id)
    for task in run.tasks:
        if task.status not in {'COMPLETED', 'CANCELLED'}:
            task.status = 'COMPLETED'
            task.completed_at = now
            task.set_update_audit(user_id)
    act.status = 'BLOCKED'
    act.blocked_reason = 'Sem retorno pendente.'
    act.set_update_audit(user_id)


async def decide_return_review(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    choice: str,
    justification: str | None,
) -> dict[str, Any]:
    """Registra a escolha do proponente e aplica o efeito (FR-039/FR-040)."""
    act = await _review_activity(session, process_id, user_id, 'edit')
    process = await ensure_process_mutable(session, process_id)

    # TODO(spec-030): teste de concorrência adiado — provar que duas escolhas
    # simultâneas na mesma execução da revisão do retorno têm um único
    # vencedor e a outra recebe ConflictError (FR-040), com duas sessões
    # reais.
    run = await _open_run(session, act, lock=True)
    if run is None:
        raise ConflictError('Nenhum retorno pendente para decidir.')
    source = run.execution_reason
    if choice not in available_choices(source):
        raise ValidationError(
            f'Escolha {choice!r} não se aplica a um retorno de {source}.'
        )

    _complete_review_run(act, run, user_id)
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='RETURN_REVIEW_DECIDED',
            context_data={
                'choice': choice,
                'source': source,
                'justification': justification,
                'run_number': run.run_number,
            },
        )
    )

    submission_run = None
    if choice == CHOICE_REVISE:
        submission_run = await _open_new_submission_run(
            session,
            process_id,
            reason=f'Revisão após retorno ({source})',
            task_title='Revisar e Ajustar Submissão da Proposta',
            user_id=user_id,
        )
        await session.commit()
    elif choice == CHOICE_CONTEST_AI:
        try:
            await pre_evaluation_service.request_direct_review(
                session, process_id, user_id, justification
            )
        except ConflictError:
            await session.rollback()
            raise
    else:
        process.status = STATUS_CLOSED
        process.closed_at = utc_now()
        process.closure_reason = (
            'Desistência do proponente na revisão do retorno'
            + (f': {justification}' if justification else '.')
        )
        process.set_update_audit(user_id)
        counts = await _cancel_pending_children(session, process, user_id)
        session.add(
            AuditEvent(
                process_instance_id=process_id,
                user_id=user_id,
                event_type='PROCESS_WITHDRAWN',
                context_data={
                    'previous_status': STATUS_OPEN,
                    'result_status': STATUS_CLOSED,
                    'cancelled_counts': counts,
                },
            )
        )
        await session.commit()

    return {
        'choice': choice,
        'process_status': process.status,
        'submission_run': submission_run,
    }
