from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
import yaml

from pivma.core.authorization import USERS_READ
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    User,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.rbac_factory import (
    AccessProfileFactory,
    UserAccessProfileFactory,
)
from tests.factories.user_factory import UserFactory

DEFAULT_LIMIT = 100
PAGE_LIMIT = 2


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


@pytest_asyncio.fixture
async def listing_reader(session, user):
    permissions = [
        Permission(code=code, description=f'Permission {code}')
        for code in (USERS_READ, 'rbac.read')
    ]
    profile = AccessProfile(
        system_key=None,
        name='User listing reader',
        description='Can list users',
    )
    session.add_all([*permissions, profile])
    await session.flush()
    session.add_all(
        [
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
            for permission in permissions
        ]
        + [UserAccessProfile(user_id=user.id, profile_id=profile.id)]
    )
    await session.commit()
    return user


async def persist_user(session, **overrides) -> User:
    user = UserFactory(password_hash='test-hash', **overrides)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def persist_profile(session, **overrides) -> AccessProfile:
    profile = AccessProfileFactory(**overrides)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def persist_assignment(session, user, profile, *, deleted_at=None):
    assignment = UserAccessProfileFactory(user=user, profile=profile)
    assignment.deleted_at = deleted_at
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


def user_ids(response):
    return [item['id'] for item in response.json()['items']]


def test_list_users_defaults_to_first_page_of_active_accounts(
    client, listing_reader
):
    authenticate(client, listing_reader)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['offset'] == 0
    assert response.json()['limit'] == DEFAULT_LIMIT
    assert response.json()['items']


@pytest.mark.parametrize('active_query', [None, 'true'])
def test_list_users_defaults_to_active_accounts(
    client, deleted_user, listing_reader, active_query
):
    authenticate(client, listing_reader)
    params = {} if active_query is None else {'active': active_query}

    response = client.get('/users', params=params)

    assert response.status_code == HTTPStatus.OK
    assert str(deleted_user.id) not in user_ids(response)
    assert all(item['active'] for item in response.json()['items'])


@pytest.mark.asyncio
async def test_list_users_searches_username_substring(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='Alice-Santos', email='alice.santos@example.com'
    )
    authenticate(client, listing_reader)

    response = client.get('/users', params={'search': 'Santo'})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


@pytest.mark.asyncio
async def test_list_users_searches_email_substring(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='EmailTarget', email='alice.santos@example.com'
    )
    authenticate(client, listing_reader)

    response = client.get('/users', params={'search': 'SANTOS@EXAMPLE'})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


@pytest.mark.asyncio
async def test_list_users_username_search_is_case_insensitive(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='JoaoDaSilva', email='joao@example.com'
    )
    authenticate(client, listing_reader)

    responses = [
        client.get('/users', params={'search': search})
        for search in ('joaodasilva', 'JoaoDaSilva', 'JOAODASILVA')
    ]

    assert [response.status_code for response in responses] == [
        HTTPStatus.OK
    ] * 3
    assert [user_ids(response) for response in responses] == [
        [str(target.id)]
    ] * 3


@pytest.mark.asyncio
async def test_list_users_email_search_is_case_insensitive(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='CaseEmail', email='Joao.Silva@example.com'
    )
    authenticate(client, listing_reader)

    responses = [
        client.get('/users', params={'search': search})
        for search in ('joao.silva@EXAMPLE', 'Joao.Silva@example.com', 'JOAO')
    ]

    assert [response.status_code for response in responses] == [
        HTTPStatus.OK
    ] * 3
    assert [user_ids(response) for response in responses] == [
        [str(target.id)]
    ] * 3


@pytest.mark.asyncio
async def test_list_users_strips_search_outer_spaces(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='TrimmedTarget', email='trimmed@example.com'
    )
    authenticate(client, listing_reader)

    response = client.get('/users', params={'search': '  TrimmedTarget  '})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


@pytest.mark.asyncio
@pytest.mark.parametrize('search', ['', '   '])
async def test_list_users_empty_search_matches_search_omission(
    client, listing_reader, session, search
):
    await persist_user(
        session, username='EmptySearchTarget', email='empty@example.com'
    )
    authenticate(client, listing_reader)

    without_search = client.get('/users')
    with_search = client.get('/users', params={'search': search})

    assert without_search.status_code == HTTPStatus.OK
    assert with_search.status_code == HTTPStatus.OK
    assert user_ids(with_search) == user_ids(without_search)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('search', 'email'),
    [('%', 'literal%percent@example.com'), ('_', 'literal_under@example.com')],
)
async def test_list_users_search_treats_wildcards_as_literals(
    client, listing_reader, session, search, email
):
    target = await persist_user(
        session,
        username=f'Literal{search}Target',
        email=email,
    )
    await persist_user(
        session, username='OrdinaryTarget', email='ordinary@example.com'
    )
    authenticate(client, listing_reader)

    response = client.get('/users', params={'search': search})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


