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

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from pivma.core.database.models import AuditEvent
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    process_tasks,
    sign_up,
)


@pytest.mark.asyncio
async def test_new_user_reaches_approved_triage_on_pre_validated_method(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. Usuário novo se cadastra e entra sem nenhum perfil global.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
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
    submission_task = process_tasks(client, process_id)['proponent']
    assert submission_task['status'] == 'READY'

    # 3. Envia a submissão; sem IA configurada, segue direto para a triagem.
    response = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Ensaio RhCE para irritação'}},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['status'] == 'COMPLETED'
    assert client.get(f'/processes/{process_id}').json()['status'] == 'OPEN'

    # O proponente não pode decidir a própria triagem.
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Auto-aprovação.'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    log_out(client)

    # 4. O administrador concede o perfil BraCVAM a outro usuário novo.
    triador = sign_up(client, 'triador')
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.post(
        f'/rbac/users/{triador["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    log_out(client)

    log_in(client, 'triador')
    me = client.get('/auth/me').json()
    assert 'triage.review' in me['access']['global_permissions']
    triage_task = process_tasks(client, process_id)['bracvam']
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
    assert response.json()['process_status'] == 'OPEN'

    # 6. Estado final observável pela API e trilha de auditoria.
    assert client.get(f'/processes/{process_id}').json()['status'] == 'OPEN'
    tasks = process_tasks(client, process_id)
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
