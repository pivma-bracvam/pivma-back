"""Jornada: o proponente só lê os pareceres depois da decisão (Spec 049, US2).

Enquanto o triador edita os pareceres, o formulário do proponente não os
mostra. Depois que a triagem pede revisão, eles aparecem sem o autor.
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

FORM = '/processes/{}/activities/proposal_submission/form'


def _form(client, process_id, **params):
    response = client.get(FORM.format(process_id), params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response


@pytest.mark.asyncio
async def test_proponente_le_pareceres_so_depois_do_pedido_de_revisao(
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
        FORM.format(process_id),
        json={'values': submission_values('Ensaio RhCE')},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    log_out(client)

    # 2. O triador salva um parecer e o vê no formulário.
    log_in(client, 'triador')
    triador_id = client.get('/auth/me').json()['user']['id']
    response = client.post(
        f'/processes/{process_id}/triage/reviews',
        json={
            'reviews': [
                {
                    'field_key': 'method_title',
                    'status': 'NAO_CONFORME',
                    'comments': 'Indicar o desfecho no título.',
                }
            ]
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    reviews = _form(client, process_id).json()['reviews']
    assert reviews['method_title']['comments'] == (
        'Indicar o desfecho no título.'
    )
    log_out(client)

    # 3. O proponente abre o formulário e ainda não vê o rascunho.
    log_in(client, 'proponente')
    assert _form(client, process_id).json()['reviews'] == {}
    log_out(client)

    # 4. O triador pede revisão.
    log_in(client, 'triador')
    response = client.post(
        f'/processes/{process_id}/triage/decision',
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Ajustar o título.',
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    log_out(client)

    # 5. O proponente lê o parecer da rodada 1, sem saber quem o escreveu.
    log_in(client, 'proponente')
    response = _form(client, process_id, run_number=1)
    parecer = response.json()['reviews']['method_title']
    assert parecer['comments'] == 'Indicar o desfecho no título.'
    assert triador_id not in response.text
