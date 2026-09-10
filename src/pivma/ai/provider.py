"""Provedor de modelos de linguagem (Spec 013).

Abstrai o acesso a LLMs atrás de uma interface única e trocável, injetada
pela API no padrão de ``src/pivma/dependencies.py``. Duas implementações:

- ``OpenAIModelProvider``: usa ``ChatOpenAI`` via LangChain, com três camadas
  nomeadas (``extraction`` / ``fast`` / ``reasoning``) e saída estruturada.
- ``FakeModelProvider``: determinístico, sem rede — usado em dev e testes
  (``AI_PROVIDER=fake``) para não gastar tokens.

A escolha da camada por tipo de critério vive em ``layer_for_check_type``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from pivma.ai.schemas import (
    CriterionVerdict,
    SuggestedCriteria,
    SuggestedCriterion,
)
from pivma.core.settings import Settings

ModelLayer = Literal['extraction', 'fast', 'reasoning', 'none']
TargetKind = Literal['text', 'document', 'image']

_FAST_CHECK_TYPES = frozenset({'presence', 'conformity'})
_MIN_KEYWORD_LEN = 5
_MIN_CONTENT_LEN = 40


class AIProviderError(RuntimeError):
    """Falha ao acionar o provedor de modelos (ex.: chave ausente)."""


def layer_for_check_type(check_type: str) -> ModelLayer:
    """Camada de modelo adequada ao tipo de verificação do critério."""
    return 'fast' if check_type in _FAST_CHECK_TYPES else 'reasoning'


@dataclass
class EvaluationInput:
    """Tudo o que o provedor precisa para avaliar um critério."""

    objective: str
    statement: str
    check_type: str
    polarity: str
    content: str
    target_kind: TargetKind = 'text'
    required_evidence: str | None = None
    references: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CriterionOutcome:
    """Resultado de uma avaliação de critério, com metadados de custo."""

    verdict: CriterionVerdict
    model_layer: ModelLayer
    cost: float = 0.0


class ModelProvider(ABC):
    """Contrato do provedor de modelos consumido pelo pipeline."""

    name: str = 'abstract'

    @abstractmethod
    def models_used(self) -> dict[str, str | None]:
        """Nome do modelo por camada, para auditoria da execução."""

    @abstractmethod
    async def evaluate_criterion(
        self, data: EvaluationInput
    ) -> CriterionOutcome:
        """Avalia um único critério sobre um conteúdo."""

    @abstractmethod
    async def suggest_criteria(
        self, objective: str, target_type: str
    ) -> list[SuggestedCriterion]:
        """Sugere critérios estruturados a partir de um objetivo."""


# ---------------------------------------------------------------------------
# Implementação real — OpenAI via LangChain
# ---------------------------------------------------------------------------


_INDETERMINATE_NON_TEXT = CriterionVerdict(
    conclusion='indeterminate',
    justification=(
        'Leitura de documento, OCR e análise de imagem ainda não estão '
        'disponíveis nesta versão.'
    ),
    evidence_completeness='insufficient',
)


class OpenAIModelProvider(ModelProvider):
    name = 'openai'

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.OPENAI_API_KEY
        self._model_names: dict[str, str] = {
            'extraction': settings.AI_MODEL_EXTRACTION,
            'fast': settings.AI_MODEL_FAST,
            'reasoning': settings.AI_MODEL_REASONING,
        }
        self._clients: dict[str, Any] = {}

    def models_used(self) -> dict[str, str | None]:
        return dict(self._model_names)

    def _client(self, layer: str) -> Any:
        if not self._api_key:
            raise AIProviderError(
                'OPENAI_API_KEY não configurada; defina AI_PROVIDER=fake '
                'para operar sem serviço externo.'
            )
        if layer not in self._clients:
            from langchain_openai import ChatOpenAI  # noqa: PLC0415

            self._clients[layer] = ChatOpenAI(
                model=self._model_names[layer],
                api_key=self._api_key,
                temperature=0,
            )
        return self._clients[layer]

    async def evaluate_criterion(
        self, data: EvaluationInput
    ) -> CriterionOutcome:
        if data.target_kind != 'text':
            return CriterionOutcome(
                verdict=_INDETERMINATE_NON_TEXT, model_layer='none'
            )

        layer = layer_for_check_type(data.check_type)
        structured = self._client(layer).with_structured_output(
            CriterionVerdict, include_raw=True
        )
        result = await structured.ainvoke(_build_criterion_prompt(data))
        verdict = result['parsed'] or _INDETERMINATE_NON_TEXT
        usage = getattr(result.get('raw'), 'usage_metadata', None)
        return CriterionOutcome(
            verdict=verdict, model_layer=layer, cost=_estimate_cost(usage)
        )

    async def suggest_criteria(
        self, objective: str, target_type: str
    ) -> list[SuggestedCriterion]:
        structured = self._client('reasoning').with_structured_output(
            SuggestedCriteria
        )
        out: SuggestedCriteria = await structured.ainvoke(
            _build_suggest_prompt(objective, target_type)
        )
        return out.suggestions


def _build_criterion_prompt(data: EvaluationInput) -> str:
    refs = ', '.join(
        f'{r.get("identifier")} ({r.get("version_label")})'
        for r in data.references
    )
    parts = [
        'Você avalia um critério regulatório sobre um conteúdo submetido.',
        f'Objetivo geral da avaliação: {data.objective}',
        f'Critério ({data.check_type}, polaridade {data.polarity}): '
        f'{data.statement}',
    ]
    if data.required_evidence:
        parts.append(f'Evidência exigida: {data.required_evidence}')
    if refs:
        parts.append(f'Referências normativas aplicáveis: {refs}')
    parts.append(
        'Se a evidência for insuficiente, conclua "indeterminate". '
        'Não trate o nome do arquivo como evidência.'
    )
    parts.append(f'--- CONTEÚDO ---\n{data.content}')
    return '\n\n'.join(parts)


def _build_suggest_prompt(objective: str, target_type: str) -> str:
    return (
        'Um gestor regulatório quer configurar uma avaliação automatizada.\n'
        f'Alvo: {target_type}\n'
        f'Objetivo informado: {objective}\n\n'
        'Proponha entre 4 e 10 critérios verificáveis, em linguagem de '
        'negócio, cada um com o tipo de verificação mais adequado '
        '(presence, conformity, quality, comparison, '
        'cross_field_consistency) e uma severidade sugerida.'
    )


def _estimate_cost(usage: dict[str, Any] | None) -> float:
    if not usage:
        return 0.0
    inp = usage.get('input_tokens', 0) or 0
    out = usage.get('output_tokens', 0) or 0
    # Estimativa grosseira (ajuste fino posterior): US$/milhão de tokens.
    return round((inp * 0.05 + out * 0.40) / 1_000_000, 6)


# ---------------------------------------------------------------------------
# Implementação fake — determinística, sem rede
# ---------------------------------------------------------------------------


_FAKE_POP_CRITERIA = [
    ('Deve possuir identificação do documento', 'presence', 'low'),
    ('Deve possuir controle de versão', 'presence', 'low'),
    ('Deve apresentar objetivo e escopo', 'conformity', 'medium'),
    ('Deve identificar responsáveis', 'presence', 'low'),
    (
        'Deve listar materiais e equipamentos necessários',
        'conformity',
        'medium',
    ),
    (
        'O procedimento deve permitir reprodução por outro laboratório',
        'quality',
        'critical',
    ),
    ('Deve apresentar critérios de aceitação', 'conformity', 'critical'),
    ('Deve descrever controles de qualidade aplicados', 'quality', 'high'),
    (
        'Deve apresentar referências bibliográficas ou normativas',
        'presence',
        'low',
    ),
    ('Deve possuir histórico de revisão', 'presence', 'info'),
]

_FAKE_GENERIC_CRITERIA = [
    (
        'O conteúdo deve descrever o objetivo de forma clara',
        'conformity',
        'medium',
    ),
    ('O conteúdo deve apresentar metodologia suficiente', 'quality', 'high'),
    (
        'O conteúdo deve apresentar resultados quando aplicável',
        'presence',
        'medium',
    ),
    ('O conteúdo deve declarar limitações', 'presence', 'low'),
]


class FakeModelProvider(ModelProvider):
    name = 'fake'

    def models_used(self) -> dict[str, str | None]:  # noqa: PLR6301
        return {'extraction': None, 'fast': None, 'reasoning': None}

    async def evaluate_criterion(  # noqa: PLR6301
        self, data: EvaluationInput
    ) -> CriterionOutcome:
        verdict = _fake_verdict(data)
        layer: ModelLayer = (
            'none'
            if data.target_kind != 'text'
            else layer_for_check_type(data.check_type)
        )
        return CriterionOutcome(verdict=verdict, model_layer=layer)

    async def suggest_criteria(  # noqa: PLR6301
        self, objective: str, target_type: str
    ) -> list[SuggestedCriterion]:
        pool = (
            _FAKE_POP_CRITERIA
            if target_type in {'field', 'document', 'field_set'}
            else _FAKE_GENERIC_CRITERIA
        )
        return [
            SuggestedCriterion(
                statement=statement,
                check_type=check_type,
                suggested_severity=severity,
            )
            for statement, check_type, severity in pool
        ]


def _fake_verdict(data: EvaluationInput) -> CriterionVerdict:
    if data.target_kind != 'text':
        return _INDETERMINATE_NON_TEXT
    content = (data.content or '').strip().lower()
    if not content:
        return CriterionVerdict(
            conclusion='indeterminate',
            justification='Nenhum conteúdo submetido para o critério.',
            evidence_completeness='insufficient',
        )
    keywords = [
        w for w in _tokens(data.statement) if len(w) >= _MIN_KEYWORD_LEN
    ]
    if keywords:
        hit = any(k in content for k in keywords)
    else:
        hit = len(content) >= _MIN_CONTENT_LEN
    if data.polarity == 'negative':
        conclusion = 'non_compliant' if hit else 'compliant'
    elif data.polarity == 'consistency':
        conclusion = 'partial'
    else:
        conclusion = 'compliant' if hit else 'non_compliant'
    return CriterionVerdict(
        conclusion=conclusion,
        evidence_excerpt=content[:160] if hit else None,
        justification='Avaliação simulada (provedor fake).',
        inference_confidence=0.5,
        evidence_completeness='partial',
    )


def _tokens(text: str) -> list[str]:
    return [
        ''.join(ch for ch in word if ch.isalnum()).lower()
        for word in text.split()
    ]


# ---------------------------------------------------------------------------
# Factory / dependência
# ---------------------------------------------------------------------------


def get_model_provider(settings: Settings) -> ModelProvider:
    if settings.AI_PROVIDER == 'fake':
        return FakeModelProvider()
    return OpenAIModelProvider(settings)
