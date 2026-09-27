"""Só o Grupo de Seleção do processo vê o conteúdo das amostras (Spec 031).

Cada teste percorre todas as rotas de amostras: laboratório participante,
laboratório líder e Grupo Gestor não veem a atividade (404); admin e
BraCVAM veem a atividade, mas não a editam (403) — o conteúdo exige a
concessão de edição (research R3).
"""

import json
from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_samples_router import (
    ORIGIN,
    PDF,
    _attachments_dir,  # noqa: F401 (fixture autouse)
    _url,
)
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
    grant_cargo,
)
from tests.factories.sample_factory import (
    add_participating_lab,
    sample_process,
    substance_payload,
)
from tests.factories.user_factory import UserFactory

ROUTES = (
    'list',
    'create',
    'update',
    'delete',
    'upload_sds',
    'download_sds',
    'complete',
    'labels',
    'vial',
)


def _call(client, route, ctx):  # noqa: PLR0911
    item = _url(ctx.process_id, f'/{ctx.substance["id"]}')
    match route:
        case 'list':
            return client.get(_url(ctx.process_id))
        case 'create':
            return client.post(
                _url(ctx.process_id),
                json=substance_payload(cas_number='7732-18-5'),
                headers=ORIGIN,
            )
        case 'update':
            return client.patch(item, json={'lot': 'L-X'}, headers=ORIGIN)
        case 'delete':
            return client.delete(item, headers=ORIGIN)
        case 'upload_sds':
            return client.put(
                f'{item}/sds',
                files={'file': ('sds.pdf', PDF, 'application/pdf')},
                headers=ORIGIN,
            )
        case 'download_sds':
            return client.get(f'{item}/sds')
        case 'complete':
            return client.post(
                _url(ctx.process_id, '/complete'), headers=ORIGIN
            )
        case 'labels':
            return client.get(_url(ctx.process_id, '/labels'))
        case 'vial':
            return client.get(_url(ctx.process_id, f'/vials/{ctx.code}'))
    raise AssertionError(route)


async def _prepared(session, client):
    """Processo com uma substância com SDS e 2 laboratórios."""
    ctx = await sample_process(session, lab_count=2)
    authenticate(client, ctx.selector)
    response = client.post(
        _url(ctx.process_id), json=substance_payload(), headers=ORIGIN
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    ctx.substance = response.json()
    ctx.code = ctx.substance['blind_codes'][0]['code']
    client.put(
        _url(ctx.process_id, f'/{ctx.substance["id"]}/sds'),
        files={'file': ('sds.pdf', PDF, 'application/pdf')},
        headers=ORIGIN,
    )
    client.cookies.clear()
    return ctx


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _assert_every_route(client, ctx, expected):
    for route in ROUTES:
        response = _call(client, route, ctx)
        assert response.status_code == expected, (route, response.text)


def _assert_no_identity(response, ctx):
    text = json.dumps(response.json(), ensure_ascii=False)
    for secret in (
        ctx.substance['chemical_name'],
        ctx.substance['cas_number'],
        ctx.substance['lot'],
        *(c['code'] for c in ctx.substance['blind_codes']),
    ):
        assert secret not in text


@pytest.mark.asyncio
async def test_participating_lab_gets_404_on_every_sample_route(
    session, client
):
    ctx = await _prepared(session, client)
    authenticate(client, ctx.lab_users[0])

    _assert_every_route(client, ctx, HTTPStatus.NOT_FOUND)


@pytest.mark.asyncio
async def test_lead_lab_gets_404_on_every_sample_route(session, client):
    ctx = await _prepared(session, client)
    lead = await add_participating_lab(
        session, ctx.process_id, role_key='lead_laboratory'
    )
    authenticate(client, lead.user)

    _assert_every_route(client, ctx, HTTPStatus.NOT_FOUND)


@pytest.mark.asyncio
async def test_group_manager_gets_404_on_every_sample_route(session, client):
    ctx = await _prepared(session, client)
    manager = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=manager,
        role_key='group_manager',
    )
    authenticate(client, manager)

    _assert_every_route(client, ctx, HTTPStatus.NOT_FOUND)


@pytest.mark.asyncio
async def test_admin_gets_403_on_every_sample_route(
    session, client, ai_eval_admin
):
    ctx = await _prepared(session, client)
    authenticate(client, ai_eval_admin)

    _assert_every_route(client, ctx, HTTPStatus.FORBIDDEN)


