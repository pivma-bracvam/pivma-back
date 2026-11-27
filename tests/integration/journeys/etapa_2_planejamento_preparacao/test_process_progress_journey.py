"""Jornadas do andamento do processo (Spec 048).

Personas:

- Helena, do BraCVAM. Designa os cargos do estudo, inclusive o Patrocinador,
  e revoga uma designação quando preciso.
- Paula, a Patrocinadora. Quer saber em que ponto estão os processos que
  patrocina: quem participa, a fase atual e o que está em andamento. Não vê
  nome químico, CAS, código cego nem o conteúdo dos formulários.
- Pedro, o proponente, que submete o processo e acompanha o andamento sem
  saber quem avalia nem quais laboratórios testam o método.
- Lara, de um dos laboratórios participantes, que acompanha só a própria
  execução.

Estado inicial comum: ambiente com os templates padrão; o proponente
submete o processo do template 1 pela API pública, Helena aprova a triagem e
designa o Grupo Gestor, o Grupo de Seleção e os laboratórios, e a definição
das amostras fica em andamento.

Jornadas:

1. Paula vê só os processos que patrocina, com a fase atual e quantas
   atividades estão em andamento, e o processo some quando Helena revoga a
   designação (US1).
2. Paula acompanha o processo da Fase 2 à Fase 3: vê o proponente e a
   equipe, as atividades em andamento e, depois da homologação, um
   recebimento por laboratório. O cartão da lista mostra a mesma fase do
   detalhe (US2).
3. Paula acompanha a Fase 3 sem ver nada do estudo, e as rotas de amostras
   e de formulário continuam fechadas para ela (US3).
4. Na mesma Fase 3, Pedro e Lara abrem o andamento: os dois veem a mesma
   fase de Paula, mas Pedro não vê avaliador nem laboratório, e Lara vê só
   o próprio laboratório (US4).

Os desvios (cada cargo, cada estado, paginação) ficam nos testes focados de
`tests/api/routers/test_process_progress*.py`.
"""

from http import HTTPStatus

import pytest

from tests.api.routers.test_process_progress import open_runs_of
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import VALID_CAS, substance_payload
from tests.factories.submission_factory import submission_values
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    approve_structure,
    complete_study_team,
    designate,
    ok,
    open_sample_definition,
    register_substance,
    study_team,
)

LIST = '/processes'
SPONSOR = {'role': 'sponsor'}
PHASE_2 = 'phase_2_role_assignment'
PHASE_3 = 'phase_3_validation_execution'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def _cartoes(client, params=SPONSOR):
    return {
        item['id']: item
        for item in ok(client.get(LIST, params=params))['data']
    }


def _detalhe(client, process_id):
    return ok(client.get(f'{LIST}/{process_id}/progress'))


def _pessoas(detalhe):
    return {r['role_key']: r['people'] for r in detalhe['roles']}


def _cartao_igual_ao_detalhe(client, process_id, detalhe):
    cartao = _cartoes(client, params={})[process_id]
    assert cartao['current_phase'] == detalhe['current_phase']
    assert cartao['open_activity_count'] == len(open_runs_of(detalhe))


def _abre_fase_3(client, team, process_id, bracvam_user, substancias):
    """O Grupo de Seleção cadastra e conclui as amostras; Helena homologa."""
    authenticate(client, team.selector)
    cadastradas = [
        register_substance(client, process_id, payload)
        for payload in substancias
    ]
    ok(
        client.post(
            f'/processes/{process_id}/samples/complete', headers=ORIGIN
        )
    )
    approve_structure(client, process_id, bracvam_user)
    return cadastradas


@pytest.mark.asyncio
async def test_patrocinadora_ve_so_os_processos_que_patrocina(
    session, client, bracvam_user
):
    team = await study_team(session, lab_count=1)

    # 1. Dois processos chegam à Fase 2 com as amostras em andamento.
    patrocinado = open_sample_definition(client, team, bracvam_user)
    outro = open_sample_definition(client, team, bracvam_user)

    # 2. Helena designa Paula Patrocinadora no primeiro e Colaboradora no
    #    segundo.
    designacao = designate(client, patrocinado, team.sponsor, 'sponsor')
    designate(client, outro, team.sponsor, 'collaborator')

    # 3. Paula filtra os processos em que é Patrocinadora e vê só o que
    #    patrocina, com a data da designação, a fase atual e as atividades
    #    em andamento.
    authenticate(client, team.sponsor)
    cartoes = _cartoes(client)
    assert list(cartoes) == [patrocinado]
    cartao = cartoes[patrocinado]
    assert cartao['code']
    assert cartao['title'] == 'Estudo cego de irritação ocular'
    assert cartao['status'] == 'OPEN'
    assert cartao['started_at'] is not None
    assert [(r['role_key'], r['assigned_at']) for r in cartao['my_roles']] == [
        ('sponsor', designacao['assigned_at'])
    ]
    assert cartao['current_phase']['key'] == PHASE_2
    assert cartao['open_activity_count'] >= 1

    # 4. Helena revoga a designação de Paula.
    authenticate(client, bracvam_user)
    revogada = client.delete(
        f'/processes/{patrocinado}/participants/{designacao["id"]}',
        headers=ORIGIN,
    )
    assert revogada.status_code == HTTPStatus.NO_CONTENT, revogada.text

    # 5. Paula consulta de novo e a lista de patrocínios está vazia.
    authenticate(client, team.sponsor)
    assert ok(client.get(LIST, params=SPONSOR))['data'] == []


