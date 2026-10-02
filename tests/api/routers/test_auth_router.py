from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from pivma.core.database.models import (
    AccessProfile,
    Assignment,
    UserAccessProfile,
)
from pivma.core.security import create_access_token, verify_password
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)

VALID_PASSWORD = 'Factory-Passphrase-2026'
JWT_SECRET_KEY = 'test-jwt-secret-key-with-at-least-32-bytes'
TRUSTED_ORIGIN = 'https://testserver'
NEW_PASSWORD = 'NovaSenha-2026'


def login(client, identifier, password=VALID_PASSWORD):
    return client.post(
        '/auth/login',
        json={'identifier': identifier, 'password': password},
    )


def update_me(client, payload, origin=TRUSTED_ORIGIN):
    headers = {} if origin is None else {'Origin': origin}
    return client.patch('/auth/me', json=payload, headers=headers)


def account_state(user):
    return (
        user.full_name,
        user.password_hash,
        user.updated_at,
        user.updated_by,
    )


def test_login_with_username_and_recognize_identity(client, user):
    response = login(client, user.username.swapcase())

    assert response.status_code == HTTPStatus.OK
    assert response.content == b''
    assert 'access_token' in client.cookies

    identity = client.get('/auth/me')

    assert identity.status_code == HTTPStatus.OK
    assert identity.json() == {
        'user': {
            'id': str(user.id),
            'full_name': user.full_name,
            'username': user.username,
            'email': user.email,
        },
        'access': {
            'profiles': [],
            'global_permissions': [],
            'scopes': [],
        },
    }


@pytest.mark.asyncio
async def test_me_returns_full_name(client, user, session):
    user.full_name = 'Maria Silva'
    await session.commit()

    assert login(client, user.username).status_code == HTTPStatus.OK
    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['user']['full_name'] == 'Maria Silva'
    assert 'full_name' not in response.json()


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
    assert response.json() == {
        'detail': {
            'code': 'invalid_credentials',
            'message': 'Usuário ou senha inválidos.',
        }
    }
    assert 'Incorrect-Passphrase-2026' not in response.text
    assert 'access_token' not in client.cookies


def test_login_rejects_unknown_identifier_with_same_response(client):
    response = login(client, 'missing@example.com')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'invalid_credentials',
            'message': 'Usuário ou senha inválidos.',
        }
    }
    assert 'access_token' not in client.cookies


def test_login_rejects_deleted_user_with_same_response(client, deleted_user):
    response = login(client, deleted_user.username)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'invalid_credentials',
            'message': 'Usuário ou senha inválidos.',
        }
    }
    assert 'access_token' not in client.cookies


def test_me_rejects_missing_cookie(client):
    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'not_authenticated',
            'message': 'Sessão ausente ou expirada.',
        }
    }


def test_me_rejects_tampered_token(client, user):
    token = create_access_token(user.id, JWT_SECRET_KEY)
    header, payload, signature = token.split('.')
    replacement = 'a' if signature[0] != 'a' else 'b'
    tampered_token = f'{header}.{payload}.{replacement}{signature[1:]}'
    client.cookies.set('access_token', tampered_token)

    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'not_authenticated',
            'message': 'Sessão ausente ou expirada.',
        }
    }


def test_me_rejects_expired_token(client, user):
    token = create_access_token(
        user.id,
        JWT_SECRET_KEY,
        now=datetime.now(UTC) - timedelta(hours=8, seconds=1),
    )
    client.cookies.set('access_token', token)

    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'not_authenticated',
            'message': 'Sessão ausente ou expirada.',
        }
    }


def test_me_rejects_user_deleted_after_login(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK
    user.deleted_at = datetime.now(UTC)
    session.add(user)

    response = client.get('/auth/me')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'not_authenticated',
            'message': 'Sessão ausente ou expirada.',
        }
    }


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
    assert response.json() == {
        'detail': {
            'code': 'invalid_origin',
            'message': 'Origem da requisição não confiável.',
        }
    }
    assert 'access_token' in client.cookies


