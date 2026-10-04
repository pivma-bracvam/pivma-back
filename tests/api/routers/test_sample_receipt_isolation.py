"""Isolamento por laboratório e cegamento no recebimento (Spec 040, US5).

Também cobre o que um laboratório vê da inconformidade de outro (US6).
"""

import json
from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_sample_receipt_router import (
    lab_ready,
    register,
    vials_url,
)
from tests.factories.laboratory_run_factory import end_affiliation
from tests.factories.sample_factory import _user
from tests.factories.sample_receipt_factory import codes_of

SECRET_KEYS = (
    'chemical_name',
    'cas_number',
    'reference_classification',
    'sds',
    'justification',
)


def _assert_blind(body, ctx):
    text = json.dumps(body, ensure_ascii=False)
    for key in SECRET_KEYS:
        assert f'"{key}"' not in text
    for substance in ctx.substances:
        assert substance['chemical_name'] not in text
        assert substance['cas_number'] not in text
        assert substance['reference_classification'] not in text


async def _other_code(session, ctx):
    return (await codes_of(session, ctx, 1))[0]


@pytest.mark.asyncio
async def test_vial_of_other_lab_is_404_like_unknown_code(session, client):
    ctx = await lab_ready(session, client)
    other = await _other_code(session, ctx)

    response = client.get(f'/processes/{ctx.process_id}/samples/vials/{other}')
    unknown = client.get(f'/processes/{ctx.process_id}/samples/vials/ZZZZZZZZ')

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == unknown.json()


@pytest.mark.asyncio
async def test_registering_vial_of_other_lab_is_404(session, client):
    ctx = await lab_ready(session, client)
    other = await _other_code(session, ctx)

    response = register(client, ctx.process_id, other)

    assert response.status_code == HTTPStatus.NOT_FOUND
    authenticate(client, ctx.lab_users[1])
    vials = client.get(vials_url(ctx.process_id)).json()['data']
    assert {v['status'] for v in vials} == {'pending'}


@pytest.mark.asyncio
async def test_lab_without_effective_designation_cannot_list_or_register(
    session, client
):
    ctx = await lab_ready(session, client)
    await end_affiliation(session, ctx.lab_users[0])

    listed = client.get(vials_url(ctx.process_id))
    registered = register(client, ctx.process_id, ctx.codes[0])

    assert listed.status_code == HTTPStatus.NOT_FOUND
    assert registered.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_user_without_role_gets_404(session, client):
    ctx = await lab_ready(session, client)
    authenticate(client, await _user(session))

    assert client.get(vials_url(ctx.process_id)).status_code == (
        HTTPStatus.NOT_FOUND
    )
    assert register(client, ctx.process_id, ctx.codes[0]).status_code == (
        HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_manager_and_selection_group_cannot_register(session, client):
    ctx = await lab_ready(session, client)

    for user in (ctx.group_manager, ctx.selector):
        authenticate(client, user)
        response = register(client, ctx.process_id, ctx.codes[0])
        assert response.status_code == HTTPStatus.NOT_FOUND, user


@pytest.mark.asyncio
async def test_lab_responses_never_carry_identity(session, client):
    ctx = await lab_ready(session, client)

    registered = register(
        client, ctx.process_id, ctx.codes[0], temperature_celsius=30
    )
    listed = client.get(vials_url(ctx.process_id))
    vial = client.get(
        f'/processes/{ctx.process_id}/samples/vials/{ctx.codes[0]}'
    )

    for response in (registered, listed, vial):
        assert response.status_code < HTTPStatus.BAD_REQUEST, response.text
        _assert_blind(response.json(), ctx)


@pytest.mark.asyncio
async def test_other_lab_sees_nothing_of_a_nonconformity(session, client):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], package_state='violated')

    authenticate(client, ctx.lab_users[1])
    vials = client.get(vials_url(ctx.process_id)).json()['data']
    tasks = client.get(
        '/tasks', params={'process_id': str(ctx.process_id)}
    ).json()['data']
    events = client.get(
        f'/processes/{ctx.process_id}/timeline', params={'per_page': 100}
    ).json()['data']

    assert ctx.codes[0] not in {v['code'] for v in vials}
    assert {v['status'] for v in vials} == {'pending'}
    assert 'sample_receipt_resolution' not in {
        t['activity_key'] for t in tasks
    }
    types = {e['event_type'] for e in events}
    assert 'SAMPLE_RECEIPT_REGISTERED' not in types
    assert 'SAMPLE_NONCONFORMITY_OPENED' not in types
    assert 'SAMPLE_RECEIPT_RESOLUTION_OPENED' not in types


@pytest.mark.asyncio
async def test_reporting_lab_sees_its_registration_but_not_resolution(
    session, client
):
    ctx = await lab_ready(session, client)
    register(client, ctx.process_id, ctx.codes[0], package_state='violated')

    events = client.get(
        f'/processes/{ctx.process_id}/timeline', params={'per_page': 100}
    ).json()['data']

    types = {e['event_type'] for e in events}
    assert 'SAMPLE_RECEIPT_REGISTERED' in types
    assert 'SAMPLE_NONCONFORMITY_OPENED' not in types
    assert 'SAMPLE_RECEIPT_RESOLUTION_OPENED' not in types


@pytest.mark.asyncio
async def test_post_requires_trusted_origin(session, client):
    ctx = await lab_ready(session, client)

    response = client.post(
        vials_url(ctx.process_id, f'/{ctx.codes[0]}'), json={}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
