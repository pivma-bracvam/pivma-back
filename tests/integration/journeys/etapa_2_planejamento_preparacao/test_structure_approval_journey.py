"""Jornadas da homologação da estrutura do estudo (Spec 042, issue #27).

Personas:

- Helena, do BraCVAM. Antes de liberar a Etapa 3, confere se a equipe está
  completa e se cada laboratório participante tem amostras. Não vê nome
  químico, CAS nem código cego.
- Marcos, do Grupo Gestor. Monta a equipe do estudo e corrige o que Helena
  reprovar.
- Ricardo, do Grupo de Seleção de Amostras. Define as amostras e as conclui
  de novo quando Helena reprova o ponto.
- Thiago, analista de um laboratório participante. Só começa o recebimento
  depois da aprovação.

Estado inicial comum: deploy novo com perfis, permissões, templates e
administrador canônicos. Os atores se cadastram pela API; o administrador
concede o perfil BraCVAM a Helena e cadastra instituições, laboratórios e
vínculos. O proponente submete o processo, Helena aprova a triagem e a
equipe designa os oito cargos pela API. Ricardo cadastra uma substância com
SDS. Cada troca de ator usa logout/login públicos.

Jornadas:

1. Helena confere a estrutura completa, aprova, e a Etapa 3 abre para os
   laboratórios (US1).
2. Helena reprova o ponto dos laboratórios; Marcos troca o laboratório,
   Ricardo refaz as amostras e Helena aprova na terceira execução (US2, o
   critério de conclusão da issue).
3. Helena só aprova a estrutura completa: a decisão é recusada antes da
   abertura e com pendência, e Marcos não decide (US3).

Os desvios de cada passo (cada erro, cada perfil, concorrência) ficam nos
testes focados de `tests/api/routers/test_structure_approval_*`.
"""

from http import HTTPStatus
from types import SimpleNamespace

import pytest

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from tests.factories.sample_factory import (
    VALID_CAS,
    substance_payload,
)
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    designate,
    ok,
    register_substance,
)

APPROVAL = 'structure_approval'
APPROVAL_TITLE = 'Homologação da Estrutura do Estudo'
SECRET_NAME = 'Substância secreta'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def _entrar(client, user):
    if client.cookies.get('access_token'):
        log_out(client)
    log_in(client, user.username)


def _administrador(client):
    if client.cookies.get('access_token'):
        log_out(client)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _laboratorio_com_analista(client, name):
    """O administrador cadastra laboratório e vínculo de um usuário novo."""
    user = SimpleNamespace(**sign_up(client, name))
    _administrador(client)
    institution = ok(
        client.post('/institutional/institutions', json={'name': name}),
        HTTPStatus.CREATED,
    )
    laboratory = SimpleNamespace(
        **ok(
            client.post(
                '/institutional/laboratories',
                json={'name': name, 'institution_id': institution['id']},
            ),
            HTTPStatus.CREATED,
        )
    )
    affiliation = ok(
        client.post(
            f'/institutional/users/{user.id}/affiliations',
            json={
                'institution_id': institution['id'],
                'laboratory_id': laboratory.id,
            },
        ),
        HTTPStatus.CREATED,
    )
    assert affiliation['active'] is True
    assert affiliation['laboratory']['id'] == laboratory.id
    return laboratory, user


