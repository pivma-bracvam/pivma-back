"""Revisão do retorno ao proponente (Spec 030, US4)."""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException

from pivma.core import return_review_service as svc
from pivma.core.process_engine import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from pivma.dependencies import CurrentUser, Session, TrustedOrigin
from pivma.schemas import (
    ReturnReviewDecisionRequest,
    ReturnReviewDecisionResponse,
    ReturnReviewResponse,
)

router = APIRouter(prefix='/processes', tags=['Return Review'])


@router.get('/{id}/return-review', response_model=ReturnReviewResponse)
async def get_return_review(
    id: UUID, session: Session, current_user: CurrentUser
):
    try:
        return await svc.get_open_return_review(session, id, current_user.id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail=str(e)
        ) from e


@router.post(
    '/{id}/return-review', response_model=ReturnReviewDecisionResponse
)
async def decide_return_review(
    id: UUID,
    body: ReturnReviewDecisionRequest,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    try:
        return await svc.decide_return_review(
            session, id, current_user.id, body.choice, body.justification
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
            status_code=HTTPStatus.CONFLICT,
            detail={'code': 'invalid_transition', 'message': str(e)},
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
