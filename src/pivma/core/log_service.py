import json
from pathlib import Path
from uuid import UUID

from pivma.ai.contracts import (
    AIEvaluationVerdict,
    AIStepExecutionLog,
    OperationalEventIndex,
    PipelineExecutionGroup,
)
from pivma.core.logging import AI_LOGS_DIR, APP_LOGS_DIR


def _parse_operational_record(
    line: str,
    status: str | None,
    operation_type: str | None,
) -> OperationalEventIndex | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except Exception:
        return None

    has_ident = 'event_id' in data or 'correlation_id' in data
    match_status = not status or data.get('status') == status
    match_op = (
        not operation_type or data.get('operation_type') == operation_type
    )

    if not (has_ident and match_status and match_op):
        return None

    try:
        return OperationalEventIndex.model_validate(data)
    except Exception:
        return None


def _parse_ai_step_record(
    line: str,
    correlation_id: str | None,
) -> tuple[str, AIStepExecutionLog] | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except Exception:
        return None

    if 'correlation_id' not in data or 'step_name' not in data:
        return None

    cid = str(data['correlation_id'])
    if correlation_id and cid != str(correlation_id):
        return None

    try:
        step_log = AIStepExecutionLog.model_validate(data)
        return cid, step_log
    except Exception:
        return None


def _build_pipeline_group(
    cid: str,
    steps: list[AIStepExecutionLog],
) -> PipelineExecutionGroup:
    steps_sorted = sorted(steps, key=lambda s: s.step_order)
    total_duration = sum(s.step_duration_ms for s in steps_sorted)
    total_cost = sum(s.simulated_cost or s.real_cost for s in steps_sorted)

    verdict = None
    for s in reversed(steps_sorted):
        is_verdict_step = s.step_name == 'verdict_synthesis'
        if is_verdict_step and 'verdict' in s.output_payload:
            try:
                verdict = AIEvaluationVerdict.model_validate(
                    s.output_payload['verdict']
                )
                break
            except Exception:
                pass

    field_key = steps_sorted[0].field_key if steps_sorted else None
    started_at = steps_sorted[0].timestamp if steps_sorted else None
    completed_at = steps_sorted[-1].timestamp if steps_sorted else None

    pipeline_name = (
        steps_sorted[0].pipeline_name
        if steps_sorted
        else 'form_ai_pre_evaluation'
    )
    return PipelineExecutionGroup(
        correlation_id=UUID(cid),
        pipeline_name=pipeline_name,
        field_key=field_key,
        status='COMPLETED',
        started_at=started_at,
        completed_at=completed_at,
        total_duration_ms=round(total_duration, 2),
        total_cost=round(total_cost, 6),
        steps=steps_sorted,
        verdict=verdict,
    )


def _read_operational_file(
    log_file: Path,
    remaining_limit: int,
    status: str | None,
    operation_type: str | None,
) -> list[OperationalEventIndex]:
    records: list[OperationalEventIndex] = []
    if not log_file.is_file():
        return records

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError:
        return records

    for raw_line in reversed(lines):
        rec = _parse_operational_record(raw_line, status, operation_type)
        if rec is not None:
            records.append(rec)
            if len(records) >= remaining_limit:
                break
    return records


def _collect_ai_steps(
    log_file: Path,
    grouped_steps: dict[str, list[AIStepExecutionLog]],
    correlation_id: str | None,
) -> None:
    if not log_file.is_file():
        return

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError:
        return

    for raw_line in lines:
        parsed = _parse_ai_step_record(raw_line, correlation_id)
        if parsed is not None:
            cid, step_log = parsed
            if cid not in grouped_steps:
                grouped_steps[cid] = []
            grouped_steps[cid].append(step_log)


class LogQueryService:
    """Serviço de leitura e agregação dos logs estruturados JSONL."""

    def __init__(
        self,
        app_logs_dir: Path = APP_LOGS_DIR,
        ai_logs_dir: Path = AI_LOGS_DIR,
    ) -> None:
        self.app_logs_dir = app_logs_dir
        self.ai_logs_dir = ai_logs_dir

    def get_operational_events(
        self,
        limit: int = 100,
        status: str | None = None,
        operation_type: str | None = None,
    ) -> list[OperationalEventIndex]:
        events: list[OperationalEventIndex] = []
        if not self.app_logs_dir.exists():
            return events

        log_files = sorted(self.app_logs_dir.glob('*.jsonl'), reverse=True)
        for log_file in log_files:
            rem = limit - len(events)
            events.extend(
                _read_operational_file(log_file, rem, status, operation_type)
            )
            if len(events) >= limit:
                break

        return events

    def get_ai_pipeline_groups(
        self,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[PipelineExecutionGroup]:
        if not self.ai_logs_dir.exists():
            return []

        grouped_steps: dict[str, list[AIStepExecutionLog]] = {}
        for log_file in sorted(self.ai_logs_dir.glob('*.jsonl'), reverse=True):
            _collect_ai_steps(log_file, grouped_steps, correlation_id)

        groups: list[PipelineExecutionGroup] = []
        for cid, steps in grouped_steps.items():
            groups.append(_build_pipeline_group(cid, steps))
            if len(groups) >= limit:
                break

        return groups


log_query_service = LogQueryService()
