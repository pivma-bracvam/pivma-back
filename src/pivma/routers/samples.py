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
from pivma.core.errors import api_error, domain_error
from pivma.core.listing import PageQuery, PerPageQuery, build_pagination
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
    NoFilters,
    SampleCompletionResponse,
    SampleLabelListResponse,
    SampleSubstance,
    SampleSubstanceCreate,
    SampleSubstanceList,
    SampleSubstanceUpdate,
    SortApplied,
)

router = APIRouter(prefix='/processes', tags=['Samples'])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AttachmentError):
        return _attachment_http_error(exc)
    if isinstance(exc, NotFoundError):
        return domain_error(HTTPStatus.NOT_FOUND, exc)
    if isinstance(exc, AuthorizationError):
        return domain_error(HTTPStatus.FORBIDDEN, exc)
    if isinstance(exc, ConflictError):
        return api_error(
            HTTPStatus.CONFLICT, exc.code or 'invalid_transition', str(exc)
        )
    if isinstance(exc, ValidationError):
        return api_error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            exc.code or 'validation_error',
            str(exc),
            **getattr(exc, 'extra', {}),
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


@router.get('/{id}/samples/labels', response_model=SampleLabelListResponse)
async def list_sample_labels(  # noqa: PLR0913, PLR0917
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    try:
        labels, total = await svc.list_labels(
            session,
            settings,
            id,
            current_user.id,
            page=page,
            per_page=per_page,
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return SampleLabelListResponse(
        data=labels,
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='laboratory', order='asc'),
    )


@router.get('/{id}/samples/vials/{code}', response_model=BlindVial)
async def get_sample_vial(
    id: UUID, code: str, session: Session, current_user: CurrentUser
):
    try:
        return await svc.get_blind_vial(session, id, code, current_user.id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get(
    '/{id}/samples/vials/{code}/qr.svg',
    response_class=Response,
    responses={
        200: {
            'content': {'image/svg+xml': {}},
            'description': 'Imagem SVG do QR do frasco, para a etiqueta.',
        }
    },
)
async def get_sample_vial_qr(
    id: UUID,
    code: str,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
):
    try:
        svg = await svc.vial_qr_svg(
            session, settings, id, code, current_user.id
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    # A imagem só muda se o código mudar; a sessão continua exigida.
    return Response(
        content=svg,
        media_type='image/svg+xml',
        headers={'Cache-Control': 'private, max-age=3600'},
    )


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
