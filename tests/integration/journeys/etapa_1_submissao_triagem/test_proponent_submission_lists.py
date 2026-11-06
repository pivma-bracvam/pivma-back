"""Jornada: o proponente acompanha os próprios rascunhos e submissões.

Parte de um deploy novo e usa a API pública. O proponente separa o que ainda
não enviou do que já enviou, sem ver processos de outra pessoa. A submissão
devolvida pela triagem continua entre as enviadas, para ele responder ao
retorno. Decisão registrada em `docs/observacoes-e-pendencias.md`.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from tests.factories.submission_factory import submission_values
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)

FORM = '/processes/{pid}/activities/proposal_submission/form'


def _make_bracvam(client, username):
    """Cadastra o usuário e concede o perfil BraCVAM pelo administrador."""
    user = sign_up(client, username)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    granted = client.post(
        f'/rbac/users/{user["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)


def _new_process(client, title):
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': title},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()['id']


def _listed(client, **params):
    """Ids da listagem de processos, como o frontend os receberia."""
    response = client.get('/processes', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return [item['id'] for item in response.json()['data']]


@pytest.mark.asyncio
async def test_proponent_tracks_own_drafts_and_sent_submissions(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    _make_bracvam(client, 'triador')

    # 1. O proponente cria dois processos e envia só um deles.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    draft = _new_process(client, 'Ainda em rascunho')
    sent = _new_process(client, 'Já enviada')
    submitted = client.post(
        FORM.format(pid=sent), json={'values': submission_values('Método')}
    )
    assert submitted.status_code == HTTPStatus.OK, submitted.text

    # 2. Cada processo aparece na própria lista.
    assert _listed(client, mine=True, submission_state='draft') == [draft]
    assert _listed(client, mine=True, submission_state='submitted') == [sent]
    log_out(client)

    # 3. Outro proponente não encontra nada.
    sign_up(client, 'outra-pessoa')
    log_in(client, 'outra-pessoa')
    assert _listed(client, mine=True) == []
    log_out(client)

    # 4. O BraCVAM vê os dois processos, mas nenhum é dele.
    log_in(client, 'triador')
    assert set(_listed(client)) == {draft, sent}
    assert _listed(client, mine=True) == []

    # 5. A triagem devolve a submissão enviada.
    decided = client.post(
        f'/processes/{sent}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Ajustar.'},
    )
    assert decided.status_code == HTTPStatus.OK, decided.text
    log_out(client)

    # 6. Ela continua entre as enviadas e o proponente abre o retorno.
    log_in(client, 'proponente')
    assert _listed(client, mine=True, submission_state='submitted') == [sent]
    assert client.get(f'/processes/{sent}/return-review').status_code == (
        HTTPStatus.OK
    )

    # 7. Ao revisar, a submissão reabre sem voltar para os rascunhos.
    revised = client.post(
        f'/processes/{sent}/return-review', json={'choice': 'REVISE'}
    )
    assert revised.status_code == HTTPStatus.OK, revised.text
    assert _listed(client, mine=True, submission_state='draft') == [draft]
    assert _listed(client, mine=True, submission_state='submitted') == [sent]
