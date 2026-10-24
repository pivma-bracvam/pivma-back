"""Jornadas da Spec 043: tipos de submissão e código da submissão.

Persona: um proponente recém-cadastrado num deploy novo (bootstrap real de
perfis, permissões, templates e administrador inicial), usando só a API
pública.

US1: o proponente abre a lista de tipos e vê os quatro tipos na ordem
pedida pelo BraCVAM, com os nomes e descrições novos. Abre o formulário do
primeiro tipo, cria a submissão e não consegue criar uma da Prova de
Conceito, que saiu do sistema.

US2: o proponente cria duas submissões no mesmo ano e recebe os códigos
`VAL-<ano>-0001` e `VAL-<ano>-0002`, que aparecem também na lista de
processos.
"""

from datetime import datetime
from http import HTTPStatus
from zoneinfo import ZoneInfo

import pytest

from tests.integration.journeys.conftest import (
    bootstrap_fresh_deploy,
    log_in,
    process_tasks,
    sign_up,
)

SUBMISSION_TYPES = (
    (
        'pre_validated_method',
        'Método Novo',
        'Método em desenvolvimento ou já desenvolvido, cujo processo de '
        'validação ainda não foi executado.',
    ),
    (
        'validated_method_dossier',
        'Método Novo – Dossiê Completo',
        'Método novo já desenvolvido, com protocolo estabelecido e processo '
        'de validação concluído, cujo dossiê está disponível para avaliação '
        'por pares.',
    ),
    (
        'scope_extension',
        'Extensão do Domínio de Aplicação',
        'Proposta de ampliação do domínio de aplicação de um método já '
        'validado, incluindo uma nova finalidade de uso ou aplicação '
        'regulatória.',
    ),
    (
        'me_too_validation',
        'Método Similar',
        'Método de ensaio estrutural e funcionalmente semelhante a um método '
        'de referência já validado e aceito, podendo ser candidato a um '
        'processo de validação baseado em padrões de desempenho '
        '(performance standards).',
    ),
)


@pytest.mark.asyncio
async def test_proponente_ve_os_tipos_na_ordem_do_bracvam_e_cria_submissao(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)

    # 1. O proponente se cadastra e entra.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')

    # 2. Vê os quatro tipos, na ordem do BraCVAM, com os textos novos.
    response = client.get('/processes/templates')
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert [
        (item['key'], item['name'], item['description'])
        for item in body['data']
    ] == list(SUBMISSION_TYPES)
    assert body['pagination']['total_items'] == len(SUBMISSION_TYPES)

    # 3. Abre o formulário do primeiro tipo e vê o nome novo.
    response = client.get(
        '/processes/templates/pre_validated_method'
        '/forms/submission_pre_validated_v1'
    )
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['name'] == 'Formulário de Submissão - Método Novo'

    # 4. Cria a submissão do primeiro tipo.
    response = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Ensaio RhCE para irritação',
        },
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    process_id = response.json()['id']
    submission_task = process_tasks(client, process_id)['proposal_submission']
    assert submission_task['status'] == 'READY'

    # 5. A Prova de Conceito não existe mais.
    response = client.post(
        '/processes',
        json={'template_key': 'proof_of_concept', 'title': 'Prova antiga'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'

    # 6. A lista de processos mostra só a submissão do passo 4.
    response = client.get('/processes')
    assert response.status_code == HTTPStatus.OK, response.text
    assert [item['id'] for item in response.json()['data']] == [process_id]


@pytest.mark.asyncio
async def test_proponente_recebe_codigos_sequenciais_do_ano(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    year = datetime.now(ZoneInfo('America/Sao_Paulo')).year

    # 1. O proponente se cadastra e entra.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')

    # 2. A primeira submissão do ano recebe o número 0001.
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Primeira'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    first = response.json()
    assert first['code'] == f'VAL-{year}-0001'

    # 3. A segunda recebe o número seguinte.
    response = client.post(
        '/processes',
        json={'template_key': 'scope_extension', 'title': 'Segunda'},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    second = response.json()
    assert second['code'] == f'VAL-{year}-0002'

    # 4. A lista de processos mostra os dois códigos.
    response = client.get('/processes')
    assert response.status_code == HTTPStatus.OK, response.text
    assert {item['code'] for item in response.json()['data']} == {
        first['code'],
        second['code'],
    }
