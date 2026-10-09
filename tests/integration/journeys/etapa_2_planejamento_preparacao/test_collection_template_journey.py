"""Jornadas do catálogo de templates de coleta de dados (Spec 041).

1. Beatriz, da equipe BraCVAM, monta o template "Ensaio de citotoxicidade"
   com seis colunas de tipos mistos, confere a ordem na consulta, baixa o
   arquivo-modelo em CSV e em Excel e encontra o template no catálogo.
2. Beatriz erra três colunas (chave repetida, chave reservada e seleção sem
   opções), vê cada recusa sem que o template mude e corrige cada pedido.
3. Paulo, proponente sem a permissão do catálogo, cria um processo sem
   template e não consegue vincular um. Beatriz cria um processo com o
   template e vê o vínculo na resposta, na consulta, na listagem e na trilha.
4. Um processo vinculado conclui a definição das amostras. Beatriz vê o
   template travado, não consegue adicionar coluna, mas ainda o renomeia e
   baixa o arquivo.
5. Beatriz exclui uma coluna que sobrou, vê que ela some da consulta e do
   arquivo e recria uma coluna com a mesma chave e posição.
6. Paulo não acessa o catálogo até o administrador lhe conceder o perfil
   BraCVAM; depois disso cria e lista templates.

Partem de um deploy novo e usam a API pública, exceto a jornada 4, que
parte da equipe de estudo de `sample_steps.study_team`.
"""

import io
from http import HTTPStatus

import pytest
from openpyxl import load_workbook

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.collection_template_factory import (
    grant_catalog_permission,
)
from tests.factories.sample_factory import VALID_CAS, substance_payload
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)
from tests.integration.journeys.sample_steps import (
    ok,
    open_sample_definition,
    register_substance,
    study_team,
)

FIXED = ['codigo_amostra', 'experimento', 'replica']
US1_COLUMNS = [
    {'key': 'viabilidade', 'label': 'Viabilidade (%)', 'type': 'decimal',
     'required': True},
    {'key': 'contagem_celulas', 'label': 'Contagem de células',
     'type': 'integer', 'required': True},
    {'key': 'data_leitura', 'label': 'Data da leitura', 'type': 'date',
     'required': True},
    {'key': 'observacao', 'label': 'Observação', 'type': 'text'},
    {'key': 'resultado', 'label': 'Resultado', 'type': 'select',
     'required': True,
     'options': ['positivo', 'negativo', 'inconclusivo']},
    {'key': 'lote_reagente', 'label': 'Lote do reagente', 'type': 'text'},
]  # fmt: skip
TEMPLATES = '/collection-templates'


