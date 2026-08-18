import os
from contextlib import contextmanager
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault(
    'DATABASE_URL',
    'postgresql+psycopg://unused:unused@localhost/unused',
)
os.environ.setdefault(
    'JWT_SECRET_KEY',
    'test-jwt-secret-key-with-at-least-32-bytes',
)
os.environ.setdefault('AUTH_ALLOWED_ORIGINS', '["https://testserver"]')

from pivma import app
from pivma.core.database import get_session
from pivma.core.database.models import table_registry
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.user_factory import UserFactory


@pytest.fixture(scope='session')
def engine():
    # Caso do windows + Docker no CI
    import sys  # noqa: PLC0415

    if sys.platform == 'win32':
        yield create_async_engine(Settings().DATABASE_URL)
    else:
        with PostgresContainer(
            'pgvector/pgvector:pg17', driver='psycopg'
        ) as postgres:
            _engine = create_async_engine(postgres.get_connection_url())
            yield _engine


@pytest_asyncio.fixture(scope='session', autouse=True)
async def setup_database(engine):
    """Cria as tabelas uma única vez no início da sessão de testes."""
    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.drop_all)


@pytest_asyncio.fixture
async def session(engine):
    """Sessão isolada via transação e savepoint (nested transaction)."""
    connection = await engine.connect()
    transaction = await connection.begin()
    nested = await connection.begin_nested()

    session = AsyncSession(bind=connection, expire_on_commit=False)

    @event.listens_for(session.sync_session, 'after_transaction_end')
    def restart_savepoint(sync_session, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.sync_connection.begin_nested()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
def client(session):
    def get_session_override():
        return session

    with TestClient(app, base_url='https://testserver') as client:
        app.dependency_overrides[get_session] = get_session_override
        yield client

    app.dependency_overrides.clear()


@contextmanager
def _mock_db_time(*, model, time=datetime(2024, 1, 1)):
    def fake_time_handler(mapper, connection, target):
        if hasattr(target, 'created_at'):
            target.created_at = time
        if hasattr(target, 'updated_at'):
            target.updated_at = time

    event.listen(model, 'before_insert', fake_time_handler)
    yield time
    event.remove(model, 'before_insert', fake_time_handler)


@pytest.fixture
def mock_db_time():
    return _mock_db_time


@pytest_asyncio.fixture
async def user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def deleted_user(session):
    user = UserFactory()
    user.deleted_at = datetime(2026, 8, 12)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
def auth_token(user):
    settings = Settings()
    return create_access_token(user.id, settings.JWT_SECRET_KEY)
