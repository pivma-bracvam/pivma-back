"""Recebimento de amostras e inconformidades (Spec 040).

O laboratório participante lista e registra os próprios frascos; o Grupo de
Seleção de Amostras lista e decide as inconformidades. As regras de acesso
vivem em ``sample_receipt_service``.
"""

from http import HTTPStatus
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, UploadFile
from fastapi.responses import FileResponse

from pivma.core import sample_receipt_service as svc
from pivma.core.listing import (
    PageQuery,
    PerPageQuery,
    build_pagination,
    paginate_items,
)
from pivma.dependencies import (
    CurrentUser,
    Session,
    SettingsDependency,
    TrustedOrigin,
)
from pivma.routers.samples import _DOMAIN_ERRORS, _http_error  # noqa: PLC2701
from pivma.schemas import (
    NonconformityDecisionRequest,
    NonconformityFilters,
    NonconformityListResponse,
    NonconformityPublic,
    ReceiptPhoto,
    ReceiptVialFilters,
    ReceiptVialListResponse,
    SampleReceiptCheck,
    SampleReceiptCreate,
    SampleReceiptResult,
    SortApplied,
)

router = APIRouter(prefix='/processes', tags=['Sample Receipt'])


@router.get(
    '/{id}/sample-receipt/vials', response_model=ReceiptVialListResponse
)
async def list_receipt_vials(  # noqa: PLR0913, PLR0917
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    search: str | None = Query(default=None, min_length=1, max_length=8),
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    try:
        vials = await svc.list_vials(session, id, current_user.id, search)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    items, total = paginate_items(vials, page, per_page)
    return ReceiptVialListResponse(
        data=items,
        pagination=build_pagination(page, per_page, total),
        filters_applied=ReceiptVialFilters(search=search),
        sort=SortApplied(by='laboratory', order='asc'),
    )


@router.post(
    '/{id}/sample-receipt/vials/{code}/check',
    response_model=SampleReceiptCheck,
)
async def check_vial_receipt(  # noqa: PLR0913, PLR0917
    id: UUID,
    code: str,
    body: SampleReceiptCreate,
    session: Session,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    """Avisa, antes de confirmar, se o registro geraria inconformidade."""
    try:
        return await svc.check_receipt(
            session, id, code, current_user.id, body.model_dump()
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post(
    '/{id}/sample-receipt/vials/{code}',
    response_model=SampleReceiptResult,
    status_code=HTTPStatus.CREATED,
)
async def register_vial_receipt(  # noqa: PLR0913, PLR0917
    id: UUID,
    code: str,
    body: SampleReceiptCreate,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _origin: TrustedOrigin,
):
    try:
        return await svc.register_receipt(
            session, settings, id, code, current_user.id, body.model_dump()
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post(
    '/{id}/sample-receipt/vials/{code}/photos',
    response_model=ReceiptPhoto,
    status_code=HTTPStatus.CREATED,
)
async def attach_receipt_photo(  # noqa: PLR0913, PLR0917
    id: UUID,
    code: str,
    file: UploadFile,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
    _origin: TrustedOrigin,
):
    try:
        return await svc.add_photo(
            session, settings, id, code, current_user.id, file
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get('/{id}/sample-receipt/photos/{photo_id}')
async def download_receipt_photo(
    id: UUID,
    photo_id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: SettingsDependency,
):
    try:
        artifact, path = await svc.get_photo(
            session, settings, id, photo_id, current_user.id
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    meta = artifact.metadata_payload or {}
    return FileResponse(
        path=path,
        media_type=artifact.mime_type,
        filename=meta.get('original_filename') or artifact.name,
    )


@router.get(
    '/{id}/sample-receipt/nonconformities',
    response_model=NonconformityListResponse,
)
async def list_receipt_nonconformities(  # noqa: PLR0913, PLR0917
    id: UUID,
    session: Session,
    current_user: CurrentUser,
    status: Literal['open', 'resolved'] | None = Query(default=None),
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    try:
        items, total = await svc.list_nonconformities(
            session,
            id,
            current_user.id,
            status=status,
            page=page,
            per_page=per_page,
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return NonconformityListResponse(
        data=items,
        pagination=build_pagination(page, per_page, total),
        filters_applied=NonconformityFilters(status=status),
        sort=SortApplied(by='opened_at', order='asc'),
    )


@router.post(
    '/{id}/sample-receipt/nonconformities/{nonconformity_id}/decision',
    response_model=NonconformityPublic,
)
async def decide_receipt_nonconformity(  # noqa: PLR0913, PLR0917
    id: UUID,
    nonconformity_id: UUID,
    body: NonconformityDecisionRequest,
    session: Session,
    settings: SettingsDependency,
    current_user: CurrentUser,
    _origin: TrustedOrigin,
):
    try:
        return await svc.decide_nonconformity(
            session,
            settings,
            id,
            nonconformity_id,
            current_user.id,
            body.decision,
            body.justification,
            body.lab_guidance,
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
