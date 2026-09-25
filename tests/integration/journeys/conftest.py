"""Helpers das jornadas: deploy novo e uso da API pública como o frontend."""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.bootstrap_system import (
    sync_canonical_permissions,
    sync_canonical_profiles,
    sync_initial_administrator,
    sync_profile_permissions,
)
from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY

ADMIN_EMAIL = 'admin@example.com'
ADMIN_PASSWORD = 'admin-password-123'
PASSWORD = 'senha-segura-123'


async def bootstrap_fresh_deploy(session, monkeypatch):
    """Reproduz `run_system_bootstrap` na sessão transacional do teste."""
    monkeypatch.setenv('INITIAL_ADMIN_EMAIL', ADMIN_EMAIL)
    monkeypatch.setenv('INITIAL_ADMIN_PASSWORD', ADMIN_PASSWORD)
    profiles = await sync_canonical_profiles(session)
    permissions = await sync_canonical_permissions(session)
    await sync_profile_permissions(session, profiles, permissions)
    await session.commit()
    await bootstrap_all_templates(session)
    await sync_initial_administrator(
        session, profiles[ADMINISTRATOR_SYSTEM_KEY]
    )
    await session.commit()


def sign_up(client, username):
    response = client.post(
        '/users',
        json={
            'username': username,
            'email': f'{username}@example.com',
            'full_name': f'Usuário {username}',
            'password': PASSWORD,
        },
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def log_in(client, identifier, password=PASSWORD):
    client.cookies.clear()
    response = client.post(
        '/auth/login',
        json={'identifier': identifier, 'password': password},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert 'access_token' in client.cookies


def log_out(client):
    response = client.post('/auth/logout')
    assert response.status_code == HTTPStatus.NO_CONTENT
    client.cookies.clear()


def process_tasks(client, process_id):
    response = client.get('/tasks', params={'process_id': process_id})
    assert response.status_code == HTTPStatus.OK, response.text
    return {task['assigned_role']: task for task in response.json()}


@pytest.fixture
def journey_client(client):
    # Endpoints mutáveis exigem Origin confiável, como faria o navegador.
    client.headers['Origin'] = 'https://testserver'
    return client
