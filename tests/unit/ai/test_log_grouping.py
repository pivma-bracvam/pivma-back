# ruff: noqa: PLR2004, PLC2701
"""Unit — agrupamento de etapas de pré-avaliação (Spec 014, US4)."""

from uuid import uuid4

from pivma.ai.contracts import AIStepExecutionLog
from pivma.core.log_service import _build_pipeline_group


def _step(cid, order, cost=0.01, duration=12.0):
    return AIStepExecutionLog(
        correlation_id=cid,
        pipeline_name='form_ai_pre_evaluation',
        field_key=f'criterio {order}',
        step_order=order,
        step_name='criterion_evaluation',
        step_duration_ms=duration,
        real_cost=cost,
        model_name='fast',
        input_payload={'check_type': 'conformity'},
        output_payload={'conclusion': 'compliant'},
    )


def test_groups_criterion_steps_by_correlation_id():
    cid = uuid4()
    steps = [_step(cid, 2), _step(cid, 1), _step(cid, 3)]

    group = _build_pipeline_group(str(cid), steps)

    assert group.correlation_id == cid
    assert group.pipeline_name == 'form_ai_pre_evaluation'
    assert [s.step_order for s in group.steps] == [1, 2, 3]
    assert group.total_cost == 0.03
    assert round(group.total_duration_ms, 2) == 36.0
    # Formato legado removido: sem campo de veredito.
    assert not hasattr(group, 'verdict')


def test_empty_step_list_is_handled():
    cid = uuid4()
    group = _build_pipeline_group(str(cid), [])
    assert group.correlation_id == cid
    assert group.steps == []
