# ruff: noqa: PLR2004
"""Integração — snapshot imutável do conteúdo avaliado (Spec 014, US3)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import EvaluationAssignment, EvaluationRun
from pivma.core.process_engine import utc_now
from tests.ai_eval_helpers import (
    AI_FIELD,
    FULL_VALUES,
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


async def _run_completed(client, session, ai_eval_admin) -> UUID:
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
    assert result['status_code'] == HTTPStatus.OK
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    await svc._execute(session, run_id)
    return run_id


@pytest.mark.asyncio
async def test_snapshot_written_on_execute(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    run_id = await _run_completed(client, session, ai_eval_admin)

    run = await session.get(EvaluationRun, run_id)
    snapshot = run.evaluated_content_snapshot
    assert isinstance(snapshot, list)
    assert snapshot
    entry = next(c for c in snapshot if c['field_key'] == AI_FIELD)
    assert entry['value'] == FULL_VALUES[AI_FIELD]
    assert entry['label']


@pytest.mark.asyncio
async def test_snapshot_unchanged_after_assignment_removed(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    run_id = await _run_completed(client, session, ai_eval_admin)
    process_id = (await session.get(EvaluationRun, run_id)).process_instance_id

    before = (await svc.get_pre_evaluation(session, process_id, None))[
        'evaluated_content'
    ]

    # Remove a associação de avaliação do template.
    for a in await session.scalars(select(EvaluationAssignment)):
        a.deleted_at = utc_now()
    await session.commit()

    after = (await svc.get_pre_evaluation(session, process_id, None))[
        'evaluated_content'
    ]
    assert after == before
    assert any(c['field_key'] == AI_FIELD for c in after)


@pytest.mark.asyncio
async def test_null_snapshot_falls_back_to_reconstruction(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    run_id = await _run_completed(client, session, ai_eval_admin)
    run = await session.get(EvaluationRun, run_id)
    run.evaluated_content_snapshot = None
    await session.commit()

    payload = await svc.get_pre_evaluation(
        session, run.process_instance_id, None
    )
    assert any(
        c['field_key'] == AI_FIELD for c in payload['evaluated_content']
    )
