from urllib.parse import urlsplit

from pydantic import Field, field_validator
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

    # Diretório das demonstrações estáticas (servidas em /demos)
    DEMOS_DIR: str | None = Field(default=None)

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
