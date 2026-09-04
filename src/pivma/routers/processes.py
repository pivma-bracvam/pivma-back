from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from pivma.core.authorization import (
    active_proponent_process_scope,
    can_manage_participants,
)
from pivma.core.database.models import (
    AuditEvent,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.database.models import User as UserModel
from pivma.core.process_engine import (
    instantiate_process,
)
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    CreateProcessRequest,
    ProcessInstanceDetail,
    ProcessInstanceListResponse,
    ProcessTemplateDetail,
    ProcessTemplateSummary,
    ProcessTimelineResponse,
    TimelineEvent,
)

router = APIRouter(prefix="/processes", tags=["Processes"])

PARTICIPANT_EVENT_TYPES = frozenset({
    "PARTICIPANT_ASSIGNED",
    "PARTICIPANT_REVOKED",
    "CONFLICT_DECLARED",
})


async def _visible_events(
    session: Session,
    current_user: UserModel,
    process_id,
    events: list[AuditEvent],
) -> list[AuditEvent]:
    manages_participants = await can_manage_participants(
        session, current_user.id, process_id
    )
    if manages_participants:
        return events

    visible = []
    for event in events:
        if event.event_type in PARTICIPANT_EVENT_TYPES:
            context = event.context_data or {}
            if context.get("participant_user_id") != str(current_user.id):
                continue
        visible.append(event)
    return visible


@router.get(
    "/templates",
    response_model=list[ProcessTemplateSummary],
    status_code=HTTPStatus.OK,
)
async def list_templates(session: Session, _: CurrentUser):
    stmt = select(ProcessTemplate).where(
        ProcessTemplate.deleted_at.is_(None),
        ProcessTemplate.is_active.is_(True),
    )
    res = await session.execute(stmt)
    return res.scalars().all()


@router.get(
    "/templates/{key}",
    response_model=ProcessTemplateDetail,
    status_code=HTTPStatus.OK,
)
async def get_template_detail(key: str, session: Session, _: CurrentUser):
    stmt = (
        select(ProcessTemplate)
        .where(ProcessTemplate.key == key, ProcessTemplate.deleted_at.is_(None))
        .options(selectinload(ProcessTemplate.versions))
    )
    res = await session.execute(stmt)
    template = res.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Template '{key}' não encontrado.",
        )

    published_versions = sorted(
        [v for v in template.versions if v.deleted_at is None and v.is_published],
        key=lambda x: x.version_number,
        reverse=True,
    )
    if not published_versions:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=(f"Nenhuma versão publicada encontrada para o template '{key}'."),
        )

    latest = published_versions[0]
    return ProcessTemplateDetail(
        id=template.id,
        key=template.key,
        name=template.name,
        version_number=latest.version_number,
        definition=latest.definition_payload,
    )


@router.post(
    "",
    response_model=ProcessInstanceDetail,
    status_code=HTTPStatus.CREATED,
)
async def create_process(
    body: CreateProcessRequest,
    session: Session,
    current_user: CurrentUser,
):
    stmt = (
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(
            ProcessTemplate.key == body.template_key,
            ProcessTemplate.deleted_at.is_(None),
            ProcessTemplate.is_active.is_(True),
            ProcessTemplateVersion.deleted_at.is_(None),
            ProcessTemplateVersion.is_published.is_(True),
        )
        .order_by(ProcessTemplateVersion.version_number.desc())
    )
    res = await session.execute(stmt)
    latest_version = res.scalars().first()
    if not latest_version:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=(f"Template '{body.template_key}' não encontrado ou inativo."),
        )

    try:
        process = await instantiate_process(
            session=session,
            template_version=latest_version,
            title=body.title,
            creator_user_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Erro ao instanciar processo: {e!s}",
        )

    return ProcessInstanceDetail(
        id=process.id,
        code=process.code,
        title=process.title,
        status=process.status,
        template_key=body.template_key,
        version_number=latest_version.version_number,
        started_at=process.started_at,
        closed_at=process.closed_at,
        closure_reason=process.closure_reason,
    )


@router.get(
    "",
    response_model=ProcessInstanceListResponse,
    status_code=HTTPStatus.OK,
)
async def list_processes(
    session: Session,
    current_user: CurrentUser,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.deleted_at.is_(None),
            or_(
                ProcessInstance.status != "SUBMISSION",
                ProcessInstance.id.in_(
                    active_proponent_process_scope(current_user.id)
                ),
            ),
        )
        .options(
            selectinload(ProcessInstance.template_version).selectinload(
                ProcessTemplateVersion.template
            )
        )
    )
    if status:
        stmt = stmt.where(ProcessInstance.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        stmt
        .order_by(ProcessInstance.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = (await session.execute(stmt)).scalars().all()

    detail_items = [
        ProcessInstanceDetail(
            id=p.id,
            code=p.code,
            title=p.title,
            status=p.status,
            template_key=p.template_version.template.key,
            version_number=p.template_version.version_number,
            started_at=p.started_at,
            closed_at=p.closed_at,
            closure_reason=p.closure_reason,
        )
        for p in items
    ]

    return ProcessInstanceListResponse(
        items=detail_items,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{id}",
    response_model=ProcessInstanceDetail,
    status_code=HTTPStatus.OK,
)
async def get_process(id: UUID, session: Session, current_user: CurrentUser):
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.id == id,
            ProcessInstance.deleted_at.is_(None),
            or_(
                ProcessInstance.status != "SUBMISSION",
                ProcessInstance.id.in_(
                    active_proponent_process_scope(current_user.id)
                ),
            ),
        )
        .options(
            selectinload(ProcessInstance.template_version).selectinload(
                ProcessTemplateVersion.template
            )
        )
    )
    p = (await session.execute(stmt)).scalar_one_or_none()
    if not p:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Processo não encontrado."
        )

    return ProcessInstanceDetail(
        id=p.id,
        code=p.code,
        title=p.title,
        status=p.status,
        template_key=p.template_version.template.key,
        version_number=p.template_version.version_number,
        started_at=p.started_at,
        closed_at=p.closed_at,
        closure_reason=p.closure_reason,
    )


@router.get(
    "/{id}/timeline",
    response_model=ProcessTimelineResponse,
    status_code=HTTPStatus.OK,
)
async def get_process_timeline(id: UUID, session: Session, current_user: CurrentUser):
    p_stmt = select(ProcessInstance).where(
        ProcessInstance.id == id,
        ProcessInstance.deleted_at.is_(None),
        or_(
            ProcessInstance.status != "SUBMISSION",
            ProcessInstance.id.in_(
                active_proponent_process_scope(current_user.id)
            ),
        ),
    )
    p = (await session.execute(p_stmt)).scalar_one_or_none()
    if not p:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Processo não encontrado."
        )

    events_stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.process_instance_id == id,
            AuditEvent.deleted_at.is_(None),
        )
        .order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
    )
    events = list((await session.execute(events_stmt)).scalars().all())
    events = await _visible_events(session, current_user, id, events)

    return ProcessTimelineResponse(
        process_id=p.id,
        code=p.code,
        events=[
            TimelineEvent(
                id=e.id,
                event_type=e.event_type,
                user_id=e.user_id,
                activity_run_id=e.activity_run_id,
                occurred_at=e.occurred_at,
                context_data=e.context_data,
            )
            for e in events
        ],
    )
