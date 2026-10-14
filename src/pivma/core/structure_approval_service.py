"""Homologação da estrutura do estudo (Spec 042, issue #27).

O BraCVAM confere a Etapa 2 antes da Etapa 3. Os pontos auditados são as
dependências da atividade ``structure_approval`` no template, sem lista fixa
de chaves (research R2). As pendências são calculadas na hora, porque
designar e revogar continuam permitidos depois que um ponto conclui
(research R3). A decisão trava o processo: duas decisões simultâneas sobre
a mesma execução terminam com uma só gravada (research R6).

O painel mostra só contagens das amostras: nada de nome químico, CAS, SDS ou
código cego (FR-006).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.authorization import compute_effectiveness_map
from pivma.core.collection_template_service import lock_template_row
from pivma.core.database.models import (
    ActivityDependency,
    ActivityInstance,
    ActivityRun,
    Assignment,
    AuditEvent,
    BlindSampleCode,
    Decision,
    Phase,
    ProcessInstance,
    ProcessTemplateVersion,
    StudySubstance,
)
from pivma.core.process_engine import (
    SAMPLE_DEFINITION_ACTIVITY_TYPE,
    ConflictError,
    NotFoundError,
    ValidationError,
    _activate_activity,  # noqa: PLC2701
    _advance_dependent_activities,  # noqa: PLC2701
    _complete_activity_run,  # noqa: PLC2701
    _frozen_laboratory_ids,  # noqa: PLC2701
    _lock_process,  # noqa: PLC2701
    ensure_process_mutable,
    require_activity_access,
)
from pivma.core.references import laboratory_refs, user_refs
from pivma.core.sample_service import active_laboratories

STRUCTURE_APPROVAL_KEY = 'structure_approval'
DECISION_TYPE = 'STRUCTURE_APPROVAL'
ROLE_ASSIGNMENT = 'role_assignment'
REJECTED_REASON = 'Aguardando a reexecução dos pontos reprovados.'
PENDING_MESSAGES = {
    'activity_not_completed': 'Atividade não concluída.',
    'role_without_designation': 'Cargo sem designação ativa.',
    'laboratory_without_codes': 'Laboratório participante sem códigos cegos.',
    'codes_without_laboratory': (
        'Códigos cegos de laboratório que não é participante ativo.'
    ),
}


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------


async def _approval(
    session: AsyncSession, process_id: UUID
) -> ActivityInstance:
    """A homologação do processo, relida do banco."""
    act = await session.scalar(
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == STRUCTURE_APPROVAL_KEY,
        )
        .execution_options(populate_existing=True)
    )
    if act is None:
        raise NotFoundError('Homologação da estrutura não encontrada.')
    return act


async def _points(
    session: AsyncSession, act: ActivityInstance
) -> list[ActivityInstance]:
    """As atividades de que a homologação depende, na ordem do template."""
    return list(
        await session.scalars(
            select(ActivityInstance)
            .join(
                ActivityDependency,
                ActivityDependency.required_activity_id == ActivityInstance.id,
            )
            .join(Phase, Phase.id == ActivityInstance.phase_id)
            .where(
                ActivityDependency.dependent_activity_id == act.id,
                ActivityDependency.deleted_at.is_(None),
            )
            .order_by(Phase.order_index, ActivityInstance.order_index)
            .execution_options(populate_existing=True)
        )
    )


async def _latest_run_numbers(
    session: AsyncSession, activity_ids: list[UUID]
) -> dict[UUID, int]:
    rows = await session.execute(
        select(
            ActivityRun.activity_instance_id, func.max(ActivityRun.run_number)
        )
        .where(ActivityRun.activity_instance_id.in_(activity_ids))
        .group_by(ActivityRun.activity_instance_id)
    )
    return dict(rows.tuples().all())


async def _open_run(
    session: AsyncSession, act: ActivityInstance
) -> ActivityRun | None:
    if act.status != 'IN_PROGRESS':
        return None
    return await session.scalar(
        select(ActivityRun)
        .where(
            ActivityRun.activity_instance_id == act.id,
            ActivityRun.status == 'IN_PROGRESS',
        )
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )


async def _template_activities(
    session: AsyncSession, process_id: UUID
) -> dict[str, dict[str, Any]]:
    """Definição das atividades na versão do template do processo."""
    version = await session.scalar(
        select(ProcessTemplateVersion)
        .join(
            ProcessInstance,
            ProcessInstance.template_version_id == ProcessTemplateVersion.id,
        )
        .where(ProcessInstance.id == process_id)
        .execution_options(skip_soft_delete_filter=True)
    )
    return {
        a['key']: a
        for phase in version.definition_payload.get('phases', [])
        for a in phase.get('activities', [])
    }


async def _active_assignments(
    session: AsyncSession, process_id: UUID, role_keys: list[str]
) -> list[Assignment]:
    """Designações ativas (não revogadas nem excluídas) dos cargos."""
    return list(
        await session.scalars(
            select(Assignment)
            .where(
                Assignment.process_instance_id == process_id,
                Assignment.role_key.in_(role_keys),
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
            )
            .order_by(Assignment.created_at, Assignment.id)
        )
    )


def _pending(code: str, laboratory=None) -> dict[str, Any]:
    return {
        'code': code,
        'message': PENDING_MESSAGES[code],
        'laboratory': laboratory,
    }


async def _sample_pending(
    session: AsyncSession, process_id: UUID
) -> list[dict[str, Any]]:
    """Laboratórios participantes ativos sem códigos e o inverso (R3).

    As duas consultas já vêm ordenadas por nome, e a ordem se mantém.
    """
    participants = [
        lab.id for lab in await active_laboratories(session, process_id)
    ]
    with_codes = await _frozen_laboratory_ids(session, process_id)
    missing = [i for i in participants if i not in with_codes]
    orphan = [i for i in with_codes if i not in participants]
    refs = await laboratory_refs(session, missing + orphan)
    return [_pending('laboratory_without_codes', refs[i]) for i in missing] + [
        _pending('codes_without_laboratory', refs[i]) for i in orphan
    ]


async def _pending_by_point(
    session: AsyncSession,
    process_id: UUID,
    points: list[ActivityInstance],
    templates: dict[str, dict[str, Any]],
    assignments: list[Assignment],
) -> dict[UUID, list[dict[str, Any]]]:
    """As quatro regras de pendência de data-model.md, por ponto."""
    designated_roles = {a.role_key for a in assignments}
    pending: dict[UUID, list[dict[str, Any]]] = {}
    for point in points:
        items = []
        if point.status != 'COMPLETED':
            items.append(_pending('activity_not_completed'))
        if point.activity_type == ROLE_ASSIGNMENT:
            role_key = templates.get(point.key, {}).get('target_role_key')
            if role_key not in designated_roles:
                items.append(_pending('role_without_designation'))
        elif point.activity_type == SAMPLE_DEFINITION_ACTIVITY_TYPE:
            items.extend(await _sample_pending(session, process_id))
        pending[point.id] = items
    return pending


def _target_roles(
    points: list[ActivityInstance], templates: dict[str, dict[str, Any]]
) -> dict[UUID, str]:
    return {
        point.id: templates.get(point.key, {}).get('target_role_key')
        for point in points
        if point.activity_type == ROLE_ASSIGNMENT
    }


async def _structure(
    session: AsyncSession, process_id: UUID, act: ActivityInstance
) -> tuple[list[ActivityInstance], dict, list[Assignment], dict]:
    """Pontos, cargo-alvo de cada atribuição, designações e pendências."""
    points = await _points(session, act)
    templates = await _template_activities(session, process_id)
    target_roles = _target_roles(points, templates)
    assignments = await _active_assignments(
        session, process_id, list(target_roles.values())
    )
    pending = await _pending_by_point(
        session, process_id, points, templates, assignments
    )
    return points, target_roles, assignments, pending


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------


async def _sample_counts(session: AsyncSession, process_id: UUID) -> dict:
    substance_count = await session.scalar(
        select(func.count()).where(
            StudySubstance.process_instance_id == process_id,
            StudySubstance.deleted_at.is_(None),
        )
    )
    code_count, laboratory_count = (
        await session.execute(
            select(
                func.count(),
                func.count(distinct(BlindSampleCode.laboratory_id)),
            ).where(
                BlindSampleCode.process_instance_id == process_id,
                BlindSampleCode.deleted_at.is_(None),
            )
        )
    ).one()
    return {
        'substance_count': substance_count,
        'laboratory_count': laboratory_count,
        'code_count': code_count,
    }


async def _designations(
    session: AsyncSession, assignments: list[Assignment]
) -> dict[str, list[dict[str, Any]]]:
    """Designações ativas por cargo, com pessoa, laboratório e efetividade."""
    users = await user_refs(session, (a.user_id for a in assignments))
    labs = await laboratory_refs(
        session, (a.laboratory_id for a in assignments)
    )
    effective = await compute_effectiveness_map(session, assignments)
    by_role: dict[str, list[dict[str, Any]]] = {}
    for a in assignments:
        by_role.setdefault(a.role_key, []).append({
            'assignment_id': a.id,
            'user': users[a.user_id],
            'laboratory': labs.get(a.laboratory_id),
            'is_effective': effective[a.id],
        })
    return by_role


async def _decisions(
    session: AsyncSession, process_id: UUID
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Decision, ActivityRun.run_number)
            .join(ActivityRun, ActivityRun.id == Decision.activity_run_id)
            .where(
                Decision.process_instance_id == process_id,
                Decision.decision_type == DECISION_TYPE,
            )
            .order_by(Decision.decided_at.desc(), Decision.id.desc())
        )
    ).all()
    users = await user_refs(session, (d.decided_by for d, _ in rows))
    return [
        {
            'id': d.id,
            'run_number': run_number,
            'outcome': d.outcome,
            'justification': d.justification,
            'rejected_points': d.rejected_points,
            'decided_by': users[d.decided_by],
            'decided_at': d.decided_at,
        }
        for d, run_number in rows
    ]


async def get_panel(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Painel da homologação para quem vê a atividade (Admin e BraCVAM)."""
    if (
        await session.scalar(
            select(ProcessInstance.id).where(ProcessInstance.id == process_id)
        )
        is None
    ):
        raise NotFoundError('Processo não encontrado.')
    act = await _approval(session, process_id)
    await require_activity_access(session, user_id, act, 'view')
    points, target_roles, assignments, pending = await _structure(
        session, process_id, act
    )
    run_numbers = await _latest_run_numbers(
        session, [act.id, *(p.id for p in points)]
    )
    designations = await _designations(session, assignments)
    samples = await _sample_counts(session, process_id)
    return {
        'status': act.status,
        'run_number': run_numbers.get(act.id),
        'blocked_reason': act.blocked_reason,
        'points': [
            {
                'activity_key': p.key,
                'name': p.name,
                'activity_type': p.activity_type,
                'status': p.status,
                'run_number': run_numbers.get(p.id),
                'designations': (
                    designations.get(target_roles[p.id], [])
                    if p.id in target_roles
                    else None
                ),
                'samples': (
                    samples
                    if p.activity_type == SAMPLE_DEFINITION_ACTIVITY_TYPE
                    else None
                ),
                'pending': pending[p.id],
            }
            for p in points
        ],
        'decisions': await _decisions(session, process_id),
    }


