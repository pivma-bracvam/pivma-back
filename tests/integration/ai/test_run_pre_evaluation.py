# ruff: noqa: PLR2004
"""Integração — run_pre_evaluation persiste e roteia (Spec 013, US2)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import (
    ActivityRun,
    Artifact,
    AuditEvent,
    EvaluationRun,
    EvaluationRunItem,
    ProcessInstance,
)
from tests.ai_eval_helpers import (
    COMPLIANT_STATEMENT,
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


async def _submitted_run(
    client, session, ai_eval_admin, *, severity, statement=None
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    if statement is None:
        statement = (
            NON_COMPLIANT_STATEMENT
            if severity in {'critical', 'high'}
            else COMPLIANT_STATEMENT
        )
    publish_evaluation_and_assign(
        client, severity=severity, statement=statement
    )

    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK
    return UUID(result['body']['pre_evaluation']['run_id'])


@pytest.mark.asyncio
async def test_execute_persists_items_and_report_and_routes_negative(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    run_id = await _submitted_run(
        client, session, ai_eval_admin, severity='critical'
    )

    await svc._execute(session, run_id)

    run = await session.get(EvaluationRun, run_id)
    assert run.status == 'completed'
    assert run.consolidated_result == 'negative'
    assert run.provider_name == 'fake'
    assert run.models_used == {
        'extraction': None,
        'fast': None,
        'reasoning': None,
    }

    items = list(
        await session.scalars(
            select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
        )
    )
    assert len(items) == 1
    assert items[0].criterion_statement
    assert items[0].evaluation_version_id is not None

    report = await session.scalar(
        select(Artifact).where(
            Artifact.process_instance_id == run.process_instance_id,
            Artifact.key == 'ai_pre_evaluation_report',
        )
    )
    assert report is not None
    assert report.metadata_payload['consolidated_result'] == 'negative'


@pytest.mark.asyncio
async def test_execute_positive_result_unblocks_triage(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    run_id = await _submitted_run(
        client, session, ai_eval_admin, severity='low'
    )

    await svc._execute(session, run_id)

    run = await session.get(EvaluationRun, run_id)
    assert run.consolidated_result == 'positive'

    from pivma.core.database.models import ActivityInstance  # noqa: PLC0415

    triage = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == run.process_instance_id,
            ActivityInstance.key == 'triage_evaluation',
        )
    )
    assert triage.status == 'IN_PROGRESS'

    # Issue #22 (US3): desbloqueio pelo motor genérico passa a registrar
    # evento de auditoria, consistente com qualquer outra atividade
    # dependente — antes, este caminho não emitia nada.
    triage_run = await session.scalar(
        select(ActivityRun).where(
            ActivityRun.activity_instance_id == triage.id
        )
    )
    unblock_event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == run.process_instance_id,
            AuditEvent.event_type == 'ACTIVITY_UNBLOCKED',
            AuditEvent.activity_run_id == triage_run.id,
        )
    )
    assert unblock_event is not None
    assert unblock_event.context_data['activity_key'] == 'triage_evaluation'


@pytest.mark.asyncio
async def test_low_severity_non_compliant_now_routes_negative(
    client, ai_eval_admin, session, fake_provider
):
    """Spec 026, FR-001: severidade deixa de decidir o roteamento."""
    del fake_provider
    run_id = await _submitted_run(
        client,
        session,
        ai_eval_admin,
        severity='low',
        statement=NON_COMPLIANT_STATEMENT,
    )

    await svc._execute(session, run_id)

    run = await session.get(EvaluationRun, run_id)
    assert run.consolidated_result == 'negative'

    process = await session.get(ProcessInstance, run.process_instance_id)
    assert process.status == 'SUBMISSION'


@pytest.mark.asyncio
async def test_document_target_indeterminate_routes_negative(
    client, ai_eval_admin, session, fake_provider
):
    """Spec 026, FR-003: indeterminado bloqueia como não conforme/parcial."""
    del fake_provider
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client,
        severity='low',
        statement=COMPLIANT_STATEMENT,
        target_type='document',
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK
    run_id = UUID(result['body']['pre_evaluation']['run_id'])

    await svc._execute(session, run_id)

    run = await session.get(EvaluationRun, run_id)
    assert run.consolidated_result == 'negative'

    items = list(
        await session.scalars(
            select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
        )
    )
    assert len(items) == 1
    assert items[0].conclusion == 'indeterminate'


@pytest.mark.asyncio
async def test_execute_is_idempotent_on_non_pending_run(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    run_id = await _submitted_run(
        client, session, ai_eval_admin, severity='critical'
    )
    await svc._execute(session, run_id)
    await svc._execute(session, run_id)  # segundo processamento é no-op

    items = list(
        await session.scalars(
            select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
        )
    )
    assert len(items) == 1
