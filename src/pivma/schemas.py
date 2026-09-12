from datetime import date, datetime
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
    model_validator,
)

USERNAME_PATTERN = r'^[A-Za-z0-9._-]+$'
email_adapter = TypeAdapter(EmailStr)
FullNameValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


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
    full_name: FullNameValue
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
    full_name: str | None
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    full_name: FullNameValue


class ProfileSummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra='forbid')


class AdminUser(UserPublic):
    active: bool
    profiles: list[ProfileSummary]
    model_config = ConfigDict(extra='forbid', from_attributes=True)


class LoginCredentials(BaseModel):
    model_config = ConfigDict(extra='forbid')

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


class CurrentUserResponse(BaseModel):
    user: UserIdentity
    access: CurrentUserAccess
    model_config = ConfigDict(extra='forbid')


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


# ==========================================
# INSTITUTIONAL AFFILIATION SCHEMAS
# ==========================================


InstitutionalName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class InstitutionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: InstitutionalName


class InstitutionUpdate(InstitutionCreate):
    pass


class InstitutionSummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra='forbid')


class InstitutionPublic(InstitutionSummary):
    created_by: UUID | None
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime | None
    deleted_by: UUID | None
    deleted_at: datetime | None


class LaboratoryCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    institution_id: UUID
    name: InstitutionalName


class LaboratoryUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: InstitutionalName


class LaboratorySummary(BaseModel):
    id: UUID
    name: str
    active: bool
    model_config = ConfigDict(extra='forbid')


class LaboratoryPublic(LaboratorySummary):
    institution_id: UUID
    created_by: UUID | None
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime | None
    deleted_by: UUID | None
    deleted_at: datetime | None


class AffiliationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

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
    model_config = ConfigDict(extra='forbid')


class SelfAffiliationPublic(BaseModel):
    id: UUID
    institution: InstitutionSummary
    laboratory: LaboratorySummary | None
    model_config = ConfigDict(extra='forbid')


class InstitutionalChangePublic(BaseModel):
    id: UUID
    action: str
    target_type: str
    target_id: UUID
    actor_user_id: UUID | None
    occurred_at: datetime
    model_config = ConfigDict(extra='forbid')


class InstitutionalChangePage(FilterPage):
    items: list[InstitutionalChangePublic]
    model_config = ConfigDict(extra='forbid')


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
    model_config = ConfigDict(extra='forbid')

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


# ==========================================
# KANBAN DE PENDÊNCIAS (Spec 018)
# ==========================================

KanbanColumn = Literal[
    'NAO_INICIADO', 'EM_ANDAMENTO', 'EM_ATRASO', 'CONCLUIDO'
]


class KanbanCardProcess(BaseModel):
    id: UUID
    code: str
    title: str
    template_key: str


class KanbanCardItem(BaseModel):
    activity_id: UUID
    activity_key: str
    activity_name: str
    column: KanbanColumn
    cargo: ActivityCargo
    process: KanbanCardProcess
    blocked_reason: str | None = None
    blocking_activity_key: str | None = None
    blocking_activity_status: str | None = None
    blocking_activity_cargo: ActivityCargo | None = None
    run_started_at: datetime | None = None
    sla_hours: int | None = None
    completed_at: datetime | None = None
    cargo_unassigned: bool = False
    actionable_now: bool = False


class KanbanPage(BaseModel):
    items: list[KanbanCardItem]
    total: int
    page: int
    size: int
    counts_by_column: dict[KanbanColumn, int]


class AttachmentMetadata(BaseModel):
    artifact_id: UUID
    filename: str
    size: int
    mime_type: str | None = None
    extension: str
    checksum_sha256: str
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AttachmentUploadResponse(BaseModel):
    field_key: str
    attachment: AttachmentMetadata
    replaced_previous: bool = False


class AttachmentRemovedResponse(BaseModel):
    field_key: str
    removed: bool = True


class FormFieldDefinition(BaseModel):
    field_key: str
    label: str
    help_text: str | None = None
    field_type: str
    is_required: bool
    order_index: int
    section: str | None = None
    options: Any | None = None
    validation_rules: dict | None = None
    ai_evaluation_enabled: bool = False
    ai_context_instructions: str | None = None
    ai_validation_rules: dict | None = None
    attachment: AttachmentMetadata | None = None
    model_config = ConfigDict(from_attributes=True)


