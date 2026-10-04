"""Spec 040 — e-mail ao Grupo de Seleção na inconformidade do recebimento."""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import Notification, Task
from pivma.notifications.channels import FakeEmailChannel
from pivma.notifications.worker import process_next
from tests.api.routers.test_sample_receipt_router import lab_ready, register
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import _user


async def _warm_vial(session, client):
    ctx = await lab_ready(session, client)
    ctx.second_selector = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.second_selector,
        role_key='sample_selection_group',
    )
    response = register(
        client, ctx.process_id, ctx.codes[0], temperature_celsius=21.0
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return ctx


@pytest.mark.asyncio
async def test_one_email_per_selection_group_member_without_identity(
    session, client, email_invite_settings
):
    ctx = await _warm_vial(session, client)
    channel = FakeEmailChannel()

    queued = list(
        await session.scalars(
            select(Notification).where(
                Notification.kind == 'sample_receipt_nonconformity_email'
            )
        )
    )
    while await process_next(session, channel, email_invite_settings):
        pass

    assert {n.recipient for n in queued} == {
        ctx.selector.email,
        ctx.second_selector.email,
    }
    assert {n.subject_type for n in queued} == {'sample_receipt_nonconformity'}
    assert len(channel.sent) == 2  # noqa: PLR2004
    message = channel.sent[0]
    for body in (message.text, message.html):
        assert ctx.codes[0] in body
        assert ctx.labs[0].name in body
        assert 'temperatura fora da faixa' in body
        for substance in ctx.substances:
            assert substance['chemical_name'] not in body
            assert substance['cas_number'] not in body
            assert substance['reference_classification'] not in body


@pytest.mark.asyncio
async def test_without_email_channel_registration_and_task_still_happen(
    session, client
):
    await _warm_vial(session, client)

    notifications = await session.scalar(
        select(func.count()).select_from(Notification)
    )
    task = await session.scalar(
        select(Task).where(
            Task.assigned_role == 'sample_selection_group',
            Task.status == 'READY',
        )
    )

    assert notifications == 0
    assert task is not None