@pytest.mark.asyncio
async def test_patrocinadora_acompanha_da_fase_2_a_fase_3(
    session, client, bracvam_user
):
    team = await study_team(session, lab_count=2)

    # 1. Processo com dois laboratórios, amostras em andamento e a equipe
    #    completa, com Paula Patrocinadora.
    process_id = open_sample_definition(client, team, bracvam_user)
    complete_study_team(client, team, process_id, bracvam_user)

    # 2. Paula abre o detalhe: vê o proponente e o Grupo Gestor, sem e-mail,
    #    e as atividades em andamento da Fase 2.
    authenticate(client, team.sponsor)
    resposta = client.get(f'{LIST}/{process_id}/progress')
    detalhe = ok(resposta)
    pessoas = _pessoas(detalhe)
    assert [p['user']['id'] for p in pessoas['proponent']] == [
        str(team.proponent.id)
    ]
    assert [p['user']['id'] for p in pessoas['group_manager']] == [
        str(team.manager.id)
    ]
    assert '"email"' not in resposta.text
    assert detalhe['current_phase']['key'] == PHASE_2
    atividades = open_runs_of(detalhe)
    assert 'sample_definition' in {a['key'] for a in atividades}
    assert {a['phase_key'] for a in atividades} == {PHASE_2}
    _cartao_igual_ao_detalhe(client, process_id, detalhe)

    # 3. O Grupo de Seleção cadastra a substância e conclui as amostras;
    #    Helena aprova a estrutura.
    _abre_fase_3(client, team, process_id, bracvam_user, [substance_payload()])

    # 4. Paula vê a Fase 3 com um recebimento por laboratório, e o cartão
    #    continua igual ao detalhe.
    authenticate(client, team.sponsor)
    detalhe = _detalhe(client, process_id)
    assert detalhe['current_phase']['key'] == PHASE_3
    recebimentos = sorted(
        a['laboratory']['name']
        for a in open_runs_of(detalhe)
        if a['key'] == 'sample_receipt'
    )
    assert recebimentos == sorted(lab.name for lab in team.laboratories)
    _cartao_igual_ao_detalhe(client, process_id, detalhe)


@pytest.mark.asyncio
async def test_patrocinadora_acompanha_sem_ver_o_estudo(
    session, client, bracvam_user
):
    team = await study_team(session, lab_count=2)

    # 1. Processo na Fase 3 com duas substâncias de nome e CAS conhecidos.
    process_id = open_sample_definition(client, team, bracvam_user)
    complete_study_team(client, team, process_id, bracvam_user)
    substancias = _abre_fase_3(
        client,
        team,
        process_id,
        bracvam_user,
        [
            substance_payload(
                chemical_name=f'Substância secreta {index}',
                cas_number=VALID_CAS[index],
            )
            for index in range(2)
        ],
    )
    segredos = [
        valor
        for substancia in substancias
        for valor in (
            substancia['chemical_name'],
            substancia['cas_number'],
            *(codigo['code'] for codigo in substancia['blind_codes']),
        )
    ]
    segredos += ['sds.pdf', submission_values()['method_description']]

    # 2. Paula abre a lista e o detalhe: nenhum dado do estudo aparece.
    authenticate(client, team.sponsor)
    respostas = [
        client.get(LIST, params=SPONSOR),
        client.get(f'{LIST}/{process_id}/progress'),
    ]
    for resposta in respostas:
        assert resposta.status_code == HTTPStatus.OK
        for segredo in segredos:
            assert segredo not in resposta.text, segredo

    # 3. As amostras e o plano estatístico continuam fechados para ela.
    for caminho in ('samples', 'activities/statistical_plan/form'):
        negado = client.get(f'/processes/{process_id}/{caminho}')
        assert negado.status_code in {
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
        }, caminho
        for segredo in segredos:
            assert segredo not in negado.text, segredo


@pytest.mark.asyncio
async def test_proponente_e_laboratorio_acompanham_com_recorte(
    session, client, bracvam_user
):
    team = await study_team(session, lab_count=2)

    # 1. Processo na Fase 3 com a equipe completa e um recebimento aberto
    #    por laboratório.
    process_id = open_sample_definition(client, team, bracvam_user)
    complete_study_team(client, team, process_id, bracvam_user)
    _abre_fase_3(client, team, process_id, bracvam_user, [substance_payload()])
    authenticate(client, team.sponsor)
    da_patrocinadora = _detalhe(client, process_id)

    # 2. Pedro abre o andamento: vê a mesma fase de Paula, o Grupo Gestor e a
    #    Patrocinadora, sem o avaliador ad hoc e sem nenhum laboratório.
    authenticate(client, team.proponent)
    do_proponente = _detalhe(client, process_id)
    assert do_proponente['current_phase'] == da_patrocinadora['current_phase']
    pessoas = _pessoas(do_proponente)
    assert [p['user']['id'] for p in pessoas['sponsor']] == [
        str(team.sponsor.id)
    ]
    assert 'adhoc_evaluator' not in pessoas
    assert 'participating_laboratory' not in pessoas
    assert all(a['laboratory'] is None for a in open_runs_of(do_proponente))
    _cartao_igual_ao_detalhe(client, process_id, do_proponente)

    # 3. Lara abre o andamento: vê a própria equipe e o próprio recebimento,
    #    e nada do outro laboratório.
    lara, outro = team.lab_users[1], team.laboratories[0]
    authenticate(client, lara)
    da_lara = _detalhe(client, process_id)
    assert da_lara['current_phase'] == da_patrocinadora['current_phase']
    recebimentos = [
        a['laboratory']['id']
        for a in open_runs_of(da_lara)
        if a['key'] == 'sample_receipt'
    ]
    assert recebimentos == [str(team.laboratories[1].id)]
    assert outro.name not in str(da_lara)
    _cartao_igual_ao_detalhe(client, process_id, da_lara)
