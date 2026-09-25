import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import any_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import ColumnElement

from pivma.core.authorization import (
    ACTIVITY_CARGOS,
    GLOBAL_ACTIVITY_CARGOS,
    active_participant_process_scope,
    global_cargos,
    has_current_conflict,
    has_platform_wide_access,
    has_process_review_access,
    is_active_effective_proponent,
    process_cargos_scope,
    user_cargos,
)
from pivma.core.database.models import (
    ActivityDependency,
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    Decision,
    EvaluationAssignment,
    EvaluationRun,
    FieldReview,
    FormField,
    FormInstance,
    FormTemplate,
    FormValue,
    Phase,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    RoleAssignmentInvite,
    Task,
)


class ProcessEngineError(Exception):
    pass


class ValidationError(ProcessEngineError):
    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors or []


class ConflictError(ProcessEngineError):
    pass


class NotFoundError(ProcessEngineError):
    pass


class AuthorizationError(ProcessEngineError):
    pass


LIFECYCLE_DELETE = 'DELETE'
LIFECYCLE_ARCHIVE = 'ARCHIVE'
# Ciclo de vida do processo (Spec 030): é tudo o que o processo guarda. A
# posição no fluxo (submissão, pré-avaliação, triagem...) vem das fases e
# atividades.
STATUS_OPEN = 'OPEN'
STATUS_CLOSED = 'CLOSED'
STATUS_CANCELLED = 'CANCELLED'
STATUS_ARCHIVED = 'ARCHIVED'
TERMINAL_PROCESS_STATUSES = frozenset({
    STATUS_CLOSED,
    STATUS_CANCELLED,
    STATUS_ARCHIVED,
})
IMMUTABLE_PROCESS_STATUSES = frozenset({
    STATUS_CLOSED,
    STATUS_CANCELLED,
    STATUS_ARCHIVED,
})

# Alvos de avaliação por IA que se prendem a `field_keys` do formulário.
FIELD_TARGET_TYPES = frozenset({'field', 'field_set', 'document'})

# Título de tarefa da triagem preservado do antigo caminho bespoke
# (`_unblock_triage_activity`, removido na Issue #22) — o motor genérico
# usaria `act.name` ("Triagem e Decisão BraCVAM") por padrão; este texto é
# passado explicitamente a `_advance_dependent_activities` para não mudar o
# que já é exibido a quem faz a triagem hoje.
TRIAGE_TASK_TITLE = 'Realizar Triagem da Proposta'


def lifecycle_available_actions(
    *,
    status: str,
    can_delete: bool,
    can_review: bool,
) -> list[str]:
    """Calcula as operações que o ator pode tentar no processo."""
    actions: list[str] = []
    if status not in TERMINAL_PROCESS_STATUSES and can_delete:
        actions.append(LIFECYCLE_DELETE)
    if status in {STATUS_CLOSED, STATUS_CANCELLED} and can_review:
        actions.append(LIFECYCLE_ARCHIVE)
    return actions


async def process_visibility_clause(
    session: AsyncSession, user_id: UUID
) -> ColumnElement | None:
    """Quem vê o cabeçalho de um processo (Spec 018; Spec 030, FR-015).

    `None` significa "sem restrição" — Admin e BraCVAM, que têm concessão de
    ver em toda atividade. Os demais veem os processos em que têm atribuição
    ativa, em qualquer cargo; o conteúdo de cada atividade segue as
    concessões (`require_activity_access`), não esta cláusula.
    """
    if await has_platform_wide_access(session, user_id):
        return None
    return ProcessInstance.id.in_(active_participant_process_scope(user_id))


async def activity_view_clause(
    session: AsyncSession, user_id: UUID
) -> ColumnElement | None:
    """Filtro SQL das atividades que o usuário vê (Spec 030, R12).

    `None` para Admin/BraCVAM: toda atividade concede ver a `admin` e
    `bracvam`. Os demais veem a atividade quando algum cargo ativo no
    processo dela está em `view_roles`.
    """
    if await global_cargos(session, user_id):
        return None
    return exists(
        process_cargos_scope(user_id).where(
            Assignment.process_instance_id
            == ActivityInstance.process_instance_id,
            Assignment.role_key == any_(ActivityInstance.view_roles),
        )
    )


async def _guard_against_current_conflict(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> None:
    if await has_current_conflict(session, user_id, process_id):
        raise AuthorizationError(
            'Usuário com conflito de interesse vigente neste processo.'
        )


async def available_lifecycle_actions(
    session: AsyncSession, process: ProcessInstance, user_id: UUID
) -> list[str]:
    """Projeta ações aplicáveis sem substituir a autorização do comando."""
    can_delete = await is_active_effective_proponent(
        session, user_id, process.id
    ) or await has_platform_wide_access(session, user_id)
    review_access = await has_process_review_access(session, user_id)
    if review_access and await has_current_conflict(
        session, user_id, process.id
    ):
        review_access = False
    return lifecycle_available_actions(
        status=process.status,
        can_delete=can_delete,
        can_review=review_access,
    )


async def ensure_process_mutable(
    session: AsyncSession, process_id: UUID
) -> ProcessInstance:
    """Bloqueia mutações sobre processo terminal, excluído ou inexistente.

    Ignora o filtro global de soft-delete (Spec 022) e checa o status
    diretamente: um processo excluído tem `status=CANCELLED`, já coberto por
    `IMMUTABLE_PROCESS_STATUSES`, então a tentativa é rejeitada com o mesmo
    `409 invalid_transition` de qualquer outro processo terminal, em vez de
    um `404` que quebraria o contrato de erro já coberto por testes.
    """
    process = await session.scalar(
        select(ProcessInstance)
        .where(ProcessInstance.id == process_id)
        .execution_options(skip_soft_delete_filter=True)
    )
    if process is None:
        raise NotFoundError('Processo não encontrado.')
    if process.status in IMMUTABLE_PROCESS_STATUSES:
        raise ConflictError(
            f'Processo em status {process.status!r} não permite mutações.'
        )
    return process


async def _locked_lifecycle_process(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> ProcessInstance:
    """Carrega e trava o processo alvo de `DELETE`/`ARCHIVE`.

    Ignora o filtro global de soft-delete: `ARCHIVE` precisa alcançar um
    processo já excluído (seu `CANCELLED` satisfaz a pré-condição de
    arquivamento), e uma segunda tentativa de `DELETE` sobre ele deve cair
    na checagem de status terminal em `delete_process` (409), não em um
    `404` de visibilidade.
    """
    visibility = await process_visibility_clause(session, user_id)
    process_stmt = (
        select(ProcessInstance)
        .where(ProcessInstance.id == process_id)
        .execution_options(skip_soft_delete_filter=True)
    )
    if visibility is not None:
        process_stmt = process_stmt.where(visibility)
    process = await session.scalar(process_stmt.with_for_update())
    if process is None:
        raise NotFoundError('Processo não encontrado.')
    return process


async def _commit_lifecycle_change(
    session: AsyncSession,
    process: ProcessInstance,
    user_id: UUID,
) -> dict[str, Any]:
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        'id': process.id,
        'status': process.status,
        'available_actions': await available_lifecycle_actions(
            session, process, user_id
        ),
    }


async def delete_process(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Exclui logicamente (soft-delete) um processo não-terminal.

    Aceito para o proponente efetivo do processo ou para um usuário com
    perfil global Admin/BraCVAM, em qualquer estado não-terminal,
    independentemente de já ter sido formalmente submetido (Spec 022,
    revisão 2026-09-13). Documentos armazenados nunca são removidos.
    """
    process = await _locked_lifecycle_process(session, process_id, user_id)
    is_proponent = await is_active_effective_proponent(
        session, user_id, process_id
    )
    if not is_proponent and not await has_platform_wide_access(
        session, user_id
    ):
        raise AuthorizationError(
            'Somente o proponente efetivo ou um usuário com perfil global '
            'Admin/BraCVAM pode excluir este processo.'
        )
    if process.status in TERMINAL_PROCESS_STATUSES:
        raise ConflictError(
            f'Processo em status {process.status!r} não pode ser excluído.'
        )
    previous_status = process.status
    counts = await _cancel_pending_children(session, process, user_id)
    process.status = STATUS_CANCELLED
    process.closed_at = utc_now()
    process.set_update_audit(user_id)
    process.set_deletion_audit(user_id)
    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=user_id,
            event_type='PROCESS_DELETED',
            context_data={
                'previous_status': previous_status,
                'result_status': STATUS_CANCELLED,
                'cancelled_counts': counts,
            },
        )
    )
    return await _commit_lifecycle_change(session, process, user_id)


async def archive_process(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Move um processo terminal para o arquivo histórico."""
    process = await _locked_lifecycle_process(session, process_id, user_id)
    if not await has_process_review_access(session, user_id):
        raise AuthorizationError(
            'Apenas usuários com permissão de revisão podem '
            'arquivar processos.'
        )
    if await has_current_conflict(session, user_id, process_id):
        raise AuthorizationError(
            'Usuário com conflito de interesse vigente neste processo.'
        )
    if process.status not in {STATUS_CLOSED, STATUS_CANCELLED}:
        raise ConflictError(
            f'Processo em status {process.status!r} não pode ser arquivado.'
        )
    previous_status = process.status
    process.status = STATUS_ARCHIVED
    process.set_update_audit(user_id)
    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=user_id,
            event_type='PROCESS_ARCHIVED',
            context_data={
                'previous_status': previous_status,
                'result_status': STATUS_ARCHIVED,
            },
        )
    )
    return await _commit_lifecycle_change(session, process, user_id)


