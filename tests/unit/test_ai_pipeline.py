from uuid import uuid4

from pivma.ai.contracts import PipelineContext
from pivma.ai.pipeline import FormAIPipelineEngine
from pivma.ai.steps.context_extraction import ContextExtractionStep
from pivma.ai.steps.mock_evaluation import MockEvaluationStep
from pivma.ai.steps.verdict_synthesis import VerdictSynthesisStep


def test_context_extraction_step():
    step = ContextExtractionStep()
    context = PipelineContext(
        form_instance_id=uuid4(),
        field_key='scientific_justification',
        field_label='Justificativa Científica',
        submitted_value='Proposta de teste para validação de citotoxicidade.',
        instructions='Verificar fundamentação biológica.',
    )
    result = step.execute(context)
    assert result.step_order == 1  # noqa: PLR2004
    assert result.step_name == 'context_extraction'
    assert result.status == 'SUCCESS'
    assert result.duration_ms >= 0.0
    assert result.simulated_cost > 0.0
    assert 'sanitized_length' in result.output_payload
    assert context.data.get('sanitized_context') is not None


def test_mock_evaluation_step():
    step = MockEvaluationStep()
    context = PipelineContext(
        form_instance_id=uuid4(),
        field_key='scientific_justification',
        field_label='Justificativa Científica',
        submitted_value='Proposta de teste.',
        data={'sanitized_context': 'Proposta de teste.'},
    )
    result = step.execute(context)
    assert result.step_order == 2  # noqa: PLR2004
    assert result.step_name == 'mock_evaluation'
    assert result.status == 'SUCCESS'
    assert result.duration_ms > 0.0
    assert result.simulated_cost > 0.0
    assert 'issues_found' in result.output_payload
    assert context.data.get('issues') is not None


def test_verdict_synthesis_step_defaults_to_negative():
    step = VerdictSynthesisStep()
    context = PipelineContext(
        form_instance_id=uuid4(),
        field_key='scientific_justification',
        field_label='Justificativa Científica',
        submitted_value='Proposta de teste.',
        data={
            'issues': [
                'Ausência de detalhamento dos controles positivos e negativos.'
            ]
        },
    )
    result = step.execute(context)
    assert result.step_order == 3  # noqa: PLR2004
    assert result.step_name == 'verdict_synthesis'
    assert result.status == 'SUCCESS'
    assert result.output_payload['verdict']['status'] in {
        'REPROVED',
        'NEEDS_ADJUSTMENT',
    }
    assert len(result.output_payload['verdict']['issues']) > 0
    assert len(result.output_payload['verdict']['recommendations']) > 0


def test_form_ai_pipeline_engine_executes_all_3_steps():
    engine = FormAIPipelineEngine()
    context = PipelineContext(
        form_instance_id=uuid4(),
        field_key='scientific_justification',
        field_label='Justificativa Científica',
        submitted_value='Proposta de teste.',
        instructions='Verificar fundamentação.',
    )
    group = engine.run_field_pipeline(context)
    assert group.status == 'COMPLETED'
    assert len(group.steps) == 3  # noqa: PLR2004
    assert group.steps[0].step_name == 'context_extraction'
    assert group.steps[1].step_name == 'mock_evaluation'
    assert group.steps[2].step_name == 'verdict_synthesis'
    assert group.total_duration_ms > 0.0
    assert group.total_cost > 0.0
    assert group.verdict is not None
    assert group.verdict.status in {'REPROVED', 'NEEDS_ADJUSTMENT'}
