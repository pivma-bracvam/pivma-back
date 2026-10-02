from datetime import date, datetime
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_serializer,
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


# ==========================================
# REFERÊNCIAS (Specs 032 e 033)
# ==========================================
# Entidades relacionadas em respostas: objetos pequenos de formato fixo, em
# um nível só. Campos de auditoria continuam como identificadores.


class ProcessRef(BaseModel):
    id: UUID = Field(description='Identificador do processo')
    code: str = Field(description='Código do processo')
    title: str = Field(description='Título do processo')


class PhaseRef(BaseModel):
    key: str = Field(description='Chave da fase no template')
    order: int = Field(description='Ordem da fase no processo')


class UserRef(BaseModel):
    """Pessoa referenciada. Nunca traz e-mail."""

    id: UUID = Field(description='Identificador do usuário')
    username: str = Field(description='Nome de usuário')
    full_name: str | None = Field(description='Nome completo')


class ProfileRef(BaseModel):
    id: UUID = Field(description='Identificador do perfil')
    name: str = Field(description='Nome do perfil')
    active: bool = Field(description='Perfil ativo')
    model_config = ConfigDict(extra='forbid')


class InstitutionRef(BaseModel):
    id: UUID = Field(description='Identificador da instituição')
    name: str = Field(description='Nome da instituição')
    active: bool = Field(description='Instituição ativa')
    model_config = ConfigDict(extra='forbid')


class LaboratoryRef(BaseModel):
    id: UUID = Field(description='Identificador do laboratório')
    name: str = Field(description='Nome do laboratório')
    active: bool = Field(description='Laboratório ativo')
    institution: InstitutionRef = Field(
        description='Instituição do laboratório'
    )
    model_config = ConfigDict(extra='forbid')


class TemplateRef(BaseModel):
    key: str = Field(description='Chave do template de processo')
    name: str = Field(description='Nome do template de processo')
    version: int = Field(description='Versão do template usada no processo')


# ==========================================
# ERROS (Spec 034)
# ==========================================


class FieldError(BaseModel):
    location: Literal['body', 'query', 'path', 'header', 'cookie'] = Field(
        description='Onde está o campo: corpo, consulta, caminho, cabeçalho'
    )
    field: str = Field(
        description='Caminho do campo separado por ponto; vazio para o corpo'
    )
    code: str = Field(description='Tipo do problema (ex.: missing)')
    message: str = Field(description='Mensagem em português')


class ErrorDetail(BaseModel):
    """Erro no formato único. Códigos específicos podem trazer contexto."""

    code: str = Field(description='Código estável do erro, em inglês')
    message: str = Field(description='Mensagem em português')
    fields: list[FieldError] | None = Field(
        None, description='Campos com problema (só em erros de validação)'
    )
    model_config = ConfigDict(extra='allow')


class ErrorResponse(BaseModel):
    detail: ErrorDetail = Field(description='Erro da requisição')


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
            raise ValueError('Senha inválida.')
        return value


class UserPublic(BaseModel):
    id: UUID
    username: str
    email: Annotated[str, Field(json_schema_extra={'format': 'email'})]
    full_name: str | None
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=64,
            pattern=USERNAME_PATTERN,
        ),
    ] = None
    email: Annotated[str, Field(json_schema_extra={'format': 'email'})] = None
    full_name: FullNameValue = None
    password: Annotated[
        str, StringConstraints(min_length=8, max_length=128)
    ] = None

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
            raise ValueError('Senha inválida.')
        return value

    @model_validator(mode='after')
    def require_update_field(self):
        if not self.model_fields_set:
            raise ValueError('Informe ao menos um campo.')
        if any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError('Campos de atualização não podem ser nulos.')
        return self


class AdminUser(UserPublic):
    active: bool
    profiles: list[ProfileRef]
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
    profiles: list[ProfileRef]
    global_permissions: list[str]
    scopes: list[AccessScope]
    model_config = ConfigDict(extra='forbid')


