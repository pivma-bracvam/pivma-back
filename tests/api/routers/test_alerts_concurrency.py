"""Marcações de leitura simultâneas (Spec 047, US2, research R9).

Cada requisição usa a própria sessão, com dados commitados e limpos ao
final, como em `test_password_reset_concurrency.py`.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.database import get_session
from pivma.core.database.models import (
    Alert,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.alert_factory import make_alert, make_process, make_user

UNREAD = 4


@pytest.fixture
def client(engine):
    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = independent_session
    with TestClient(app, base_url='https://testserver') as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def inbox(engine):
    """Usuário com alerts não lidos, commitados fora da transação do teste."""

    async def create():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            process = await make_process(session)
            user = await make_user(session)
            alerts = [
                await make_alert(session, user, process) for _ in range(UNREAD)
            ]
            return user, process, alerts

    async def cleanup(user, process):
        async with AsyncSession(engine) as session:
            await session.execute(
                delete(Alert).where(Alert.user_id == user.id)
            )
            version_id = process.template_version_id
            version = await session.get(ProcessTemplateVersion, version_id)
            await session.execute(
                delete(ProcessInstance).where(ProcessInstance.id == process.id)
            )
            await session.execute(
                delete(ProcessTemplateVersion).where(
                    ProcessTemplateVersion.id == version_id
                )
            )
            await session.execute(
                delete(ProcessTemplate).where(
                    ProcessTemplate.id == version.template_id
                )
            )
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()

    user, process, alerts = asyncio.run(create())
    yield user, alerts
    asyncio.run(cleanup(user, process))


def _headers(user):
    token = create_access_token(user.id, Settings().JWT_SECRET_KEY)
    return {'Authorization': f'Bearer {token}'}


def _race(client, user, paths):
    with ThreadPoolExecutor(len(paths)) as executor:
        return list(
            executor.map(
                lambda path: client.post(path, headers=_headers(user)), paths
            )
        )


def _stored(engine, user):
    async def run():
        async with AsyncSession(engine) as session:
            return list(
                await session.scalars(
                    select(Alert).where(Alert.user_id == user.id)
                )
            )

    return asyncio.run(run())


def test_concurrent_read_all_marks_each_alert_once(engine, client, inbox):
    user, _ = inbox

    responses = _race(client, user, ['/alerts/read-all', '/alerts/read-all'])

    assert [r.status_code for r in responses] == [HTTPStatus.OK] * 2
    assert sum(r.json()['updated'] for r in responses) == UNREAD
    assert all(alert.read_at for alert in _stored(engine, user))


def test_concurrent_read_one_and_read_all_keep_single_read_at(
    engine, client, inbox
):
    user, alerts = inbox
    target = alerts[0]

    responses = _race(
        client, user, [f'/alerts/{target.id}/read', '/alerts/read-all']
    )

    assert [r.status_code for r in responses] == [HTTPStatus.OK] * 2
    read_one = responses[0].json()['read_at']
    stored = {alert.id: alert for alert in _stored(engine, user)}
    assert stored[target.id].read_at.isoformat() == read_one