def test_list_users_without_match_returns_empty_page(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get(
        '/users', params={'search': 'does-not-exist', 'offset': 3, 'limit': 7}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'offset': 3, 'limit': 7, 'items': []}


def test_list_users_response_has_only_page_fields(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()) == {'offset', 'limit', 'items'}


def test_list_users_items_have_only_administrative_fields(
    client, listing_reader
):
    authenticate(client, listing_reader)

    response = client.get('/users')

    assert response.status_code == HTTPStatus.OK
    assert all(
        set(item) == {'id', 'username', 'email', 'active'}
        for item in response.json()['items']
    )


def test_list_users_openapi_matches_versioned_contract(client):
    generated = client.get('/openapi.json').json()
    contract_path = (
        Path(__file__).resolve().parents[3]
        / 'specs'
        / '007-admin-user-listing'
        / 'contracts'
        / 'users.openapi.yaml'
    )
    contract = yaml.safe_load(contract_path.read_text())
    generated_operation = generated['paths']['/users']['get']
    contract_operation = contract['paths']['/users']['get']

    assert (
        generated_operation['operationId'] == contract_operation['operationId']
    )
    assert (
        generated_operation['x-required-permission']
        == contract_operation['x-required-permission']
    )

    generated_page = generated['components']['schemas']['AdminUserPage']
    contract_page = contract['components']['schemas']['AdminUserPage']
    assert generated_page['required'] == contract_page['required']
    assert (
        generated_page['properties']['offset']['type']
        == contract_page['properties']['offset']['type']
    )
    assert (
        generated_page['properties']['offset']['minimum']
        == contract_page['properties']['offset']['minimum']
    )
    assert (
        generated_page['properties']['limit']['type']
        == contract_page['properties']['limit']['type']
    )
    assert (
        generated_page['properties']['limit']['minimum']
        == contract_page['properties']['limit']['minimum']
    )
    assert (
        generated_page['properties']['limit']['maximum']
        == contract_page['properties']['limit']['maximum']
    )
    assert (
        generated_page['properties']['items']['type']
        == contract_page['properties']['items']['type']
    )
    assert (
        generated_page['properties']['items']['items']
        == contract_page['properties']['items']['items']
    )

    response_components = contract['components']['responses']
    response_refs = {'401': 'NotAuthenticated', '403': 'Forbidden'}
    for status, component_name in response_refs.items():
        assert status in generated_operation['responses']
        assert (
            generated_operation['responses'][status]['description']
            == (response_components[component_name]['description'])
        )


@pytest.mark.asyncio
async def test_listed_user_id_is_accepted_by_rbac_access_endpoint(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='RbacTarget', email='rbac.target@example.com'
    )
    authenticate(client, listing_reader)

    listing = client.get('/users', params={'search': 'RbacTarget'})
    assert listing.status_code == HTTPStatus.OK
    listed_id = listing.json()['items'][0]['id']
    access = client.get(f'/rbac/users/{listed_id}/access')

    assert listed_id == str(target.id)
    assert access.status_code == HTTPStatus.OK
    assert access.json()['user_id'] == listed_id


@pytest.mark.asyncio
async def test_list_users_limit_restricts_matching_items(
    client, listing_reader, session
):
    for index in range(3):
        await persist_user(
            session,
            username=f'LimitedTarget{index}',
            email=f'limited{index}@example.com',
        )
    authenticate(client, listing_reader)

    response = client.get(
        '/users', params={'search': 'LimitedTarget', 'limit': PAGE_LIMIT}
    )

    assert response.status_code == HTTPStatus.OK
    assert len(response.json()['items']) == PAGE_LIMIT


@pytest.mark.parametrize('limit', [1, 100])
def test_list_users_accepts_valid_limits(client, listing_reader, limit):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'limit': limit})

    assert response.status_code == HTTPStatus.OK
    assert response.json()['limit'] == limit


@pytest.mark.asyncio
async def test_list_users_pages_cover_each_matching_account_once(
    client, listing_reader, session
):
    targets = [
        await persist_user(
            session,
            username=f'PageTarget{index}',
            email=f'page{index}@example.com',
        )
        for index in range(5)
    ]
    authenticate(client, listing_reader)

    pages = [
        client.get(
            '/users',
            params={
                'search': 'PageTarget',
                'offset': offset,
                'limit': PAGE_LIMIT,
            },
        )
        for offset in (0, 2, 4)
    ]
    listed_ids = [item_id for page in pages for item_id in user_ids(page)]

    assert [page.status_code for page in pages] == [HTTPStatus.OK] * 3
    assert listed_ids == [
        str(target.id)
        for target in sorted(
            targets, key=lambda item: (item.username.lower(), item.id)
        )
    ]


@pytest.mark.asyncio
async def test_list_users_orders_by_username_case_insensitively(
    client, listing_reader, session
):
    targets = [
        await persist_user(
            session,
            username=username,
            email=f'{index}@ordering.example.com',
        )
        for index, username in enumerate((
            'OrderTarget-Z',
            'ordertarget-a',
            'OrderTarget-B',
        ))
    ]
    authenticate(client, listing_reader)

    response = client.get('/users', params={'search': 'OrderTarget'})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [
        str(target.id)
        for target in sorted(
            targets, key=lambda item: (item.username.lower(), item.id)
        )
    ]