async def _equipe_montada(session, client, monkeypatch):
    """Preparo comum pela API, após o bootstrap de um deploy novo."""
    await bootstrap_fresh_deploy(session, monkeypatch)
    team = SimpleNamespace(**{
        role: SimpleNamespace(**sign_up(client, name))
        for role, name in (
            ('proponent', 'proponente'),
            ('manager', 'marcos'),
            ('selector', 'ricardo'),
            ('sponsor', 'patrocinador'),
            ('statistician', 'estatistica'),
            ('collaborator', 'colaboradora'),
            ('adhoc', 'avaliadora'),
            ('helena', 'helena'),
        )
    })
    _administrador(client)
    granted = client.post(
        f'/rbac/users/{team.helena.id}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    pairs = [
        _laboratorio_com_analista(client, name) for name in ('thiago', 'lab2')
    ]
    team.laboratories = [lab for lab, _ in pairs]
    team.lab_users = [user for _, user in pairs]

    _entrar(client, team.proponent)
    team.process_id = ok(
        client.post(
            '/processes',
            json={
                'template_key': 'pre_validated_method',
                'title': 'Estudo cego de irritação ocular',
            },
        ),
        HTTPStatus.CREATED,
    )['id']
    assert (
        _tarefas(client, team.process_id, 'proposal_submission')[0]['status']
        == 'READY'
    )
    submitted = ok(
        client.post(
            f'/processes/{team.process_id}/activities/proposal_submission/form',
            json={'values': {'method_title': 'Ensaio RhCE'}},
        )
    )
    assert submitted['status'] == 'COMPLETED'
    _entrar(client, team.helena)
    assert (
        _tarefas(client, team.process_id, 'triage_evaluation')[0]['status']
        == 'READY'
    )
    triaged = ok(
        client.post(
            f'/processes/{team.process_id}/triage/decision',
            json={'outcome': 'APPROVED', 'justification': 'Aderente.'},
        )
    )
    assert triaged['outcome'] == 'APPROVED'
    _entrar(client, team.proponent)
    designate(client, team.process_id, team.manager, 'group_manager')
    designate(client, team.process_id, team.sponsor, 'sponsor')
    _entrar(client, team.manager)
    for user, role in (
        (team.selector, 'sample_selection_group'),
        (team.statistician, 'statistician'),
        (team.collaborator, 'collaborator'),
        (team.adhoc, 'adhoc_evaluator'),
    ):
        designate(client, team.process_id, user, role)
    for laboratory, user in pairs:
        designate(
            client,
            team.process_id,
            user,
            'participating_laboratory',
            laboratory,
        )
    designate(
        client,
        team.process_id,
        team.lab_users[0],
        'lead_laboratory',
        team.laboratories[0],
    )
    _entrar(client, team.selector)
    assert (
        _tarefas(client, team.process_id, 'sample_definition')[0]['status']
        == 'READY'
    )
    team.substance = register_substance(
        client,
        team.process_id,
        substance_payload(chemical_name=SECRET_NAME, cas_number=VALID_CAS[0]),
    )
    team.marcos = team.manager
    team.ricardo, team.thiago = team.selector, team.lab_users[0]
    return team


def _concluir_amostras(client, team):
    _entrar(client, team.ricardo)
    ok(
        client.post(
            f'/processes/{team.process_id}/samples/complete', headers=ORIGIN
        )
    )


def _tarefas(client, process_id, activity_key, **params):
    """Tarefas da atividade visíveis ao usuário, da execução mais antiga."""
    data = ok(
        client.get(
            '/tasks',
            params={
                'process_id': process_id,
                'activity_key': activity_key,
                'per_page': 100,
                **params,
            },
        )
    )['data']
    return sorted(data, key=lambda task: task['activity_run_number'])


def _painel(client, process_id):
    return ok(client.get(f'/processes/{process_id}/structure-approval'))


def _pontos(panel):
    return {point['activity_key']: point for point in panel['points']}


def _decidir(client, process_id, **body):
    return client.post(
        f'/processes/{process_id}/structure-approval/decision',
        json=body,
        headers=ORIGIN,
    )


def _eventos(client, process_id, event_type):
    data = ok(
        client.get(
            f'/processes/{process_id}/timeline', params={'per_page': 100}
        )
    )['data']
    return [event for event in data if event['event_type'] == event_type]


