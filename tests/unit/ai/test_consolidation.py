"""Regra de consolidação da pré-avaliação (Spec 026, FR-001/FR-003)."""

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


def test_low_and_medium_non_conformities_now_block():
    result = consolidate([
        _c('non_compliant', 'low'),
        _c('non_compliant', 'medium'),
        _c('compliant', 'high'),
    ])

    assert result.result == 'negative'
    assert result.alerts == [False, False, False]


def test_only_indeterminate_is_negative():
    result = consolidate([
        _c('indeterminate', 'critical'),
        _c('indeterminate', 'high'),
    ])

    assert result.result == 'negative'
    assert result.alerts == [False, False]


def test_partial_blocks_and_is_not_alerted():
    result = consolidate([_c('partial', 'critical')])

    assert result.result == 'negative'
    assert result.alerts == [False]


def test_blocking_item_is_not_flagged_as_mere_alert():
    result = consolidate([
        _c('non_compliant', 'critical'),
        _c('non_compliant', 'low'),
    ])

    assert result.alerts == [False, False]


def test_single_low_severity_non_compliant_among_compliant_blocks():
    result = consolidate([
        _c('compliant', 'critical'),
        _c('compliant', 'high'),
        _c('non_compliant', 'low'),
    ])

    assert result.result == 'negative'
    assert result.alerts == [False, False, False]


def test_all_compliant_is_positive():
    result = consolidate([
        _c('compliant', 'critical'),
        _c('compliant', 'low'),
    ])

    assert result.result == 'positive'
    assert result.alerts == [False, False]


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
