# ruff: noqa: PLR2004

"""Spec 028 — gestão de convite (criar, listar, reenviar, revogar).

Reaproveita os fixtures de processo já usados pelos testes de participantes
(Spec 006), inclusive `_process_in_planning_phase` (processo real na Fase 2
via API, Spec 017/028).
"""

from datetime import datetime
from http import HTTPStatus

import pytest

from tests.api.routers.test_participant_router import (
    ORIGIN,
    _process_in_planning_phase,
    authenticate,
    create_process,
    grant_participants_management,
)
from tests.factories.user_factory import UserFactory


def create_invite(  # noqa: PLR0913, PLR0917
    client, process_id, email, role_key, laboratory_id=None, channel=None
):
    payload = {'email': email, 'role_key': role_key}
    if laboratory_id is not None:
        payload['laboratory_id'] = str(laboratory_id)
    if channel is not None:
        payload['channel'] = channel
    return client.post(
        f'/processes/{process_id}/participants/invites',
        headers=ORIGIN,
        json=payload,
    )


def list_invites(client, process_id):
    return client.get(f'/processes/{process_id}/participants/invites')


def resend_invite_req(client, process_id, invite_id):
    return client.post(
        f'/processes/{process_id}/participants/invites/{invite_id}/resend',
        headers=ORIGIN,
    )


def revoke_invite_req(client, process_id, invite_id):
    return client.post(
        f'/processes/{process_id}/participants/invites/{invite_id}/revoke',
        headers=ORIGIN,
    )


# --- U-I: já cobertos em tests/unit/schemas/test_invite_schemas.py ---
# --- A-I: criação/listagem ---


@pytest.mark.asyncio
async def test_authorized_person_creates_invite_and_receives_token(
    client, session, bracvam_user
):
    """A-I01: cria convite e recebe 201 com token bruto só nesta resposta."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)

    resp = create_invite(
        client, process_id, 'patrocinador@exemplo.org', 'sponsor'
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert 'token' in body
    assert len(body['token']) >= 32
    assert body['status'] == 'pending'
    assert body['email'] == 'patrocinador@exemplo.org'

    list_resp = list_invites(client, process_id)
    for item in list_resp.json():
        assert 'token' not in item


@pytest.mark.asyncio
async def test_unauthorized_person_denied_creating_invite(
    client, session, bracvam_user
):
    """A-I02: sem autorização para o papel, 403 ao criar."""
    process_id, _proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    stranger = UserFactory()
    session.add(stranger)
    await session.commit()
    authenticate(client, stranger)

    resp = create_invite(client, process_id, 'x@exemplo.org', 'statistician')
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_second_pending_invite_same_target_is_rejected(
    client, session, bracvam_user
):
    """A-I03: segundo convite pendente para (processo, papel, e-mail) → 409."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)

    first = create_invite(client, process_id, 'dup@exemplo.org', 'sponsor')
    assert first.status_code == HTTPStatus.CREATED
    second = create_invite(client, process_id, 'dup@exemplo.org', 'sponsor')
    assert second.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_laboratory_role_invite_without_laboratory_id_is_422(
    client, session, bracvam_user
):
    """A-I04: convite de papel laboratorial sem laboratory_id → 422."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    resp = create_invite(
        client, process_id, 'lab@exemplo.org', 'lead_laboratory'
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_invite_on_deleted_process_is_conflict(client, session):
    """A-I05: processo excluído logicamente rejeita criação de convite."""
    user = UserFactory()
    session.add(user)
    await session.commit()
    await grant_participants_management(session, user)
    process = await create_process(session)
    process.deleted_at = datetime.utcnow()
    await session.commit()
    authenticate(client, user)

    resp = create_invite(client, process.id, 'a@exemplo.org', 'statistician')
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_listing_filters_by_per_role_authorization(
    client, session, bracvam_user
):
    """A-I06: listagem retorna só convites cujo papel o usuário autoriza."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    create_invite(client, process_id, 'a@exemplo.org', 'sponsor')

    # BraCVAM (autorização global) cria um convite para um papel próprio.
    # `bracvam_user` (fixture) só tem triage.review/IA por padrão — a
    # permissão genérica de participantes precisa ser concedida à parte,
    # como qualquer outro teste que a use.
    await grant_participants_management(session, bracvam_user)
    authenticate(client, bracvam_user)
    create_invite(client, process_id, 'b@exemplo.org', 'adhoc_evaluator')

    # Proponente só enxerga o convite do papel que ele próprio autoriza.
    authenticate(client, proponente)
    resp = list_invites(client, process_id)
    assert resp.status_code == HTTPStatus.OK
    roles_seen = {item['role_key'] for item in resp.json()}
    assert roles_seen == {'sponsor'}

    # BraCVAM (autorização global) enxerga os dois.
    authenticate(client, bracvam_user)
    resp = list_invites(client, process_id)
    roles_seen = {item['role_key'] for item in resp.json()}
    assert roles_seen == {'sponsor', 'adhoc_evaluator'}


# --- A-N: reenvio/revogação (User Story 3) ---


