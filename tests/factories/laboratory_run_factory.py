"""Processo com atividades executadas por laboratório (Spec 036).

``LAB_RUN_TEMPLATE`` estende o template de amostras da Spec 031 com uma fase
de execução: recebimento, envio de resultados e devolução (custódia) por
laboratório, uma avaliação estatística única e um retorno por laboratório
que só é ativado depois da estatística.
"""

from types import SimpleNamespace

from sqlalchemy import select

from pivma.core import sample_service
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    StudySubstance,
    Task,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import (
    SAMPLE_TEMPLATE,
    _user,
    sample_process,
    substance_payload,
)

LAB_ROLE = 'participating_laboratory'

LAB_RUN_TEMPLATE = {
    'process_template': {
        'key': 'lab_run_probe',
        'name': 'Execução por laboratório',
        'version': 1,
    },
    'phases': [
        SAMPLE_TEMPLATE['phases'][0],
        {
            'key': 'phase_execution',
            'name': 'Execução',
            'order_index': 2,
            'activities': [
                {
                    'key': 'receipt',
                    'name': 'Recebimento das Amostras',
                    'order_index': 1,
                    'assigned_role': LAB_ROLE,
                    'execution_scope': 'per_laboratory',
                    'access': {
                        'edit': [LAB_ROLE, 'group_manager', 'admin'],
                        'view': ['statistician', 'lead_laboratory'],
                    },
                    'dependencies': [
                        {'required_activity_key': 'sample_definition'}
                    ],
                },
                {
                    'key': 'upload',
                    'name': 'Envio de Resultados',
                    'order_index': 2,
                    'assigned_role': LAB_ROLE,
                    'execution_scope': 'per_laboratory',
                    'sla_hours': 48,
                    'form_template_key': 'lab_results_v1',
                    'access': {'edit': [LAB_ROLE], 'view': ['group_manager']},
                    'dependencies': [{'required_activity_key': 'receipt'}],
                },
                {
                    'key': 'material_return',
                    'name': 'Devolução ou Descarte',
                    'order_index': 3,
                    'assigned_role': LAB_ROLE,
                    'execution_scope': 'per_laboratory',
                    'custody': True,
                    'access': {'edit': [LAB_ROLE], 'view': ['group_manager']},
                    'dependencies': [
                        {'required_activity_key': 'receipt'},
                        {'required_activity_key': 'upload'},
                    ],
                },
                {
                    'key': 'statistics',
                    'name': 'Avaliação Estatística',
                    'order_index': 4,
                    'assigned_role': 'statistician',
                    'dependencies': [{'required_activity_key': 'upload'}],
                },
                {
                    'key': 'lab_feedback',
                    'name': 'Retorno ao Laboratório',
                    'order_index': 5,
                    'assigned_role': LAB_ROLE,
                    'execution_scope': 'per_laboratory',
                    'access': {'edit': [LAB_ROLE], 'view': ['group_manager']},
                    'dependencies': [{'required_activity_key': 'statistics'}],
                },
            ],
        },
    ],
    'forms': [
        {
            'key': 'lab_results_v1',
            'name': 'Resultados do laboratório',
            'version': 1,
            'fields': [
                {
                    'field_key': 'result_note',
                    'label': 'Resultado',
                    'field_type': 'text',
                    'is_required': True,
                    'order_index': 1,
                },
                {
                    'field_key': 'raw_data',
                    'label': 'Dados brutos',
                    'field_type': 'file_upload',
                    'is_required': False,
                    'order_index': 2,
                },
            ],
        }
    ],
}


async def freeze_samples(session, ctx) -> None:
    """Cadastra uma substância com SDS e conclui `sample_definition`."""
    await sample_service.create_substance(
        session, ctx.process_id, ctx.selector.id, substance_payload()
    )
    run = await session.scalar(
        select(ActivityRun)
        .join(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == ctx.process_id,
            ActivityInstance.key == 'sample_definition',
        )
    )
    artifact = Artifact(
        process_instance_id=ctx.process_id,
        activity_run_id=run.id,
        key='sample_sds',
        name='sds.pdf',
    )
    session.add(artifact)
    await session.flush()
    substance = await session.scalar(
        select(StudySubstance).where(
            StudySubstance.process_instance_id == ctx.process_id
        )
    )
    substance.sds_artifact_id = artifact.id
    await session.commit()
    await sample_service.complete_sample_definition(
        session, ctx.process_id, ctx.selector.id
    )