class CurrentUserResponse(BaseModel):
    user: UserIdentity
    access: CurrentUserAccess
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
            raise ValueError('As permissões não podem se repetir.')
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
            raise ValueError('As permissões não podem se repetir.')
        return value

    def model_post_init(self, __context) -> None:
        if not self.model_fields_set:
            raise ValueError('Informe ao menos um campo.')


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
    profiles: list[ProfileRef]
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


class InstitutionPublic(InstitutionRef):
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


class LaboratoryPublic(BaseModel):
    id: UUID
    name: str
    active: bool
    institution: InstitutionRef = Field(
        description='Instituição do laboratório'
    )
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
    user: UserRef = Field(description='Pessoa afiliada')
    institution: InstitutionRef
    laboratory: LaboratoryRef | None
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
    institution: InstitutionRef
    laboratory: LaboratoryRef | None
    model_config = ConfigDict(extra='forbid')


class InstitutionalChangePublic(BaseModel):
    id: UUID
    action: str
    target_type: str
    target_id: UUID
    actor_user_id: UUID | None
    occurred_at: datetime
    model_config = ConfigDict(extra='forbid')


# ==========================================
# LISTAGENS (Spec 032)
# ==========================================

ItemT = TypeVar('ItemT')
FiltersT = TypeVar('FiltersT')
FacetsT = TypeVar('FacetsT')
SummaryT = TypeVar('SummaryT')

# Blocos do envelope que só aparecem quando pedidos em `include`.
_OPTIONAL_ENVELOPE_BLOCKS = ('facets', 'summary')


class Pagination(BaseModel):
    page: int = Field(description='Página atual, começando em 1')
    per_page: int = Field(description='Itens por página')
    total_items: int = Field(description='Total de itens com os filtros')
    total_pages: int = Field(description='Total de páginas; 0 sem itens')
    has_next: bool = Field(description='Existe página seguinte')
    has_prev: bool = Field(description='Existe página anterior')


class SortApplied(BaseModel):
    by: str = Field(description='Campo de ordenação aplicado')
    order: Literal['asc', 'desc'] = Field(description='Direção aplicada')


class ListPage(BaseModel, Generic[ItemT, FiltersT]):
    """Resposta padrão de listagem (Spec 032, FR-001 a FR-008).

    Base das listagens sem contagens nem resumo (Spec 033).
    """

    data: list[ItemT] = Field(description='Itens da página')
    pagination: Pagination = Field(description='Paginação por página')
    filters_applied: FiltersT = Field(
        description='Filtros aplicados, incluindo os padrões'
    )
    sort: SortApplied = Field(description='Ordenação aplicada')


class NoFilters(BaseModel):
    """Listagem sem filtros."""


class ListEnvelope(
    ListPage[ItemT, FiltersT], Generic[ItemT, FiltersT, FacetsT, SummaryT]
):
    """Listagem com contagens e resumo sob demanda (Spec 032)."""

    facets: FacetsT | None = Field(
        None,
        description='Contagens por valor de filtro (só com include=facets)',
    )
    summary: SummaryT | None = Field(
        None, description='Agregados da listagem (só com include=summary)'
    )

    @model_serializer(mode='wrap')
    def _omit_unrequested_blocks(self, handler: SerializerFunctionWrapHandler):
        # Só no nível do envelope: `exclude_none` apagaria também os campos
        # nulos dos itens (ex.: `due_date`) (research R4). Sem anotação de
        # retorno de propósito: com ela, o OpenAPI troca o schema do envelope
        # por um objeto genérico.
        data = handler(self)
        for key in _OPTIONAL_ENVELOPE_BLOCKS:
            if data.get(key) is None:
                data.pop(key, None)
        return data


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


# Spec 030: o processo expõe só o ciclo de vida; a posição no fluxo vem das
# fases e atividades.
ProcessLifecycle = Literal['OPEN', 'CLOSED', 'CANCELLED', 'ARCHIVED']


