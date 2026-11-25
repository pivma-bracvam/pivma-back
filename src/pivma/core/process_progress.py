"""Andamento do processo por cargo (Spec 048).

`ProgressView` é a única regra de quem vê quais pessoas e quais execuções no
andamento. A lista (`GET /processes`) e o detalhe
(`GET /processes/{id}/progress`) usam as mesmas funções, para que o cartão e
o detalhe mostrem a mesma fase e a mesma contagem.

Ninguém vê aqui dado interno do estudo (FR-007), e o andamento não muda o
acesso às atividades (FR-008).
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import get_args
from uuid import UUID

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import (
    GROUP_MANAGER_ROLE_KEY,
    LABORATORY_ROLE_KEYS,
    PARTICIPATING_LABORATORY_ROLE_KEY,
    PROPONENT_ROLE_KEY,
    effective_assignment_clause,
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
from pivma.core.process_engine import STATUS_OPEN
from pivma.core.references import laboratory_refs
from pivma.schemas import (
    LaboratoryRef,
    ParticipantRole,
    ProcessProgress,
    ProgressActivity,
    ProgressPerson,
    ProgressPhase,
    ProgressPhaseStatus,
    ProgressRole,
    UserRef,
    ViewerRole,
)

RUN_IN_PROGRESS = 'IN_PROGRESS'

# Veem todas as pessoas e todas as execuções, de todos os laboratórios:
# quem coordena o estudo e o Patrocinador (decisão de 2026-11-23).
FULL_VIEW_ROLES = frozenset({
    GROUP_MANAGER_ROLE_KEY,
    'study_manager',
    'sponsor',
})
# Quem conduz o processo. Os demais cargos veem estas pessoas.
COORDINATION_ROLES = FULL_VIEW_ROLES | {PROPONENT_ROLE_KEY}
# Revisão cega (RF050): o avaliador não vê o proponente nem outro avaliador.
BLIND_REVIEW_ROLES = frozenset({'adhoc_evaluator', 'peer_reviewer'})


@dataclass(frozen=True)
class ProgressView:
    """O que um usuário vê no andamento de um processo.

    Com mais de um cargo no processo, vale a união do que cada um libera.
    """

    user_id: UUID
    full: bool
    roles: frozenset[str]
    laboratories: frozenset[UUID]

    def sees_role(self, role_key: str) -> bool:
        if self.full or role_key in self.roles:
            return True
        if role_key in LABORATORY_ROLE_KEYS:
            return bool(self.laboratories)
        if role_key == PROPONENT_ROLE_KEY:
            return not self.roles <= BLIND_REVIEW_ROLES
        return role_key in COORDINATION_ROLES

    def sees_person(
        self, role_key: str, user_id: UUID, laboratory_id: UUID | None
    ) -> bool:
        if self.full or user_id == self.user_id:
            return True
        if role_key in LABORATORY_ROLE_KEYS:
            # Isolamento por laboratório (constituição III, RF044).
            return laboratory_id in self.laboratories
        if role_key in BLIND_REVIEW_ROLES:
            return False
        return self.sees_role(role_key)

    def sees_run(self, laboratory_id: UUID | None) -> bool:
        """Mesma regra de `laboratory_run_visibility_clause`."""
        return (
            self.full
            or laboratory_id is None
            or laboratory_id in self.laboratories
        )


def progress_view(
    user_id: UUID, platform_wide: bool, assignments: Sequence[Row]
) -> ProgressView:
    """`assignments` vem de `viewer_assignments` para um processo."""
    roles = frozenset(a.role_key for a in assignments)
    return ProgressView(
        user_id=user_id,
        full=platform_wide or bool(roles & FULL_VIEW_ROLES),
        roles=roles,
        laboratories=frozenset(
            a.laboratory_id
            for a in assignments
            if a.role_key == PARTICIPATING_LABORATORY_ROLE_KEY
        ),
    )


async def viewer_assignments(
    session: AsyncSession, user_id: UUID, process_ids: Sequence[UUID]
) -> dict[UUID, list[Row]]:
    """Designações efetivas do usuário em cada processo, da mais antiga."""
    if not process_ids:
        return {}
    rows = await session.execute(
        process_cargos_scope(user_id)
        .with_only_columns(
            Assignment.process_instance_id,
            Assignment.role_key,
            Assignment.laboratory_id,
            Assignment.assigned_at,
        )
        .where(Assignment.process_instance_id.in_(process_ids))
        .order_by(Assignment.assigned_at, Assignment.id)
    )
    grouped: dict[UUID, list[Row]] = defaultdict(list)
    for row in rows:
        grouped[row.process_instance_id].append(row)
    return grouped


def viewer_roles(
    assignments: Sequence[Row], laboratories: dict[UUID, LaboratoryRef]
) -> list[ViewerRole]:
    return [
        ViewerRole(
            role_key=a.role_key,
            laboratory=laboratories.get(a.laboratory_id),
            assigned_at=a.assigned_at,
        )
        for a in assignments
    ]


async def open_runs(
    session: AsyncSession, processes: Sequence[ProcessInstance]
) -> dict[UUID, list[Row]]:
    """Execuções em andamento dos processos `OPEN`, em ordem estável (R6)."""
    process_ids = [p.id for p in processes if p.status == STATUS_OPEN]
    if not process_ids:
        return {}
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
    grouped: dict[UUID, list[Row]] = defaultdict(list)
    for row in rows:
        grouped[row.process_instance_id].append(row)
    return grouped


def current_phase(runs: Sequence[Row]) -> ProgressPhase | None:
    """A fase de maior ordem entre as execuções em andamento (FR-004).

    Conta todas as execuções, inclusive as que o usuário não vê: a fase do
    processo não depende de quem olha.
    """
    if not runs:
        return None
    row = max(runs, key=lambda r: r.phase_order)
    return ProgressPhase(
        key=row.phase_key, name=row.phase_name, order=row.phase_order
    )


async def build_progress(
    session: AsyncSession,
    process: ProcessInstance,
    user_id: UUID,
    platform_wide: bool,
) -> ProcessProgress:
    mine = (await viewer_assignments(session, user_id, [process.id])).get(
        process.id, []
    )
    view = progress_view(user_id, platform_wide, mine)
    phases = await session.scalars(
        select(Phase)
        .where(Phase.process_instance_id == process.id)
        .order_by(Phase.order_index, Phase.id)
    )
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
    assignments = [
        (a, u)
        for a, u in assignments
        if view.sees_person(a.role_key, a.user_id, a.laboratory_id)
    ]
    runs = (await open_runs(session, [process])).get(process.id, [])
    visible_runs = [r for r in runs if view.sees_run(r.laboratory_id)]
    laboratories = await laboratory_refs(
        session,
        [a.laboratory_id for a, _ in assignments]
        + [r.laboratory_id for r in visible_runs]
        + [a.laboratory_id for a in mine],
    )

    people: dict[str, list[ProgressPerson]] = defaultdict(list)
    for assignment, user in assignments:
        people[assignment.role_key].append(
            ProgressPerson(
                user=UserRef(
                    id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                ),
                laboratory=laboratories.get(assignment.laboratory_id),
            )
        )

    return ProcessProgress(
        process_id=process.id,
        my_roles=viewer_roles(mine, laboratories),
        current_phase=current_phase(runs),
        phases=[
            ProgressPhaseStatus(
                key=phase.key,
                name=phase.name,
                order=phase.order_index,
                status=phase.status,
            )
            for phase in phases
        ],
        roles=[
            ProgressRole(role_key=role_key, people=people[role_key])
            for role_key in get_args(ParticipantRole)
            if view.sees_role(role_key)
        ],
        open_activities=[
            ProgressActivity(
                key=run.key,
                name=run.name,
                phase_key=run.phase_key,
                started_at=run.started_at,
                laboratory=laboratories.get(run.laboratory_id),
            )
            for run in visible_runs
        ],
    )
