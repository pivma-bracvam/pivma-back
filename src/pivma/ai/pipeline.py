import time
from datetime import datetime, timezone
from uuid import uuid4

from pivma.ai.contracts import (
    AIStepExecutionLog,
    OperationalEventIndex,
    PipelineContext,
    PipelineExecutionGroup,
)
from pivma.ai.steps.context_extraction import ContextExtractionStep
from pivma.ai.steps.mock_evaluation import MockEvaluationStep
from pivma.ai.steps.verdict_synthesis import VerdictSynthesisStep
from pivma.core.logging import get_ai_logger, get_operational_logger
from pivma.core.sse_broadcaster import broadcaster


class FormAIPipelineEngine:
    """Orquestrador da avaliação de formulários em 3 etapas."""

    def __init__(self):
        self.step_1 = ContextExtractionStep()
        self.step_2 = MockEvaluationStep()
        self.step_3 = VerdictSynthesisStep()

    def run_field_pipeline(
        self, context: PipelineContext
    ) -> PipelineExecutionGroup:
        pipeline_start = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        correlation_id = context.correlation_id

        steps_logs: list[AIStepExecutionLog] = []
        total_cost = 0.0

        ai_logger = get_ai_logger()
        app_logger = get_operational_logger()

        steps = [self.step_1, self.step_2, self.step_3]

        for step in steps:
            res = step.execute(context)
            total_cost += res.simulated_cost

            step_log = AIStepExecutionLog(
                event_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
                correlation_id=correlation_id,
                pipeline_name="form_ai_field_evaluation",
                field_key=context.field_key,
                step_order=res.step_order,
                step_name=res.step_name,
                status=res.status,
                step_duration_ms=res.duration_ms,
                simulated_cost=res.simulated_cost,
                input_payload=res.input_payload,
                output_payload=res.output_payload,
                error_details={"error": res.error} if res.error else None,
            )
            steps_logs.append(step_log)

            # Gravar no log especializado de IA (logs/ai/ai_steps.jsonl)
            ai_logger.info(
                "ai_step_executed",
                **step_log.model_dump(mode="json"),
            )
            broadcaster.broadcast_ai_step(step_log.model_dump(mode="json"))

        total_duration_ms = round(
            (time.perf_counter() - pipeline_start) * 1000, 2
        )
        completed_at = datetime.now(timezone.utc)

        # Gravar no Índice Operacional Geral (logs/application/events.jsonl)
        op_event = OperationalEventIndex(
            event_id=uuid4(),
            timestamp=completed_at,
            operation_type="FORM_AI_FIELD_EVALUATION",
            correlation_id=correlation_id,
            resource_id=str(context.form_instance_id),
            status="SUCCESS",
            total_duration_ms=total_duration_ms,
            specialized_log_ref=f"logs/ai/ai_steps.jsonl#{correlation_id}",
            metadata={
                "field_key": context.field_key,
                "total_simulated_cost": total_cost,
                "steps_count": len(steps_logs),
            },
        )
        app_logger.info(
            "operational_event",
            **op_event.model_dump(mode="json"),
        )
        broadcaster.broadcast_operational(op_event.model_dump(mode="json"))

        return PipelineExecutionGroup(
            correlation_id=correlation_id,
            pipeline_name="form_ai_field_evaluation",
            form_instance_id=context.form_instance_id,
            field_key=context.field_key,
            status="COMPLETED",
            started_at=started_at,
            completed_at=completed_at,
            total_duration_ms=total_duration_ms,
            total_cost=round(total_cost, 6),
            steps=steps_logs,
            verdict=context.data.get("verdict"),
        )
