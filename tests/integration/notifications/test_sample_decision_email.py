"""Spec 040 — e-mail ao laboratório quando o Grupo de Seleção decide."""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import Notification, User
from pivma.notifications.channels import FakeEmailChannel
from pivma.notifications.worker import process_next
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_sample_nonconformity_router import nc_url
from tests.api.routers.test_sample_receipt_router import (
    ORIGIN,
    lab_ready,
    register,
)
from tests.factories.sample_factory import assign_lab

DECISION_EMAIL = 'sample_receipt_decision_email'
GUIDANCE = 'Descarte o frasco antigo como resíduo químico.'
JUSTIFICATION = 'Segredo do Grupo de Seleção.'


async def _decided(session, client, decision='resend'):
    """Lab 0 com dois analistas registra um frasco avariado; Ricardo decide."""
    ctx = await lab_ready(session, client)
    assignment = await assign_lab(session, ctx.process_id, ctx.labs[0])
    ctx.second_analyst = await session.get(User, assignment.user_id)
    response = register(
        client, ctx.process_id, ctx.codes[0], package_state='damaged'
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    authenticate(client, ctx.selector)
    [item] = client.get(nc_url(ctx.process_id)).json()['data']
    response = client.post(
        nc_url(ctx.process_id, f'/{item["id"]}/decision'),
        json={
            'decision': decision,
            'justification': JUSTIFICATION,
            'lab_guidance': GUIDANCE,
        },
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    ctx.decided = response.json()
    return ctx


async def _decision_emails(session):
    return list(
        await session.scalars(
            select(Notification).where(Notification.kind == DECISION_EMAIL)
        )
    )


@pytest.mark.asyncio
async def test_one_email_per_lab_analyst_with_status_and_guidance(
    session, client, email_invite_settings
):
    ctx = await _decided(session, client)
    channel = FakeEmailChannel()

    queued = await _decision_emails(session)
    while await process_next(session, channel, email_invite_settings):
        pass

    assert {n.recipient for n in queued} == {
        ctx.lab_users[0].email,
        ctx.second_analyst.email,
    }
    analysts = {ctx.lab_users[0].email, ctx.second_analyst.email}
    sent = [m for m in channel.sent if m.to in analysts]
    assert len(sent) == 2  # noqa: PLR2004
    for body in (sent[0].text, sent[0].html):
        assert ctx.codes[0] in body
        assert ctx.labs[0].name in body
        assert 'substituído' in body
        assert GUIDANCE in body
        assert JUSTIFICATION not in body
        assert ctx.decided['replacement_code'] not in body
        for substance in ctx.substances:
            assert substance['chemical_name'] not in body
            assert substance['cas_number'] not in body
            assert substance['reference_classification'] not in body


@pytest.mark.asyncio
async def test_other_lab_and_selection_group_get_no_decision_email(
    session, client, email_invite_settings
):
    ctx = await _decided(session, client, decision='accept_with_caveat')

    recipients = {n.recipient for n in await _decision_emails(session)}

    assert ctx.lab_users[1].email not in recipients
    assert ctx.selector.email not in recipients


@pytest.mark.asyncio
async def test_without_email_channel_decision_is_saved_and_nothing_queued(
    session, client
):
    ctx = await _decided(session, client, decision='accept_with_caveat')

    queued = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.kind == DECISION_EMAIL)
    )

    assert queued == 0
    assert ctx.decided['status'] == 'RESOLVED'
    assert ctx.decided['lab_guidance'] == GUIDANCE
