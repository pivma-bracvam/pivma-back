"""Rotas de configuração de avaliações por IA (Spec 013, US1/US5/US6)."""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from pivma.core import evaluation_service as svc
from pivma.core.authorization import (
    AI_EVALUATIONS_MANAGE,
    AI_EVALUATIONS_READ,
)
from pivma.core.database.models import EvaluationVersion, User
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from pivma.dependencies import (
    ModelProviderDep,
    Session,
    TrustedOrigin,
    require_permission,
)
from pivma.schemas import (
    AgreementMetricsResponse,
    AssignmentsResponse,
    CreateEvaluationRequest,
    EvaluableFieldsResponse,
    EvaluationDefinitionPage,
    EvaluationDefinitionResponse,
    EvaluationTestRequest,
    EvaluationTestResponse,
    EvaluationVersionResponse,
    EvaluationVersionSummary,
    PatchEvaluationVersionRequest,
    PublishResponse,
    ReferenceCreateRequest,
    ReferenceImpactResponse,
    ReferencePublic,
    ReplaceAssignmentsRequest,
    SuggestCriteriaRequest,
    SuggestCriteriaResponse,
)

router = APIRouter(prefix='/ai-evaluations', tags=['AI Evaluations'])
templates_router = APIRouter(prefix='/form-templates', tags=['AI Evaluations'])

ReadUser = Annotated[User, Depends(require_permission(AI_EVALUATIONS_READ))]
ManageUser = Annotated[
    User, Depends(require_permission(AI_EVALUATIONS_MANAGE))
]
MAX_LIMIT = 100


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        status = HTTPStatus.NOT_FOUND
    elif isinstance(exc, ConflictError):
        status = HTTPStatus.CONFLICT
    elif isinstance(exc, ValidationError):
        status = HTTPStatus.UNPROCESSABLE_ENTITY
    else:  # pragma: no cover - defensive
        raise exc
    raise HTTPException(status_code=status, detail=str(exc)) from exc


def _version_summary(version: EvaluationVersion) -> EvaluationVersionSummary:
    return EvaluationVersionSummary(
        version_number=version.version_number,
        status=version.status,
        criteria_count=len(svc._active_criteria(version)),
        test_run_count=version.test_run_count,
        published_at=version.published_at,
    )


def _version_response(
    version: EvaluationVersion,
) -> EvaluationVersionResponse:
    return EvaluationVersionResponse(
        version_number=version.version_number,
        status=version.status,
        objective=version.objective,
        references=version.references or [],
        test_run_count=version.test_run_count,
        published_at=version.published_at,
        criteria=[
            {
                'id': c.id,
                'order_index': c.order_index,
                'statement': c.statement,
                'check_type': c.check_type,
                'polarity': c.polarity,
                'required_evidence': c.required_evidence,
                'severity': c.severity,
                'on_missing_info': c.on_missing_info,
                'recommendation_hint': c.recommendation_hint,
            }
            for c in svc._active_criteria(version)
        ],
    )


# --------------------------------------------------------------------------
# Biblioteca
# --------------------------------------------------------------------------


@router.get('', response_model=EvaluationDefinitionPage)
async def list_evaluations(
    session: Session,
    actor: ReadUser,
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
):
    del actor
    items = await svc.list_definitions(
        session, search=search, offset=offset, limit=limit
    )
    return EvaluationDefinitionPage(
        offset=offset,
        limit=limit,
        items=[
            {
                **item,
                'latest_version': (
                    _version_summary(item['latest_version'])
                    if item['latest_version'] is not None
                    else None
                ),
            }
            for item in items
        ],
    )


