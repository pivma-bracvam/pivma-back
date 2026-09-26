"""Leitura do estado das atividades nos testes (Spec 030).

Desde a Spec 030 o processo guarda só o ciclo de vida; a posição no fluxo
(submissão, pré-avaliação, triagem) é lida das atividades.
"""

from sqlalchemy import select

from pivma.core.database.models import ActivityInstance


async def activity_status(session, process_id, key):
    return await session.scalar(
        select(ActivityInstance.status)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == key,
        )
        .execution_options(populate_existing=True)
    )


async def in_triage(session, process_id):
    """Submissão concluída e triagem aberta (o antigo status `TRIAGE`)."""
    return (
        await activity_status(session, process_id, 'proposal_submission')
        == 'COMPLETED'
        and await activity_status(session, process_id, 'triage_evaluation')
        == 'IN_PROGRESS'
    )


async def back_with_proponent(session, process_id):
    """Retorno aberto ao proponente e triagem fechada (o antigo `SUBMISSION`

    depois de uma devolução): a revisão do retorno está em andamento.
    """
    return (
        await activity_status(session, process_id, 'submission_return_review')
        == 'IN_PROGRESS'
        and await activity_status(session, process_id, 'triage_evaluation')
        != 'IN_PROGRESS'
    )
