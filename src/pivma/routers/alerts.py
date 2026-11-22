"""Caixa de alerts do usuário (Spec 047).

Contrato em `specs/047-alerts/contracts/alerts-api.md`. Cada usuário vê e
marca só os próprios alerts; o de outro responde `404` (FR-016).
"""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter

from pivma.core import alert_service
from pivma.core.database.models import Alert
from pivma.core.errors import http_error
from pivma.core.listing import PageQuery, PerPageQuery, build_pagination
from pivma.dependencies import CurrentUser, Session, TrustedOrigin
from pivma.schemas import (
    AlertFilters,
    AlertItem,
    AlertListResponse,
    AlertReadAllResponse,
    AlertTarget,
    SortApplied,
)

router = APIRouter(prefix='/alerts', tags=['Alerts'])


def _item(alert: Alert) -> AlertItem:
    return AlertItem(
        id=alert.id,
        kind=alert.kind,
        target=AlertTarget(
            type=alert.target_type,
            process_id=alert.process_instance_id,
            id=alert.target_id,
        ),
        params=alert.params,
        read_at=alert.read_at,
        created_at=alert.created_at,
    )


@router.get('', response_model=AlertListResponse)
async def list_alerts(
    session: Session,
    current_user: CurrentUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
    unread: bool | None = None,
):
    items, total = await alert_service.list_alerts(
        session, current_user.id, unread=unread, page=page, per_page=per_page
    )
    return AlertListResponse(
        data=[_item(alert) for alert in items],
        pagination=build_pagination(page, per_page, total),
        filters_applied=AlertFilters(unread=unread),
        sort=SortApplied(by='created_at', order='desc'),
        unread_count=await alert_service.unread_count(
            session, current_user.id
        ),
    )


# Antes de `/{alert_id}/read`, para `read-all` não ser lido como id.
@router.post('/read-all', response_model=AlertReadAllResponse)
async def mark_all_alerts_read(
    session: Session, current_user: CurrentUser, _: TrustedOrigin
):
    updated = await alert_service.mark_all_read(session, current_user.id)
    return AlertReadAllResponse(updated=updated)


@router.post('/{alert_id}/read', response_model=AlertItem)
async def mark_alert_read(
    alert_id: UUID,
    session: Session,
    current_user: CurrentUser,
    _: TrustedOrigin,
):
    alert = await alert_service.mark_read(session, current_user.id, alert_id)
    if alert is None:
        raise http_error(HTTPStatus.NOT_FOUND, 'Alert não encontrado.')
    return _item(alert)
