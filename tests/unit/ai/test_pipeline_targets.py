# ruff: noqa: PLR2004
"""Pipeline — alvo documento/OCR/imagem sempre indeterminado (Spec 013)."""

import pytest

from pivma.ai.evaluation_pipeline import (
    PipelineCriterion,
    PipelineRequest,
    run_evaluation_pipeline,
)
from pivma.ai.provider import FakeModelProvider


def _criterion(**overrides):
    base = dict(
        statement='Deve conter procedimento detalhado',
        check_type='quality',
        polarity='positive',
        severity='high',
        content='conteudo textual relevante com procedimento detalhado',
        target_kind='text',
    )
    base.update(overrides)
    return PipelineCriterion(**base)


@pytest.mark.asyncio
async def test_document_target_is_indeterminate_without_model_call():
    request = PipelineRequest(
        objective='obj',
        criteria=[_criterion(target_kind='document')],
    )

    outcome = await run_evaluation_pipeline(request, FakeModelProvider())

    assert outcome.items[0].conclusion == 'indeterminate'
    assert outcome.items[0].model_layer == 'none'
    assert outcome.consolidated_result == 'positive'


@pytest.mark.asyncio
async def test_layer_matches_check_type():
    request = PipelineRequest(
        objective='obj',
        criteria=[
            _criterion(check_type='presence'),
            _criterion(check_type='quality'),
        ],
    )

    outcome = await run_evaluation_pipeline(request, FakeModelProvider())

    layers = [i.model_layer for i in outcome.items]
    assert layers == ['fast', 'reasoning']
