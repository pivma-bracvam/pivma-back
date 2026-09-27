"""Spec 033, US1 (3e) - etiquetas de amostra no envelope padrão."""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import (
    VALID_CAS,
    sample_process,
    substance_payload,
)

ENVELOPE_KEYS = {'data', 'pagination', 'filters_applied', 'sort'}
ORIGIN = {'Origin': 'https://testserver'}


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


async def _six_labels(session, client):
    """3 laboratórios × 2 substâncias = 6 frascos."""
    ctx = await sample_process(session, lab_count=3)
    authenticate(client, ctx.selector)
    for cas in VALID_CAS[:2]:
        created = client.post(
            f'/processes/{ctx.process_id}/samples',
            json=substance_payload(cas_number=cas),
            headers=ORIGIN,
        )
        assert created.status_code == HTTPStatus.CREATED, created.text
    return ctx


def _labels(client, process_id, **params):
    response = client.get(
        f'/processes/{process_id}/samples/labels', params=params
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest.mark.asyncio
async def test_labels_envelope(session, client):
    ctx = await _six_labels(session, client)

    body = _labels(client, ctx.process_id)

    assert set(body) == ENVELOPE_KEYS
    assert len(body['data']) == 6  # noqa: PLR2004
    assert body['sort'] == {'by': 'laboratory', 'order': 'asc'}


@pytest.mark.asyncio
async def test_labels_second_page(session, client):
    ctx = await _six_labels(session, client)

    body = _labels(client, ctx.process_id, page=2, per_page=4)

    assert len(body['data']) == 2  # noqa: PLR2004
    assert body['pagination']['total_items'] == 6  # noqa: PLR2004
    assert all('qr_svg' not in label for label in body['data'])


@pytest.mark.asyncio
async def test_labels_access_unchanged(session, client):
    ctx = await _six_labels(session, client)

    authenticate(client, ctx.lab_users[0])
    response = client.get(f'/processes/{ctx.process_id}/samples/labels')

    assert response.status_code == HTTPStatus.NOT_FOUND
