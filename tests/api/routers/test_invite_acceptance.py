# ruff: noqa: PLR2004

"""Spec 028 — pré-visualização e aceite público de convite."""

from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import AuditEvent, RoleAssignmentInvite
from tests.api.routers.test_invites_router import create_invite
from tests.api.routers.test_participant_router import (
    ORIGIN,
    _process_in_planning_phase,
    authenticate,
    create_active_laboratory_affiliation,
)
from tests.factories.user_factory import UserFactory


def accept_invite_req(client, token):
    return client.post(f'/invites/{token}/accept', headers=ORIGIN)


@pytest.mark.asyncio
async def test_preview_masks_email_without_authentication(
    client, session, bracvam_user
):
    """A-V01: pré-visualização pública, e-mail mascarado."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'convidado@exemplo.org', 'sponsor'
    )
    token = created.json()['token']

    client.cookies.clear()
    resp = client.get(f'/invites/{token}')
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body['role_key'] == 'sponsor'
    assert body['masked_email'] == 'c********@exemplo.org'
    assert 'convidado@exemplo.org' not in resp.text


@pytest.mark.asyncio
async def test_preview_unknown_token_is_404(client):
    """A-V02: token inexistente → 404."""
    resp = client.get('/invites/token-que-nao-existe')
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_preview_expired_invite_shows_expired_flag(
    client, session, bracvam_user
):
    """A-V03: convite pendente e expirado devolve expired=true, não 404."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'venceu@exemplo.org', 'sponsor'
    )
    token = created.json()['token']
    invite_id = created.json()['id']

    invite = await session.get(RoleAssignmentInvite, invite_id)
    invite.expires_at = datetime.utcnow() - timedelta(hours=1)
    await session.commit()

    resp = client.get(f'/invites/{token}')
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['expired'] is True


@pytest.mark.asyncio
async def test_accept_with_matching_email_creates_assignment(
    client, session, bracvam_user
):
    """A-A01: aceite com e-mail correspondente cria a designação, 200."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'novo@exemplo.org', 'sponsor'
    )
    token = created.json()['token']

    new_user = UserFactory(email='novo@exemplo.org')
    session.add(new_user)
    await session.commit()
    authenticate(client, new_user)

    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body['role_key'] == 'sponsor'
    assert body['assignment_id'] is not None
    assert body['invite']['status'] == 'accepted'

    participants = client.get(
        f'/processes/{process_id}/participants'
    ).json()
    assert any(
        p['user_id'] == str(new_user.id) and p['role_key'] == 'sponsor'
        for p in participants
    )


@pytest.mark.asyncio
async def test_accept_with_existing_account_login_works(
    client, session, bracvam_user
):
    """A-A01 (variante): pessoa que já tem conta só faz login e aceita."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    existing_user = UserFactory(email='ja-tenho-conta@exemplo.org')
    session.add(existing_user)
    await session.commit()

    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'ja-tenho-conta@exemplo.org', 'group_manager'
    )
    token = created.json()['token']

    authenticate(client, existing_user)
    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_accept_with_mismatched_email_is_forbidden(
    client, session, bracvam_user
):
    """A-A02: e-mail de sessão diferente do convite → 403, convite intacto."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'alvo@exemplo.org', 'sponsor'
    )
    token = created.json()['token']
    invite_id = created.json()['id']

    wrong_user = UserFactory(email='outro@exemplo.org')
    session.add(wrong_user)
    await session.commit()
    authenticate(client, wrong_user)

    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.FORBIDDEN

    authenticate(client, proponente)
    preview = client.get(
        f'/processes/{process_id}/participants/invites'
    ).json()
    invite_row = next(i for i in preview if i['id'] == invite_id)
    assert invite_row['status'] == 'pending'


@pytest.mark.asyncio
async def test_accept_expired_invite_is_conflict(
    client, session, bracvam_user
):
    """A-A03: convite expirado → 409."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'expirado@exemplo.org', 'sponsor'
    )
    token = created.json()['token']
    invite_id = created.json()['id']

    invite = await session.get(RoleAssignmentInvite, invite_id)
    invite.expires_at = datetime.utcnow() - timedelta(hours=1)
    await session.commit()

    new_user = UserFactory(email='expirado@exemplo.org')
    session.add(new_user)
    await session.commit()
    authenticate(client, new_user)

    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
