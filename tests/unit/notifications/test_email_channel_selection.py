"""Spec 036 — canal de e-mail escolhido por configuração (FR-007, R8)."""

import pytest
from cryptography.fernet import Fernet

from pivma.core.settings import Settings
from pivma.notifications.channels import (
    FakeEmailChannel,
    SmtpEmailChannel,
    get_email_channel,
)

KEY = Fernet.generate_key().decode()
COMPLETE = {
    'NOTIFICATION_FROM_ADDRESS': 'nao-responda@pivma.test',
    'NOTIFICATION_ENCRYPTION_KEY': KEY,
    'SMTP_HOST': 'smtp.exemplo.org',
}


def test_smtp_backend_returns_smtp_channel():
    settings = Settings(NOTIFICATION_EMAIL_BACKEND='smtp', **COMPLETE)

    assert isinstance(get_email_channel(settings), SmtpEmailChannel)


def test_fake_backend_returns_fake_channel():
    settings = Settings(NOTIFICATION_EMAIL_BACKEND='fake', **COMPLETE)

    assert isinstance(get_email_channel(settings), FakeEmailChannel)


@pytest.mark.parametrize(
    'overrides',
    [
        {'NOTIFICATION_EMAIL_BACKEND': None},
        {'NOTIFICATION_FROM_ADDRESS': None},
        {'NOTIFICATION_ENCRYPTION_KEY': None},
        {'SMTP_HOST': None},
    ],
    ids=['no-backend', 'no-sender', 'no-key', 'smtp-without-host'],
)
def test_incomplete_configuration_returns_no_channel(overrides):
    values = {'NOTIFICATION_EMAIL_BACKEND': 'smtp', **COMPLETE, **overrides}

    assert get_email_channel(Settings(**values)) is None
