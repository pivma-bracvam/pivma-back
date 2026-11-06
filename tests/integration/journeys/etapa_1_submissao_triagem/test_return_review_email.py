"""Jornada: o proponente fecha o sistema e sabe da devolução por e-mail
(Spec 046, US2).

Parte de um deploy novo e usa a API pública. O canal é o `FakeEmailChannel`,
e o worker roda na própria sessão do teste, como `process_next` faz em
produção. A pré-avaliação roda de forma síncrona por
`pre_evaluation_service`, porque o background fica desligado nos testes.
"""

from datetime import datetime
from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import Notification
from pivma.notifications.channels import FakeEmailChannel
from pivma.notifications.worker import process_next
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
    process_tasks,
    sign_up,
)

FORM = '/processes/{pid}/activities/proposal_submission/form'
PROPONENT_EMAIL = 'proponente@example.com'


async def _inbox(session, settings):
    """O worker entrega o que estiver pendente; devolve o que chegou."""
    channel = FakeEmailChannel()
    while await process_next(session, channel, settings):
        pass
    return channel.sent


def _ai_process(client):
    """O proponente envia uma submissão que a IA vai devolver."""
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK, result['body']
    return (
        result['process_id'],
        UUID(result['body']['pre_evaluation']['run_id']),
    )


@pytest.mark.asyncio
async def test_proponente_recebe_aviso_da_devolucao_pela_triagem_e_pela_ia(
    journey_client, session, monkeypatch, fake_provider, return_email_settings
):
    del fake_provider
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'triador')

    # 1. O administrador publica uma avaliação que reprova o template 4.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    log_out(client)

    # 2. O proponente envia a proposta. Ninguém avaliou, então não há aviso.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    process = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Ensaio RhCE'},
    ).json()
    pid = process['id']
    client.post(FORM.format(pid=pid), json={'values': submission_values()})
    assert await _inbox(session, return_email_settings) == []
    log_out(client)

    # 3. A triagem devolve. O proponente recebe um e-mail com o processo, a
    #    origem, o prazo da tarefa e a orientação de entrar na plataforma.
    log_in(client, 'triador')
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Faltam dados.'},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    log_out(client)
    [message] = await _inbox(session, return_email_settings)
    assert message.to == PROPONENT_EMAIL
    assert message.subject == f'Submissão devolvida — {process["code"]}'
    assert f'{process["code"]} — Ensaio RhCE' in message.text
    assert 'Origem: Triagem' in message.text
    assert 'Acesse a pi*VMA' in message.text

    # 4. O proponente entra, vê a tarefa com o mesmo prazo, revisa e reenvia.
    #    Nada disso gera outro aviso.
    log_in(client, 'proponente')
    due_date = process_tasks(client, pid)['submission_return_review'][
        'due_date'
    ]
    deadline = datetime.fromisoformat(due_date).strftime('%d/%m/%Y %H:%M')
    assert f'Prazo: {deadline} (UTC)' in message.text
    revise = client.post(
        f'/processes/{pid}/return-review', json={'choice': 'REVISE'}
    )
    assert revise.status_code == HTTPStatus.OK, revise.text
    sent = client.post(
        FORM.format(pid=pid), json={'values': submission_values('V2')}
    )
    assert sent.status_code == HTTPStatus.OK, sent.text
    assert await _inbox(session, return_email_settings) == []

    # 5. Em outro processo, a IA devolve. O aviso traz a origem da IA.
    _, run_id = _ai_process(client)
    await svc._execute(session, run_id)
    [message] = await _inbox(session, return_email_settings)
    assert message.to == PROPONENT_EMAIL
    assert 'Origem: Pré-avaliação por IA' in message.text


@pytest.mark.asyncio
async def test_reprocessamento_cancela_aviso_pendente_e_nova_devolucao_avisa(
    journey_client, session, monkeypatch, fake_provider, return_email_settings
):
    del fake_provider
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. O administrador publica uma avaliação que reprova o template 4.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    log_out(client)

    # 2. O proponente envia e a pré-avaliação falha. O aviso fica na fila,
    #    que o usuário não enxerga: a leitura direta é a exceção da jornada.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    pid, run_id = _ai_process(client)
    await svc._mark_failed(session, run_id)
    pending = await session.scalar(select(Notification))
    assert pending.status == 'pending'
    log_out(client)

    # 3. O administrador reprocessa antes do envio. O aviso é cancelado e o
    #    retorno some da fila do proponente.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    retry = client.post(f'/admin/pre-evaluations/{run_id}/retry')
    assert retry.status_code == HTTPStatus.ACCEPTED, retry.text
    new_run_id = UUID(retry.json()['new_run_id'])
    log_out(client)
    assert await _inbox(session, return_email_settings) == []
    await session.refresh(pending)
    assert pending.status == 'cancelled'

    log_in(client, 'proponente')
    tasks = process_tasks(client, pid)
    assert tasks['submission_return_review']['status'] == 'CANCELLED'
    assert (
        client.get(f'/processes/{pid}/return-review').status_code
        == HTTPStatus.NOT_FOUND
    )

    # 4. A nova execução também devolve: chega um aviso novo.
    await svc._execute(session, new_run_id)
    [message] = await _inbox(session, return_email_settings)
    assert message.to == PROPONENT_EMAIL
    assert (
        client.get(f'/processes/{pid}/return-review').status_code
        == HTTPStatus.OK
    )
