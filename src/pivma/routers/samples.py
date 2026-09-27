"""Definição e Preparação das Amostras — estudo cego (Spec 031).

Só o Grupo de Seleção de Amostras do processo acessa estas rotas; a regra
vive em ``sample_service._sample_activity``.
"""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from pivma.core import sample_service as svc
from pivma.core.attachment_service import (
    AttachmentError,
    attachment_abspath,
    remove_file_best_effort,
)
from pivma.core.process_engine import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    SettingsDependency,
    TrustedOrigin,
)
from pivma.routers.forms import _attachment_http_error  # noqa: PLC2701
from pivma.schemas import (
    BlindVial,
    SampleCompletionResponse,
    SampleLabel,
    SampleSubstance,
    SampleSubstanceCreate,
    SampleSubstanceList,
    SampleSubstanceUpdate,
)

router = APIRouter(prefix='/processes', tags=['Samples'])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AttachmentError):
        return _attachment_http_error(exc)
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(exc))
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                'code': getattr(exc, 'code', 'invalid_transition'),
                'message': str(exc),
            },
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                'code': getattr(exc, 'code', 'validation_error'),
                'message': str(exc),
                **getattr(exc, 'extra', {}),
            },
        )
    raise exc


_DOMAIN_ERRORS = (
    AttachmentError,
    NotFoundError,
    AuthorizationError,
    ConflictError,
    ValidationError,
)


@router.get('/{id}/samples', response_model=SampleSubstanceList)
async def list_samples(id: UUID, session: Session, current_user: CurrentUser):
    try:
        return await svc.list_substances(session, id, current_user.id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get('/{id}/samples/labels', response_model=list[SampleLabel])
async def list_sample_labels(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
):
    try:
        return await svc.list_labels(session, settings, id, current_user.id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get('/{id}/samples/vials/{code}', response_model=BlindVial)
async def get_sample_vial(
    id: UUID, code: str, session: Session, current_user: CurrentUser
):
    try:
        return await svc.get_blind_vial(session, id, code, current_user.id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post(
    '/{id}/samples',
    response_model=SampleSubstance,
    status_code=HTTPStatus.CREATED,
)
async def create_sample(
    id: UUID,
    body: SampleSubstanceCreate,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    try:
        return await svc.create_substance(
            session, id, current_user.id, body.model_dump()
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.patch('/{id}/samples/{substance_id}', response_model=SampleSubstance)
async def update_sample(  # noqa: PLR0913, PLR0917
    id: UUID,
    substance_id: UUID,
    body: SampleSubstanceUpdate,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    try:
        return await svc.update_substance(
            session,
            id,
            substance_id,
            current_user.id,
            body.model_dump(exclude_unset=True),
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.delete(
    '/{id}/samples/{substance_id}', status_code=HTTPStatus.NO_CONTENT
)
async def delete_sample(  # noqa: PLR0913, PLR0917
    id: UUID,
    substance_id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _origin: TrustedOrigin,
):
    try:
        removed = await svc.delete_substance(
            session, id, substance_id, current_user.id
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    if removed:
        remove_file_best_effort(attachment_abspath(settings, removed))
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.post('/{id}/samples/complete', response_model=SampleCompletionResponse)
async def complete_samples(
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    try:
        return await svc.complete_sample_definition(
            session, id, current_user.id
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.put('/{id}/samples/{substance_id}/sds', response_model=SampleSubstance)
async def upload_sample_sds(  # noqa: PLR0913, PLR0917
    id: UUID,
    substance_id: UUID,
    file: UploadFile,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _origin: TrustedOrigin,
):
    try:
        return await svc.upload_sds(
            session, settings, id, substance_id, current_user.id, file
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get('/{id}/samples/{substance_id}/sds')
async def download_sample_sds(
    id: UUID,
    substance_id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
):
    try:
        artifact, path = await svc.get_sds(
            session, settings, id, substance_id, current_user.id
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    meta = artifact.metadata_payload or {}
    return FileResponse(
        path=path,
        media_type='application/pdf',
        filename=meta.get('original_filename') or artifact.name,
        headers={'ETag': f'"{artifact.checksum_sha256 or ""}"'},
    )
