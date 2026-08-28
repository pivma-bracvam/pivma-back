from http import HTTPStatus

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

ORIGIN = {'Origin': 'https://testserver'}


@pytest_asyncio.fixture
async def institutional_administrator(session, user):
    permissions = [
        Permission(code=code, description=code)
        for code in (
            INSTITUTIONAL_READ,
            INSTITUTIONAL_CATALOGS_MANAGE,
            INSTITUTIONAL_AFFILIATIONS_MANAGE,
        )
    ]
    profile = AccessProfile(name='Institutional admin', description='admin')
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


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


def create_institution(client, name):
    return client.post(
        '/institutional/institutions', headers=ORIGIN, json={'name': name}
    )


def create_laboratory(client, institution_id, name):
    return client.post(
        '/institutional/laboratories',
        headers=ORIGIN,
        json={'institution_id': institution_id, 'name': name},
    )


def create_affiliation(client, user_id, institution_id, laboratory_id=None):
    payload = {'institution_id': institution_id}
    if laboratory_id is not None:
        payload['laboratory_id'] = laboratory_id
    return client.post(
        f'/institutional/users/{user_id}/affiliations',
        headers=ORIGIN,
        json=payload,
    )


# --- User Story 1: catálogo de instituições e laboratórios ---


def test_create_institution_returns_active_record_with_audit(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    created = create_institution(client, 'Fiocruz')
    assert created.status_code == HTTPStatus.CREATED
    institution = created.json()
    assert institution['active'] is True
    assert institution['created_by'] == str(institutional_administrator.id)


def test_create_laboratory_returns_active_record_linked_to_institution(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UFMG').json()
    created = create_laboratory(client, institution['id'], 'Lab A')
    assert created.status_code == HTTPStatus.CREATED
    laboratory = created.json()
    assert laboratory['active'] is True
    assert laboratory['institution_id'] == institution['id']


def test_list_laboratories_orders_by_institution_then_name(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'PUC').json()
    create_laboratory(client, institution['id'], 'Zebra lab')
    create_laboratory(client, institution['id'], 'Alpha lab')

    listed = client.get('/institutional/laboratories')
    assert listed.status_code == HTTPStatus.OK
    names = [
        item['name']
        for item in listed.json()
        if item['institution_id'] == institution['id']
    ]
    assert names == ['Alpha lab', 'Zebra lab']


def test_update_laboratory_renames_without_moving_institution(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UnB').json()
    laboratory = create_laboratory(client, institution['id'], 'Lab A').json()

    changed = client.patch(
        f'/institutional/laboratories/{laboratory["id"]}',
        headers=ORIGIN,
        json={'name': 'Lab B'},
    )
    assert changed.status_code == HTTPStatus.OK
    assert changed.json()['institution_id'] == institution['id']
    assert changed.json()['name'] == 'Lab B'


def test_deactivate_laboratory_removes_it_from_active_use(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UERJ').json()
    laboratory = create_laboratory(client, institution['id'], 'Lab A').json()

    deactivated = client.delete(
        f'/institutional/laboratories/{laboratory["id"]}', headers=ORIGIN
    )
    assert deactivated.status_code == HTTPStatus.NO_CONTENT
    assert (
        client.get(f'/institutional/laboratories/{laboratory["id"]}').json()[
            'active'
        ]
        is False
    )


def test_catalog_mutations_record_institutional_history(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'Unicamp').json()
    laboratory = create_laboratory(
        client, institution['id'], 'Lab history'
    ).json()
    client.patch(
        f'/institutional/laboratories/{laboratory["id"]}',
        headers=ORIGIN,
        json={'name': 'Lab history renamed'},
    )
    client.delete(
        f'/institutional/laboratories/{laboratory["id"]}', headers=ORIGIN
    )

    changes = client.get('/institutional/changes')
    assert changes.status_code == HTTPStatus.OK
    assert {
        'institution.created',
        'laboratory.created',
        'laboratory.updated',
        'laboratory.deactivated',
    }.issubset({item['action'] for item in changes.json()['items']})


def test_institution_read_returns_404_for_unknown_id(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    response = client.get(
        '/institutional/institutions/00000000-0000-0000-0000-000000000001'
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_institution_create_rejects_blank_name(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    response = create_institution(client, '')
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_institution_create_rejects_duplicate_name_case_insensitive(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    assert create_institution(client, 'UFRJ').status_code == HTTPStatus.CREATED
    duplicate = create_institution(client, 'ufrj')
    assert duplicate.status_code == HTTPStatus.CONFLICT


def test_laboratory_create_rejects_duplicate_name_within_same_institution(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UFPE').json()
    assert (
        create_laboratory(client, institution['id'], 'Lab X').status_code
        == HTTPStatus.CREATED
    )
    duplicate = create_laboratory(client, institution['id'], 'lab x')
    assert duplicate.status_code == HTTPStatus.CONFLICT


def test_history_pagination_matches_full_listing_slice(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    initial_history = client.get('/institutional/changes').json()['items']
    create_institution(client, 'UFBA')
    create_institution(client, 'UFC')

    first_page = client.get('/institutional/changes?offset=0&limit=1')
    second_page = client.get('/institutional/changes?offset=1&limit=1')
    all_changes = client.get('/institutional/changes?offset=0&limit=100')
    assert first_page.status_code == second_page.status_code == HTTPStatus.OK
    assert [*first_page.json()['items'], *second_page.json()['items']] == (
        all_changes.json()['items'][:2]
    )
    assert len(all_changes.json()['items']) == len(initial_history) + 2


def test_history_rejects_limit_above_maximum(
    client, institutional_administrator
):
    authenticate(client, institutional_administrator)
    response = client.get('/institutional/changes?limit=101')
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- User Story 2: vinculação de usuários ---


def test_create_affiliation_composes_users_scope(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'USP').json()
    laboratory = create_laboratory(client, institution['id'], 'Lab').json()

    created = create_affiliation(
        client, other_user.id, institution['id'], laboratory['id']
    )
    assert created.status_code == HTTPStatus.CREATED
    affiliation = created.json()
    assert affiliation['user_id'] == str(other_user.id)
    assert affiliation['active'] is True

    authenticate(client, other_user)
    assert client.get('/institutional/me/affiliations').json() == [
        {
            'id': affiliation['id'],
            'institution': {
                'id': institution['id'],
                'name': 'USP',
                'active': True,
            },
            'laboratory': {
                'id': laboratory['id'],
                'name': 'Lab',
                'active': True,
            },
        }
    ]


def test_self_affiliations_returns_union_of_multiple_active_scopes(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    first_institution = create_institution(client, 'UFV').json()
    second_institution = create_institution(client, 'UFES').json()
    create_affiliation(client, other_user.id, first_institution['id'])
    create_affiliation(client, other_user.id, second_institution['id'])

    authenticate(client, other_user)
    own = client.get('/institutional/me/affiliations')
    assert own.status_code == HTTPStatus.OK
    assert {item['institution']['id'] for item in own.json()} == {
        first_institution['id'],
        second_institution['id'],
    }


def test_admin_lists_affiliations_of_a_specific_user(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UFF').json()
    create_affiliation(client, other_user.id, institution['id'])

    listed = client.get(f'/institutional/users/{other_user.id}/affiliations')
    assert listed.status_code == HTTPStatus.OK
    assert [item['user_id'] for item in listed.json()] == [str(other_user.id)]


def test_deactivated_affiliation_stops_composing_scope_on_next_request(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UFG').json()
    affiliation = create_affiliation(
        client, other_user.id, institution['id']
    ).json()

    authenticate(client, other_user)
    assert client.get('/institutional/me/affiliations').json() == [
        {
            'id': affiliation['id'],
            'institution': {
                'id': institution['id'],
                'name': 'UFG',
                'active': True,
            },
            'laboratory': None,
        }
    ]

    authenticate(client, institutional_administrator)
    deactivated = client.delete(
        f'/institutional/users/{other_user.id}/affiliations'
        f'/{affiliation["id"]}',
        headers=ORIGIN,
    )
    assert deactivated.status_code == HTTPStatus.NO_CONTENT

    authenticate(client, other_user)
    assert client.get('/institutional/me/affiliations').json() == []


def test_correcting_an_affiliation_starts_a_new_traceable_cycle(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'UFPR').json()
    first_cycle = create_affiliation(
        client, other_user.id, institution['id']
    ).json()
    assert (
        client.delete(
            f'/institutional/users/{other_user.id}/affiliations'
            f'/{first_cycle["id"]}',
            headers=ORIGIN,
        ).status_code
        == HTTPStatus.NO_CONTENT
    )

    second_cycle = create_affiliation(client, other_user.id, institution['id'])
    assert second_cycle.status_code == HTTPStatus.CREATED
    assert second_cycle.json()['id'] != first_cycle['id']

    history_targets = {
        item['target_id']
        for item in client.get('/institutional/changes').json()['items']
        if item['action'] in {'affiliation.created', 'affiliation.deactivated'}
    }
    assert {first_cycle['id'], second_cycle.json()['id']}.issubset(
        history_targets
    )


def test_affiliation_rejects_laboratory_from_another_institution(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    first = create_institution(client, 'A').json()
    second = create_institution(client, 'B').json()
    laboratory = create_laboratory(client, first['id'], 'Lab A').json()

    response = create_affiliation(
        client, other_user.id, second['id'], laboratory['id']
    )
    assert response.status_code == HTTPStatus.CONFLICT


def test_affiliation_rejects_unknown_user(client, institutional_administrator):
    authenticate(client, institutional_administrator)
    institution = create_institution(client, 'IFRJ').json()
    response = create_affiliation(
        client, '00000000-0000-0000-0000-000000000002', institution['id']
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_affiliation_rejects_unknown_institution(
    client, institutional_administrator, other_user
):
    authenticate(client, institutional_administrator)
    response = create_affiliation(
        client, other_user.id, '00000000-0000-0000-0000-000000000003'
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
