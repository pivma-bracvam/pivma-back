"""Regra fixa e embutida de consolidação da pré-avaliação (Spec 013).

Converte os resultados por critério num resultado da pré-avaliação:

- **negative** se existe pelo menos uma não conformidade de severidade
  ``high`` ou ``critical``;
- **positive** caso contrário.

Não conformidades de menor severidade, resultados parciais e indeterminados
não barram o proponente — viram *alertas* exibidos na triagem. Um critério
apenas ``indeterminate`` nunca torna o resultado negativo.
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
BLOCKING_SEVERITIES = frozenset({'high', 'critical'})

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
    return (
        item.conclusion == 'non_compliant'
        and item.severity in BLOCKING_SEVERITIES
    )


def consolidate(items: Sequence[EvaluatedCriterion]) -> Consolidation:
    summary = {
        'total': len(items),
        'compliant': 0,
        'non_compliant': 0,
        'partial': 0,
        'indeterminate': 0,
    }
    alerts: list[bool] = []
    has_blocking = False

    for item in items:
        if item.conclusion in summary:
            summary[item.conclusion] += 1
        blocking = _is_blocking(item)
        has_blocking = has_blocking or blocking
        alerts.append(item.conclusion != 'compliant' and not blocking)

    result = NEGATIVE if has_blocking else POSITIVE
    return Consolidation(result=result, alerts=alerts, summary=summary)