@pytest.mark.asyncio
async def test_list_users_breaks_case_insensitive_username_ties_by_uuid(
    client, listing_reader, session
):
    first = await persist_user(
        session, username='TieTarget', email='first@tie.example.com'
    )
    first.deleted_at = datetime(2026, 8, 1)
    await session.commit()
    second = await persist_user(
        session, username='tietarget', email='second@tie.example.com'
    )
    second.deleted_at = datetime(2026, 8, 2)
    await session.commit()
    targets = [first, second]
    authenticate(client, listing_reader)

    response = client.get(
        '/users', params={'search': 'TieTarget', 'active': 'false'}
    )

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [
        str(target.id)
        for target in sorted(
            targets, key=lambda item: (item.username.lower(), item.id)
        )
    ]


def test_list_users_active_false_returns_only_inactive_accounts(
    client, deleted_user, listing_reader
):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'active': 'false'})

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'] == [
        {
            'id': str(deleted_user.id),
            'username': deleted_user.username,
            'email': deleted_user.email,
            'active': False,
        }
    ]


@pytest.mark.asyncio
async def test_list_users_profile_filter_matches_active_assignment(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='ProfileTarget', email='profile.target@example.com'
    )
    profile = await persist_profile(session, name='Active profile')
    await persist_assignment(session, target, profile)
    authenticate(client, listing_reader)

    response = client.get('/users', params={'profile_id': str(profile.id)})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


@pytest.mark.asyncio
async def test_list_users_profile_filter_ignores_ended_assignment(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='EndedAssignmentTarget', email='ended@example.com'
    )
    profile = await persist_profile(session, name='Ended assignment profile')
    await persist_assignment(
        session, target, profile, deleted_at=datetime(2026, 8, 1)
    )
    authenticate(client, listing_reader)

    response = client.get('/users', params={'profile_id': str(profile.id)})

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'] == []


@pytest.mark.asyncio
async def test_list_users_profile_filter_ignores_inactive_profile(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='InactiveProfileTarget', email='inactive@example.com'
    )
    profile = await persist_profile(session, name='Inactive profile')
    profile.deleted_at = datetime(2026, 8, 1)
    await session.commit()
    await persist_assignment(session, target, profile)
    authenticate(client, listing_reader)

    response = client.get('/users', params={'profile_id': str(profile.id)})

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'] == []


def test_list_users_unknown_profile_returns_empty_page(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'profile_id': str(UUID(int=999))})

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'] == []


@pytest.mark.asyncio
async def test_profile_filter_ignores_historical_duplicates(
    client, listing_reader, session
):
    target = await persist_user(
        session, username='HistoricalTarget', email='historical@example.com'
    )
    profile = await persist_profile(session, name='Historical profile')
    await persist_assignment(session, target, profile)
    await persist_assignment(
        session, target, profile, deleted_at=datetime(2026, 8, 1)
    )
    authenticate(client, listing_reader)

    response = client.get('/users', params={'profile_id': str(profile.id)})

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


@pytest.mark.asyncio
async def test_list_users_combines_filters_before_pagination(
    client, listing_reader, session
):
    profile = await persist_profile(session, name='Combined profile')
    target = await persist_user(
        session,
        username='CombinedTarget',
        email='combined.target@example.com',
    )
    await persist_assignment(session, target, profile)
    await persist_user(
        session,
        username='CombinedOtherTarget',
        email='other@example.com',
    )
    authenticate(client, listing_reader)

    response = client.get(
        '/users',
        params={
            'search': 'CombinedTarget',
            'active': 'true',
            'profile_id': str(profile.id),
            'offset': 0,
            'limit': 1,
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert user_ids(response) == [str(target.id)]


@pytest.mark.asyncio
async def test_list_users_offset_beyond_matches_returns_empty_page(
    client, listing_reader, session
):
    await persist_user(
        session, username='OffsetTarget', email='offset@example.com'
    )
    authenticate(client, listing_reader)

    response = client.get(
        '/users', params={'search': 'OffsetTarget', 'offset': 2, 'limit': 1}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'] == []


@pytest.mark.parametrize('offset', [-1])
def test_list_users_rejects_negative_offset(client, listing_reader, offset):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'offset': offset})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'items' not in response.json()


def test_list_users_rejects_zero_limit(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'limit': 0})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'items' not in response.json()


def test_list_users_rejects_limit_above_maximum(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'limit': 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'items' not in response.json()


def test_list_users_rejects_invalid_active(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'active': 'not-a-boolean'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'items' not in response.json()


def test_list_users_rejects_malformed_profile_id(client, listing_reader):
    authenticate(client, listing_reader)

    response = client.get('/users', params={'profile_id': 'not-a-uuid'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert 'items' not in response.json()
