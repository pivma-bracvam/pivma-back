"""Jornadas da Etapa 3: recebimento de amostras (Spec 040, US3 a US8).

Fonte: jornadas enviadas pelo usuário em 2026-10-04 ("Jornadas humanizadas
do usuário" e "Lista de Ações do Usuário"), issues #28 e #71.

Personas:

- Thiago, analista do laboratório participante. Está na bancada com a caixa
  térmica aberta, luvas e termômetro na mão. Quer conferir o material,
  registrar a chegada e começar o ensaio. Não pode ver nome químico, CAS,
  SDS nem nada de outro laboratório.
- Ricardo, do Grupo de Seleção de Amostras, guardião do cegamento. Precisa
  saber na hora se um frasco chegou comprometido para decidir o que fazer,
  sem revelar a identidade da substância.

Estado inicial comum: ambiente com os templates padrão; um processo do
template 1 percorrido pela API pública até a definição das amostras
concluída, com dois laboratórios e duas substâncias refrigeradas (2 °C a
8 °C), cada uma com um frasco de reserva. A Etapa 3 está aberta.

Jornadas:

1. O recebimento perfeito (Jornada 1; Lista de Ações 3).
2. O recebimento com desvio (Jornada 2; Lista de Ações 4).
3. A proteção contra falhas humanas (Jornada 3; Lista de Ações 2).
4. A perspectiva de retaguarda (Jornada 4; Lista de Ações 4). Ricardo vê o
   alerta pela tarefa "Resolver problemas no recebimento de amostras" e pela
   lista de inconformidades, que fazem o papel da central (decisão do usuário
   em 2026-10-04). O frasco reserva vai com código novo (issue #71,
   decisão 3), não com o mesmo código citado no texto original da jornada.
5. Privacidade e isolamento (Lista de Ações 1).

Os desvios de cada jornada (cada campo inválido, cada perfil negado,
concorrência) ficam nos testes focados de `tests/api/routers/test_sample_*`.
"""

import json
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import Notification
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import VALID_CAS, substance_payload
from tests.factories.sample_receipt_factory import receipt_payload
from tests.integration.journeys.sample_steps import (
    ORIGIN,
    my_tasks,
    ok,
    open_sample_definition,
    register_substance,
    study_team,
)

GABARITO = 'Não irritante'
PHOTO = b'\x89PNG\r\n\x1a\n frasco trincado'
HANDLING = 'Usar luvas nitrílicas e capela. Manter refrigerado.'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


async def _etapa_3_aberta(session, client, bracvam_user):
    """Estado inicial comum: Ricardo cadastrou e concluiu as amostras."""
    team = await study_team(session, lab_count=2)
    process_id = open_sample_definition(client, team, bracvam_user)
    authenticate(client, team.selector)
    team.substances = [
        register_substance(
            client,
            process_id,
            substance_payload(
                chemical_name=f'Substância secreta {index}',
                cas_number=VALID_CAS[index],
                reference_classification=GABARITO,
                safe_handling_instructions=HANDLING,
                storage_temperature_regime='refrigerated',
                reserve_vials_count=1,
            ),
        )
        for index in range(2)
    ]
    ok(
        client.post(
            f'/processes/{process_id}/samples/complete', headers=ORIGIN
        )
    )
    team.process_id = process_id
    team.thiago, team.ricardo = team.lab_users[0], team.selector
    return team


def _codigos(team, index):
    """Códigos dos frascos que o laboratório `index` recebeu na caixa."""
    laboratory_id = str(team.laboratories[index].id)
    return sorted(
        code['code']
        for substance in team.substances
        for code in substance['blind_codes']
        if code['laboratory_id'] == laboratory_id
    )


def _frascos(client, process_id, **params):
    return ok(
        client.get(
            f'/processes/{process_id}/sample-receipt/vials', params=params
        )
    )['data']


def _pre_verificar(client, process_id, code, **overrides):
    return client.post(
        f'/processes/{process_id}/sample-receipt/vials/{code}/check',
        json=receipt_payload(**overrides),
        headers=ORIGIN,
    )


def _registrar(client, process_id, code, **overrides):
    return client.post(
        f'/processes/{process_id}/sample-receipt/vials/{code}',
        json=receipt_payload(**overrides),
        headers=ORIGIN,
    )


