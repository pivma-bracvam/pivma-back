"""Alterações simultâneas no template de coleta (Spec 041, FR-019).

Os dados são confirmados fora da transação do teste, para que as operações
concorram de verdade; ao final, todas as tabelas são esvaziadas.

Nos dois primeiros testes, uma conexão segura a trava da linha do template
enquanto a requisição roda. O teste confirma em ``pg_stat_activity`` que a
requisição espera por essa trava antes de liberá-la, sem depender de tempo.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.collection_template_service import locked_template_ids
from pivma.core.database import get_session
from pivma.core.database.models import CollectionTemplateColumn
from tests.api.routers.test_participant_concurrency import run_concurrently
from tests.api.routers.test_sample_receipt_concurrency import (
    _headers,  # noqa: PLC2701
    _session_factory,  # noqa: PLC2701
    _truncate,  # noqa: PLC2701
)
from tests.factories.collection_template_factory import (
    catalog_manager,
    collection_template,
    column_payload,
    linked_process,
)

LOCK_WAIT_LIMIT_SECONDS = 5
LOCK_TEMPLATE_ROW = text(
    'SELECT id FROM collection_templates WHERE id = :id FOR UPDATE'
)
# A requisição espera pela linha do template travada pelo teste.
WAITING_FOR_TEMPLATE = text(
    'SELECT count(*) FROM pg_stat_activity '
    "WHERE wait_event_type = 'Lock' "
    "AND query LIKE '%FROM collection_templates%'"
)


async def _setup(engine):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        manager = await catalog_manager(session)
        template = await collection_template(session, manager)
        ctx = await linked_process(
            session, template.id, complete_definition=False
        )
        return SimpleNamespace(
            manager_id=manager.id,
            template_id=template.id,
            process_id=ctx.process_id,
            selector_id=ctx.selector.id,
        )


async def _columns(engine, template_id):
    async with AsyncSession(engine) as session:
        return list(
            await session.scalars(
                select(CollectionTemplateColumn).where(
                    CollectionTemplateColumn.collection_template_id
                    == template_id
                )
            )
        )


async def _is_locked(engine, template_id):
    async with AsyncSession(engine) as session:
        return template_id in await locked_template_ids(session, [template_id])


def _waits_for_template_lock(sync_engine) -> bool:
    deadline = time.monotonic() + LOCK_WAIT_LIMIT_SECONDS
    while time.monotonic() < deadline:
        # Uma transação por consulta: dentro de uma transação, o
        # `pg_stat_activity` devolve sempre o mesmo retrato.
        with sync_engine.connect() as connection:
            if connection.scalar(WAITING_FOR_TEMPLATE):
                return True
        time.sleep(0.05)
    return False


def _while_holding_template(engine, ctx, write, request):
    """Trava o template, faz `write` e dispara `request` sem confirmar.

    Confirma depois de ver a requisição esperando; devolve se ela esperou e
    a resposta.
    """
    sync_engine = create_engine(
        engine.url.render_as_string(hide_password=False)
    )
    app.dependency_overrides[get_session] = _session_factory(engine)
    try:
        with (
            TestClient(app, base_url='https://testserver') as client,
            ThreadPoolExecutor(1) as executor,
        ):
            with sync_engine.begin() as connection:
                connection.execute(LOCK_TEMPLATE_ROW, {'id': ctx.template_id})
                write(connection)
                future = executor.submit(request, client)
                waited = _waits_for_template_lock(sync_engine)
            return waited, future.result()
    finally:
        app.dependency_overrides.clear()
        sync_engine.dispose()


def _run(engine, requests):
    """Executa as requisições ao mesmo tempo; devolve as respostas."""
    app.dependency_overrides[get_session] = _session_factory(engine)
    try:
        with TestClient(app, base_url='https://testserver') as client:
            return run_concurrently(client, requests)
    finally:
        app.dependency_overrides.clear()


def _add_column(ctx, **overrides):
    url = f'/collection-templates/{ctx.template_id}/columns'
    payload = column_payload(**overrides)
    headers = _headers(ctx.manager_id)
    return lambda client: client.post(url, json=payload, headers=headers)


def test_column_waits_for_sample_completion_and_is_refused(engine):
    """US3, cenário 8: a conclusão entra primeiro e a coluna é recusada."""
    ctx = asyncio.run(_setup(engine))
    try:

        def complete_samples(connection):
            connection.execute(
                text(
                    "UPDATE activity_instances SET status = 'COMPLETED' "
                    'WHERE process_instance_id = :process_id '
                    "AND key = 'sample_definition'"
                ),
                {'process_id': ctx.process_id},
            )

        waited, response = _while_holding_template(
            engine, ctx, complete_samples, _add_column(ctx)
        )

        assert waited
        assert response.status_code == HTTPStatus.CONFLICT, response.text
        assert response.json()['detail']['code'] == 'template_locked'
        assert asyncio.run(_columns(engine, ctx.template_id)) == []
    finally:
        asyncio.run(_truncate(engine))


def test_sample_completion_waits_for_structural_change(engine):
    """FR-019: a coluna entra primeiro e a conclusão espera por ela.

    Sem a trava em `complete_sample_definition`, a conclusão não espera e o
    teste falha na consulta a `pg_stat_activity`.
    """
    ctx = asyncio.run(_setup(engine))
    try:

        def add_column(connection):
            connection.execute(
                text(
                    'INSERT INTO collection_template_columns '
                    '(id, collection_template_id, label, key, column_type, '
                    'position, required) '
                    "VALUES (gen_random_uuid(), :template_id, 'Lote', "
                    "'lote', 'text', 1, false)"
                ),
                {'template_id': ctx.template_id},
            )

        url = f'/processes/{ctx.process_id}/samples/complete'
        headers = _headers(ctx.selector_id)
        waited, response = _while_holding_template(
            engine,
            ctx,
            add_column,
            lambda client: client.post(url, headers=headers),
        )

        assert waited
        assert response.status_code == HTTPStatus.OK, response.text
        columns = asyncio.run(_columns(engine, ctx.template_id))
        assert [column.key for column in columns] == ['lote']
        assert asyncio.run(_is_locked(engine, ctx.template_id))
    finally:
        asyncio.run(_truncate(engine))


def test_same_key_at_once_keeps_one_column(engine):
    """Edge Cases: sem 500, a segunda vê `duplicate_key`."""
    ctx = asyncio.run(_setup(engine))
    try:
        responses = _run(
            engine,
            [_add_column(ctx, key='lote'), _add_column(ctx, key='lote')],
        )

        statuses = sorted(r.status_code for r in responses)
        assert statuses == [HTTPStatus.CREATED, HTTPStatus.CONFLICT]
        refused = next(
            r for r in responses if r.status_code == HTTPStatus.CONFLICT
        )
        assert refused.json()['detail']['code'] == 'duplicate_key'
    finally:
        asyncio.run(_truncate(engine))


def test_two_columns_without_position_get_distinct_positions(engine):
    """Edge Cases: a posição automática não se repete."""
    ctx = asyncio.run(_setup(engine))
    try:
        responses = _run(engine, [_add_column(ctx), _add_column(ctx)])

        assert [r.status_code for r in responses] == [
            HTTPStatus.CREATED,
            HTTPStatus.CREATED,
        ]
        assert sorted(r.json()['position'] for r in responses) == [1, 2]
    finally:
        asyncio.run(_truncate(engine))
