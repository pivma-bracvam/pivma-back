import asyncio
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.database import get_session
from pivma.core.database.models import User


@pytest.mark.parametrize('conflict_field', ['username', 'email'])
def test_two_concurrent_equivalent_registrations_create_one_user(
    engine, session, conflict_field
):
    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as db_session:
            yield db_session

    first = {
        'username': 'Concurrent.User',
        'email': 'concurrent.first@example.com',
        'password': 'Concurrent-Passphrase-2026-A',
    }
    second = {
        'username': 'concurrent.user',
        'email': 'concurrent.second@example.com',
        'password': 'Concurrent-Passphrase-2026-B',
    }
    if conflict_field == 'email':
        second['username'] = 'Concurrent.Second'
        second['email'] = first['email'].swapcase()

    app.dependency_overrides[get_session] = independent_session
    try:
        with TestClient(app) as client, ThreadPoolExecutor(2) as executor:
            responses = list(
                executor.map(
                    lambda payload: client.post('/users', json=payload),
                    (first, second),
                )
            )

        assert sorted(response.status_code for response in responses) == [
            HTTPStatus.CREATED,
            HTTPStatus.CONFLICT,
        ]

        async def count_users():
            async with AsyncSession(engine) as db_session:
                return await db_session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(
                        func.lower(User.username).in_([
                            first['username'].lower(),
                            second['username'].lower(),
                        ])
                    )
                )

        assert asyncio.run(count_users()) == 1
    finally:
        app.dependency_overrides.clear()

        async def cleanup():
            async with AsyncSession(engine) as db_session:
                await db_session.execute(
                    delete(User).where(
                        func.lower(User.username).in_([
                            first['username'].lower(),
                            second['username'].lower(),
                        ])
                    )
                )
                await db_session.commit()

        asyncio.run(cleanup())
