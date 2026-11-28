"""Jornada: os convites ficam com quem gerencia participantes (Spec 049, US3).

O BraCVAM convida um avaliador ad hoc e uma analista de laboratório. A
analista aceita e vê o próprio aceite. O proponente não vê nenhum convite
nem o e-mail dos convidados. O BraCVAM vê todos, com e-mail e autor.
"""

from http import HTTPStatus
from types import SimpleNamespace

import pytest

from tests.factories.submission_factory import submission_values
from tests.integration.journeys.conftest import (
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    make_bracvam,
    sign_up,
)
from tests.integration.journeys.etapa_2_planejamento_preparacao.test_structure_approval_journey import (  # noqa: E501
    _laboratorio_com_analista,  # noqa: PLC2701
)
from tests.integration.journeys.sample_steps import designate, ok

ADHOC_EMAIL = 'especialista@exemplo.org'


def _timeline(client, process_id):
    response = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response


def _of_type(response, event_type):
    return [
        e for e in response.json()['data'] if e['event_type'] == event_type
    ]


@pytest.mark.asyncio
async def test_proponente_nao_ve_convites_e_analista_ve_o_proprio_aceite(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    make_bracvam(client, 'helena')
    gestor = SimpleNamespace(**sign_up(client, 'marcos'))
    laboratory, analista = _laboratorio_com_analista(client, 'thiago')
    log_out(client)

    # 1. O proponente envia e o BraCVAM aprova a triagem.
    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    process_id = ok(
        client.post(
            '/processes',
            json={'template_key': 'pre_validated_method', 'title': 'Método'},
        ),
        HTTPStatus.CREATED,
    )['id']
    ok(
        client.post(
            f'/processes/{process_id}/activities/proposal_submission/form',
            json={'values': submission_values('Ensaio RhCE')},
        )
    )
    log_out(client)
    log_in(client, 'helena')
    ok(
        client.post(
            f'/processes/{process_id}/triage/decision',
            json={'outcome': 'APPROVED', 'justification': 'Completa.'},
        )
    )

    # 2. O BraCVAM designa o Grupo Gestor e convida o especialista e a
    # analista do laboratório.
    designate(client, process_id, gestor, 'group_manager')
    invites = f'/processes/{process_id}/participants/invites'
    ok(
        client.post(
            invites, json={'email': ADHOC_EMAIL, 'role_key': 'adhoc_evaluator'}
        ),
        HTTPStatus.CREATED,
    )
    token = ok(
        client.post(
            invites,
            json={
                'email': analista.email,
                'role_key': 'participating_laboratory',
                'laboratory_id': laboratory.id,
            },
        ),
        HTTPStatus.CREATED,
    )['token']
    log_out(client)

    # 3. A analista aceita e vê o próprio aceite.
    log_in(client, analista.username)
    ok(client.post(f'/invites/{token}/accept'))
    [accepted] = _of_type(_timeline(client, process_id), 'INVITE_ACCEPTED')
    assert accepted['user_id'] == analista.id
    log_out(client)

    # 4. O proponente não vê nenhum convite nem o e-mail dos convidados.
    log_in(client, 'proponente')
    response = _timeline(client, process_id)
    assert not {
        e['event_type']
        for e in response.json()['data']
        if e['event_type'].startswith('INVITE_')
    }
    assert ADHOC_EMAIL not in response.text
    assert analista.email not in response.text
    log_out(client)

    # 5. O BraCVAM vê os convites, com e-mail e autor.
    log_in(client, 'helena')
    response = _timeline(client, process_id)
    created = _of_type(response, 'INVITE_CREATED')
    assert {e['context_data']['email'] for e in created} == {
        ADHOC_EMAIL,
        analista.email,
    }
    assert all(e['user_id'] is not None for e in created)
    [accepted] = _of_type(response, 'INVITE_ACCEPTED')
    assert accepted['user_id'] == analista.id
