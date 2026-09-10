# ruff: noqa: PLR2004
"""API — métricas de concordância humano–IA (Spec 013, US4)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import EvaluationRunItem
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}


@pytest.mark.asyncio
async def test_agreement_metrics_reflect_recorded_feedback(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    await svc._execute(session, run_id)

    item = await session.scalar(
        select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
    )

    authenticate(client, ai_eval_admin)
    client.post(
        f'/processes/{result["process_id"]}/pre-evaluation/{run_id}/feedback',
        json={'items': [{'item_id': str(item.id), 'verdict': 'disagree'}]},
        headers=ORIGIN,
    )

    metrics = client.get('/ai-evaluations/agreement-metrics')
    assert metrics.status_code == HTTPStatus.OK
    body = metrics.json()
    assert body['total_feedback'] == 1
    assert body['overall_agreement_rate'] == 0.0
    assert body['by_check_type'].get('quality') == 0.0
    assert body['most_contested_criteria']


@pytest.mark.asyncio
async def test_agreement_metrics_empty_when_no_feedback(
    client, ai_eval_admin, session
):
    authenticate(client, ai_eval_admin)
    body = client.get('/ai-evaluations/agreement-metrics').json()
    assert body['total_feedback'] == 0
    assert body['overall_agreement_rate'] is None
