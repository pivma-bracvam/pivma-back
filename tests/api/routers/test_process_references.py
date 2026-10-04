"""Spec 033, US3 - template do processo e laboratório das etiquetas."""

import json
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import ProcessTemplate
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import (
    VALID_CAS,
    sample_process,
    substance_payload,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


async def _proponent_with_process(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    created = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Método'},
    )
    assert created.status_code == HTTPStatus.CREATED, created.text
    template = await session.scalar(
        select(ProcessTemplate).where(
            ProcessTemplate.key == 'pre_validated_method'
        )
    )
    expected = {
        'key': 'pre_validated_method',
        'name': template.name,
        'version': 4,
    }
    return created.json(), expected


@pytest.mark.asyncio
async def test_process_list_has_template_ref(client, session):
    _, expected = await _proponent_with_process(client, session)

    [item] = client.get('/processes').json()['data']

    assert item['template'] == expected
    assert not {'template_key', 'version_number'} & set(item)


@pytest.mark.asyncio
async def test_process_detail_and_create_have_template_ref(client, session):
    created, expected = await _proponent_with_process(client, session)

    detail = client.get(f'/processes/{created["id"]}').json()

    assert created['template'] == expected
    assert detail['template'] == expected


@pytest.mark.asyncio
async def test_label_has_laboratory_ref_without_identity(client, session):
    ctx = await sample_process(session, lab_count=2)
    authenticate(client, ctx.selector)
    payload = substance_payload(cas_number=VALID_CAS[0])
    created = client.post(
        f'/processes/{ctx.process_id}/samples', json=payload, headers=ORIGIN
    )
    assert created.status_code == HTTPStatus.CREATED, created.text

    body = client.get(f'/processes/{ctx.process_id}/samples/labels').json()

    lab_ids = {str(lab.id) for lab in ctx.labs}
    for label in body['data']:
        assert label['laboratory']['id'] in lab_ids
        assert set(label['laboratory']['institution']) == {
            'id',
            'name',
            'active',
        }
        assert not {'laboratory_id', 'laboratory_name'} & set(label)
    blob = json.dumps(body)
    assert payload['chemical_name'] not in blob
    assert payload['cas_number'] not in blob
