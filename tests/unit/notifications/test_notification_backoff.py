"""Spec 036 — intervalo entre tentativas (FR-004, research R5)."""

import pytest

from pivma.core.settings import Settings
from pivma.notifications.service import retry_delay


@pytest.fixture
def settings():
    return Settings(
        NOTIFICATION_RETRY_BASE_SECONDS=30,
        NOTIFICATION_RETRY_MAX_SECONDS=900,
    )


@pytest.mark.parametrize(
    ('attempt', 'seconds'),
    [(1, 30), (2, 60), (3, 120), (5, 480), (6, 900), (20, 900)],
)
def test_retry_delay_doubles_until_the_maximum(settings, attempt, seconds):
    assert retry_delay(attempt, settings).total_seconds() == seconds
