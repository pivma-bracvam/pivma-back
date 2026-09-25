"""Ações de ciclo de vida sobre o novo domínio de status (Spec 030)."""

from pivma.core.process_engine import lifecycle_available_actions


def test_available_actions_for_open():
    assert lifecycle_available_actions(
        status='OPEN', can_delete=True, can_review=True
    ) == ['DELETE']


def test_available_actions_for_closed_and_cancelled():
    for status in ('CLOSED', 'CANCELLED'):
        assert lifecycle_available_actions(
            status=status, can_delete=True, can_review=True
        ) == ['ARCHIVE']


def test_available_actions_for_archived():
    assert (
        lifecycle_available_actions(
            status='ARCHIVED', can_delete=True, can_review=True
        )
        == []
    )