class FormFieldUpdateDefinition(BaseModel):
    field_key: str
    label: str
    help_text: str | None = None
    field_type: str = 'text'
    is_required: bool = False
    order_index: int = 0
    section: str | None = 'Geral'
    options: Any | None = None
    validation_rules: dict[str, Any] | None = None
    ai_evaluation_enabled: bool = False
    ai_context_instructions: str | None = None
    ai_validation_rules: dict[str, Any] | None = None
    model_config = ConfigDict(extra='ignore')


class UpdateFormTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    fields: list[FormFieldUpdateDefinition]


class FormTemplateDetailResponse(BaseModel):
    id: UUID
    key: str
    name: str
    version: int
    description: str | None = None
    fields: list[FormFieldUpdateDefinition]
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


class ReplaceSubmissionRequest(BaseModel):
    """Payload completo para a submissão ainda em elaboração."""

    model_config = ConfigDict(extra='forbid')

    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=255),
    ]
    values: dict[str, Any]


class PatchSubmissionRequest(BaseModel):
    """Payload parcial; valores ausentes permanecem no rascunho."""

    model_config = ConfigDict(extra='forbid')

    title: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=255),
    ] = None
    values: dict[str, Any] | None = None

    @model_validator(mode='after')
    def require_editable_attribute(self):
        if 'title' in self.model_fields_set and self.title is None:
            raise ValueError('title não pode ser nulo.')
        if 'values' in self.model_fields_set and self.values is None:
            raise ValueError('values não pode ser nulo.')
        if self.title is None and (self.values is None or not self.values):
            raise ValueError('Informe title e/ou values para atualizar.')
        return self


class ProcessSubmissionResponse(BaseModel):
    id: UUID
    title: str
    status: str
    template_key: str
    version_number: int
    run_number: int
    form_instance_id: UUID
    is_submitted: bool
    values: dict[str, Any]


class SubmissionVersionSummary(BaseModel):
    run_number: int
    submitted_at: datetime
    returned_at: datetime
    title: str
    return_justification: str


class SubmissionVersionResponse(SubmissionVersionSummary):
    values: dict[str, Any]
    attachments: list[dict[str, Any]]


class FieldReviewItem(BaseModel):
    field_key: str
    status: str
    comments: str | None = None


class SaveFieldReviewsRequest(BaseModel):
    reviews: list[FieldReviewItem]


class TriageDecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
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
    pre_evaluation: dict[str, Any] | None = None


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
    'group_manager',
    'study_manager',
    'statistician',
    'adhoc_evaluator',
    'peer_reviewer',
    'lead_laboratory',
    'participating_laboratory',
    'proponent',
]

# Cargo declarado por uma atividade de processo (`Task.assigned_role` / YAML do
# template). Mesmo vocabulário contextual de `ParticipantRole` (resolvido via
# `Assignment` ativa no processo), mais dois valores reservados de cargo global
# (resolvidos via `AccessProfile`, nunca por processo) — Spec 018.
ActivityCargo = Literal[
    'group_manager',
    'study_manager',
    'statistician',
    'adhoc_evaluator',
    'peer_reviewer',
    'lead_laboratory',
    'participating_laboratory',
    'proponent',
    'admin',
    'bracvam',
]
GLOBAL_ACTIVITY_CARGOS = frozenset({'admin', 'bracvam'})

LABORATORY_ROLE_KEYS = frozenset({
    'lead_laboratory',
    'participating_laboratory',
})

ParticipantJustification = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ParticipantAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_default=True)

    user_id: UUID
    role_key: ParticipantRole
    laboratory_id: UUID | None = None

    @field_validator('laboratory_id')
    @classmethod
    def validate_laboratory_requirement(cls, value, info):
        role = info.data.get('role_key')
        if role is None:
            return value
        if role in LABORATORY_ROLE_KEYS and value is None:
            raise ValueError('laboratory_id is required for laboratory roles')
        if role not in LABORATORY_ROLE_KEYS and value is not None:
            raise ValueError('laboratory_id is not allowed for this role')
        return value


class ParticipantAssignmentPublic(BaseModel):
    model_config = ConfigDict(extra='forbid')

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
    model_config = ConfigDict(extra='forbid')

    has_conflict: bool
    justification: ParticipantJustification


