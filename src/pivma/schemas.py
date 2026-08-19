from datetime import datetime
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


class LoginCredentials(BaseModel):
    model_config = ConfigDict(extra='forbid')

    identifier: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=320),
    ]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserIdentity(UserPublic):
    pass


class FilterPage(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1)


PermissionCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
ProfileName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)
]
ProfileDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class PermissionPublic(BaseModel):
    code: str
    description: str
    model_config = ConfigDict(from_attributes=True)


class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: ProfileName
    description: ProfileDescription
    permission_codes: list[PermissionCode] = Field(default_factory=list)

    @field_validator('permission_codes')
    @classmethod
    def unique_permission_codes(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('permission_codes must be unique')
        return value


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: ProfileName | None = None
    description: ProfileDescription | None = None
    permission_codes: list[PermissionCode] | None = None

    @field_validator('permission_codes')
    @classmethod
    def unique_permission_codes(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError('permission_codes must be unique')
        return value

    def model_post_init(self, __context) -> None:
        if not self.model_fields_set:
            raise ValueError('At least one field is required')


class ProfilePublic(BaseModel):
    id: UUID
    name: str
    description: str
    active: bool
    official: bool
    permission_codes: list[str]
    created_by: UUID | None
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime | None
    deleted_by: UUID | None
    deleted_at: datetime | None
    model_config = ConfigDict(extra='forbid')


class ProfileSummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra='forbid')


class UserAccess(BaseModel):
    user_id: UUID
    profiles: list[ProfileSummary]
    effective_permissions: list[str]
    model_config = ConfigDict(extra='forbid')


class ProfileAssignmentPublic(BaseModel):
    id: UUID
    user_id: UUID
    profile_id: UUID
    created_by: UUID | None
    created_at: datetime
    active: bool
    deleted_by: UUID | None
    deleted_at: datetime | None
    model_config = ConfigDict(extra='forbid')


class RbacChangePublic(BaseModel):
    id: UUID
    action: str
    target_type: str
    target_id: UUID
    actor_user_id: UUID | None
    occurred_at: datetime
    model_config = ConfigDict(extra='forbid')


class RbacChangePage(FilterPage):
    items: list[RbacChangePublic]
    model_config = ConfigDict(extra='forbid')
