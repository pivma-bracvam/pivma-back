from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8'
    )

    DATABASE_URL: str = Field(init=False)
    JWT_SECRET_KEY: str = Field(init=False)
    AUTH_ALLOWED_ORIGINS: list[str] = Field(init=False, min_length=1)

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
            has_extra_parts = any(
                (
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                    parsed.username,
                    parsed.password,
                )
            )
            if not has_valid_base or has_extra_parts:
                raise ValueError(
                    'AUTH_ALLOWED_ORIGINS must contain valid origins'
                )
        return value


def get_settings() -> Settings:
    return Settings()
