from http import HTTPStatus

import pytest

from pivma.core.security import verify_password
from pivma.routers.users import create_user
from pivma.schemas import UserSchema

VALID_PASSWORD = 'Unique-Passphrase-2026'


def test_create_user(client):
    response = client.post(
        '/users/',
        json={
            'username': 'alice',
            'email': 'alice@example.com',
            'password': VALID_PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    assert 'id' in response.json()
    assert response.json()['username'] == 'alice'
    assert response.json()['email'] == 'alice@example.com'
    assert 'password' not in response.json()


@pytest.mark.asyncio
async def test_create_user_stores_only_argon2id_hash(session):
    user = UserSchema.model_validate({
        'username': 'Secure.User',
        'email': 'Secure.User@Example.COM',
        'password': VALID_PASSWORD,
    })

    db_user = await create_user(user, session)

    assert db_user.password_hash.startswith('$argon2id$')
    assert db_user.password_hash != VALID_PASSWORD
    assert verify_password(db_user.password_hash, VALID_PASSWORD)


def test_create_user_already_exists_username(client, user):
    response = client.post(
        '/users/',
        json={
            'username': user.username,
            'email': 'different@example.com',
            'password': VALID_PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_already_exists_email(client, user):
    response = client.post(
        '/users/',
        json={
            'username': 'different',
            'email': user.email,
            'password': VALID_PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Email already exists'}


def test_create_user_rejects_case_insensitive_username(client, user):
    response = client.post(
        '/users/',
        json={
            'username': user.username.swapcase(),
            'email': 'available@example.com',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_rejects_case_insensitive_email(client, user):
    response = client.post(
        '/users/',
        json={
            'username': 'available',
            'email': user.email.swapcase(),
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Email already exists'}


def test_create_user_preserves_username_and_email_case_after_trim(client):
    response = client.post(
        '/users/',
        json={
            'username': '  Alice.Example  ',
            'email': '  Alice.Example@Example.COM  ',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['username'] == 'Alice.Example'
    assert response.json()['email'] == 'Alice.Example@Example.COM'


def test_create_user_reports_username_before_email(client, user):
    response = client.post(
        '/users/',
        json={
            'username': user.username,
            'email': user.email,
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {'detail': 'Username already exists'}


def test_create_user_frees_identifiers_after_deletion(client, deleted_user):
    response = client.post(
        '/users/',
        json={
            'username': deleted_user.username.swapcase(),
            'email': 'available-after-delete@example.com',
            'password': VALID_PASSWORD,
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['username'] == deleted_user.username.swapcase()


def test_create_user_sanitizes_password_validation_error(client):
    response = client.post(
        '/users/',
        json={
            'username': 'invalid-password',
            'email': 'invalid@example.com',
            'password': 'secret value',
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {'detail': 'Invalid password'}
    assert 'secret value' not in response.text
