"""Spec 033, US4 - listagens e referências documentadas; logs ocultos."""

from http import HTTPStatus

import pytest

from pivma import app
from tests.api.routers.test_rbac_router import authenticate

LISTINGS = [
    '/users',
    '/rbac/permissions',
    '/rbac/profiles',
    '/rbac/changes',
    '/institutional/institutions',
    '/institutional/laboratories',
    '/institutional/users/{user_id}/affiliations',
    '/institutional/me/affiliations',
    '/institutional/changes',
    '/processes/templates',
    '/processes',
    '/processes/{id}/submission-versions',
    '/processes/{id}/timeline',
    '/processes/{process_id}/participants',
    '/processes/{process_id}/participants/history',
    '/processes/{process_id}/participants/invites',
    '/ai-evaluations',
    '/ai-evaluations/references',
    '/processes/{id}/samples/labels',
]
REFERENCES = [
    'UserRef',
    'ProfileRef',
    'InstitutionRef',
    'LaboratoryRef',
    'TemplateRef',
    'ProcessRef',
]


def _openapi():
    return app.openapi()


@pytest.mark.parametrize('path', LISTINGS)
def test_listings_are_documented_as_envelopes(path):
    spec = _openapi()
    operation = spec['paths'][path]['get']
    schema = operation['responses']['200']['content']['application/json'][
        'schema'
    ]
    envelope = spec['components']['schemas'][schema['$ref'].rsplit('/', 1)[-1]]

    assert envelope['type'] == 'object'
    assert {'data', 'pagination', 'filters_applied', 'sort'} <= set(
        envelope['required']
    )
    params = {p['name'] for p in operation.get('parameters', [])}
    assert {'page', 'per_page'} <= params
    assert not {'offset', 'limit', 'size'} & params


@pytest.mark.parametrize('name', REFERENCES)
def test_reference_schemas_have_descriptions(name):
    schema = _openapi()['components']['schemas'][name]

    for field, spec in schema['properties'].items():
        assert spec.get('description'), f'{name}.{field} sem descrição'


def test_admin_logs_hidden_from_openapi():
    paths = _openapi()['paths']

    assert '/admin/logs/operational' not in paths
    assert '/admin/logs/ai' not in paths


@pytest.mark.asyncio
async def test_admin_logs_still_respond(client, ai_eval_admin):
    authenticate(client, ai_eval_admin)

    response = client.get('/admin/logs/operational')

    assert response.status_code == HTTPStatus.OK
