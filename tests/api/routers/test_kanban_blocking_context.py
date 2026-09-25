"""Spec 018 - User Story 3: contexto de ordem no Kanban.

Cobre `blocking_activity_status`/`blocking_activity_cargo` (predecessor
completo, não só a chave) e `actionable_now` (distingue "minha vez" de
"vez de outro cargo").
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.rbac_factory import (
    AccessProfileFactory,
    UserAccessProfileFactory,
)
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_blocked_item_exposes_predecessor_status_and_cargo(
    client, session
):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)

    resp = client.post(
        '/processes',
        json={
            'template_key': 'validated_method_dossier',
            'title': 'Contexto de bloqueio',
        },
    )
    process_id = resp.json()['id']

    # `proposal_submission` ainda EM_ANDAMENTO: eu (proponente) sou a vez.
    kanban = client.get(
        '/activities/kanban', params={'process_id': process_id}
    ).json()
    by_key = {i['activity_key']: i for i in kanban['items']}
    assert by_key['proposal_submission']['actionable_now'] is True
    assert by_key['proposal_submission']['column'] == 'EM_ANDAMENTO'

    assign_sponsor = by_key['assign_sponsor']
    assert assign_sponsor['column'] == 'NAO_INICIADO'
    assert assign_sponsor['blocking_activity_key'] == 'triage_evaluation'
    assert assign_sponsor['blocking_activity_status'] == 'BLOCKED'
    assert assign_sponsor['blocking_activity_cargo'] == 'bracvam'

    # Submeter a proposta libera a triagem: o predecessor muda de status.
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Método com contexto de bloqueio',
                'terminology_notes': (
                    'Conceito descrito com nomenclatura atual e '
                    'detalhamento suficiente para avaliação.'
                ),
            }
        },
    )
    kanban_after = client.get(
        '/activities/kanban', params={'process_id': process_id}
    ).json()
    by_key_after = {i['activity_key']: i for i in kanban_after['items']}
    assert by_key_after['assign_sponsor']['blocking_activity_status'] in {
        'READY',
        'IN_PROGRESS',
    }
    # `proposal_submission` está concluída: já não é mais "minha vez".
    assert by_key_after['proposal_submission']['column'] == 'CONCLUIDO'
    assert by_key_after['proposal_submission']['actionable_now'] is False


@pytest.mark.asyncio
async def test_actionable_now_distinguishes_cargo_holder_from_others(
    client, session
):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    bracvam_user = UserFactory()
    profile = AccessProfileFactory(system_key='bracvam')
    session.add_all([proponent, bracvam_user, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=bracvam_user, profile=profile))
    await session.commit()

    authenticate(client, proponent)
    resp = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Acionável agora',
        },
    )
    process_id = resp.json()['id']
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Método de teste'}},
    )

    # O proponente não ocupa o cargo `bracvam` da triagem.
    resp_proponent = client.get(
        '/activities/kanban', params={'process_id': process_id}
    )
    triage_for_proponent = next(
        i
        for i in resp_proponent.json()['items']
        if i['activity_key'] == 'triage_evaluation'
    )
    assert triage_for_proponent['actionable_now'] is False

    # A pessoa com o perfil global BraCVAM, sim.
    authenticate(client, bracvam_user)
    resp_bracvam = client.get(
        '/activities/kanban', params={'process_id': process_id}
    )
    assert resp_bracvam.status_code == HTTPStatus.OK
    triage_for_bracvam = next(
        i
        for i in resp_bracvam.json()['items']
        if i['activity_key'] == 'triage_evaluation'
    )
    assert triage_for_bracvam['actionable_now'] is True
