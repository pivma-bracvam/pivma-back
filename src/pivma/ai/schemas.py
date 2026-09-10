"""Modelos de saída estruturada do LLM (Spec 013).

Estes schemas são passados a ``ChatOpenAI.with_structured_output`` para que
o modelo devolva diretamente objetos validados — o usuário regulatório nunca
escreve prompt nem define formato de saída.
"""

from typing import Literal

from pydantic import BaseModel, Field

Conclusion = Literal['compliant', 'non_compliant', 'partial', 'indeterminate']
EvidenceCompleteness = Literal['sufficient', 'partial', 'insufficient']
CheckType = Literal[
    'presence',
    'conformity',
    'quality',
    'comparison',
    'cross_field_consistency',
]
Polarity = Literal['positive', 'negative', 'consistency']
Severity = Literal['info', 'low', 'medium', 'high', 'critical']


class CriterionVerdict(BaseModel):
    """Resultado da avaliação de um único critério sobre um conteúdo."""

    conclusion: Conclusion = Field(
        description=(
            'Conclusão do critério. Use "indeterminate" sempre que a '
            'evidência for insuficiente para decidir — nunca invente.'
        )
    )
    evidence_excerpt: str | None = Field(
        default=None,
        description='Trecho literal do conteúdo que sustenta a conclusão.',
    )
    evidence_location: str | None = Field(
        default=None,
        description='Onde a evidência foi encontrada (ex.: "Seção 5").',
    )
    justification: str | None = Field(
        default=None,
        description='Explicação curta e objetiva da conclusão.',
    )
    recommendation: str | None = Field(
        default=None,
        description='O que o proponente deveria ajustar, quando aplicável.',
    )
    inference_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description='Confiança da inferência (informação secundária).',
    )
    evidence_completeness: EvidenceCompleteness | None = Field(
        default=None,
        description='Quão completa era a evidência disponível.',
    )


class SuggestedCriterion(BaseModel):
    """Critério proposto pelo assistente a partir de um objetivo."""

    statement: str = Field(
        description='Enunciado do critério em linguagem de negócio.'
    )
    check_type: CheckType = Field(
        description='Tipo de verificação mais adequado ao critério.'
    )
    polarity: Polarity = Field(default='positive')
    suggested_severity: Severity = Field(default='medium')


class SuggestedCriteria(BaseModel):
    """Envelope de saída estruturada do assistente de sugestão."""

    suggestions: list[SuggestedCriterion] = Field(default_factory=list)
