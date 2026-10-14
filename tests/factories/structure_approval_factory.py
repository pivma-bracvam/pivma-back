"""Processo com a Etapa 2 montada e a homologação da estrutura (Spec 042).

Usa o template real `pre_validated_method` e os serviços do domínio:
submissão, triagem aprovada, os oito cargos designados e uma substância com
SDS. Com `complete_samples`, a homologação abre para o BraCVAM. A jornada
percorre o mesmo caminho pela API pública.
"""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    load_yaml_template,
    sync_template_from_dict,
)
from pivma.core import participant_service, sample_service
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    Decision,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    Task,
)
from pivma.core.process_engine import (
    execute_triage_decision,
    instantiate_process,
    submit_proposal_form,
)
from tests.factories.sample_factory import (
    _user,  # noqa: PLC2701
    lab_user,
    new_laboratory,
    substance_payload,
)
from tests.factories.sample_receipt_factory import attach_sds

ORIGIN = {'Origin': 'https://testserver'}
TEMPLATE_KEY = 'pre_validated_method'
TEMPLATE_FILE = (
    Path(__file__).parents[2]
    / 'src/pivma/templates_data/01_pre_validated_method.yaml'
)
APPROVAL_KEY = 'structure_approval'
PHASE_2_KEY = 'phase_2_role_assignment'
# Cargo de cada atribuição não laboratorial e o atributo do contexto.
PERSON_ROLES = {
    'group_manager': 'manager',
    'sponsor': 'sponsor',
    'sample_selection_group': 'selector',
    'statistician': 'statistician',
    'collaborator': 'collaborator',
    'adhoc_evaluator': 'adhoc',
}


def previous_version_payload() -> dict:
    """O template 1 como era antes da homologação (FR-003).

    Sem `structure_approval`, com o recebimento dependendo das amostras e
    uma versão abaixo da atual.
    """
    data = deepcopy(load_yaml_template(TEMPLATE_FILE))
    data['process_template']['version'] -= 1
    for phase in data['phases']:
        phase['activities'] = [
            a for a in phase['activities'] if a['key'] != APPROVAL_KEY
        ]
        for activity in phase['activities']:
            for dependency in activity.get('dependencies') or []:
                if dependency['required_activity_key'] == APPROVAL_KEY:
                    dependency['required_activity_key'] = 'sample_definition'
    return data


async def _template_version(session, *, previous: bool):
    if previous:
        _, version, _ = await sync_template_from_dict(
            session, previous_version_payload()
        )
        return version
    return await session.scalar(
        select(ProcessTemplateVersion)
        .join(
            ProcessTemplate,
            ProcessTemplate.id == ProcessTemplateVersion.template_id,
        )
        .where(ProcessTemplate.key == TEMPLATE_KEY)
        .order_by(ProcessTemplateVersion.version_number.desc())
        .limit(1)
    )


async def _approve_triage(session, process_id, proponent, bracvam) -> None:
    await submit_proposal_form(
        session,
        process_id,
        'proposal_submission',
        {'method_title': 'Ensaio RhCE'},
        proponent.id,
    )
    await execute_triage_decision(
        session, process_id, 'APPROVED', 'Aderente.', bracvam.id
    )


async def designate(session, ctx, user, role_key, laboratory=None):
    """Designa pelo serviço de participantes, como a rota faria."""
    process = await session.get(ProcessInstance, ctx.process_id)
    assignment = await participant_service.create_assignment(
        session,
        process,
        user_id=user.id,
        role_key=role_key,
        laboratory_id=laboratory.id if laboratory else None,
        actor_id=ctx.proponent.id,
        source='api',
    )
    await session.commit()
    return assignment


async def finish_samples(session, ctx) -> None:
    """O Grupo de Seleção conclui as amostras."""
    await sample_service.complete_sample_definition(
        session, ctx.process_id, ctx.selector.id
    )


