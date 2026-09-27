"""Spec 032 - `GET /tasks` no padrão de listagem.

Envelope, referências, paginação, ordenação, rodada vigente e filtros. Os
dados vêm de `tests/factories/task_listing_factory.py`, que cria tarefas com
status, prazo e rodada controlados.
"""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.task_listing_factory import add_task, listing_process
from tests.factories.user_factory import UserFactory


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


def _now():
    return datetime.now(UTC).replace(tzinfo=None)


def _list(client, **params):
    response = client.get('/tasks', params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


# --- US5: envelope ---------------------------------------------------------


@pytest.mark.asyncio
async def test_task_list_returns_envelope_blocks(client, session):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    await add_task(session, process, 'proposal_submission')

    authenticate(client, proponent)
    body = _list(client)

    assert set(body) == {'data', 'pagination', 'filters_applied', 'sort'}
    assert len(body['data']) == 1


@pytest.mark.asyncio
async def test_task_list_filters_applied_echoes_defaults(client, session):
    proponent = await _user(session)

    authenticate(client, proponent)
    body = _list(client)

    assert body['filters_applied'] == {
        'status': [],
        'activity_key': [],
        'phase_order': None,
        'process_id': None,
        'role': None,
        'actionable': False,
        'current_run': True,
        'overdue': False,
    }
    assert body['sort'] == {'by': 'due_date', 'order': 'asc'}


@pytest.mark.asyncio
async def test_task_list_default_pagination(client, session):
    proponent = await _user(session)

    authenticate(client, proponent)
    pagination = _list(client)['pagination']

    assert pagination['page'] == 1
    assert pagination['per_page'] == 20  # noqa: PLR2004


def test_task_list_requires_authentication(client):
    assert client.get('/tasks').status_code == HTTPStatus.UNAUTHORIZED


# --- US4: referências ------------------------------------------------------


@pytest.mark.asyncio
async def test_task_item_process_is_reference(client, session):
    proponent = await _user(session)
    process = await listing_process(
        session, proponent=proponent, title='Método X'
    )
    await add_task(session, process, 'proposal_submission')

    authenticate(client, proponent)
    item = _list(client)['data'][0]

    assert item['process'] == {
        'id': str(process.id),
        'code': process.code,
        'title': 'Método X',
    }
    assert not {'process_id', 'process_code', 'process_title'} & set(item)


@pytest.mark.asyncio
async def test_task_item_phase_is_reference(client, session):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    await add_task(session, process, 'proposal_submission')

    authenticate(client, proponent)
    item = _list(client)['data'][0]

    assert item['phase'] == {'key': 'phase_1_submission_triage', 'order': 1}
    assert not {'phase_key', 'phase_order'} & set(item)


# --- US3: paginação --------------------------------------------------------


async def _bracvam_with_tasks(session, count, **task_kwargs):
    """`count` triagens abertas, uma por processo; o BraCVAM vê todas."""
    proponent = await _user(session)
    return [
        await add_task(
            session,
            await listing_process(session, proponent=proponent),
            'triage_evaluation',
            **task_kwargs,
        )
        for _ in range(count)
    ]


@pytest.mark.asyncio
async def test_task_list_second_page_of_45(client, session, bracvam_user):
    await _bracvam_with_tasks(session, 45)

    authenticate(client, bracvam_user)
    body = _list(client, page=2, per_page=20)

    assert len(body['data']) == 20  # noqa: PLR2004
    assert body['pagination'] == {
        'page': 2,
        'per_page': 20,
        'total_items': 45,
        'total_pages': 3,
        'has_next': True,
        'has_prev': True,
    }


@pytest.mark.asyncio
async def test_task_list_page_beyond_last_is_empty(
    client, session, bracvam_user
):
    await _bracvam_with_tasks(session, 45)

    authenticate(client, bracvam_user)
    body = _list(client, page=5)

    assert body['data'] == []
    assert body['pagination']['total_items'] == 45  # noqa: PLR2004
    assert body['pagination']['has_next'] is False


@pytest.mark.asyncio
async def test_task_list_rejects_per_page_above_100(client, session):
    authenticate(client, await _user(session))

    response = client.get('/tasks', params={'per_page': 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_task_list_rejects_page_zero(client, session):
    authenticate(client, await _user(session))

    response = client.get('/tasks', params={'page': 0})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_task_list_pages_have_no_gaps_or_repeats(
    client, session, bracvam_user
):
    due = _now() + timedelta(days=1)
    tasks = await _bracvam_with_tasks(session, 5, due_date=due)

    authenticate(client, bracvam_user)
    seen = [
        item['id']
        for page in (1, 2, 3)
        for item in _list(client, page=page, per_page=2)['data']
    ]

    assert len(seen) == 5  # noqa: PLR2004
    assert set(seen) == {str(t.id) for t in tasks}


@pytest.mark.asyncio
async def test_task_list_total_ignores_invisible_tasks(client, session):
    owner = await _user(session)
    stranger = await _user(session)
    await add_task(
        session,
        await listing_process(session, proponent=owner),
        'proposal_submission',
    )
    await add_task(
        session,
        await listing_process(session, proponent=stranger),
        'proposal_submission',
    )

    authenticate(client, owner)
    body = _list(client)

    assert body['pagination']['total_items'] == 1


# --- US3: ordenação --------------------------------------------------------


async def _three_due_dates(session):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    now = _now()
    far = await add_task(
        session, process, 'proposal_submission', due_date=now + timedelta(2)
    )
    near = await add_task(
        session, process, 'triage_evaluation', due_date=now + timedelta(1)
    )
    none = await add_task(session, process, 'submission_return_review')
    return far, near, none


@pytest.mark.asyncio
async def test_task_list_default_order_due_date_nulls_last(
    client, session, bracvam_user
):
    far, near, none = await _three_due_dates(session)

    authenticate(client, bracvam_user)
    ids = [item['id'] for item in _list(client)['data']]

    assert ids == [str(near.id), str(far.id), str(none.id)]


@pytest.mark.asyncio
async def test_task_list_desc_keeps_nulls_last(client, session, bracvam_user):
    far, near, none = await _three_due_dates(session)

    authenticate(client, bracvam_user)
    body = _list(client, sort_order='desc')

    assert [item['id'] for item in body['data']] == [
        str(far.id),
        str(near.id),
        str(none.id),
    ]
    assert body['sort'] == {'by': 'due_date', 'order': 'desc'}


@pytest.mark.asyncio
async def test_task_list_sort_by_created_at(client, session, bracvam_user):
    far, near, none = await _three_due_dates(session)
    # Na transação do teste, `now()` é o mesmo para todas as tarefas.
    base = _now()
    near.created_at = base - timedelta(hours=1)
    none.created_at = base - timedelta(hours=2)
    far.created_at = base - timedelta(hours=3)
    await session.commit()

    authenticate(client, bracvam_user)
    body = _list(client, sort_by='created_at')

    assert [item['id'] for item in body['data']] == [
        str(far.id),
        str(none.id),
        str(near.id),
    ]
    assert body['sort'] == {'by': 'created_at', 'order': 'asc'}


@pytest.mark.asyncio
async def test_task_list_rejects_unknown_sort_by(client, session):
    authenticate(client, await _user(session))

    response = client.get('/tasks', params={'sort_by': 'title'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_task_list_rejects_unknown_sort_order(client, session):
    authenticate(client, await _user(session))

    response = client.get('/tasks', params={'sort_order': 'up'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- US3: rodada vigente ---------------------------------------------------


async def _triage_with_two_runs(session):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    first = await add_task(
        session, process, 'triage_evaluation', status='COMPLETED'
    )
    second = await add_task(
        session, process, 'triage_evaluation', run_number=2
    )
    return process, first, second


@pytest.mark.asyncio
async def test_task_list_defaults_to_current_run(
    client, session, bracvam_user
):
    _, _, second = await _triage_with_two_runs(session)

    authenticate(client, bracvam_user)
    body = _list(client)

    assert [item['id'] for item in body['data']] == [str(second.id)]
    assert body['filters_applied']['current_run'] is True


@pytest.mark.asyncio
async def test_task_list_current_run_false_includes_history(
    client, session, bracvam_user
):
    _, first, second = await _triage_with_two_runs(session)

    authenticate(client, bracvam_user)
    body = _list(client, current_run='false')

    assert {item['id'] for item in body['data']} == {
        str(first.id),
        str(second.id),
    }


# --- US3: filtros ----------------------------------------------------------


@pytest.mark.asyncio
async def test_task_list_filters_multiple_status(
    client, session, bracvam_user
):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    ready = await add_task(session, process, 'proposal_submission')
    cancelled = await add_task(
        session, process, 'triage_evaluation', status='CANCELLED'
    )
    await add_task(
        session, process, 'submission_return_review', status='COMPLETED'
    )

    authenticate(client, bracvam_user)
    response = client.get(
        '/tasks', params=[('status', 'READY'), ('status', 'CANCELLED')]
    )

    assert response.status_code == HTTPStatus.OK
    assert {item['id'] for item in response.json()['data']} == {
        str(ready.id),
        str(cancelled.id),
    }


@pytest.mark.asyncio
async def test_task_list_rejects_unknown_status(client, session):
    authenticate(client, await _user(session))

    response = client.get('/tasks', params={'status': 'FOO'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_task_list_filters_multiple_activity_keys(
    client, session, bracvam_user
):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    submission = await add_task(session, process, 'proposal_submission')
    triage = await add_task(session, process, 'triage_evaluation')
    await add_task(session, process, 'submission_return_review')

    authenticate(client, bracvam_user)
    response = client.get(
        '/tasks',
        params=[
            ('activity_key', 'proposal_submission'),
            ('activity_key', 'triage_evaluation'),
        ],
    )

    assert {item['id'] for item in response.json()['data']} == {
        str(submission.id),
        str(triage.id),
    }


@pytest.mark.asyncio
async def test_task_list_filters_phase_order(client, session, bracvam_user):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    await add_task(session, process, 'proposal_submission')
    phase_two = await add_task(session, process, 'assign_group_manager')

    authenticate(client, bracvam_user)
    body = _list(client, phase_order=2)

    assert [item['id'] for item in body['data']] == [str(phase_two.id)]


@pytest.mark.asyncio
async def test_task_list_overdue_only_open_past_due(
    client, session, bracvam_user
):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    now = _now()
    overdue = await add_task(
        session,
        process,
        'proposal_submission',
        due_date=now - timedelta(days=2),
    )
    await add_task(
        session, process, 'triage_evaluation', due_date=now + timedelta(2)
    )
    await add_task(session, process, 'submission_return_review')
    await add_task(
        session,
        process,
        'assign_group_manager',
        status='COMPLETED',
        due_date=now - timedelta(days=2),
    )

    authenticate(client, bracvam_user)
    body = _list(client, overdue='true')

    assert [item['id'] for item in body['data']] == [str(overdue.id)]


@pytest.mark.asyncio
async def test_task_list_keeps_process_and_role_filters(
    client, session, bracvam_user
):
    proponent = await _user(session)
    process = await listing_process(session, proponent=proponent)
    other = await listing_process(session, proponent=proponent)
    submission = await add_task(session, process, 'proposal_submission')
    triage = await add_task(session, process, 'triage_evaluation')
    await add_task(session, other, 'proposal_submission')

    authenticate(client, bracvam_user)
    by_process = _list(client, process_id=str(process.id))
    by_role = _list(client, process_id=str(process.id), role='bracvam')

    assert {i['id'] for i in by_process['data']} == {
        str(submission.id),
        str(triage.id),
    }
    assert [i['id'] for i in by_role['data']] == [str(triage.id)]
