from http import HTTPStatus

import pytest

from pivma.routers.users import create_user
from pivma.schemas import UserSchema


@pytest.mark.asyncio
async def test_public_registration_initializes_audit_fields(client, session):
    response = client.post(
        '/users/',
        json={
            'username': 'audit.user',
            'email': 'audit@example.com',
            'password': 'Audit-Passphrase-2026',
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    db_user = await create_user(
        UserSchema(
            username='audit.direct',
            email='audit.direct@example.com',
            password='Audit-Direct-Passphrase-2026',
        ),
        session,
    )
    assert db_user.created_at is not None
    assert db_user.created_by is None
    assert db_user.updated_at is None
    assert db_user.updated_by is None
    assert db_user.deleted_at is None
    assert db_user.deleted_by is None
    assert set(response.json()) == {'id', 'username', 'email'}
