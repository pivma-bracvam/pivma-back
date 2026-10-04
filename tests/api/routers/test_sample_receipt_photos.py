"""Fotos no registro do frasco (Spec 040, US8)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import AuditEvent
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_sample_receipt_router import (
    ORIGIN,
    lab_ready,
    register,
    vials_url,
)
from tests.api.routers.test_samples_router import (
    _attachments_dir,  # noqa: F401 (fixture autouse)
)

PNG = b'\x89PNG\r\n\x1a\n foto'


def attach(client, ctx, code, *, name='frasco.png', content=PNG):
    return client.post(
        vials_url(ctx.process_id, f'/{code}/photos'),
        files={'file': (name, content, 'image/png')},
        headers=ORIGIN,
    )


async def registered(session, client, **overrides):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], **overrides)
    return ctx


@pytest.mark.asyncio
async def test_photo_is_attached_listed_and_audited(session, client):
    ctx = await registered(session, client, package_state='damaged')

    response = attach(client, ctx, ctx.codes[0])

    assert response.status_code == HTTPStatus.CREATED, response.text
    photo = response.json()
    vial = client.get(vials_url(ctx.process_id)).json()['data'][0]
    assert [p['id'] for p in vial['photos']] == [photo['id']]
    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == 'SAMPLE_RECEIPT_PHOTO_ATTACHED'
        )
    )
    assert event.context_data['artifact_id'] == photo['id']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('name', 'content', 'code'),
    [
        ('frasco.pdf', PNG, 'extension_not_allowed'),
        ('frasco.png', b'', 'empty_file'),
    ],
)
async def test_invalid_photo_is_refused(session, client, name, content, code):
    ctx = await registered(session, client)

    response = attach(client, ctx, ctx.codes[0], name=name, content=content)

    assert response.status_code >= HTTPStatus.BAD_REQUEST
    assert response.json()['detail']['code'] == code


@pytest.mark.asyncio
async def test_photo_over_size_limit_is_refused(session, client, monkeypatch):
    monkeypatch.setenv('ATTACHMENT_MAX_SIZE_MB', '1')
    ctx = await registered(session, client)

    response = attach(
        client, ctx, ctx.codes[0], content=PNG + b'0' * (1024 * 1024)
    )

    assert response.json()['detail']['code'] == 'file_too_large'


@pytest.mark.asyncio
async def test_photo_on_unregistered_vial_returns_404(session, client):
    ctx = await registered(session, client)

    response = attach(client, ctx, ctx.codes[1])

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_photo_after_lab_receipt_completed_returns_409(session, client):
    ctx = await registered(session, client)
    register(client, ctx.process_id, ctx.codes[1])

    response = attach(client, ctx, ctx.codes[0])

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_photo_download_by_lab_and_group_only(session, client):
    ctx = await registered(session, client, package_state='damaged')
    photo = attach(client, ctx, ctx.codes[0]).json()
    url = f'/processes/{ctx.process_id}/sample-receipt/photos/{photo["id"]}'

    expected = [
        (ctx.lab_users[0], HTTPStatus.OK),
        (ctx.selector, HTTPStatus.OK),
        (ctx.lab_users[1], HTTPStatus.NOT_FOUND),
        (ctx.group_manager, HTTPStatus.NOT_FOUND),
    ]
    for user, status in expected:
        authenticate(client, user)
        response = client.get(url)
        assert response.status_code == status, user
        if status == HTTPStatus.OK:
            assert response.content == PNG
