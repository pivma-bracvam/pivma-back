# ruff: noqa: PLR2004
"""Escolhas simultâneas sobre o mesmo retorno (Spec 046, FR-015)."""

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    AuditEvent,
    DirectReviewRequest,
    ProcessInstance,
)
from pivma.core.return_review_service import decide_return_review
from tests.factories.return_review_factory import (
    committed_return_review,
    count_rows,
    split_outcomes,
)


async def _decide(engine, ctx, choice):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await decide_return_review(
            session, ctx.process_id, ctx.proponent.id, choice, None
        )


async def _race(engine, ctx, *choices):
    results = await asyncio.gather(
        *(_decide(engine, ctx, choice) for choice in choices),
        return_exceptions=True,
    )
    winners, conflicts = split_outcomes(results)
    assert len(winners) == 1
    assert len(conflicts) == len(choices) - 1
    return winners[0]


async def _submission_runs(engine, ctx):
    return await count_rows(
        engine,
        ActivityRun,
        ActivityRun.activity_instance_id.in_(
            select(ActivityInstance.id).where(
                ActivityInstance.process_instance_id == ctx.process_id,
                ActivityInstance.key == 'proposal_submission',
            )
        ),
    )


async def _decided_events(engine, ctx):
    return await count_rows(
        engine,
        AuditEvent,
        AuditEvent.process_instance_id == ctx.process_id,
        AuditEvent.event_type == 'RETURN_REVIEW_DECIDED',
    )


@pytest.mark.asyncio
async def test_revise_and_withdraw_race_has_one_winner(engine):
    async with committed_return_review(engine, 'triage_return') as ctx:
        winner = await _race(engine, ctx, 'REVISE', 'WITHDRAW')

        async with AsyncSession(engine) as check:
            status = await check.scalar(
                select(ProcessInstance.status).where(
                    ProcessInstance.id == ctx.process_id
                )
            )
        expected = (
            (2, 'OPEN') if winner['choice'] == 'REVISE' else (1, 'CLOSED')
        )
        assert (await _submission_runs(engine, ctx), status) == expected
        assert await _decided_events(engine, ctx) == 1


@pytest.mark.asyncio
async def test_double_revise_opens_one_submission_run(engine):
    async with committed_return_review(engine, 'triage_return') as ctx:
        await _race(engine, ctx, 'REVISE', 'REVISE')

        assert await _submission_runs(engine, ctx) == 2
        assert await _decided_events(engine, ctx) == 1


@pytest.mark.asyncio
async def test_revise_and_contest_race_has_one_winner(engine):
    async with committed_return_review(engine, 'ai_failed') as ctx:
        winner = await _race(engine, ctx, 'REVISE', 'CONTEST_AI')

        requests = await count_rows(
            engine,
            DirectReviewRequest,
            DirectReviewRequest.process_instance_id == ctx.process_id,
        )
        expected = (2, 0) if winner['choice'] == 'REVISE' else (1, 1)
        assert (await _submission_runs(engine, ctx), requests) == expected
        assert await _decided_events(engine, ctx) == 1