async def planning_process(
    session,
    bracvam,
    *,
    lab_count: int = 2,
    collection_template_id=None,
    previous_version: bool = False,
) -> SimpleNamespace:
    """Processo com a triagem aprovada e as pessoas da equipe, sem cargos.

    As duas primeiras atribuições da Etapa 2 ficam em andamento.
    """
    await bootstrap_all_templates(session)
    version = await _template_version(session, previous=previous_version)
    ctx = SimpleNamespace(
        proponent=await _user(session),
        laboratories=[await new_laboratory(session) for _ in range(lab_count)],
    )
    ctx.lab_users = [await lab_user(session, lab) for lab in ctx.laboratories]
    for attribute in PERSON_ROLES.values():
        setattr(ctx, attribute, await _user(session))

    process = await instantiate_process(
        session,
        version,
        'Estudo cego de irritação ocular',
        ctx.proponent.id,
        collection_template_id=collection_template_id,
    )
    await session.commit()
    ctx.process_id = process.id
    await _approve_triage(session, ctx.process_id, ctx.proponent, bracvam)
    return ctx


async def structure_process(  # noqa: PLR0913
    session,
    bracvam,
    *,
    lab_count: int = 2,
    collection_template_id=None,
    complete_samples: bool = True,
    previous_version: bool = False,
) -> SimpleNamespace:
    """Processo com os oito cargos designados e uma substância com SDS.

    Com `complete_samples`, conclui as amostras: na versão atual, a
    homologação fica em andamento; com `previous_version`, o recebimento
    abre por laboratório.
    """
    ctx = await planning_process(
        session,
        bracvam,
        lab_count=lab_count,
        collection_template_id=collection_template_id,
        previous_version=previous_version,
    )
    for role_key, attribute in PERSON_ROLES.items():
        await designate(session, ctx, getattr(ctx, attribute), role_key)
    await designate(
        session,
        ctx,
        ctx.lab_users[0],
        'lead_laboratory',
        ctx.laboratories[0],
    )
    ctx.lab_assignments = [
        await designate(
            session, ctx, user, 'participating_laboratory', laboratory
        )
        for laboratory, user in zip(
            ctx.laboratories, ctx.lab_users, strict=True
        )
    ]

    ctx.substance = await sample_service.create_substance(
        session, ctx.process_id, ctx.selector.id, substance_payload()
    )
    await attach_sds(session, ctx.process_id, ctx.substance['id'])
    if complete_samples:
        await finish_samples(session, ctx)
    return ctx


def panel(client, process_id):
    return client.get(f'/processes/{process_id}/structure-approval')


def decide(client, process_id, **body):
    return client.post(
        f'/processes/{process_id}/structure-approval/decision',
        json=body,
        headers=ORIGIN,
    )


# ---------------------------------------------------------------------------
# Leituras do banco para os testes focados
# ---------------------------------------------------------------------------


async def activity(session, process_id, key=APPROVAL_KEY) -> ActivityInstance:
    return await session.scalar(
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == key,
        )
        .execution_options(populate_existing=True)
    )


async def runs(session, process_id, key=APPROVAL_KEY) -> list[ActivityRun]:
    """Execuções da atividade, por número e laboratório."""
    return list(
        await session.scalars(
            select(ActivityRun)
            .join(ActivityInstance)
            .where(
                ActivityInstance.process_instance_id == process_id,
                ActivityInstance.key == key,
            )
            .order_by(ActivityRun.run_number, ActivityRun.laboratory_id)
            .execution_options(populate_existing=True)
        )
    )


async def run_tasks(session, run_id) -> list[Task]:
    return list(
        await session.scalars(
            select(Task)
            .where(Task.activity_run_id == run_id)
            .execution_options(populate_existing=True)
        )
    )


async def decisions(session, process_id) -> list[Decision]:
    return list(
        await session.scalars(
            select(Decision)
            .where(
                Decision.process_instance_id == process_id,
                Decision.decision_type == 'STRUCTURE_APPROVAL',
            )
            .order_by(Decision.decided_at)
        )
    )


async def events(session, process_id, event_type) -> list[AuditEvent]:
    return list(
        await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.process_instance_id == process_id,
                AuditEvent.event_type == event_type,
            )
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        )
    )


async def snapshot(session, process_id) -> tuple:
    """Estado que nenhuma recusa pode mudar (tasks.md, "Tests")."""
    approval = await activity(session, process_id)
    return (
        approval.status,
        [(r.run_number, r.status) for r in await runs(session, process_id)],
        len(await decisions(session, process_id)),
        len(await runs(session, process_id, 'sample_receipt')),
    )
