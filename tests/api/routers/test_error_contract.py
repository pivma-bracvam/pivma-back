"""Spec 034 - formato único das respostas de erro.

Cada teste provoca um erro de uma classe e confere o formato
`{"detail": {"code", "message"}}`, o código e o status.
"""

import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from pivma import app
from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.authorization import USERS_MANAGE
from pivma.core.database.models import FormField, FormTemplate
from pivma.core.invite_service import hash_invite_token
from pivma.dependencies import get_model_provider
from tests.api.routers.test_rbac_router import authenticate
from tests.conftest import _make_rbac_user
from tests.factories.invite_factory import InviteFactory
from tests.factories.task_listing_factory import listing_process
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
ENGLISH_MESSAGES = {
    'Not authenticated',
    'Not Found',
    'Method Not Allowed',
    'Forbidden',
    'Invalid origin',
    'Invalid credentials',
    'User not found',
    'Internal Server Error',
    'Field required',
}


def _assert_error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {'detail'}
    assert isinstance(body['detail'], dict)
    assert body['detail']['code'] == code
    assert isinstance(body['detail']['message'], str)
    assert body['detail']['message']
    blob = json.dumps(body)
    for leaked in ('"loc"', '"input"', '"msg"', '"type"'):
        assert leaked not in blob
    return body['detail']


async def _user(session, **kwargs):
    user = UserFactory(**kwargs)
    session.add(user)
    await session.commit()
    return user


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def test_unauthenticated_uses_not_authenticated(client):
    _assert_error(client.get('/tasks'), 401, 'not_authenticated')


async def _manager(session):
    return await _make_rbac_user(
        session, system_key=None, name='Gestor', codes=(USERS_MANAGE,)
    )


@pytest.mark.asyncio
async def test_untrusted_origin_uses_invalid_origin(client, session):
    authenticate(client, await _manager(session))

    response = client.delete(f'/users/{uuid4()}')

    _assert_error(response, 403, 'invalid_origin')


@pytest.mark.asyncio
async def test_missing_permission_uses_forbidden(client, session):
    authenticate(client, await _user(session))

    _assert_error(client.get('/users'), 403, 'forbidden')


@pytest.mark.asyncio
async def test_admin_route_uses_admin_only(client, session):
    authenticate(client, await _user(session))

    _assert_error(client.get('/admin/logs/operational'), 403, 'admin_only')


@pytest.mark.asyncio
async def test_invalid_credentials_code(client, session):
    user = await _user(session)

    response = client.post(
        '/auth/login',
        json={'identifier': user.username, 'password': 'senha-errada-123'},
        headers=ORIGIN,
    )

    _assert_error(response, 401, 'invalid_credentials')


@pytest.mark.asyncio
async def test_hidden_resource_404_matches_missing(client, session):
    owner = await _user(session)
    process = await listing_process(session, proponent=owner)

    authenticate(client, await _user(session))
    hidden = _assert_error(
        client.get(f'/processes/{process.id}'), 404, 'not_found'
    )
    missing = _assert_error(
        client.get(f'/processes/{uuid4()}'), 404, 'not_found'
    )

    assert hidden['message'] == missing['message']


def test_unknown_route_uses_not_found(client):
    _assert_error(client.get('/nao-existe'), 404, 'not_found')


@pytest.mark.asyncio
async def test_wrong_method_uses_method_not_allowed(client, session):
    authenticate(client, await _user(session))

    _assert_error(
        client.put('/tasks', headers=ORIGIN), 405, 'method_not_allowed'
    )


@pytest.mark.asyncio
async def test_business_rule_keeps_specific_code(
    client, session, bracvam_user
):
    await bootstrap_all_templates(session)
    authenticate(client, await _user(session))
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Sem envio'},
        headers=ORIGIN,
    ).json()['id']

    # A triagem ainda não está em andamento: a submissão não foi enviada.
    authenticate(client, bracvam_user)
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Ok.'},
        headers=ORIGIN,
    )

    _assert_error(response, 409, 'invalid_transition')


