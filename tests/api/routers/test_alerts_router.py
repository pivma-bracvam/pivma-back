"""Caixa de alerts: listagem, contador e leitura (Spec 047, US2)."""

from datetime import datetime, timedelta
from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from pivma.core.database.models import Alert, AuditEvent
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.alert_factory import make_alert, make_process
from tests.factories.collection_template_factory import authenticate

BASE = datetime(2026, 11, 21, 12, 0)
UNTRUSTED = {'Origin': 'https://evil.test'}
LAST_PAGE_ITEMS = 5  # 25 alerts, 10 por página


def _headers(user):
    token = create_access_token(user.id, Settings().JWT_SECRET_KEY)
    return {'Authorization': f'Bearer {token}'}


def _list(client, user, **params):
    response = client.get('/alerts', params=params, headers=_headers(user))
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest_asyncio.fixture
async def process(session):
    return await make_process(session)


@pytest.mark.asyncio
async def test_lists_only_own_alerts_newest_first(
    client, session, user, other_user, process
):
    old = await make_alert(session, user, process, created_at=BASE)
    new = await make_alert(
        session, user, process, created_at=BASE + timedelta(hours=1)
    )
    await make_alert(session, other_user, process, created_at=BASE)

    body = _list(client, user)

    assert [item['id'] for item in body['data']] == [str(new.id), str(old.id)]
    assert body['sort'] == {'by': 'created_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_same_created_at_breaks_tie_by_id_desc(
    client, session, user, process
):
    """Research R8."""
    first = await make_alert(session, user, process, created_at=BASE)
    second = await make_alert(session, user, process, created_at=BASE)

    body = _list(client, user)

    expected = sorted([first.id, second.id], reverse=True)
    assert [UUID(item['id']) for item in body['data']] == expected


@pytest.mark.asyncio
async def test_unread_true_returns_only_unread(client, session, user, process):
    unread = await make_alert(session, user, process)
    await make_alert(session, user, process, read_at=BASE)

    body = _list(client, user, unread='true')

    assert [item['id'] for item in body['data']] == [str(unread.id)]
    assert body['filters_applied'] == {'unread': True}


@pytest.mark.asyncio
async def test_unread_false_returns_only_read(client, session, user, process):
    await make_alert(session, user, process)
    read = await make_alert(session, user, process, read_at=BASE)

    body = _list(client, user, unread='false')

    assert [item['id'] for item in body['data']] == [str(read.id)]


@pytest.mark.asyncio
async def test_unread_count_ignores_filter_and_page(
    client, session, user, process
):
    """FR-013, SC-003."""
    unread = 3
    for _ in range(unread):
        await make_alert(session, user, process)
    await make_alert(session, user, process, read_at=BASE)

    for params in ({}, {'unread': 'false'}, {'per_page': 1}, {'page': 2}):
        assert _list(client, user, **params)['unread_count'] == unread


@pytest.mark.asyncio
async def test_pagination_envelope(client, session, user, process):
    for i in range(25):
        await make_alert(
            session, user, process, created_at=BASE + timedelta(minutes=i)
        )

    body = _list(client, user, per_page=10, page=3)

    assert len(body['data']) == LAST_PAGE_ITEMS
    assert body['pagination'] == {
        'page': 3,
        'per_page': 10,
        'total_items': 25,
        'total_pages': 3,
        'has_next': False,
        'has_prev': True,
    }


@pytest.mark.asyncio
async def test_page_beyond_last_is_empty_with_count(
    client, session, user, process
):
    await make_alert(session, user, process)

    body = _list(client, user, page=5)

    assert body['data'] == []
    assert body['unread_count'] == 1


@pytest.mark.asyncio
async def test_empty_inbox(client, user):
    body = _list(client, user)

    assert body['data'] == []
    assert body['unread_count'] == 0


@pytest.mark.asyncio
async def test_target_serialization_by_type(client, session, user, process):
    task_id = uuid4()
    await make_alert(
        session,
        user,
        process,
        target_type='task',
        target_id=task_id,
        created_at=BASE + timedelta(hours=1),
    )
    await make_alert(
        session,
        user,
        process,
        kind='structure_approved',
        target_type='process',
        created_at=BASE,
    )

    task_item, process_item = _list(client, user)['data']

    assert task_item['target'] == {
        'type': 'task',
        'process_id': str(process.id),
        'id': str(task_id),
    }
    assert process_item['target'] == {
        'type': 'process',
        'process_id': str(process.id),
        'id': None,
    }


