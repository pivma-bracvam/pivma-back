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
    FieldReview,
    FormInstance,
    FormValue,
    Phase,
    ProcessInstance,
    Task,
)
from pivma.core.process_engine import delete_process


@pytest.mark.asyncio
async def test_delete_preserves_aggregate_and_files(
    session, user, process_retirement_factory, tmp_path: Path
):
    """Soft-delete (revisão 2026-09-13): nada é removido, só ocultado."""
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
    }

    await delete_process(session, process.id, user.id)

    assert (tmp_path / str(process.id)).exists()
    saved = await session.scalar(
        select(ProcessInstance)
        .where(ProcessInstance.id == process.id)
        .execution_options(skip_soft_delete_filter=True)
    )
    assert saved is not None
    assert saved.status == 'CANCELLED'
    assert saved.deleted_at is not None
    assert saved.deleted_by == user.id
    for model, ids in aggregate_ids.items():
        if not ids:
            continue
        count = await session.scalar(
            select(func.count(model.id)).where(model.id.in_(ids))
        )
        assert count == len(ids), model.__tablename__


@pytest.mark.asyncio
async def test_soft_deleted_process_is_hidden_from_plain_query_but_not_bypass(
    session, user, process_retirement_factory
):
    """Rede de segurança global de soft-delete (Spec 022, FR-013/FR-024)."""
    process = await process_retirement_factory.draft(user)

    await delete_process(session, process.id, user.id)

    plain_result = await session.scalars(
        select(ProcessInstance).where(ProcessInstance.id == process.id)
    )
    assert plain_result.first() is None

    bypass_result = await session.scalars(
        select(ProcessInstance)
        .where(ProcessInstance.id == process.id)
        .execution_options(skip_soft_delete_filter=True)
    )
    found = bypass_result.first()
    assert found is not None
    assert found.deleted_at is not None
