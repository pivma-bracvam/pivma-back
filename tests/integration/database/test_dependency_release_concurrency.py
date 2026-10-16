"""Dois pré-requisitos concluídos ao mesmo tempo (Spec 042, research R12).

Uma atividade só abre quando todas as dependências concluem. Se as duas
últimas concluem em transações simultâneas, cada uma pode ler a outra ainda
em andamento, e a atividade ficaria bloqueada sem ninguém para abri-la.

A ordem é forçada, sem depender de sorte: a transação A conclui o primeiro
pré-requisito e não confirma; a transação B conclui o segundo. O teste só
confirma A depois de ver B terminar ou esperar por uma trava em
`pg_stat_activity`. Os dados ficam confirmados fora da transação do teste,
e todas as tabelas são esvaziadas ao final.
"""

import asyncio
import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.core import participant_service
from pivma.core.database.models import ProcessInstance
from pivma.core.structure_approval_service import execute_structure_decision
from tests.api.routers.test_sample_receipt_concurrency import (
    _truncate,  # noqa: PLC2701
)
from tests.conftest import _make_rbac_user
from tests.factories.structure_approval_factory import (
    activity,
    designate,
    events,
    planning_process,
    runs,
    structure_process,
)

LOCK_WAIT_LIMIT_SECONDS = 5
WAITING_FOR_ACTIVITY = text(
    'SELECT count(*) FROM pg_stat_activity '
    "WHERE wait_event_type = 'Lock' "
    "AND query LIKE '%FROM activity_instances%'"
)


async def _bracvam(session):
    return await _make_rbac_user(
        session, system_key='bracvam', name='BraCVAM', codes=()
    )


async def _assign(session, ctx, user, role_key, laboratory=None):
    """Designa pelo serviço, sem confirmar a transação."""
    process = await session.get(ProcessInstance, ctx.process_id)
    await participant_service.create_assignment(
        session,
        process,
        user_id=user.id,
        role_key=role_key,
        laboratory_id=laboratory.id if laboratory else None,
        actor_id=ctx.proponent.id,
        source='api',
    )


async def _complete(session, ctx, role_key):
    """Declara concluída a atribuição reaberta, sem confirmar (R14)."""
    process = await session.get(ProcessInstance, ctx.process_id)
    await participant_service.complete_role_assignment(
        session, process, role_key, ctx.manager.id
    )


async def _b_finished_or_waiting(engine, task) -> bool:
    deadline = time.monotonic() + LOCK_WAIT_LIMIT_SECONDS
    while time.monotonic() < deadline:
        if task.done():
            return True
        async with engine.connect() as connection:
            if await connection.scalar(WAITING_FOR_ACTIVITY):
                return True
        await asyncio.sleep(0.05)
    return False


async def _race(engine, first, second) -> None:
    """A executa `first` sem confirmar; B executa `second` e confirma."""

    async def run_b():
        async with AsyncSession(engine, expire_on_commit=False) as session_b:
            await second(session_b)
            await session_b.commit()

    async with AsyncSession(engine, expire_on_commit=False) as session_a:
        await first(session_a)
        await session_a.flush()
        task_b = asyncio.create_task(run_b())
        assert await _b_finished_or_waiting(engine, task_b)
        await session_a.commit()
    await task_b


@pytest.mark.asyncio
async def test_last_two_rejected_points_reopen_the_approval_once(engine):
    try:
        async with AsyncSession(engine, expire_on_commit=False) as setup:
            bracvam = await _bracvam(setup)
            ctx = await structure_process(setup, bracvam)
            await execute_structure_decision(
                setup,
                ctx.process_id,
                bracvam.id,
                'REJECTED',
                'Equipe incompleta.',
                [
                    {
                        'activity_key': 'assign_statistician',
                        'reason': 'Rever.',
                    },
                    {'activity_key': 'assign_sponsor', 'reason': 'Rever.'},
                ],
            )

        await _race(
            engine,
            lambda s: _complete(s, ctx, 'statistician'),
            lambda s: _complete(s, ctx, 'sponsor'),
        )

        async with AsyncSession(engine) as check:
            approval = await activity(check, ctx.process_id)
            approval_runs = await runs(check, ctx.process_id)
            unblocked = await events(
                check, ctx.process_id, 'ACTIVITY_UNBLOCKED'
            )
        assert approval.status == 'IN_PROGRESS'
        assert [(r.run_number, r.status) for r in approval_runs] == [
            (1, 'COMPLETED'),
            (2, 'IN_PROGRESS'),
        ]
        reopened_run = approval_runs[1].id
        assert [e.activity_run_id for e in unblocked].count(reopened_run) == 1
    finally:
        await _truncate(engine)


@pytest.mark.asyncio
async def test_sample_definition_opens_when_its_two_roles_close_together(
    engine,
):
    try:
        async with AsyncSession(engine, expire_on_commit=False) as setup:
            ctx = await planning_process(setup, await _bracvam(setup))
            await designate(setup, ctx, ctx.manager, 'group_manager')

        await _race(
            engine,
            lambda s: _assign(s, ctx, ctx.selector, 'sample_selection_group'),
            lambda s: _assign(
                s,
                ctx,
                ctx.lab_users[0],
                'participating_laboratory',
                ctx.laboratories[0],
            ),
        )

        async with AsyncSession(engine) as check:
            samples = await activity(
                check, ctx.process_id, 'sample_definition'
            )
            sample_runs = await runs(
                check, ctx.process_id, 'sample_definition'
            )
        assert samples.status == 'IN_PROGRESS'
        assert [r.run_number for r in sample_runs] == [1]
    finally:
        await _truncate(engine)
