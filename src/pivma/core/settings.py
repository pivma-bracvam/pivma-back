from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    DATABASE_URL: str = Field(init=False)
    JWT_SECRET_KEY: str = Field(init=False)
    AUTH_ALLOWED_ORIGINS: list[str] = Field(init=False, min_length=1)

    # Avaliação por IA (Spec 013). Defaults seguros: sem chave e sem
    # provedor real, o sistema usa o provedor fake e conclui de forma
    # indeterminada — nunca uma conclusão positiva simulada.
    OPENAI_API_KEY: str | None = Field(default=None)
    AI_PROVIDER: str = Field(default='openai')
    AI_MODEL_EXTRACTION: str = Field(default='gpt-5.4-nano')
    AI_MODEL_FAST: str = Field(default='gpt-5.4-nano')
    AI_MODEL_REASONING: str = Field(default='gpt-5.4-mini')

    # Anexos de formulário (Spec 016). Armazenamento em disco local; sem
    # serviço externo. `ATTACHMENTS_DIR` é a raiz onde os binários vivem
    # (coberta por `var/` no `.gitignore`); o teto de tamanho e a allowlist
    # de extensões valem quando o campo não os declara em `validation_rules`.
    ATTACHMENTS_DIR: str = Field(default='var/attachments')
    ATTACHMENT_MAX_SIZE_MB: int = Field(default=25)
    ATTACHMENT_DEFAULT_EXTENSIONS: list[str] = Field(
        default_factory=lambda: ['pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg']
    )

    # Convite de designação por link (Spec 028). Prazo padrão de validade do
    # link, configurável por implantação (FR-008) — não é um parâmetro por
    # convite individual.
    INVITE_EXPIRATION_HOURS: int = Field(default=1)

    # Amostras cegas (Spec 031). Base da URL do frontend gravada no QR code
    # do frasco; sem valor, usa a primeira origem de `AUTH_ALLOWED_ORIGINS`.
    SAMPLE_QR_BASE_URL: str | None = Field(default=None)

    # Notificações (Spec 036). Sem `NOTIFICATION_EMAIL_BACKEND`, o canal de
    # e-mail fica indisponível e convites por e-mail são recusados (FR-019).
    # SMTP é aceito por praticamente todos os provedores: trocar de provedor
    # é trocar estas variáveis (FR-008).
    NOTIFICATION_EMAIL_BACKEND: Literal['smtp', 'fake'] | None = Field(
        default=None
    )
    SMTP_HOST: str | None = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str | None = Field(default=None)
    SMTP_PASSWORD: str | None = Field(default=None)
    SMTP_SECURITY: Literal['starttls', 'ssl', 'none'] = Field(
        default='starttls'
    )
    SMTP_TIMEOUT_SECONDS: int = Field(default=15)
    NOTIFICATION_FROM_ADDRESS: str | None = Field(default=None)
    NOTIFICATION_FROM_NAME: str = Field(default='pi*VMA')
    # Chave Fernet que cifra o conteúdo dos envios pendentes (FR-009).
    NOTIFICATION_ENCRYPTION_KEY: str | None = Field(default=None)
    NOTIFICATION_MAX_ATTEMPTS: int = Field(default=5, ge=1)
    NOTIFICATION_RETRY_BASE_SECONDS: int = Field(default=30, ge=1)
    NOTIFICATION_RETRY_MAX_SECONDS: int = Field(default=900, ge=1)
    NOTIFICATION_POLL_SECONDS: int = Field(default=5, ge=1)
    # Endereço completo da página de aceite do convite no frontend, com o
    # marcador `{token}` (Spec 036, FR-018).
    INVITE_URL_TEMPLATE: str | None = Field(default=None)
    # Página de redefinição de senha no frontend, com `{token}` (Spec 039).
    PASSWORD_RESET_URL_TEMPLATE: str | None = Field(default=None)

    @field_validator('INVITE_URL_TEMPLATE', 'PASSWORD_RESET_URL_TEMPLATE')
    @classmethod
    def validate_url_template(cls, value, info: ValidationInfo):
        if value is not None and value.count('{token}') != 1:
            raise ValueError(
                f'{info.field_name} must contain {{token}} exactly once'
            )
        return value

    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret_key(cls, value):
        if len(value.encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError('JWT_SECRET_KEY must contain at least 32 bytes')
        return value

    @field_validator('AUTH_ALLOWED_ORIGINS')
    @classmethod
    def validate_auth_allowed_origins(cls, value):
        for origin in value:
            parsed = urlsplit(origin)
            has_valid_base = (
                parsed.scheme in {'http', 'https'} and parsed.netloc
            )
            has_extra_parts = any((
                parsed.path,
                parsed.query,
                parsed.fragment,
                parsed.username,
                parsed.password,
            ))
            if not has_valid_base or has_extra_parts:
                raise ValueError(
                    'AUTH_ALLOWED_ORIGINS must contain valid origins'
                )
        return value


def get_settings() -> Settings:
    return Settings()
