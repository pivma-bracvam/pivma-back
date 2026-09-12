from pathlib import Path

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    ActivityDependency,
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    ConflictInterestDeclaration,
    Decision,
    DirectReviewRequest,
    EvaluationRun,
    EvaluationRunItem,
    FieldReview,
    FormInstance,
    FormValue,
    Phase,
    ProcessInstance,
    ReviewerFeedback,
    Task,
)
from pivma.core.process_engine import execute_process_lifecycle


@pytest.mark.asyncio
async def test_delete_draft_removes_complete_aggregate_and_files(
    session, user, process_retirement_factory, tmp_path: Path
):
    process = await process_retirement_factory.draft(user)
    await process_retirement_factory.add_attachment(process, user, tmp_path)
    activity_ids = list(
        await session.scalars(
            select(ActivityInstance.id).where(
                ActivityInstance.process_instance_id == process.id
            )
        )
    )
    run_ids = list(
        await session.scalars(
            select(ActivityRun.id).where(
                ActivityRun.activity_instance_id.in_(activity_ids)
            )
        )
    )
    form_ids = list(
        await session.scalars(
            select(FormInstance.id).where(
                FormInstance.activity_run_id.in_(run_ids)
            )
        )
    )
    evaluation_run = EvaluationRun(
        process_instance_id=process.id,
        activity_run_id=run_ids[0],
        form_instance_id=form_ids[0],
        status='in_progress',
    )
    evaluation_run.set_creation_audit(user.id)
    session.add(evaluation_run)
    await session.commit()
    assignment_ids = list(
        await session.scalars(
            select(Assignment.id).where(
                Assignment.process_instance_id == process.id
            )
        )
    )

    aggregate_ids = {
        Phase: list(
            await session.scalars(
                select(Phase.id).where(Phase.process_instance_id == process.id)
            )
        ),
        ActivityInstance: activity_ids,
        ActivityDependency: list(
            await session.scalars(
                select(ActivityDependency.id).where(
                    ActivityDependency.dependent_activity_id.in_(activity_ids)
                    | ActivityDependency.required_activity_id.in_(activity_ids)
                )
            )
        ),
        ActivityRun: run_ids,
        Task: list(
            await session.scalars(
                select(Task.id).where(Task.activity_run_id.in_(run_ids))
            )
        ),
        FormInstance: form_ids,
        FormValue: list(
            await session.scalars(
                select(FormValue.id).where(
                    FormValue.form_instance_id.in_(form_ids)
                )
            )
        ),
        FieldReview: list(
            await session.scalars(
                select(FieldReview.id).where(
                    FieldReview.form_instance_id.in_(form_ids)
                )
            )
        ),
        Artifact: list(
            await session.scalars(
                select(Artifact.id).where(
                    Artifact.process_instance_id == process.id
                )
            )
        ),
        Decision: list(
            await session.scalars(
                select(Decision.id).where(
                    Decision.process_instance_id == process.id
                )
            )
        ),
        Assignment: assignment_ids,
        ConflictInterestDeclaration: list(
            await session.scalars(
                select(ConflictInterestDeclaration.id).where(
                    ConflictInterestDeclaration.assignment_id.in_(
                        assignment_ids
                    )
                )
            )
        ),
        AuditEvent: list(
            await session.scalars(
                select(AuditEvent.id).where(
                    AuditEvent.process_instance_id == process.id
                )
            )
        ),
        EvaluationRun: [evaluation_run.id],
        EvaluationRunItem: [],
        ReviewerFeedback: [],
        DirectReviewRequest: list(
            await session.scalars(
                select(DirectReviewRequest.id).where(
                    DirectReviewRequest.process_instance_id == process.id
                )
            )
        ),
    }
    result = await execute_process_lifecycle(
        session,
        process.id,
        'DELETE_DRAFT',
        'Descartar massa de teste',
        user.id,
        attachment_root=tmp_path,
    )

    assert result['deleted'] is True
    assert not (tmp_path / str(process.id)).exists()
    assert await session.get(ProcessInstance, process.id) is None
    for model, ids in aggregate_ids.items():
        if not ids:
            continue
        count = await session.scalar(
            select(func.count()).select_from(model).where(model.id.in_(ids))
        )
        assert count == 0, model.__tablename__


@pytest.mark.asyncio
async def test_file_cleanup_failure_keeps_database_rows(
    session, user, process_retirement_factory, tmp_path, monkeypatch
):
    process = await process_retirement_factory.draft(user)
    await process_retirement_factory.add_attachment(process, user, tmp_path)
    process_id = process.id

    def fail_cleanup(*_args, **_kwargs):
        raise OSError('disco indisponível')

    monkeypatch.setattr(
        'pivma.core.process_engine.remove_process_attachments', fail_cleanup
    )

    with pytest.raises(OSError, match='disco indisponível'):
        await execute_process_lifecycle(
            session,
            process_id,
            'DELETE_DRAFT',
            'Não apagar sem limpar arquivos',
            user.id,
            attachment_root=tmp_path,
        )

    await session.rollback()
    assert await session.get(ProcessInstance, process_id) is not None
    assert (tmp_path / str(process_id)).is_dir()