async def _cancel_pending_children(
    session: AsyncSession, process: ProcessInstance, user_id: UUID
) -> dict[str, int]:
    counts = {
        'phases': 0,
        'activities': 0,
        'activity_runs': 0,
        'tasks': 0,
        'evaluation_runs': 0,
    }
    phases = list(
        await session.scalars(
            select(Phase).where(Phase.process_instance_id == process.id)
        )
    )
    for phase in phases:
        if phase.status not in {'COMPLETED', STATUS_CANCELLED}:
            phase.status = STATUS_CANCELLED
            phase.set_update_audit(user_id)
            counts['phases'] += 1

    activities = list(
        await session.scalars(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process.id
            )
        )
    )
    for activity in activities:
        if activity.status not in {'COMPLETED', STATUS_CANCELLED}:
            activity.status = STATUS_CANCELLED
            activity.blocked_reason = 'Processo cancelado.'
            activity.set_update_audit(user_id)
            counts['activities'] += 1

    activity_ids = [activity.id for activity in activities]
    runs = list(
        await session.scalars(
            select(ActivityRun).where(
                ActivityRun.activity_instance_id.in_(activity_ids)
            )
        )
    )
    for run in runs:
        if run.status not in {'COMPLETED', STATUS_CANCELLED}:
            run.status = STATUS_CANCELLED
            run.completed_at = run.completed_at or utc_now()
            run.set_update_audit(user_id)
            counts['activity_runs'] += 1

    run_ids = [run.id for run in runs]
    tasks = list(
        await session.scalars(
            select(Task).where(Task.activity_run_id.in_(run_ids))
        )
    )
    for task in tasks:
        if task.status not in {'COMPLETED', STATUS_CANCELLED}:
            task.status = STATUS_CANCELLED
            task.completed_at = task.completed_at or utc_now()
            task.set_update_audit(user_id)
            counts['tasks'] += 1

    evaluation_runs = list(
        await session.scalars(
            select(EvaluationRun).where(
                EvaluationRun.process_instance_id == process.id
            )
        )
    )
    for evaluation_run in evaluation_runs:
        if evaluation_run.status not in {
            'completed',
            'failed',
            STATUS_CANCELLED,
        }:
            evaluation_run.status = STATUS_CANCELLED
            evaluation_run.finished_at = (
                evaluation_run.finished_at or utc_now()
            )
            evaluation_run.set_update_audit(user_id)
            counts['evaluation_runs'] += 1
    return counts


@dataclass
class TriageContext:
    process: ProcessInstance
    triage_act: ActivityInstance
    triage_run: ActivityRun
    justification: str
    user_id: UUID


def utc_now() -> datetime:
    return datetime.now(UTC)


def _compute_activity_due_date(
    *, run_started_at: datetime | None, sla_hours: int | None
) -> datetime | None:
    """Deriva o prazo (`Task.due_date`) de uma atividade a partir do SLA.

    Soma `sla_hours` a `run_started_at` sem normalizar para timezone-aware
    (Spec 024, FR-003): `run_started_at` chega aqui naive (mesmo padrão
    `datetime.utcnow()` de toda coluna de data deste projeto, sem
    `DateTime(timezone=True)`), e `Task.due_date` é uma coluna naive —
    misturar aware/naive nesta soma quebraria a persistência ou a
    comparação posterior. Sem `sla_hours` declarado, sem prazo — nunca um
    valor inferido (FR-002).
    """
    if sla_hours is None or run_started_at is None:
        return None
    return run_started_at + timedelta(hours=sla_hours)


async def _template_activity_data(
    session: AsyncSession, process_id: UUID, activity_key: str
) -> dict[str, Any]:
    """Busca a definição declarativa de uma atividade pelo processo.

    Lê da versão de template gravada na instância (nunca "a mais recente"),
    mesma fonte já usada por `_advance_dependent_activities` — preserva a
    imutabilidade de versão (Spec 004 FR-001/FR-002; Spec 024 FR-004) para
    `_open_new_submission_run`, único caminho restante que ainda resolve uma
    atividade pela chave em vez do motor genérico de dependências (a triagem
    passou a usar o motor genérico na Issue #22).
    """
    process = await session.get(ProcessInstance, process_id)
    if process is None:
        return {}
    template_version = await session.get(
        ProcessTemplateVersion, process.template_version_id
    )
    payload = template_version.definition_payload if template_version else {}
    for phase in payload.get('phases', []):
        for activity in phase.get('activities', []):
            if activity.get('key') == activity_key:
                return activity
    return {}


def _resolve_activity_cargo(a_data: dict[str, Any]) -> str:
    """Cargo declarado por uma atividade do template (Spec 018, FR-016).

    Falha alto e cedo (na instanciação/ativação)
    quando um template declara um `assigned_role` fora do vocabulário
    compartilhado com `Assignment.role_key` — em vez de aceitar string livre
    e deixar a inconsistência para ser descoberta depois.
    """
    cargo = a_data.get('assigned_role', 'proponent')
    if cargo not in ACTIVITY_CARGOS:
        raise ValidationError(
            f'Cargo de atividade inválido: {cargo!r}. Valores aceitos: '
            f'{sorted(ACTIVITY_CARGOS)}.'
        )
    return cargo


