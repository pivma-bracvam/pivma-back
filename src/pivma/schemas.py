from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
)

USERNAME_PATTERN = r'^[A-Za-z0-9._-]+$'
email_adapter = TypeAdapter(EmailStr)


class Message(BaseModel):
    message: str


class UserSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=64,
            pattern=USERNAME_PATTERN,
        ),
    ]
    email: Annotated[str, Field(json_schema_extra={'format': 'email'})]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]

    @field_validator('email', mode='before')
    @classmethod
    def validate_email_preserving_case(cls, value):
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        email_adapter.validate_python(trimmed)
        return trimmed

    @field_validator('password')
    @classmethod
    def reject_password_whitespace(cls, value):
        if any(character.isspace() for character in value):
            raise ValueError('Invalid password')
        return value


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: Annotated[str, Field(json_schema_extra={'format': 'email'})]
    model_config = ConfigDict(from_attributes=True)


class FilterPage(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1)
