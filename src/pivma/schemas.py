from datetime import datetime
from typing import Annotated, Any, Literal
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

USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"
email_adapter = TypeAdapter(EmailStr)
FullNameValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class Message(BaseModel):
    message: str


class UserSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=64,
            pattern=USERNAME_PATTERN,
        ),
    ]
    email: Annotated[str, Field(json_schema_extra={"format": "email"})]
    full_name: FullNameValue
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_preserving_case(cls, value):
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        email_adapter.validate_python(trimmed)
        return trimmed

    @field_validator("password")
    @classmethod
    def reject_password_whitespace(cls, value):
        if any(character.isspace() for character in value):
            raise ValueError("Invalid password")
        return value


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: Annotated[str, Field(json_schema_extra={"format": "email"})]
    full_name: str | None
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    full_name: FullNameValue


class ProfileSummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra="forbid")


class AdminUser(UserPublic):
    active: bool
    profiles: list[ProfileSummary]
    model_config = ConfigDict(extra='forbid', from_attributes=True)


class LoginCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=320),
    ]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserIdentity(UserPublic):
    pass


class AccessScope(BaseModel):
    process_id: UUID
    institution_id: UUID | None
    laboratory_id: UUID | None
    roles: list[str]
    model_config = ConfigDict(extra='forbid')


class CurrentUserAccess(BaseModel):
    profiles: list[ProfileSummary]
    global_permissions: list[str]
    scopes: list[AccessScope]
    model_config = ConfigDict(extra='forbid')


class CurrentUserResponse(UserIdentity):
    user: UserIdentity
    access: CurrentUserAccess


