"""Jornada: o BraCVAM sabe que o proponente desistiu (Spec 047, US6).

Ator: duas pessoas do BraCVAM e o proponente. Objetivo: quem acompanha o
processo saber que ele fechou pela desistência, sem precisar abri-lo.
Parte de um deploy novo e usa só a API pública.
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


def _withdrawals(client):
    response = client.get('/alerts')
    assert response.status_code == HTTPStatus.OK, response.text
    return [
        a for a in response.json()['data'] if a['kind'] == 'process_withdrawn'
    ]


@pytest.mark.asyncio
async def test_bracvam_ve_a_desistencia_do_proponente(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triadora')
    make_bracvam(client, 'colega')

    # 1. O proponente envia a proposta e a triadora pede revisão.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    process = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Ensaio RhCE'},
    ).json()
    pid = process['id']
    client.post(FORM.format(pid=pid), json={'values': submission_values()})
    log_out(client)
    log_in(client, 'triadora')
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Faltam dados.'},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    log_out(client)

    # 2. O proponente desiste na revisão do retorno.
    log_in(client, 'proponente')
    withdrawn = client.post(
        f'/processes/{pid}/return-review',
        json={'choice': 'WITHDRAW', 'justification': 'Mudamos de estratégia.'},
    )
    assert withdrawn.status_code == HTTPStatus.OK, withdrawn.text
    assert withdrawn.json()['process_status'] == 'CLOSED'

    # 3. O proponente, que desistiu, não recebe o alert.
    assert _withdrawals(client) == []
    log_out(client)

    # 4. Cada pessoa do BraCVAM vê a desistência, com destino no processo e
    #    sem a justificativa do proponente.
    for username in ('triadora', 'colega'):
        log_in(client, username)
        [alert] = _withdrawals(client)
        assert alert['params']['process_code'] == process['code']
        assert alert['target'] == {
            'type': 'process',
            'process_id': pid,
            'id': None,
        }
        assert 'Mudamos' not in str(alert)
        log_out(client)