class ProcessInstanceDetail(BaseModel):
    id: UUID
    code: str
    title: str
    status: ProcessLifecycle
    template: TemplateRef = Field(description='Template e versão do processo')
    started_at: datetime | None = None
    closed_at: datetime | None = None
    closure_reason: str | None = None
    available_actions: list[Literal['DELETE', 'ARCHIVE']] = Field(
        default_factory=list
    )
    model_config = ConfigDict(from_attributes=True)


class ProcessLifecycleResponse(BaseModel):
    id: UUID
    status: ProcessLifecycle | None = None
    available_actions: list[Literal['DELETE', 'ARCHIVE']] = Field(
        default_factory=list
    )


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
    status: ProcessLifecycle
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
    process_status: ProcessLifecycle
    decision_id: UUID
    outcome: str
    return_review_run: int | None = None


class ActivityCompletionResponse(BaseModel):
    activity_key: str
    run_number: int
    status: str
    artifact_id: UUID | None = None
    pre_evaluation: dict[str, Any] | None = None


TaskStatus = Literal['READY', 'COMPLETED', 'CANCELLED']
# Execução que tem tarefa; a bloqueada não tem (Spec 036, R11).
ActivityRunStatus = Literal[
    'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'WAIVED', 'SUPERSEDED'
]


class TaskSummary(BaseModel):
    id: UUID
    process: ProcessRef
    # Atividade, execução e fase da tarefa: permitem agrupar por atividade
    # (ex.: kanban da etapa 1) sem uma chamada por tarefa.
    activity_key: str
    activity_run_number: int
    phase: PhaseRef
    title: str
    assigned_role: str | None = None
    status: TaskStatus
    due_date: datetime | None = None
    can_act: bool = Field(
        description=(
            'O usuário pode agir nesta tarefa: tem concessão de editar a '
            'atividade e não tem conflito de interesse vigente no processo'
        )
    )
    laboratory: LaboratoryRef | None = Field(
        default=None,
        description=(
            'Laboratório da execução; nulo em atividade de execução única'
        ),
    )
    activity_run_status: ActivityRunStatus = Field(
        description='Status da execução da tarefa'
    )
    model_config = ConfigDict(from_attributes=True)


class TaskFiltersApplied(BaseModel):
    status: list[TaskStatus] = Field(
        description='Status pedidos; vazio = todos'
    )
    activity_key: list[str] = Field(
        description='Atividades pedidas; vazio = todas'
    )
    phase_order: int | None = Field(description='Ordem da fase')
    process_id: UUID | None = Field(description='Processo')
    role: str | None = Field(description='Cargo da tarefa')
    actionable: bool = Field(
        description='Só tarefas em que o usuário pode agir'
    )
    current_run: bool = Field(
        description='Só a rodada vigente de cada atividade (padrão)'
    )
    overdue: bool = Field(description='Só tarefas abertas com prazo vencido')


class TaskFacets(BaseModel):
    activity_key: dict[str, int] = Field(
        description='Quantidade de tarefas por atividade'
    )
    status: dict[str, int] = Field(
        description='Quantidade de tarefas por status'
    )


class TaskListSummary(BaseModel):
    ai_pre_evaluation_in_progress: int = Field(
        description='Processos visíveis com pré-avaliação por IA em andamento'
    )


class TaskListResponse(
    ListEnvelope[TaskSummary, TaskFiltersApplied, TaskFacets, TaskListSummary]
):
    """Lista de tarefas no padrão de listagem (Spec 032)."""


class TaskDetail(BaseModel):
    id: UUID
    process_id: UUID
    activity_key: str
    activity_run_number: int
    title: str
    status: str
    is_blocked: bool
    blocked_reason: str | None = None
    due_date: datetime | None = None
    laboratory: LaboratoryRef | None = Field(
        default=None,
        description=(
            'Laboratório da execução; nulo em atividade de execução única'
        ),
    )
    activity_run_status: ActivityRunStatus = Field(
        description='Status da execução da tarefa'
    )


