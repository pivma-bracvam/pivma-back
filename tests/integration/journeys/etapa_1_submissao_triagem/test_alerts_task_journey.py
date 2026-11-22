"""Jornada: a triagem sabe que chegou uma submissão, e o proponente sabe que
ela voltou (Spec 047, US1).

Ator: duas pessoas do BraCVAM e o proponente. Objetivo: cada um ver, na
caixa de alerts, a tarefa nova que pede ação sua e chegar a ela pelo
destino do alert. Parte de um deploy novo e usa só a API pública. Sem
avaliação por IA associada, a proposta enviada vai direto para a triagem.
"""

from http import HTTPStatus

import pytest

from tests.factories.submission_factory import submission_values
from tests.integration.journeys.conftest import (
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    make_bracvam,
    sign_up,
)

FORM = '/processes/{pid}/activities/proposal_submission/form'
TASK_PARAMS = {
    'process_code',
    'process_title',
    'activity_key',
    'activity_name',
    'run_number',
    'due_date',
}


def _alerts(client, **params):
    response = client.get('/alerts', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest.mark.asyncio
async def test_triagem_ve_a_submissao_nova_e_proponente_ve_a_devolucao(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triadora')
    make_bracvam(client, 'colega')

    # 1. O proponente cria e envia a proposta. Ele mesmo fez a ação, então
    #    não tem alert.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    process = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Ensaio RhCE'},
    ).json()
    pid = process['id']
    sent = client.post(
        FORM.format(pid=pid), json={'values': submission_values()}
    )
    assert sent.status_code == HTTPStatus.OK, sent.text
    assert _alerts(client)['data'] == []
    log_out(client)

    # 2. Cada pessoa do BraCVAM vê um alert não lido da triagem, com o
    #    código do processo e destino na tarefa.
    for username in ('triadora', 'colega'):
        log_in(client, username)
        inbox = _alerts(client, unread='true')
        assert inbox['unread_count'] == 1
        [alert] = inbox['data']
        assert alert['kind'] == 'task_opened'
        assert alert['params']['activity_key'] == 'triage_evaluation'
        assert alert['params']['process_code'] == process['code']
        assert alert['target']['type'] == 'task'
        assert alert['target']['process_id'] == pid
        log_out(client)

    # 3. A triadora abre a tarefa pelo destino do alert, marca o alert como
    #    lido e pede revisão.
    log_in(client, 'triadora')
    [alert] = _alerts(client)['data']
    task = client.get(f'/tasks/{alert["target"]["id"]}')
    assert task.status_code == HTTPStatus.OK, task.text
    assert task.json()['activity_key'] == 'triage_evaluation'
    read = client.post(f'/alerts/{alert["id"]}/read')
    assert read.status_code == HTTPStatus.OK, read.text
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Faltam dados.'},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text

    # 4. Ela não ganha alert pela própria decisão.
    inbox = _alerts(client)
    assert inbox['unread_count'] == 0
    assert [a['id'] for a in inbox['data']] == [alert['id']]
    log_out(client)

    # 5. O proponente vê a devolução como tarefa nova, sem justificativa,
    #    parecer nem nome de quem triou.
    log_in(client, 'proponente')
    [returned] = _alerts(client, unread='true')['data']
    assert returned['params']['activity_key'] == 'submission_return_review'
    assert set(returned['params']) == TASK_PARAMS
    assert 'Faltam dados.' not in str(returned)
    log_out(client)

    # 6. A colega continua com o alert da triagem não lido: concluir a
    #    tarefa não muda o alert.
    log_in(client, 'colega')
    inbox = _alerts(client)
    assert inbox['unread_count'] == 1
    assert inbox['data'][0]['params']['activity_key'] == 'triage_evaluation'