async def frozen_lab_process(
    session, *, lab_count: int = 3, freeze: bool = True
) -> SimpleNamespace:
    """Processo com laboratórios, Grupo Gestor e estatístico designados."""
    ctx = await sample_process(
        session, lab_count=lab_count, template=LAB_RUN_TEMPLATE
    )
    ctx.group_manager = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.group_manager,
        role_key='group_manager',
    )
    ctx.statistician = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.statistician,
        role_key='statistician',
    )
    if freeze:
        await freeze_samples(session, ctx)
    return ctx


async def activity(session, process_id, key) -> ActivityInstance:
    return await session.scalar(
        select(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == key,
        )
        .execution_options(populate_existing=True)
    )


async def runs_by_lab(session, process_id, key) -> dict:
    """Execução vigente (maior número) de cada laboratório na atividade."""
    act = await activity(session, process_id, key)
    rows = (
        await session.scalars(
            select(ActivityRun)
            .where(
                ActivityRun.activity_instance_id == act.id,
                ActivityRun.deleted_at.is_(None),
            )
            .order_by(ActivityRun.run_number)
            .execution_options(populate_existing=True)
        )
    ).all()
    current = {}
    for run in rows:
        current[run.laboratory_id] = run
    return current


async def tasks_of(session, run_id) -> list[Task]:
    return list(
        await session.scalars(
            select(Task)
            .where(Task.activity_run_id == run_id, Task.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
    )


async def complete_lab(session, ctx, key, index):
    """O usuário do laboratório `index` conclui a própria execução."""
    from pivma.core.process_engine import (  # noqa: PLC0415
        complete_laboratory_run,
    )

    run = await complete_laboratory_run(
        session,
        ctx.process_id,
        key,
        ctx.labs[index].id,
        ctx.lab_users[index].id,
    )
    await session.commit()
    return run


async def complete_chain(session, ctx, index, keys=('receipt', 'upload')):
    for key in keys:
        await complete_lab(session, ctx, key, index)


async def complete_statistics(session, ctx):
    """Conclui a avaliação estatística (atividade única) e avança."""
    from pivma.core.database.models import ProcessInstance  # noqa: PLC0415
    from pivma.core.process_engine import (  # noqa: PLC0415
        _advance_dependent_activities,  # noqa: PLC2701
        _complete_activity_run,  # noqa: PLC2701
    )

    act = await activity(session, ctx.process_id, 'statistics')
    run = (await runs_by_lab(session, ctx.process_id, 'statistics'))[None]
    process = await session.get(ProcessInstance, ctx.process_id)
    await _complete_activity_run(session, run, act, ctx.statistician.id)
    await _advance_dependent_activities(
        session, process, act, ctx.statistician.id
    )
    await session.commit()


async def end_affiliation(session, user) -> None:
    """Encerra o vínculo institucional do usuário (Spec 035)."""
    from datetime import datetime  # noqa: PLC0415

    from pivma.core.database.models import (  # noqa: PLC0415
        UserInstitutionalAffiliation,
    )

    for affiliation in await session.scalars(
        select(UserInstitutionalAffiliation).where(
            UserInstitutionalAffiliation.user_id == user.id
        )
    ):
        affiliation.deleted_at = datetime.utcnow()
    await session.commit()


async def waive(session, ctx, index, reason='Equipamento quebrado.'):
    """O Grupo Gestor dispensa o laboratório `index` na fase de execução."""
    from pivma.core.process_engine import waive_laboratory  # noqa: PLC0415

    result = await waive_laboratory(
        session,
        ctx.process_id,
        'phase_execution',
        ctx.labs[index].id,
        reason,
        ctx.group_manager.id,
    )
    await session.commit()
    return result


async def reopen(session, ctx, key, index, reason='Controle positivo fora.'):
    """O Grupo Gestor reabre a execução do laboratório `index`."""
    from pivma.core.process_engine import (  # noqa: PLC0415
        reopen_laboratory_run,
    )

    result = await reopen_laboratory_run(
        session,
        ctx.process_id,
        key,
        ctx.labs[index].id,
        reason,
        ctx.group_manager.id,
    )
    await session.commit()
    return result


async def all_labs_done(session, ctx, keys=('receipt', 'upload')):
    for index in range(len(ctx.labs)):
        await complete_chain(session, ctx, index, keys)
