"""Acompanhamento do Patrocinador (Spec 048).

Duas rotas de leitura: os processos em que o usuário é Patrocinador e o
andamento de um deles. Não gravam evento (FR-010) e não mudam o acesso às
atividades (FR-008). As respostas só trazem os campos do contrato, sem dado
interno do estudo (FR-007).
"""

from collections import defaultdict
from collections.abc import Sequence
from http import HTTPStatus
from typing import get_args
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    effective_assignment_clause,
    has_platform_wide_access,
    process_cargos_scope,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Assignment,
    Laboratory,
    Phase,
    ProcessInstance,
    User,
)
from pivma.core.errors import http_error
from pivma.core.listing import PageQuery, PerPageQuery, build_pagination
from pivma.core.process_engine import STATUS_OPEN
from pivma.core.references import laboratory_refs
from pivma.dependencies import CurrentUser, Session
from pivma.schemas import (
    NoFilters,
    ParticipantRole,
    SortApplied,
    SponsoredProcessListResponse,
    SponsoredProcessSummary,
    SponsorTrackingDetail,
    TrackingActivity,
    TrackingPerson,
    TrackingPhase,
    TrackingRole,
    UserRef,
)

router = APIRouter(prefix='/sponsor-tracking', tags=['Sponsor Tracking'])

SPONSOR_ROLE_KEY = 'sponsor'
RUN_IN_PROGRESS = 'IN_PROGRESS'
NOT_FOUND_MESSAGE = 'Processo não encontrado.'


def _sponsorships(user_id: UUID):
    """Processos com designação efetiva do usuário como Patrocinador (R2).

    Cada linha traz a data da designação ativa mais antiga (R3). A lista lê
    essa data na mesma consulta que pagina os processos: com duas consultas,
    uma revogação entre elas deixaria o processo na página sem data.
    """
    return (
        process_cargos_scope(user_id)
        .with_only_columns(
            Assignment.process_instance_id,
            func.min(Assignment.assigned_at).label('since'),
        )
        .where(Assignment.role_key == SPONSOR_ROLE_KEY)
        .group_by(Assignment.process_instance_id)
        .subquery()
    )


async def _open_runs(
    session: AsyncSession, process_ids: Sequence[UUID]
) -> list[Row]:
    """Execuções em andamento dos processos, em ordem estável (R6).

    Quem chama passa só processos `OPEN`. A lista e o detalhe usam esta
    mesma consulta, para que o cartão e o detalhe mostrem a mesma fase.
    """
    if not process_ids:
        return []
    rows = await session.execute(
        select(
            ActivityInstance.process_instance_id,
            ActivityInstance.key,
            ActivityInstance.name,
            Phase.key.label('phase_key'),
            Phase.name.label('phase_name'),
            Phase.order_index.label('phase_order'),
            ActivityRun.started_at,
            ActivityRun.laboratory_id,
        )
        .join(
            ActivityInstance,
            ActivityInstance.id == ActivityRun.activity_instance_id,
        )
        .join(Phase, Phase.id == ActivityInstance.phase_id)
        .outerjoin(Laboratory, Laboratory.id == ActivityRun.laboratory_id)
        .where(
            ActivityInstance.process_instance_id.in_(process_ids),
            ActivityRun.status == RUN_IN_PROGRESS,
        )
        .order_by(
            Phase.order_index,
            ActivityInstance.order_index,
            Laboratory.name,
            ActivityRun.id,
        )
    )
    return list(rows)


def _current_phase(rows: Sequence[Row]) -> TrackingPhase | None:
    """A fase de maior ordem entre as execuções em andamento (FR-004)."""
    if not rows:
        return None
    row = max(rows, key=lambda r: r.phase_order)
    return TrackingPhase(
        key=row.phase_key, name=row.phase_name, order=row.phase_order
    )


