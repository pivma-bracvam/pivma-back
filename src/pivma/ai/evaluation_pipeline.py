"""Pipeline de pré-avaliação dirigido por configuração (Spec 013).

Substitui o veredito fixo por campo (Spec 010) por uma avaliação por
critério: preparação → avaliação de cada critério (na camada de modelo
adequada) → consolidação → síntese. A orquestração fica escondida aqui;
os serviços chamam apenas ``run_evaluation_pipeline``.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pivma.ai.consolidation import EvaluatedCriterion, consolidate
from pivma.ai.contracts import AIStepExecutionLog, OperationalEventIndex
from pivma.ai.provider import EvaluationInput, ModelProvider
from pivma.core.logging import get_ai_logger, get_operational_logger
from pivma.core.sse_broadcaster import broadcaster

PIPELINE_NAME = 'form_ai_pre_evaluation'
OPERATION_TYPE = 'FORM_AI_PRE_EVALUATION'


@dataclass
class PipelineCriterion:
    statement: str
    check_type: str
    polarity: str
    severity: str
    content: str
    required_evidence: str | None = None
    target_kind: str = 'text'
    criterion_id: UUID | None = None
    evaluation_version_id: UUID | None = None


@dataclass
class PipelineRequest:
    objective: str
    criteria: list[PipelineCriterion]
    correlation_id: UUID = field(default_factory=uuid4)
    references: list[dict[str, Any]] = field(default_factory=list)
    resource_id: str | None = None


@dataclass
class PipelineItem:
    criterion: PipelineCriterion
    conclusion: str
    is_alert: bool
    model_layer: str
    evidence_excerpt: str | None = None
    evidence_location: str | None = None
    justification: str | None = None
    recommendation: str | None = None
    inference_confidence: float | None = None
    evidence_completeness: str | None = None


@dataclass
class PipelineOutcome:
    consolidated_result: str
    summary: dict[str, int]
    items: list[PipelineItem]
    real_cost: float
    models_used: dict[str, str | None]
    provider_name: str


async def run_evaluation_pipeline(
    request: PipelineRequest, provider: ModelProvider
) -> PipelineOutcome:
    started = time.perf_counter()
    ai_logger = get_ai_logger()
    app_logger = get_operational_logger()

    items: list[PipelineItem] = []
    total_cost = 0.0

    for order, criterion in enumerate(request.criteria, start=1):
        step_start = time.perf_counter()
        data = EvaluationInput(
            objective=request.objective,
            statement=criterion.statement,
            check_type=criterion.check_type,
            polarity=criterion.polarity,
            content=criterion.content,
            target_kind=criterion.target_kind,
            required_evidence=criterion.required_evidence,
            references=request.references,
        )
        outcome = await provider.evaluate_criterion(data)
        total_cost += outcome.cost
        verdict = outcome.verdict

        items.append(
            PipelineItem(
                criterion=criterion,
                conclusion=verdict.conclusion,
                is_alert=False,
                model_layer=outcome.model_layer,
                evidence_excerpt=verdict.evidence_excerpt,
                evidence_location=verdict.evidence_location,
                justification=verdict.justification,
                recommendation=verdict.recommendation,
                inference_confidence=verdict.inference_confidence,
                evidence_completeness=verdict.evidence_completeness,
            )
        )

        step_ms = round((time.perf_counter() - step_start) * 1000, 2)
        step_log = AIStepExecutionLog(
            correlation_id=request.correlation_id,
            pipeline_name=PIPELINE_NAME,
            field_key=criterion.statement[:64],
            step_order=order,
            step_name='criterion_evaluation',
            step_duration_ms=step_ms,
            real_cost=outcome.cost,
            model_name=outcome.model_layer,
            input_payload={
                'check_type': criterion.check_type,
                'polarity': criterion.polarity,
                'target_kind': criterion.target_kind,
            },
            output_payload={'conclusion': verdict.conclusion},
        )
        ai_logger.info('ai_step_executed', **step_log.model_dump(mode='json'))
        broadcaster.broadcast_ai_step(step_log.model_dump(mode='json'))

    consolidation = consolidate([
        EvaluatedCriterion(i.conclusion, i.criterion.severity) for i in items
    ])
    for item, is_alert in zip(items, consolidation.alerts, strict=True):
        item.is_alert = is_alert

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    op_event = OperationalEventIndex(
        timestamp=datetime.now(timezone.utc),
        operation_type=OPERATION_TYPE,
        correlation_id=request.correlation_id,
        resource_id=request.resource_id,
        status='SUCCESS',
        total_duration_ms=total_ms,
        specialized_log_ref=(
            f'logs/ai/ai_steps.jsonl#{request.correlation_id}'
        ),
        metadata={
            'provider': provider.name,
            'models_used': provider.models_used(),
            'real_cost': round(total_cost, 6),
            'consolidated_result': consolidation.result,
            'criteria_count': len(items),
        },
    )
    app_logger.info('operational_event', **op_event.model_dump(mode='json'))
    broadcaster.broadcast_operational(op_event.model_dump(mode='json'))

    return PipelineOutcome(
        consolidated_result=consolidation.result,
        summary=consolidation.summary,
        items=items,
        real_cost=round(total_cost, 6),
        models_used=provider.models_used(),
        provider_name=provider.name,
    )
