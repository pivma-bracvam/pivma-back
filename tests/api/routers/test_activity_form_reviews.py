"""`reviews` de `GET .../form` só traz pareceres decididos (Spec 049, US2)."""

from http import HTTPStatus

import pytest

from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_return_review import (
    ORIGIN,
    VALUES,
    _ai_return,
    _choose,
    _created_process,
    _form,
    _revised,
    _save_review,
    _triage_decides_return,
)


async def _reviews_in_draft(client, session, triador):
    """Submissão enviada e um parecer salvo, sem decisão da triagem."""
    proponent, pid = await _created_process(client, session)
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    authenticate(client, triador)
    saved = _save_review(client, pid, 'method_title', 'Rever o título.')
    assert saved.status_code == HTTPStatus.OK, saved.text
    return proponent, pid


@pytest.mark.asyncio
async def test_proponent_gets_no_reviews_before_decision(
    client, session, bracvam_user
):
    proponent, pid = await _reviews_in_draft(client, session, bracvam_user)
    authenticate(client, proponent)

    assert _form(client, pid)['reviews'] == {}


@pytest.mark.asyncio
async def test_triage_reads_own_draft_reviews(client, session, bracvam_user):
    _, pid = await _reviews_in_draft(client, session, bracvam_user)

    reviews = _form(client, pid)['reviews']

    assert reviews['method_title']['comments'] == 'Rever o título.'


@pytest.mark.asyncio
async def test_proponent_gets_reviews_after_decision_without_reviewer(
    client, session, bracvam_user
):
    proponent, pid = await _reviews_in_draft(client, session, bracvam_user)
    _triage_decides_return(client, pid, proponent, bracvam_user, None, {})

    response = client.get(
        f'/processes/{pid}/activities/proposal_submission/form',
        params={'run_number': 1},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    parecer = response.json()['reviews']['method_title']
    assert parecer['status'] == 'NAO_CONFORME'
    assert parecer['comments'] == 'Rever o título.'
    assert str(bracvam_user.id) not in response.text


@pytest.mark.asyncio
async def test_proponent_gets_no_reviews_of_triage_opened_by_contest(
    client, session, ai_eval_admin, fake_provider, bracvam_user
):
    del fake_provider
    proponent, pid, _ = await _ai_return(client, session, ai_eval_admin)
    assert _choose(client, pid, 'CONTEST_AI').status_code == HTTPStatus.OK
    authenticate(client, bracvam_user)
    saved = _save_review(client, pid, 'method_title', 'Ainda em edição.')
    assert saved.status_code == HTTPStatus.OK, saved.text

    authenticate(client, proponent)

    assert _form(client, pid, run_number=1)['reviews'] == {}


@pytest.mark.asyncio
async def test_previous_reviews_unchanged_after_revision(
    client, session, bracvam_user
):
    """Regressão da Spec 046."""
    _, pid = await _revised(
        client, session, bracvam_user, {'method_title': 'Rever.'}
    )

    previous = _form(client, pid)['previous_reviews']

    assert previous['method_title']['comments'] == 'Rever.'
