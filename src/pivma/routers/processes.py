import logging
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pivma.core.authorization import (
    can_manage_participants,
    can_manage_process_templates,
    has_process_review_access,
    user_cargos,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    FormTemplate,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.database.models import User as UserModel
from pivma.core.errors import (
    api_error,
    domain_error,
    form_field_errors,
    http_error,
)
from pivma.core.listing import (
    PageQuery,
    PerPageQuery,
    build_pagination,
    paginate_items,
    paginate_query,
)
from pivma.core.process_engine import (
    STATUS_ARCHIVED,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    archive_process,
    available_lifecycle_actions,
    delete_process,
    get_returned_submission_version,
    instantiate_process,
    list_returned_submission_versions,
    process_visibility_clause,
    update_form_template_definition,
    update_process_submission,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    CreateProcessRequest,
    FormFieldUpdateDefinition,
    FormTemplateDetailResponse,
    NoFilters,
    PatchSubmissionRequest,
    ProcessInstanceDetail,
    ProcessLifecycle,
    ProcessLifecycleResponse,
    ProcessListFilters,
    ProcessListResponse,
    ProcessSubmissionResponse,
    ProcessTemplateDetail,
    ProcessTemplateListResponse,
    ProcessTemplateSummary,
    ReplaceSubmissionRequest,
    SortApplied,
    SubmissionVersionListResponse,
    SubmissionVersionResponse,
    TemplateRef,
    TimelineEvent,
    TimelineListResponse,
    UpdateFormTemplateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/processes', tags=['Processes'])

PARTICIPANT_EVENT_TYPES = frozenset({
    'PARTICIPANT_ASSIGNED',
    'PARTICIPANT_REVOKED',
    'CONFLICT_DECLARED',
    # Spec 035: perda e volta da validade de designação laboratorial.
    'PARTICIPANT_EFFECTIVENESS_LOST',
    'PARTICIPANT_EFFECTIVENESS_RESTORED',
})


def _normalize_definition_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Garante `activity_type` explícito em cada atividade da definição.

    A definição declarativa (YAML) de um template pode não declarar
    `activity_type` — os métodos oficiais anteriores à Spec 017 não o
    fazem. O valor padrão (`form`) só é aplicado no banco no momento da
    instanciação (`_create_phases_and_activities`); esta função aplica a
    mesma regra na leitura (Spec 017 FR-006), para que
    `GET /processes/templates/{key}` seja consistente independentemente de
    o YAML de origem declarar o campo ou não. Retorna uma cópia — nunca
    modifica o payload persistido.
    """
    normalized = deepcopy(payload)
    for phase in normalized.get('phases', []):
        for activity in phase.get('activities', []):
            activity.setdefault('activity_type', 'form')
    return normalized


async def _events_of_visible_activities(
    session: Session,
    user_id,
    process_id,
    events: list[AuditEvent],
) -> list[AuditEvent]:
    """Descarta eventos de execuções cuja atividade o usuário não vê

    (Spec 030, FR-021). Eventos sem execução (processo, participantes)
    seguem as regras de `_visible_events`.
    """
    run_ids = {e.activity_run_id for e in events if e.activity_run_id}
    if not run_ids:
        return events
    cargos = await user_cargos(session, user_id, process_id)
    rows = await session.execute(
        select(ActivityRun.id, ActivityInstance.view_roles)
        .join(
            ActivityInstance,
            ActivityInstance.id == ActivityRun.activity_instance_id,
        )
        .where(ActivityRun.id.in_(run_ids))
    )
    hidden = {run_id for run_id, roles in rows if not cargos & set(roles)}
    return [e for e in events if e.activity_run_id not in hidden]


async def _visible_events(
    session: Session,
    current_user: UserModel,
    process_id,
    events: list[AuditEvent],
) -> list[AuditEvent]:
    events = await _events_of_visible_activities(
        session, current_user.id, process_id, events
    )
    manages_participants = await can_manage_participants(
        session, current_user.id, process_id
    )
    if manages_participants:
        return events

    visible = []
    for event in events:
        if event.event_type in PARTICIPANT_EVENT_TYPES:
            context = event.context_data or {}
            if context.get('participant_user_id') != str(current_user.id):
                continue
        visible.append(event)
    return visible


def _template_ref(
    version: ProcessTemplateVersion, template: ProcessTemplate
) -> TemplateRef:
    return TemplateRef(
        key=template.key, name=template.name, version=version.version_number
    )


@router.get(
    '/templates',
    response_model=ProcessTemplateListResponse,
    status_code=HTTPStatus.OK,
)
async def list_templates(
    session: Session,
    _: CurrentUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    items, total = await paginate_query(
        session,
        select(ProcessTemplate).where(
            ProcessTemplate.deleted_at.is_(None),
            ProcessTemplate.is_active.is_(True),
        ),
        order_by=(ProcessTemplate.name, ProcessTemplate.key),
        page=page,
        per_page=per_page,
    )
    return ProcessTemplateListResponse(
        data=[
            ProcessTemplateSummary.model_validate(item, from_attributes=True)
            for item in items
        ],
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='name', order='asc'),
    )


@router.get(
    '/templates/{key}',
    response_model=ProcessTemplateDetail,
    status_code=HTTPStatus.OK,
)
async def get_template_detail(key: str, session: Session, _: CurrentUser):
    stmt = (
        select(ProcessTemplate)
        .where(
            ProcessTemplate.key == key, ProcessTemplate.deleted_at.is_(None)
        )
        .options(selectinload(ProcessTemplate.versions))
    )
    res = await session.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise http_error(HTTPStatus.NOT_FOUND, 'Template não encontrado.')

    published_versions = sorted(
        [
            v
            for v in template.versions
            if v.deleted_at is None and v.is_published
        ],
        key=lambda x: x.version_number,
        reverse=True,
    )
    if not published_versions:
        raise http_error(
            HTTPStatus.NOT_FOUND,
            'Nenhuma versão publicada encontrada para o template.',
        )

    latest = published_versions[0]
    return ProcessTemplateDetail(
        id=template.id,
        key=template.key,
        name=template.name,
        version_number=latest.version_number,
        definition=_normalize_definition_payload(latest.definition_payload),
    )


@router.get(
    '/templates/{key}/forms/{form_key}',
    response_model=FormTemplateDetailResponse,
    status_code=HTTPStatus.OK,
)
async def get_form_template_detail(
    key: str,
    form_key: str,
    session: Session,
    _: CurrentUser,
):
    # Validar se o processo existe
    p_stmt = select(ProcessTemplate).where(
        ProcessTemplate.key == key, ProcessTemplate.deleted_at.is_(None)
    )
    if not (await session.execute(p_stmt)).scalar_one_or_none():
        raise http_error(
            HTTPStatus.NOT_FOUND, 'Template de processo não encontrado.'
        )

    stmt = (
        select(FormTemplate)
        .where(
            FormTemplate.key == form_key,
            FormTemplate.deleted_at.is_(None),
        )
        .options(selectinload(FormTemplate.fields))
    )
    form_template = (await session.execute(stmt)).scalar_one_or_none()
    if not form_template:
        raise http_error(
            HTTPStatus.NOT_FOUND, 'Template de formulário não encontrado.'
        )

    active_fields = sorted(
        [f for f in form_template.fields if f.deleted_at is None],
        key=lambda x: x.order_index,
    )

    return FormTemplateDetailResponse(
        id=form_template.id,
        key=form_template.key,
        name=form_template.name,
        version=form_template.version,
        description=form_template.description,
        fields=[
            FormFieldUpdateDefinition(
                field_key=f.field_key,
                label=f.label,
                help_text=f.help_text,
                field_type=f.field_type,
                is_required=f.is_required,
                order_index=f.order_index,
                section=(
                    f.validation_rules.get('section')
                    if f.validation_rules
                    else 'Geral'
                ),
                options=f.options,
                validation_rules=f.validation_rules,
                ai_evaluation_enabled=f.ai_evaluation_enabled,
                ai_context_instructions=f.ai_context_instructions,
                ai_validation_rules=f.ai_validation_rules,
            )
            for f in active_fields
        ],
    )


@router.put(
    '/templates/{key}/forms/{form_key}',
    response_model=FormTemplateDetailResponse,
    status_code=HTTPStatus.OK,
)
async def update_form_template_definition_endpoint(
    key: str,
    form_key: str,
    body: UpdateFormTemplateRequest,
    session: Session,
    current_user: CurrentUser,
):
    if not await can_manage_process_templates(session, current_user.id):
        raise http_error(
            HTTPStatus.FORBIDDEN, 'Acesso restrito à equipe de gestão BraCVAM.'
        )

    fields_data = [f.model_dump() for f in body.fields]
    try:
        template, fields = await update_form_template_definition(
            session=session,
            process_template_key=key,
            form_template_key=form_key,
            fields_data=fields_data,
            user_id=current_user.id,
            name=body.name,
            description=body.description,
        )
    except NotFoundError as exc:
        raise domain_error(HTTPStatus.NOT_FOUND, exc) from exc
    except ValidationError as exc:
        raise domain_error(HTTPStatus.UNPROCESSABLE_ENTITY, exc) from exc

    active_fields = sorted(
        [f for f in fields if f.deleted_at is None],
        key=lambda x: x.order_index,
    )

    return FormTemplateDetailResponse(
        id=template.id,
        key=template.key,
        name=template.name,
        version=template.version,
        description=template.description,
        fields=[
            FormFieldUpdateDefinition(
                field_key=f.field_key,
                label=f.label,
                help_text=f.help_text,
                field_type=f.field_type,
                is_required=f.is_required,
                order_index=f.order_index,
                section=(
                    f.validation_rules.get('section')
                    if f.validation_rules
                    else 'Geral'
                ),
                options=f.options,
                validation_rules=f.validation_rules,
                ai_evaluation_enabled=f.ai_evaluation_enabled,
                ai_context_instructions=f.ai_context_instructions,
                ai_validation_rules=f.ai_validation_rules,
            )
            for f in active_fields
        ],
    )


@router.post(
    '',
    response_model=ProcessInstanceDetail,
    status_code=HTTPStatus.CREATED,
)
async def create_process(
    body: CreateProcessRequest,
    session: Session,
    current_user: CurrentUser,
):
    stmt = (
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(
            ProcessTemplate.key == body.template_key,
            ProcessTemplate.deleted_at.is_(None),
            ProcessTemplate.is_active.is_(True),
            ProcessTemplateVersion.deleted_at.is_(None),
            ProcessTemplateVersion.is_published.is_(True),
        )
        .order_by(ProcessTemplateVersion.version_number.desc())
    )
    res = await session.execute(stmt)
    latest_version = res.scalars().first()
    if not latest_version:
        raise http_error(
            HTTPStatus.NOT_FOUND, 'Template não encontrado ou inativo.'
        )

    try:
        process = await instantiate_process(
            session=session,
            template_version=latest_version,
            title=body.title,
            creator_user_id=current_user.id,
        )
    except Exception as e:
        # O detalhe vai para o log, nunca para a resposta (Spec 034, R4).
        logger.exception('process instantiation failed')
        raise api_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            'internal_error',
            'Não foi possível criar o processo.',
        ) from e

    return ProcessInstanceDetail(
        id=process.id,
        code=process.code,
        title=process.title,
        status=process.status,
        template=_template_ref(
            latest_version,
            await session.get(ProcessTemplate, latest_version.template_id),
        ),
        started_at=process.started_at,
        closed_at=process.closed_at,
        closure_reason=process.closure_reason,
        available_actions=await available_lifecycle_actions(
            session, process, current_user.id
        ),
    )


@router.get(
    '',
    response_model=ProcessListResponse,
    status_code=HTTPStatus.OK,
)
async def list_processes(
    session: Session,
    current_user: CurrentUser,
    status: ProcessLifecycle | None = None,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    stmt = select(ProcessInstance).where(ProcessInstance.deleted_at.is_(None))
    if status == STATUS_ARCHIVED and not await has_process_review_access(
        session, current_user.id
    ):
        raise api_error(
            HTTPStatus.FORBIDDEN, 'forbidden', 'Acesso restrito à plataforma.'
        )
    visibility = await process_visibility_clause(session, current_user.id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    stmt = stmt.options(
        selectinload(ProcessInstance.template_version).selectinload(
            ProcessTemplateVersion.template
        )
    )
    if status:
        stmt = stmt.where(ProcessInstance.status == status)
    else:
        stmt = stmt.where(ProcessInstance.status != STATUS_ARCHIVED)

    items, total = await paginate_query(
        session,
        stmt,
        order_by=(
            ProcessInstance.created_at.desc(),
            ProcessInstance.id.desc(),
        ),
        page=page,
        per_page=per_page,
    )

    detail_items = []
    for process in items:
        detail_items.append(
            ProcessInstanceDetail(
                id=process.id,
                code=process.code,
                title=process.title,
                status=process.status,
                template=_template_ref(
                    process.template_version, process.template_version.template
                ),
                started_at=process.started_at,
                closed_at=process.closed_at,
                closure_reason=process.closure_reason,
                available_actions=await available_lifecycle_actions(
                    session, process, current_user.id
                ),
            )
        )

    return ProcessListResponse(
        data=detail_items,
        pagination=build_pagination(page, per_page, total),
        filters_applied=ProcessListFilters(status=status),
        sort=SortApplied(by='created_at', order='desc'),
    )


@router.get(
    '/{id}',
    response_model=ProcessInstanceDetail,
    status_code=HTTPStatus.OK,
)
async def get_process(id: UUID, session: Session, current_user: CurrentUser):
    stmt = select(ProcessInstance).where(
        ProcessInstance.id == id, ProcessInstance.deleted_at.is_(None)
    )
    visibility = await process_visibility_clause(session, current_user.id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    stmt = stmt.options(
        selectinload(ProcessInstance.template_version).selectinload(
            ProcessTemplateVersion.template
        )
    )
    p = (await session.execute(stmt)).scalar_one_or_none()
    if not p:
        raise http_error(HTTPStatus.NOT_FOUND, 'Processo não encontrado.')

    return ProcessInstanceDetail(
        id=p.id,
        code=p.code,
        title=p.title,
        status=p.status,
        template=_template_ref(
            p.template_version, p.template_version.template
        ),
        started_at=p.started_at,
        closed_at=p.closed_at,
        closure_reason=p.closure_reason,
        available_actions=await available_lifecycle_actions(
            session, p, current_user.id
        ),
    )


def _retirement_http_error(error: Exception) -> HTTPException:
    if isinstance(error, NotFoundError):
        return api_error(HTTPStatus.NOT_FOUND, 'not_found', str(error))
    if isinstance(error, AuthorizationError):
        return api_error(HTTPStatus.FORBIDDEN, 'forbidden', str(error))
    return api_error(HTTPStatus.CONFLICT, 'invalid_transition', str(error))


@router.delete(
    '/{id}',
    status_code=HTTPStatus.NO_CONTENT,
)
async def delete_process_endpoint(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
):
    try:
        await delete_process(session, id, current_user.id)
    except (NotFoundError, AuthorizationError, ConflictError) as exc:
        raise _retirement_http_error(exc) from exc


@router.patch(
    '/{id}/archive',
    response_model=ProcessLifecycleResponse,
    response_model_exclude_none=True,
    status_code=HTTPStatus.OK,
)
async def archive_process_endpoint(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
):
    try:
        return await archive_process(session, id, current_user.id)
    except (NotFoundError, AuthorizationError, ConflictError) as exc:
        raise _retirement_http_error(exc) from exc


def _submission_http_error(error: Exception) -> HTTPException:
    if isinstance(error, NotFoundError):
        status = HTTPStatus.NOT_FOUND
    elif isinstance(error, AuthorizationError):
        status = HTTPStatus.FORBIDDEN
    elif isinstance(error, ConflictError):
        status = HTTPStatus.CONFLICT
    else:
        status = HTTPStatus.UNPROCESSABLE_ENTITY
    if isinstance(error, ValidationError) and error.errors:
        return api_error(
            status,
            'invalid_submission_values',
            'Há campos da submissão com valores inválidos.',
            fields=form_field_errors(error.errors),
        )
    if isinstance(error, ConflictError):
        return api_error(status, 'invalid_transition', str(error))
    return domain_error(status, error)


@router.put(
    '/{id}',
    response_model=ProcessSubmissionResponse,
    status_code=HTTPStatus.OK,
)
async def replace_process_submission(
    id: UUID,
    body: ReplaceSubmissionRequest,
    session: Session,
    current_user: CurrentUser,
):
    try:
        return await update_process_submission(
            session,
            id,
            current_user.id,
            mode='PUT',
            title=body.title,
            values_dict=body.values,
        )
    except (
        NotFoundError,
        AuthorizationError,
        ConflictError,
        ValidationError,
    ) as exc:
        raise _submission_http_error(exc) from exc


@router.patch(
    '/{id}',
    response_model=ProcessSubmissionResponse,
    status_code=HTTPStatus.OK,
)
async def patch_process_submission(
    id: UUID,
    body: PatchSubmissionRequest,
    session: Session,
    current_user: CurrentUser,
):
    try:
        return await update_process_submission(
            session,
            id,
            current_user.id,
            mode='PATCH',
            title=body.title,
            values_dict=body.values,
        )
    except (
        NotFoundError,
        AuthorizationError,
        ConflictError,
        ValidationError,
    ) as exc:
        raise _submission_http_error(exc) from exc


@router.get(
    '/{id}/submission-versions',
    response_model=SubmissionVersionListResponse,
    status_code=HTTPStatus.OK,
)
async def list_submission_versions(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    try:
        # O serviço filtra por acesso e ordena; a página vem depois (R2).
        versions, total = paginate_items(
            await list_returned_submission_versions(
                session, id, current_user.id
            ),
            page,
            per_page,
        )
        return SubmissionVersionListResponse(
            data=versions,
            pagination=build_pagination(page, per_page, total),
            filters_applied=NoFilters(),
            sort=SortApplied(by='returned_at', order='desc'),
        )
    except NotFoundError as exc:
        raise domain_error(HTTPStatus.NOT_FOUND, exc) from exc


@router.get(
    '/{id}/submission-versions/{run_number}',
    response_model=SubmissionVersionResponse,
    status_code=HTTPStatus.OK,
)
async def get_submission_version(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    run_number: int = Path(..., ge=1),
):
    try:
        return await get_returned_submission_version(
            session, id, run_number, current_user.id
        )
    except NotFoundError as exc:
        raise domain_error(HTTPStatus.NOT_FOUND, exc) from exc


@router.get(
    '/{id}/timeline',
    response_model=TimelineListResponse,
    status_code=HTTPStatus.OK,
)
async def get_process_timeline(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    p_stmt = select(ProcessInstance).where(
        ProcessInstance.id == id, ProcessInstance.deleted_at.is_(None)
    )
    visibility = await process_visibility_clause(session, current_user.id)
    if visibility is not None:
        p_stmt = p_stmt.where(visibility)
    p = (await session.execute(p_stmt)).scalar_one_or_none()
    if not p:
        raise http_error(HTTPStatus.NOT_FOUND, 'Processo não encontrado.')

    events_stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.process_instance_id == id,
            AuditEvent.deleted_at.is_(None),
        )
        .order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
    )
    events = list((await session.execute(events_stmt)).scalars().all())
    # O filtro de visibilidade roda em Python: a página vem depois dele,
    # para o total refletir só o que o usuário vê (Spec 033, R2).
    events, total = paginate_items(
        await _visible_events(session, current_user, id, events),
        page,
        per_page,
    )

    return TimelineListResponse(
        data=[
            TimelineEvent(
                id=e.id,
                event_type=e.event_type,
                user_id=e.user_id,
                activity_run_id=e.activity_run_id,
                occurred_at=e.occurred_at,
                context_data=e.context_data,
            )
            for e in events
        ],
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='occurred_at', order='asc'),
    )