@pytest.mark.parametrize('final_status', ['accepted', 'revoked'])
async def test_accept_already_resolved_invite_is_conflict(
    client, session, bracvam_user, final_status
):
    """A-A04: convite já aceito ou revogado → 409, parametrizado."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, f'{final_status}@exemplo.org', 'sponsor'
    )
    token = created.json()['token']
    invite_id = created.json()['id']

    target_user = UserFactory(email=f'{final_status}@exemplo.org')
    session.add(target_user)
    await session.commit()

    if final_status == 'accepted':
        authenticate(client, target_user)
        accept_invite_req(client, token)
    else:
        authenticate(client, proponente)
        client.post(
            f'/processes/{process_id}/participants/invites/'
            f'{invite_id}/revoke',
            headers=ORIGIN,
        )

    authenticate(client, target_user)
    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_accept_laboratory_role_without_affiliation_is_conflict(
    client, session, bracvam_user
):
    """A-A05: sem vínculo laboratorial vigente → 409, convite fica pending."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    gestor = UserFactory()
    session.add(gestor)
    await session.commit()
    authenticate(client, proponente)
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        create_participant,
    )

    create_participant(client, process_id, gestor.id, 'group_manager')

    from tests.factories.institutional_factory import (  # noqa: PLC0415
        InstitutionFactory,
        LaboratoryFactory,
    )

    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.commit()

    authenticate(client, gestor)
    created = create_invite(
        client,
        process_id,
        'semlab@exemplo.org',
        'lead_laboratory',
        laboratory_id=laboratory.id,
    )
    token = created.json()['token']
    invite_id = created.json()['id']

    new_user = UserFactory(email='semlab@exemplo.org')
    session.add(new_user)
    await session.commit()
    authenticate(client, new_user)

    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.CONFLICT

    authenticate(client, gestor)
    invites = client.get(
        f'/processes/{process_id}/participants/invites'
    ).json()
    invite_row = next(i for i in invites if i['id'] == invite_id)
    assert invite_row['status'] == 'pending'


@pytest.mark.asyncio
async def test_accept_laboratory_role_with_affiliation_succeeds(
    client, session, bracvam_user
):
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    gestor = UserFactory()
    session.add(gestor)
    await session.commit()
    authenticate(client, proponente)
    from tests.api.routers.test_participant_router import (  # noqa: PLC0415
        create_participant,
    )

    create_participant(client, process_id, gestor.id, 'group_manager')

    new_user = UserFactory(email='comlab@exemplo.org')
    session.add(new_user)
    await session.commit()
    laboratory, _affiliation = await create_active_laboratory_affiliation(
        session, new_user
    )

    authenticate(client, gestor)
    created = create_invite(
        client,
        process_id,
        'comlab@exemplo.org',
        'lead_laboratory',
        laboratory_id=laboratory.id,
    )
    token = created.json()['token']

    authenticate(client, new_user)
    resp = accept_invite_req(client, token)
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_accept_records_invite_accepted_and_participant_assigned(
    client, session, bracvam_user
):
    """A-A06: aceite grava INVITE_ACCEPTED e PARTICIPANT_ASSIGNED juntos."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'auditoria@exemplo.org', 'sponsor'
    )
    token = created.json()['token']

    new_user = UserFactory(email='auditoria@exemplo.org')
    session.add(new_user)
    await session.commit()
    authenticate(client, new_user)
    accept_invite_req(client, token)

    invite_count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'INVITE_ACCEPTED',
            AuditEvent.process_instance_id == process_id,
        )
    )
    assignment_count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'PARTICIPANT_ASSIGNED',
            AuditEvent.process_instance_id == process_id,
            AuditEvent.context_data['role_key'].astext == 'sponsor',
        )
    )
    assert invite_count == 1
    assert assignment_count == 1


@pytest.mark.asyncio
async def test_accept_closes_activity_when_last_pending_invite(
    client, session, bracvam_user
):
    """A-A07: aceitar o último convite pendente fecha a etapa."""
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    created = create_invite(
        client, process_id, 'unico@exemplo.org', 'sponsor'
    )
    token = created.json()['token']

    new_user = UserFactory(email='unico@exemplo.org')
    session.add(new_user)
    await session.commit()
    authenticate(client, new_user)
    accept_invite_req(client, token)

    tasks = client.get('/tasks', params={'process_id': process_id}).json()
    sponsor_task = next(
        t for t in tasks if t['title'] == 'Definir o Patrocinador'
    )
    assert sponsor_task['status'] == 'COMPLETED'
