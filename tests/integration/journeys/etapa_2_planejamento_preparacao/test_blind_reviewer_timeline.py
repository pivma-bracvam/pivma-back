"""Jornada: o avaliador ad hoc lê a linha do tempo sem identificar o
proponente nem o outro avaliador (Spec 049, US4; RF050).

O BraCVAM aprova a triagem, designa o Grupo Gestor e dois avaliadores ad
hoc. Um avaliador lê a linha do tempo: os eventos do proponente chegam sem
autor, e o id do outro avaliador não aparece. O BraCVAM vê todos os autores.
"""

from http import HTTPStatus
from types import SimpleNamespace

import pytest

from tests.factories.submission_factory import submission_values
from tests.integration.journeys.conftest import (
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    make_bracvam,
    sign_up,
)
from tests.integration.journeys.sample_steps import designate, ok


def _timeline(client, process_id):
    response = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response


def _created(response):
    [event] = [
        e
        for e in response.json()['data']
        if e['event_type'] == 'PROCESS_CREATED'
    ]
    return event


@pytest.mark.asyncio
async def test_avaliador_ad_hoc_le_a_linha_do_tempo_as_cegas(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'helena')
    team = SimpleNamespace(**{
        key: SimpleNamespace(**sign_up(client, name))
        for key, name in (
            ('proponent', 'proponente'),
            ('gestor', 'marcos'),
            ('adhoc_1', 'especialista1'),
            ('adhoc_2', 'especialista2'),
        )
    })

    # 1. O proponente cria o processo e envia a submissão.
    log_in(client, 'proponente')
    process_id = ok(
        client.post(
            '/processes',
            json={'template_key': 'pre_validated_method', 'title': 'Método'},
        ),
        HTTPStatus.CREATED,
    )['id']
    ok(
        client.post(
            f'/processes/{process_id}/activities/proposal_submission/form',
            json={'values': submission_values('Ensaio RhCE')},
        )
    )
    log_out(client)

    # 2. O BraCVAM aprova a triagem, designa o Grupo Gestor e, depois dele,
    # os dois avaliadores ad hoc.
    log_in(client, 'helena')
    helena_id = client.get('/auth/me').json()['user']['id']
    ok(
        client.post(
            f'/processes/{process_id}/triage/decision',
            json={'outcome': 'APPROVED', 'justification': 'Completa.'},
        )
    )
    designate(client, process_id, team.gestor, 'group_manager')
    designate(client, process_id, team.adhoc_1, 'adhoc_evaluator')
    designate(client, process_id, team.adhoc_2, 'adhoc_evaluator')
    log_out(client)

    # 3. O avaliador 1 lê a linha do tempo sem o proponente e sem o outro
    # avaliador; a própria designação traz o autor do BraCVAM.
    log_in(client, 'especialista1')
    response = _timeline(client, process_id)
    assert _created(response)['user_id'] is None
    assert team.proponent.id not in response.text
    assert team.adhoc_2.id not in response.text
    [own] = [
        e
        for e in response.json()['data']
        if e['event_type'] == 'PARTICIPANT_ASSIGNED'
    ]
    assert own['context_data']['participant_user_id'] == team.adhoc_1.id
    assert own['user_id'] == helena_id
    log_out(client)

    # 4. O BraCVAM vê a mesma linha do tempo com todos os autores.
    log_in(client, 'helena')
    response = _timeline(client, process_id)
    assert _created(response)['user_id'] == team.proponent.id
    assert team.adhoc_2.id in response.text
