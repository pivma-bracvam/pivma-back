"""Catálogo de templates de coleta de dados (Spec 041, issue #26).

Toda rota exige ``collection_templates.manage``; as escritas exigem origem
confiável. As regras vivem em ``core/collection_template_service.py``.
"""

from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from pivma.core import collection_template_service as svc
from pivma.core.authorization import COLLECTION_TEMPLATES_MANAGE
from pivma.core.database.models import (
    CollectionTemplate,
    CollectionTemplateColumn,
    User,
)
from pivma.core.errors import domain_error
from pivma.core.listing import (
    PageQuery,
    PerPageQuery,
    build_pagination,
    paginate_query,
)
from pivma.core.process_engine import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from pivma.dependencies import Session, TrustedOrigin, require_permission
from pivma.schemas import (
    CollectionTemplateColumnCreate,
    CollectionTemplateColumnPublic,
    CollectionTemplateColumnUpdate,
    CollectionTemplateCreate,
    CollectionTemplateListResponse,
    CollectionTemplatePublic,
    CollectionTemplateSummary,
    CollectionTemplateUpdate,
    NoFilters,
    SortApplied,
)

router = APIRouter(
    prefix='/collection-templates', tags=['collection-templates']
)
CatalogManager = Annotated[
    User, Depends(require_permission(COLLECTION_TEMPLATES_MANAGE))
]
_DOMAIN_ERRORS = (NotFoundError, ConflictError, ValidationError)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return domain_error(HTTPStatus.NOT_FOUND, exc)
    if isinstance(exc, ConflictError):
        return domain_error(HTTPStatus.CONFLICT, exc)
    return domain_error(HTTPStatus.UNPROCESSABLE_ENTITY, exc)


def _summary_fields(template: CollectionTemplate, locked: bool) -> dict:
    return {
        'id': template.id,
        'name': template.name,
        'description': template.description,
        'min_experiments': template.min_experiments,
        'min_replicates': template.min_replicates,
        'locked': locked,
        'created_by': template.created_by,
        'created_at': template.created_at,
        'updated_by': template.updated_by,
        'updated_at': template.updated_at,
    }


def _column_public(
    column: CollectionTemplateColumn,
) -> CollectionTemplateColumnPublic:
    return CollectionTemplateColumnPublic(
        id=column.id,
        key=column.key,
        label=column.label,
        type=column.column_type,
        required=column.required,
        options=column.options,
        position=column.position,
    )


async def _template_public(
    session: Session, template: CollectionTemplate
) -> CollectionTemplatePublic:
    locked = template.id in await svc.locked_template_ids(
        session, [template.id]
    )
    columns = await svc.active_columns(session, template.id)
    return CollectionTemplatePublic(
        **_summary_fields(template, locked),
        columns=[_column_public(column) for column in columns],
    )


@router.get('', response_model=CollectionTemplateListResponse)
async def list_collection_templates(
    session: Session,
    _: CatalogManager,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    items, total = await paginate_query(
        session,
        select(CollectionTemplate),
        order_by=(func.lower(CollectionTemplate.name), CollectionTemplate.id),
        page=page,
        per_page=per_page,
    )
    locked = await svc.locked_template_ids(session, [t.id for t in items])
    return CollectionTemplateListResponse(
        data=[
            CollectionTemplateSummary(**_summary_fields(t, t.id in locked))
            for t in items
        ],
        pagination=build_pagination(page, per_page, total),
        filters_applied=NoFilters(),
        sort=SortApplied(by='name', order='asc'),
    )


@router.post(
    '',
    response_model=CollectionTemplatePublic,
    status_code=HTTPStatus.CREATED,
)
async def create_collection_template(
    payload: CollectionTemplateCreate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    template = await svc.create_template(
        session, actor.id, payload.model_dump()
    )
    return await _template_public(session, template)


@router.get('/{template_id}', response_model=CollectionTemplatePublic)
async def read_collection_template(
    template_id: UUID, session: Session, _: CatalogManager
):
    try:
        template = await svc.get_template(session, template_id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return await _template_public(session, template)


@router.patch('/{template_id}', response_model=CollectionTemplatePublic)
async def update_collection_template(
    template_id: UUID,
    payload: CollectionTemplateUpdate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    try:
        template = await svc.update_template(
            session,
            template_id,
            actor.id,
            payload.model_dump(exclude_unset=True),
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return await _template_public(session, template)


@router.post(
    '/{template_id}/columns',
    response_model=CollectionTemplateColumnPublic,
    status_code=HTTPStatus.CREATED,
)
async def add_collection_template_column(
    template_id: UUID,
    payload: CollectionTemplateColumnCreate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    try:
        column = await svc.add_column(
            session, template_id, actor.id, payload.model_dump()
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return _column_public(column)


@router.patch(
    '/{template_id}/columns/{column_id}',
    response_model=CollectionTemplateColumnPublic,
)
async def update_collection_template_column(  # noqa: PLR0913, PLR0917
    template_id: UUID,
    column_id: UUID,
    payload: CollectionTemplateColumnUpdate,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
):
    try:
        column = await svc.update_column(
            session,
            template_id,
            column_id,
            actor.id,
            payload.model_dump(exclude_unset=True),
        )
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return _column_public(column)


@router.delete(
    '/{template_id}/columns/{column_id}',
    status_code=HTTPStatus.NO_CONTENT,
)
async def delete_collection_template_column(
    template_id: UUID,
    column_id: UUID,
    session: Session,
    actor: CatalogManager,
    _: TrustedOrigin,
) -> Response:
    try:
        await svc.delete_column(session, template_id, column_id, actor.id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get(
    '/{template_id}/file',
    response_class=Response,
    responses={
        HTTPStatus.OK: {
            'description': 'Arquivo-modelo só com o cabeçalho',
            'content': {svc.CSV_MEDIA_TYPE: {}, svc.XLSX_MEDIA_TYPE: {}},
        }
    },
)
async def download_collection_template_file(
    template_id: UUID,
    session: Session,
    _: CatalogManager,
    format: Annotated[Literal['csv', 'xlsx'], Query()],
) -> Response:
    try:
        template = await svc.get_template(session, template_id)
    except _DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc
    header = svc.file_header(await svc.active_columns(session, template.id))
    if format == 'csv':
        content, media_type = svc.render_csv(header), svc.CSV_MEDIA_TYPE
    else:
        content, media_type = svc.render_xlsx(header), svc.XLSX_MEDIA_TYPE
    return Response(
        content=content,
        media_type=media_type,
        headers={
            'Content-Disposition': (
                'attachment; '
                f'filename="template-coleta-{template.id}.{format}"'
            )
        },
    )
