import pytest

from pivma.core.process_engine import (
    STATUS_ARCHIVED,
    STATUS_CANCELLED,
    lifecycle_available_actions,
)


@pytest.mark.parametrize(
    'status', ['SUBMISSION', 'TRIAGE', 'AI_PRE_EVALUATION']
)
def test_non_terminal_process_is_deletable_by_authorized_actor(status):
    assert lifecycle_available_actions(
        status=status, can_delete=True, can_review=False
    ) == ['DELETE']
    assert lifecycle_available_actions(
        status=status, can_delete=False, can_review=True
    ) == []


@pytest.mark.parametrize('status', ['CLOSED', STATUS_CANCELLED])
def test_reviewer_can_archive_terminal_process(status):
    actions = lifecycle_available_actions(
        status=status, can_delete=False, can_review=True
    )
    assert actions == ['ARCHIVE']


@pytest.mark.parametrize('status', ['CLOSED', STATUS_CANCELLED])
def test_terminal_process_is_never_deletable(status):
    actions = lifecycle_available_actions(
        status=status, can_delete=True, can_review=False
    )
    assert actions == []


def test_archived_process_has_no_available_actions():
    assert lifecycle_available_actions(
        status=STATUS_ARCHIVED, can_delete=True, can_review=True
    ) == []
