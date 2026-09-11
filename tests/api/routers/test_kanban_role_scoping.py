"""Spec 018 - User Story 2: cargos globais x cargos por processo no Kanban.

Cobre os cenários de aceite da User Story 2 do spec.md: um mesmo usuário
`Padrão` com cargos diferentes em métodos diferentes, revogação de
atribuição, e duas pessoas no mesmo cargo contextual.
"""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import ProcessInstance
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import AssignmentFactory
from tests.factories.user_factory import UserFactory


async def _create_process(client, title):
    resp = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': title},
    )
    assert resp.status_code == HTTPStatus.CREATED
    return resp.json()['id']


def _submit_to_reach_triage(client, process_id):
    """Move o processo de `SUBMISSION` para `TRIAGE`.

    Necessário antes de testar visibilidade por cargo não-Proponente: a
    trava por proponente (Spec 009) restringe `SUBMISSION`/
    `AI_PRE_EVALUATION` só a quem tem `Assignment` de `proponent` —
    `Gestor`/outros cargos só passam a valer depois disso. Chamado como o
    próprio proponente (dono do processo) já autenticado.
    """
    resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Método de teste'}},
    )
    assert resp.status_code == HTTPStatus.OK, resp.json()


@pytest.mark.asyncio
async def test_padrao_user_sees_only_methods_with_active_role(client, session):
    await bootstrap_all_templates(session)
    owner_a = UserFactory()
    owner_b = UserFactory()
    owner_c = UserFactory()
    padrao = UserFactory()
    session.add_all([owner_a, owner_b, owner_c, padrao])
    await session.commit()

    authenticate(client, owner_a)
    process_a = await _create_process(client, 'Método A')
    authenticate(client, owner_b)
    process_b = await _create_process(client, 'Método B')
    # Gestor só passa a valer fora de SUBMISSION (trava por proponente).
    _submit_to_reach_triage(client, process_b)
    authenticate(client, owner_c)
    process_c = await _create_process(client, 'Método C')

    proc_a = await session.get(ProcessInstance, process_a)
    proc_b = await session.get(ProcessInstance, process_b)
    session.add(
        AssignmentFactory(process=proc_a, user=padrao, role_key='proponent')
    )
    session.add(
        AssignmentFactory(
            process=proc_b, user=padrao, role_key='group_manager'
        )
    )
    await session.commit()

    authenticate(client, padrao)
    resp = client.get('/activities/kanban', params={'size': 200})
    assert resp.status_code == HTTPStatus.OK
    process_ids_seen = {item['process']['id'] for item in resp.json()['items']}

    assert process_a in process_ids_seen
    assert process_b in process_ids_seen
    assert process_c not in process_ids_seen

    # `GET /auth/me` é a fonte de "qual cargo eu ocupo em cada processo"
    # (research.md achado A4) — confirma Proponente em A e Gestor em B,
    # cargos diferentes para o mesmo usuário em processos diferentes.
    me = client.get('/auth/me').json()
    roles_by_process = {
        scope['process_id']: scope['roles'] for scope in me['access']['scopes']
    }
    assert roles_by_process[process_a] == ['proponent']
    assert roles_by_process[process_b] == ['group_manager']


@pytest.mark.asyncio
async def test_revoked_assignment_removes_process_from_next_query(
    client, session
):
    await bootstrap_all_templates(session)
    owner = UserFactory()
    manager = UserFactory()
    session.add_all([owner, manager])
    await session.commit()

    authenticate(client, owner)
    process_id = await _create_process(client, 'Método com gestor revogado')
    _submit_to_reach_triage(client, process_id)

    process = await session.get(ProcessInstance, process_id)
    assignment = AssignmentFactory(
        process=process, user=manager, role_key='group_manager'
    )
    session.add(assignment)
    await session.commit()

    authenticate(client, manager)
    resp_before = client.get('/activities/kanban', params={'size': 200})
    ids_before = {i['process']['id'] for i in resp_before.json()['items']}
    assert process_id in ids_before

    assignment.revoked_at = datetime.now(UTC)
    await session.commit()

    resp_after = client.get('/activities/kanban', params={'size': 200})
    ids_after = {i['process']['id'] for i in resp_after.json()['items']}
    assert process_id not in ids_after


@pytest.mark.asyncio
async def test_two_people_in_same_role_both_see_the_pendency(client, session):
    await bootstrap_all_templates(session)
    owner = UserFactory()
    first_manager = UserFactory()
    second_manager = UserFactory()
    session.add_all([owner, first_manager, second_manager])
    await session.commit()

    authenticate(client, owner)
    process_id = await _create_process(client, 'Método com dois gestores')
    _submit_to_reach_triage(client, process_id)

    process = await session.get(ProcessInstance, process_id)
    session.add(
        AssignmentFactory(
            process=process, user=first_manager, role_key='group_manager'
        )
    )
    session.add(
        AssignmentFactory(
            process=process, user=second_manager, role_key='group_manager'
        )
    )
    await session.commit()

    for manager in (first_manager, second_manager):
        authenticate(client, manager)
        resp = client.get('/activities/kanban', params={'size': 200})
        ids_seen = {i['process']['id'] for i in resp.json()['items']}
        assert process_id in ids_seen


@pytest.mark.asyncio
async def test_cargo_unassigned_is_flagged_for_a_participant_manager(
    client, session
):
    """Ninguém tem o perfil global `bracvam` nesta base de teste — a

    pendência de triagem (cargo global `bracvam`) aparece sinalizada como
    sem ocupante para quem pode gerenciar atribuições naquele método, em
    vez de ficar "solta" (spec, Edge Cases; `resolve_activity_holders`
    vazio).
    """
    await bootstrap_all_templates(session)
    owner = UserFactory()
    manager = UserFactory()
    session.add_all([owner, manager])
    await session.commit()

    authenticate(client, owner)
    process_id = await _create_process(client, 'Método sem bracvam definido')
    _submit_to_reach_triage(client, process_id)

    process = await session.get(ProcessInstance, process_id)
    session.add(
        AssignmentFactory(
            process=process, user=manager, role_key='group_manager'
        )
    )
    await session.commit()

    authenticate(client, manager)
    resp = client.get('/activities/kanban', params={'process_id': process_id})
    assert resp.status_code == HTTPStatus.OK
    triage_item = next(
        i
        for i in resp.json()['items']
        if i['activity_key'] == 'triage_evaluation'
    )
    assert triage_item['cargo'] == 'bracvam'
    assert triage_item['cargo_unassigned'] is True

    # `owner` (o proponente) não pode gerenciar participantes deste
    # processo — a sinalização não aparece para ele.
    authenticate(client, owner)
    resp_owner = client.get(
        '/activities/kanban', params={'process_id': process_id}
    )
    triage_item_owner = next(
        i
        for i in resp_owner.json()['items']
        if i['activity_key'] == 'triage_evaluation'
    )
    assert triage_item_owner['cargo_unassigned'] is False
