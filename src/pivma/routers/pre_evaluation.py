"""Rotas de pré-avaliação por IA e intervenção direta (Spec 013, US2/US3)."""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException

from pivma.core import pre_evaluation_service as svc
from pivma.core.authorization import (
    TRIAGE_REVIEW,
    has_permission,
    is_active_effective_proponent,
)
from pivma.core.database.models import EvaluationRun
from pivma.core.process_engine import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    get_current_activity_run,
)
from pivma.dependencies import AdminUser, CurrentUser, Session, TrustedOrigin
from pivma.schemas import (
    DirectReviewRequestBody,
    DirectReviewResponse,
    PreEvaluationResponse,
    ReviewerFeedbackRequest,
    ReviewerFeedbackResponse,
)

router = APIRouter(prefix='/processes', tags=['AI Pre-Evaluation'])
admin_router = APIRouter(
    prefix='/admin/pre-evaluations', tags=['AI Pre-Evaluation']
)

STALE_MINUTES = svc.STALE_MINUTES


async def _ensure_can_read(
    session: Session, process_id: UUID, user_id: UUID
) -> None:
    """Ler a pré-avaliação exige ver a submissão (Spec 030, FR-017)."""
    try:
        await get_current_activity_run(
            session, process_id, 'proposal_submission', user_id, 'view'
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e


@router.get('/{id}/pre-evaluation', response_model=PreEvaluationResponse)
async def get_pre_evaluation(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    run_id: UUID | None = None,
):
    await _ensure_can_read(session, id, current_user.id)
    try:
        return await svc.get_pre_evaluation(session, id, run_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e


@router.post(
    '/{id}/submission/direct-review', response_model=DirectReviewResponse
)
async def request_direct_review(
    id: UUID,
    body: DirectReviewRequestBody,
    session: Session,
    current_user: CurrentUser,
    origin: TrustedOrigin,
):
    del origin
    if not await is_active_effective_proponent(session, current_user.id, id):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Apenas o proponente pode solicitar intervenção direta.',
        )
    try:
        request = await svc.request_direct_review(
            session, id, current_user.id, body.justification
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e

    return DirectReviewResponse(
        # Spec 030 (FR-006): só o ciclo de vida, nunca a posição no fluxo.
        process_status='OPEN',
        direct_review_request_id=request.id,
    )


@router.post(
    '/{id}/pre-evaluation/{run_id}/feedback',
    response_model=ReviewerFeedbackResponse,
)
async def record_feedback(  # noqa: PLR0913, PLR0917
    id: UUID,
    run_id: UUID,
    body: ReviewerFeedbackRequest,
    session: Session,
    current_user: CurrentUser,
    origin: TrustedOrigin,
):
    del origin
    if not await has_permission(session, current_user.id, TRIAGE_REVIEW):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Apenas o BraCVAM registra feedback da pré-avaliação.',
        )
    try:
        recorded = await svc.record_feedback(
            session,
            id,
            run_id,
            current_user.id,
            [item.model_dump() for item in body.items],
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail=str(e)
        ) from e
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e
    return ReviewerFeedbackResponse(recorded=recorded)


@admin_router.post('/{run_id}/retry', status_code=HTTPStatus.ACCEPTED)
async def retry_pre_evaluation(
    run_id: UUID,
    session: Session,
    actor: AdminUser,
    origin: TrustedOrigin,
    background_tasks: BackgroundTasks,
):
    del actor, origin
    run = await session.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Execução não encontrada.'
        )
    try:
        new_run = await svc.retry_run(session, run_id, run.created_by)
    except (ConflictError, AuthorizationError) as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e
    background_tasks.add_task(svc.run_pre_evaluation, new_run.id)
    return {'new_run_id': str(new_run.id), 'status': new_run.status}
