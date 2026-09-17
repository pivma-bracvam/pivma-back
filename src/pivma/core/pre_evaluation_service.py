"""Execução assíncrona da pré-avaliação por IA (Spec 013, US2/US3/US4).

``run_pre_evaluation`` roda em ``BackgroundTasks`` do FastAPI: abre a própria
sessão, executa o pipeline por critério para cada avaliação associada,
consolida o resultado por severidade e aplica o roteamento fixo
(positivo → triagem; negativo/falha → volta ao proponente).
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pivma.ai.consolidation import EvaluatedCriterion, consolidate
from pivma.ai.evaluation_pipeline import (
    PipelineCriterion,
    PipelineItem,
    PipelineRequest,
    run_evaluation_pipeline,
)
from pivma.ai.provider import get_model_provider
from pivma.core.authorization import has_current_conflict
from pivma.core.database import engine
from pivma.core.database.models import (
    ActivityInstance,
    Artifact,
    AuditEvent,
    DirectReviewRequest,
    EvaluationAssignment,
    EvaluationCriterion,
    EvaluationRun,
    EvaluationRunItem,
    EvaluationVersion,
    FormInstance,
    FormTemplate,
    ProcessInstance,
    ReviewerFeedback,
)
from pivma.core.process_engine import (
    STATUS_AI_PRE_EVALUATION,
    STATUS_ARCHIVED,
    STATUS_CANCELLED,
    TRIAGE_TASK_TITLE,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    _advance_dependent_activities,  # noqa: PLC2701
    _open_new_submission_run,  # noqa: PLC2701
    ensure_process_mutable,
)
from pivma.core.settings import Settings

logger = logging.getLogger(__name__)

STALE_MINUTES = 15
_FILE_FIELD_TYPES = frozenset({'file_upload'})
_GENERIC_FAILURE = 'Falha ao concluir a pré-avaliação automática por IA.'


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Execução em segundo plano
# --------------------------------------------------------------------------


async def run_pre_evaluation(run_id: UUID) -> None:
    """Ponto de entrada agendado por ``BackgroundTasks``."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            await _execute(session, run_id)
        except Exception:  # noqa: BLE001 - qualquer falha vira status failed
            logger.exception('pre_evaluation.failed run_id=%s', run_id)
            await session.rollback()
            await _mark_failed(session, run_id)