def _inconformidades(client, process_id):
    return ok(
        client.get(f'/processes/{process_id}/sample-receipt/nonconformities')
    )['data']


def _sem_identidade(blob, team):
    text = json.dumps(blob, ensure_ascii=False)
    for substance in team.substances:
        assert substance['chemical_name'] not in text
        assert substance['cas_number'] not in text
    assert GABARITO not in text
    for key in ('chemical_name', 'cas_number', 'reference_classification'):
        assert f'"{key}"' not in text


@pytest.mark.asyncio
async def test_jornada_1_recebimento_perfeito(session, client, bracvam_user):
    """Thiago recebe a remessa em condições ideais e registra a custódia.

    Passos:

    1. Thiago entra e encontra a tarefa "Confirmação de Recebimento de
       Amostras" pronta. Espera ver: tarefa `READY`.
    2. Abre a lista de frascos. Espera ver: só os frascos do próprio
       laboratório, com instruções de manuseio e temperatura de estocagem.
       Não deve ver: nome comercial, CAS, SDS ou frascos de outro laboratório.
    3. Confirma o código bipando o QR do frasco. Espera ver: o mesmo código,
       o manuseio e a faixa de 2 °C a 8 °C.
    4. Informa data e hora de abertura, 4,5 °C, embalagem íntegra e a
       observação, e confere antes de enviar. Espera ver: condições dentro
       do padrão.
    5. Confirma o recebimento de cada frasco. Espera ver: no último, a
       mensagem de que o lote está na cadeia de custódia e liberado para os
       ensaios, sem alerta.

    Desfecho: a tarefa de Thiago conclui; a do outro laboratório continua
    pronta; Ricardo não recebe alerta nenhum.
    """
    team = await _etapa_3_aberta(session, client, bracvam_user)
    process_id = team.process_id
    caixa = _codigos(team, 0)

    # 1. Thiago encontra a tarefa de recebimento.
    authenticate(client, team.thiago)
    tarefa = my_tasks(client, process_id)['sample_receipt']
    assert tarefa['status'] == 'READY'
    assert tarefa['title'] == 'Confirmação de Recebimento de Amostras'

    # 2. A lista traz só os frascos dele, com manuseio e faixa.
    frascos = _frascos(client, process_id)
    assert [f['code'] for f in frascos] == caixa
    for frasco in frascos:
        assert frasco['status'] == 'pending'
        assert frasco['laboratory']['id'] == str(team.laboratories[0].id)
        assert frasco['safe_handling_instructions'] == HANDLING
        assert frasco['storage_temperature_min'] == 2.0  # noqa: PLR2004
        assert frasco['storage_temperature_max'] == 8.0  # noqa: PLR2004
    _sem_identidade(frascos, team)

    # 3. Bipa o QR do primeiro frasco.
    qr = ok(client.get(f'/processes/{process_id}/samples/vials/{caixa[0]}'))
    assert qr['code'] == caixa[0]
    assert qr['safe_handling_instructions'] == HANDLING
    _sem_identidade(qr, team)

    # 4. Preenche e confere antes de enviar.
    conferencia = ok(_pre_verificar(client, process_id, caixa[0]))
    assert conferencia['conforming'] is True
    assert conferencia['deviations'] == []

    # 5. Confirma os dois frascos; o segundo fecha o lote.
    primeiro = ok(_registrar(client, process_id, caixa[0]), HTTPStatus.CREATED)
    assert primeiro['vial']['status'] == 'received'
    assert primeiro['laboratory_receipt_status'] == 'in_progress'
    ultimo = ok(_registrar(client, process_id, caixa[1]), HTTPStatus.CREATED)
    assert ultimo['conforming'] is True
    assert ultimo['laboratory_receipt_status'] == 'completed'
    assert 'cadeia de custódia' in ultimo['message']
    assert 'liberado para os ensaios' in ultimo['message']

    # Desfecho: tarefa concluída; o outro laboratório segue; sem alerta.
    concluida = my_tasks(client, process_id)['sample_receipt']
    assert concluida['status'] == 'COMPLETED'
    authenticate(client, team.lab_users[1])
    assert my_tasks(client, process_id)['sample_receipt']['status'] == 'READY'
    authenticate(client, team.ricardo)
    assert 'sample_receipt_resolution' not in my_tasks(client, process_id)
    assert _inconformidades(client, process_id) == []


