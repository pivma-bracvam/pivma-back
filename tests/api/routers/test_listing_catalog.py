"""Spec 033, US1 (3a) - listagens do catálogo e do RBAC no envelope padrão."""

from http import HTTPStatus

import pytest
import pytest_asyncio

from pivma.core.authorization import INSTITUTIONAL_READ, RBAC_READ, USERS_READ
from pivma.core.database.models import InstitutionalChange, RbacChange
from tests.api.routers.test_rbac_router import authenticate
from tests.conftest import _make_rbac_user
from tests.factories.institutional_factory import (
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
)
from tests.factories.user_factory import UserFactory

ENVELOPE_KEYS = {'data', 'pagination', 'filters_applied', 'sort'}


@pytest_asyncio.fixture
async def reader(session):
    """Lê usuários, RBAC e catálogo institucional."""
    return await _make_rbac_user(
        session,
        system_key=None,
        name='Leitor do catálogo',
        codes=(USERS_READ, RBAC_READ, INSTITUTIONAL_READ),
    )


def _get(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


def _assert_envelope(body, *, sort, filters):
    assert set(body) == ENVELOPE_KEYS
    assert body['pagination']['page'] == 1
    assert body['pagination']['per_page'] == 20  # noqa: PLR2004
    assert body['sort'] == sort
    assert body['filters_applied'] == filters


async def _affiliated_user(session, count=1):
    user = UserFactory()
    institution = InstitutionFactory()
    session.add_all([user, institution])
    await session.commit()
    for _ in range(count):
        laboratory = LaboratoryFactory(institution=institution)
        session.add(laboratory)
        await session.commit()
        session.add(
            UserInstitutionalAffiliationFactory(
                user=user, institution=institution, laboratory=laboratory
            )
        )
        await session.commit()
    return user


@pytest.mark.asyncio
async def test_users_list_envelope(client, reader):
    authenticate(client, reader)

    _assert_envelope(
        _get(client, '/users'),
        sort={'by': 'username', 'order': 'asc'},
        filters={'search': None, 'active': True, 'profile_id': None},
    )


@pytest.mark.asyncio
async def test_users_list_second_page_with_search(client, session, reader):
    session.add_all([UserFactory(username=f'busca{i:02}') for i in range(25)])
    await session.commit()

    authenticate(client, reader)
    body = _get(client, '/users', search='busca', page=2, per_page=20)

    assert len(body['data']) == 5  # noqa: PLR2004
    assert body['pagination']['total_items'] == 25  # noqa: PLR2004
    assert body['filters_applied']['search'] == 'busca'


@pytest.mark.asyncio
async def test_rbac_permissions_envelope(client, reader):
    authenticate(client, reader)

    _assert_envelope(
        _get(client, '/rbac/permissions'),
        sort={'by': 'code', 'order': 'asc'},
        filters={},
    )


@pytest.mark.asyncio
async def test_rbac_profiles_envelope(client, reader):
    authenticate(client, reader)

    _assert_envelope(
        _get(client, '/rbac/profiles'),
        sort={'by': 'name', 'order': 'asc'},
        filters={},
    )


@pytest.mark.asyncio
async def test_rbac_changes_envelope_and_page(client, session, reader):
    for index in range(2):
        change = RbacChange(
            action=f'profile.created.{index}',
            target_type='profile',
            target_id=reader.id,
        )
        change.set_creation_audit(reader.id)
        session.add(change)
    await session.commit()

    authenticate(client, reader)
    body = _get(client, '/rbac/changes', page=2, per_page=1)

    assert len(body['data']) == 1
    assert body['pagination']['has_prev'] is True
    assert body['sort'] == {'by': 'occurred_at', 'order': 'desc'}


@pytest.mark.asyncio
async def test_institutions_envelope(client, reader):
    authenticate(client, reader)

    _assert_envelope(
        _get(client, '/institutional/institutions'),
        sort={'by': 'name', 'order': 'asc'},
        filters={},
    )


@pytest.mark.asyncio
async def test_laboratories_envelope(client, reader):
    authenticate(client, reader)

    _assert_envelope(
        _get(client, '/institutional/laboratories'),
        sort={'by': 'institution', 'order': 'asc'},
        filters={},
    )


@pytest.mark.asyncio
async def test_user_affiliations_envelope(client, session, reader):
    user = await _affiliated_user(session)

    authenticate(client, reader)
    body = _get(client, f'/institutional/users/{user.id}/affiliations')

    _assert_envelope(
        body, sort={'by': 'created_at', 'order': 'desc'}, filters={}
    )
    assert len(body['data']) == 1


@pytest.mark.asyncio
async def test_my_affiliations_envelope(client, session):
    user = await _affiliated_user(session, count=2)

    authenticate(client, user)
    body = _get(client, '/institutional/me/affiliations')

    _assert_envelope(
        body, sort={'by': 'created_at', 'order': 'desc'}, filters={}
    )
    assert len(body['data']) == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_institutional_changes_envelope_and_page(
    client, session, reader
):
    for index in range(2):
        change = InstitutionalChange(
            action=f'institution.created.{index}',
            target_type='institution',
            target_id=reader.id,
        )
        change.set_creation_audit(reader.id)
        session.add(change)
    await session.commit()

    authenticate(client, reader)
    body = _get(client, '/institutional/changes', page=2, per_page=1)

    assert len(body['data']) == 1
    assert body['pagination']['has_prev'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'path',
    [
        '/users',
        '/rbac/permissions',
        '/rbac/profiles',
        '/rbac/changes',
        '/institutional/institutions',
        '/institutional/laboratories',
        '/institutional/users/{user_id}/affiliations',
        '/institutional/me/affiliations',
        '/institutional/changes',
    ],
)
async def test_catalog_lists_reject_per_page_above_100(client, reader, path):
    authenticate(client, reader)

    response = client.get(
        path.format(user_id=reader.id), params={'per_page': 101}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
