"""O proponente acompanha a triagem sem saber quem avaliou (Spec 049, US1)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import Decision
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_return_review import (
    ORIGIN,
    VALUES,
    _created_process,
    _save_review,
)
from tests.factories.alert_factory import same_profile_user

DECISION_EVENTS = {
    'APPROVED': 'TRIAGE_APPROVED',
    'REJECTED': 'TRIAGE_REJECTED',
    'NEEDS_REVISION': 'REVISION_REQUESTED',
}


def _submit(client, pid):
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text


def _decide(client, pid, outcome, justification='Justificativa da triagem.'):
    return client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': outcome, 'justification': justification},
        headers=ORIGIN,
    )


def _timeline(client, pid, **params):
    response = client.get(
        f'/processes/{pid}/timeline', params={'per_page': 100, **params}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response


def _of_type(response, event_type):
    return [
        e for e in response.json()['data'] if e['event_type'] == event_type
    ]


async def _decided(client, session, triador, outcome, *, reviews=False):
    proponent, pid = await _created_process(client, session)
    _submit(client, pid)
    authenticate(client, triador)
    if reviews:
        saved = _save_review(client, pid, 'method_title', 'Rever o título.')
        assert saved.status_code == HTTPStatus.OK, saved.text
    decision = _decide(client, pid, outcome)
    assert decision.status_code == HTTPStatus.OK, decision.text
    authenticate(client, proponent)
    return proponent, pid


@pytest.mark.asyncio
async def test_proponent_sees_rejection_without_author(
    client, session, bracvam_user
):
    _, pid = await _decided(client, session, bracvam_user, 'REJECTED')

    response = _timeline(client, pid)

    [rejected] = _of_type(response, 'TRIAGE_REJECTED')
    assert rejected['context_data']['justification'] == (
        'Justificativa da triagem.'
    )
    assert rejected['user_id'] is None
    assert str(bracvam_user.id) not in response.text


@pytest.mark.asyncio
async def test_proponent_sees_revision_request_without_author(
    client, session, bracvam_user
):
    _, pid = await _decided(client, session, bracvam_user, 'NEEDS_REVISION')

    response = _timeline(client, pid)

    [requested] = _of_type(response, 'REVISION_REQUESTED')
    assert requested['context_data']['justification'] == (
        'Justificativa da triagem.'
    )
    assert requested['user_id'] is None
    [opened] = _of_type(response, 'RETURN_REVIEW_OPENED')
    assert opened['user_id'] is None


@pytest.mark.asyncio
async def test_proponent_timeline_omits_field_reviews_and_counts_visible(
    client, session, bracvam_user
):
    """FR-005 e FR-009: o total conta só o que o proponente recebe."""
    _, pid = await _decided(
        client, session, bracvam_user, 'NEEDS_REVISION', reviews=True
    )

    response = _timeline(client, pid)

    assert _of_type(response, 'FIELD_REVIEWED') == []
    body = response.json()
    assert body['pagination']['total_items'] == len(body['data'])


@pytest.mark.asyncio
async def test_proponent_cannot_save_field_reviews(client, session):
    _, pid = await _created_process(client, session)
    _submit(client, pid)

    response = _save_review(client, pid, 'method_title', 'Auto-parecer.')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'


@pytest.mark.asyncio
async def test_proponent_cannot_decide_triage(client, session):
    _, pid = await _created_process(client, session)
    _submit(client, pid)

    response = _decide(client, pid, 'APPROVED')

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['detail']['code'] == 'forbidden'
    decisions = await session.scalars(
        select(Decision).where(Decision.process_instance_id == pid)
    )
    assert list(decisions) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', sorted(DECISION_EVENTS))
async def test_bracvam_keeps_triage_author_and_field_reviews(
    client, session, bracvam_user, outcome
):
    """SC-005: quem tem `triage.review` continua vendo o autor."""
    _, pid = await _decided(
        client, session, bracvam_user, outcome, reviews=True
    )
    authenticate(client, bracvam_user)

    response = _timeline(client, pid)

    [decided] = _of_type(response, DECISION_EVENTS[outcome])
    assert decided['user_id'] == str(bracvam_user.id)
    [reviewed] = _of_type(response, 'FIELD_REVIEWED')
    assert reviewed['user_id'] == str(bracvam_user.id)


@pytest.mark.asyncio
async def test_proponent_with_triage_review_sees_triage_author(
    client, session, bracvam_user
):
    """Edge case: o perfil com `triage.review` libera o autor."""
    await bootstrap_all_templates(session)
    proponent = await same_profile_user(session, bracvam_user)
    authenticate(client, proponent)
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Processo'},
        headers=ORIGIN,
    ).json()['id']
    _submit(client, pid)
    authenticate(client, bracvam_user)
    assert _decide(client, pid, 'APPROVED').status_code == HTTPStatus.OK
    authenticate(client, proponent)

    [approved] = _of_type(_timeline(client, pid), 'TRIAGE_APPROVED')

    assert approved['user_id'] == str(bracvam_user.id)