@pytest.mark.asyncio
async def test_bracvam_homologa_a_estrutura_e_libera_o_recebimento(
    journey_client, session, monkeypatch
):
    # 1. A equipe está montada e Ricardo conclui as amostras.
    client = journey_client
    team = await _equipe_montada(session, client, monkeypatch)
    _concluir_amostras(client, team)

    # 2. Helena vê a tarefa da homologação; Thiago ainda não tem recebimento.
    _entrar(client, team.helena)
    [task] = _tarefas(client, team.process_id, APPROVAL)
    assert task['title'] == APPROVAL_TITLE
    assert task['status'] == 'READY'
    _entrar(client, team.thiago)
    assert _tarefas(client, team.process_id, 'sample_receipt') == []

    # 3. Helena abre o painel: os nove pontos concluídos, sem pendência e
    #    só com as contagens das amostras.
    _entrar(client, team.helena)
    response = client.get(f'/processes/{team.process_id}/structure-approval')
    panel = ok(response)
    assert panel['status'] == 'IN_PROGRESS'
    assert len(panel['points']) == 9  # noqa: PLR2004
    assert {p['status'] for p in panel['points']} == {'COMPLETED'}
    assert all(p['pending'] == [] for p in panel['points'])
    assert _pontos(panel)['sample_definition']['samples'] == {
        'substance_count': 1,
        'laboratory_count': 2,
        'code_count': 2,
    }
    assert SECRET_NAME not in response.text
    assert VALID_CAS[0] not in response.text

    # 4. Helena aprova com justificativa.
    decision = ok(
        _decidir(
            client,
            team.process_id,
            outcome='APPROVED',
            justification='Equipe e amostras conferidas.',
        )
    )
    assert decision['status'] == 'COMPLETED'
    assert decision['reopened'] == []

    # 5. Thiago vê a tarefa de recebimento do próprio laboratório.
    _entrar(client, team.thiago)
    [receipt] = _tarefas(client, team.process_id, 'sample_receipt')
    assert receipt['status'] == 'READY'
    assert receipt['laboratory']['id'] == str(team.laboratories[0].id)

    # 6. A linha do tempo e o painel mostram a decisão de Helena.
    _entrar(client, team.helena)
    [event] = _eventos(client, team.process_id, 'STRUCTURE_APPROVED')
    assert event['user_id'] == str(team.helena.id)
    assert event['context_data']['justification'] == (
        'Equipe e amostras conferidas.'
    )
    [recorded] = _painel(client, team.process_id)['decisions']
    assert recorded['outcome'] == 'APPROVED'
    assert recorded['decided_by']['id'] == str(team.helena.id)


def _designacao(client, process_id, laboratory):
    """Designação ativa do laboratório participante, vista por Marcos."""
    data = ok(
        client.get(
            f'/processes/{process_id}/participants', params={'per_page': 100}
        )
    )['data']
    return next(
        item
        for item in data
        if item['role_key'] == 'participating_laboratory'
        and item['laboratory']['id'] == str(laboratory.id)
    )


