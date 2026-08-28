from http import HTTPStatus
from uuid import uuid4

import pytest
import pytest_asyncio

from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
    INSTITUTIONAL_READ,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories import (
    InstitutionFactory,
    UserInstitutionalAffiliationFactory,
)

ORIGIN = {'Origin': 'https://testserver'}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


@pytest_asyncio.fixture
async def permission_user(request, session, user):
    permission = Permission(code=request.param, description=request.param)
    profile = AccessProfile(
        name=f'Profile {request.param}', description='profile'
    )
    session.add_all([permission, profile])
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        ),
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()
    return user


@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('get', '/institutional/institutions'),
        ('post', '/institutional/institutions'),
        ('get', '/institutional/me/affiliations'),
        ('get', f'/institutional/users/{uuid4()}/affiliations'),
        ('get', '/institutional/changes'),
    ],
)
def test_institutional_routes_require_authentication(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    'permission_user', [INSTITUTIONAL_READ], indirect=True
)
def test_read_permission_cannot_mutate_catalog_or_affiliations(
    client, permission_user
):
    authenticate(client, permission_user)
    assert (
        client.get('/institutional/institutions').status_code == HTTPStatus.OK
    )
    assert (
        client.post(
            '/institutional/institutions',
            headers=ORIGIN,
            json={'name': 'Denied'},
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        client.post(
            f'/institutional/users/{uuid4()}/affiliations',
            headers=ORIGIN,
            json={'institution_id': str(uuid4())},
        ).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.parametrize(
    'permission_user', [INSTITUTIONAL_CATALOGS_MANAGE], indirect=True
)
def test_catalog_management_does_not_grant_global_read(
    client, permission_user
):
    authenticate(client, permission_user)
    assert (
        client.get('/institutional/institutions').status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        client.get('/institutional/me/affiliations').status_code
        == HTTPStatus.OK
    )


@pytest.mark.parametrize(
    'permission_user', [INSTITUTIONAL_AFFILIATIONS_MANAGE], indirect=True
)
def test_affiliation_management_does_not_grant_catalog_management(
    client, permission_user
):
    authenticate(client, permission_user)
    assert (
        client.post(
            '/institutional/institutions',
            headers=ORIGIN,
            json={'name': 'Denied'},
        ).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.parametrize(
    'permission_user', [INSTITUTIONAL_CATALOGS_MANAGE], indirect=True
)
def test_catalog_management_does_not_grant_affiliation_management(
    client, permission_user, other_user
):
    authenticate(client, permission_user)
    assert (
        client.post(
            f'/institutional/users/{other_user.id}/affiliations',
            headers=ORIGIN,
            json={'institution_id': str(uuid4())},
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        client.delete(
            f'/institutional/users/{other_user.id}/affiliations/{uuid4()}',
            headers=ORIGIN,
        ).status_code
        == HTTPStatus.FORBIDDEN
    )


@pytest.mark.parametrize(
    'permission_user', [INSTITUTIONAL_CATALOGS_MANAGE], indirect=True
)
def test_mutation_requires_trusted_origin_after_permission_check(
    client, permission_user
):
    authenticate(client, permission_user)
    response = client.post(
        '/institutional/institutions', json={'name': 'Origin'}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Invalid origin'}


@pytest.mark.parametrize(
    'permission_user', [INSTITUTIONAL_AFFILIATIONS_MANAGE], indirect=True
)
@pytest.mark.asyncio
async def test_affiliation_manager_cannot_probe_another_users_affiliations(
    client, session, permission_user, other_user
):
    institution = InstitutionFactory()
    affiliation = UserInstitutionalAffiliationFactory(
        user=other_user, institution=institution
    )
    session.add_all([institution, affiliation])
    await session.commit()

    authenticate(client, permission_user)
    known = client.get(f'/institutional/users/{other_user.id}/affiliations')
    unknown = client.get(f'/institutional/users/{uuid4()}/affiliations')

    assert [known.status_code, unknown.status_code] == [
        HTTPStatus.FORBIDDEN,
        HTTPStatus.FORBIDDEN,
    ]
    assert [known.json(), unknown.json()] == [
        {'detail': 'Forbidden'},
        {'detail': 'Forbidden'},
    ]
