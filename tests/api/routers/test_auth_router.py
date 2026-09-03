from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from pivma.core.database.models import (
    AccessProfile,
    Assignment,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)

VALID_PASSWORD = 'Factory-Passphrase-2026'
JWT_SECRET_KEY = 'test-jwt-secret-key-with-at-least-32-bytes'
TRUSTED_ORIGIN = 'https://testserver'


def login(client, identifier, password=VALID_PASSWORD):
    return client.post(
        '/auth/login',
        json={'identifier': identifier, 'password': password},
    )


def test_login_with_username_and_recognize_identity(client, user):
    response = login(client, user.username.swapcase())

    assert response.status_code == HTTPStatus.OK
    assert response.content == b''
    assert 'access_token' in client.cookies

    identity = client.get('/auth/me')

    assert identity.status_code == HTTPStatus.OK
    assert identity.json() == {
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
        },
        'access': {
            'profiles': [],
            'global_permissions': [],
            'scopes': [],
        },
    }


def test_login_with_email(client, user):
    response = login(client, user.email.swapcase())

    assert response.status_code == HTTPStatus.OK
    assert 'access_token' in client.cookies


@pytest.mark.asyncio
async def test_me_returns_effective_permissions_and_process_scopes(
    client, user, session
):
    template = ProcessTemplateFactory()
    version = ProcessTemplateVersionFactory(template=template)
    process = ProcessInstanceFactory(template_version=version)
    session.add_all([template, version, process])
    await session.flush()
    session.add(
        Assignment(
            process_instance_id=process.id,
            user_id=user.id,
            role_key='proponent',
            assigned_by=user.id,
        )
    )
    await session.flush()

    assert login(client, user.username).status_code == HTTPStatus.OK
    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['access']['global_permissions'] == []
    assert response.json()['access']['profiles'] == []
    assert response.json()['access']['scopes'] == [
        {
            'process_id': str(process.id),
            'institution_id': None,
            'laboratory_id': None,
            'roles': ['proponent'],
        }
    ]


@pytest.mark.asyncio
async def test_me_returns_active_global_profile_names(client, user, session):
    profile = AccessProfile(
        system_key=None,
        name='Grupo Gestor',
        description='Perfil de gestão',
    )
    session.add(profile)
    await session.flush()
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile.id))
    await session.flush()

    assert login(client, user.username).status_code == HTTPStatus.OK
    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['access']['profiles'] == [
        {'id': str(profile.id), 'name': 'Grupo Gestor', 'active': True}
    ]


def test_login_rejects_incorrect_password_without_secret(client, user):
    response = login(client, user.username, 'Incorrect-Passphrase-2026')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Invalid credentials'}
    assert 'Incorrect-Passphrase-2026' not in response.text
    assert 'access_token' not in client.cookies


def test_login_rejects_unknown_identifier_with_same_response(client):
    response = login(client, 'missing@example.com')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Invalid credentials'}
    assert 'access_token' not in client.cookies


def test_login_rejects_deleted_user_with_same_response(client, deleted_user):
    response = login(client, deleted_user.username)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Invalid credentials'}
    assert 'access_token' not in client.cookies


def test_me_rejects_missing_cookie(client):
    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}


def test_me_rejects_tampered_token(client, user):
    token = create_access_token(user.id, JWT_SECRET_KEY)
    header, payload, signature = token.split('.')
    replacement = 'a' if signature[0] != 'a' else 'b'
    tampered_token = f'{header}.{payload}.{replacement}{signature[1:]}'
    client.cookies.set('access_token', tampered_token)

    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}


def test_me_rejects_expired_token(client, user):
    token = create_access_token(
        user.id,
        JWT_SECRET_KEY,
        now=datetime.now(UTC) - timedelta(hours=8, seconds=1),
    )
    client.cookies.set('access_token', token)

    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}


def test_me_rejects_user_deleted_after_login(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK
    user.deleted_at = datetime.now(UTC)
    session.add(user)

    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}


def test_login_sets_secure_cookie_for_eight_hours(client, user):
    response = login(client, user.username)

    cookie = response.headers['set-cookie'].lower()
    assert 'access_token=' in cookie
    assert 'httponly' in cookie
    assert 'secure' in cookie
    assert 'samesite=strict' in cookie
    assert 'path=/' in cookie
    assert 'max-age=28800' in cookie


def test_logout_removes_cookie_for_trusted_origin(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = client.post(
        '/auth/logout',
        headers={'Origin': TRUSTED_ORIGIN},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert 'access_token' not in client.cookies
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie
    assert 'secure' in cookie
    assert 'samesite=strict' in cookie
    assert 'path=/' in cookie
    assert client.get('/auth/me').status_code == HTTPStatus.UNAUTHORIZED


def test_logout_rejects_missing_origin_without_removing_cookie(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = client.post('/auth/logout')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Invalid origin'}
    assert 'access_token' in client.cookies


def test_logout_rejects_untrusted_origin_without_removing_cookie(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = client.post(
        '/auth/logout',
        headers={'Origin': 'https://attacker.example'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Invalid origin'}
    assert 'access_token' in client.cookies


def test_logout_requires_authentication(client):
    response = client.post(
        '/auth/logout',
        headers={'Origin': TRUSTED_ORIGIN},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {'detail': 'Not authenticated'}


def test_cors_allows_configured_origin_with_credentials(client):
    response = client.options(
        '/auth/logout',
        headers={
            'Origin': TRUSTED_ORIGIN,
            'Access-Control-Request-Method': 'POST',
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers['access-control-allow-origin'] == TRUSTED_ORIGIN
    assert response.headers['access-control-allow-credentials'] == 'true'


def test_cors_does_not_allow_untrusted_origin(client):
    response = client.options(
        '/auth/logout',
        headers={
            'Origin': 'https://attacker.example',
            'Access-Control-Request-Method': 'POST',
        },
    )

    assert 'access-control-allow-origin' not in response.headers


def test_openapi_declares_access_token_as_cookie_security_scheme(client):
    schema = client.get('/openapi.json').json()

    assert schema['components']['securitySchemes']['APIKeyCookie'] == {
        'type': 'apiKey',
        'in': 'cookie',
        'name': 'access_token',
    }
    assert {
        'APIKeyCookie': [],
    } in schema['paths']['/auth/me']['get']['security']
    current_user_access = schema['components']['schemas']['CurrentUserAccess']
    assert current_user_access['required'] == [
        'profiles',
        'global_permissions',
        'scopes',
    ]
    assert current_user_access['properties']['profiles'] == {
        'items': {'$ref': '#/components/schemas/ProfileSummary'},
        'title': 'Profiles',
        'type': 'array',
    }
    assert not any(
        parameter['name'] == 'access_token'
        for parameter in schema['paths']['/auth/me']['get'].get(
            'parameters', []
        )
    )