@router.post(
    '',
    status_code=HTTPStatus.CREATED,
    response_model=EvaluationDefinitionResponse,
)
async def create_evaluation(
    body: CreateEvaluationRequest,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        definition, version = await svc.create_definition(
            session,
            name=body.name,
            description=body.description,
            mode=body.mode,
            objective=body.objective,
            user_id=actor.id,
        )
    except (ConflictError, NotFoundError, ValidationError) as exc:
        _raise_http(exc)

    return EvaluationDefinitionResponse(
        id=definition.id,
        name=definition.name,
        slug=definition.slug,
        mode=definition.mode,
        description=definition.description,
        versions=[_version_summary(version)],
    )


@router.get(
    '/{definition_id:uuid}', response_model=EvaluationDefinitionResponse
)
async def get_evaluation(
    definition_id: UUID, session: Session, actor: ReadUser
):
    del actor
    try:
        definition, versions = await svc.get_definition_detail(
            session, definition_id
        )
    except NotFoundError as exc:
        _raise_http(exc)

    return EvaluationDefinitionResponse(
        id=definition.id,
        name=definition.name,
        slug=definition.slug,
        mode=definition.mode,
        description=definition.description,
        versions=[_version_summary(v) for v in versions],
    )


@router.delete('/{definition_id:uuid}', status_code=HTTPStatus.NO_CONTENT)
async def delete_evaluation(
    definition_id: UUID,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
    force: bool = False,
):
    del origin
    try:
        await svc.soft_delete_definition(
            session, definition_id, force=force, user_id=actor.id
        )
    except (NotFoundError, ConflictError) as exc:
        _raise_http(exc)


# --------------------------------------------------------------------------
# Assistente
# --------------------------------------------------------------------------


@router.post('/suggest-criteria', response_model=SuggestCriteriaResponse)
async def suggest_criteria(
    body: SuggestCriteriaRequest,
    provider: ModelProviderDep,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin, actor
    try:
        suggestions = await svc.suggest_criteria(
            provider,
            objective=body.objective,
            target_type=body.target_type,
        )
    except Exception as exc:  # noqa: BLE001 - provider failure -> 503
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail='Serviço de IA indisponível.',
        ) from exc
    return SuggestCriteriaResponse(suggestions=suggestions)


# --------------------------------------------------------------------------
# Referências normativas
# --------------------------------------------------------------------------


@router.get('/references', response_model=list[ReferencePublic])
async def list_references(session: Session, actor: ReadUser):
    del actor
    return await svc.list_references(session)


@router.post(
    '/references',
    status_code=HTTPStatus.CREATED,
    response_model=ReferencePublic,
)
async def create_reference(
    body: ReferenceCreateRequest,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        return await svc.create_reference(
            session,
            identifier=body.identifier,
            label=body.label,
            version_label=body.version_label,
            reference_date=body.reference_date,
            user_id=actor.id,
        )
    except ConflictError as exc:
        _raise_http(exc)


@router.get(
    '/references/{reference_id:uuid}/impact',
    response_model=ReferenceImpactResponse,
)
async def get_reference_impact(
    reference_id: UUID, session: Session, actor: ReadUser
):
    del actor
    return await svc.reference_impact(session, reference_id)


# --------------------------------------------------------------------------
# Versões
# --------------------------------------------------------------------------


@router.get(
    '/{definition_id:uuid}/versions/{number:int}',
    response_model=EvaluationVersionResponse,
)
async def get_version(
    definition_id: UUID,
    number: int,
    session: Session,
    actor: ReadUser,
):
    del actor
    try:
        version = await svc.get_version(session, definition_id, number)
    except NotFoundError as exc:
        _raise_http(exc)
    return _version_response(version)


@router.patch(
    '/{definition_id:uuid}/versions/{number:int}',
    response_model=EvaluationVersionResponse,
)
async def patch_version(  # noqa: PLR0913, PLR0917
    definition_id: UUID,
    number: int,
    body: PatchEvaluationVersionRequest,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        version = await svc.patch_draft_version(
            session,
            definition_id,
            number,
            objective=body.objective,
            reference_ids=body.references,
            criteria=(
                [c.model_dump() for c in body.criteria]
                if body.criteria is not None
                else None
            ),
            user_id=actor.id,
        )
    except (NotFoundError, ConflictError, ValidationError) as exc:
        _raise_http(exc)
    return _version_response(version)


@router.post(
    '/{definition_id:uuid}/versions',
    status_code=HTTPStatus.CREATED,
    response_model=EvaluationVersionResponse,
)
async def create_version(
    definition_id: UUID,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        version = await svc.create_new_version(
            session, definition_id, actor.id
        )
    except (NotFoundError, ConflictError) as exc:
        _raise_http(exc)
    return _version_response(version)


@router.post(
    '/{definition_id:uuid}/versions/{number:int}/publish',
    response_model=PublishResponse,
)
async def publish_version(
    definition_id: UUID,
    number: int,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        version, warning = await svc.publish_version(
            session, definition_id, number, actor.id
        )
    except (NotFoundError, ConflictError, ValidationError) as exc:
        _raise_http(exc)
    return PublishResponse(
        version_number=version.version_number,
        status=version.status,
        published_at=version.published_at,
        test_warning=warning,
    )


@router.post(
    '/{definition_id:uuid}/versions/{number:int}/test',
    response_model=EvaluationTestResponse,
)
async def test_version(  # noqa: PLR0913, PLR0917
    definition_id: UUID,
    number: int,
    body: EvaluationTestRequest,
    session: Session,
    provider: ModelProviderDep,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        return await svc.run_test(
            session,
            provider,
            definition_id,
            number,
            sample_content=body.sample_content,
            user_id=actor.id,
        )
    except (NotFoundError, ConflictError) as exc:
        _raise_http(exc)
    except Exception as exc:  # noqa: BLE001 - provider failure -> 503
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail='Serviço de IA indisponível.',
        ) from exc


# --------------------------------------------------------------------------
# Associações
# --------------------------------------------------------------------------


@templates_router.get(
    '/{template_key}/evaluation-assignments',
    response_model=AssignmentsResponse,
)
async def list_assignments(
    template_key: str, session: Session, actor: ReadUser
):
    del actor
    try:
        assignments = await svc.get_assignments(session, template_key)
    except NotFoundError as exc:
        _raise_http(exc)
    return AssignmentsResponse(
        template_key=template_key, assignments=assignments
    )


@templates_router.put(
    '/{template_key}/evaluation-assignments',
    response_model=AssignmentsResponse,
)
async def replace_assignments(
    template_key: str,
    body: ReplaceAssignmentsRequest,
    session: Session,
    actor: ManageUser,
    origin: TrustedOrigin,
):
    del origin
    try:
        assignments = await svc.replace_assignments(
            session,
            template_key,
            [a.model_dump() for a in body.assignments],
            actor.id,
        )
    except (NotFoundError, ValidationError, ConflictError) as exc:
        _raise_http(exc)
    return AssignmentsResponse(
        template_key=template_key, assignments=assignments
    )


@templates_router.get(
    '/{template_key}/evaluable-fields',
    response_model=EvaluableFieldsResponse,
)
async def list_evaluable_fields(
    template_key: str, session: Session, actor: ReadUser
):
    del actor
    try:
        fields = await svc.get_evaluable_fields(session, template_key)
    except NotFoundError as exc:
        _raise_http(exc)
    return EvaluableFieldsResponse(fields=fields)


@router.get('/agreement-metrics', response_model=AgreementMetricsResponse)
async def agreement_metrics(
    session: Session,
    actor: ReadUser,
    check_type: str | None = None,
):
    del actor
    return await svc.agreement_metrics(session, check_type=check_type)
