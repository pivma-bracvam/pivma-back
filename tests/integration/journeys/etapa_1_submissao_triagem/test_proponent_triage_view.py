"""Jornadas: o proponente acompanha a triagem nos três desfechos (Spec 049,
US1; issue #81).

O proponente vê a tarefa da triagem, com prazo e rodada, e a decisão com a
justificativa, mas não pode agir nela e não sabe quem avaliou.
"""

from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from pivma.core import pre_evaluation_service as svc
from tests.ai_eval_helpers import (
    COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.factories.submission_factory import submission_values
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    make_bracvam,
    process_tasks,
    sign_up,
)


def _timeline(client, process_id):
    response = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response


@pytest.mark.asyncio
async def test_proponente_acompanha_triagem_aprovada_sem_ver_o_triador(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triador')

    # 1. O proponente cria o processo e envia a submissão.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Método'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    process_id = response.json()['id']
    response = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': submission_values('Ensaio RhCE')},
    )
    assert response.status_code == HTTPStatus.OK, response.text

    # 2. Ele vê a triagem com a BraCVAM, mas ela não é uma pendência dele.
    triage = process_tasks(client, process_id)['triage_evaluation']
    assert triage['status'] == 'READY'
    assert triage['can_act'] is False
    assert triage['due_date'] is not None
    assert triage['activity_run_number'] == 1
    pending = client.get(
        '/tasks', params={'process_id': process_id, 'actionable': True}
    ).json()['data']
    assert 'triage_evaluation' not in {t['activity_key'] for t in pending}
    log_out(client)

    # 3. O triador registra um parecer por campo e aprova.
    log_in(client, 'triador')
    triador_id = client.get('/auth/me').json()['user']['id']
    response = client.post(
        f'/processes/{process_id}/triage/reviews',
        json={
            'reviews': [
                {
                    'field_key': 'method_title',
                    'status': 'NAO_CONFORME',
                    'comments': 'Rever o título.',
                }
            ]
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Proposta completa.'},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    log_out(client)

    # 4. O proponente vê a triagem concluída e a decisão, sem o autor.
    log_in(client, 'proponente')
    triage = process_tasks(client, process_id)['triage_evaluation']
    assert triage['status'] == 'COMPLETED'
    response = _timeline(client, process_id)
    events = response.json()['data']
    [approved] = [e for e in events if e['event_type'] == 'TRIAGE_APPROVED']
    assert approved['context_data']['justification'] == 'Proposta completa.'
    assert approved['user_id'] is None
    assert 'FIELD_REVIEWED' not in {e['event_type'] for e in events}
    assert triador_id not in response.text


def _decision_seen_by_proponent(client, process_id, event_type):
    response = _timeline(client, process_id)
    [event] = [
        e for e in response.json()['data'] if e['event_type'] == event_type
    ]
    return response, event


@pytest.mark.asyncio
async def test_proponente_ve_reprovacao_apos_pre_avaliacao_positiva(
    journey_client, session, monkeypatch, fake_provider
):
    del fake_provider
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    triador = sign_up(client, 'triador')

    # 1. O administrador publica uma avaliação de IA que a submissão cumpre
    #    e dá o perfil BraCVAM ao triador.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=COMPLIANT_STATEMENT
    )
    granted = client.post(
        f'/rbac/users/{triador["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)

    # 2. O proponente envia, e a IA aprova a pré-avaliação.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK, result['body']
    process_id = result['process_id']
    await svc._execute(
        session, UUID(result['body']['pre_evaluation']['run_id'])
    )

    # 3. Ele vê a triagem aberta, com prazo e rodada, sem poder agir.
    triage = process_tasks(client, process_id)['triage_evaluation']
    assert triage['status'] == 'READY'
    assert triage['can_act'] is False
    assert triage['due_date'] is not None
    assert triage['activity_run_number'] == 1
    log_out(client)

    # 4. O triador reprova.
    log_in(client, 'triador')
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={'outcome': 'REJECTED', 'justification': 'Fora do escopo.'},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    log_out(client)

    # 5. O proponente vê a triagem concluída e a reprovação, sem o autor.
    log_in(client, 'proponente')
    assert (
        process_tasks(client, process_id)['triage_evaluation']['status']
        == 'COMPLETED'
    )
    response, rejected = _decision_seen_by_proponent(
        client, process_id, 'TRIAGE_REJECTED'
    )
    assert rejected['context_data']['justification'] == 'Fora do escopo.'
    assert rejected['user_id'] is None
    assert triador['id'] not in response.text


@pytest.mark.asyncio
async def test_proponente_ve_pedido_de_revisao_sem_o_triador(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triador')

    # 1. O proponente cria o processo e envia a submissão.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Método'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    process_id = response.json()['id']
    response = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': submission_values('Ensaio RhCE')},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    log_out(client)

    # 2. O triador pede revisão.
    log_in(client, 'triador')
    triador_id = client.get('/auth/me').json()['user']['id']
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Faltam controles.',
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    log_out(client)

    # 3. O proponente vê a triagem concluída, o pedido com a justificativa
    #    e a revisão do retorno aberta para ele, sem saber quem avaliou.
    log_in(client, 'proponente')
    tasks = process_tasks(client, process_id)
    assert tasks['triage_evaluation']['status'] == 'COMPLETED'
    assert tasks['submission_return_review']['status'] == 'READY'
    response, requested = _decision_seen_by_proponent(
        client, process_id, 'REVISION_REQUESTED'
    )
    assert requested['context_data']['justification'] == 'Faltam controles.'
    assert requested['user_id'] is None
    assert triador_id not in response.text