async def _process_with_file_field(client, session):
    await bootstrap_all_templates(session)
    authenticate(client, await _user(session))
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Anexos'},
        headers=ORIGIN,
    ).json()['id']
    template = await session.scalar(
        select(FormTemplate).where(
            FormTemplate.key == 'submission_pre_validated_v1'
        )
    )
    session.add(
        FormField(
            form_template_id=template.id,
            field_key='pop_document',
            label='POP',
            field_type='file_upload',
            is_required=False,
            order_index=20,
            validation_rules={'max_size_mb': 1},
        )
    )
    await session.commit()
    return pid


def _upload(client, pid, data):
    return client.post(
        f'/processes/{pid}/activities/proposal_submission/form'
        '/fields/pop_document/attachment',
        files={'file': ('pop.pdf', data, 'application/pdf')},
        headers=ORIGIN,
    )


@pytest.mark.asyncio
async def test_attachment_errors_keep_status_and_code(client, session):
    pid = await _process_with_file_field(client, session)

    _assert_error(_upload(client, pid, b''), 400, 'empty_file')
    _assert_error(
        _upload(client, pid, b'x' * (1024 * 1024 + 8)), 413, 'file_too_large'
    )


def test_unhandled_exception_uses_internal_error():
    @app.get('/__teste_erro_interno__', include_in_schema=False)
    async def _boom():
        raise RuntimeError('segredo interno')

    try:
        with TestClient(app, raise_server_exceptions=False) as raw_client:
            response = raw_client.get('/__teste_erro_interno__')
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, 'path', None) != '/__teste_erro_interno__'
        ]

    _assert_error(response, 500, 'internal_error')
    assert 'segredo interno' not in response.text


class _BrokenProvider:
    def __getattr__(self, name):
        raise RuntimeError('provedor fora do ar')


@pytest.mark.asyncio
async def test_ai_unavailable_code(client, ai_eval_admin):
    app.dependency_overrides[get_model_provider] = _BrokenProvider
    try:
        authenticate(client, ai_eval_admin)
        response = client.post(
            '/ai-evaluations/suggest-criteria',
            json={'objective': 'Avaliar o método.', 'target_type': 'field'},
            headers=ORIGIN,
        )
    finally:
        app.dependency_overrides.pop(get_model_provider, None)

    _assert_error(response, 503, 'ai_unavailable')


@pytest.mark.asyncio
async def test_self_deactivation_code(client, session):
    manager = await _manager(session)
    authenticate(client, manager)

    response = client.delete(f'/users/{manager.id}', headers=ORIGIN)

    _assert_error(response, 409, 'self_deactivation')


async def _invite(session, *, email, expires_at=None):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    token = f'token-{uuid4()}'
    invite = InviteFactory(
        process=process,
        role_key='sponsor',
        email=email,
        token_hash=hash_invite_token(token),
    )
    if expires_at is not None:
        invite.expires_at = expires_at
    invite.set_creation_audit(proponent.id)
    session.add(invite)
    await session.commit()
    return token


@pytest.mark.asyncio
async def test_invite_codes(client, session):
    token = await _invite(session, email='alvo@exemplo.org')
    authenticate(client, await _user(session, email='outro@exemplo.org'))
    _assert_error(
        client.post(f'/invites/{token}/accept', headers=ORIGIN),
        403,
        'invite_email_mismatch',
    )

    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
    expired = await _invite(
        session, email='expira@exemplo.org', expires_at=past
    )
    authenticate(client, await _user(session, email='expira@exemplo.org'))
    _assert_error(
        client.post(f'/invites/{expired}/accept', headers=ORIGIN),
        409,
        'invite_expired',
    )


@pytest.mark.asyncio
async def test_error_messages_are_portuguese(client, session):
    responses = [
        client.get('/tasks'),
        client.get('/nao-existe'),
    ]
    authenticate(client, await _manager(session))
    responses += [
        client.delete(f'/users/{uuid4()}'),
        client.get('/users'),
        client.get(f'/processes/{uuid4()}'),
        client.put('/tasks', headers=ORIGIN),
    ]

    for response in responses:
        assert response.json()['detail']['message'] not in ENGLISH_MESSAGES