@pytest.mark.asyncio
async def test_jornada_2_recebimento_com_desvio(session, client, bracvam_user):
    """O frasco sofreu no transporte e Thiago registra o problema.

    Passos:

    1. Thiago abre a caixa: o gelo derreteu e o termômetro marca 21 °C. Lê
       o QR do frasco. Espera ver: a faixa pedida, de 2 °C a 8 °C.
    2. Informa data e hora, 21 °C, embalagem íntegra e a observação sobre o
       gelo fundido, e confere antes de finalizar. Espera ver: aviso de
       condição fora do padrão, de que uma inconformidade será registrada e
       de que a equipe responsável será avisada.
    3. Confirma o registro. Espera ver: sucesso, não erro, com a orientação
       de manter o material segregado até as instruções.
    4. Fotografa o frasco e anexa a foto ao registro. Espera ver: a foto no
       frasco.
    5. Volta à lista. Espera ver: o frasco aguardando decisão e a tarefa de
       recebimento ainda aberta: ele não segue para o ensaio com o lote
       incompleto.

    Desfecho: o registro fica salvo e Ricardo é avisado (Jornada 4).
    """
    team = await _etapa_3_aberta(session, client, bracvam_user)
    process_id = team.process_id
    frasco = _codigos(team, 0)[0]
    nota = 'Gelo totalmente fundido, temperatura ambiente atingida no frete.'
    authenticate(client, team.thiago)

    # 1. Lê o QR: a faixa pedida é de 2 °C a 8 °C.
    qr = ok(client.get(f'/processes/{process_id}/samples/vials/{frasco}'))
    assert (qr['storage_temperature_min'], qr['storage_temperature_max']) == (
        2.0,
        8.0,
    )

    # 2. Confere antes de finalizar: o sistema avisa do desvio.
    aviso = ok(
        _pre_verificar(
            client, process_id, frasco, temperature_celsius=21.0, notes=nota
        )
    )
    assert aviso['conforming'] is False
    assert aviso['deviations'] == ['temperature_out_of_range']
    assert 'fora do padrão' in aviso['message']
    assert 'inconformidade será registrada' in aviso['message']
    assert 'equipe responsável' in aviso['message']

    # 3. Confirma: sucesso, com a orientação de segregar o material.
    registro = ok(
        _registrar(
            client, process_id, frasco, temperature_celsius=21.0, notes=nota
        ),
        HTTPStatus.CREATED,
    )
    assert registro['conforming'] is False
    assert registro['laboratory_receipt_status'] == 'awaiting_decision'
    assert 'foi notificada' in registro['message']
    assert 'segregado' in registro['message']
    _sem_identidade(registro, team)

    # 4. Anexa a foto do frasco.
    foto = ok(
        client.post(
            f'/processes/{process_id}/sample-receipt/vials/{frasco}/photos',
            files={'file': ('frasco.png', PHOTO, 'image/png')},
            headers=ORIGIN,
        ),
        HTTPStatus.CREATED,
    )

    # 5. O frasco aguarda decisão e o recebimento continua aberto.
    na_lista = {f['code']: f for f in _frascos(client, process_id)}[frasco]
    assert na_lista['status'] == 'awaiting_decision'
    assert na_lista['receipt']['notes'] == nota
    assert [p['id'] for p in na_lista['photos']] == [foto['id']]
    assert my_tasks(client, process_id)['sample_receipt']['status'] == 'READY'