@router.get(
    '/processes',
    response_model=SponsoredProcessListResponse,
    status_code=HTTPStatus.OK,
)
async def list_sponsored_processes(
    session: Session,
    current_user: CurrentUser,
    page: PageQuery = 1,
    per_page: PerPageQuery = 20,
):
    sponsorships = _sponsorships(current_user.id)
    stmt = (
        select(ProcessInstance, sponsorships.c.since)
        .join(
            sponsorships,
            sponsorships.c.process_instance_id == ProcessInstance.id,
        )
        .where(ProcessInstance.deleted_at.is_(None))
    )
    # `paginate_query` devolve só a primeira coluna; aqui a página precisa
    # da data da designação junto com o processo.
    total = await session.scalar(
        select(func.count()).select_from(stmt.subquery())
    )
    items = (
        await session.execute(
            stmt
            .order_by(
                ProcessInstance.created_at.desc(), ProcessInstance.id.desc()
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    runs: dict[UUID, list[Row]] = defaultdict(list)
    for row in await _open_runs(
        session, [p.id for p, _ in items if p.status == STATUS_OPEN]
    ):
        runs[row.process_instance_id].append(row)

    return SponsoredProcessListResponse(
        data=[
            SponsoredProcessSummary(
                id=process.id,
                code=process.code,
                title=process.title,
                status=process.status,
                started_at=process.started_at,
                closed_at=process.closed_at,
                sponsored_since=since,
                current_phase=_current_phase(runs[process.id]),
                open_activity_count=len(runs[process.id]),
            )
            for process, since in items
        ],
        pagination=build_pagination(page, per_page, total or 0),
        filters_applied=NoFilters(),
        sort=SortApplied(by='created_at', order='desc'),
    )


@router.get(
    '/processes/{process_id}',
    response_model=SponsorTrackingDetail,
    status_code=HTTPStatus.OK,
)
async def get_sponsored_process(
    process_id: UUID, session: Session, current_user: CurrentUser
):
    process = await session.scalar(
        select(ProcessInstance).where(
            ProcessInstance.id == process_id,
            ProcessInstance.deleted_at.is_(None),
        )
    )
    if process is None:
        raise http_error(HTTPStatus.NOT_FOUND, NOT_FOUND_MESSAGE)
    sponsorships = _sponsorships(current_user.id)
    since = await session.scalar(
        select(sponsorships.c.since).where(
            sponsorships.c.process_instance_id == process.id
        )
    )
    # Admin e BraCVAM veem qualquer processo; os demais cargos recebem o
    # mesmo 404 de um processo inexistente (R4).
    if since is None and not await has_platform_wide_access(
        session, current_user.id
    ):
        raise http_error(HTTPStatus.NOT_FOUND, NOT_FOUND_MESSAGE)

    assignments = (
        await session.execute(
            select(Assignment, User)
            .join(User, User.id == Assignment.user_id)
            .where(
                Assignment.process_instance_id == process.id,
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
                User.deleted_at.is_(None),
                effective_assignment_clause(),
            )
            .order_by(Assignment.assigned_at, Assignment.id)
        )
    ).all()
    runs = (
        await _open_runs(session, [process.id])
        if process.status == STATUS_OPEN
        else []
    )
    laboratories = await laboratory_refs(
        session,
        [a.laboratory_id for a, _ in assignments]
        + [r.laboratory_id for r in runs],
    )

    people: dict[str, list[TrackingPerson]] = defaultdict(list)
    for assignment, user in assignments:
        people[assignment.role_key].append(
            TrackingPerson(
                user=UserRef(
                    id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                ),
                laboratory=laboratories.get(assignment.laboratory_id),
            )
        )

    return SponsorTrackingDetail(
        id=process.id,
        code=process.code,
        title=process.title,
        status=process.status,
        started_at=process.started_at,
        closed_at=process.closed_at,
        sponsored_since=since,
        current_phase=_current_phase(runs),
        roles=[
            TrackingRole(role_key=role_key, people=people[role_key])
            for role_key in get_args(ParticipantRole)
        ],
        open_activities=[
            TrackingActivity(
                key=run.key,
                name=run.name,
                phase_key=run.phase_key,
                started_at=run.started_at,
                laboratory=laboratories.get(run.laboratory_id),
            )
            for run in runs
        ],
    )