class TimelineEvent(BaseModel):
    id: UUID
    event_type: str
    user_id: UUID | None = None
    activity_run_id: UUID | None = None
    occurred_at: datetime
    context_data: dict | None = None
    model_config = ConfigDict(from_attributes=True)


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
    # Issue #41 — papéis novos da Etapa 2 (Spec 028: matriz de atribuição de
    # cargo). `sponsor` e `sample_selection_group` são exigidos pela esteira
    # completa da Etapa 2; `regulatory_observer` (ANVISA/MAPA) é reservado
    # embora esta feature não o utilize; `collaborator` é o papel amplo de
    # "Colaboradores e Observadores", distinto de `regulatory_observer`.
    'sponsor',
    'sample_selection_group',
    'regulatory_observer',
    'collaborator',
]

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
            raise ValueError(
                'Informe o laboratório para cargos de laboratório.'
            )
        if role not in LABORATORY_ROLE_KEYS and value is not None:
            raise ValueError('Este cargo não aceita laboratório.')
        return value


class ParticipantAssignmentPublic(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: UUID
    process: ProcessRef = Field(description='Processo da designação')
    user: UserRef = Field(description='Pessoa designada')
    role_key: str
    laboratory: LaboratoryRef | None = Field(
        description=(
            'Laboratório da designação; nulo fora dos cargos de laboratório'
        )
    )
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


# ==========================================
# ROLE ASSIGNMENT INVITES (Spec 028)
# ==========================================

InviteChannel = Literal['link', 'email']


class InviteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_default=True)

    email: Annotated[str, Field(json_schema_extra={'format': 'email'})]
    role_key: ParticipantRole
    laboratory_id: UUID | None = None
    channel: InviteChannel = 'link'

    @field_validator('email', mode='before')
    @classmethod
    def validate_email_preserving_case(cls, value):
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        email_adapter.validate_python(trimmed)
        return trimmed

    @field_validator('laboratory_id')
    @classmethod
    def validate_laboratory_requirement(cls, value, info):
        role = info.data.get('role_key')
        if role is None:
            return value
        if role in LABORATORY_ROLE_KEYS and value is None:
            raise ValueError(
                'Informe o laboratório para cargos de laboratório.'
            )
        if role not in LABORATORY_ROLE_KEYS and value is not None:
            raise ValueError('Este cargo não aceita laboratório.')
        return value


class InviteDeliveryPublic(BaseModel):
    """Situação do envio automático do convite (Spec 036, FR-017)."""

    model_config = ConfigDict(extra='forbid')

    status: Literal['pending', 'sent', 'failed', 'cancelled']
    attempts: int
    last_attempt_at: datetime | None
    sent_at: datetime | None
    error_code: str | None


