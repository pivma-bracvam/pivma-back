"""Provedor de modelos e seleção de camada (Spec 013, FR-024a-e)."""

import pytest

from pivma.ai.provider import (
    AIProviderError,
    EvaluationInput,
    FakeModelProvider,
    OpenAIModelProvider,
    get_model_provider,
    layer_for_check_type,
)
from pivma.core.settings import Settings

MIN_SUGGESTIONS = 4


def _settings(**overrides):
    base = dict(
        DATABASE_URL='postgresql+psycopg://u:p@localhost/db',
        JWT_SECRET_KEY='x' * 32,
        AUTH_ALLOWED_ORIGINS=['https://testserver'],
    )
    base.update(overrides)
    return Settings(**base)


@pytest.mark.parametrize(
    ('check_type', 'expected'),
    [
        ('presence', 'fast'),
        ('conformity', 'fast'),
        ('quality', 'reasoning'),
        ('comparison', 'reasoning'),
        ('cross_field_consistency', 'reasoning'),
    ],
)
def test_layer_for_check_type(check_type, expected):
    assert layer_for_check_type(check_type) == expected


def test_factory_returns_fake_when_provider_is_fake():
    provider = get_model_provider(_settings(AI_PROVIDER='fake'))

    assert isinstance(provider, FakeModelProvider)


def test_factory_returns_openai_when_provider_is_openai():
    provider = get_model_provider(
        _settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-test')
    )

    assert isinstance(provider, OpenAIModelProvider)


@pytest.mark.asyncio
async def test_openai_provider_raises_clear_error_without_key():
    provider = OpenAIModelProvider(_settings(OPENAI_API_KEY=None))
    data = EvaluationInput(
        objective='obj',
        statement='deve conter metodologia',
        check_type='conformity',
        polarity='positive',
        content='texto qualquer',
    )

    with pytest.raises(AIProviderError):
        await provider.evaluate_criterion(data)


@pytest.mark.asyncio
async def test_fake_provider_is_indeterminate_for_non_text_targets():
    provider = FakeModelProvider()
    data = EvaluationInput(
        objective='obj',
        statement='documento deve ter imagem',
        check_type='presence',
        polarity='positive',
        content='qualquer',
        target_kind='document',
    )

    outcome = await provider.evaluate_criterion(data)

    assert outcome.verdict.conclusion == 'indeterminate'
    assert outcome.model_layer == 'none'


@pytest.mark.asyncio
async def test_fake_provider_is_indeterminate_for_empty_content():
    provider = FakeModelProvider()
    data = EvaluationInput(
        objective='obj',
        statement='deve conter objetivo',
        check_type='conformity',
        polarity='positive',
        content='   ',
    )

    outcome = await provider.evaluate_criterion(data)

    assert outcome.verdict.conclusion == 'indeterminate'


@pytest.mark.asyncio
async def test_fake_provider_positive_polarity_matches_keyword():
    provider = FakeModelProvider()
    hit = EvaluationInput(
        objective='obj',
        statement='deve apresentar metodologia detalhada',
        check_type='quality',
        polarity='positive',
        content='O documento descreve a metodologia detalhada do ensaio.',
    )
    miss = EvaluationInput(
        objective='obj',
        statement='deve apresentar metodologia detalhada',
        check_type='quality',
        polarity='positive',
        content='Conteúdo irrelevante sobre outro assunto qualquer aqui.',
    )

    assert (await provider.evaluate_criterion(hit)).verdict.conclusion == (
        'compliant'
    )
    assert (await provider.evaluate_criterion(miss)).verdict.conclusion == (
        'non_compliant'
    )
    assert (await provider.evaluate_criterion(hit)).model_layer == 'reasoning'


@pytest.mark.asyncio
async def test_fake_provider_suggests_criteria_by_target_type():
    provider = FakeModelProvider()

    field_suggestions = await provider.suggest_criteria('obj', 'field')
    form_suggestions = await provider.suggest_criteria('obj', 'form')

    assert len(field_suggestions) >= MIN_SUGGESTIONS
    assert any(s.suggested_severity == 'critical' for s in field_suggestions)
    assert len(form_suggestions) >= MIN_SUGGESTIONS