def test_logout_rejects_untrusted_origin_without_removing_cookie(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = client.post(
        '/auth/logout',
        headers={'Origin': 'https://attacker.example'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {
        'detail': {
            'code': 'invalid_origin',
            'message': 'Origem da requisição não confiável.',
        }
    }
    assert 'access_token' in client.cookies


def test_logout_requires_authentication(client):
    response = client.post(
        '/auth/logout',
        headers={'Origin': TRUSTED_ORIGIN},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        'detail': {
            'code': 'not_authenticated',
            'message': 'Sessão ausente ou expirada.',
        }
    }


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
    user_identity = schema['components']['schemas']['UserIdentity']
    assert user_identity['required'] == [
        'id',
        'username',
        'email',
        'full_name',
    ]
    assert user_identity['properties']['full_name'] == {
        'anyOf': [{'type': 'string'}, {'type': 'null'}],
        'title': 'Full Name',
    }
    assert current_user_access['required'] == [
        'profiles',
        'global_permissions',
        'scopes',
    ]
    assert current_user_access['properties']['profiles'] == {
        'items': {'$ref': '#/components/schemas/ProfileRef'},
        'title': 'Profiles',
        'type': 'array',
    }
    assert not any(
        parameter['name'] == 'access_token'
        for parameter in schema['paths']['/auth/me']['get'].get(
            'parameters', []
        )
    )


def test_update_me_returns_public_projection_with_trimmed_name(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = update_me(client, {'full_name': '  Maria Silva  '})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'full_name': 'Maria Silva',
    }


@pytest.mark.asyncio
async def test_update_me_persists_full_name(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK

    update_me(client, {'full_name': 'Maria Silva'})
    await session.refresh(user)

    assert user.full_name == 'Maria Silva'


def test_update_me_full_name_is_visible_in_current_session(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    update_me(client, {'full_name': 'Maria Silva'})
    identity = client.get('/auth/me')

    assert identity.json()['user']['full_name'] == 'Maria Silva'


@pytest.mark.asyncio
async def test_update_me_full_name_records_audit(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK

    update_me(client, {'full_name': 'Maria Silva'})
    await session.refresh(user)

    assert user.updated_at is not None
    assert user.updated_by == user.id


def test_update_me_response_has_no_secret(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = update_me(client, {'full_name': 'Maria Silva'})

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()).isdisjoint({
        'password',
        'password_hash',
        'current_password',
        'new_password',
        'access_token',
    })


def change_password(client, current_password=VALID_PASSWORD, **extra):
    return update_me(
        client,
        {
            'current_password': current_password,
            'new_password': NEW_PASSWORD,
            **extra,
        },
    )


@pytest.mark.asyncio
async def test_update_me_changes_password_hash(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = change_password(client)
    await session.refresh(user)

    assert response.status_code == HTTPStatus.OK
    assert verify_password(user.password_hash, NEW_PASSWORD)


def test_update_me_new_password_allows_login(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK
    assert change_password(client).status_code == HTTPStatus.OK

    response = login(client, user.username, NEW_PASSWORD)

    assert response.status_code == HTTPStatus.OK


def test_update_me_old_password_no_longer_allows_login(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK
    assert change_password(client).status_code == HTTPStatus.OK

    response = login(client, user.username)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail']['code'] == 'invalid_credentials'


def test_update_me_accepts_new_password_equal_to_current(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK
    payload = {
        'current_password': VALID_PASSWORD,
        'new_password': VALID_PASSWORD,
    }
    assert update_me(client, payload).status_code == HTTPStatus.OK

    response = login(client, user.username)

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_update_me_password_records_audit(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK

    change_password(client)
    await session.refresh(user)

    assert user.updated_at is not None
    assert user.updated_by == user.id


def test_update_me_rejects_wrong_current_password(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = change_password(client, current_password='Senha-Errada-2026')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {
        'detail': {
            'code': 'invalid_current_password',
            'message': 'Senha atual incorreta.',
        }
    }


@pytest.mark.asyncio
async def test_update_me_wrong_current_password_keeps_account(
    client, user, session
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    before = account_state(user)

    response = change_password(client, current_password='Senha-Errada-2026')
    await session.refresh(user)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert account_state(user) == before


@pytest.mark.asyncio
async def test_update_me_wrong_current_password_keeps_full_name(
    client, user, session
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    full_name = user.full_name

    response = change_password(
        client, current_password='Senha-Errada-2026', full_name='Maria Silva'
    )
    await session.refresh(user)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert user.full_name == full_name


def test_update_me_short_wrong_current_password_returns_400(client, user):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = change_password(client, current_password='x')

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()['detail']['code'] == 'invalid_current_password'


@pytest.mark.asyncio
async def test_update_me_new_password_requires_current_password(
    client, user, session
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    password_hash = user.password_hash

    response = update_me(client, {'new_password': NEW_PASSWORD})
    await session.refresh(user)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'
    assert [
        item['message'] for item in response.json()['detail']['fields']
    ] == ['Informe a senha atual para trocar a senha.']
    assert user.password_hash == password_hash


@pytest.mark.asyncio
async def test_update_me_hides_new_password_rule(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK
    password_hash = user.password_hash

    response = update_me(
        client,
        {'current_password': VALID_PASSWORD, 'new_password': 'Curta-7'},
    )
    await session.refresh(user)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['fields'] == [
        {
            'location': 'body',
            'field': 'new_password',
            'code': 'invalid',
            'message': 'Senha inválida.',
        }
    ]
    assert user.password_hash == password_hash


@pytest.mark.asyncio
async def test_update_me_changes_name_and_password_together(
    client, user, session
):
    assert login(client, user.username).status_code == HTTPStatus.OK

    response = change_password(client, full_name='Maria Silva')
    await session.refresh(user)

    assert response.status_code == HTTPStatus.OK
    assert user.full_name == 'Maria Silva'
    assert verify_password(user.password_hash, NEW_PASSWORD)


@pytest.mark.asyncio
async def test_update_me_requires_session(client, user, session):
    before = account_state(user)

    response = update_me(client, {'full_name': 'Maria Silva'})
    await session.refresh(user)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail']['code'] == 'not_authenticated'
    assert account_state(user) == before


def test_update_me_rejects_user_deleted_after_login(client, user, session):
    assert login(client, user.username).status_code == HTTPStatus.OK
    user.deleted_at = datetime.now(UTC)
    session.add(user)

    response = update_me(client, {'full_name': 'Maria Silva'})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail']['code'] == 'not_authenticated'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'origin', [None, 'https://attacker.example'], ids=['missing', 'untrusted']
)
async def test_update_me_rejects_untrusted_origin(
    client, user, session, origin
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    before = account_state(user)

    response = update_me(client, {'full_name': 'Maria Silva'}, origin=origin)
    await session.refresh(user)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'invalid_origin'
    assert account_state(user) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('username', 'novo.usuario'),
        ('email', 'novo.usuario@example.com'),
        ('password_hash', 'hash-forjado'),
    ],
)
async def test_update_me_rejects_account_field(
    client, user, session, field, value
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    before = (getattr(user, field), *account_state(user))

    response = update_me(client, {'full_name': 'Maria Silva', field: value})
    await session.refresh(user)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [
        (item['field'], item['code'])
        for item in response.json()['detail']['fields']
    ] == [(field, 'extra_forbidden')]
    assert (getattr(user, field), *account_state(user)) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['id', 'user_id'])
async def test_update_me_rejects_other_account_id(
    client, user, other_user, session, field
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    before = (account_state(user), account_state(other_user))

    response = update_me(
        client, {'full_name': 'Maria Silva', field: str(other_user.id)}
    )
    await session.refresh(user)
    await session.refresh(other_user)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert [
        (item['field'], item['code'])
        for item in response.json()['detail']['fields']
    ] == [(field, 'extra_forbidden')]
    assert (account_state(user), account_state(other_user)) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('payload', 'fields'),
    [
        ({}, ['']),
        ({'full_name': None}, ['full_name']),
        ({'full_name': '   '}, ['full_name']),
        ({'current_password': VALID_PASSWORD}, ['']),
        (
            {'current_password': None, 'new_password': NEW_PASSWORD},
            ['current_password'],
        ),
        (
            {'current_password': VALID_PASSWORD, 'new_password': None},
            ['new_password'],
        ),
    ],
    ids=[
        'empty',
        'null_full_name',
        'blank_full_name',
        'current_password_only',
        'null_current_password',
        'null_new_password',
    ],
)
async def test_update_me_rejects_invalid_body(
    client, user, session, payload, fields
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    before = account_state(user)

    response = update_me(client, payload)
    await session.refresh(user)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'
    assert [
        item['field'] for item in response.json()['detail']['fields']
    ] == fields
    assert account_state(user) == before


@pytest.mark.asyncio
async def test_update_me_keeps_other_account(
    client, user, other_user, session
):
    assert login(client, user.username).status_code == HTTPStatus.OK
    before = account_state(other_user)

    response = change_password(client, full_name='Maria Silva')
    await session.refresh(other_user)

    assert response.status_code == HTTPStatus.OK
    assert account_state(other_user) == before


def test_openapi_declares_update_current_user(client):
    operation = client.get('/openapi.json').json()['paths']['/auth/me'][
        'patch'
    ]

    assert operation['operationId'] == 'updateCurrentUser'
    assert {'200', '400', '401', '403', '422'} <= set(operation['responses'])
