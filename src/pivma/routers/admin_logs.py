from fastapi import APIRouter, Query

from pivma.ai.contracts import OperationalEventIndex, PipelineExecutionGroup
from pivma.core.log_service import log_query_service
from pivma.dependencies import AdminUser

router = APIRouter(prefix='/admin/logs', tags=['Admin Observability'])


@router.get(
    '/operational',
    response_model=list[OperationalEventIndex],
    summary='Consultar histórico do Índice Operacional',
)
async def get_operational_logs(
    admin_user: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    operation_type: str | None = Query(default=None),
):
    return log_query_service.get_operational_events(
        limit=limit,
        status=status,
        operation_type=operation_type,
    )


@router.get(
    '/ai',
    response_model=list[PipelineExecutionGroup],
    summary='Consultar histórico de etapas de IA agrupadas por pipeline',
)
async def get_ai_pipeline_logs(
    admin_user: AdminUser,
    correlation_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    return log_query_service.get_ai_pipeline_groups(
        correlation_id=correlation_id,
        limit=limit,
    )
