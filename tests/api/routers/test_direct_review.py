# ruff: noqa: PLR2004
"""API — solicitação de intervenção direta do BraCVAM (Spec 013, US3)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import Artifact, ProcessInstance
from tests.ai_eval_helpers import (
    COMPLIANT_STATEMENT,
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


async def _completed_run(client, session, ai_eval_admin, *, statement):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=statement
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    await svc._execute(session, run_id)
    return proponent, result['process_id'], run_id


@pytest.mark.asyncio
async def test_direct_review_after_negative_moves_to_triage(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, run_id = await _completed_run(
        client, session, ai_eval_admin, statement=NON_COMPLIANT_STATEMENT
    )

    authenticate(client, proponent)
    resp = client.post(
        f'/processes/{process_id}/submission/direct-review',
        json={'justification': 'Discordo da avaliação automática.'},
        headers={'Origin': 'https://testserver'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['process_status'] == 'TRIAGE'

    process = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == process_id)
    )
    assert process.status == 'TRIAGE'

    report = await session.scalar(
        select(Artifact).where(
            Artifact.process_instance_id == process_id,
            Artifact.key == 'ai_pre_evaluation_report',
        )
    )
    assert report is not None  # relatório da IA preservado

    view = client.get(f'/processes/{process_id}/pre-evaluation').json()
    assert view['direct_review_request'] is not None


@pytest.mark.asyncio
async def test_second_direct_review_is_conflict(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, _ = await _completed_run(
        client, session, ai_eval_admin, statement=NON_COMPLIANT_STATEMENT
    )
    authenticate(client, proponent)
    origin = {'Origin': 'https://testserver'}
    client.post(
        f'/processes/{process_id}/submission/direct-review',
        json={},
        headers=origin,
    )
    again = client.post(
        f'/processes/{process_id}/submission/direct-review',
        json={},
        headers=origin,
    )
    assert again.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_direct_review_rejected_when_result_positive(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, _ = await _completed_run(
        client, session, ai_eval_admin, statement=COMPLIANT_STATEMENT
    )
    authenticate(client, proponent)
    resp = client.post(
        f'/processes/{process_id}/submission/direct-review',
        json={},
        headers={'Origin': 'https://testserver'},
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_non_proponent_cannot_request_direct_review(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    _, process_id, _ = await _completed_run(
        client, session, ai_eval_admin, statement=NON_COMPLIANT_STATEMENT
    )
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)
    resp = client.post(
        f'/processes/{process_id}/submission/direct-review',
        json={},
        headers={'Origin': 'https://testserver'},
    )
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_direct_review_after_failed_run_moves_to_triage(
    client, ai_eval_admin, session, fake_provider
):
    """SC-012: uma falha da IA nunca impede a triagem humana."""
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

    process_id = result['process_id']
    await svc._mark_failed(session, run_id)

    view = client.get(f'/processes/{process_id}/pre-evaluation').json()
    assert view['status'] == 'failed'

    resp = client.post(
        f'/processes/{process_id}/submission/direct-review',
        json={'justification': 'A IA falhou; solicito triagem humana.'},
        headers={'Origin': 'https://testserver'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['process_status'] == 'TRIAGE'

    process = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == process_id)
    )
    assert process.status == 'TRIAGE'
