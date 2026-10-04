"""Registros e decisões simultâneos no recebimento (Spec 040, R11).

Os dados são confirmados fora da transação do teste, para que as duas
requisições concorram de verdade; ao final, todas as tabelas são esvaziadas
(nenhum outro teste deixa dados confirmados).
"""

import asyncio
from http import HTTPStatus

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.database import get_session
from pivma.core.database.models import (
    AuditEvent,
    SampleReceiptNonconformity,
    table_registry,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.api.routers.test_participant_concurrency import run_concurrently
from tests.factories.sample_receipt_factory import (
    codes_of,
    receipt_payload,
    receipt_process,
)


def _headers(user_id):
    return {
        'Cookie': 'access_token='
        + create_access_token(user_id, Settings().JWT_SECRET_KEY),
        'Origin': 'https://testserver',
    }


async def _setup(engine, **kwargs):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        ctx = await receipt_process(session, **kwargs)
        ctx.codes = [await codes_of(session, ctx, i) for i in range(2)]
        return ctx


async def _truncate(engine):
    tables = ', '.join(
        f'"{t.name}"' for t in table_registry.metadata.sorted_tables
    )
    async with engine.begin() as connection:
        await connection.execute(text(f'TRUNCATE {tables} CASCADE'))


async def _count_events(engine, process_id, event_type):
    async with AsyncSession(engine) as session:
        return await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.process_instance_id == process_id,
                AuditEvent.event_type == event_type,
            )
        )


async def _open_items(engine, process_id):
    async with AsyncSession(engine) as session:
        return list(
            await session.scalars(
                select(SampleReceiptNonconformity.id)
                .where(
                    SampleReceiptNonconformity.process_instance_id
                    == process_id
                )
                .order_by(SampleReceiptNonconformity.laboratory_id)
            )
        )


def _session_factory(engine):
    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    return independent_session


def _run(engine, requests):
    """Executa as requisições ao mesmo tempo; devolve os status."""
    app.dependency_overrides[get_session] = _session_factory(engine)
    try:
        with TestClient(app, base_url='https://testserver') as client:
            return [r.status_code for r in run_concurrently(client, requests)]
    finally:
        app.dependency_overrides.clear()


def _call(engine, request):
    """Uma requisição sozinha, com dados confirmados."""
    app.dependency_overrides[get_session] = _session_factory(engine)
    try:
        with TestClient(app, base_url='https://testserver') as client:
            response = request(client)
            assert response.status_code < HTTPStatus.BAD_REQUEST, response.text
    finally:
        app.dependency_overrides.clear()


def _register(ctx, lab, code, **overrides):
    url = f'/processes/{ctx.process_id}/sample-receipt/vials/{code}'
    headers = _headers(ctx.lab_users[lab].id)
    payload = receipt_payload(**overrides)
    return lambda client: client.post(url, json=payload, headers=headers)


def _decide(ctx, item_id, decision):
    url = (
        f'/processes/{ctx.process_id}/sample-receipt/nonconformities/'
        f'{item_id}/decision'
    )
    headers = _headers(ctx.selector.id)
    body = {'decision': decision, 'justification': 'Concorrência.'}
    return lambda client: client.post(url, json=body, headers=headers)


def test_same_vial_registered_twice_at_once_keeps_one(engine):
    ctx = asyncio.run(_setup(engine))
    try:
        code = ctx.codes[0][0]
        statuses = _run(
            engine, [_register(ctx, 0, code), _register(ctx, 0, code)]
        )
        assert sorted(statuses) == [HTTPStatus.CREATED, HTTPStatus.CONFLICT]
    finally:
        asyncio.run(_truncate(engine))


def test_last_two_vials_at_once_complete_lab_once(engine):
    ctx = asyncio.run(_setup(engine))
    try:
        first, second = ctx.codes[0]
        statuses = _run(
            engine, [_register(ctx, 0, first), _register(ctx, 0, second)]
        )
        assert statuses == [HTTPStatus.CREATED, HTTPStatus.CREATED]
        completed = asyncio.run(
            _count_events(engine, ctx.process_id, 'LABORATORY_RUN_COMPLETED')
        )
        assert completed == 1
    finally:
        asyncio.run(_truncate(engine))


def test_two_decisions_on_same_item_keep_one(engine):
    ctx = asyncio.run(_setup(engine))
    try:
        _call(
            engine,
            _register(ctx, 0, ctx.codes[0][0], package_state='damaged'),
        )
        (item_id,) = asyncio.run(_open_items(engine, ctx.process_id))
        statuses = _run(
            engine,
            [
                _decide(ctx, item_id, 'accept_with_caveat'),
                _decide(ctx, item_id, 'resend'),
            ],
        )
        assert sorted(statuses) == [HTTPStatus.OK, HTTPStatus.CONFLICT]
    finally:
        asyncio.run(_truncate(engine))


def test_two_resends_with_one_reserve_vial_keep_one(engine):
    ctx = asyncio.run(_setup(engine, substance_count=1, reserve=1))
    try:
        for lab in (0, 1):
            _call(
                engine,
                _register(
                    ctx, lab, ctx.codes[lab][0], package_state='damaged'
                ),
            )
        items = asyncio.run(_open_items(engine, ctx.process_id))
        statuses = _run(
            engine, [_decide(ctx, item, 'resend') for item in items]
        )
        assert sorted(statuses) == [HTTPStatus.OK, HTTPStatus.CONFLICT]
    finally:
        asyncio.run(_truncate(engine))
