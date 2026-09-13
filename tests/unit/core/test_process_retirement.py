import pytest

from pivma.core.process_engine import (
    STATUS_ARCHIVED,
    STATUS_CANCELLED,
    lifecycle_available_actions,
)


def test_returned_submission_is_withdrawable_but_not_deletable():
    actions = lifecycle_available_actions(
        status='SUBMISSION',
        never_submitted=False,
        can_delete=True,
        can_review=False,
        revision_pending=True,
    )
    assert actions == ['WITHDRAW']


def test_never_submitted_draft_is_deletable_only_by_proponent():
    assert lifecycle_available_actions(
        status='SUBMISSION',
        never_submitted=True,
        can_delete=True,
        can_review=False,
    ) == ['DELETE_DRAFT']
    assert lifecycle_available_actions(
        status='SUBMISSION',
        never_submitted=True,
        can_delete=False,
        can_review=True,
    ) == []


def test_reviewer_can_cancel_submitted_process():
    actions = lifecycle_available_actions(
        status='AI_PRE_EVALUATION',
        never_submitted=False,
        can_delete=False,
        can_review=True,
    )
    assert actions == ['CANCEL']


@pytest.mark.parametrize('status', ['CLOSED', STATUS_CANCELLED])
def test_reviewer_can_archive_terminal_process(status):
    actions = lifecycle_available_actions(
        status=status,
        never_submitted=False,
        can_delete=False,
        can_review=True,
    )
    assert actions == ['ARCHIVE']


def test_archived_process_has_no_available_actions():
    assert lifecycle_available_actions(
        status=STATUS_ARCHIVED,
        never_submitted=False,
        can_delete=True,
        can_review=True,
        revision_pending=True,
    ) == []
