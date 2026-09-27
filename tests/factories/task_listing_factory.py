"""Dados controlados para a lista de tarefas (Spec 032).

Template mínimo com as atividades da etapa 1 e duas da Fase 2, todas sem
dependências. As tarefas criadas pela instanciação são descartadas, para que
cada teste crie só as tarefas de que precisa, com status, prazo e rodada
definidos.
"""

from sqlalchemy import select

from pivma.bootstrap_process_templates import sync_template_from_dict
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    ProcessInstance,
    Task,
    User,
)
from pivma.core.process_engine import instantiate_process


def _activity(key, name, order, edit_role, **extra):
    return {
        'key': key,
        'name': name,
        'order_index': order,
        'assigned_role': edit_role,
        'access': {'edit': [edit_role], 'view': []},
        'dependencies': [],
        **extra,
    }


LISTING_TEMPLATE = {
    'process_template': {
        'key': 'task_listing_probe',
        'name': 'Lista de tarefas',
        'version': 1,
    },
    'phases': [
        {
            'key': 'phase_1_submission_triage',
            'name': 'Fase 1',
            'order_index': 1,
            'activities': [
                _activity('proposal_submission', 'Submissão', 1, 'proponent'),
                _activity('triage_evaluation', 'Triagem', 2, 'bracvam'),
                _activity(
                    'submission_return_review',
                    'Revisão do Retorno',
                    3,
                    'proponent',
                ),
            ],
        },
        {
            'key': 'phase_2_role_assignment',
            'name': 'Fase 2',
            'order_index': 2,
            'activities': [
                _activity(
                    'assign_group_manager', 'Grupo Gestor', 1, 'proponent'
                ),
                _activity(
                    'sample_definition',
                    'Amostras',
                    2,
                    'sample_selection_group',
                    activity_type='sample_definition',
                ),
            ],
        },
    ],
    'forms': [],
}


async def listing_process(
    session, *, proponent: User, title: str = 'Processo'
) -> ProcessInstance:
    """Processo do template mínimo sem nenhuma tarefa nem execução ativa.

    O criador vira `proponent` pela própria instanciação.
    """
    _, version, _ = await sync_template_from_dict(session, LISTING_TEMPLATE)
    process = await instantiate_process(session, version, title, proponent.id)
    runs = (
        await session.scalars(
            select(ActivityRun)
            .join(ActivityInstance)
            .where(ActivityInstance.process_instance_id == process.id)
        )
    ).all()
    for run in runs:
        run.set_deletion_audit(proponent.id)
        for task in await session.scalars(
            select(Task).where(Task.activity_run_id == run.id)
        ):
            task.set_deletion_audit(proponent.id)
    await session.commit()
    return process


async def add_task(  # noqa: PLR0913
    session,
    process: ProcessInstance,
    activity_key: str,
    *,
    run_number: int = 1,
    status: str = 'READY',
    due_date=None,
) -> Task:
    activity = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == process.id,
            ActivityInstance.key == activity_key,
        )
    )
    run = ActivityRun(
        activity_instance_id=activity.id,
        run_number=run_number,
        status='COMPLETED' if status == 'COMPLETED' else 'IN_PROGRESS',
    )
    session.add(run)
    await session.flush()
    task = Task(
        activity_run_id=run.id,
        title=activity.name,
        assigned_role=activity.edit_roles[0],
        status=status,
        due_date=due_date,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task
