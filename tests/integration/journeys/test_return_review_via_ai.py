"""Jornada: a IA reprova, o proponente contesta e o BraCVAM aprova
(Spec 030, US4)."""

from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.bootstrap_system import BRACVAM_PROFILE_ID
from pivma.core import pre_evaluation_service as svc
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.integration.journeys.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    bootstrap_fresh_deploy,
    log_in,
    log_out,
    sign_up,
)


@pytest.mark.asyncio
async def test_ai_rejection_contested_then_approved(
    journey_client, session, monkeypatch, fake_provider
):
    del fake_provider
    client = journey_client
    await bootstrap_fresh_deploy(session, monkeypatch)
    triador = sign_up(client, 'triador')

    log_in(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    granted = client.post(
        f'/rbac/users/{triador["id"]}/profiles/{BRACVAM_PROFILE_ID}'
    )
    assert granted.status_code == HTTPStatus.CREATED, granted.text
    log_out(client)

    sign_up(client, 'proponente')
    log_in(client, 'proponente')
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK, result['body']
    pid = result['process_id']
    await svc._execute(
        session, UUID(result['body']['pre_evaluation']['run_id'])
    )

    review = client.get(f'/processes/{pid}/return-review').json()
    assert review['source'] == 'AI_PRE_EVALUATION'
    assert review['ai_pre_evaluation']['consolidated_result'] == 'negative'
    contest = client.post(
        f'/processes/{pid}/return-review',
        json={'choice': 'CONTEST_AI', 'justification': 'A IA errou.'},
    )
    assert contest.status_code == HTTPStatus.OK, contest.text
    log_out(client)

    log_in(client, 'triador')
    decision = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'Aprovado.'},
    )
    assert decision.status_code == HTTPStatus.OK, decision.text
    assert decision.json()['process_status'] == 'OPEN'
