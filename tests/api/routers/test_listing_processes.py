"""Spec 033, US1 (3b) - listagens de processos no envelope padrão."""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

ENVELOPE_KEYS = {'data', 'pagination', 'filters_applied', 'sort'}
ORIGIN = {'Origin': 'https://testserver'}
FORM = '/processes/{pid}/activities/proposal_submission/form'


def _get(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


async def _proponent(session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _new_process(client, title='Processo'):
    response = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': title},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()['id']


def _return_for_revision(client, pid, proponent, bracvam_user, value):
    """Envia, a triagem pede revisão e o proponente reabre a submissão."""
    authenticate(client, proponent)
    client.post(FORM.format(pid=pid), json={'values': {'method_title': value}})
    authenticate(client, bracvam_user)
    decided = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'NEEDS_REVISION', 'justification': 'Ajustar.'},
        headers=ORIGIN,
    )
    assert decided.status_code == HTTPStatus.OK, decided.text
    authenticate(client, proponent)
    revised = client.post(
        f'/processes/{pid}/return-review',
        json={'choice': 'REVISE'},
        headers=ORIGIN,
    )
    assert revised.status_code == HTTPStatus.OK, revised.text


@pytest.mark.asyncio
async def test_templates_envelope_ordered_by_name(client, session):
    authenticate(client, await _proponent(session))

    body = _get(client, '/processes/templates')

    assert set(body) == ENVELOPE_KEYS
    names = [item['name'] for item in body['data']]
    assert names == sorted(names)
    assert body['sort'] == {'by': 'name', 'order': 'asc'}


@pytest.mark.asyncio
async def test_processes_envelope_default_filters(client, session):
    authenticate(client, await _proponent(session))

    body = _get(client, '/processes')

    assert set(body) == ENVELOPE_KEYS
    assert body['filters_applied'] == {'status': None}
    assert body['sort'] == {'by': 'created_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_processes_second_page(client, session):
    authenticate(client, await _proponent(session))
    for index in range(3):
        _new_process(client, f'Processo {index}')

    body = _get(client, '/processes', page=2, per_page=2)

    assert len(body['data']) == 1
    assert body['pagination']['total_items'] == 3  # noqa: PLR2004
    assert body['pagination']['has_prev'] is True


@pytest.mark.asyncio
async def test_processes_status_filter_echoed(client, session):
    authenticate(client, await _proponent(session))
    _new_process(client)

    body = _get(client, '/processes', status='CLOSED')

    assert body['data'] == []
    assert body['filters_applied'] == {'status': 'CLOSED'}


@pytest.mark.asyncio
async def test_processes_ignores_legacy_size_param(client, session):
    authenticate(client, await _proponent(session))

    body = _get(client, '/processes', size=1)

    assert body['pagination']['per_page'] == 20  # noqa: PLR2004


@pytest.mark.asyncio
async def test_submission_versions_envelope(client, session, bracvam_user):
    proponent = await _proponent(session)
    authenticate(client, proponent)
    pid = _new_process(client)
    _return_for_revision(client, pid, proponent, bracvam_user, 'V1')
    _return_for_revision(client, pid, proponent, bracvam_user, 'V2')

    authenticate(client, proponent)
    body = _get(client, f'/processes/{pid}/submission-versions')

    assert set(body) == ENVELOPE_KEYS
    assert len(body['data']) == 2  # noqa: PLR2004
    assert body['sort'] == {'by': 'returned_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_timeline_envelope(client, session):
    authenticate(client, await _proponent(session))
    pid = _new_process(client)

    body = _get(client, f'/processes/{pid}/timeline')

    assert set(body) == ENVELOPE_KEYS
    assert body['sort'] == {'by': 'occurred_at', 'order': 'asc'}
    assert body['data']


@pytest.mark.asyncio
async def test_timeline_total_counts_only_visible_events(
    client, session, bracvam_user
):
    proponent = await _proponent(session)
    authenticate(client, proponent)
    pid = _new_process(client)
    client.post(FORM.format(pid=pid), json={'values': {'method_title': 'V1'}})
    authenticate(client, bracvam_user)
    client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Ok.'},
        headers=ORIGIN,
    )

    totals = {}
    for user in (proponent, bracvam_user):
        authenticate(client, user)
        body = _get(client, f'/processes/{pid}/timeline', per_page=100)
        # O total é o que o usuário vê, não o total de eventos do processo.
        assert body['pagination']['total_items'] == len(body['data'])
        totals[user.id] = body['pagination']['total_items']

    # O BraCVAM vê a triagem; o proponente não vê todos os eventos dela.
    assert totals[proponent.id] < totals[bracvam_user.id]


@pytest.mark.asyncio
async def test_timeline_second_page_keeps_order(client, session):
    authenticate(client, await _proponent(session))
    pid = _new_process(client)
    # O envio gera mais eventos além da criação e da designação.
    client.post(FORM.format(pid=pid), json={'values': {'method_title': 'V1'}})
    full = _get(client, f'/processes/{pid}/timeline', per_page=100)['data']
    assert len(full) > 2  # noqa: PLR2004

    first = _get(client, f'/processes/{pid}/timeline', per_page=2)['data']
    second = _get(client, f'/processes/{pid}/timeline', per_page=2, page=2)[
        'data'
    ]

    assert [e['id'] for e in first + second] == [e['id'] for e in full[:4]]


@pytest.mark.asyncio
async def test_timeline_invisible_process_404(client, session):
    authenticate(client, await _proponent(session))
    pid = _new_process(client)
    stranger = UserFactory()
    session.add(stranger)
    await session.commit()

    authenticate(client, stranger)
    response = client.get(f'/processes/{pid}/timeline')

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'path',
    [
        '/processes/templates',
        '/processes',
        '/processes/{pid}/submission-versions',
        '/processes/{pid}/timeline',
    ],
)
async def test_process_lists_reject_per_page_above_100(client, session, path):
    authenticate(client, await _proponent(session))
    pid = _new_process(client)

    response = client.get(path.format(pid=pid), params={'per_page': 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