@pytest.mark.asyncio
async def test_resend_generates_new_token_and_expiry(
    client, session, bracvam_user
):
    """A-N01: reenvio gera novo token, novo prazo, 200."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(client, process_id, 'r@exemplo.org', 'sponsor')
    invite_id = created.json()['id']
    original_token = created.json()['token']

    resp = resend_invite_req(client, process_id, invite_id)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['token'] != original_token


@pytest.mark.asyncio
async def test_previous_token_returns_404_after_resend(
    client, session, bracvam_user
):
    """A-N02: token anterior ao reenvio deixa de funcionar."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(client, process_id, 'r2@exemplo.org', 'sponsor')
    invite_id = created.json()['id']
    original_token = created.json()['token']

    resend_invite_req(client, process_id, invite_id)

    resp = client.get(f'/invites/{original_token}')
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_resend_of_accepted_invite_is_conflict(
    client, session, bracvam_user
):
    """A-N03: reenvio de convite já aceito → 409."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(client, process_id, 'r3@exemplo.org', 'sponsor')
    invite_id = created.json()['id']
    token = created.json()['token']

    accepted_user = UserFactory(email='r3@exemplo.org')
    session.add(accepted_user)
    await session.commit()
    authenticate(client, accepted_user)
    client.post(f'/invites/{token}/accept', headers=ORIGIN)

    authenticate(client, proponente)
    resp = resend_invite_req(client, process_id, invite_id)
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_resend_after_activity_closed_is_conflict(
    client, session, bracvam_user
):
    """A-N04: reenvio depois que a etapa já se encerrou → 409.

    Cenário alcançável: a etapa fecha por designação direta *antes* de
    qualquer convite existir (FR-016, zero convites pendentes); um convite
    "tardio" criado depois para o mesmo papel (sem titularidade única,
    FR-019, ainda é aceito na criação) fica `pending` mesmo com a etapa já
    `COMPLETED` — reenviá-lo é que passa a ser rejeitado (FR-012).
    """
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        create_participant,
    )

    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)

    other_target = UserFactory()
    session.add(other_target)
    await session.commit()
    designate_resp = create_participant(
        client, process_id, other_target.id, 'sponsor'
    )
    assert designate_resp.status_code == HTTPStatus.CREATED

    created = create_invite(client, process_id, 'r4@exemplo.org', 'sponsor')
    assert created.status_code == HTTPStatus.CREATED
    invite_id = created.json()['id']

    resp = resend_invite_req(client, process_id, invite_id)
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_revoke_marks_invite_revoked(client, session, bracvam_user):
    """A-N05: revogação marca status='revoked' e recebe 200."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(client, process_id, 'r5@exemplo.org', 'sponsor')
    invite_id = created.json()['id']

    resp = revoke_invite_req(client, process_id, invite_id)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == 'revoked'


@pytest.mark.asyncio
async def test_accept_and_revoke_pending_sibling_closes_activity(
    client, session, bracvam_user
):
    """A-N06: aceitar um convite e revogar o outro pendente fecha a etapa.

    `adhoc_evaluator` (linhas 7-8 da matriz) só desbloqueia depois que
    `group_manager` fecha (Sequência de Preenchimento) — designa isso
    primeiro. `bracvam_user` precisa da permissão genérica para gerir os
    dois papéis usados aqui.
    """
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        create_participant,
    )

    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    await grant_participants_management(session, bracvam_user)

    gestor = UserFactory()
    session.add(gestor)
    await session.commit()
    authenticate(client, proponente)
    gestor_resp = create_participant(
        client, process_id, gestor.id, 'group_manager'
    )
    assert gestor_resp.status_code == HTTPStatus.CREATED

    authenticate(client, bracvam_user)
    first = create_invite(
        client, process_id, 'sib1@exemplo.org', 'adhoc_evaluator'
    )
    second = create_invite(
        client, process_id, 'sib2@exemplo.org', 'adhoc_evaluator'
    )
    assert first.status_code == HTTPStatus.CREATED
    assert second.status_code == HTTPStatus.CREATED

    accepted_user = UserFactory(email='sib1@exemplo.org')
    session.add(accepted_user)
    await session.commit()
    authenticate(client, accepted_user)
    accept_resp = client.post(
        f'/invites/{first.json()["token"]}/accept', headers=ORIGIN
    )
    assert accept_resp.status_code == HTTPStatus.OK

    # Spec 030: a atividade é do cargo `bracvam`; o convidado não a vê.
    authenticate(client, bracvam_user)
    tasks_before = client.get(
        '/tasks', params={'process_id': process_id}
    ).json()
    title = 'Definir Especialistas Temáticos (Comitê ADHOC)'
    before = [t for t in tasks_before if t['title'] == title]
    assert before
    assert before[0]['status'] != 'COMPLETED'

    revoke_resp = revoke_invite_req(client, process_id, second.json()['id'])
    assert revoke_resp.status_code == HTTPStatus.OK

    tasks_after = client.get(
        '/tasks', params={'process_id': process_id}
    ).json()
    after = [t for t in tasks_after if t['title'] == title]
    assert after
    assert after[0]['status'] == 'COMPLETED'


@pytest.mark.asyncio
async def test_unauthorized_person_denied_resend_and_revoke(
    client, session, bracvam_user
):
    """A-N07: sem autorização para o papel, 403 ao reenviar/revogar."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(client, process_id, 'n7@exemplo.org', 'sponsor')
    invite_id = created.json()['id']

    stranger = UserFactory()
    session.add(stranger)
    await session.commit()
    authenticate(client, stranger)

    assert (
        resend_invite_req(client, process_id, invite_id).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        revoke_invite_req(client, process_id, invite_id).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.asyncio
async def test_resend_and_revoke_without_trusted_origin_are_forbidden(
    client, session, bracvam_user
):
    """A-N08: sem Origin confiável, 403 ao reenviar/revogar."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(client, process_id, 'n8@exemplo.org', 'sponsor')
    invite_id = created.json()['id']

    resend_resp = client.post(
        f'/processes/{process_id}/participants/invites/{invite_id}/resend'
    )
    revoke_resp = client.post(
        f'/processes/{process_id}/participants/invites/{invite_id}/revoke'
    )
    assert resend_resp.status_code == HTTPStatus.FORBIDDEN
    assert revoke_resp.status_code == HTTPStatus.FORBIDDEN