# ---------------------------------------------------------------------------
# Decisão
# ---------------------------------------------------------------------------


def _event(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    run_id: UUID,
    user_id: UUID,
    event_type: str,
    context: dict[str, Any],
) -> None:
    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run_id,
            user_id=user_id,
            event_type=event_type,
            context_data=context,
        )
    )


async def _approve(
    session: AsyncSession,
    process: ProcessInstance,
    act: ActivityInstance,
    user_id: UUID,
) -> None:
    """Fecha a fase 2 e abre a Etapa 3 (FR-010)."""
    phase = await session.get(Phase, act.phase_id)
    phase.status = 'COMPLETED'
    phase.set_update_audit(user_id)
    if process.collection_template_id is not None:
        # Serializa com as alterações estruturais do template: a Etapa 3
        # começa aqui e o trava (research R9).
        await lock_template_row(session, process.collection_template_id)
    await _advance_dependent_activities(session, process, act, user_id)


async def _reject(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    act: ActivityInstance,
    points: list[ActivityInstance],
    rejected_points: list[dict[str, str]],
    user_id: UUID,
) -> list[dict[str, Any]]:
    """Bloqueia a homologação e reabre cada ponto reprovado (R4)."""
    act.status = 'BLOCKED'
    act.blocked_reason = REJECTED_REASON
    act.set_update_audit(user_id)

    by_key = {p.key: p for p in points}
    templates = await _template_activities(session, process_id)
    previous = await _latest_run_numbers(session, [p.id for p in points])
    reopened = []
    for item in rejected_points:
        point = by_key[item['activity_key']]
        run = await _activate_activity(
            session,
            point,
            templates[point.key],
            user_id,
            reason=item['reason'],
        )
        _event(
            session,
            process_id,
            run.id,
            user_id,
            'ACTIVITY_REOPENED',
            {
                'activity_key': point.key,
                'previous_run_number': previous.get(point.id),
                'run_number': run.run_number,
                'reason': item['reason'],
            },
        )
        reopened.append({
            'activity_key': point.key,
            'run_number': run.run_number,
        })
    return reopened


