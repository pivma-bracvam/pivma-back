# ruff: noqa: PLR2004
"""Integração — observabilidade da pré-avaliação (Spec 014, US4 / achado M4).

Garante que as etapas `criterion_evaluation` de uma execução são lidas do log
e agrupadas por `correlation_id`, no formato atual (sem `verdict` legado).
"""

import json
from uuid import uuid4

from pivma.ai.contracts import AIStepExecutionLog
from pivma.core.log_service import LogQueryService


def _line(cid, order):
    return AIStepExecutionLog(
        correlation_id=cid,
        pipeline_name='form_ai_pre_evaluation',
        field_key=f'criterio {order}',
        step_order=order,
        step_name='criterion_evaluation',
        step_duration_ms=10.0 + order,
        real_cost=0.002,
        model_name='fast',
        input_payload={'check_type': 'conformity'},
        output_payload={'conclusion': 'compliant'},
    ).model_dump(mode='json')


def test_ai_pipeline_groups_criterion_steps_by_run(tmp_path):
    run_a, run_b = uuid4(), uuid4()
    log_file = tmp_path / 'ai_steps.jsonl'
    lines = [
        _line(run_a, 1),
        _line(run_a, 2),
        _line(run_b, 1),
        _line(run_a, 3),
    ]
    log_file.write_text(
        '\n'.join(json.dumps(d) for d in lines) + '\n', encoding='utf-8'
    )

    service = LogQueryService(ai_logs_dir=tmp_path)

    all_groups = service.get_ai_pipeline_groups()
    groups = {str(g.correlation_id): g for g in all_groups}
    assert set(groups) == {str(run_a), str(run_b)}

    group_a = groups[str(run_a)]
    assert group_a.pipeline_name == 'form_ai_pre_evaluation'
    assert [s.step_order for s in group_a.steps] == [1, 2, 3]
    assert all(s.step_name == 'criterion_evaluation' for s in group_a.steps)
    assert round(group_a.total_cost, 6) == 0.006
    assert not hasattr(group_a, 'verdict')

    filtered = service.get_ai_pipeline_groups(correlation_id=str(run_b))
    assert len(filtered) == 1
    assert len(filtered[0].steps) == 1
