# ruff: noqa: PLR2004
"""API — submissão dispara pré-avaliação assíncrona (Spec 013, US2)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import ActivityInstance, ProcessInstance
from tests.activity_state import in_triage
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_submit_with_assignment_holds_triage_and_returns_in_progress(
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

    assert result['status_code'] == HTTPStatus.OK
    pre_eval = result['body']['pre_evaluation']
    assert pre_eval is not None
    assert pre_eval['status'] == 'in_progress'

    process = await session.scalar(
        select(ProcessInstance).where(
            ProcessInstance.id == result['process_id']
        )
    )
    assert process.status == 'OPEN'
    triage = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == result['process_id'],
            ActivityInstance.key == 'triage_evaluation',
        )
    )
    assert triage.status != 'READY'


@pytest.mark.asyncio
async def test_submit_without_assignment_advances_to_triage(client, session):
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)

    result = create_and_submit_process(client)

    assert result['status_code'] == HTTPStatus.OK
    assert result['body']['pre_evaluation'] is None

    assert await in_triage(session, result['process_id'])