def _grant_bracvam(client, user_id):
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    granted = client.post(
        f'/rbac/users/{user_id}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)


async def _beatriz_logged_in(client, session, monkeypatch):
    """Deploy novo; o administrador concede o perfil BraCVAM a Beatriz."""
    await bootstrap_fresh_deploy(session, monkeypatch)
    beatriz = sign_up(client, 'beatriz')
    _grant_bracvam(client, beatriz['id'])
    log_in(client, 'beatriz')


def _create_template(client, name='Ensaio de citotoxicidade'):
    response = client.post(
        TEMPLATES,
        json={
            'name': name,
            'description': 'Viabilidade celular por MTT.',
            'min_experiments': 3,
            'min_replicates': 2,
        },
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()


def _add_column(client, template_id, column):
    return client.post(f'{TEMPLATES}/{template_id}/columns', json=column)


def _column_keys(client, template_id):
    response = client.get(f'{TEMPLATES}/{template_id}')
    assert response.status_code == HTTPStatus.OK, response.text
    return [column['key'] for column in response.json()['columns']]


def _csv_header(client, template_id):
    response = client.get(
        f'{TEMPLATES}/{template_id}/file', params={'format': 'csv'}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.content.decode('utf-8-sig').strip().split(';')


@pytest.mark.asyncio
async def test_bracvam_monta_template_e_baixa_arquivo_modelo(
    journey_client, session, monkeypatch
):
    client = journey_client
    await _beatriz_logged_in(client, session, monkeypatch)

    # 1. Beatriz cria o template e o vê vazio e destravado.
    template = _create_template(client)
    assert template['columns'] == []
    assert template['locked'] is False

    # 2. Adiciona as seis colunas sem posição e as vê em sequência.
    positions = []
    for column in US1_COLUMNS:
        response = _add_column(client, template['id'], column)
        assert response.status_code == HTTPStatus.CREATED, response.text
        positions.append(response.json()['position'])
    assert positions == [1, 2, 3, 4, 5, 6]

    # 3. Consulta o template e vê as colunas na ordem.
    keys = [column['key'] for column in US1_COLUMNS]
    assert _column_keys(client, template['id']) == keys

    # 4. Baixa o CSV: uma linha com os nove cabeçalhos.
    assert _csv_header(client, template['id']) == [*FIXED, *keys]

    # 5. Baixa o Excel: os mesmos nove cabeçalhos na linha 1.
    response = client.get(
        f'{TEMPLATES}/{template["id"]}/file', params={'format': 'xlsx'}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    sheet = load_workbook(io.BytesIO(response.content))['resultados']
    assert [cell.value for cell in sheet[1]] == [*FIXED, *keys]

    # 6. Lista o catálogo e encontra o template.
    listed = client.get(TEMPLATES).json()['data']
    assert [item['id'] for item in listed] == [template['id']]


@pytest.mark.asyncio
async def test_bracvam_corrige_colunas_recusadas(
    journey_client, session, monkeypatch
):
    client = journey_client
    await _beatriz_logged_in(client, session, monkeypatch)
    template = _create_template(client)
    viabilidade = {
        'key': 'viabilidade',
        'label': 'Viabilidade',
        'type': 'text',
    }
    assert _add_column(client, template['id'], viabilidade).status_code == (
        HTTPStatus.CREATED
    )

    attempts = [
        # 1. Beatriz repete uma chave e vê `duplicate_key`.
        (
            viabilidade,
            'duplicate_key',
            {'key': 'viabilidade_final', 'label': 'Final', 'type': 'text'},
        ),
        # 2. Usa a chave reservada `replica` e vê `reserved_key`.
        (
            {'key': 'replica', 'label': 'Réplica', 'type': 'integer'},
            'reserved_key',
            {'key': 'replica_tecnica', 'label': 'Réplica', 'type': 'integer'},
        ),
        # 3. Cria uma seleção sem opções e vê `invalid_options`.
        (
            {'key': 'resultado', 'label': 'Resultado', 'type': 'select'},
            'invalid_options',
            {
                'key': 'resultado',
                'label': 'Resultado',
                'type': 'select',
                'options': ['positivo', 'negativo'],
            },
        ),
    ]
    for wrong, code, fixed in attempts:
        keys_before = _column_keys(client, template['id'])
        refused = _add_column(client, template['id'], wrong)
        assert refused.json()['detail']['code'] == code
        # 4. Depois de cada recusa, o template tem as mesmas colunas.
        assert _column_keys(client, template['id']) == keys_before
        # 5. Beatriz corrige o pedido e vê a coluna aceita.
        accepted = _add_column(client, template['id'], fixed)
        assert accepted.status_code == HTTPStatus.CREATED, accepted.text

    assert _column_keys(client, template['id']) == [
        'viabilidade',
        'viabilidade_final',
        'replica_tecnica',
        'resultado',
    ]


def _create_process(client, **fields):
    return client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Validação de citotoxicidade',
            **fields,
        },
    )


@pytest.mark.asyncio
async def test_proponente_sem_permissao_e_bracvam_vinculam_template(
    journey_client, session, monkeypatch
):
    client = journey_client
    await _beatriz_logged_in(client, session, monkeypatch)
    template = _create_template(client)
    log_out(client)

    # 1. Paulo, recém-cadastrado, cria um processo sem template.
    sign_up(client, 'paulo')
    log_in(client, 'paulo')
    created = _create_process(client)
    assert created.status_code == HTTPStatus.CREATED, created.text
    assert created.json()['collection_template_id'] is None

    # 2. Paulo tenta vincular o template e é recusado; segue com um processo.
    refused = _create_process(client, collection_template_id=template['id'])
    assert refused.status_code == HTTPStatus.FORBIDDEN
    assert refused.json()['detail']['code'] == 'forbidden'
    assert client.get('/processes').json()['pagination']['total_items'] == 1
    log_out(client)

    # 3. Beatriz cria um processo com o template e vê o vínculo na
    #    resposta, na consulta e na listagem.
    log_in(client, 'beatriz')
    linked = _create_process(client, collection_template_id=template['id'])
    assert linked.status_code == HTTPStatus.CREATED, linked.text
    process_id = linked.json()['id']
    assert linked.json()['collection_template_id'] == template['id']
    read = client.get(f'/processes/{process_id}').json()
    assert read['collection_template_id'] == template['id']
    listed = {
        item['id']: item['collection_template_id']
        for item in client.get('/processes').json()['data']
    }
    assert listed[process_id] == template['id']

    # 4. Na trilha do processo, a criação registra o template.
    events = client.get(f'/processes/{process_id}/timeline').json()['data']
    created_event = next(
        e for e in events if e['event_type'] == 'PROCESS_CREATED'
    )
    assert (
        created_event['context_data']['collection_template_id']
        == (template['id'])
    )


@pytest.fixture
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


@pytest.mark.asyncio
@pytest.mark.usefixtures('_attachments_dir')
async def test_estrutura_trava_quando_a_definicao_das_amostras_conclui(
    journey_client, session, bracvam_user
):
    client = journey_client
    team = await study_team(session, lab_count=1)
    # O proponente já tem a permissão do catálogo, por um perfil
    # personalizado. Ao criar a linha da permissão, o perfil BraCVAM de
    # Beatriz (`bracvam_user`) também passa a cobri-la, como em produção.
    await grant_catalog_permission(session, team.proponent)

    # 1. Beatriz cria o template e o vê destravado.
    authenticate(client, bracvam_user)
    template = _create_template(client)
    assert template['locked'] is False
    added = _add_column(
        client,
        template['id'],
        {'key': 'viabilidade', 'label': 'Viabilidade', 'type': 'decimal'},
    )
    assert added.status_code == HTTPStatus.CREATED, added.text

    # 2. O proponente cria o processo com o template; o processo segue
    #    até a definição das amostras.
    process_id = open_sample_definition(
        client, team, bracvam_user, collection_template_id=template['id']
    )

    # 3. O Grupo de Seleção cadastra a substância e conclui a definição.
    authenticate(client, team.selector)
    register_substance(
        client, process_id, substance_payload(cas_number=VALID_CAS[0])
    )
    ok(client.post(f'/processes/{process_id}/samples/complete'))

    # 4. Beatriz consulta o template e o vê travado.
    authenticate(client, bracvam_user)
    read = client.get(f'{TEMPLATES}/{template["id"]}').json()
    assert read['locked'] is True

    # 5. Beatriz tenta adicionar uma coluna e é recusada.
    refused = _add_column(
        client,
        template['id'],
        {'key': 'lote', 'label': 'Lote', 'type': 'text'},
    )
    assert refused.status_code == HTTPStatus.CONFLICT
    assert refused.json()['detail']['code'] == 'template_locked'
    assert _column_keys(client, template['id']) == ['viabilidade']

    # 6. Ainda renomeia o template e baixa o arquivo-modelo.
    renamed = client.patch(
        f'{TEMPLATES}/{template["id"]}', json={'name': 'Citotoxicidade v2'}
    )
    assert renamed.status_code == HTTPStatus.OK, renamed.text
    assert _csv_header(client, template['id']) == [*FIXED, 'viabilidade']


@pytest.mark.asyncio
async def test_bracvam_exclui_coluna_e_reaproveita_a_chave(
    journey_client, session, monkeypatch
):
    client = journey_client
    await _beatriz_logged_in(client, session, monkeypatch)
    template = _create_template(client)
    for column in US1_COLUMNS:
        _add_column(client, template['id'], column)
    columns = client.get(f'{TEMPLATES}/{template["id"]}').json()['columns']
    lote = next(c for c in columns if c['key'] == 'lote_reagente')

    # 1. Beatriz exclui a coluna `lote_reagente`.
    deleted = client.delete(
        f'{TEMPLATES}/{template["id"]}/columns/{lote["id"]}'
    )
    assert deleted.status_code == HTTPStatus.NO_CONTENT

    # 2. A coluna some da consulta e do arquivo-modelo.
    assert 'lote_reagente' not in _column_keys(client, template['id'])
    assert 'lote_reagente' not in _csv_header(client, template['id'])

    # 3. Beatriz recria a coluna com a mesma chave e a mesma posição.
    recreated = _add_column(
        client,
        template['id'],
        {
            'key': 'lote_reagente',
            'label': 'Lote do reagente',
            'type': 'text',
            'position': lote['position'],
        },
    )
    assert recreated.status_code == HTTPStatus.CREATED, recreated.text
    assert _column_keys(client, template['id'])[-1] == 'lote_reagente'


@pytest.mark.asyncio
async def test_acesso_ao_catalogo_depende_da_permissao(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    paulo = sign_up(client, 'paulo')
    log_in(client, 'paulo')

    # 1. Paulo, recém-cadastrado, não lista o catálogo nem cria template.
    listed = client.get(TEMPLATES)
    created = client.post(
        TEMPLATES,
        json={'name': 'Ensaio', 'min_experiments': 1, 'min_replicates': 1},
    )
    for response in (listed, created):
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()['detail']['code'] == 'forbidden'
    log_out(client)

    # 2. O administrador concede o perfil BraCVAM a Paulo.
    _grant_bracvam(client, paulo['id'])

    # 3. Paulo entra de novo, cria o template e o vê na listagem.
    log_in(client, 'paulo')
    template = _create_template(client)
    listed = client.get(TEMPLATES)
    assert listed.status_code == HTTPStatus.OK, listed.text
    assert [item['id'] for item in listed.json()['data']] == [template['id']]
