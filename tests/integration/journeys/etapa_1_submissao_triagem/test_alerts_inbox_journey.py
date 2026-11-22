# ruff: noqa: PLR2004
"""Jornada: a pessoa do BraCVAM lê e limpa a caixa de alerts (Spec 047, US2).

Ator: duas pessoas do BraCVAM, A e B. Objetivo: ver quantos alerts faltam
ler, filtrar os não lidos, marcar um e depois todos, sem mexer na caixa da
outra. Parte de um deploy novo e usa só a API pública. Conta só os alerts
de triagem, que não mudam quando outros tipos entrarem.
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


def _alerts(client, **params):
    response = client.get('/alerts', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _send_proposal(client, title):
    process = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': title},
    ).json()
    sent = client.post(
        FORM.format(pid=process['id']), json={'values': submission_values()}
    )
    assert sent.status_code == HTTPStatus.OK, sent.text
    return process['id']


@pytest.mark.asyncio
async def test_bracvam_le_e_limpa_a_caixa_sem_mexer_na_da_colega(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'pessoa_a')
    make_bracvam(client, 'pessoa_b')

    # 1. O proponente envia duas propostas; cada pessoa do BraCVAM fica com
    #    dois alerts de triagem não lidos.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    first = _send_proposal(client, 'Ensaio RhCE')
    _send_proposal(client, 'Ensaio BCOP')
    log_out(client)
    log_in(client, 'pessoa_a')
    inbox = _alerts(client)
    assert inbox['unread_count'] == 2
    assert {a['params']['activity_key'] for a in inbox['data']} == {
        'triage_evaluation'
    }

    # 2. A pede revisão na primeira proposta e não ganha alert novo.
    decision = client.post(
        f'/processes/{first}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Faltam dados.'},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    assert _alerts(client)['unread_count'] == 2

    # 3. A filtra os não lidos e recebe os dois.
    unread = _alerts(client, unread='true')['data']
    assert len(unread) == 2

    # 4. A marca um como lido; o contador vai a 1.
    marked = client.post(f'/alerts/{unread[0]["id"]}/read')
    assert marked.status_code == HTTPStatus.OK, marked.text
    assert marked.json()['read_at'] is not None
    assert _alerts(client)['unread_count'] == 1

    # 5. A marca todos; o que faltava passa a lido e o contador vai a 0.
    cleared = client.post('/alerts/read-all')
    assert cleared.json() == {'updated': 1}
    assert _alerts(client)['unread_count'] == 0
    log_out(client)

    # 6. B continua com os dois não lidos.
    log_in(client, 'pessoa_b')
    assert _alerts(client)['unread_count'] == 2

    # 7. B tenta marcar um alert de A e recebe 404, como se não existisse.
    foreign = client.post(f'/alerts/{unread[1]["id"]}/read')
    assert foreign.status_code == HTTPStatus.NOT_FOUND
    assert foreign.json()['detail']['code'] == 'not_found'
    assert _alerts(client)['unread_count'] == 2
