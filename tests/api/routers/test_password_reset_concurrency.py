"""Spec 039 — uso único e pedidos simultâneos (FR-005, FR-014).

Cada requisição usa a própria sessão, com dados commitados e limpos ao
final, como em `test_user_concurrency.py`.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.database import get_session
from pivma.core.database.models import Notification, PasswordResetToken, User
from pivma.core.security import verify_password
from pivma.notifications.channels import FakeEmailChannel
from pivma.notifications.worker import process_next
from tests.api.routers.test_password_reset import (
    RESET_URL_PREFIX,
    RESET_URL_TEMPLATE,
    forgot,
    reset,
)
from tests.conftest import email_settings
from tests.factories.user_factory import UserFactory

PASSWORDS = ('Concorrente-Senha-A-2026', 'Concorrente-Senha-B-2026')


@pytest.fixture
def settings(use_settings):
    return use_settings(
        email_settings(PASSWORD_RESET_URL_TEMPLATE=RESET_URL_TEMPLATE)
    )


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
def committed_user(engine):
    user = UserFactory()

    async def create():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(user)
            await session.commit()

    async def cleanup():
        async with AsyncSession(engine) as session:
            await session.execute(
                delete(Notification).where(Notification.subject_id == user.id)
            )
            await session.execute(
                delete(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id
                )
            )
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()

    asyncio.run(create())
    yield user
    asyncio.run(cleanup())


def deliver_reset_token(engine, settings):
    async def run():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            channel = FakeEmailChannel()
            await process_next(session, channel, settings)
            return channel.sent[-1].text

    text = asyncio.run(run())
    return re.search(
        re.escape(RESET_URL_PREFIX) + r'([A-Za-z0-9_-]+)', text
    ).group(1)


def race_resets(client, token):
    """Duas redefinições simultâneas; devolve o status de cada senha."""
    with ThreadPoolExecutor(2) as executor:
        responses = executor.map(
            lambda password: reset(client, token, password), PASSWORDS
        )
        return {
            password: response.status_code
            for password, response in zip(PASSWORDS, responses, strict=True)
        }


def read_rows(engine, user):
    async def run():
        async with AsyncSession(engine) as session:
            tokens = list(
                await session.scalars(
                    select(PasswordResetToken)
                    .where(PasswordResetToken.user_id == user.id)
                    .execution_options(skip_soft_delete_filter=True)
                )
            )
            stored_user = await session.get(User, user.id)
            return tokens, stored_user

    return asyncio.run(run())


def test_concurrent_resets_with_same_token_succeed_once(
    engine, client, committed_user, settings
):
    """FR-014."""
    forgot(client, committed_user.email)
    token = deliver_reset_token(engine, settings)

    statuses = race_resets(client, token)

    assert sorted(statuses.values()) == [
        HTTPStatus.NO_CONTENT,
        HTTPStatus.BAD_REQUEST,
    ]


def test_concurrent_resets_keep_password_of_successful_request(
    engine, client, committed_user, settings
):
    forgot(client, committed_user.email)
    token = deliver_reset_token(engine, settings)

    statuses = race_resets(client, token)

    [winner] = [
        password
        for password, status in statuses.items()
        if status == HTTPStatus.NO_CONTENT
    ]
    [stored_token], stored_user = read_rows(engine, committed_user)
    assert stored_token.used_at is not None
    assert verify_password(stored_user.password_hash, winner)


def test_concurrent_requests_leave_one_valid_token(
    engine, client, committed_user, settings
):
    """FR-005."""
    with ThreadPoolExecutor(2) as executor:
        list(
            executor.map(
                lambda _: forgot(client, committed_user.email), range(2)
            )
        )

    tokens, _user = read_rows(engine, committed_user)
    assert len(tokens) == 2  # noqa: PLR2004
    assert [token.deleted_at for token in tokens].count(None) == 1
