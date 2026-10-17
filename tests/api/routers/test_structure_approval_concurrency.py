"""Decisões simultâneas sobre a mesma homologação (Spec 042, FR-018).

Os dados são confirmados fora da transação do teste, para que as duas
requisições concorram de verdade; ao final, todas as tabelas são esvaziadas.
"""

import asyncio
from http import HTTPStatus
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.database import get_session
from tests.api.routers.test_participant_concurrency import run_concurrently
from tests.api.routers.test_sample_receipt_concurrency import (
    _count_events,  # noqa: PLC2701
    _headers,  # noqa: PLC2701
    _session_factory,  # noqa: PLC2701
    _truncate,  # noqa: PLC2701
)
from tests.conftest import _make_rbac_user
from tests.factories.structure_approval_factory import (
    decisions,
    structure_process,
)

APPROVE = {'outcome': 'APPROVED', 'justification': 'Estrutura conferida.'}
REJECT = {
    'outcome': 'REJECTED',
    'justification': 'Equipe incompleta.',
    'rejected_points': [
        {'activity_key': 'assign_sponsor', 'reason': 'Patrocinador errado.'}
    ],
}


async def _setup(engine):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        bracvam = await _make_rbac_user(
            session, system_key='bracvam', name='BraCVAM', codes=()
        )
        ctx = await structure_process(session, bracvam)
        return SimpleNamespace(process_id=ctx.process_id, bracvam=bracvam)


async def _decisions(engine, process_id):
    async with AsyncSession(engine) as session:
        return await decisions(session, process_id)


def _decide(ctx, body):
    url = f'/processes/{ctx.process_id}/structure-approval/decision'
    headers = _headers(ctx.bracvam.id)
    return lambda client: client.post(url, json=body, headers=headers)


def _run(engine, requests):
    app.dependency_overrides[get_session] = _session_factory(engine)
    try:
        with TestClient(app, base_url='https://testserver') as client:
            return run_concurrently(client, requests)
    finally:
        app.dependency_overrides.clear()


def _assert_one_won(responses):
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [HTTPStatus.OK, HTTPStatus.CONFLICT]
    refused = next(
        r for r in responses if r.status_code == HTTPStatus.CONFLICT
    )
    assert refused.json()['detail']['code'] == 'invalid_transition'


def test_two_approvals_record_one_decision(engine):
    ctx = asyncio.run(_setup(engine))
    try:
        responses = _run(
            engine, [_decide(ctx, APPROVE), _decide(ctx, APPROVE)]
        )

        _assert_one_won(responses)
        assert len(asyncio.run(_decisions(engine, ctx.process_id))) == 1
        approved = asyncio.run(
            _count_events(engine, ctx.process_id, 'STRUCTURE_APPROVED')
        )
        assert approved == 1
    finally:
        asyncio.run(_truncate(engine))


def test_approval_and_rejection_record_one_decision(engine):
    ctx = asyncio.run(_setup(engine))
    try:
        responses = _run(engine, [_decide(ctx, APPROVE), _decide(ctx, REJECT)])

        _assert_one_won(responses)
        assert len(asyncio.run(_decisions(engine, ctx.process_id))) == 1
    finally:
        asyncio.run(_truncate(engine))
