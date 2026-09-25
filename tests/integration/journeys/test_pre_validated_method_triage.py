"""Jornada: um usuário novo leva o processo 1 (Método Pré-Validado) até a
triagem aprovada pelo BraCVAM.

Diferente dos testes de roteador, a jornada parte do estado de um deploy
novo (bootstrap real de perfis, permissões, templates e administrador
inicial) e só usa a API pública: cadastro, login por cookie, troca de
usuário por logout/login e concessão do perfil BraCVAM pelo administrador.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.bootstrap_system import (
    BRACVAM_PROFILE_ID,
    sync_canonical_permissions,
    sync_canonical_profiles,
    sync_initial_administrator,
    sync_profile_permissions,
)
from pivma.core.authorization import ADMINISTRATOR_SYSTEM_KEY
from pivma.core.database.models import AuditEvent

ADMIN_EMAIL = 'admin@example.com'
ADMIN_PASSWORD = 'admin-password-123'
PASSWORD = 'senha-segura-123'


async def _bootstrap_fresh_deploy(session, monkeypatch):
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


def _sign_up(client, username):
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


def _log_in(client, identifier, password=PASSWORD):
    client.cookies.clear()
    response = client.post(
        '/auth/login',
        json={'identifier': identifier, 'password': password},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert 'access_token' in client.cookies


def _log_out(client):
    response = client.post('/auth/logout')
    assert response.status_code == HTTPStatus.NO_CONTENT
    client.cookies.clear()


def _process_tasks(client, process_id):
    response = client.get('/tasks', params={'process_id': process_id})
    print(response)
    assert response.status_code == HTTPStatus.OK, response.text
    return {task['assigned_role']: task for task in response.json()}


@pytest.mark.asyncio
async def test_new_user_reaches_approved_triage_on_pre_validated_method(
    client, session, monkeypatch
):
    await _bootstrap_fresh_deploy(session, monkeypatch)
    # Endpoints mutáveis exigem Origin confiável, como faria o navegador.
    client.headers['Origin'] = 'https://testserver'

    # 1. Usuário novo se cadastra e entra sem nenhum perfil global.
    _sign_up(client, 'proponente')
    _log_in(client, 'proponente')
    me = client.get('/auth/me').json()
    assert me['access']['profiles'] == []
    assert 'triage.review' not in me['access']['global_permissions']

    # 2. Cria o processo a partir do template 1.
    response = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Método in vitro de irritação ocular',
        },
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    process_id = response.json()['id']
    submission_task = _process_tasks(client, process_id)['proponent']
    assert submission_task['status'] == 'READY'

    # 3. Envia a submissão; sem IA configurada, segue direto para a triagem.
    response = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Ensaio RhCE para irritação'}},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['status'] == 'COMPLETED'
    assert client.get(f'/processes/{process_id}').json()['status'] == (
        'TRIAGE'
    )

    # O proponente não pode decidir a própria triagem.
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Auto-aprovação.'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    _log_out(client)

    # 4. O administrador concede o perfil BraCVAM a outro usuário novo.
    triador = _sign_up(client, 'triador')
    _log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.post(
        f'/rbac/users/{triador["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    _log_out(client)

    _log_in(client, 'triador')
    me = client.get('/auth/me').json()
    assert 'triage.review' in me['access']['global_permissions']
    triage_task = _process_tasks(client, process_id)['bracvam']
    assert triage_task['status'] == 'READY'

    # 5. O BraCVAM aprova a triagem.
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={
            'outcome': 'APPROVED',
            'justification': 'Proposta aderente ao escopo.',
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['outcome'] == 'APPROVED'
    assert response.json()['new_process_status'] == 'PLANNING'

    # 6. Estado final observável pela API e trilha de auditoria.
    assert client.get(f'/processes/{process_id}').json()['status'] == (
        'PLANNING'
    )
    tasks = _process_tasks(client, process_id)
    assert tasks['proponent']['status'] == 'COMPLETED'
    assert tasks['bracvam']['status'] == 'COMPLETED'

    events = list(
        await session.scalars(
            select(AuditEvent.event_type).where(
                AuditEvent.process_instance_id == process_id
            )
        )
    )
    assert 'SUBMISSION_SUBMITTED' in events
    assert 'TRIAGE_APPROVED' in events