@pytest.mark.asyncio
async def test_bracvam_gets_403_on_every_sample_route(
    session, client, bracvam_user
):
    ctx = await _prepared(session, client)
    authenticate(client, bracvam_user)

    _assert_every_route(client, ctx, HTTPStatus.FORBIDDEN)


@pytest.mark.asyncio
async def test_unauthenticated_gets_401_on_every_sample_route(session, client):
    ctx = await _prepared(session, client)

    _assert_every_route(client, ctx, HTTPStatus.UNAUTHORIZED)


@pytest.mark.asyncio
async def test_sample_group_of_other_process_gets_404(session, client):
    ctx = await _prepared(session, client)
    other = await sample_process(session, lab_count=1)
    authenticate(client, other.selector)

    _assert_every_route(client, ctx, HTTPStatus.NOT_FOUND)


@pytest.mark.asyncio
async def test_sample_group_member_with_conflict_gets_403(session, client):
    ctx = await _prepared(session, client)
    member = await _user(session)
    assignment = await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=member,
        role_key='sample_selection_group',
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()
    authenticate(client, member)

    _assert_every_route(client, ctx, HTTPStatus.FORBIDDEN)


@pytest.mark.asyncio
async def test_sds_download_denied_to_everyone_but_sample_group(
    session, client, ai_eval_admin, bracvam_user
):
    ctx = await _prepared(session, client)
    manager = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=manager,
        role_key='group_manager',
    )
    expectations = (
        (ctx.lab_users[0], HTTPStatus.NOT_FOUND),
        (manager, HTTPStatus.NOT_FOUND),
        (ai_eval_admin, HTTPStatus.FORBIDDEN),
        (bracvam_user, HTTPStatus.FORBIDDEN),
        (ctx.selector, HTTPStatus.OK),
    )

    for user, expected in expectations:
        authenticate(client, user)
        response = _call(client, 'download_sds', ctx)
        assert response.status_code == expected, user.username


@pytest.mark.asyncio
async def test_admin_and_bracvam_see_sample_task_status_only(
    session, client, ai_eval_admin, bracvam_user
):
    ctx = await _prepared(session, client)

    for user in (ai_eval_admin, bracvam_user):
        authenticate(client, user)
        response = client.get(
            '/tasks', params={'process_id': str(ctx.process_id)}
        )
        assert response.status_code == HTTPStatus.OK
        tasks = [
            t
            for t in response.json()['data']
            if t['activity_key'] == 'sample_definition'
        ]
        assert len(tasks) == 1
        assert tasks[0]['status'] == 'READY'
        _assert_no_identity(response, ctx)


@pytest.mark.asyncio
async def test_participating_lab_does_not_see_sample_task(session, client):
    ctx = await _prepared(session, client)
    authenticate(client, ctx.lab_users[0])

    response = client.get('/tasks', params={'process_id': str(ctx.process_id)})

    assert response.status_code == HTTPStatus.OK
    assert not [
        t
        for t in response.json()['data']
        if t['activity_key'] == 'sample_definition'
    ]


@pytest.mark.asyncio
async def test_timeline_sample_events_carry_no_identity(
    session, client, ai_eval_admin
):
    ctx = await _prepared(session, client)
    authenticate(client, ctx.selector)
    client.post(_url(ctx.process_id, '/complete'), headers=ORIGIN)
    authenticate(client, ai_eval_admin)

    response = client.get(f'/processes/{ctx.process_id}/timeline')

    assert response.status_code == HTTPStatus.OK
    types = {e['event_type'] for e in response.json()['events']}
    assert {
        'SAMPLE_SUBSTANCE_REGISTERED',
        'SAMPLE_CODES_GENERATED',
        'SAMPLE_SDS_UPLOADED',
        'SAMPLE_DEFINITION_COMPLETED',
    } <= types
    _assert_no_identity(response, ctx)


@pytest.mark.asyncio
async def test_timeline_hides_sample_events_from_participating_lab(
    session, client
):
    ctx = await _prepared(session, client)
    authenticate(client, ctx.lab_users[0])

    response = client.get(f'/processes/{ctx.process_id}/timeline')

    assert response.status_code == HTTPStatus.OK
    assert not [
        e
        for e in response.json()['events']
        if e['event_type'].startswith('SAMPLE_')
    ]
