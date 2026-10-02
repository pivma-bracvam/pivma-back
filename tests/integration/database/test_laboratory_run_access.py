"""Só o próprio laboratório age na execução dele (Spec 036, US2, R8)."""

import pytest
from sqlalchemy import select

from pivma.core.database.models import Assignment
from pivma.core.process_engine import (
    AuthorizationError,
    NotFoundError,
    complete_laboratory_run,
)
from tests.factories.laboratory_run_factory import (
    end_affiliation,
    frozen_lab_process,
    runs_by_lab,
)
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
)


async def _complete(session, ctx, lab_index, user_id):
    return await complete_laboratory_run(
        session, ctx.process_id, 'receipt', ctx.labs[lab_index].id, user_id
    )


async def _status(session, ctx, lab_id):
    return (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        lab_id
    ].status


@pytest.mark.asyncio
async def test_lab_a_cannot_complete_lab_b_run(session):
    ctx = await frozen_lab_process(session)
    lab_b = ctx.labs[1].id

    with pytest.raises(NotFoundError):
        await _complete(session, ctx, 1, ctx.lab_users[0].id)
    await session.rollback()

    assert await _status(session, ctx, lab_b) == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_lab_user_without_effective_designation_is_refused(session):
    """Mesma resposta de quem nunca teve o cargo (Spec 035, FR-005)."""
    ctx = await frozen_lab_process(session)
    lab_a = ctx.labs[0].id
    await end_affiliation(session, ctx.lab_users[0])

    with pytest.raises(NotFoundError):
        await _complete(session, ctx, 0, ctx.lab_users[0].id)
    await session.rollback()

    assert await _status(session, ctx, lab_a) == 'IN_PROGRESS'


@pytest.mark.asyncio
async def test_group_manager_cannot_act_on_lab_run(session):
    ctx = await frozen_lab_process(session)

    with pytest.raises(AuthorizationError):
        await _complete(session, ctx, 0, ctx.group_manager.id)


@pytest.mark.asyncio
async def test_admin_global_cargo_completes_any_lab_run(
    session, ai_eval_admin
):
    ctx = await frozen_lab_process(session)

    run = await _complete(session, ctx, 2, ai_eval_admin.id)

    assert run.status == 'COMPLETED'


@pytest.mark.asyncio
async def test_lab_user_with_current_conflict_is_refused(session):
    ctx = await frozen_lab_process(session)
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.user_id == ctx.lab_users[0].id,
        )
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    with pytest.raises(AuthorizationError):
        await _complete(session, ctx, 0, ctx.lab_users[0].id)


@pytest.mark.asyncio
async def test_user_who_does_not_see_activity_gets_not_found(session):
    ctx = await frozen_lab_process(session)

    with pytest.raises(NotFoundError):
        await _complete(session, ctx, 0, ctx.selector.id)
