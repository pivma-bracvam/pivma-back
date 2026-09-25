import pytest
from pydantic import ValidationError

from pivma.core.settings import Settings


def test_settings_accepts_required_authentication_configuration(monkeypatch):
    monkeypatch.setenv(
        'JWT_SECRET_KEY',
        'configured-jwt-secret-with-at-least-32-bytes',
    )
    monkeypatch.setenv(
        'AUTH_ALLOWED_ORIGINS',
        '["https://app.example.com"]',
    )

    settings = Settings()

    assert settings.AUTH_ALLOWED_ORIGINS == ['https://app.example.com']


def test_settings_ignores_unknown_environment_variables(monkeypatch):
    monkeypatch.setenv(
        'JWT_SECRET_KEY',
        'configured-jwt-secret-with-at-least-32-bytes',
    )
    monkeypatch.setenv(
        'AUTH_ALLOWED_ORIGINS',
        '["https://app.example.com"]',
    )
    monkeypatch.setenv('UNKNOWN_SETTING', 'ignored')

    settings = Settings()

    assert not hasattr(settings, 'UNKNOWN_SETTING')


def test_settings_rejects_short_jwt_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'too-short')

    with pytest.raises(ValidationError, match='at least 32 bytes'):
        Settings()


def test_settings_rejects_empty_authentication_origins(monkeypatch):
    monkeypatch.setenv('AUTH_ALLOWED_ORIGINS', '[]')

    with pytest.raises(ValidationError, match='at least 1 item'):
        Settings()


@pytest.mark.parametrize(
    'origin',
    [
        'app.example.com',
        'https://user@app.example.com',
        'https://app.example.com/path',
    ],
)
def test_settings_rejects_invalid_authentication_origin(
    monkeypatch,
    origin,
):
    monkeypatch.setenv('AUTH_ALLOWED_ORIGINS', f'["{origin}"]')

    with pytest.raises(ValidationError, match='valid origins'):
        Settings()