class InvitePublic(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: UUID
    process: ProcessRef = Field(description='Processo do convite')
    role_key: str
    laboratory: LaboratoryRef | None = Field(
        description=(
            'Laboratório do convite; nulo fora dos cargos de laboratório'
        )
    )
    email: str
    channel: str
    status: Literal['pending', 'accepted', 'revoked']
    expired: bool
    expires_at: datetime
    created_by: UUID
    created_at: datetime
    accepted_at: datetime | None
    accepted_by: UUID | None
    revoked_at: datetime | None
    revoked_by: UUID | None
    delivery: InviteDeliveryPublic | None = Field(
        default=None,
        description=(
            'Situação do envio mais recente do convite (Spec 036); nulo no '
            'canal `link`'
        ),
    )


class InviteCreatedResponse(InvitePublic):
    token: str


class InvitePreview(BaseModel):
    model_config = ConfigDict(extra='forbid')

    role_key: str
    process_code: str
    process_title: str
    masked_email: str
    expires_at: datetime
    expired: bool


class InviteAcceptResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    invite: InvitePublic
    assignment_id: UUID
    process_id: UUID
    role_key: str


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


# Revisão do retorno (Spec 030, US4)
ReturnReviewChoice = Literal['REVISE', 'CONTEST_AI', 'WITHDRAW']
ReturnReviewSource = Literal['AI_PRE_EVALUATION', 'TRIAGE']


class ReturnReviewTriageDecision(BaseModel):
    outcome: str
    justification: str
    decided_at: datetime


class ReturnReviewResponse(BaseModel):
    run_number: int
    source: ReturnReviewSource
    opened_at: datetime
    due_date: datetime | None = None
    available_choices: list[ReturnReviewChoice]
    ai_pre_evaluation: PreEvaluationResponse | None = None
    triage_decision: ReturnReviewTriageDecision | None = None


class ReturnReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    choice: ReturnReviewChoice
    justification: str | None = None


class ReturnReviewDecisionResponse(BaseModel):
    choice: ReturnReviewChoice
    process_status: ProcessLifecycle
    submission_run: int | None = None


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


# ---------------------------------------------------------------------------
# Spec 031 — Definição e Preparação das Amostras (estudo cego)
# ---------------------------------------------------------------------------

SampleText255 = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
SampleText64 = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
SampleLongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
# O formato e o dígito verificador do CAS são validados no serviço, que
# responde com `code='invalid_cas'`; aqui só se limita o tamanho.
SampleCasNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]
SampleActivityStatus = Literal['BLOCKED', 'IN_PROGRESS', 'COMPLETED']


class SampleSubstanceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    chemical_name: SampleText255
    cas_number: SampleCasNumber
    lot: SampleText64
    safe_handling_instructions: SampleLongText
    purity: SampleText64 | None = None
    solubility: SampleLongText | None = None


class SampleSubstanceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    chemical_name: SampleText255 | None = None
    cas_number: SampleCasNumber | None = None
    lot: SampleText64 | None = None
    safe_handling_instructions: SampleLongText | None = None
    purity: SampleText64 | None = None
    solubility: SampleLongText | None = None


class SampleBlindCode(BaseModel):
    code: str
    laboratory_id: UUID
    laboratory_name: str


class SampleSds(BaseModel):
    filename: str
    size: int | None = None
    uploaded_at: datetime


class SampleSubstance(BaseModel):
    id: UUID
    chemical_name: str
    cas_number: str
    lot: str
    purity: str | None = None
    solubility: str | None = None
    safe_handling_instructions: str
    sds: SampleSds | None = None
    blind_codes: list[SampleBlindCode]


class SampleSubstanceList(BaseModel):
    activity_status: SampleActivityStatus
    substances: list[SampleSubstance]


class SampleCompletionResponse(BaseModel):
    activity_status: SampleActivityStatus
    substance_count: int
    laboratory_count: int
    code_count: int


class SampleLabel(BaseModel):
    code: str
    study_code: str
    laboratory: LaboratoryRef = Field(description='Laboratório destinatário')
    lot: str
    qr_url: str = Field(
        description=(
            'URL do frasco gravada no QR; a imagem vem de '
            'GET /processes/{id}/samples/vials/{code}/qr.svg'
        )
    )


class BlindVial(BaseModel):
    """Visão cega do frasco: nunca nome químico, CAS nem SDS (FR-021)."""

    model_config = ConfigDict(extra='forbid')

    code: str
    lot: str
    safe_handling_instructions: str


# ==========================================
# RESPOSTAS DE LISTAGEM (Spec 033)
# ==========================================
# Uma classe nomeada por listagem, para o OpenAPI ter um schema legível.


class UserListFilters(BaseModel):
    search: str | None = Field(
        description='Busca por nome de usuário ou e-mail'
    )
    active: bool = Field(description='Contas ativas (true) ou inativas')
    profile_id: UUID | None = Field(description='Contas com este perfil')


class UserListResponse(ListPage[AdminUser, UserListFilters]):
    """Usuários da administração."""