async def execute_structure_decision(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    outcome: str,
    justification: str,
    rejected_points: list[dict[str, str]] | None,
) -> dict[str, Any]:
    """Aprova ou reprova a execução aberta da homologação (FR-009 a FR-018).

    A autorização vem antes da trava, para quem não vê receber 404 sem
    esperar. Sob a trava do processo, a homologação é relida: a segunda
    decisão simultânea encontra a execução já concluída.
    """
    act = await _approval(session, process_id)
    await require_activity_access(session, user_id, act, 'edit')
    process = await _lock_process(session, process_id)
    await ensure_process_mutable(session, process_id)
    act = await _approval(session, process_id)
    run = await _open_run(session, act)
    if run is None:
        raise ConflictError(
            'A homologação não está aberta para decisão.',
            code='invalid_transition',
        )
    points, _, _, pending = await _structure(session, process_id, act)
    if outcome == 'REJECTED':
        point_keys = {p.key for p in points}
        if any(i['activity_key'] not in point_keys for i in rejected_points):
            raise ValidationError(
                'Ponto reprovado não pertence à homologação.',
                code='invalid_point',
            )
    elif any(pending.values()):
        raise ConflictError(
            'A estrutura tem pendências; confira o painel.',
            code='structure_pending',
        )

    decision = Decision(
        process_instance_id=process_id,
        activity_run_id=run.id,
        decision_type=DECISION_TYPE,
        outcome=outcome,
        justification=justification,
        decided_by=user_id,
        rejected_points=rejected_points,
    )
    decision.set_creation_audit(user_id)
    session.add(decision)
    await _complete_activity_run(session, run, act, user_id)
    process.set_update_audit(user_id)

    context = {'decision_id': str(decision.id), 'justification': justification}
    if outcome == 'APPROVED':
        await _approve(session, process, act, user_id)
        _event(
            session, process_id, run.id, user_id, 'STRUCTURE_APPROVED', context
        )
        reopened = []
    else:
        reopened = await _reject(
            session, process_id, act, points, rejected_points, user_id
        )
        _event(
            session,
            process_id,
            run.id,
            user_id,
            'STRUCTURE_REJECTED',
            {**context, 'rejected_points': rejected_points},
        )
    await session.commit()
    return {
        'decision_id': decision.id,
        'outcome': outcome,
        'status': act.status,
        'reopened': reopened,
    }
