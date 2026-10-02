"""Dispensa e reabertura de execuções por laboratório (Spec 036).

Só o gestor do processo (`group_manager` efetivo, Admin, BraCVAM) usa estas
rotas; quem não vê o processo recebe 404.
"""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from pivma.core.authorization import (
    has_platform_wide_access,
    is_effective_group_manager,
)
from pivma.core.database.models import (
    ActivityInstance,
    Phase,
    ProcessInstance,
)
from pivma.core.errors import api_error, domain_error, http_error
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
    process_visibility_clause,
    reopen_laboratory_run,
    waive_laboratory,
)
from pivma.core.references import laboratory_refs, user_refs
from pivma.dependencies import CurrentUser, Session, TrustedOrigin
from pivma.schemas import (
    LaboratoryRunReopened,
    LaboratoryRunReopenRequest,
    LaboratoryWaiverCreate,
    LaboratoryWaiverPublic,
    PhaseRef,
)

router = APIRouter(prefix='/processes', tags=['Laboratory Runs'])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return domain_error(HTTPStatus.NOT_FOUND, exc)
    if isinstance(exc, ConflictError):
        return api_error(
            HTTPStatus.CONFLICT, exc.code or 'invalid_transition', str(exc)
        )
    if isinstance(exc, ValidationError):
        return api_error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            exc.code or 'validation_error',
            str(exc),
        )
    raise exc


async def _require_process_manager(session, user_id, process_id) -> None:
    """404 sem visão do processo; 403 sem ser gestor dele (FR-017, FR-022)."""
    stmt = select(ProcessInstance.id).where(ProcessInstance.id == process_id)
    visibility = await process_visibility_clause(session, user_id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    if await session.scalar(stmt) is None:
        raise http_error(HTTPStatus.NOT_FOUND, 'Processo não encontrado.')
    if not (
        await has_platform_wide_access(session, user_id)
        or await is_effective_group_manager(session, user_id, process_id)
    ):
        raise http_error(
            HTTPStatus.FORBIDDEN, 'Só o gestor do processo pode fazer isso.'
        )


@router.post(
    '/{id}/phases/{phase_key}/laboratory-waivers',
    response_model=LaboratoryWaiverPublic,
    status_code=HTTPStatus.CREATED,
)
async def create_laboratory_waiver(  # noqa: PLR0913, PLR0917
    id: UUID,
    phase_key: str,
    body: LaboratoryWaiverCreate,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    await _require_process_manager(session, current_user.id, id)
    try:
        waiver, waived_keys = await waive_laboratory(
            session,
            id,
            phase_key,
            body.laboratory_id,
            body.reason,
            current_user.id,
        )
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise _http_error(exc) from exc
    await session.commit()

    phase = await session.get(Phase, waiver.phase_id)
    laboratory = (await laboratory_refs(session, [waiver.laboratory_id]))[
        waiver.laboratory_id
    ]
    author = (await user_refs(session, [current_user.id]))[current_user.id]
    return LaboratoryWaiverPublic(
        id=waiver.id,
        process_id=id,
        phase=PhaseRef(key=phase.key, order=phase.order_index),
        laboratory=laboratory,
        reason=waiver.reason,
        waived_by=author,
        created_at=waiver.created_at,
        waived_activity_keys=waived_keys,
    )


@router.post(
    '/{id}/activities/{activity_key}/laboratories/{laboratory_id}/reopen',
    response_model=LaboratoryRunReopened,
    status_code=HTTPStatus.CREATED,
)
async def reopen_laboratory_execution(  # noqa: PLR0913, PLR0917
    id: UUID,
    activity_key: str,
    laboratory_id: UUID,
    body: LaboratoryRunReopenRequest,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    await _require_process_manager(session, current_user.id, id)
    try:
        run, reblocked = await reopen_laboratory_run(
            session,
            id,
            activity_key,
            laboratory_id,
            body.reason,
            current_user.id,
        )
    except (NotFoundError, ConflictError, ValidationError) as exc:
        raise _http_error(exc) from exc
    await session.commit()

    act_status = await session.scalar(
        select(ActivityInstance.status).where(
            ActivityInstance.id == run.activity_instance_id
        )
    )
    laboratory = (await laboratory_refs(session, [laboratory_id]))[
        laboratory_id
    ]
    return LaboratoryRunReopened(
        activity_key=activity_key,
        laboratory=laboratory,
        previous_run_number=run.run_number - 1,
        run_number=run.run_number,
        activity_status=act_status,
        reblocked_activity_keys=reblocked,
    )
