# ruff: noqa: PLR2004
"""Teste opt-in contra a OpenAI real (Spec 013, Polish T069).

Consome tokens reais. Roda apenas quando ``RUN_OPENAI_TESTS`` e
``OPENAI_API_KEY`` estão presentes no ambiente.
"""

import os

import pytest

from pivma.ai.provider import EvaluationInput, OpenAIModelProvider
from pivma.core.settings import Settings

pytestmark = pytest.mark.skipif(
    not os.getenv('RUN_OPENAI_TESTS') or not os.getenv('OPENAI_API_KEY'),
    reason='defina RUN_OPENAI_TESTS=1 e OPENAI_API_KEY para rodar',
)


@pytest.mark.asyncio
async def test_openai_provider_evaluates_a_text_criterion():
    provider = OpenAIModelProvider(Settings())
    data = EvaluationInput(
        objective='Verificar completude do resumo.',
        statement='O resumo deve mencionar objetivo e metodologia.',
        check_type='conformity',
        polarity='positive',
        content=(
            'Este estudo tem por objetivo validar um método alternativo. '
            'A metodologia baseia-se em epiderme humana reconstruída.'
        ),
    )

    outcome = await provider.evaluate_criterion(data)

    assert outcome.verdict.conclusion in {
        'compliant',
        'non_compliant',
        'partial',
        'indeterminate',
    }
    assert outcome.model_layer == 'fast'
