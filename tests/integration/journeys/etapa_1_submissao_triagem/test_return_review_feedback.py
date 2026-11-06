# ruff: noqa: PLR2004
"""Jornada: o proponente corrige a proposta lendo os pareceres da triagem e
consulta depois os pareceres de cada rodada devolvida (Spec 046, US1).

Parte de um deploy novo e usa a API pública. A primeira jornada usa o
template 1 (Método Novo), em que só a triagem avalia. A segunda usa o
template 4 (Dossiê), em que a IA devolve sem pareceres por campo.
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
from tests.factories.submission_factory import submission_values
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    make_bracvam,
    sign_up,
)

FORM = '/processes/{pid}/activities/proposal_submission/form'


def _triage_returns(client, pid, reviews, justification):
    for field_key, comments in reviews.items():
        saved = client.post(
            f'/processes/{pid}/triage/reviews',
            json={
                'reviews': [
                    {
                        'field_key': field_key,
                        'status': 'NAO_CONFORME',
                        'comments': comments,
                    }
                ]
            },
        )
        assert saved.status_code == HTTPStatus.OK, saved.text
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': justification},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text


def _choose_revise(client, pid):
    response = client.post(
        f'/processes/{pid}/return-review', json={'choice': 'REVISE'}
    )
    assert response.status_code == HTTPStatus.OK, response.text


def _comments(reviews):
    return {key: review['comments'] for key, review in reviews.items()}


@pytest.mark.asyncio
async def test_proponente_corrige_com_pareceres_e_consulta_cada_rodada(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triador')

    # 1. O proponente cria o processo e envia a primeira versão.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Método'},
    ).json()['id']
    client.post(FORM.format(pid=pid), json={'values': submission_values('V1')})
    log_out(client)

    # 2. A triagem aponta dois campos e devolve a submissão.
    log_in(client, 'triador')
    _triage_returns(
        client,
        pid,
        {'method_title': 'Título vago.', 'application_area': 'Delimitar.'},
        'Ajustar dois campos.',
    )
    log_out(client)

    # 3. O proponente entra em uma nova sessão e escolhe revisar. O formulário
    #    novo não tem pareceres próprios e traz os da rodada devolvida.
    log_in(client, 'proponente')
    _choose_revise(client, pid)
    log_out(client)
    log_in(client, 'proponente')
    form = client.get(FORM.format(pid=pid)).json()
    assert form['reviews'] == {}
    assert _comments(form['previous_reviews']) == {
        'method_title': 'Título vago.',
        'application_area': 'Delimitar.',
    }
    parecer = form['previous_reviews']['method_title']
    assert parecer['status'] == 'NAO_CONFORME'
    assert parecer['reviewed_at']

    # 4. Ele salva o rascunho e reenvia. A versão devolvida segue igual.
    version_1 = client.get(f'/processes/{pid}/submission-versions/1').json()
    assert version_1['reviews'] == form['previous_reviews']
    assert version_1['return_justification'] == 'Ajustar dois campos.'
    draft = client.put(
        FORM.format(pid=pid), json={'values': {'method_title': 'V2 rascunho'}}
    )
    assert draft.status_code == HTTPStatus.OK, draft.text
    sent = client.post(
        FORM.format(pid=pid), json={'values': submission_values('V2')}
    )
    assert sent.status_code == HTTPStatus.OK, sent.text
    again = client.get(f'/processes/{pid}/submission-versions/1').json()
    assert again['reviews'] == version_1['reviews']
    log_out(client)

    # 5. A triagem devolve a rodada 2 com outro parecer.
    log_in(client, 'triador')
    _triage_returns(
        client, pid, {'country': 'Rever o país.'}, 'Ajustar o país.'
    )
    log_out(client)

    # 6. Cada versão mostra só os pareceres da própria rodada.
    log_in(client, 'proponente')
    version_1 = client.get(f'/processes/{pid}/submission-versions/1').json()
    version_2 = client.get(f'/processes/{pid}/submission-versions/2').json()
    assert set(version_1['reviews']) == {'method_title', 'application_area'}
    assert _comments(version_2['reviews']) == {'country': 'Rever o país.'}


@pytest.mark.asyncio
async def test_proponente_revisa_retorno_da_ia_sem_pareceres(
    journey_client, session, monkeypatch, fake_provider
):
    del fake_provider
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. O administrador publica uma avaliação que a submissão não cumpre.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    log_out(client)

    # 2. O proponente envia e a IA devolve a submissão.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK, result['body']
    pid = result['process_id']
    await svc._execute(
        session, UUID(result['body']['pre_evaluation']['run_id'])
    )

    # 3. Ele escolhe revisar. A IA não grava pareceres por campo.
    _choose_revise(client, pid)
    form = client.get(FORM.format(pid=pid)).json()
    assert form['previous_reviews'] == {}

    # 4. O resultado da IA continua disponível na pré-avaliação.
    pre_evaluation = client.get(f'/processes/{pid}/pre-evaluation').json()
    assert pre_evaluation['consolidated_result'] == 'negative'