@pytest.mark.asyncio
async def test_jornada_3_protecao_contra_falhas_humanas(
    session, client, bracvam_user
):
    """Na correria, Thiago esquece campos e digita um valor inválido.

    Passos:

    1. Thiago preenche só o código e tenta concluir. Espera ver: envio
       bloqueado, com a temperatura e o estado da embalagem apontados.
    2. Digita letras na temperatura. Espera ver: envio bloqueado, com a
       temperatura apontada.
    3. Não seleciona o estado da embalagem. Espera ver: envio bloqueado,
       com o estado da embalagem apontado.
    4. Confere a lista. Espera ver: o frasco continua pendente, nada foi
       gravado.
    5. Preenche tudo corretamente. Espera ver: a conferência aceita os dados
       (o salvar fica liberado) e o registro é salvo.
    """
    team = await _etapa_3_aberta(session, client, bracvam_user)
    process_id = team.process_id
    frasco = _codigos(team, 0)[0]
    url = f'/processes/{process_id}/sample-receipt/vials/{frasco}'
    authenticate(client, team.thiago)

    def campos(response):
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        return {f['field'] for f in response.json()['detail']['fields']}

    # 1. Só o código: temperatura e embalagem faltam.
    so_data = {'opened_at': receipt_payload()['opened_at']}
    resposta = client.post(url, json=so_data, headers=ORIGIN)
    assert campos(resposta) == {'temperature_celsius', 'package_state'}

    # 2. Letras na temperatura.
    resposta = _registrar(
        client, process_id, frasco, temperature_celsius='4,5C'
    )
    assert campos(resposta) == {'temperature_celsius'}

    # 3. Sem o estado da embalagem.
    sem_estado = receipt_payload()
    del sem_estado['package_state']
    resposta = client.post(url, json=sem_estado, headers=ORIGIN)
    assert campos(resposta) == {'package_state'}

    # 4. Nada foi gravado.
    assert _frascos(client, process_id)[0]['status'] == 'pending'

    # 5. Corrige: a conferência aceita e o registro é salvo.
    assert ok(_pre_verificar(client, process_id, frasco))['conforming']
    ok(_registrar(client, process_id, frasco), HTTPStatus.CREATED)
    estados = {f['code']: f['status'] for f in _frascos(client, process_id)}
    assert estados[frasco] == 'received'


@pytest.mark.asyncio
async def test_jornada_4_retaguarda_do_grupo_de_selecao(  # noqa: PLR0914
    session, client, bracvam_user, email_invite_settings
):
    """Ricardo recebe o alerta e mantém a validação nos trilhos.

    Estado inicial: além do comum, Thiago registrou um frasco em ordem e o
    outro a 21 °C, com observação e foto (Jornada 2).

    Passos:

    1. Ricardo entra. Espera ver: a tarefa "Resolver problemas no
       recebimento de amostras" pronta e um e-mail na fila.
    2. Abre as inconformidades. Espera ver: "Alerta de Recebimento: o
       laboratório ... registrou desvio térmico no frasco ...", com data e
       hora, 21 °C, a faixa esperada, a observação e a foto de Thiago.
    3. Abre a foto. Espera ver: a imagem enviada.
    4. Decide enviar um frasco reserva, com justificativa. Espera ver: o
       código novo, a reserva zerada, a etiqueta nova para imprimir e a
       tarefa concluída.
    5. Thiago recebe a caixa nova. Espera ver: o frasco antigo substituído e
       um frasco pendente com outro código, sem nada que ligue um ao outro.
       Registra em ordem. Espera ver: o lote completo e liberado.

    Desfecho: o cronograma segue sem que ninguém fora do Grupo de Seleção
    saiba qual substância estava no frasco.
    """
    team = await _etapa_3_aberta(session, client, bracvam_user)
    process_id = team.process_id
    bom, quente = _codigos(team, 0)
    nota = 'Gelo totalmente fundido durante o frete.'

    # Estado inicial: Thiago registrou um frasco em ordem e o quente.
    authenticate(client, team.thiago)
    ok(_registrar(client, process_id, bom), HTTPStatus.CREATED)
    ok(
        _registrar(
            client, process_id, quente, temperature_celsius=21.0, notes=nota
        ),
        HTTPStatus.CREATED,
    )
    foto = ok(
        client.post(
            f'/processes/{process_id}/sample-receipt/vials/{quente}/photos',
            files={'file': ('frasco.png', PHOTO, 'image/png')},
            headers=ORIGIN,
        ),
        HTTPStatus.CREATED,
    )

    # 1. Ricardo vê a tarefa pronta. O e-mail não aparece pela API; a
    #    consulta direta confere que ele foi para a fila.
    authenticate(client, team.ricardo)
    tarefa = my_tasks(client, process_id)['sample_receipt_resolution']
    assert tarefa['status'] == 'READY'
    assert tarefa['title'] == 'Resolver problemas no recebimento de amostras'
    email = await session.scalar(
        select(Notification).where(
            Notification.subject_type == 'sample_receipt_nonconformity'
        )
    )
    assert email.recipient == team.ricardo.email

    # 2. O alerta traz os dados exatos informados por Thiago.
    [alerta] = _inconformidades(client, process_id)
    laboratorio = team.laboratories[0].name
    assert alerta['alert'] == (
        f'Alerta de Recebimento: o laboratório {laboratorio} registrou '
        f'desvio térmico no frasco {quente}.'
    )
    assert alerta['receipt']['temperature_celsius'] == 21.0  # noqa: PLR2004
    assert alerta['receipt']['opened_at']
    assert alerta['receipt']['notes'] == nota
    assert alerta['expected_temperature'] == {
        'regime': 'refrigerated',
        'min': 2.0,
        'max': 8.0,
    }

    # 3. Abre a foto.
    assert [p['id'] for p in alerta['photos']] == [foto['id']]
    imagem = client.get(
        f'/processes/{process_id}/sample-receipt/photos/{foto["id"]}'
    )
    assert imagem.content == PHOTO

    # 4. Envia um frasco reserva.
    decidido = ok(
        client.post(
            f'/processes/{process_id}/sample-receipt/nonconformities/'
            f'{alerta["id"]}/decision',
            json={
                'decision': 'resend',
                'justification': 'Frasco reserva despachado.',
            },
            headers=ORIGIN,
        )
    )
    novo = decidido['replacement_code']
    assert novo not in {None, quente}
    assert decidido['substance']['reserve_vials_count'] == 0
    etiquetas = ok(client.get(f'/processes/{process_id}/samples/labels'))
    assert novo in {e['code'] for e in etiquetas['data']}
    assert (
        my_tasks(client, process_id)['sample_receipt_resolution']['status']
        == 'COMPLETED'
    )

    # 5. Thiago recebe o frasco novo e fecha o lote.
    authenticate(client, team.thiago)
    frascos = {f['code']: f for f in _frascos(client, process_id)}
    assert frascos[quente]['status'] == 'replaced'
    assert frascos[novo]['status'] == 'pending'
    texto = json.dumps(list(frascos.values()))
    for vinculo in ('replacement', 'justification', 'despachado'):
        assert vinculo not in texto
    fim = ok(_registrar(client, process_id, novo), HTTPStatus.CREATED)
    assert fim['laboratory_receipt_status'] == 'completed'


