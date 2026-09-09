from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from pivma.ai.contracts import OperationalEventIndex, PipelineExecutionGroup
from pivma.core.log_service import log_query_service
from pivma.core.sse_broadcaster import broadcaster
from pivma.dependencies import AdminUser

router = APIRouter(prefix="/admin/logs", tags=["Admin Observability"])


@router.get(
    "/operational/stream",
    summary="Stream em tempo real do Índice Operacional (SSE)",
)
async def stream_operational_logs(admin_user: AdminUser):
    return StreamingResponse(
        broadcaster.subscribe_operational(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/operational",
    response_model=list[OperationalEventIndex],
    summary="Consultar histórico do Índice Operacional",
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
    "/ai/stream",
    summary="Stream em tempo real de eventos de IA (SSE)",
)
async def stream_ai_logs(admin_user: AdminUser):
    return StreamingResponse(
        broadcaster.subscribe_ai(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/ai",
    response_model=list[PipelineExecutionGroup],
    summary="Consultar histórico de etapas de IA agrupadas por pipeline",
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
