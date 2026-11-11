# ruff: noqa: PLR2004
"""Disputas pela mesma execução da IA (Spec 046, FR-016 e FR-016a)."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import (
    Artifact,
    AuditEvent,
    DirectReviewRequest,
    EvaluationRun,
)
from pivma.core.process_engine import ConflictError
from pivma.core.return_review_service import decide_return_review
from tests.factories.return_review_factory import (
    committed_return_review,
    count_rows,
    split_outcomes,
)


async def _retry(engine, ctx):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await svc.retry_run(
            session, ctx.evaluation_run_id, ctx.admin.id
        )


async def _contest(engine, ctx):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await decide_return_review(
            session, ctx.process_id, ctx.proponent.id, 'CONTEST_AI', None
        )


async def _execute(engine, ctx):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await svc._execute(session, ctx.evaluation_run_id)


async def _evaluation_runs(engine, ctx):
    return await count_rows(
        engine,
        EvaluationRun,
        EvaluationRun.process_instance_id == ctx.process_id,
    )


async def _direct_requests(engine, ctx):
    return await count_rows(
        engine,
        DirectReviewRequest,
        DirectReviewRequest.process_instance_id == ctx.process_id,
    )


async def _reports(engine, ctx):
    return await count_rows(
        engine,
        Artifact,
        Artifact.process_instance_id == ctx.process_id,
        Artifact.key == 'ai_pre_evaluation_report',
    )


@pytest.mark.asyncio
async def test_double_retry_creates_one_run(engine, return_email_settings):
    del return_email_settings
    async with committed_return_review(engine, 'ai_failed') as ctx:
        results = await asyncio.gather(
            _retry(engine, ctx), _retry(engine, ctx), return_exceptions=True
        )

        winners, conflicts = split_outcomes(results)
        assert (len(winners), len(conflicts)) == (1, 1)
        assert await _evaluation_runs(engine, ctx) == 2
        assert (
            await count_rows(
                engine,
                AuditEvent,
                AuditEvent.process_instance_id == ctx.process_id,
                AuditEvent.event_type == 'NOTIFICATION_CANCELLED',
            )
            == 1
        )


@pytest.mark.asyncio
async def test_retry_and_contest_race_has_one_winner(engine, monkeypatch):
    original = svc.request_direct_review
    lock_held = asyncio.Event()

    async def slow_contest(*args, **kwargs):
        # A contestação já tem a trava do retorno e segura o commit para o
        # reprocessamento chegar a ela.
        lock_held.set()
        await asyncio.sleep(0.1)
        return await original(*args, **kwargs)

    async def retry_during_contest(ctx):
        await asyncio.wait_for(lock_held.wait(), timeout=5)
        return await _retry(engine, ctx)

    monkeypatch.setattr(svc, 'request_direct_review', slow_contest)
    async with committed_return_review(engine, 'ai_failed') as ctx:
        results = await asyncio.gather(
            _contest(engine, ctx),
            retry_during_contest(ctx),
            return_exceptions=True,
        )

        split_outcomes(results)
        assert isinstance(results[1], ConflictError)
        assert await _evaluation_runs(engine, ctx) == 1
        assert await _direct_requests(engine, ctx) == 1


@pytest.mark.asyncio
async def test_execute_and_retry_race_keeps_one_result(engine):
    async with committed_return_review(engine, 'ai_in_progress') as ctx:
        results = await asyncio.gather(
            _execute(engine, ctx), _retry(engine, ctx), return_exceptions=True
        )

        winners, conflicts = split_outcomes(results)
        assert (len(winners), len(conflicts)) == (1, 1)
        assert results[0] is None
        assert await _evaluation_runs(engine, ctx) == 1
        assert await _reports(engine, ctx) == 1


@pytest.mark.asyncio
async def test_execute_and_contest_race_keeps_one_result(engine):
    async with committed_return_review(engine, 'ai_in_progress') as ctx:
        results = await asyncio.gather(
            _execute(engine, ctx),
            _contest(engine, ctx),
            return_exceptions=True,
        )

        split_outcomes(results)
        assert results[0] is None
        assert await _reports(engine, ctx) == 1
        assert await _direct_requests(engine, ctx) <= 1
