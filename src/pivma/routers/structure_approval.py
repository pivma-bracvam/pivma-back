"""Homologação da estrutura do estudo (Spec 042).

Admin e BraCVAM veem o painel; só o BraCVAM decide. As regras de acesso
vivem em ``structure_approval_service``.
"""

from uuid import UUID

from fastapi import APIRouter

from pivma.core import structure_approval_service as svc
from pivma.dependencies import CurrentUser, Session, TrustedOrigin
from pivma.routers.samples import _DOMAIN_ERRORS, _http_error  # noqa: PLC2701
from pivma.schemas import (
    StructureApprovalPanel,
    StructureDecisionRequest,
    StructureDecisionResponse,
)

router = APIRouter(prefix='/processes', tags=['Structure Approval'])


@router.get('/{id}/structure-approval', response_model=StructureApprovalPanel)
async def get_structure_approval(
    id: UUID, session: Session, current_user: CurrentUser
):
    try:
        return await svc.get_panel(session, id, current_user.id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post(
    '/{id}/structure-approval/decision',
    response_model=StructureDecisionResponse,
)
async def decide_structure_approval(
    id: UUID,
    body: StructureDecisionRequest,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    rejected = (
        [point.model_dump() for point in body.rejected_points]
        if body.rejected_points is not None
        else None
    )
    try:
        return await svc.execute_structure_decision(
            session,
            id,
            current_user.id,
            body.outcome,
            body.justification,
            rejected,
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
