# ruff: noqa: PLR2004

"""Spec 036 — convite por e-mail de ponta a ponta, com canal falso."""

from datetime import datetime, timedelta
from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.notifications.channels import (
    FakeEmailChannel,
    PermanentDeliveryError,
    TemporaryDeliveryError,
)
from pivma.notifications.worker import process_next
from tests.api.routers.test_invites_router import create_invite
from tests.api.routers.test_participant_router import (
    _process_in_planning_phase,
    authenticate,
)


async def _email_invite(client, session, bracvam_user, email):
    process_id, proponente = await _process_in_planning_phase(
        client, session, bracvam_user
    )
    authenticate(client, proponente)
    resp = create_invite(client, process_id, email, 'sponsor', channel='email')
    assert resp.status_code == HTTPStatus.CREATED
    return process_id, resp.json()


@pytest.mark.asyncio
async def test_email_invite_is_delivered_with_working_link(
    client, session, bracvam_user, email_invite_settings
):
    """US1 / FR-012, FR-018: mensagem com o link que abre o convite."""
    process_id, invite = await _email_invite(
        client, session, bracvam_user, 'ana@exemplo.org'
    )
    channel = FakeEmailChannel()

    await process_next(session, channel, email_invite_settings)

    [message] = channel.sent
    link = f'https://front.test/convites/{invite["token"]}'
    assert message.to == 'ana@exemplo.org'
    assert link in message.text
    assert link in message.html
    assert client.get(f'/invites/{invite["token"]}').status_code == (
        HTTPStatus.OK
    )
    listed = client.get(f'/processes/{process_id}/participants/invites')
    [item] = [i for i in listed.json()['data'] if i['id'] == invite['id']]
    assert item['delivery']['status'] == 'sent'
    assert item['delivery']['attempts'] == 1
    assert item['delivery']['sent_at'] is not None


# --- US2: falha de envio não trava o convite e fica visível ---


def _delivery(client, process_id, invite_id):
    listed = client.get(f'/processes/{process_id}/participants/invites')
    [item] = [i for i in listed.json()['data'] if i['id'] == invite_id]
    return item['delivery']


@pytest.mark.asyncio
async def test_temporary_failures_until_limit_end_as_failed(
    client, session, bracvam_user, use_settings
):
    """US2-1, US2-3 / FR-004, FR-016: convite criado; envio termina falho."""
    from tests.conftest import email_settings  # noqa: PLC0415

    settings = use_settings(email_settings(NOTIFICATION_MAX_ATTEMPTS=3))
    process_id, invite = await _email_invite(
        client, session, bracvam_user, 'falha@exemplo.org'
    )
    assert len(invite['token']) >= 32
    channel = FakeEmailChannel(
        failures=[TemporaryDeliveryError('connection', 'down')] * 3
    )
    start = datetime.utcnow()

    for step in range(3):
        await process_next(
            session, channel, settings, now=start + timedelta(minutes=10 * step)
        )
        if step < 2:
            delivery = _delivery(client, process_id, invite['id'])
            assert delivery['status'] == 'pending'
            assert delivery['attempts'] == step + 1

    delivery = _delivery(client, process_id, invite['id'])
    assert delivery['status'] == 'failed'
    assert delivery['error_code'] == 'max_attempts'
    assert delivery['attempts'] == 3
    assert channel.sent == []
    assert client.get(f'/invites/{invite["token"]}').status_code == (
        HTTPStatus.OK
    )


@pytest.mark.asyncio
async def test_temporary_failure_then_success_ends_as_sent(
    client, session, bracvam_user, email_invite_settings
):
    """US2-2: o serviço volta antes do limite e a mensagem sai."""
    process_id, invite = await _email_invite(
        client, session, bracvam_user, 'volta@exemplo.org'
    )
    channel = FakeEmailChannel(
        failures=[TemporaryDeliveryError('connection', 'down')]
    )
    start = datetime.utcnow()

    await process_next(session, channel, email_invite_settings, now=start)
    await process_next(
        session,
        channel,
        email_invite_settings,
        now=start + timedelta(minutes=1),
    )

    delivery = _delivery(client, process_id, invite['id'])
    assert delivery['status'] == 'sent'
    assert delivery['attempts'] == 2
    assert delivery['sent_at'] is not None
    assert len(channel.sent) == 1


@pytest.mark.asyncio
async def test_expired_invite_is_not_sent(
    client, session, bracvam_user, email_invite_settings
):
    """Edge case / FR-015: convite vencido antes do envio não sai."""
    process_id, invite = await _email_invite(
        client, session, bracvam_user, 'tarde@exemplo.org'
    )
    channel = FakeEmailChannel()
    expires_at = datetime.fromisoformat(invite['expires_at'])

    await process_next(
        session,
        channel,
        email_invite_settings,
        now=expires_at + timedelta(minutes=1),
    )

    delivery = _delivery(client, process_id, invite['id'])
    assert delivery['status'] == 'failed'
    assert delivery['error_code'] == 'expired'
    assert channel.sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['sent', 'failed', 'cancelled'])
async def test_token_is_not_stored_after_delivery_ends(  # noqa: PLR0913, PLR0917
    client, session, bracvam_user, email_invite_settings, outcome
):
    """SC-005: depois do fim do envio, nenhum campo guarda o token."""
    from sqlalchemy import select  # noqa: PLC0415

    from pivma.core.database.models import Notification  # noqa: PLC0415
    from tests.api.routers.test_invites_router import (  # noqa: PLC0415
        revoke_invite_req,
    )

    process_id, invite = await _email_invite(
        client, session, bracvam_user, f'{outcome}@exemplo.org'
    )
    channel = FakeEmailChannel()
    if outcome == 'failed':
        channel.failures.append(
            PermanentDeliveryError('smtp_permanent', '550 rejected')
        )
    if outcome == 'cancelled':
        revoke_invite_req(client, process_id, invite['id'])
    else:
        await process_next(session, channel, email_invite_settings)

    rows = (
        await session.scalars(
            select(Notification).where(
                Notification.subject_id == UUID(invite['id'])
            )
        )
    ).all()
    assert [row.status for row in rows] == [outcome]
    for row in rows:
        assert row.payload_encrypted is None
        values = [
            str(getattr(row, column.key))
            for column in Notification.__table__.columns
        ]
        assert not any(invite['token'] in value for value in values)