def resolve_activity_access(
    a_data: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Concessões de ver e editar de uma atividade do template (Spec 030).

    Sem `access`, o cargo responsável edita. Editar implica ver, e os cargos
    globais `admin` e `bracvam` sempre veem (FR-009, FR-012, FR-016). Falha
    alto quando não há cargo de edição ou quando um cargo está fora do
    vocabulário (FR-013).
    """
    key = a_data.get('key')
    access = a_data.get('access') or {}
    if 'edit' in access:
        edit = set(access['edit'] or [])
    else:
        edit = {_resolve_activity_cargo(a_data)}
    if not edit:
        raise ValidationError(
            f'Atividade {key!r} não concede edição a nenhum cargo.'
        )
    view = edit | set(access.get('view') or []) | GLOBAL_ACTIVITY_CARGOS
    unknown = sorted(view - ACTIVITY_CARGOS)
    if unknown:
        raise ValidationError(
            f'Atividade {key!r} concede acesso a cargo inválido: '
            f'{", ".join(unknown)}.'
        )
    return sorted(view), sorted(edit)


async def generate_process_code(session: AsyncSession) -> str:
    year = datetime.now(UTC).year
    return f'VAL-{year}-{secrets.token_hex(8)}'


async def _create_phases_and_activities(
    session: AsyncSession,
    process_id: UUID,
    payload: dict[str, Any],
    creator_id: UUID,
) -> tuple[dict[str, ActivityInstance], dict[str, dict[str, Any]]]:
    activity_map: dict[str, ActivityInstance] = {}
    activity_meta: dict[str, dict[str, Any]] = {}

    for p_data in payload.get('phases', []):
        is_first = p_data.get('order_index') == 1
        phase = Phase(
            process_instance_id=process_id,
            key=p_data['key'],
            name=p_data['name'],
            order_index=p_data.get('order_index', 1),
            status='IN_PROGRESS' if is_first else 'NOT_STARTED',
        )
        phase.set_creation_audit(creator_id)
        session.add(phase)
        await session.flush()

        for a_data in p_data.get('activities', []):
            act_key = a_data['key']
            act = ActivityInstance(
                process_instance_id=process_id,
                phase_id=phase.id,
                key=act_key,
                name=a_data['name'],
                order_index=a_data.get('order_index', 1),
                status='BLOCKED',
                blocked_reason=None,
                activity_type=a_data.get('activity_type', 'form'),
            )
            act.view_roles, act.edit_roles = resolve_activity_access(a_data)
            act.set_creation_audit(creator_id)
            session.add(act)
            await session.flush()
            activity_map[act_key] = act
            activity_meta[act_key] = a_data

    return activity_map, activity_meta


async def _init_first_activity(
    session: AsyncSession,
    act: ActivityInstance,
    a_data: dict[str, Any],
    creator_id: UUID,
) -> None:
    act.status = 'IN_PROGRESS'
    act.blocked_reason = None

    run = ActivityRun(
        activity_instance_id=act.id,
        run_number=1,
        status='IN_PROGRESS',
        execution_reason='Submissão inicial',
    )
    run.set_creation_audit(creator_id)
    session.add(run)
    await session.flush()

    task = Task(
        activity_run_id=run.id,
        title=f'Preencher {act.name}',
        # Sempre por cargo, nunca vinculada à pessoa que disparou a
        # submissão (Spec 018, FR-016/FR-017) — `created_by` (AuditMixin)
        # já registra quem criou; múltiplos proponentes podem coexistir.
        assigned_role=_resolve_activity_cargo(a_data),
        status='READY',
        due_date=_compute_activity_due_date(
            run_started_at=run.started_at,
            sla_hours=a_data.get('sla_hours'),
        ),
    )
    task.set_creation_audit(creator_id)
    session.add(task)

    f_key = a_data.get('form_template_key')
    if f_key:
        f_stmt = select(FormTemplate).where(
            FormTemplate.key == f_key, FormTemplate.deleted_at.is_(None)
        )
        f_template = (await session.execute(f_stmt)).scalar_one_or_none()
        if f_template:
            form_inst = FormInstance(
                form_template_id=f_template.id,
                activity_run_id=run.id,
                is_submitted=False,
            )
            form_inst.set_creation_audit(creator_id)
            session.add(form_inst)


async def instantiate_process(
    session: AsyncSession,
    template_version: ProcessTemplateVersion,
    title: str,
    creator_user_id: UUID,
) -> ProcessInstance:
    code = await generate_process_code(session)
    payload = template_version.definition_payload

    process = ProcessInstance(
        template_version_id=template_version.id,
        code=code,
        title=title,
        status=STATUS_OPEN,
        started_at=utc_now(),
    )
    process.set_creation_audit(creator_user_id)
    session.add(process)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise

    assignment = Assignment(
        process_instance_id=process.id,
        user_id=creator_user_id,
        role_key='proponent',
        assigned_by=creator_user_id,
    )
    assignment.set_creation_audit(creator_user_id)
    session.add(assignment)

    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=creator_user_id,
            event_type='PROCESS_CREATED',
            context_data={'code': code, 'title': title},
        )
    )
    session.add(
        AuditEvent(
            process_instance_id=process.id,
            user_id=creator_user_id,
            event_type='PARTICIPANT_ASSIGNED',
            context_data={
                'assignment_id': str(assignment.id),
                'participant_user_id': str(creator_user_id),
                'role_key': 'proponent',
                'laboratory_id': None,
                'result': 'success',
                'source': 'process_creation',
            },
        )
    )

    try:  # noqa: PLW0717
        act_map, act_meta = await _create_phases_and_activities(
            session, process.id, payload, creator_user_id
        )

        for act_key, a_data in act_meta.items():
            act = act_map[act_key]
            deps = a_data.get('dependencies', [])
            if not deps:
                await _init_first_activity(
                    session, act, a_data, creator_user_id
                )
            else:
                act.status = 'BLOCKED'
                act.blocked_reason = 'Aguardando atividades predecessoras.'
                for dep in deps:
                    req_key = dep.get('required_activity_key')
                    req_act = act_map.get(req_key) if req_key else None
                    dep_row = ActivityDependency(
                        dependent_activity_id=act.id,
                        required_activity_id=req_act.id if req_act else None,
                        required_status=dep.get(
                            'required_status', 'COMPLETED'
                        ),
                        condition_type=dep.get(
                            'condition_type', 'ACTIVITY_COMPLETED'
                        ),
                    )
                    dep_row.set_creation_audit(creator_user_id)
                    session.add(dep_row)

        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return process


AccessLevel = Literal['view', 'edit']


async def require_activity_access(
    session: AsyncSession,
    user_id: UUID,
    activity: ActivityInstance,
    level: AccessLevel,
) -> None:
    """Exige concessão do cargo do usuário na atividade (Spec 030, R6).

    Sem ver → "não encontrado", sem revelar a atividade (FR-017). Vê mas não
    edita → proibido (FR-018). Conflito de interesse vigente bloqueia a
    edição acima de qualquer concessão (FR-022).
    """
    cargos = await user_cargos(session, user_id, activity.process_instance_id)
    if not cargos & set(activity.view_roles):
        raise NotFoundError(f'Atividade {activity.key!r} não encontrada.')
    if level == 'view':
        return
    if await has_current_conflict(
        session, user_id, activity.process_instance_id
    ):
        raise AuthorizationError(
            'Usuário com conflito de interesse vigente neste processo.'
        )
    if not cargos & set(activity.edit_roles):
        raise AuthorizationError(
            f'Sem permissão para editar a atividade {activity.key!r}.'
        )


async def get_current_form_instance(
    session: AsyncSession,
    process_id: UUID,
    activity_key: str,
    user_id: UUID | None = None,
    access: AccessLevel = 'view',
) -> tuple[
    ActivityInstance,
    ActivityRun,
    FormInstance,
    FormTemplate,
    list[FormField],
]:
    if user_id is not None:
        process_exists = await session.scalar(
            select(ProcessInstance.id).where(
                ProcessInstance.id == process_id,
                ProcessInstance.deleted_at.is_(None),
            )
        )
        if process_exists is None:
            raise NotFoundError('Processo não encontrado.')

    stmt = (
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == activity_key,
            ActivityInstance.deleted_at.is_(None),
        )
        .options(
            selectinload(ActivityInstance.runs)
            .selectinload(ActivityRun.form_instances)
            .selectinload(FormInstance.values),
            selectinload(ActivityInstance.runs)
            .selectinload(ActivityRun.form_instances)
            .selectinload(FormInstance.reviews),
        )
    )
    act = (await session.execute(stmt)).scalar_one_or_none()
    if not act:
        raise NotFoundError(f'Atividade {activity_key!r} não encontrada.')
    if user_id is not None:
        await require_activity_access(session, user_id, act, access)

    runs = sorted(
        [r for r in act.runs if r.deleted_at is None],
        key=lambda x: x.run_number,
        reverse=True,
    )
    if not runs:
        raise NotFoundError(f'Sem execuções na atividade {activity_key!r}.')

    current_run = runs[0]
    form_instances = [
        fi for fi in current_run.form_instances if fi.deleted_at is None
    ]
    if not form_instances:
        raise NotFoundError(f'Sem formulário na atividade {activity_key!r}.')

    form_instance = form_instances[0]

    f_stmt = (
        select(FormTemplate)
        .where(
            FormTemplate.id == form_instance.form_template_id,
            FormTemplate.deleted_at.is_(None),
        )
        .options(selectinload(FormTemplate.fields))
    )
    template = (await session.execute(f_stmt)).scalar_one_or_none()
    if not template:
        raise NotFoundError('Template do formulário não encontrado.')

    fields = sorted(
        [f for f in template.fields if f.deleted_at is None],
        key=lambda x: x.order_index,
    )
    return act, current_run, form_instance, template, fields


async def get_current_activity_run(
    session: AsyncSession,
    process_id: UUID,
    activity_key: str,
    user_id: UUID | None = None,
    access: AccessLevel = 'view',
) -> tuple[ActivityInstance, ActivityRun]:
    """Obtém a ActivityInstance e sua execução mais recente ativa.

    Não exige a presença de FormInstance.
    """
    if user_id is not None:
        process_exists = await session.scalar(
            select(ProcessInstance.id).where(
                ProcessInstance.id == process_id,
                ProcessInstance.deleted_at.is_(None),
            )
        )
        if process_exists is None:
            raise NotFoundError('Processo não encontrado.')

    stmt = (
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == activity_key,
            ActivityInstance.deleted_at.is_(None),
        )
        .options(
            selectinload(ActivityInstance.runs),
        )
    )
    act = (await session.execute(stmt)).scalar_one_or_none()
    if not act:
        raise NotFoundError(f'Atividade {activity_key!r} não encontrada.')
    if user_id is not None:
        await require_activity_access(session, user_id, act, access)

    runs = sorted(
        [r for r in act.runs if r.deleted_at is None],
        key=lambda x: x.run_number,
        reverse=True,
    )
    if not runs:
        raise NotFoundError(f'Sem execuções na atividade {activity_key!r}.')

    return act, runs[0]


def _set_value_on_field(
    form_value: FormValue, field_type: str, val: Any
) -> None:
    if field_type in {'text', 'textarea'}:
        form_value.text_value = str(val) if val is not None else None
    elif field_type == 'integer':
        form_value.numeric_value = int(val) if val is not None else None
    elif field_type == 'float':
        form_value.numeric_value = float(val) if val is not None else None
    elif field_type == 'boolean':
        form_value.boolean_value = bool(val) if val is not None else None
    elif field_type == 'date':
        if isinstance(val, str):
            form_value.date_value = date.fromisoformat(val)
        elif isinstance(val, date):
            form_value.date_value = val
        else:
            form_value.date_value = None
    elif field_type == 'file_upload':
        # Anexos vivem em `file_attachment_id`, gerido pela rota de anexo.
        return
    else:
        form_value.json_value = val


def _clear_form_value(form_value: FormValue) -> None:
    """Limpa todas as colunas de armazenamento antes de gravar um valor."""
    form_value.text_value = None
    form_value.numeric_value = None
    form_value.boolean_value = None
    form_value.date_value = None
    form_value.json_value = None


def _form_value_to_python(  # noqa: PLR0911
    form_value: FormValue, field_type: str
) -> Any:
    if field_type in {'text', 'textarea'}:
        return form_value.text_value
    if field_type == 'integer':
        return (
            int(form_value.numeric_value)
            if form_value.numeric_value is not None
            else None
        )
    if field_type == 'float':
        return (
            float(form_value.numeric_value)
            if form_value.numeric_value is not None
            else None
        )
    if field_type == 'boolean':
        return form_value.boolean_value
    if field_type == 'date':
        return (
            form_value.date_value.isoformat()
            if form_value.date_value
            else None
        )
    if field_type == 'file_upload':
        return None
    return form_value.json_value


def _draft_validation_error(
    field_key: str, code: str, message: str
) -> dict[str, str]:
    return {'field_key': field_key, 'code': code, 'message': message}


def _configured_option_values(options: Any) -> list[Any]:
    if not isinstance(options, list):
        return []
    result: list[Any] = []
    for option in options:
        if isinstance(option, dict) and 'value' in option:
            result.append(option['value'])
        elif isinstance(option, (str, int, float, bool)):
            result.append(option)
    return result


def _validate_draft_values(  # noqa: PLR0912
    fields: list[FormField], values_dict: dict[str, Any]
) -> None:
    field_map = {field.field_key: field for field in fields}
    errors: list[dict[str, str]] = []

    for field_key, value in values_dict.items():
        field = field_map.get(field_key)
        if field is None:
            errors.append(
                _draft_validation_error(
                    field_key,
                    'unknown_field',
                    (
                        f"O campo '{field_key}' não pertence à definição "
                        'do formulário.'
                    ),
                )
            )
            continue

        field_type = field.field_type
        if field_type == 'file_upload':
            errors.append(
                _draft_validation_error(
                    field_key,
                    'file_upload_uses_attachment_endpoint',
                    (
                        'Anexos são enviados pela rota dedicada '
                        '.../form/fields/{field_key}/attachment, não no '
                        'corpo do rascunho.'
                    ),
                )
            )
            continue

        if value is None:
            continue

        compatible = True
        code = 'invalid_type'
        if field_type in {'text', 'textarea'}:
            compatible = isinstance(value, str)
        elif field_type == 'integer':
            compatible = isinstance(value, int) and not isinstance(value, bool)
        elif field_type == 'float':
            compatible = isinstance(value, (int, float)) and not isinstance(
                value, bool
            )
        elif field_type == 'boolean':
            compatible = isinstance(value, bool)
        elif field_type == 'date':
            if isinstance(value, str):
                try:
                    compatible = date.fromisoformat(value).isoformat() == value
                except ValueError:
                    compatible = False
            else:
                compatible = False
        elif field_type == 'select':
            compatible = any(
                value == option
                for option in _configured_option_values(field.options)
            )
            code = 'invalid_option'
        else:
            compatible = False
            code = 'unsupported_field_type'

        if not compatible:
            errors.append(
                _draft_validation_error(
                    field_key,
                    code,
                    f"Valor incompatível com o tipo '{field_type}'.",
                )
            )
            continue

        if field_type in {'integer', 'float'}:
            rules = field.validation_rules or {}
            minimum = rules.get('min')
            maximum = rules.get('max')
            if minimum is not None and value < minimum:
                errors.append(
                    _draft_validation_error(
                        field_key,
                        'min_value',
                        f'O valor deve ser maior ou igual a {minimum}.',
                    )
                )
            if maximum is not None and value > maximum:
                errors.append(
                    _draft_validation_error(
                        field_key,
                        'max_value',
                        f'O valor deve ser menor ou igual a {maximum}.',
                    )
                )

    if errors:
        raise ValidationError(
            'Valores de formulário inválidos.', errors=errors
        )


def _validate_submission_update_values(
    fields: list[FormField],
    values_dict: dict[str, Any],
    *,
    require_complete: bool,
) -> None:
    """Valida valores de PUT/PATCH sem alterar a sessão."""
    _validate_draft_values(fields, values_dict)

    non_file_fields = [f for f in fields if f.field_type != 'file_upload']
    errors: list[dict[str, str]] = []
    if require_complete:
        for field in non_file_fields:
            if field.field_key not in values_dict:
                errors.append(
                    _draft_validation_error(
                        field.field_key,
                        'required_field',
                        (
                            f"O campo '{field.field_key}' deve ser informado "
                            'no PUT completo.'
                        ),
                    )
                )

    for field in non_file_fields:
        if not field.is_required or field.field_key not in values_dict:
            continue
        value = values_dict[field.field_key]
        missing = value is None or (
            isinstance(value, str) and not value.strip()
        )
        if missing:
            errors.append(
                _draft_validation_error(
                    field.field_key,
                    'required_field',
                    f"O campo '{field.field_key}' é obrigatório.",
                )
            )

    if errors:
        raise ValidationError(
            'Valores de formulário incompletos.', errors=errors
        )


async def _load_editable_submission(
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
) -> tuple[
    ProcessInstance,
    ActivityInstance,
    ActivityRun,
    FormInstance,
    FormTemplate,
    list[FormField],
]:
    """Carrega a submissão atual após autorização e guarda de estado."""
    process = await session.scalar(
        select(ProcessInstance).where(
            ProcessInstance.id == process_id,
            ProcessInstance.deleted_at.is_(None),
        )
    )
    if process is None:
        raise NotFoundError('Processo não encontrado.')

    submission_act = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'proposal_submission',
            ActivityInstance.deleted_at.is_(None),
        )
    )
    if submission_act is None:
        raise NotFoundError('Processo não encontrado.')
    await require_activity_access(session, user_id, submission_act, 'edit')
    if process.status != STATUS_OPEN:
        raise ConflictError(
            f'Processo em status {process.status!r} não permite edição.'
        )

    (
        act,
        run,
        form_instance,
        template,
        fields,
    ) = await get_current_form_instance(
        session, process_id, 'proposal_submission'
    )
    if form_instance.is_submitted:
        raise ConflictError('O formulário desta execução já foi submetido.')
    return process, act, run, form_instance, template, fields


async def _serialize_submission_values(
    session: AsyncSession,
    form_instance_id: UUID,
    fields: list[FormField],
) -> dict[str, Any]:
    field_map = {
        field.id: field
        for field in fields
        if field.field_type != 'file_upload'
    }
    values = await session.scalars(
        select(FormValue).where(
            FormValue.form_instance_id == form_instance_id,
            FormValue.deleted_at.is_(None),
        )
    )
    return {
        field_map[value.form_field_id].field_key: _form_value_to_python(
            value, field_map[value.form_field_id].field_type
        )
        for value in values
        if value.form_field_id in field_map
    }


async def _submission_response(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process: ProcessInstance,
    run: ActivityRun,
    form_instance: FormInstance,
    template: FormTemplate,
    fields: list[FormField],
) -> dict[str, Any]:
    process_template = await session.get(
        ProcessTemplateVersion, process.template_version_id
    )
    return {
        'id': process.id,
        'title': process.title,
        'status': process.status,
        'template_key': template.key,
        'version_number': process_template.version_number
        if process_template is not None
        else 1,
        'run_number': run.run_number,
        'form_instance_id': form_instance.id,
        'is_submitted': form_instance.is_submitted,
        'values': await _serialize_submission_values(
            session, form_instance.id, fields
        ),
    }


async def update_process_submission(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    process_id: UUID,
    user_id: UUID,
    *,
    mode: str,
    title: str | None,
    values_dict: dict[str, Any] | None,
) -> dict[str, Any]:
    """Atualiza título e valores do rascunho em uma única transação."""
    (
        process,
        _act,
        run,
        form_instance,
        template,
        fields,
    ) = await _load_editable_submission(session, process_id, user_id)
    values_dict = values_dict or {}
    _validate_submission_update_values(
        fields,
        values_dict,
        require_complete=mode == 'PUT',
    )

    field_map = {field.field_key: field for field in fields}
    active_values = {
        value.form_field_id: value
        for value in await session.scalars(
            select(FormValue).where(
                FormValue.form_instance_id == form_instance.id,
                FormValue.deleted_at.is_(None),
            )
        )
    }
    keys_to_update = (
        [
            field.field_key
            for field in fields
            if field.field_type != 'file_upload'
        ]
        if mode == 'PUT'
        else list(values_dict)
    )
    for field_key in keys_to_update:
        field = field_map[field_key]
        form_value = active_values.get(field.id)
        if form_value is None:
            form_value = FormValue(
                form_instance_id=form_instance.id,
                form_field_id=field.id,
            )
            form_value.set_creation_audit(user_id)
            session.add(form_value)
        else:
            form_value.set_update_audit(user_id)
        _clear_form_value(form_value)
        _set_value_on_field(
            form_value, field.field_type, values_dict[field_key]
        )

    changed_attributes = list(keys_to_update)
    if title is not None:
        process.title = title
        process.set_update_audit(user_id)
        changed_attributes.insert(0, 'title')

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=run.id,
            user_id=user_id,
            event_type='SUBMISSION_UPDATED',
            context_data={
                'mode': mode,
                'operation': mode,
                'attributes': sorted(set(changed_attributes)),
                'fields': sorted(set(keys_to_update)),
            },
        )
    )
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return await _submission_response(
        session, process, run, form_instance, template, fields
    )


async def _visible_process(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> ProcessInstance:
    stmt = select(ProcessInstance).where(
        ProcessInstance.id == process_id,
        ProcessInstance.deleted_at.is_(None),
    )
    visibility = await process_visibility_clause(session, user_id)
    if visibility is not None:
        stmt = stmt.where(visibility)
    process = await session.scalar(stmt)
    if process is None:
        raise NotFoundError('Processo não encontrado.')
    return process


async def _visible_submission(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> None:
    """Exige ver a submissão, além do cabeçalho do processo (Spec 030)."""
    await _visible_process(session, process_id, user_id)
    submission_act = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'proposal_submission',
            ActivityInstance.deleted_at.is_(None),
        )
    )
    if submission_act is None:
        raise NotFoundError('Processo não encontrado.')
    await require_activity_access(session, user_id, submission_act, 'view')


async def list_returned_submission_versions(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> list[dict[str, Any]]:
    """Projeta versões submetidas que foram devolvidas para revisão."""
    await _visible_submission(session, process_id, user_id)
    revision_events = list(
        await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.process_instance_id == process_id,
                AuditEvent.event_type == 'REVISION_REQUESTED',
                AuditEvent.deleted_at.is_(None),
            )
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        )
    )
    returned_by_run: dict[int, AuditEvent] = {}
    for event in revision_events:
        context = event.context_data or {}
        try:
            previous_run = int(context['new_run_number']) - 1
        except KeyError, TypeError, ValueError:
            continue
        if previous_run > 0 and previous_run not in returned_by_run:
            returned_by_run[previous_run] = event

    if not returned_by_run:
        return []
    return await _load_submission_version_rows(
        session, process_id, returned_by_run
    )


async def get_returned_submission_version(
    session: AsyncSession,
    process_id: UUID,
    run_number: int,
    user_id: UUID,
) -> dict[str, Any]:
    await _visible_submission(session, process_id, user_id)
    revision_events = list(
        await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.process_instance_id == process_id,
                AuditEvent.event_type == 'REVISION_REQUESTED',
                AuditEvent.deleted_at.is_(None),
            )
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        )
    )
    returned_by_run: dict[int, AuditEvent] = {}
    for event in revision_events:
        context = event.context_data or {}
        try:
            previous_run = int(context['new_run_number']) - 1
        except KeyError, TypeError, ValueError:
            continue
        if previous_run > 0 and previous_run not in returned_by_run:
            returned_by_run[previous_run] = event
    if run_number not in returned_by_run:
        raise NotFoundError('Versão de submissão não encontrada.')
    rows = await _load_submission_version_rows(
        session, process_id, {run_number: returned_by_run[run_number]}
    )
    if not rows:
        raise NotFoundError('Versão de submissão não encontrada.')
    return rows[0]


async def _load_submission_version_rows(
    session: AsyncSession,
    process_id: UUID,
    returned_by_run: dict[int, AuditEvent],
) -> list[dict[str, Any]]:
    act = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'proposal_submission',
            ActivityInstance.deleted_at.is_(None),
        )
    )
    if act is None:
        return []

    runs = list(
        await session.scalars(
            select(ActivityRun)
            .where(
                ActivityRun.activity_instance_id == act.id,
                ActivityRun.run_number.in_(returned_by_run.keys()),
                ActivityRun.status == 'COMPLETED',
                ActivityRun.deleted_at.is_(None),
            )
            .options(
                selectinload(ActivityRun.form_instances),
                selectinload(ActivityRun.artifacts),
            )
            .order_by(ActivityRun.run_number.desc())
        )
    )
    result: list[dict[str, Any]] = []
    for run in runs:
        form_instance = next(
            (
                item
                for item in run.form_instances
                if item.deleted_at is None and item.is_submitted
            ),
            None,
        )
        artifact = next(
            (
                item
                for item in run.artifacts
                if item.key == 'proposal_dossier' and item.deleted_at is None
            ),
            None,
        )
        if form_instance is None or artifact is None:
            continue
        metadata = artifact.metadata_payload or {}
        returned_event = returned_by_run[run.run_number]
        context = returned_event.context_data or {}
        submitted_at = form_instance.submitted_at or run.completed_at
        if submitted_at is None:
            continue
        result.append({
            'run_number': run.run_number,
            'submitted_at': submitted_at,
            'returned_at': returned_event.occurred_at,
            'title': metadata.get('title', ''),
            'return_justification': str(context.get('justification') or ''),
            'values': metadata.get('values') or {},
            'attachments': metadata.get('attachments') or [],
        })
    return result


async def is_artifact_referenced_by_submitted_form(
    session: AsyncSession, artifact_id: UUID
) -> bool:
    """Indica se um anexo ainda compõe algum snapshot submetido."""
    return (
        await session.scalar(
            select(FormValue.id)
            .join(FormInstance, FormInstance.id == FormValue.form_instance_id)
            .where(
                FormValue.file_attachment_id == artifact_id,
                FormValue.deleted_at.is_(None),
                FormInstance.is_submitted.is_(True),
                FormInstance.deleted_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )


async def save_form_values_draft(
    session: AsyncSession,
    process_id: UUID,
    activity_key: str,
    values_dict: dict[str, Any],
    user_id: UUID,
) -> FormInstance:
    await ensure_process_mutable(session, process_id)
    _, current_run, form_instance, _, fields = await get_current_form_instance(
        session, process_id, activity_key, user_id, 'edit'
    )

    if form_instance.is_submitted:
        raise ConflictError('Formulário já submetido.')

    _validate_draft_values(fields, values_dict)

    field_map = {f.field_key: f for f in fields}
    val_stmt = select(FormValue).where(
        FormValue.form_instance_id == form_instance.id,
        FormValue.deleted_at.is_(None),
    )
    existing_vals = {
        v.form_field_id: v for v in (await session.execute(val_stmt)).scalars()
    }

    for f_key, val in values_dict.items():
        field = field_map[f_key]
        fv = existing_vals.get(field.id)
        if fv is None:
            fv = FormValue(
                form_instance_id=form_instance.id,
                form_field_id=field.id,
            )
            fv.set_creation_audit(user_id)
            session.add(fv)
        else:
            fv.set_update_audit(user_id)

        _set_value_on_field(fv, field.field_type, val)

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=current_run.id,
            user_id=user_id,
            event_type='FORM_DRAFT_SAVED',
            context_data={'activity_key': activity_key},
        )
    )
    await session.commit()
    return form_instance


def _validate_form_values(
    fields: list[FormField], values_dict: dict[str, Any]
) -> None:
    errors = []
    for field in fields:
        if field.field_type == 'file_upload':
            # Anexos são validados por `_required_attachment_errors`, contra o
            # vínculo `FormValue.file_attachment_id`, não contra `values_dict`.
            continue
        val = values_dict.get(field.field_key)
        missing = val is None or (isinstance(val, str) and not val.strip())
        if field.is_required and (
            field.field_key not in values_dict or missing
        ):
            errors.append(
                f"O campo '{field.label}' ({field.field_key}) é obrigatório."
            )
    if errors:
        raise ValidationError('; '.join(errors))


async def _required_attachment_errors(
    session: AsyncSession,
    form_instance_id: UUID,
    fields: list[FormField],
) -> list[dict[str, str]]:
    required = {
        f.id: f
        for f in fields
        if f.field_type == 'file_upload' and f.is_required
    }
    if not required:
        return []
    rows = (
        (
            await session.execute(
                select(FormValue).where(
                    FormValue.form_instance_id == form_instance_id,
                    FormValue.form_field_id.in_(required.keys()),
                    FormValue.deleted_at.is_(None),
                    FormValue.file_attachment_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    satisfied = {fv.form_field_id for fv in rows}
    return [
        {
            'field_key': field.field_key,
            'code': 'attachment_required',
            'message': f"O anexo '{field.label}' é obrigatório.",
        }
        for field_id, field in required.items()
        if field_id not in satisfied
    ]


async def _mark_submitted_attachments(
    session: AsyncSession,
    form_instance_id: UUID,
    fields: list[FormField],
    user_id: UUID,
) -> list[dict[str, Any]]:
    file_fields = {
        f.id: f.field_key for f in fields if f.field_type == 'file_upload'
    }
    if not file_fields:
        return []
    form_values = (
        (
            await session.execute(
                select(FormValue).where(
                    FormValue.form_instance_id == form_instance_id,
                    FormValue.form_field_id.in_(file_fields.keys()),
                    FormValue.deleted_at.is_(None),
                    FormValue.file_attachment_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not form_values:
        return []
    by_artifact = {
        fv.file_attachment_id: file_fields[fv.form_field_id]
        for fv in form_values
    }
    artifacts = (
        (
            await session.execute(
                select(Artifact).where(
                    Artifact.id.in_(by_artifact.keys()),
                    Artifact.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    manifest: list[dict[str, Any]] = []
    for artifact in artifacts:
        artifact.status = 'SUBMITTED'
        artifact.set_update_audit(user_id)
        meta = artifact.metadata_payload or {}
        manifest.append({
            'field_key': by_artifact[artifact.id],
            'artifact_id': str(artifact.id),
            'filename': meta.get('original_filename') or artifact.name,
            'size': artifact.file_size,
            'mime_type': artifact.mime_type,
            'checksum': artifact.checksum_sha256,
        })
    return manifest


async def _save_submitted_values(
    session: AsyncSession,
    form_instance_id: UUID,
    fields: list[FormField],
    values_dict: dict[str, Any],
    user_id: UUID,
) -> None:
    field_map = {f.field_key: f for f in fields}
    val_stmt = select(FormValue).where(
        FormValue.form_instance_id == form_instance_id,
        FormValue.deleted_at.is_(None),
    )
    existing_vals = {
        v.form_field_id: v for v in (await session.execute(val_stmt)).scalars()
    }

    for f_key, val in values_dict.items():
        if f_key not in field_map:
            continue
        field = field_map[f_key]
        if field.field_type == 'file_upload':
            continue
        fv = existing_vals.get(field.id)
        if fv is None:
            fv = FormValue(
                form_instance_id=form_instance_id,
                form_field_id=field.id,
            )
            fv.set_creation_audit(user_id)
            session.add(fv)
        else:
            fv.set_update_audit(user_id)

        _set_value_on_field(fv, field.field_type, val)


async def _dependency_satisfied(
    session: AsyncSession, dependency: ActivityDependency
) -> bool:
    if dependency.required_activity_id is None:
        return True
    required_act = await session.get(
        ActivityInstance, dependency.required_activity_id
    )
    return (
        required_act is not None
        and required_act.status == dependency.required_status
    )


async def _activate_activity(  # noqa: PLR0913, PLR0917
    session: AsyncSession,
    act: ActivityInstance,
    a_data: dict[str, Any],
    user_id: UUID,
    reason: str,
    task_title: str | None = None,
) -> ActivityRun:
    """Ativa uma atividade BLOCKED cuja(s) dependência(s) já foram satisfeitas.

    Generaliza o que ``_init_first_activity`` faz para a primeira atividade
    (sem dependências), permitindo qualquer ``activity_type`` — cria
    ``FormInstance`` apenas quando a atividade declara ``form_template_key``
    (Spec 017, FR-005). ``run_number`` é derivado do máximo já existente para
    a atividade (não fixo em 1): diferente da ativação inicial, uma atividade
    dependente pode ser bloqueada e desbloqueada mais de uma vez (ex.
    diligência de triagem, Issue #22) — cada ciclo precisa da sua própria
    execução, nunca reaproveitando a anterior. ``task_title`` permite ao
    chamador preservar um texto de tarefa já em uso (em vez de ``act.name``)
    quando a atividade tinha, antes da Issue #22, um caminho de ativação
    bespoke com um título próprio.
    """
    act.status = 'IN_PROGRESS'
    act.blocked_reason = None
    act.set_update_audit(user_id)

    phase = await session.get(Phase, act.phase_id)
    if phase is not None and phase.status == 'NOT_STARTED':
        phase.status = 'IN_PROGRESS'
        phase.set_update_audit(user_id)

    prev_runs_stmt = select(ActivityRun.run_number).where(
        ActivityRun.activity_instance_id == act.id,
        ActivityRun.deleted_at.is_(None),
    )
    prev_run_numbers = (await session.execute(prev_runs_stmt)).scalars().all()
    next_run_number = max(prev_run_numbers, default=0) + 1

    run = ActivityRun(
        activity_instance_id=act.id,
        run_number=next_run_number,
        status='IN_PROGRESS',
        execution_reason=reason,
    )
    run.set_creation_audit(user_id)
    session.add(run)
    await session.flush()

    task = Task(
        activity_run_id=run.id,
        title=task_title or act.name,
        assigned_role=_resolve_activity_cargo(a_data),
        status='READY',
        due_date=_compute_activity_due_date(
            run_started_at=run.started_at,
            sla_hours=a_data.get('sla_hours'),
        ),
    )
    task.set_creation_audit(user_id)
    session.add(task)

    f_key = a_data.get('form_template_key')
    if f_key:
        f_stmt = select(FormTemplate).where(
            FormTemplate.key == f_key, FormTemplate.deleted_at.is_(None)
        )
        f_template = (await session.execute(f_stmt)).scalar_one_or_none()
        if f_template:
            form_inst = FormInstance(
                form_template_id=f_template.id,
                activity_run_id=run.id,
                is_submitted=False,
            )
            form_inst.set_creation_audit(user_id)
            session.add(form_inst)

    return run


async def _advance_dependent_activities(
    session: AsyncSession,
    process: ProcessInstance,
    completed_act: ActivityInstance,
    user_id: UUID,
    task_titles: dict[str, str] | None = None,
) -> None:
    """Desbloqueia atividades cuja dependência acabou de ser satisfeita.

    Lê de volta as linhas de ``ActivityDependency`` já gravadas na
    instanciação (Spec 004) para decidir avanço, em vez de uma chave de
    atividade hardcoded — mecanismo mínimo exigido pela Spec 017 (FR-005,
    User Story 2) para que fases futuras não precisem de uma função dedicada
    no motor a cada nova atividade declarada.

    ``task_titles`` (chave = ``activity_key``) permite preservar um título de
    tarefa específico para uma atividade cujo caminho de ativação era, antes
    da Issue #22, bespoke (ex. ``triage_evaluation``) — sem isso, toda
    atividade destravada por aqui usa ``act.name`` como título (Spec 017).
    """
    dep_stmt = select(ActivityDependency).where(
        ActivityDependency.required_activity_id == completed_act.id,
        ActivityDependency.deleted_at.is_(None),
    )
    dependencies = (await session.execute(dep_stmt)).scalars().all()
    if not dependencies:
        return

    template_version = await session.get(
        ProcessTemplateVersion, process.template_version_id
    )
    payload = template_version.definition_payload if template_version else {}
    activities_by_key = {
        a['key']: a
        for p in payload.get('phases', [])
        for a in p.get('activities', [])
    }

    seen_dependent_ids: set[UUID] = set()
    for dependency in dependencies:
        if dependency.dependent_activity_id in seen_dependent_ids:
            continue
        seen_dependent_ids.add(dependency.dependent_activity_id)

        dependent_act = await session.get(
            ActivityInstance, dependency.dependent_activity_id
        )
        if dependent_act is None or dependent_act.status != 'BLOCKED':
            continue

        all_deps_stmt = select(ActivityDependency).where(
            ActivityDependency.dependent_activity_id == dependent_act.id,
            ActivityDependency.deleted_at.is_(None),
        )
        all_deps = (await session.execute(all_deps_stmt)).scalars().all()
        satisfied = all([
            await _dependency_satisfied(session, d) for d in all_deps
        ])
        if not satisfied:
            continue

        a_data = activities_by_key.get(dependent_act.key, {})
        run = await _activate_activity(
            session,
            dependent_act,
            a_data,
            user_id,
            reason=(
                'Fase liberada automaticamente após conclusão da '
                f'dependência {completed_act.key!r}.'
            ),
            task_title=(task_titles or {}).get(dependent_act.key),
        )

        session.add(
            AuditEvent(
                process_instance_id=process.id,
                activity_run_id=run.id,
                user_id=user_id,
                event_type='ACTIVITY_UNBLOCKED',
                context_data={
                    'activity_key': dependent_act.key,
                    'activity_type': dependent_act.activity_type,
                    'unblocked_by': completed_act.key,
                },
            )
        )


async def _complete_activity_run(
    session: AsyncSession,
    run: ActivityRun,
    act: ActivityInstance,
    user_id: UUID,
) -> None:
    """Conclui a execução atual de uma atividade e suas tarefas.

    Ponto único para o efeito hoje duplicado em ``submit_proposal_form`` e
    ``execute_triage_decision`` (Issue #22): marcar a execução, a atividade e
    todas as suas tarefas como ``COMPLETED``. Não destrava dependentes — isso
    fica a cargo do chamador, via ``_advance_dependent_activities``, porque
    nem toda conclusão avança algo no mesmo instante (ex. triagem rejeitada).
    """
    run.status = 'COMPLETED'
    run.completed_at = utc_now()
    run.set_update_audit(user_id)

    act.status = 'COMPLETED'
    act.set_update_audit(user_id)

    t_stmt = select(Task).where(
        Task.activity_run_id == run.id, Task.deleted_at.is_(None)
    )
    for t in (await session.execute(t_stmt)).scalars().all():
        t.status = 'COMPLETED'
        t.completed_at = utc_now()
        t.set_update_audit(user_id)


async def _find_role_assignment_activity(
    session: AsyncSession, process: ProcessInstance, role_key: str
) -> ActivityInstance | None:
    """Resolve a `ActivityInstance` de `role_assignment` do papel, se houver.

    Extraído de `_maybe_close_role_assignment_activity` para ser reaproveitado
    também por `invite_service.resend_invite`/`revoke_invite` (FR-012/FR-013:
    ambos precisam saber se a etapa já se encerrou, não só o estado do
    próprio convite).
    """
    version = await session.get(
        ProcessTemplateVersion, process.template_version_id
    )
    payload = version.definition_payload if version else {}
    activity_key = next(
        (
            a['key']
            for p in payload.get('phases', [])
            for a in p.get('activities', [])
            if a.get('activity_type') == 'role_assignment'
            and a.get('target_role_key') == role_key
        ),
        None,
    )
    if activity_key is None:
        return None

    return await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process.id,
            ActivityInstance.key == activity_key,
            ActivityInstance.deleted_at.is_(None),
        )
    )


async def _maybe_close_role_assignment_activity(
    session: AsyncSession,
    process: ProcessInstance,
    role_key: str,
    user_id: UUID,
) -> None:
    """Fecha a etapa de atribuição de cargo do papel, se aplicável (Spec 028).

    Chamado ao final de toda designação criada (direta, Spec 006, ou por
    aceite de convite). Reaproveita ``_complete_activity_run`` +
    ``_advance_dependent_activities`` (Spec 026) — não existe um endpoint
    "concluir atividade" dedicado (research.md R4). Sempre no-op silencioso
    quando não há nada a fechar: papel sem etapa ``role_assignment``
    declarada na versão do template desta instância, etapa já ``COMPLETED``,
    etapa ainda ``BLOCKED`` (sem execução), ou convite ``pending`` restante
    para o papel (FR-017) — nesse último caso a etapa só fecha quando o
    último convite pendente for aceito ou revogado.
    """
    act = await _find_role_assignment_activity(session, process, role_key)
    if act is None or act.status == 'COMPLETED':
        return

    run = await session.scalar(
        select(ActivityRun)
        .where(
            ActivityRun.activity_instance_id == act.id,
            ActivityRun.deleted_at.is_(None),
        )
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
    )
    if run is None:
        return

    pending_invite = await session.scalar(
        select(RoleAssignmentInvite.id).where(
            RoleAssignmentInvite.process_instance_id == process.id,
            RoleAssignmentInvite.role_key == role_key,
            RoleAssignmentInvite.status == 'pending',
            RoleAssignmentInvite.deleted_at.is_(None),
        )
    )
    if pending_invite is not None:
        return

    await _complete_activity_run(session, run, act, user_id)
    await _advance_dependent_activities(session, process, act, user_id)


async def submit_proposal_form(  # noqa: PLR0914, PLR0915
    session: AsyncSession,
    process_id: UUID,
    activity_key: str,
    values_dict: dict[str, Any],
    user_id: UUID,
) -> tuple[ActivityInstance, ActivityRun, Artifact, EvaluationRun | None]:
    await ensure_process_mutable(session, process_id)
    (
        act,
        current_run,
        form_inst,
        template,
        fields,
    ) = await get_current_form_instance(
        session, process_id, activity_key, user_id, 'edit'
    )

    if form_inst.is_submitted:
        raise ConflictError('O formulário desta execução já foi submetido.')

    _validate_form_values(fields, values_dict)
    attachment_errors = await _required_attachment_errors(
        session, form_inst.id, fields
    )
    if attachment_errors:
        raise ValidationError(
            'Anexos obrigatórios ausentes.', errors=attachment_errors
        )
    await _save_submitted_values(
        session, form_inst.id, fields, values_dict, user_id
    )
    attachments_manifest = await _mark_submitted_attachments(
        session, form_inst.id, fields, user_id
    )

    form_inst.is_submitted = True
    form_inst.submitted_at = utc_now()
    form_inst.set_update_audit(user_id)

    await _complete_activity_run(session, current_run, act, user_id)

    p_stmt = select(ProcessInstance).where(ProcessInstance.id == process_id)
    process = (await session.execute(p_stmt)).scalar_one()

    doc_name = (
        f'Dossiê de Submissão - {act.name} (Run #{current_run.run_number})'
    )
    artifact = Artifact(
        process_instance_id=process_id,
        activity_run_id=current_run.id,
        key='proposal_dossier',
        name=doc_name,
        status='SUBMITTED',
        metadata_payload={
            'form_key': template.key,
            'values': await _serialize_submission_values(
                session, form_inst.id, fields
            ),
            'attachments': attachments_manifest,
            'title': process.title,
        },
    )
    artifact.set_creation_audit(user_id)
    session.add(artifact)

    assignment_stmt = select(EvaluationAssignment.id).where(
        EvaluationAssignment.form_template_id == template.id,
        EvaluationAssignment.enabled.is_(True),
        EvaluationAssignment.deleted_at.is_(None),
    )
    has_assignments = (
        await session.execute(assignment_stmt)
    ).first() is not None

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=current_run.id,
            user_id=user_id,
            event_type='SUBMISSION_SUBMITTED',
            context_data={'run_number': current_run.run_number},
        )
    )

    pending_run: EvaluationRun | None = None
    if has_assignments:
        pending_run = EvaluationRun(
            process_instance_id=process_id,
            activity_run_id=current_run.id,
            form_instance_id=form_inst.id,
        )
        pending_run.set_creation_audit(user_id)
        session.add(pending_run)

        # A submissão fica travada (formulário enviado) aguardando a
        # pré-avaliação assíncrona; o roteamento definitivo ocorre em
        # `pre_evaluation_service._execute`.
        process.set_update_audit(user_id)

        triage_stmt = select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'triage_evaluation',
            ActivityInstance.deleted_at.is_(None),
        )
        triage_act = (await session.execute(triage_stmt)).scalar_one_or_none()
        if triage_act:
            triage_act.blocked_reason = (
                'Aguardando pré-avaliação automática por IA.'
            )
            triage_act.set_update_audit(user_id)

        session.add(
            AuditEvent(
                process_instance_id=process_id,
                activity_run_id=current_run.id,
                user_id=user_id,
                event_type='AI_PRE_EVALUATION_STARTED',
                context_data={'run_number': current_run.run_number},
            )
        )
    else:
        # Sem avaliações por IA associadas: segue direto para a triagem com
        # relatório de pré-avaliação vazio (Spec 013 FR-027).
        await _advance_dependent_activities(
            session,
            process,
            act,
            user_id,
            task_titles={'triage_evaluation': TRIAGE_TASK_TITLE},
        )
        process.set_update_audit(user_id)

    await session.commit()
    return act, current_run, artifact, pending_run


async def _open_triage_run(
    session: AsyncSession, process_id: UUID, user_id: UUID
) -> tuple[ActivityInstance, ActivityRun]:
    """Execução aberta da triagem, com concessão de edição (Spec 030, R7).

    Substitui o antigo status de processo `TRIAGE`: a triagem só aceita
    avaliação e decisão enquanto a atividade tem execução em andamento.
    """
    act = await session.scalar(
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'triage_evaluation',
            ActivityInstance.deleted_at.is_(None),
        )
        .options(selectinload(ActivityInstance.runs))
    )
    if act is None:
        raise NotFoundError("Atividade 'triage_evaluation' não encontrada.")
    await require_activity_access(session, user_id, act, 'edit')
    runs = sorted(
        (r for r in act.runs if r.deleted_at is None),
        key=lambda r: r.run_number,
    )
    if (
        act.status != 'IN_PROGRESS'
        or not runs
        or runs[-1].status != 'IN_PROGRESS'
    ):
        raise ConflictError('A triagem não está aberta para decisão.')
    return act, runs[-1]


async def save_field_reviews(
    session: AsyncSession,
    process_id: UUID,
    reviews_list: list[dict[str, Any]],
    user_id: UUID,
) -> None:
    await _guard_against_current_conflict(session, process_id, user_id)
    await ensure_process_mutable(session, process_id)

    _, _, sub_form, _, sub_fields = await get_current_form_instance(
        session, process_id, 'proposal_submission'
    )
    _, triage_run = await _open_triage_run(session, process_id, user_id)

    field_map = {f.field_key: f for f in sub_fields}

    rev_stmt = select(FieldReview).where(
        FieldReview.form_instance_id == sub_form.id,
        FieldReview.activity_run_id == triage_run.id,
        FieldReview.deleted_at.is_(None),
    )
    existing_revs = {
        r.form_field_id: r for r in (await session.execute(rev_stmt)).scalars()
    }

    for item in reviews_list:
        f_key = item['field_key']
        if f_key not in field_map:
            continue
        field = field_map[f_key]
        fr = existing_revs.get(field.id)
        if fr is None:
            fr = FieldReview(
                form_instance_id=sub_form.id,
                form_field_id=field.id,
                activity_run_id=triage_run.id,
                status=item['status'],
                comments=item.get('comments'),
                reviewed_by=user_id,
            )
            fr.set_creation_audit(user_id)
            session.add(fr)
        else:
            fr.status = item['status']
            fr.comments = item.get('comments')
            fr.reviewed_by = user_id
            fr.reviewed_at = utc_now()
            fr.set_update_audit(user_id)

    session.add(
        AuditEvent(
            process_instance_id=process_id,
            activity_run_id=triage_run.id,
            user_id=user_id,
            event_type='FIELD_REVIEWED',
            context_data={'count': len(reviews_list)},
        )
    )
    await session.commit()


async def _open_new_submission_run(
    session: AsyncSession,
    process_id: UUID,
    *,
    reason: str,
    task_title: str,
    user_id: UUID,
) -> int:
    """Abre nova execução da submissão para o proponente ajustar.

    Reutilizado pela diligência de triagem e pelo retorno automático da
    pré-avaliação por IA. Copia os valores da execução anterior e cria a
    tarefa do proponente. Não altera o estado da triagem nem do processo.
    """
    await ensure_process_mutable(session, process_id)
    (
        sub_act,
        prev_sub_run,
        prev_sub_form,
        form_tmpl,
        _,
    ) = await get_current_form_instance(
        session, process_id, 'proposal_submission'
    )

    next_run_number = prev_sub_run.run_number + 1

    new_sub_run = ActivityRun(
        activity_instance_id=sub_act.id,
        run_number=next_run_number,
        status='IN_PROGRESS',
        execution_reason=reason,
    )
    new_sub_run.set_creation_audit(user_id)
    session.add(new_sub_run)
    await session.flush()

    new_form_inst = FormInstance(
        form_template_id=form_tmpl.id,
        activity_run_id=new_sub_run.id,
        is_submitted=False,
    )
    new_form_inst.set_creation_audit(user_id)
    session.add(new_form_inst)
    await session.flush()

    prev_vals_stmt = select(FormValue).where(
        FormValue.form_instance_id == prev_sub_form.id,
        FormValue.deleted_at.is_(None),
    )
    for pv in (await session.execute(prev_vals_stmt)).scalars().all():
        nv = FormValue(
            form_instance_id=new_form_inst.id,
            form_field_id=pv.form_field_id,
            text_value=pv.text_value,
            numeric_value=pv.numeric_value,
            boolean_value=pv.boolean_value,
            date_value=pv.date_value,
            json_value=pv.json_value,
            file_attachment_id=pv.file_attachment_id,
        )
        nv.set_creation_audit(user_id)
        session.add(nv)

    submission_a_data = await _template_activity_data(
        session, process_id, 'proposal_submission'
    )
    prop_task = Task(
        activity_run_id=new_sub_run.id,
        title=task_title,
        assigned_role='proponent',
        status='READY',
        due_date=_compute_activity_due_date(
            run_started_at=new_sub_run.started_at,
            sla_hours=submission_a_data.get('sla_hours'),
        ),
    )
    prop_task.set_creation_audit(user_id)
    session.add(prop_task)

    sub_act.status = 'IN_PROGRESS'
    sub_act.set_update_audit(user_id)

    return next_run_number


async def _handle_needs_revision(
    session: AsyncSession, ctx: TriageContext
) -> int:
    next_run_number = await _open_new_submission_run(
        session,
        ctx.process.id,
        reason=f'Diligência de triagem: {ctx.justification}',
        task_title=('Revisar e Ajustar Submissão da Proposta (Diligência)'),
        user_id=ctx.user_id,
    )

    ctx.triage_act.status = 'BLOCKED'
    ctx.triage_act.blocked_reason = 'Aguardando reenvio pelo proponente.'
    ctx.triage_act.set_update_audit(ctx.user_id)

    ctx.process.set_update_audit(ctx.user_id)

    session.add(
        AuditEvent(
            process_instance_id=ctx.process.id,
            activity_run_id=ctx.triage_run.id,
            user_id=ctx.user_id,
            event_type='REVISION_REQUESTED',
            context_data={
                'new_run_number': next_run_number,
                'justification': ctx.justification,
            },
        )
    )
    return next_run_number


async def _handle_approved_decision(
    session: AsyncSession, ctx: TriageContext
) -> None:
    phase_stmt = select(Phase).where(Phase.id == ctx.triage_act.phase_id)
    phase = (await session.execute(phase_stmt)).scalar_one_or_none()
    if phase:
        phase.status = 'COMPLETED'
        phase.set_update_audit(ctx.user_id)

    ctx.process.set_update_audit(ctx.user_id)

    session.add(
        AuditEvent(
            process_instance_id=ctx.process.id,
            activity_run_id=ctx.triage_run.id,
            user_id=ctx.user_id,
            event_type='TRIAGE_APPROVED',
            context_data={'justification': ctx.justification},
        )
    )

    await _advance_dependent_activities(
        session, ctx.process, ctx.triage_act, ctx.user_id
    )


async def _handle_rejected_decision(
    session: AsyncSession, ctx: TriageContext
) -> None:
    ctx.process.status = STATUS_CLOSED
    ctx.process.closed_at = utc_now()
    ctx.process.closure_reason = f'Rejeitado na triagem: {ctx.justification}'
    ctx.process.set_update_audit(ctx.user_id)

    session.add(
        AuditEvent(
            process_instance_id=ctx.process.id,
            activity_run_id=ctx.triage_run.id,
            user_id=ctx.user_id,
            event_type='TRIAGE_REJECTED',
            context_data={'justification': ctx.justification},
        )
    )


async def execute_triage_decision(
    session: AsyncSession,
    process_id: UUID,
    outcome: str,
    justification: str,
    user_id: UUID,
) -> tuple[Decision, str, int | None]:
    await _guard_against_current_conflict(session, process_id, user_id)

    p_stmt = (
        select(ProcessInstance)
        .where(ProcessInstance.id == process_id)
        .execution_options(skip_soft_delete_filter=True)
    )
    process = (await session.execute(p_stmt)).scalar_one_or_none()
    if not process:
        raise NotFoundError('Processo não encontrado.')

    triage_act, triage_run = await _open_triage_run(
        session, process_id, user_id
    )
    if process.status != STATUS_OPEN:
        raise ConflictError(f'Processo em status {process.status!r}.')

    decision = Decision(
        process_instance_id=process_id,
        activity_run_id=triage_run.id,
        decision_type='TRIAGE_INITIAL_DECISION',
        outcome=outcome,
        justification=justification,
        decided_by=user_id,
    )
    decision.set_creation_audit(user_id)
    session.add(decision)

    await _complete_activity_run(session, triage_run, triage_act, user_id)

    ctx = TriageContext(
        process=process,
        triage_act=triage_act,
        triage_run=triage_run,
        justification=justification,
        user_id=user_id,
    )

    next_run_number = None

    if outcome == 'APPROVED':
        await _handle_approved_decision(session, ctx)
    elif outcome == 'REJECTED':
        await _handle_rejected_decision(session, ctx)
    elif outcome == 'NEEDS_REVISION':
        next_run_number = await _handle_needs_revision(session, ctx)
    else:
        raise ValidationError(f'Resultado de triagem inválido: {outcome!r}.')

    await session.commit()
    return decision, process.status, next_run_number


async def _prune_evaluation_assignments(
    session: AsyncSession,
    form_template_id: UUID,
    removed_field_keys: set[str],
    user_id: UUID,
) -> None:
    """Remove chaves de campos apagados das associações de avaliação por IA.

    Uma associação que fique sem nenhum ``field_key`` é desativada (soft
    delete). Assim, remover/renomear um campo no editor não deixa associações
    órfãs que fariam ``replace_assignments`` rejeitar todo o lote depois.
    """
    stmt = select(EvaluationAssignment).where(
        EvaluationAssignment.form_template_id == form_template_id,
        EvaluationAssignment.deleted_at.is_(None),
    )
    for assignment in (await session.execute(stmt)).scalars():
        current = assignment.field_keys or []
        kept = [k for k in current if k not in removed_field_keys]
        if kept == current:
            continue
        assignment.field_keys = kept
        assignment.set_update_audit(user_id)
        if not kept and assignment.target_type in FIELD_TARGET_TYPES:
            assignment.set_deletion_audit(user_id)


async def update_form_template_definition(  # noqa: PLR0912, PLR0913, PLR0914, PLR0915, PLR0917
    session: AsyncSession,
    process_template_key: str,
    form_template_key: str,
    fields_data: list[dict[str, Any]],
    user_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> tuple[FormTemplate, list[FormField]]:
    """Atualiza a definição de um template de formulário e campos."""
    # 1. Validar chaves duplicadas
    keys = [f['field_key'] for f in fields_data if 'field_key' in f]
    if len(keys) != len(set(keys)):
        msg = 'Chaves de campos (field_key) duplicadas no formulário.'
        raise ValidationError(msg)

    # 2. Buscar ProcessTemplate
    p_stmt = select(ProcessTemplate).where(
        ProcessTemplate.key == process_template_key,
        ProcessTemplate.deleted_at.is_(None),
    )
    p_res = await session.execute(p_stmt)
    process_template = p_res.scalar_one_or_none()
    if not process_template:
        raise NotFoundError(
            f"Template de processo '{process_template_key}' não encontrado."
        )

    # 3. Buscar FormTemplate
    f_stmt = (
        select(FormTemplate)
        .where(
            FormTemplate.key == form_template_key,
            FormTemplate.deleted_at.is_(None),
        )
        .options(selectinload(FormTemplate.fields))
    )
    f_res = await session.execute(f_stmt)
    form_template = f_res.scalar_one_or_none()
    if not form_template:
        raise NotFoundError(
            f"Template de formulário '{form_template_key}' não encontrado."
        )

    if name:
        form_template.name = name
    if description is not None:
        form_template.description = description
    form_template.version += 1
    form_template.set_update_audit(user_id)

    # 4. Sincronizar FormField no banco
    existing_stmt = select(FormField).where(
        FormField.form_template_id == form_template.id,
        FormField.deleted_at.is_(None),
    )
    existing_fields = {
        f.field_key: f
        for f in (await session.execute(existing_stmt)).scalars().all()
    }

    processed_keys = set()
    result_fields: list[FormField] = []

    for f_data in fields_data:
        f_key = f_data['field_key']
        processed_keys.add(f_key)

        v_rules = dict(f_data.get('validation_rules') or {})
        if f_data.get('section'):
            v_rules['section'] = f_data['section']

        if f_key in existing_fields:
            field = existing_fields[f_key]
            field.label = f_data['label']
            field.field_type = f_data.get('field_type', 'text')
            field.help_text = f_data.get('help_text')
            field.is_required = f_data.get('is_required', False)
            field.order_index = f_data.get('order_index', 0)
            field.options = f_data.get('options')
            field.validation_rules = v_rules
            field.ai_evaluation_enabled = f_data.get(
                'ai_evaluation_enabled', False
            )
            field.ai_context_instructions = f_data.get(
                'ai_context_instructions'
            )
            field.ai_validation_rules = f_data.get('ai_validation_rules')
            field.set_update_audit(user_id)
            result_fields.append(field)
        else:
            field = FormField(
                form_template_id=form_template.id,
                field_key=f_key,
                label=f_data['label'],
                field_type=f_data.get('field_type', 'text'),
                help_text=f_data.get('help_text'),
                is_required=f_data.get('is_required', False),
                order_index=f_data.get('order_index', 0),
                options=f_data.get('options'),
                validation_rules=v_rules,
                ai_evaluation_enabled=f_data.get(
                    'ai_evaluation_enabled', False
                ),
                ai_context_instructions=f_data.get('ai_context_instructions'),
                ai_validation_rules=f_data.get('ai_validation_rules'),
            )
            field.set_creation_audit(user_id)
            session.add(field)
            result_fields.append(field)

    # Soft-delete nos campos removidos + limpeza em cascata das avaliações por
    # IA associadas a eles (senão a associação órfã trava o PUT de
    # evaluation-assignments, que valida a lista inteira).
    removed_keys = {
        f_key for f_key in existing_fields if f_key not in processed_keys
    }
    for f_key in removed_keys:
        existing_fields[f_key].set_deletion_audit(user_id)
    if removed_keys:
        await _prune_evaluation_assignments(
            session, form_template.id, removed_keys, user_id
        )

    # 5. Sincronizar ProcessTemplateVersion (definition_payload)
    v_stmt = (
        select(ProcessTemplateVersion)
        .where(
            ProcessTemplateVersion.template_id == process_template.id,
            ProcessTemplateVersion.deleted_at.is_(None),
            ProcessTemplateVersion.is_published.is_(True),
        )
        .order_by(ProcessTemplateVersion.version_number.desc())
    )
    latest_version = (await session.execute(v_stmt)).scalars().first()
    if latest_version and latest_version.definition_payload:
        payload = dict(latest_version.definition_payload)
        forms_list = list(payload.get('forms', []))
        updated_forms = []
        found_form = False

        for frm in forms_list:
            if frm.get('key') == form_template_key:
                found_form = True
                updated_form = dict(frm)
                if name:
                    updated_form['name'] = name
                if description is not None:
                    updated_form['description'] = description
                updated_form['version'] = form_template.version
                updated_form['fields'] = fields_data
                updated_forms.append(updated_form)
            else:
                updated_forms.append(frm)

        if not found_form:
            updated_forms.append({
                'key': form_template_key,
                'name': name or form_template.name,
                'version': form_template.version,
                'description': description or form_template.description,
                'fields': fields_data,
            })

        payload['forms'] = updated_forms
        latest_version.definition_payload = payload
        latest_version.set_update_audit(user_id)

    await session.commit()
    return form_template, result_fields
