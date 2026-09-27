"""Spec 033, US3 - referências no catálogo institucional e nos usuários."""

from http import HTTPStatus

import pytest
import pytest_asyncio

from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
    INSTITUTIONAL_READ,
    USERS_READ,
)
from tests.api.routers.test_institutional_router import (
    ORIGIN,
    authenticate,
    create_affiliation,
    create_institution,
    create_laboratory,
)
from tests.conftest import _make_rbac_user


@pytest_asyncio.fixture
async def catalog_admin(session):
    return await _make_rbac_user(
        session,
        system_key=None,
        name='Administrador do catálogo',
        codes=(
            INSTITUTIONAL_READ,
            INSTITUTIONAL_CATALOGS_MANAGE,
            INSTITUTIONAL_AFFILIATIONS_MANAGE,
        ),
    )


INSTITUTION_REF_KEYS = {'id', 'name', 'active'}


def _lab_setup(client):
    institution = create_institution(client, 'Fiocruz').json()
    laboratory = create_laboratory(client, institution['id'], 'Lab A')
    assert laboratory.status_code == HTTPStatus.CREATED, laboratory.text
    return institution, laboratory.json()


def test_laboratory_list_and_detail_have_institution_ref(
    client, catalog_admin
):
    authenticate(client, catalog_admin)
    institution, laboratory = _lab_setup(client)

    listed = next(
        item
        for item in client.get('/institutional/laboratories').json()['data']
        if item['id'] == laboratory['id']
    )
    detail = client.get(
        f'/institutional/laboratories/{laboratory["id"]}'
    ).json()

    for item in (listed, detail):
        assert item['institution'] == {
            'id': institution['id'],
            'name': 'Fiocruz',
            'active': True,
        }
        assert 'institution_id' not in item


def test_create_laboratory_response_has_institution_ref(client, catalog_admin):
    authenticate(client, catalog_admin)
    institution, laboratory = _lab_setup(client)

    assert laboratory['institution']['id'] == institution['id']


def test_user_affiliations_have_refs(client, catalog_admin, other_user):
    authenticate(client, catalog_admin)
    institution, laboratory = _lab_setup(client)
    create_affiliation(
        client, other_user.id, institution['id'], laboratory['id']
    )

    [item] = client.get(
        f'/institutional/users/{other_user.id}/affiliations'
    ).json()['data']

    assert item['user'] == {
        'id': str(other_user.id),
        'username': other_user.username,
        'full_name': other_user.full_name,
    }
    assert set(item['institution']) == INSTITUTION_REF_KEYS
    assert item['laboratory']['institution']['id'] == institution['id']
    assert 'user_id' not in item


def test_my_affiliations_laboratory_has_institution(
    client, catalog_admin, other_user
):
    authenticate(client, catalog_admin)
    institution, laboratory = _lab_setup(client)
    create_affiliation(
        client, other_user.id, institution['id'], laboratory['id']
    )

    authenticate(client, other_user)
    [item] = client.get('/institutional/me/affiliations').json()['data']

    assert item['laboratory']['institution'] == {
        'id': institution['id'],
        'name': 'Fiocruz',
        'active': True,
    }


def test_inactive_laboratory_ref_still_listed(
    client, catalog_admin, other_user
):
    authenticate(client, catalog_admin)
    institution, laboratory = _lab_setup(client)
    create_affiliation(
        client, other_user.id, institution['id'], laboratory['id']
    )
    deleted = client.delete(
        f'/institutional/laboratories/{laboratory["id"]}', headers=ORIGIN
    )
    assert deleted.status_code == HTTPStatus.NO_CONTENT

    [item] = client.get(
        f'/institutional/users/{other_user.id}/affiliations'
    ).json()['data']

    assert item['laboratory']['id'] == laboratory['id']
    assert item['laboratory']['active'] is False


@pytest.mark.asyncio
async def test_admin_user_profiles_json_unchanged(client, session):
    reader = await _make_rbac_user(
        session,
        system_key=None,
        name='Leitor de usuários',
        codes=(USERS_READ,),
    )

    authenticate(client, reader)
    body = client.get('/users', params={'search': reader.username}).json()

    [item] = body['data']
    assert item['profiles'] == [
        {
            'id': item['profiles'][0]['id'],
            'name': 'Leitor de usuários',
            'active': True,
        }
    ]
