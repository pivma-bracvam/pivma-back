import pytest

from pivma.core.process_engine import (
    STATUS_ARCHIVED,
    STATUS_CANCELLED,
    lifecycle_available_actions,
    normalize_lifecycle_justification,
)


def test_lifecycle_justification_is_trimmed():
    assert normalize_lifecycle_justification('  Motivo válido  ') == (
        'Motivo válido'
    )


@pytest.mark.parametrize('value', ['', '   ', '\n\t'])
def test_blank_lifecycle_justification_is_invalid(value):
    with pytest.raises(ValueError, match='justificativa'):
        normalize_lifecycle_justification(value)


def test_lifecycle_justification_over_limit_is_invalid():
    with pytest.raises(ValueError, match='2.000'):
        normalize_lifecycle_justification('x' * 2001)


def test_returned_submission_is_not_a_deletable_draft():
    actions = lifecycle_available_actions(
        status='SUBMISSION',
        never_submitted=False,
        can_delete=True,
        can_manage=False,
    )
    assert actions == []


def test_platform_can_cancel_operational_process():
    actions = lifecycle_available_actions(
        status='AI_PRE_EVALUATION',
        never_submitted=False,
        can_delete=False,
        can_manage=True,
    )
    assert actions == ['CANCEL']


@pytest.mark.parametrize('status', ['CLOSED', STATUS_CANCELLED])
def test_platform_can_archive_terminal_process(status):
    actions = lifecycle_available_actions(
        status=status,
        never_submitted=False,
        can_delete=False,
        can_manage=True,
    )
    assert actions == ['ARCHIVE']


def test_archived_process_has_no_available_actions():
    assert (
        lifecycle_available_actions(
            status=STATUS_ARCHIVED,
            never_submitted=False,
            can_delete=True,
            can_manage=True,
        )
        == []
    )
