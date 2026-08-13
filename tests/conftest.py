import os
from contextlib import contextmanager
from datetime import datetime

import factory
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
from pivma.core.database.models import User, table_registry
from pivma.core.security import hash_password
from pivma.core.settings import Settings


@pytest.fixture
def client(session):
    def get_session_override():
        return session

    with TestClient(app, base_url='https://testserver') as client:
        app.dependency_overrides[get_session] = get_session_override
        yield client

    app.dependency_overrides.clear()


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


@pytest_asyncio.fixture
async def session(engine):
    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.drop_all)


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


class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'test{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    password_hash = factory.LazyFunction(
        lambda: hash_password('Factory-Passphrase-2026')
    )