class FilterPage(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(100, ge=1)


class AdminUserPage(FilterPage):
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    items: list[AdminUser]
    model_config = ConfigDict(extra='forbid')


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
    model_config = ConfigDict(extra="forbid")

    name: ProfileName
    description: ProfileDescription
    permission_codes: list[PermissionCode] = Field(default_factory=list)

    @field_validator("permission_codes")
    @classmethod
    def unique_permission_codes(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("permission_codes must be unique")
        return value


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProfileName | None = None
    description: ProfileDescription | None = None
    permission_codes: list[PermissionCode] | None = None

    @field_validator("permission_codes")
    @classmethod
    def unique_permission_codes(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("permission_codes must be unique")
        return value

    def model_post_init(self, __context) -> None:
        if not self.model_fields_set:
            raise ValueError("At least one field is required")


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
    model_config = ConfigDict(extra="forbid")


class UserAccess(BaseModel):
    user_id: UUID
    profiles: list[ProfileSummary]
    effective_permissions: list[str]
    model_config = ConfigDict(extra="forbid")


class ProfileAssignmentPublic(BaseModel):
    id: UUID
    user_id: UUID
    profile_id: UUID
    created_by: UUID | None
    created_at: datetime
    active: bool
    deleted_by: UUID | None
    deleted_at: datetime | None
    model_config = ConfigDict(extra="forbid")


class RbacChangePublic(BaseModel):
    id: UUID
    action: str
    target_type: str
    target_id: UUID
    actor_user_id: UUID | None
    occurred_at: datetime
    model_config = ConfigDict(extra="forbid")


class RbacChangePage(FilterPage):
    items: list[RbacChangePublic]
    model_config = ConfigDict(extra="forbid")


# ==========================================
# INSTITUTIONAL AFFILIATION SCHEMAS
# ==========================================


InstitutionalName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class InstitutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: InstitutionalName


class InstitutionUpdate(InstitutionCreate):
    pass


class InstitutionSummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra="forbid")


class InstitutionPublic(InstitutionSummary):
    created_by: UUID | None
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime | None
    deleted_by: UUID | None
    deleted_at: datetime | None


class LaboratoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_id: UUID
    name: InstitutionalName


class LaboratoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: InstitutionalName


class LaboratorySummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra="forbid")


class LaboratoryPublic(LaboratorySummary):
    institution_id: UUID
    created_by: UUID | None
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime | None
    deleted_by: UUID | None
    deleted_at: datetime | None


class AffiliationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_id: UUID
    laboratory_id: UUID | None = None


class AffiliationPublic(BaseModel):
    id: UUID
    user_id: UUID
    institution: InstitutionSummary
    laboratory: LaboratorySummary | None
    active: bool
    created_by: UUID | None
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime | None
    deleted_by: UUID | None
    deleted_at: datetime | None
    model_config = ConfigDict(extra="forbid")


class SelfAffiliationPublic(BaseModel):
    id: UUID
    institution: InstitutionSummary
    laboratory: LaboratorySummary | None
    model_config = ConfigDict(extra="forbid")


class InstitutionalChangePublic(BaseModel):
    id: UUID
    action: str
    target_type: str
    target_id: UUID
    actor_user_id: UUID | None
    occurred_at: datetime
    model_config = ConfigDict(extra="forbid")


class InstitutionalChangePage(FilterPage):
    items: list[InstitutionalChangePublic]
    model_config = ConfigDict(extra="forbid")


# ==========================================
# PROCESS, FORM & TRIAGE SCHEMAS
# ==========================================


class ProcessTemplateSummary(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ProcessTemplateDetail(BaseModel):
    id: UUID
    key: str
    name: str
    version_number: int
    definition: dict
    model_config = ConfigDict(from_attributes=True)


class CreateProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=3, max_length=255)
    initial_notes: str | None = None


class ProcessInstanceDetail(BaseModel):
    id: UUID
    code: str
    title: str
    status: str
    template_key: str
    version_number: int
    started_at: datetime | None = None
    closed_at: datetime | None = None
    closure_reason: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ProcessInstanceListResponse(BaseModel):
    items: list[ProcessInstanceDetail]
    total: int
    page: int
    size: int


class FormFieldDefinition(BaseModel):
    field_key: str
    label: str
    help_text: str | None = None
    field_type: str
    is_required: bool
    order_index: int
    options: Any | None = None
    validation_rules: dict | None = None
    model_config = ConfigDict(from_attributes=True)


class FieldReviewSummary(BaseModel):
    status: str
    comments: str | None = None
    reviewed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FormInstanceResponse(BaseModel):
    form_instance_id: UUID
    template_key: str
    is_submitted: bool
    fields: list[FormFieldDefinition]
    values: dict[str, Any]
    reviews: dict[str, FieldReviewSummary]


class SaveFormValuesRequest(BaseModel):
    values: dict[str, Any]


class SubmitFormRequest(BaseModel):
    values: dict[str, Any]


class FieldReviewItem(BaseModel):
    field_key: str
    status: str
    comments: str | None = None


class SaveFieldReviewsRequest(BaseModel):
    reviews: list[FieldReviewItem]


class TriageDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str
    justification: str = Field(min_length=3)


class TriageDecisionResponse(BaseModel):
    process_id: UUID
    new_process_status: str
    decision_id: UUID
    outcome: str
    next_activity_run: int | None = None


class ActivityCompletionResponse(BaseModel):
    activity_key: str
    run_number: int
    status: str
    artifact_id: UUID | None = None


class TaskSummary(BaseModel):
    id: UUID
    process_id: UUID
    process_code: str
    title: str
    assigned_role: str | None = None
    status: str
    due_date: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class TaskDetail(BaseModel):
    id: UUID
    process_id: UUID
    activity_key: str
    activity_run_number: int
    title: str
    status: str
    is_blocked: bool
    blocked_reason: str | None = None


class TimelineEvent(BaseModel):
    id: UUID
    event_type: str
    user_id: UUID | None = None
    activity_run_id: UUID | None = None
    occurred_at: datetime
    context_data: dict | None = None
    model_config = ConfigDict(from_attributes=True)


class ProcessTimelineResponse(BaseModel):
    process_id: UUID
    code: str
    events: list[TimelineEvent]


# ==========================================
# PROCESS PARTICIPANT & CONFLICT SCHEMAS
# ==========================================


ParticipantRole = Literal[
    "group_manager",
    "study_manager",
    "statistician",
    "adhoc_evaluator",
    "peer_reviewer",
    "lead_laboratory",
    "participating_laboratory",
    "proponent",
]

LABORATORY_ROLE_KEYS = frozenset({
    "lead_laboratory",
    "participating_laboratory",
})

ParticipantJustification = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ParticipantAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)

    user_id: UUID
    role_key: ParticipantRole
    laboratory_id: UUID | None = None

    @field_validator("laboratory_id")
    @classmethod
    def validate_laboratory_requirement(cls, value, info):
        role = info.data.get("role_key")
        if role is None:
            return value
        if role in LABORATORY_ROLE_KEYS and value is None:
            raise ValueError("laboratory_id is required for laboratory roles")
        if role not in LABORATORY_ROLE_KEYS and value is not None:
            raise ValueError("laboratory_id is not allowed for this role")
        return value


class ParticipantAssignmentPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    process_id: UUID
    user_id: UUID
    role_key: str
    laboratory_id: UUID | None
    assigned_by: UUID
    assigned_at: datetime
    revoked_at: datetime | None
    active: bool
    effective: bool
    has_conflict: bool | None
    latest_declared_at: datetime | None


class ConflictDeclarationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_conflict: bool
    justification: ParticipantJustification


class ConflictDeclarationPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    assignment_id: UUID
    has_conflict: bool
    justification: str
    declared_at: datetime


class ParticipantHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment: ParticipantAssignmentPublic
    declarations: list[ConflictDeclarationPublic]


class ParticipantHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offset: int
    limit: int
    items: list[ParticipantHistoryItem]
