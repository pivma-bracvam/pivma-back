import pytest
from sqlalchemy import select

from pivma.core import pre_evaluation_service as service
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    EvaluationRun,
    FormInstance,
    ProcessInstance,
)
from pivma.core.process_engine import ConflictError, execute_process_lifecycle


@pytest.mark.asyncio
async def test_late_pre_evaluation_does_not_change_cancelled_process(
    session, user, bracvam_user, process_retirement_factory
):
    process = await process_retirement_factory.submitted(
        user, status='AI_PRE_EVALUATION'
    )
    activity_run = await session.scalar(
        select(ActivityRun)
        .join(ActivityInstance)
        .where(ActivityInstance.process_instance_id == process.id)
    )
    form = await session.scalar(
        select(FormInstance).where(
            FormInstance.activity_run_id == activity_run.id
        )
    )
    run = EvaluationRun(
        process_instance_id=process.id,
        activity_run_id=activity_run.id,
        form_instance_id=form.id,
        status='in_progress',
    )
    run.set_creation_audit(user.id)
    session.add(run)
    await session.commit()

    await execute_process_lifecycle(
        session,
        process.id,
        'CANCEL',
        'Cancelar antes da conclusão da IA',
        bracvam_user.id,
    )
    await service._execute(session, run.id)

    saved_run = await session.get(EvaluationRun, run.id)
    saved_process = await session.get(ProcessInstance, process.id)
    assert saved_run.status == 'CANCELLED'
    assert saved_process.status == 'CANCELLED'


@pytest.mark.asyncio
async def test_retry_pre_evaluation_is_rejected_after_cancellation(
    session, user, bracvam_user, process_retirement_factory
):
    process = await process_retirement_factory.submitted(
        user, status='AI_PRE_EVALUATION'
    )
    activity_run = await session.scalar(
        select(ActivityRun)
        .join(ActivityInstance)
        .where(ActivityInstance.process_instance_id == process.id)
    )
    form = await session.scalar(
        select(FormInstance).where(
            FormInstance.activity_run_id == activity_run.id
        )
    )
    run = EvaluationRun(
        process_instance_id=process.id,
        activity_run_id=activity_run.id,
        form_instance_id=form.id,
        status='in_progress',
    )
    run.set_creation_audit(user.id)
    session.add(run)
    await session.commit()
    await execute_process_lifecycle(
        session, process.id, 'CANCEL', 'Cancelar retry', bracvam_user.id
    )

    with pytest.raises(ConflictError):
        await service.retry_run(session, run.id, bracvam_user.id)