@pytest.mark.asyncio
async def test_status_codes_unchanged(client, session):
    assert client.get('/tasks').status_code == HTTPStatus.UNAUTHORIZED
    assert client.get('/nao-existe').status_code == HTTPStatus.NOT_FOUND
    authenticate(client, await _manager(session))
    assert (
        client.delete(f'/users/{uuid4()}').status_code == HTTPStatus.FORBIDDEN
    )
    assert client.get('/users').status_code == HTTPStatus.FORBIDDEN
    assert (
        client.get(f'/processes/{uuid4()}').status_code == HTTPStatus.NOT_FOUND
    )
    assert (
        client.put('/tasks', headers=ORIGIN).status_code
        == HTTPStatus.METHOD_NOT_ALLOWED
    )


# --- US2: validação por campo ----------------------------------------------


def _signup(client, **overrides):
    payload = {
        'username': 'novo-usuario',
        'email': 'nao-e-email',
        'password': 'senha-segura-123',
        **overrides,
    }
    return client.post('/users', json=payload)


def _fields_by_name(detail):
    return {item['field']: item for item in detail['fields']}


def test_validation_lists_each_field(client):
    detail = _assert_error(_signup(client), 422, 'validation_error')

    fields = _fields_by_name(detail)
    assert fields['email']['location'] == 'body'
    assert fields['full_name'] == {
        'location': 'body',
        'field': 'full_name',
        'code': 'missing',
        'message': 'Campo obrigatório.',
    }


def test_validation_never_echoes_input(client):
    response = _signup(client)

    assert 'nao-e-email' not in response.text


@pytest.mark.asyncio
async def test_query_validation_points_to_parameter(client, session):
    authenticate(client, await _user(session))

    detail = _assert_error(
        client.get('/tasks', params={'per_page': 101}),
        422,
        'validation_error',
    )

    assert detail['fields'] == [
        {
            'location': 'query',
            'field': 'per_page',
            'code': 'less_than_equal',
            'message': 'Deve ser menor ou igual a 100.',
        }
    ]


def test_password_validation_hides_rule(client):
    response = _signup(
        client, email='valido@exemplo.org', full_name='Nome', password='abc'
    )

    detail = _assert_error(response, 422, 'validation_error')
    assert _fields_by_name(detail)['password'] == {
        'location': 'body',
        'field': 'password',
        'code': 'invalid',
        'message': 'Senha inválida.',
    }
    assert '"abc"' not in response.text
    assert '8' not in json.dumps(detail['fields'])


@pytest.mark.asyncio
async def test_form_values_errors_use_fields(client, session):
    await bootstrap_all_templates(session)
    authenticate(client, await _user(session))
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Formulário'},
        headers=ORIGIN,
    ).json()['id']

    # O rascunho recusa campos que o formulário não tem.
    response = client.put(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Método', 'campo_inexistente': 'x'}},
    )

    detail = _assert_error(response, 422, 'invalid_form_values')
    assert 'errors' not in detail
    [item] = detail['fields']
    assert item['location'] == 'body'
    assert item['field'] == 'values.campo_inexistente'
    assert item['code']
    assert item['message']


@pytest.mark.asyncio
async def test_domain_field_error_keeps_format(client, session):
    from tests.factories.sample_factory import (  # noqa: PLC0415
        sample_process,
        substance_payload,
    )

    ctx = await sample_process(session, lab_count=1)
    authenticate(client, ctx.selector)

    response = client.post(
        f'/processes/{ctx.process_id}/samples',
        json=substance_payload(cas_number='50-00-1'),
        headers=ORIGIN,
    )

    _assert_error(response, 422, 'invalid_cas')


def test_validation_messages_are_portuguese(client):
    detail = _signup(client).json()['detail']

    for item in detail['fields']:
        assert item['message'] not in ENGLISH_MESSAGES
        assert not item['message'].startswith('Value error')