class ConflictDeclarationPublic(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: UUID
    assignment_id: UUID
    has_conflict: bool
    justification: str
    declared_at: datetime


class ParticipantHistoryItem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assignment: ParticipantAssignmentPublic
    declarations: list[ConflictDeclarationPublic]


class ParticipantHistoryPage(BaseModel):
    model_config = ConfigDict(extra='forbid')

    offset: int
    limit: int
    items: list[ParticipantHistoryItem]


# ---------------------------------------------------------------------------
# Spec 013 — Avaliação Configurável por IA
# ---------------------------------------------------------------------------

EvaluationMode = Literal['simple', 'advanced']
CheckType = Literal[
    'presence',
    'conformity',
    'quality',
    'comparison',
    'cross_field_consistency',
]
CriterionPolarity = Literal['positive', 'negative', 'consistency']
CriterionSeverity = Literal['info', 'low', 'medium', 'high', 'critical']
CriterionOnMissing = Literal['non_compliant', 'indeterminate']
AssignmentTargetType = Literal[
    'field', 'field_set', 'document', 'form', 'process'
]
ConsolidatedResult = Literal['positive', 'negative']
ItemConclusion = Literal[
    'compliant', 'non_compliant', 'partial', 'indeterminate'
]

EvaluationName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)
]
Statement = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=2000),
]


class CriterionInput(BaseModel):
    id: UUID | None = None
    order_index: int = Field(0, ge=0)
    statement: Statement
    check_type: CheckType
    polarity: CriterionPolarity = 'positive'
    required_evidence: str | None = None
    severity: CriterionSeverity = 'medium'
    on_missing_info: CriterionOnMissing = 'indeterminate'
    recommendation_hint: str | None = None


class CriterionPublic(BaseModel):
    id: UUID
    order_index: int
    statement: str
    check_type: str
    polarity: str
    required_evidence: str | None = None
    severity: str
    on_missing_info: str
    recommendation_hint: str | None = None
    model_config = ConfigDict(from_attributes=True)


class CreateEvaluationRequest(BaseModel):
    name: EvaluationName
    description: str | None = None
    mode: EvaluationMode = 'simple'
    objective: Statement


class EvaluationVersionSummary(BaseModel):
    version_number: int
    status: str
    criteria_count: int = 0
    test_run_count: int = 0
    published_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class EvaluationVersionResponse(BaseModel):
    version_number: int
    status: str
    objective: str
    references: list[dict[str, Any]] = Field(default_factory=list)
    test_run_count: int
    published_at: datetime | None = None
    criteria: list[CriterionPublic] = Field(default_factory=list)


class EvaluationDefinitionResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    mode: str
    description: str | None = None
    versions: list[EvaluationVersionSummary] = Field(default_factory=list)


class EvaluationDefinitionSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    mode: str
    latest_version: EvaluationVersionSummary | None = None
    published_versions: int = 0
    assignments_count: int = 0


class EvaluationDefinitionPage(FilterPage):
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    items: list[EvaluationDefinitionSummary]


class PatchEvaluationVersionRequest(BaseModel):
    objective: Statement | None = None
    references: list[UUID] | None = None
    criteria: list[CriterionInput] | None = None


class PublishResponse(BaseModel):
    version_number: int
    status: str
    published_at: datetime | None = None
    test_warning: bool


class SuggestCriteriaRequest(BaseModel):
    objective: Statement
    target_type: AssignmentTargetType


class SuggestedCriterionPublic(BaseModel):
    statement: str
    check_type: str
    polarity: str
    suggested_severity: str


class SuggestCriteriaResponse(BaseModel):
    suggestions: list[SuggestedCriterionPublic] = Field(default_factory=list)


class EvaluationTestRequest(BaseModel):
    sample_content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ]


class CriterionTestResult(BaseModel):
    criterion_id: UUID | None = None
    statement: str
    check_type: str
    severity: str
    conclusion: str
    is_alert: bool
    evidence_excerpt: str | None = None
    evidence_location: str | None = None
    justification: str | None = None
    recommendation: str | None = None


class EvaluationTestResponse(BaseModel):
    results: list[CriterionTestResult] = Field(default_factory=list)
    consolidated_result: ConsolidatedResult
    real_cost: float


