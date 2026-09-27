"""Jornada: o BraCVAM monta o quadro da etapa 1 em uma chamada (Spec 032).

Parte de um deploy novo e usa só a API pública. Três proponentes deixam os
processos em pontos diferentes da etapa 1: rascunho, pré-avaliação por IA em
andamento e aguardando triagem. O BraCVAM pede as tarefas abertas da etapa 1
com as contagens e o resumo, como o frontend faria para montar o quadro, e
depois só o que ele mesmo precisa fazer.

O background fica desligado nos testes (`tests/conftest.py`), então a
pré-avaliação continua em andamento depois do envio.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
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
    sign_up,
)

FORM = '/processes/{pid}/activities/proposal_submission/form'


def _new_process(client, title):
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': title},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()['id']


@pytest.mark.asyncio
async def test_bracvam_builds_stage_one_board_in_one_call(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    triador = sign_up(client, 'triador')

    # 1. O administrador publica a avaliação de IA do template 4 e concede o
    #    perfil BraCVAM ao triador.
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    granted = client.post(
        f'/rbac/users/{triador["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)

    # 2. Dois processos ficam em rascunho, sem envio.
    sign_up(client, 'rascunho')
    log_in(client, 'rascunho')
    for title in ('Rascunho A', 'Rascunho B'):
        _new_process(client, title)
    log_out(client)

    # 3. Dois processos do template 4 são enviados e ficam em avaliação
    #    pela IA.
    sign_up(client, 'com_ia')
    log_in(client, 'com_ia')
    for _ in range(2):
        result = create_and_submit_process(client)
        assert result['status_code'] == HTTPStatus.OK, result['body']
        assert result['body']['pre_evaluation']['status'] == 'in_progress'
    log_out(client)

    # 4. Um processo do template 1 é enviado e vai direto para a triagem.
    sign_up(client, 'triagem')
    log_in(client, 'triagem')
    pid = _new_process(client, 'Aguardando triagem')
    sent = client.post(
        FORM.format(pid=pid), json={'values': {'method_title': 'Método'}}
    )
    assert sent.status_code == HTTPStatus.OK, sent.text
    log_out(client)

    # 5. O BraCVAM monta o quadro da etapa 1 em uma chamada.
    log_in(client, 'triador')
    board = client.get(
        '/tasks',
        params=[
            ('phase_order', 1),
            ('status', 'READY'),
            ('include', 'facets'),
            ('include', 'summary'),
        ],
    )
    assert board.status_code == HTTPStatus.OK, board.text
    body = board.json()
    assert body['facets']['activity_key'] == {
        'proposal_submission': 2,
        'triage_evaluation': 1,
    }
    assert body['summary'] == {'ai_pre_evaluation_in_progress': 2}

    # 6. Só o que o BraCVAM precisa fazer: a triagem.
    mine = client.get(
        '/tasks', params={'phase_order': 1, 'actionable': 'true'}
    ).json()
    assert [(t['activity_key'], t['process']['id']) for t in mine['data']] == [
        ('triage_evaluation', pid)
    ]
    assert mine['data'][0]['can_act'] is True
