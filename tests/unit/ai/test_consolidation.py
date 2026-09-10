"""Regra de consolidação da pré-avaliação (Spec 013, FR-030)."""

from pivma.ai.consolidation import EvaluatedCriterion, consolidate


def _c(conclusion, severity):
    return EvaluatedCriterion(conclusion=conclusion, severity=severity)


def test_negative_only_with_high_or_critical_non_conformity():
    result = consolidate([
        _c('compliant', 'critical'),
        _c('non_compliant', 'high'),
        _c('compliant', 'low'),
    ])

    assert result.result == 'negative'


def test_critical_non_conformity_is_negative():
    result = consolidate([_c('non_compliant', 'critical')])

    assert result.result == 'negative'


def test_low_and_medium_non_conformities_stay_positive_as_alerts():
    result = consolidate([
        _c('non_compliant', 'low'),
        _c('non_compliant', 'medium'),
        _c('compliant', 'high'),
    ])

    assert result.result == 'positive'
    assert result.alerts == [True, True, False]


def test_only_indeterminate_is_positive():
    result = consolidate([
        _c('indeterminate', 'critical'),
        _c('indeterminate', 'high'),
    ])

    assert result.result == 'positive'
    assert result.alerts == [True, True]


def test_partial_does_not_block_and_is_alerted():
    result = consolidate([_c('partial', 'critical')])

    assert result.result == 'positive'
    assert result.alerts == [True]


def test_blocking_item_is_not_flagged_as_mere_alert():
    result = consolidate([
        _c('non_compliant', 'critical'),
        _c('non_compliant', 'low'),
    ])

    assert result.alerts == [False, True]


def test_summary_counts_each_conclusion():
    result = consolidate([
        _c('compliant', 'low'),
        _c('compliant', 'low'),
        _c('non_compliant', 'high'),
        _c('partial', 'low'),
        _c('indeterminate', 'low'),
    ])

    assert result.summary == {
        'total': 5,
        'compliant': 2,
        'non_compliant': 1,
        'partial': 1,
        'indeterminate': 1,
    }


def test_empty_input_is_positive():
    result = consolidate([])

    assert result.result == 'positive'
    assert result.alerts == []
    assert result.summary['total'] == 0
