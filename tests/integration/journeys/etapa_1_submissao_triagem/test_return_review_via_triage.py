# ruff: noqa: PLR2004
"""Jornada: a triagem pede revisão, o proponente revisa a submissão e o
BraCVAM aprova (Spec 030, US4).

Parte de um deploy novo e usa a API pública, como a jornada do processo 1,
no template 1 (Método Pré-Validado). Cobre o ciclo completo da revisão do
retorno aberta pela triagem: o pedido de revisão, a leitura da justificativa
pelo proponente, a reabertura da submissão como nova execução e a aprovação
que conclui a fase 1.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from pivma.core.database.models import Phase
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


def _decide(client, pid, outcome, justification):
    """Registra a decisão de triagem e exige `200`."""
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': outcome, 'justification': justification},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest.mark.asyncio
async def test_triage_revision_then_resubmission_then_approval(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    _make_bracvam(client, 'triador')

    # 1. Um proponente novo cria o processo e envia a primeira versão.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Método'},
    ).json()['id']
    client.post(FORM.format(pid=pid), json={'values': {'method_title': 'V1'}})
    log_out(client)

    # 2. O BraCVAM pede revisão; abre a primeira execução da revisão do
    #    retorno para o proponente.
    log_in(client, 'triador')
    decision = _decide(client, pid, 'NEEDS_REVISION', 'Faltam controles.')
    assert decision['return_review_run'] == 1
    log_out(client)

    # 3. O proponente lê a justificativa, escolhe revisar e reenvia: a
    #    submissão reabre como uma nova execução (2).
    log_in(client, 'proponente')
    review = client.get(f'/processes/{pid}/return-review').json()
    assert review['triage_decision']['justification'] == 'Faltam controles.'
    revise = client.post(
        f'/processes/{pid}/return-review', json={'choice': 'REVISE'}
    )
    assert revise.status_code == HTTPStatus.OK, revise.text
    resubmit = client.post(
        FORM.format(pid=pid), json={'values': {'method_title': 'V2'}}
    )
    assert resubmit.json()['run_number'] == 2
    log_out(client)

    # 4. O BraCVAM aprova a nova versão: o processo segue aberto e a fase 1
    #    (Submissão e Triagem) fica concluída.
    log_in(client, 'triador')
    assert _decide(client, pid, 'APPROVED', 'Ok.')['process_status'] == 'OPEN'

    assert client.get(f'/processes/{pid}').json()['status'] == 'OPEN'
    phase_1 = await session.scalar(
        select(Phase)
        .where(Phase.process_instance_id == pid, Phase.order_index == 1)
        .execution_options(populate_existing=True)
    )
    assert phase_1.status == 'COMPLETED'