async def _execute(session: AsyncSession, run_id: UUID) -> None:  # noqa: PLR0914
    run = await session.get(EvaluationRun, run_id)
    if run is None or run.status != 'in_progress':
        return
    process_status = await session.scalar(
        select(ProcessInstance.status).where(
            ProcessInstance.id == run.process_instance_id
        )
    )
    if process_status != STATUS_AI_PRE_EVALUATION:
        return

    template, fields_by_key, values = await _load_submission(session, run)
    assignments = await _active_assignments(session, template.id)
    provider = get_model_provider(Settings())

    items: list[tuple[PipelineItem, UUID]] = []
    total_cost = 0.0
    skipped_files: dict[str, str] = {}
    for assignment in assignments:
        version = await _effective_version(session, assignment)
        if version is None:
            continue
        text_keys, file_keys = _split_file_keys(
            _effective_keys(assignment, values), fields_by_key
        )
        for key in file_keys:
            field = fields_by_key.get(key)
            skipped_files.setdefault(
                key, field.label if field is not None else key
            )
        if not text_keys:
            # Anexos não são avaliados por IA (Spec 016): nenhum conteúdo de
            # arquivo é enviado ao provedor e a associação é pulada.
            continue
        content, kind = _target_content(assignment, fields_by_key, values)
        request = PipelineRequest(
            objective=version.objective,
            references=version.references or [],
            correlation_id=run.correlation_id,
            resource_id=str(run.process_instance_id),
            criteria=[
                PipelineCriterion(
                    statement=c.statement,
                    check_type=c.check_type,
                    polarity=c.polarity,
                    severity=c.severity,
                    content=content,
                    target_kind=kind,
                    required_evidence=c.required_evidence,
                    criterion_id=c.id,
                    evaluation_version_id=version.id,
                )
                for c in await _criteria(session, version.id)
            ],
        )
        outcome = await run_evaluation_pipeline(request, provider)
        total_cost += outcome.real_cost
        items.extend((item, version.id) for item in outcome.items)

    consolidation = consolidate([
        EvaluatedCriterion(item.conclusion, item.criterion.severity)
        for item, _ in items
    ])
    for (item, _), is_alert in zip(items, consolidation.alerts, strict=True):
        item.is_alert = is_alert

    for item, version_id in items:
        session.add(_run_item(run.id, version_id, item))

    process = await session.scalar(
        select(ProcessInstance)
        .where(
            ProcessInstance.id == run.process_instance_id,
            ProcessInstance.status == STATUS_AI_PRE_EVALUATION,
            ProcessInstance.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if process is None:
        await session.rollback()
        return

    snapshot = _content_fields(fields_by_key, values, assignments)
    snapshot.extend(
        {
            'field_key': key,
            'label': label,
            'ai_status': 'not_evaluated',
            'reason': 'attachment_not_ai_evaluable',
        }
        for key, label in skipped_files.items()
    )
    run.evaluated_content_snapshot = snapshot
    run.status = 'completed'
    run.consolidated_result = consolidation.result
    run.real_cost = round(total_cost, 6)
    run.provider_name = provider.name
    run.models_used = provider.models_used()
    run.finished_at = utc_now()

    report = _report_payload(run, consolidation.summary, items)
    session.add(
        Artifact(
            process_instance_id=run.process_instance_id,
            activity_run_id=run.activity_run_id,
            key='ai_pre_evaluation_report',
            name='Relatório de Pré-avaliação por IA',
            status='COMPLETED',
            metadata_payload=report,
        )
    )
    session.add(
        _audit(
            run,
            'AI_PRE_EVALUATION_COMPLETED',
            {
                'consolidated_result': consolidation.result,
            },
        )
    )

    if consolidation.result == 'positive':
        submission_act = await _submission_activity(
            session, run.process_instance_id
        )
        if submission_act is not None:
            await _advance_dependent_activities(
                session,
                process,
                submission_act,
                run.created_by,
                task_titles={'triage_evaluation': TRIAGE_TASK_TITLE},
            )
        await _set_process_status(session, run.process_instance_id, 'TRIAGE')
    else:
        await _return_to_proponent(session, run, failed=False)

    await session.commit()


async def _mark_failed(session: AsyncSession, run_id: UUID) -> None:
    run = await session.get(EvaluationRun, run_id)
    if run is None or run.status != 'in_progress':
        return
    process = await session.scalar(
        select(ProcessInstance)
        .where(
            ProcessInstance.id == run.process_instance_id,
            ProcessInstance.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if process is None or process.status in {
        STATUS_CANCELLED,
        STATUS_ARCHIVED,
    }:
        await session.rollback()
        return
    run.status = 'failed'
    run.error_summary = _GENERIC_FAILURE
    run.finished_at = utc_now()
    session.add(_audit(run, 'AI_PRE_EVALUATION_FAILED', {}))
    await _return_to_proponent(session, run, failed=True)
    await session.commit()


# --------------------------------------------------------------------------
# Roteamento
# --------------------------------------------------------------------------


async def _return_to_proponent(
    session: AsyncSession, run: EvaluationRun, *, failed: bool
) -> None:
    reason = 'Pré-avaliação automática por IA'
    if failed:
        reason += ' (falha no processamento)'
    next_run_number = await _open_new_submission_run(
        session,
        run.process_instance_id,
        reason=reason,
        task_title='Revisar submissão após a pré-avaliação por IA',
        user_id=run.created_by,
    )
    triage_act = await _triage_activity(session, run.process_instance_id)
    if triage_act is not None:
        triage_act.blocked_reason = (
            'Retornada ao proponente pela pré-avaliação por IA.'
        )
        triage_act.set_update_audit(run.created_by)
    session.add(
        AuditEvent(
            process_instance_id=run.process_instance_id,
            activity_run_id=run.activity_run_id,
            user_id=run.created_by,
            event_type='REVISION_REQUESTED',
            context_data={
                'new_run_number': next_run_number,
                'justification': reason,
                'source': 'AI_PRE_EVALUATION',
            },
        )
    )
    await _set_process_status(session, run.process_instance_id, 'SUBMISSION')


async def request_direct_review(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    justification: str | None,
) -> DirectReviewRequest:
    """Proponente ignora a IA e encaminha à triagem humana (US3)."""
    await ensure_process_mutable(session, process_id)
    run = await _latest_run(session, process_id)
    if run is None or run.status not in {'completed', 'failed'}:
        raise ConflictError('Nenhuma pré-avaliação concluída para contestar.')
    if run.status == 'completed' and run.consolidated_result == 'positive':
        raise ConflictError(
            'A pré-avaliação foi positiva; a submissão já seguiu para triagem.'
        )
    existing = await session.scalar(
        select(DirectReviewRequest).where(
            DirectReviewRequest.evaluation_run_id == run.id,
            DirectReviewRequest.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise ConflictError('Intervenção direta já solicitada.')

    request = DirectReviewRequest(
        evaluation_run_id=run.id,
        process_instance_id=process_id,
        requested_by=user_id,
        justification=justification,
    )
    request.set_creation_audit(user_id)
    session.add(request)

    await _close_open_submission_run(session, process_id, user_id)
    process = await session.get(ProcessInstance, process_id)
    submission_act = await _submission_activity(session, process_id)
    if process is not None and submission_act is not None:
        await _advance_dependent_activities(
            session,
            process,
            submission_act,
            user_id,
            task_titles={'triage_evaluation': TRIAGE_TASK_TITLE},
        )
    await _set_process_status(session, process_id, 'TRIAGE')
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            user_id=user_id,
            event_type='DIRECT_REVIEW_REQUESTED',
            context_data={'evaluation_run_id': str(run.id)},
        )
    )
    await session.commit()
    return request


async def record_feedback(
    session: AsyncSession,
    process_id: UUID,
    run_id: UUID,
    reviewer_id: UUID,
    items: list[dict[str, Any]],
) -> int:
    """Feedback do triador por critério (US4). Não altera o resultado da IA."""
    await ensure_process_mutable(session, process_id)
    if await has_current_conflict(session, reviewer_id, process_id):
        raise AuthorizationError(
            'Usuário com conflito de interesse vigente neste processo.'
        )
    run = await session.get(EvaluationRun, run_id)
    if run is None or run.process_instance_id != process_id:
        raise NotFoundError('Execução de pré-avaliação não encontrada.')

    run_item_ids = set(
        await session.scalars(
            select(EvaluationRunItem.id).where(
                EvaluationRunItem.run_id == run_id,
                EvaluationRunItem.deleted_at.is_(None),
            )
        )
    )
    recorded = 0
    for entry in items:
        item_id = entry['item_id']
        if item_id not in run_item_ids:
            raise NotFoundError('Item não pertence a esta execução.')
        existing = await session.scalar(
            select(ReviewerFeedback).where(
                ReviewerFeedback.run_item_id == item_id,
                ReviewerFeedback.reviewer_id == reviewer_id,
                ReviewerFeedback.deleted_at.is_(None),
            )
        )
        if existing is not None:
            existing.verdict = entry['verdict']
            existing.reason = entry.get('reason')
            existing.set_update_audit(reviewer_id)
        else:
            feedback = ReviewerFeedback(
                run_item_id=item_id,
                reviewer_id=reviewer_id,
                verdict=entry['verdict'],
                reason=entry.get('reason'),
            )
            feedback.set_creation_audit(reviewer_id)
            session.add(feedback)
        recorded += 1

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.activity_run_id,
            user_id=reviewer_id,
            event_type='AI_CRITERION_FEEDBACK_RECORDED',
            context_data={'run_id': str(run_id), 'count': recorded},
        )
    )
    await session.commit()
    return recorded


async def retry_run(
    session: AsyncSession, run_id: UUID, user_id: UUID
) -> EvaluationRun:
    """Cria uma nova execução (a antiga permanece imutável) — US2 T037."""
    old = await session.get(EvaluationRun, run_id)
    if old is None:
        raise NotFoundError('Execução não encontrada.')
    if old.status == 'completed':
        raise ConflictError('Execução já concluída; nada a reprocessar.')
    await ensure_process_mutable(session, old.process_instance_id)

    new_run = EvaluationRun(
        process_instance_id=old.process_instance_id,
        activity_run_id=old.activity_run_id,
        form_instance_id=old.form_instance_id,
    )
    new_run.set_creation_audit(user_id)
    session.add(new_run)
    # O reprocessamento volta a submissão para a espera pela IA; o roteamento
    # final é refeito por `_execute` ao término da nova execução.
    await _set_process_status(
        session, old.process_instance_id, STATUS_AI_PRE_EVALUATION
    )
    await session.commit()
    return new_run


async def sweep_stale_runs() -> None:
    """Marca como falha execuções presas em ``in_progress`` (startup)."""
    from sqlalchemy.exc import SQLAlchemyError  # noqa: PLC0415

    cutoff = utc_now().timestamp() - STALE_MINUTES * 60
    try:
        await _sweep_stale_runs(cutoff)
    except SQLAlchemyError:
        logger.warning('sweep_stale_runs: banco indisponível no startup')


async def _sweep_stale_runs(cutoff: float) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        stale = list(
            await session.scalars(
                select(EvaluationRun).where(
                    EvaluationRun.status == 'in_progress',
                    EvaluationRun.deleted_at.is_(None),
                )
            )
        )
        for run in stale:
            process = await session.scalar(
                select(ProcessInstance)
                .where(
                    ProcessInstance.id == run.process_instance_id,
                    ProcessInstance.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if process is None or process.status in {
                STATUS_CANCELLED,
                STATUS_ARCHIVED,
            }:
                continue
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started.timestamp() <= cutoff:
                run.status = 'failed'
                run.error_summary = _GENERIC_FAILURE
                run.finished_at = utc_now()
                session.add(_audit(run, 'AI_PRE_EVALUATION_FAILED', {}))
                await _return_to_proponent(session, run, failed=True)
        await session.commit()


# --------------------------------------------------------------------------
# Consulta
# --------------------------------------------------------------------------


async def get_pre_evaluation(
    session: AsyncSession, process_id: UUID, run_id: UUID | None
) -> dict[str, Any]:
    if run_id is not None:
        run = await session.get(EvaluationRun, run_id)
        if run is None or run.process_instance_id != process_id:
            raise NotFoundError('Execução de pré-avaliação não encontrada.')
    else:
        run = await _latest_run(session, process_id)
    if run is None:
        raise NotFoundError('Nenhuma pré-avaliação para este processo.')

    run_items = list(
        await session.scalars(
            select(EvaluationRunItem).where(
                EvaluationRunItem.run_id == run.id,
                EvaluationRunItem.deleted_at.is_(None),
            )
        )
    )
    direct_review = await session.scalar(
        select(DirectReviewRequest).where(
            DirectReviewRequest.evaluation_run_id == run.id,
            DirectReviewRequest.deleted_at.is_(None),
        )
    )
    versions_used = await _versions_used(session, run_items)
    refs_by_version = {v['version_id']: v['references'] for v in versions_used}
    evaluated_content = (
        run.evaluated_content_snapshot
        if run.evaluated_content_snapshot is not None
        else await _evaluated_content(session, run)
    )
    return {
        'run_id': run.id,
        'correlation_id': run.correlation_id,
        'status': run.status,
        'consolidated_result': run.consolidated_result,
        'provider': run.provider_name,
        'models_used': run.models_used or {},
        'real_cost': run.real_cost,
        'started_at': run.started_at,
        'finished_at': run.finished_at,
        'error_summary': run.error_summary,
        'summary': _summary_from_items(run_items),
        'attention_points': [
            {
                **_item_view(i),
                'references': refs_by_version.get(i.evaluation_version_id, []),
            }
            for i in run_items
            if i.conclusion != 'compliant'
        ],
        'evaluations': [
            {
                'definition_name': v['definition_name'],
                'version_number': v['version_number'],
                'references': v['references'],
            }
            for v in versions_used
        ],
        'evaluated_content': evaluated_content,
        'direct_review_request': (
            {
                'id': direct_review.id,
                'requested_by': direct_review.requested_by,
                'justification': direct_review.justification,
                'created_at': direct_review.created_at,
            }
            if direct_review is not None
            else None
        ),
    }


# --------------------------------------------------------------------------
# Helpers internos
# --------------------------------------------------------------------------


async def _load_submission(
    session: AsyncSession, run: EvaluationRun
) -> tuple[FormTemplate, dict[str, Any], dict[str, Any]]:
    form_inst = await session.get(FormInstance, run.form_instance_id)
    template = await session.scalar(
        select(FormTemplate)
        .where(FormTemplate.id == form_inst.form_template_id)
        .options(selectinload(FormTemplate.fields))
    )
    fields_by_key = {
        f.field_key: f for f in template.fields if f.deleted_at is None
    }
    dossier = await session.scalar(
        select(Artifact)
        .where(
            Artifact.activity_run_id == run.activity_run_id,
            Artifact.key == 'proposal_dossier',
            Artifact.deleted_at.is_(None),
        )
        .order_by(Artifact.created_at.desc())
    )
    values = {}
    if dossier and dossier.metadata_payload:
        values = dossier.metadata_payload.get('values', {})
    return template, fields_by_key, values


def _content_fields(
    fields_by_key: dict[str, Any],
    values: dict[str, Any],
    assignments: list[EvaluationAssignment],
) -> list[dict[str, Any]]:
    """Lista {field_key, label, value} dos campos cobertos pelas associações.

    Um alvo `form`/`process` (ou sem `field_keys`) cobre todos os campos.
    """
    if not assignments:
        return []
    covers_all = any(
        a.target_type in {'form', 'process'} or not (a.field_keys or [])
        for a in assignments
    )
    if covers_all:
        keys = list(values.keys())
    else:
        keys = []
        for a in assignments:
            for k in a.field_keys or []:
                if k not in keys:
                    keys.append(k)
    text_keys, _ = _split_file_keys(keys, fields_by_key)
    return [
        {
            'field_key': k,
            'label': fields_by_key[k].label if k in fields_by_key else k,
            'value': values.get(k),
        }
        for k in text_keys
    ]


async def _evaluated_content(
    session: AsyncSession, run: EvaluationRun
) -> list[dict[str, Any]]:
    """Reconstrói o conteúdo avaliado da `FormInstance` (fallback — FR-024).

    Usado quando a execução não tem snapshot (execuções pré-Spec 014 ou
    execuções que falharam).
    """
    template, fields_by_key, values = await _load_submission(session, run)
    assignments = await _active_assignments(session, template.id)
    return _content_fields(fields_by_key, values, assignments)


async def _active_assignments(
    session: AsyncSession, template_id: UUID
) -> list[EvaluationAssignment]:
    return list(
        await session.scalars(
            select(EvaluationAssignment).where(
                EvaluationAssignment.form_template_id == template_id,
                EvaluationAssignment.enabled.is_(True),
                EvaluationAssignment.deleted_at.is_(None),
            )
        )
    )


async def _effective_version(
    session: AsyncSession, assignment: EvaluationAssignment
) -> EvaluationVersion | None:
    if assignment.pinned_version_id is not None:
        version = await session.get(
            EvaluationVersion, assignment.pinned_version_id
        )
        if version is not None and version.status == 'published':
            return version
        return None
    return await session.scalar(
        select(EvaluationVersion)
        .where(
            EvaluationVersion.definition_id == assignment.definition_id,
            EvaluationVersion.status == 'published',
            EvaluationVersion.deleted_at.is_(None),
        )
        .order_by(EvaluationVersion.version_number.desc())
        .limit(1)
    )


async def _criteria(
    session: AsyncSession, version_id: UUID
) -> list[EvaluationCriterion]:
    return list(
        await session.scalars(
            select(EvaluationCriterion)
            .where(
                EvaluationCriterion.version_id == version_id,
                EvaluationCriterion.deleted_at.is_(None),
            )
            .order_by(EvaluationCriterion.order_index)
        )
    )


def _effective_keys(
    assignment: EvaluationAssignment, values: dict[str, Any]
) -> list[str]:
    keys = list(assignment.field_keys or [])
    if assignment.target_type in {'form', 'process'} or not keys:
        keys = list(values.keys())
    return keys


def _split_file_keys(
    keys: list[str], fields_by_key: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Separa (chaves de texto, chaves de anexo) de uma lista de campos."""
    text_keys, file_keys = [], []
    for key in keys:
        field = fields_by_key.get(key)
        if field is not None and field.field_type in _FILE_FIELD_TYPES:
            file_keys.append(key)
        else:
            text_keys.append(key)
    return text_keys, file_keys


def _target_content(
    assignment: EvaluationAssignment,
    fields_by_key: dict[str, Any],
    values: dict[str, Any],
) -> tuple[str, str]:
    keys, _ = _split_file_keys(
        _effective_keys(assignment, values), fields_by_key
    )
    kind = 'document' if assignment.target_type == 'document' else 'text'
    parts = []
    for key in keys:
        field = fields_by_key.get(key)
        label = field.label if field is not None else key
        parts.append(f'{label}: {values.get(key)}')
    return '\n'.join(parts), kind


def _run_item(
    run_id: UUID, version_id: UUID, item: PipelineItem
) -> EvaluationRunItem:
    return EvaluationRunItem(
        run_id=run_id,
        criterion_id=item.criterion.criterion_id,
        evaluation_version_id=version_id,
        criterion_statement=item.criterion.statement,
        check_type=item.criterion.check_type,
        polarity=item.criterion.polarity,
        severity=item.criterion.severity,
        conclusion=item.conclusion,
        is_alert=item.is_alert,
        evidence_excerpt=item.evidence_excerpt,
        evidence_location=item.evidence_location,
        justification=item.justification,
        recommendation=item.recommendation,
        inference_confidence=item.inference_confidence,
        evidence_completeness=item.evidence_completeness,
        model_layer=item.model_layer,
    )


def _report_payload(
    run: EvaluationRun,
    summary: dict[str, int],
    items: list[tuple[PipelineItem, UUID]],
) -> dict[str, Any]:
    return {
        'correlation_id': str(run.correlation_id),
        'consolidated_result': run.consolidated_result,
        'summary': summary,
        'attention_points': [
            {
                'statement': item.criterion.statement,
                'check_type': item.criterion.check_type,
                'severity': item.criterion.severity,
                'conclusion': item.conclusion,
                'is_alert': item.is_alert,
                'evidence_excerpt': item.evidence_excerpt,
                'evidence_location': item.evidence_location,
                'justification': item.justification,
                'recommendation': item.recommendation,
            }
            for item, _ in items
            if item.conclusion != 'compliant'
        ],
    }


async def _versions_used(
    session: AsyncSession, items: list[EvaluationRunItem]
) -> list[dict[str, Any]]:
    version_ids = {
        i.evaluation_version_id
        for i in items
        if i.evaluation_version_id is not None
    }
    if not version_ids:
        return []
    versions = list(
        await session.scalars(
            select(EvaluationVersion)
            .where(EvaluationVersion.id.in_(version_ids))
            .options(selectinload(EvaluationVersion.definition))
        )
    )
    return [
        {
            'version_id': v.id,
            'definition_name': (
                v.definition.name if v.definition is not None else ''
            ),
            'version_number': v.version_number,
            'references': v.references or [],
        }
        for v in versions
    ]


def _summary_from_items(items: list[EvaluationRunItem]) -> dict[str, int]:
    summary = {
        'total': len(items),
        'compliant': 0,
        'non_compliant': 0,
        'partial': 0,
        'indeterminate': 0,
    }
    for item in items:
        if item.conclusion in summary:
            summary[item.conclusion] += 1
    return summary


def _item_view(item: EvaluationRunItem) -> dict[str, Any]:
    return {
        'item_id': item.id,
        'criterion_id': item.criterion_id,
        'criterion_statement': item.criterion_statement,
        'check_type': item.check_type,
        'severity': item.severity,
        'conclusion': item.conclusion,
        'is_alert': item.is_alert,
        'evidence_excerpt': item.evidence_excerpt,
        'evidence_location': item.evidence_location,
        'justification': item.justification,
        'recommendation': item.recommendation,
        'inference_confidence': item.inference_confidence,
        'evidence_completeness': item.evidence_completeness,
    }


async def _latest_run(
    session: AsyncSession, process_id: UUID
) -> EvaluationRun | None:
    return await session.scalar(
        select(EvaluationRun)
        .where(
            EvaluationRun.process_instance_id == process_id,
            EvaluationRun.deleted_at.is_(None),
        )
        .order_by(EvaluationRun.started_at.desc())
        .limit(1)
    )


async def _triage_activity(
    session: AsyncSession, process_id: UUID
) -> ActivityInstance | None:
    return await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'triage_evaluation',
            ActivityInstance.deleted_at.is_(None),
        )
    )


async def _submission_activity(
    session: AsyncSession, process_id: UUID
) -> ActivityInstance | None:
    return await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'proposal_submission',
            ActivityInstance.deleted_at.is_(None),
        )
    )


async def _set_process_status(
    session: AsyncSession, process_id: UUID, status: str
) -> None:
    process = await session.get(ProcessInstance, process_id)
    if process is not None:
        if process.status in {STATUS_CANCELLED, STATUS_ARCHIVED}:
            raise ConflictError(
                f'Processo em status {process.status!r} não permite avanço.'
            )
        process.status = status


async def _close_open_submission_run(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> None:
    from pivma.core.database.models import ActivityRun  # noqa: PLC0415

    open_run = await session.scalar(
        select(ActivityRun)
        .join(
            ActivityInstance,
            ActivityInstance.id == ActivityRun.activity_instance_id,
        )
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'proposal_submission',
            ActivityRun.status == 'IN_PROGRESS',
            ActivityRun.deleted_at.is_(None),
        )
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
    )
    if open_run is not None:
        open_run.status = 'CANCELLED'
        open_run.set_update_audit(user_id)

        # A revisão direta (Issue #22) força a submissão a ser tratada como
        # satisfeita mesmo com uma rodada aberta cancelada — sem isto, o
        # motor genérico de dependências (`_advance_dependent_activities`)
        # nunca destravaria a triagem, porque `proposal_submission`
        # continuaria `IN_PROGRESS`.
        submission_act = await _submission_activity(session, process_id)
        if submission_act is not None:
            submission_act.status = 'COMPLETED'
            submission_act.set_update_audit(user_id)


def _audit(
    run: EvaluationRun, event_type: str, context: dict[str, Any]
) -> AuditEvent:
    return AuditEvent(
        process_instance_id=run.process_instance_id,
        activity_run_id=run.activity_run_id,
        user_id=run.created_by,
        event_type=event_type,
        context_data={'correlation_id': str(run.correlation_id), **context},
    )
