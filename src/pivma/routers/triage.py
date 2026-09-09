from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException

from pivma.core.process_engine import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    execute_triage_decision,
    save_field_reviews,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    SaveFieldReviewsRequest,
    TriageDecisionRequest,
    TriageDecisionResponse,
)

router = APIRouter(prefix='/processes', tags=['Triage'])


@router.post(
    '/{id}/triage/reviews',
    status_code=HTTPStatus.OK,
)
async def submit_field_reviews(
    id: UUID,
    body: SaveFieldReviewsRequest,
    session: Session,
    current_user: CurrentUser,
):
    try:
        reviews_dicts = [r.model_dump() for r in body.reviews]
        await save_field_reviews(
            session=session,
            process_id=id,
            reviews_list=reviews_dicts,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e
    except AuthorizationError as e:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail=str(e)
        ) from e

    return {'message': 'Avaliações de campo registradas com sucesso.'}


@router.post(
    '/{id}/triage/decision',
    response_model=TriageDecisionResponse,
    status_code=HTTPStatus.OK,
)
async def submit_triage_decision(
    id: UUID,
    body: TriageDecisionRequest,
    session: Session,
    current_user: CurrentUser,
):
    try:
        decision, new_status, next_run = await execute_triage_decision(
            session=session,
            process_id=id,
            outcome=body.outcome,
            justification=body.justification,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e
    except AuthorizationError as e:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail=str(e)
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail=str(e)
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    return TriageDecisionResponse(
        process_id=id,
        new_process_status=new_status,
        decision_id=decision.id,
        outcome=decision.outcome,
        next_activity_run=next_run,
    )