class PermissionListResponse(ListPage[PermissionPublic, NoFilters]):
    """Catálogo de permissões."""


class ProfileListResponse(ListPage[ProfilePublic, NoFilters]):
    """Perfis de acesso."""


class RbacChangeListResponse(ListPage[RbacChangePublic, NoFilters]):
    """Trilha de alterações do RBAC."""


class InstitutionListResponse(ListPage[InstitutionPublic, NoFilters]):
    """Instituições."""


class LaboratoryListResponse(ListPage[LaboratoryPublic, NoFilters]):
    """Laboratórios."""


class AffiliationListResponse(ListPage[AffiliationPublic, NoFilters]):
    """Afiliações de um usuário."""


class SelfAffiliationListResponse(ListPage[SelfAffiliationPublic, NoFilters]):
    """Afiliações ativas do usuário logado."""


class InstitutionalChangeListResponse(
    ListPage[InstitutionalChangePublic, NoFilters]
):
    """Trilha de alterações do catálogo institucional."""


class ProcessListFilters(BaseModel):
    status: ProcessLifecycle | None = Field(
        description='Status do processo; nulo = todos, menos os arquivados'
    )


class ProcessTemplateListResponse(ListPage[ProcessTemplateSummary, NoFilters]):
    """Templates de processo ativos."""


class ProcessListResponse(ListPage[ProcessInstanceDetail, ProcessListFilters]):
    """Processos visíveis ao usuário."""


class SubmissionVersionListResponse(
    ListPage[SubmissionVersionSummary, NoFilters]
):
    """Versões devolvidas da submissão."""


class TimelineListResponse(ListPage[TimelineEvent, NoFilters]):
    """Eventos da linha do tempo visíveis ao usuário, em ordem cronológica."""


class ParticipantListResponse(
    ListPage[ParticipantAssignmentPublic, NoFilters]
):
    """Designações ativas do processo visíveis ao usuário."""


class ParticipantHistoryListResponse(
    ListPage[ParticipantHistoryItem, NoFilters]
):
    """Histórico de designações e declarações de conflito."""


class InviteListResponse(ListPage[InvitePublic, NoFilters]):
    """Convites do processo que o usuário pode gerir."""


class EvaluationListFilters(BaseModel):
    search: str | None = Field(description='Busca pelo nome da avaliação')


class EvaluationListResponse(
    ListPage[EvaluationDefinitionSummary, EvaluationListFilters]
):
    """Biblioteca de avaliações de IA."""


class ReferenceListResponse(ListPage[ReferencePublic, NoFilters]):
    """Referências normativas das avaliações de IA."""


class SampleLabelListResponse(ListPage[SampleLabel, NoFilters]):
    """Etiquetas dos frascos, só para o Grupo de Seleção de Amostras."""


# ==========================================
# EXECUÇÃO POR LABORATÓRIO (Spec 036)
# ==========================================

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LaboratoryWaiverCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    laboratory_id: UUID = Field(
        description='Laboratório congelado a dispensar'
    )
    reason: Reason = Field(description='Motivo da dispensa')


class LaboratoryWaiverPublic(BaseModel):
    id: UUID
    process_id: UUID
    phase: PhaseRef
    laboratory: LaboratoryRef
    reason: str
    waived_by: UserRef
    created_at: datetime
    waived_activity_keys: list[str] = Field(
        description=(
            'Atividades cujas execuções do laboratório foram dispensadas '
            'nesta chamada, na ordem da fase'
        )
    )


class LaboratoryRunReopenRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    reason: Reason = Field(description='Motivo da reabertura')


class LaboratoryRunReopened(BaseModel):
    activity_key: str
    laboratory: LaboratoryRef
    previous_run_number: int = Field(description='Execução substituída')
    run_number: int = Field(description='Execução nova do laboratório')
    activity_status: str = Field(description='Status da atividade agora')
    reblocked_activity_keys: list[str] = Field(
        description='Atividades que voltaram a ficar bloqueadas, em cadeia'
    )
