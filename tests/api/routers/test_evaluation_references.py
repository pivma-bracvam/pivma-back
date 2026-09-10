# ruff: noqa: PLR2004
"""API — referências normativas e impacto (Spec 013, FR-007/014/015)."""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.ai_eval_helpers import TRUSTED_ORIGIN
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


def _create_reference(client, *, identifier='OECD 442D'):
    return client.post(
        '/ai-evaluations/references',
        json={
            'identifier': identifier,
            'label': 'OECD Test Guideline 442D',
            'version_label': '2018',
        },
        headers=TRUSTED_ORIGIN,
    )


@pytest.mark.asyncio
async def test_create_list_and_duplicate_reference(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)

    created = _create_reference(client)
    assert created.status_code == HTTPStatus.CREATED
    ref_id = created.json()['id']

    listed = client.get('/ai-evaluations/references')
    assert listed.status_code == HTTPStatus.OK
    assert any(r['id'] == ref_id for r in listed.json())

    dup = _create_reference(client)
    assert dup.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_reference_impact_lists_versions_using_it(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)

    ref_id = _create_reference(client).json()['id']

    definition_id = client.post(
        '/ai-evaluations',
        json={
            'name': 'Verificação com referência',
            'mode': 'simple',
            'objective': 'Avaliar contra a diretriz.',
        },
        headers=TRUSTED_ORIGIN,
    ).json()['id']
    patched = client.patch(
        f'/ai-evaluations/{definition_id}/versions/1',
        json={'references': [ref_id]},
        headers=TRUSTED_ORIGIN,
    )
    assert patched.status_code == HTTPStatus.OK

    impact = client.get(f'/ai-evaluations/references/{ref_id}/impact')
    assert impact.status_code == HTTPStatus.OK
    body = impact.json()
    assert any(
        v['definition_id'] == definition_id and v['version_number'] == 1
        for v in body['evaluation_versions']
    )
    assert body['runs_count'] == 0


@pytest.mark.asyncio
async def test_reference_write_requires_manage_permission(
    client, ai_eval_admin, session
):
    await bootstrap_all_templates(session)
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    resp = _create_reference(client)
    assert resp.status_code == HTTPStatus.FORBIDDEN
