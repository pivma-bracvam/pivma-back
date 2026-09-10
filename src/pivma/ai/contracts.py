from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AIEvaluationVerdict(BaseModel):
    field_key: str
    status: str = Field(default='REPROVED')
    confidence_score: float = Field(default=0.85)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = ConfigDict(from_attributes=True)


class OperationalEventIndex(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    operation_type: str
    correlation_id: UUID
    actor_user_id: UUID | None = None
    resource_id: str | None = None
    status: str = Field(default='SUCCESS')
    total_duration_ms: float
    specialized_log_ref: str | None = None
    error_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class AIStepExecutionLog(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: UUID
    pipeline_name: str = 'form_ai_pre_evaluation'
    field_key: str
    step_order: int
    step_name: str
    status: str = Field(default='SUCCESS')
    step_duration_ms: float
    simulated_cost: float = 0.0
    real_cost: float = 0.0
    model_name: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_details: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class PipelineExecutionGroup(BaseModel):
    correlation_id: UUID
    pipeline_name: str = 'form_ai_field_evaluation'
    form_instance_id: UUID | None = None
    field_key: str | None = None
    status: str = Field(default='COMPLETED')
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_duration_ms: float = 0.0
    total_cost: float = 0.0
    steps: list[AIStepExecutionLog] = Field(default_factory=list)
    verdict: AIEvaluationVerdict | None = None

    model_config = ConfigDict(from_attributes=True)


@dataclass
class PipelineContext:
    form_instance_id: UUID
    field_key: str
    field_label: str
    submitted_value: Any
    instructions: str | None = None
    validation_rules: dict[str, Any] | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    step_order: int
    step_name: str
    status: str
    duration_ms: float
    simulated_cost: float
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    error: str | None = None
