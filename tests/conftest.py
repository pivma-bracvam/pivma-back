import os
from contextlib import contextmanager
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event, select
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
os.environ.setdefault('AI_PROVIDER', 'fake')

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


@pytest.fixture(autouse=True)
def _stub_pre_evaluation_background(monkeypatch):
    """A pré-avaliação assíncrona abre a própria sessão (fora do container
    de teste); nos testes ela é chamada explicitamente via ``_execute``."""

    async def _noop(_run_id):
        return None

    for target in (
        'pivma.routers.forms.run_pre_evaluation',
        'pivma.core.pre_evaluation_service.run_pre_evaluation',
    ):
        monkeypatch.setattr(target, _noop, raising=False)


async def _make_rbac_user(session, *, system_key, name, codes):
    """Cria um usuário com um perfil de acesso e as permissões `codes`."""
    from pivma.core.database.models import (  # noqa: PLC0415
        AccessProfile,
        AccessProfilePermission,
        Permission,
        UserAccessProfile,
    )

    user = UserFactory()
    profile = AccessProfile(system_key=system_key, name=name, description=name)
    session.add_all([user, profile])
    await session.flush()
    for code in codes:
        permission = await session.scalar(
            select(Permission).where(Permission.code == code)
        )
        if permission is None:
            permission = Permission(
                code=code, description=f'Permission {code}'
            )
            session.add(permission)
            await session.flush()
        session.add(
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
        )
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile.id))
    await session.commit()
    return user


@pytest_asyncio.fixture
async def ai_eval_admin(session):
    """Administrador BraCVAM: config de IA + triagem (Spec 013 + 014)."""
    from tests.ai_eval_helpers import AI_EVAL_CODES  # noqa: PLC0415

    return await _make_rbac_user(
        session,
        system_key='administrator',
        name='Administrador',
        codes=(*AI_EVAL_CODES, 'triage.review'),
    )


@pytest_asyncio.fixture
async def bracvam_user(session):
    """Usuário do perfil BraCVAM (Spec 014): triagem + config de IA."""
    from tests.ai_eval_helpers import AI_EVAL_CODES  # noqa: PLC0415

    return await _make_rbac_user(
        session,
        system_key='bracvam',
        name='BraCVAM',
        codes=(*AI_EVAL_CODES, 'triage.review'),
    )


@pytest_asyncio.fixture
async def non_triage_user(session):
    """Usuário do perfil Grupo Gestor: sem permissão de triagem."""
    return await _make_rbac_user(
        session,
        system_key='management_group',
        name='Grupo Gestor',
        codes=(),
    )


@pytest.fixture
def fake_provider():
    """Injeta o provedor fake determinístico no app (Spec 013)."""
    from pivma import app  # noqa: PLC0415
    from pivma.ai.provider import FakeModelProvider  # noqa: PLC0415
    from pivma.dependencies import get_model_provider  # noqa: PLC0415

    provider = FakeModelProvider()
    app.dependency_overrides[get_model_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_model_provider, None)


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