@pytest.mark.asyncio
async def test_bracvam_reprova_o_laboratorio_e_a_estrutura_volta_para_correcao(  # noqa: PLR0914, PLR0915
    journey_client, session, monkeypatch
):
    labs = 'assign_participating_laboratory'
    # 1. A equipe está montada, as amostras concluídas e o painel aberto.
    client = journey_client
    team = await _equipe_montada(session, client, monkeypatch)
    _concluir_amostras(client, team)
    errado, errado_user = team.laboratories[1], team.lab_users[1]
    certo, certo_user = _laboratorio_com_analista(client, 'laboratorio_certo')

    # 2. Helena reprova o ponto dos laboratórios com o motivo.
    _entrar(client, team.helena)
    rejected = ok(
        _decidir(
            client,
            team.process_id,
            outcome='REJECTED',
            justification='Equipe incompleta.',
            rejected_points=[
                {'activity_key': labs, 'reason': 'Laboratório errado.'}
            ],
        )
    )
    assert rejected['status'] == 'BLOCKED'
    assert rejected['reopened'] == [{'activity_key': labs, 'run_number': 2}]

    # 3. Marcos vê a tarefa nova do ponto ao lado da concluída; Helena fica
    #    sem homologação a fazer e Thiago sem recebimento.
    _entrar(client, team.marcos)
    history = _tarefas(client, team.process_id, labs, current_run='false')
    assert [(t['activity_run_number'], t['status']) for t in history] == [
        (1, 'COMPLETED'),
        (2, 'READY'),
    ]
    _entrar(client, team.helena)
    assert _tarefas(client, team.process_id, APPROVAL, status='READY') == []
    _entrar(client, team.thiago)
    assert _tarefas(client, team.process_id, 'sample_receipt') == []

    # 4. A linha do tempo registra a reprovação e a reabertura com o motivo.
    _entrar(client, team.helena)
    [reprovacao] = _eventos(client, team.process_id, 'STRUCTURE_REJECTED')
    assert reprovacao['context_data']['rejected_points'] == [
        {'activity_key': labs, 'reason': 'Laboratório errado.'}
    ]
    [reabertura] = _eventos(client, team.process_id, 'ACTIVITY_REOPENED')
    assert reabertura['context_data']['reason'] == 'Laboratório errado.'

    # 5. Marcos revoga o laboratório errado e designa o certo: o ponto
    #    conclui e a homologação reabre para Helena.
    _entrar(client, team.marcos)
    wrong = _designacao(client, team.process_id, errado)
    revoked = client.delete(
        f'/processes/{team.process_id}/participants/{wrong["id"]}',
        headers=ORIGIN,
    )
    assert revoked.status_code == HTTPStatus.NO_CONTENT, revoked.text
    designate(
        client, team.process_id, certo_user, 'participating_laboratory', certo
    )
    _entrar(client, team.helena)
    [task] = _tarefas(client, team.process_id, APPROVAL, status='READY')
    assert task['activity_run_number'] == 2  # noqa: PLR2004

    # 6. O painel aponta as amostras fora da equipe nova, e a aprovação é
    #    recusada.
    pending = {
        (item['code'], item['laboratory']['id'])
        for item in _pontos(_painel(client, team.process_id))[
            'sample_definition'
        ]['pending']
    }
    assert pending == {
        ('laboratory_without_codes', str(certo.id)),
        ('codes_without_laboratory', str(errado.id)),
    }
    refused = _decidir(
        client, team.process_id, outcome='APPROVED', justification='Ok.'
    )
    assert refused.status_code == HTTPStatus.CONFLICT
    assert refused.json()['detail']['code'] == 'structure_pending'

    # 7. Helena reprova as amostras; Ricardo vê a tarefa e conclui de novo.
    ok(
        _decidir(
            client,
            team.process_id,
            outcome='REJECTED',
            justification='Amostras fora da equipe.',
            rejected_points=[
                {
                    'activity_key': 'sample_definition',
                    'reason': 'Gerar códigos para o laboratório novo.',
                }
            ],
        )
    )
    _entrar(client, team.ricardo)
    [samples_task] = _tarefas(client, team.process_id, 'sample_definition')
    assert (samples_task['activity_run_number'], samples_task['status']) == (
        2,
        'READY',
    )
    _concluir_amostras(client, team)

    # 8. Helena vê a homologação na execução 3, sem pendência, e aprova.
    _entrar(client, team.helena)
    panel = _painel(client, team.process_id)
    assert (panel['status'], panel['run_number']) == ('IN_PROGRESS', 3)
    assert all(point['pending'] == [] for point in panel['points'])
    ok(
        _decidir(
            client,
            team.process_id,
            outcome='APPROVED',
            justification='Equipe e amostras conferidas.',
        )
    )

    # 9. O laboratório certo vê o recebimento; o revogado não.
    _entrar(client, certo_user)
    [receipt] = _tarefas(client, team.process_id, 'sample_receipt')
    assert receipt['laboratory']['id'] == str(certo.id)
    _entrar(client, errado_user)
    assert _tarefas(client, team.process_id, 'sample_receipt') == []

    # 10. O painel mostra as três decisões, da mais recente para a mais
    #     antiga, com os pontos reprovados e os motivos.
    _entrar(client, team.helena)
    decisions = _painel(client, team.process_id)['decisions']
    assert [(d['run_number'], d['outcome']) for d in decisions] == [
        (3, 'APPROVED'),
        (2, 'REJECTED'),
        (1, 'REJECTED'),
    ]
    assert decisions[2]['rejected_points'] == [
        {'activity_key': labs, 'reason': 'Laboratório errado.'}
    ]


