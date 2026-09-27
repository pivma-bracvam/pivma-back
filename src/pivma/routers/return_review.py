"""Revisão do retorno ao proponente (Spec 030, US4)."""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter

from pivma.core import return_review_service as svc
from pivma.core.errors import api_error, domain_error
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
        raise domain_error(HTTPStatus.NOT_FOUND, e) from e


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
        raise domain_error(HTTPStatus.NOT_FOUND, e) from e
    except AuthorizationError as e:
        raise domain_error(HTTPStatus.FORBIDDEN, e) from e
    except ConflictError as e:
        raise api_error(
            HTTPStatus.CONFLICT, 'invalid_transition', str(e)
        ) from e
    except ValidationError as e:
        raise domain_error(HTTPStatus.UNPROCESSABLE_ENTITY, e) from e
