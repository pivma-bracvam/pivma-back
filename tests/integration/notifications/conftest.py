import pytest
from cryptography.fernet import Fernet

from pivma.core.settings import Settings
from pivma.notifications.channels import FakeEmailChannel
from pivma.notifications.renderers import RENDERERS

TEST_KIND = 'test_echo'


def _echo_renderer(payload):
    return (
        payload['subject'],
        f'texto: {payload["body"]}',
        f'<p>{payload["body"]}</p>',
    )


@pytest.fixture
def notification_settings():
    return Settings(
        NOTIFICATION_EMAIL_BACKEND='fake',
        NOTIFICATION_FROM_ADDRESS='nao-responda@pivma.test',
        NOTIFICATION_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        NOTIFICATION_MAX_ATTEMPTS=3,
        NOTIFICATION_RETRY_BASE_SECONDS=30,
        NOTIFICATION_RETRY_MAX_SECONDS=900,
        INVITE_URL_TEMPLATE='https://front.test/convites/{token}',
    )


@pytest.fixture
def fake_email_channel():
    return FakeEmailChannel()


@pytest.fixture
def echo_kind():
    """Tipo de aviso só de teste, para exercitar a base sem o convite."""
    RENDERERS[TEST_KIND] = _echo_renderer
    yield TEST_KIND
    RENDERERS.pop(TEST_KIND, None)