@pytest.mark.asyncio
async def test_bracvam_so_aprova_a_estrutura_completa(
    journey_client, session, monkeypatch
):
    client = journey_client
    team = await _equipe_montada(session, client, monkeypatch)
    terceiro, terceiro_user = _laboratorio_com_analista(client, 'terceiro_lab')

    # 1. Com as amostras ainda em definição, Helena não tem homologação a
    #    fazer e não consegue decidir.
    _entrar(client, team.helena)
    assert _tarefas(client, team.process_id, APPROVAL) == []
    early = _decidir(
        client, team.process_id, outcome='APPROVED', justification='Ok.'
    )
    assert early.status_code == HTTPStatus.CONFLICT
    assert early.json()['detail']['code'] == 'invalid_transition'

    # 2. Ricardo conclui as amostras e a tarefa aparece para Helena.
    _concluir_amostras(client, team)
    _entrar(client, team.helena)
    [task] = _tarefas(client, team.process_id, APPROVAL)
    assert task['status'] == 'READY'

    # 3. Marcos designa um terceiro laboratório, que fica sem amostras.
    _entrar(client, team.marcos)
    designate(
        client,
        team.process_id,
        terceiro_user,
        'participating_laboratory',
        terceiro,
    )
    _entrar(client, team.helena)
    pending = _pontos(_painel(client, team.process_id))['sample_definition'][
        'pending'
    ]
    assert [(p['code'], p['laboratory']['id']) for p in pending] == [
        ('laboratory_without_codes', str(terceiro.id))
    ]

    # 4. Helena tenta aprovar e é recusada; Thiago continua sem recebimento.
    refused = _decidir(
        client, team.process_id, outcome='APPROVED', justification='Ok.'
    )
    assert refused.status_code == HTTPStatus.CONFLICT
    assert refused.json()['detail']['code'] == 'structure_pending'
    _entrar(client, team.thiago)
    assert _tarefas(client, team.process_id, 'sample_receipt') == []

    # 5. Marcos tenta decidir e não encontra a homologação.
    _entrar(client, team.marcos)
    hidden = _decidir(
        client, team.process_id, outcome='APPROVED', justification='Ok.'
    )
    assert hidden.status_code == HTTPStatus.NOT_FOUND

    # 6. Helena reprova as amostras, Ricardo conclui de novo e Helena
    #    aprova: os três laboratórios veem o recebimento.
    _entrar(client, team.helena)
    ok(
        _decidir(
            client,
            team.process_id,
            outcome='REJECTED',
            justification='Falta o terceiro laboratório.',
            rejected_points=[
                {
                    'activity_key': 'sample_definition',
                    'reason': 'Gerar códigos para o terceiro laboratório.',
                }
            ],
        )
    )
    _concluir_amostras(client, team)
    _entrar(client, team.helena)
    ok(
        _decidir(
            client,
            team.process_id,
            outcome='APPROVED',
            justification='Equipe e amostras conferidas.',
        )
    )
    for laboratory, user in [
        *zip(team.laboratories, team.lab_users, strict=True),
        (terceiro, terceiro_user),
    ]:
        _entrar(client, user)
        [receipt] = _tarefas(client, team.process_id, 'sample_receipt')
        assert receipt['laboratory']['id'] == str(laboratory.id)
