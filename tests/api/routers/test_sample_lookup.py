"""Consulta de sugestões pelo CAS no PubChem (Spec 040, US2)."""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import StudySubstance
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import _user, sample_process


def lookup(client, process_id, cas='50-00-0'):
    return client.get(
        f'/processes/{process_id}/samples/lookup', params={'cas': cas}
    )


async def selector_ready(session, client):
    ctx = await sample_process(session, lab_count=1)
    authenticate(client, ctx.selector)
    return ctx


@pytest.mark.asyncio
async def test_known_cas_returns_suggestions_and_writes_nothing(
    session, client, fake_pubchem
):
    ctx = await selector_ready(session, client)
    fake_pubchem()

    response = lookup(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json() == {
        'cas_number': '50-00-0',
        'source': 'pubchem',
        'pubchem_cid': 712,
        'source_url': 'https://pubchem.ncbi.nlm.nih.gov/compound/712',
        'chemical_name': 'Formaldehyde',
        'iupac_name': 'formaldehyde',
        'ghs_hazard_pictograms': ['GHS05', 'GHS06', 'GHS08'],
    }
    count = await session.scalar(
        select(func.count()).select_from(StudySubstance)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_invalid_cas_returns_422_without_calling_pubchem(
    session, client, fake_pubchem
):
    ctx = await selector_ready(session, client)
    handler = fake_pubchem()

    response = lookup(client, ctx.process_id, cas='50-00-1')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['code'] == 'invalid_cas'
    assert handler.calls == []


@pytest.mark.asyncio
async def test_unknown_cas_returns_404_compound_not_found(
    session, client, fake_pubchem
):
    ctx = await selector_ready(session, client)
    fake_pubchem(known=False)

    response = lookup(client, ctx.process_id)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'compound_not_found'


@pytest.mark.asyncio
@pytest.mark.parametrize('fail', ['status', 'json', 'timeout'])
async def test_pubchem_failure_returns_503(
    session, client, fake_pubchem, fail
):
    ctx = await selector_ready(session, client)
    fake_pubchem(fail=fail)

    response = lookup(client, ctx.process_id)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()['detail']['code'] == 'lookup_unavailable'


@pytest.mark.asyncio
async def test_compound_without_ghs_returns_empty_pictograms(
    session, client, fake_pubchem
):
    ctx = await selector_ready(session, client)
    fake_pubchem(ghs=False)

    response = lookup(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK
    assert response.json()['ghs_hazard_pictograms'] == []


@pytest.mark.asyncio
async def test_lookup_denied_to_other_roles(
    session, client, fake_pubchem, ai_eval_admin
):
    ctx = await sample_process(session, lab_count=1)
    handler = fake_pubchem()

    expected = [
        (ctx.lab_users[0], HTTPStatus.NOT_FOUND),
        (await _user(session), HTTPStatus.NOT_FOUND),
        (ai_eval_admin, HTTPStatus.FORBIDDEN),
    ]
    for user, status in expected:
        authenticate(client, user)
        assert lookup(client, ctx.process_id).status_code == status
    assert handler.calls == []
