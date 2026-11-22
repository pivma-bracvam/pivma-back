"""Jornada: laboratórios e Grupo Gestor acompanham a Etapa 3 pela caixa de
alerts (Spec 047, US5).

Atores: Thiago (laboratório A), a analista do laboratório B, Ricardo (Grupo
de Seleção de Amostras) e o Grupo Gestor. Objetivo: cada um saber o que
aconteceu com a sua parte, sem ver nada da parte do outro laboratório nem
a identidade das substâncias. Parte do mesmo estado inicial das jornadas
de recebimento (`test_sample_receipt_journey.py`).
"""

import json
from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.integration.journeys.etapa_3_execucao_validacao.test_sample_receipt_journey import (  # noqa: E501
    _codigos,  # noqa: PLC2701
    _etapa_3_aberta,  # noqa: PLC2701
    _inconformidades,  # noqa: PLC2701
    _registrar,  # noqa: PLC2701
    _sem_identidade,  # noqa: PLC2701
)
from tests.integration.journeys.sample_steps import ORIGIN, ok

PHASE = 'phase_3_validation_execution'


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


def _alerts_of(client, user, kind=None):
    authenticate(client, user)
    response = client.get('/alerts')
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()['data']
    return [a for a in data if kind is None or a['kind'] == kind]


@pytest.mark.asyncio
async def test_laboratorios_e_gestor_acompanham_a_etapa_3(
    session, client, bracvam_user
):
    team = await _etapa_3_aberta(session, client, bracvam_user)
    lab_a, lab_b = team.lab_users
    pid = team.process_id

    # 1. Thiago, do laboratório A, registra o primeiro frasco avariado.
    authenticate(client, lab_a)
    first, *others = _codigos(team, 0)
    ok(_registrar(client, pid, first, package_state='damaged'), 201)
    for code in others:
        ok(_registrar(client, pid, code), 201)

    # 2. Ricardo aceita o frasco com ressalva, e Thiago vê a decisão no
    #    alert, com o código cego e a situação, sem a orientação nem a
    #    justificativa.
    authenticate(client, team.ricardo)
    [item] = _inconformidades(client, pid)
    ok(
        client.post(
            f'/processes/{pid}/sample-receipt/nonconformities/'
            f'{item["id"]}/decision',
            json={
                'decision': 'accept_with_caveat',
                'justification': 'Lacre rompido.',
                'lab_guidance': 'Use com cautela.',
            },
            headers=ORIGIN,
        )
    )
    [decided] = _alerts_of(client, lab_a, 'sample_nonconformity_decided')
    assert decided['params']['blind_code'] == first
    assert decided['params']['vial_status'] == 'accepted_with_caveat'
    assert decided['target']['type'] == 'sample_receipt'
    assert 'Lacre rompido' not in json.dumps(decided)
    assert 'Use com cautela' not in json.dumps(decided)

    # 3. Com o aceite, o lote de A fecha. O laboratório B recebe tudo em
    #    ordem e também conclui. O Grupo Gestor vê uma conclusão por
    #    laboratório, com o nome de cada um.
    authenticate(client, lab_b)
    for code in _codigos(team, 1):
        ok(_registrar(client, pid, code), 201)
    completed = _alerts_of(client, team.manager, 'laboratory_run_completed')
    assert sorted(a['params']['laboratory_name'] for a in completed) == sorted(
        lab.name for lab in team.laboratories
    )

    # 4. O Grupo Gestor dispensa o laboratório A, e só os designados de A
    #    veem a dispensa.
    authenticate(client, team.manager)
    waived = client.post(
        f'/processes/{pid}/phases/{PHASE}/laboratory-waivers',
        json={
            'laboratory_id': str(team.laboratories[0].id),
            'reason': 'Equipamento quebrado.',
        },
        headers=ORIGIN,
    )
    assert waived.status_code == HTTPStatus.CREATED, waived.text
    [waiver] = _alerts_of(client, lab_a, 'laboratory_run_waived')
    assert waiver['params']['laboratory_name'] == team.laboratories[0].name
    assert _alerts_of(client, lab_b, 'laboratory_run_waived') == []

    # 5. Nenhum alert de um laboratório fala do outro nem revela a
    #    identidade das substâncias.
    for own, other in ((lab_a, 1), (lab_b, 0)):
        alerts = _alerts_of(client, own)
        assert team.laboratories[other].name not in json.dumps(alerts)
        _sem_identidade(alerts, team)
