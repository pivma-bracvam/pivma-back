"""Spec 033, US1 (3b) - listagens de processos no envelope padrão."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import Assignment
from pivma.core.process_engine import utc_now
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.submission_factory import submission_values
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
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()['id']


def _return_for_revision(client, pid, proponent, bracvam_user, value):
    """Envia, a triagem pede revisão e o proponente reabre a submissão."""
    authenticate(client, proponent)
    client.post(
        FORM.format(pid=pid),
        json={'values': submission_values(value)},
        headers=ORIGIN,
    )
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
async def test_templates_envelope_ordered_by_display_order(client, session):
    authenticate(client, await _proponent(session))

    body = _get(client, '/processes/templates')

    assert set(body) == ENVELOPE_KEYS
    assert body['sort'] == {'by': 'display_order', 'order': 'asc'}


@pytest.mark.asyncio
async def test_processes_envelope_default_filters(client, session):
    authenticate(client, await _proponent(session))

    body = _get(client, '/processes')

    assert set(body) == ENVELOPE_KEYS
    assert body['filters_applied'] == {
        'status': None,
        'mine': False,
        'submission_state': None,
    }
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
    assert body['filters_applied']['status'] == 'CLOSED'


def _submit(client, pid):
    response = client.post(
        FORM.format(pid=pid),
        json={'values': submission_values('Método')},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text


def _ids(body):
    return [item['id'] for item in body['data']]


async def _other_user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_processes_filters_echoed(client, session):
    authenticate(client, await _proponent(session))

    body = _get(client, '/processes', mine=True, submission_state='draft')

    assert body['filters_applied'] == {
        'status': None,
        'mine': True,
        'submission_state': 'draft',
    }


@pytest.mark.asyncio
async def test_processes_mine_skips_process_of_another_proponent(
    client, session, bracvam_user
):
    authenticate(client, await _proponent(session))
    pid = _new_process(client)

    authenticate(client, bracvam_user)

    assert pid in _ids(_get(client, '/processes'))
    assert _ids(_get(client, '/processes', mine=True)) == []


@pytest.mark.asyncio
async def test_processes_mine_skips_participant_in_another_role(
    client, session
):
    owner = await _proponent(session)
    authenticate(client, owner)
    pid = _new_process(client)
    sponsor = await _other_user(session)
    session.add(
        Assignment(
            process_instance_id=UUID(pid),
            user_id=sponsor.id,
            role_key='sponsor',
            assigned_by=owner.id,
        )
    )
    await session.commit()

    authenticate(client, sponsor)

    assert _ids(_get(client, '/processes')) == [pid]
    assert _ids(_get(client, '/processes', mine=True)) == []


@pytest.mark.asyncio
async def test_processes_mine_skips_revoked_proponent(client, session):
    owner = await _proponent(session)
    authenticate(client, owner)
    pid = _new_process(client)
    assignment = await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == UUID(pid),
            Assignment.user_id == owner.id,
        )
    )
    assignment.revoked_at = utc_now()
    await session.commit()

    assert _ids(_get(client, '/processes', mine=True)) == []


@pytest.mark.asyncio
async def test_processes_submission_state_respects_visibility(client, session):
    authenticate(client, await _proponent(session))
    _new_process(client)

    authenticate(client, await _other_user(session))

    assert _ids(_get(client, '/processes', submission_state='draft')) == []


@pytest.mark.asyncio
async def test_processes_filters_combine_with_status(client, session):
    authenticate(client, await _proponent(session))
    _new_process(client)

    body = _get(
        client,
        '/processes',
        mine=True,
        submission_state='draft',
        status='CLOSED',
    )

    assert body['data'] == []


@pytest.mark.asyncio
async def test_processes_submission_state_counts_filtered_pages(
    client, session
):
    authenticate(client, await _proponent(session))
    for index in range(3):
        _new_process(client, f'Rascunho {index}')
    _submit(client, _new_process(client, 'Enviada'))

    body = _get(
        client, '/processes', submission_state='draft', per_page=2, page=2
    )

    assert len(body['data']) == 1
    assert body['pagination']['total_items'] == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_processes_rejects_unknown_submission_state(client, session):
    authenticate(client, await _proponent(session))

    response = client.get('/processes', params={'submission_state': 'sent'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


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
    client.post(
        FORM.format(pid=pid),
        json={'values': submission_values('V1')},
        headers=ORIGIN,
    )
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
    client.post(
        FORM.format(pid=pid),
        json={'values': submission_values('V1')},
        headers=ORIGIN,
    )
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