@pytest.mark.asyncio
async def test_mark_read_sets_read_at_and_lowers_count(
    client, session, user, process
):
    """FR-014."""
    alert = await make_alert(session, user, process)
    await make_alert(session, user, process)

    response = client.post(f'/alerts/{alert.id}/read', headers=_headers(user))

    assert response.status_code == HTTPStatus.OK
    assert response.json()['id'] == str(alert.id)
    assert response.json()['read_at'] is not None
    assert _list(client, user)['unread_count'] == 1


@pytest.mark.asyncio
async def test_mark_read_again_keeps_original_read_at(
    client, session, user, process
):
    """FR-014."""
    alert = await make_alert(session, user, process, read_at=BASE)

    response = client.post(f'/alerts/{alert.id}/read', headers=_headers(user))

    assert response.status_code == HTTPStatus.OK
    assert response.json()['read_at'] == BASE.isoformat()


@pytest.mark.asyncio
async def test_mark_read_of_other_users_alert_is_not_found(
    client, session, user, other_user, process
):
    """FR-016."""
    alert = await make_alert(session, other_user, process)

    response = client.post(f'/alerts/{alert.id}/read', headers=_headers(user))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'
    await session.refresh(alert)
    assert alert.read_at is None


@pytest.mark.asyncio
async def test_mark_read_of_missing_alert_is_not_found(client, user):
    response = client.post(f'/alerts/{uuid4()}/read', headers=_headers(user))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_mark_read_with_invalid_id_is_validation_error(client, user):
    response = client.post('/alerts/nao-e-uuid/read', headers=_headers(user))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'


@pytest.mark.asyncio
async def test_per_page_above_limit_is_validation_error(client, user):
    response = client.get(
        '/alerts', params={'per_page': 101}, headers=_headers(user)
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'validation_error'


@pytest.mark.asyncio
async def test_read_all_marks_only_own_unread(
    client, session, user, other_user, process
):
    """FR-015."""
    for _ in range(3):
        await make_alert(session, user, process)
    await make_alert(session, user, process, read_at=BASE)
    foreign = await make_alert(session, other_user, process)

    response = client.post('/alerts/read-all', headers=_headers(user))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'updated': 3}
    assert _list(client, user)['unread_count'] == 0
    await session.refresh(foreign)
    assert foreign.read_at is None


@pytest.mark.asyncio
async def test_read_all_without_unread_updates_nothing(
    client, session, user, process
):
    await make_alert(session, user, process, read_at=BASE)

    response = client.post('/alerts/read-all', headers=_headers(user))

    assert response.json() == {'updated': 0}


def test_list_requires_session(client):
    """FR-017."""
    response = client.get('/alerts')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail']['code'] == 'not_authenticated'


@pytest.mark.parametrize(
    'path', [f'/alerts/{uuid4()}/read', '/alerts/read-all']
)
def test_writes_require_session(client, path):
    """FR-017."""
    response = client.post(path)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail']['code'] == 'not_authenticated'


@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['read', 'read-all'])
async def test_cookie_writes_require_trusted_origin(
    client, session, user, process, route
):
    """FR-017."""
    alert = await make_alert(session, user, process)
    path = (
        f'/alerts/{alert.id}/read' if route == 'read' else '/alerts/read-all'
    )
    authenticate(client, user)

    response = client.post(path, headers=UNTRUSTED)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'invalid_origin'
    await session.refresh(alert)
    assert alert.read_at is None


@pytest.mark.asyncio
async def test_mark_read_records_no_timeline_event(
    client, session, user, process
):
    """FR-019: ler é estado pessoal, fora da linha do tempo."""
    alert = await make_alert(session, user, process)
    count = select(func.count()).select_from(AuditEvent)
    before = await session.scalar(count)

    client.post(f'/alerts/{alert.id}/read', headers=_headers(user))
    client.post('/alerts/read-all', headers=_headers(user))

    assert await session.scalar(count) == before
    refreshed = await session.get(Alert, alert.id)
    await session.refresh(refreshed)
    assert refreshed.updated_by == user.id
