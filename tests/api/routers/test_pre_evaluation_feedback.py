# ruff: noqa: PLR2004
"""API — feedback do triador por critério (Spec 013, US4)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import (
    EvaluationRunItem,
    ProcessInstance,
    ReviewerFeedback,
)
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import (
    AssignmentFactory,
    ConflictInterestDeclarationFactory,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}


async def _run_with_item(client, session, ai_eval_admin):
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
    return result['process_id'], run_id, item


@pytest.mark.asyncio
async def test_feedback_records_and_updates_without_duplicating(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    process_id, run_id, item = await _run_with_item(
        client, session, ai_eval_admin
    )
    authenticate(client, ai_eval_admin)

    first = client.post(
        f'/processes/{process_id}/pre-evaluation/{run_id}/feedback',
        json={
            'items': [
                {
                    'item_id': str(item.id),
                    'verdict': 'disagree',
                    'reason': 'O documento cobre isso na seção 7.',
                }
            ]
        },
        headers=ORIGIN,
    )
    assert first.status_code == HTTPStatus.OK
    assert first.json()['recorded'] == 1

    # reenvio do mesmo item -> atualiza, não duplica
    client.post(
        f'/processes/{process_id}/pre-evaluation/{run_id}/feedback',
        json={'items': [{'item_id': str(item.id), 'verdict': 'agree'}]},
        headers=ORIGIN,
    )
    feedback = list(
        await session.scalars(
            select(ReviewerFeedback).where(
                ReviewerFeedback.run_item_id == item.id
            )
        )
    )
    assert len(feedback) == 1
    assert feedback[0].verdict == 'agree'

    # resultado da IA inalterado
    refreshed = await session.get(EvaluationRunItem, item.id)
    assert refreshed.conclusion == item.conclusion


@pytest.mark.asyncio
async def test_feedback_blocked_by_conflict_of_interest(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    process_id, run_id, item = await _run_with_item(
        client, session, ai_eval_admin
    )

    assignment = AssignmentFactory(
        process=await session.get(ProcessInstance, process_id),
        user=ai_eval_admin,
    )
    session.add(assignment)
    await session.flush()
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    authenticate(client, ai_eval_admin)
    resp = client.post(
        f'/processes/{process_id}/pre-evaluation/{run_id}/feedback',
        json={'items': [{'item_id': str(item.id), 'verdict': 'agree'}]},
        headers=ORIGIN,
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN
