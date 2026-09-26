# ruff: noqa: PLR2004
"""Jornada: a triagem pede revisão, o proponente revisa e o BraCVAM aprova
(Spec 030, US4)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from pivma.core.database.models import Phase
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)

FORM = '/processes/{pid}/activities/proposal_submission/form'


def _make_bracvam(client, username):
    user = sign_up(client, username)
    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    granted = client.post(
        f'/rbac/users/{user["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)


def _decide(client, pid, outcome, justification):
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': outcome, 'justification': justification},
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest.mark.asyncio
async def test_triage_revision_then_resubmission_then_approval(
    journey_client, session, monkeypatch
):
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    _make_bracvam(client, 'triador')

    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Método'},
    ).json()['id']
    client.post(FORM.format(pid=pid), json={'values': {'method_title': 'V1'}})
    log_out(client)

    log_in(client, 'triador')
    decision = _decide(client, pid, 'NEEDS_REVISION', 'Faltam controles.')
    assert decision['return_review_run'] == 1
    log_out(client)

    log_in(client, 'proponente')
    review = client.get(f'/processes/{pid}/return-review').json()
    assert review['triage_decision']['justification'] == 'Faltam controles.'
    revise = client.post(
        f'/processes/{pid}/return-review', json={'choice': 'REVISE'}
    )
    assert revise.status_code == HTTPStatus.OK, revise.text
    resubmit = client.post(
        FORM.format(pid=pid), json={'values': {'method_title': 'V2'}}
    )
    assert resubmit.json()['run_number'] == 2
    log_out(client)

    log_in(client, 'triador')
    assert _decide(client, pid, 'APPROVED', 'Ok.')['process_status'] == 'OPEN'

    assert client.get(f'/processes/{pid}').json()['status'] == 'OPEN'
    phase_1 = await session.scalar(
        select(Phase)
        .where(Phase.process_instance_id == pid, Phase.order_index == 1)
        .execution_options(populate_existing=True)
    )
    assert phase_1.status == 'COMPLETED'
