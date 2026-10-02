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


# --- Spec 036: INVITE_URL_TEMPLATE (FR-018) ---


@pytest.mark.parametrize(
    'template',
    [
        'https://app.example.com/convites',
        'https://app.example.com/{token}/convites/{token}',
    ],
)
def test_settings_rejects_invite_url_template_without_single_token(
    monkeypatch, template
):
    monkeypatch.setenv('INVITE_URL_TEMPLATE', template)

    with pytest.raises(ValidationError, match='INVITE_URL_TEMPLATE'):
        Settings()


def test_settings_accepts_invite_url_template_with_one_token(monkeypatch):
    monkeypatch.setenv(
        'INVITE_URL_TEMPLATE', 'https://app.example.com/convites/{token}'
    )

    settings = Settings()

    assert settings.INVITE_URL_TEMPLATE == (
        'https://app.example.com/convites/{token}'
    )


def test_settings_accepts_missing_invite_url_template(monkeypatch):
    monkeypatch.delenv('INVITE_URL_TEMPLATE', raising=False)

    settings = Settings()

    assert settings.INVITE_URL_TEMPLATE is None


# --- Spec 039: PASSWORD_RESET_URL_TEMPLATE ---


@pytest.mark.parametrize(
    'template',
    [
        'https://app.example.com/redefinir-senha',
        'https://app.example.com/{token}/redefinir-senha/{token}',
    ],
)
def test_settings_rejects_password_reset_url_template_without_single_token(
    monkeypatch, template
):
    monkeypatch.setenv('PASSWORD_RESET_URL_TEMPLATE', template)

    with pytest.raises(ValidationError, match='PASSWORD_RESET_URL_TEMPLATE'):
        Settings()


def test_settings_accepts_password_reset_url_template_with_one_token(
    monkeypatch,
):
    monkeypatch.setenv(
        'PASSWORD_RESET_URL_TEMPLATE',
        'https://app.example.com/redefinir-senha/{token}',
    )

    settings = Settings()

    assert settings.PASSWORD_RESET_URL_TEMPLATE == (
        'https://app.example.com/redefinir-senha/{token}'
    )


def test_settings_accepts_missing_password_reset_url_template(monkeypatch):
    monkeypatch.delenv('PASSWORD_RESET_URL_TEMPLATE', raising=False)

    settings = Settings(_env_file=None)

    assert settings.PASSWORD_RESET_URL_TEMPLATE is None
