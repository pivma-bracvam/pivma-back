"""Jornada: a pré-avaliação por IA reprova a submissão, o proponente contesta
e o BraCVAM aprova na triagem (Spec 030, US4).

Parte de um deploy novo e usa a API pública, como a jornada do processo 1.
O processo é do template 4 (Dossiê), cujo formulário tem o campo avaliado
pela IA. A pré-avaliação usa o provedor fake e roda de forma síncrona por
`pre_evaluation_service._execute`, porque o background fica desligado nos
testes (`tests/conftest.py`).

A jornada acompanha a lista de tarefas (`GET /tasks`) como o frontend faz:
cada perfil só age quando aparece uma pendência `READY` para ele. `/tasks`
também lista tarefas concluídas, então as pendências são conferidas pelo
status, não pela presença na lista.
"""

from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from pivma.core import pre_evaluation_service as svc
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    process_tasks,
    sign_up,
)


def _pending(client, pid):
    """Chaves das atividades com tarefa `READY` visível ao usuário logado."""
    response = client.get(
        '/tasks', params={'process_id': pid, 'status': 'READY'}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return {task['activity_key'] for task in response.json()['data']}


@pytest.mark.asyncio
async def test_ai_rejection_contested_then_approved(
    journey_client, session, monkeypatch, fake_provider
):
    del fake_provider
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    triador = sign_up(client, 'triador')

    # 1. O administrador configura uma avaliação de IA com critério crítico que
    #    a submissão não cumpre e concede o perfil BraCVAM ao triador.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    granted = client.post(
        f'/rbac/users/{triador["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)

    # 2. Um proponente novo cria o processo e envia a submissão. A resposta
    #    não traz o resultado: a pré-avaliação fica em andamento e ainda não
    #    há retorno para revisar.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK, result['body']
    assert result['body']['pre_evaluation']['status'] == 'in_progress'
    pid = result['process_id']
    assert (
        client.get(f'/processes/{pid}/return-review').status_code
        == HTTPStatus.NOT_FOUND
    )

    # 3. Enquanto a IA avalia, o proponente acompanha a pré-avaliação em
    #    andamento e não tem nenhuma ação liberada: a submissão já está
    #    concluída e não há tarefa pendente.
    pre_evaluation = client.get(f'/processes/{pid}/pre-evaluation')
    assert pre_evaluation.json()['status'] == 'in_progress'
    tasks = process_tasks(client, pid)
    assert tasks['proposal_submission']['status'] == 'COMPLETED'
    assert _pending(client, pid) == set()

    # 4. A IA termina com resultado negativo e abre a revisão do retorno:
    #    surge a tarefa pendente do proponente.
    await svc._execute(
        session, UUID(result['body']['pre_evaluation']['run_id'])
    )
    review_task = process_tasks(client, pid)['submission_return_review']
    assert review_task['status'] == 'READY'
    assert review_task['assigned_role'] == 'proponent'
    assert _pending(client, pid) == {'submission_return_review'}

    # 5. O proponente abre o retorno, vê o resultado da IA e contesta. A
    #    tarefa passa a concluída e ele fica sem pendências.
    review = client.get(f'/processes/{pid}/return-review').json()
    assert review['source'] == 'AI_PRE_EVALUATION'
    assert review['ai_pre_evaluation']['consolidated_result'] == 'negative'
    contest = client.post(
        f'/processes/{pid}/return-review',
        json={'choice': 'CONTEST_AI', 'justification': 'A IA errou.'},
    )
    assert contest.status_code == HTTPStatus.OK, contest.text
    tasks = process_tasks(client, pid)
    assert tasks['submission_return_review']['status'] == 'COMPLETED'
    assert _pending(client, pid) == set()
    log_out(client)

    # 6. A contestação encaminha o processo à triagem humana: a pendência
    #    aparece na fila do BraCVAM, que aprova.
    log_in(client, 'triador')
    triage_task = process_tasks(client, pid)['triage_evaluation']
    assert triage_task['status'] == 'READY'
    assert triage_task['assigned_role'] == 'bracvam'
    assert _pending(client, pid) == {'triage_evaluation'}
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    assert decision.json()['process_status'] == 'OPEN'