@pytest.mark.asyncio
async def test_privacidade_e_isolamento_do_laboratorio(
    session, client, bracvam_user
):
    """Thiago só alcança os próprios frascos (Lista de Ações 1).

    Passos:

    1. Thiago entra na Etapa 3. Espera ver: só os códigos do próprio
       laboratório.
    2. Inspeciona os detalhes do frasco. Espera ver: manuseio, faixa e
       pictogramas. Não deve ver: nome químico, CAS, fornecedor ou SDS.
    3. Busca o código de um frasco do outro laboratório. Espera ver: nenhum
       resultado.
    4. Tenta abri-lo e registrá-lo pelo código. Espera ver: "não encontrado".
    5. Busca um trecho do próprio código. Espera ver: o próprio frasco.

    Desfecho: o outro laboratório continua com os frascos pendentes.
    """
    team = await _etapa_3_aberta(session, client, bracvam_user)
    process_id = team.process_id
    meus, alheio = _codigos(team, 0), _codigos(team, 1)[0]
    authenticate(client, team.thiago)

    # 1. Só os códigos dele.
    frascos = _frascos(client, process_id)
    assert [f['code'] for f in frascos] == meus

    # 2. Detalhes sem identidade química.
    detalhe = ok(
        client.get(f'/processes/{process_id}/samples/vials/{meus[0]}')
    )
    _sem_identidade([frascos, detalhe], team)
    assert '"sds"' not in json.dumps(detalhe)

    # 3. A busca pelo código alheio não acha nada.
    assert _frascos(client, process_id, search=alheio) == []

    # 4. Pelo código, o frasco alheio não existe.
    vial = client.get(f'/processes/{process_id}/samples/vials/{alheio}')
    assert vial.status_code == HTTPStatus.NOT_FOUND
    registro = _registrar(client, process_id, alheio)
    assert registro.status_code == HTTPStatus.NOT_FOUND

    # 5. A busca por um trecho do próprio código acha o frasco.
    achados = _frascos(client, process_id, search=meus[0][:4].lower())
    assert meus[0] in {f['code'] for f in achados}

    # Desfecho: o outro laboratório não foi tocado.
    authenticate(client, team.lab_users[1])
    assert {f['status'] for f in _frascos(client, process_id)} == {'pending'}
