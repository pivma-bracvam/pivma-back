"""Regra fixa e embutida de consolidação da pré-avaliação (Spec 026).

Converte os resultados por critério num resultado da pré-avaliação:

- **positive** somente se **todos** os critérios concluírem como
  ``compliant``;
- **negative** se existir ao menos um critério ``non_compliant``,
  ``partial`` ou ``indeterminate`` — independentemente da severidade.

Substitui a regra anterior da Spec 013 (que só bloqueava com não
conformidade de severidade ``high``/``critical``). Severidade permanece
registrada nos itens, mas deixa de ser insumo desta decisão.
"""

from collections.abc import Sequence
from dataclasses import dataclass

SEVERITY_ORDER = {
    'info': 0,
    'low': 1,
    'medium': 2,
    'high': 3,
    'critical': 4,
}

POSITIVE = 'positive'
NEGATIVE = 'negative'


@dataclass(frozen=True)
class EvaluatedCriterion:
    """Visão mínima de um resultado de critério para consolidar."""

    conclusion: str
    severity: str


@dataclass
class Consolidation:
    result: str
    alerts: list[bool]
    summary: dict[str, int]


def _is_blocking(item: EvaluatedCriterion) -> bool:
    return item.conclusion != 'compliant'


def consolidate(items: Sequence[EvaluatedCriterion]) -> Consolidation:
    summary = {
        'total': len(items),
        'compliant': 0,
        'non_compliant': 0,
        'partial': 0,
        'indeterminate': 0,
    }
    has_blocking = False

    for item in items:
        if item.conclusion in summary:
            summary[item.conclusion] += 1
        has_blocking = has_blocking or _is_blocking(item)

    # Toda não conformidade bloqueia agora, então nada é "alerta apenas";
    # o campo é mantido por compatibilidade de schema/API (ver research.md).
    alerts = [False] * len(items)
    result = NEGATIVE if has_blocking else POSITIVE
    return Consolidation(result=result, alerts=alerts, summary=summary)