class ReferenceCreateRequest(BaseModel):
    identifier: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    ]
    label: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    version_label: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    ]
    reference_date: date | None = None


class ReferencePublic(BaseModel):
    id: UUID
    identifier: str
    label: str
    version_label: str
    reference_date: date | None = None
    model_config = ConfigDict(from_attributes=True)


class ReferenceImpactVersion(BaseModel):
    definition_id: UUID
    version_number: int


class ReferenceImpactResponse(BaseModel):
    evaluation_versions: list[ReferenceImpactVersion] = Field(
        default_factory=list
    )
    runs_count: int = 0


class EvaluationAssignmentInput(BaseModel):
    definition_id: UUID
    pinned_version_id: UUID | None = None
    target_type: AssignmentTargetType
    field_keys: list[str] = Field(default_factory=list)
    enabled: bool = True


class EvaluationAssignmentPublic(BaseModel):
    id: UUID
    definition_id: UUID
    definition_name: str
    pinned_version_id: UUID | None = None
    effective_version_number: int | None = None
    target_type: str
    field_keys: list[str] = Field(default_factory=list)
    enabled: bool


class ReplaceAssignmentsRequest(BaseModel):
    assignments: list[EvaluationAssignmentInput] = Field(default_factory=list)


class AssignmentsResponse(BaseModel):
    template_key: str
    assignments: list[EvaluationAssignmentPublic] = Field(default_factory=list)


class EvaluableFieldPublic(BaseModel):
    field_key: str
    label: str
    assignments: list[dict[str, Any]] = Field(default_factory=list)


class EvaluableFieldsResponse(BaseModel):
    fields: list[EvaluableFieldPublic] = Field(default_factory=list)


class PreEvaluationSummary(BaseModel):
    total: int = 0
    compliant: int = 0
    non_compliant: int = 0
    partial: int = 0
    indeterminate: int = 0


class PreEvaluationItemPublic(BaseModel):
    item_id: UUID
    criterion_id: UUID | None = None
    criterion_statement: str
    check_type: str
    severity: str
    conclusion: str
    is_alert: bool
    evidence_excerpt: str | None = None
    evidence_location: str | None = None
    justification: str | None = None
    recommendation: str | None = None
    inference_confidence: float | None = None
    evidence_completeness: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)


class PreEvaluationVersionUsed(BaseModel):
    definition_name: str
    version_number: int
    references: list[dict[str, Any]] = Field(default_factory=list)


class EvaluatedContentField(BaseModel):
    field_key: str
    label: str
    value: Any = None


class PreEvaluationResponse(BaseModel):
    run_id: UUID
    correlation_id: UUID
    status: str
    consolidated_result: ConsolidatedResult | None = None
    provider: str | None = None
    models_used: dict[str, Any] = Field(default_factory=dict)
    real_cost: float = 0.0
    started_at: datetime
    finished_at: datetime | None = None
    error_summary: str | None = None
    summary: PreEvaluationSummary
    attention_points: list[PreEvaluationItemPublic] = Field(
        default_factory=list
    )
    evaluations: list[PreEvaluationVersionUsed] = Field(default_factory=list)
    evaluated_content: list[EvaluatedContentField] = Field(
        default_factory=list
    )
    direct_review_request: dict[str, Any] | None = None


class DirectReviewRequestBody(BaseModel):
    justification: str | None = None


class DirectReviewResponse(BaseModel):
    process_status: str
    direct_review_request_id: UUID


class ReviewerFeedbackItem(BaseModel):
    item_id: UUID
    verdict: Literal['agree', 'disagree', 'inconclusive']
    reason: str | None = None


class ReviewerFeedbackRequest(BaseModel):
    items: list[ReviewerFeedbackItem] = Field(default_factory=list)


class ReviewerFeedbackResponse(BaseModel):
    recorded: int


class AgreementMetricsResponse(BaseModel):
    overall_agreement_rate: float | None = None
    total_feedback: int = 0
    by_check_type: dict[str, float] = Field(default_factory=dict)
    most_contested_criteria: list[dict[str, Any]] = Field(default_factory=list)
    runs_with_most_disagreements: list[dict[str, Any]] = Field(
        default_factory=list
    )
