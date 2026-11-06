"""Jornada: a escolha do proponente vale uma vez, e o reprocessamento não
atropela uma contestação já decidida (Spec 046, US3).

Parte de um deploy novo e usa a API pública, no template 4 (Dossiê). A falha
da IA roda por `pre_evaluation_service._mark_failed`, porque o background
fica desligado nos testes.
"""

from http import HTTPStatus
from uuid import UUID

import pytest

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
    make_bracvam,
    process_tasks,
    sign_up,
)


@pytest.mark.asyncio
async def test_escolha_vale_uma_vez_e_reprocessamento_nao_atropela_contestacao(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triador')

    # 1. O administrador configura a avaliação de IA do template 4.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    log_out(client)

    # 2. O proponente envia e a pré-avaliação falha: abre-se um retorno.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK, result['body']
    pid = result['process_id']
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    await svc._mark_failed(session, run_id)
    assert (
        process_tasks(client, pid)['submission_return_review']['status']
        == 'READY'
    )

    # 3. O proponente contesta e a tarefa de retorno se conclui.
    contest = client.post(
        f'/processes/{pid}/return-review',
        json={
            'choice': 'CONTEST_AI',
            'justification': 'Pedir análise humana.',
        },
    )
    assert contest.status_code == HTTPStatus.OK, contest.text
    assert (
        process_tasks(client, pid)['submission_return_review']['status']
        == 'COMPLETED'
    )
    log_out(client)

    # 4. O administrador tenta reprocessar a execução que falhou e é recusado:
    #    o retorno já foi decidido.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    retry = client.post(f'/admin/pre-evaluations/{run_id}/retry')
    assert retry.status_code == HTTPStatus.CONFLICT, retry.text
    log_out(client)

    # 5. Uma segunda escolha do proponente também é recusada.
    log_in(client, 'proponente')
    second = client.post(
        f'/processes/{pid}/return-review', json={'choice': 'REVISE'}
    )
    assert second.status_code == HTTPStatus.CONFLICT, second.text
    pre_evaluation = client.get(f'/processes/{pid}/pre-evaluation').json()
    assert pre_evaluation['run_id'] == str(run_id)
    log_out(client)

    # 6. A triagem segue com uma única pendência para o BraCVAM.
    log_in(client, 'triador')
    ready = client.get(
        '/tasks', params={'process_id': pid, 'status': 'READY'}
    ).json()['data']
    assert [task['activity_key'] for task in ready] == ['triage_evaluation']
