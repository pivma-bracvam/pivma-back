# ruff: noqa: PLR2004
"""API — consulta da pré-avaliação e roteamento (Spec 013, US2)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import ProcessInstance
from tests.ai_eval_helpers import (
    AI_FIELD,
    COMPLIANT_STATEMENT,
    FULL_VALUES,
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


async def _scenario(
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
    run_id = UUID(result['body']['pre_evaluation']['run_id'])
    return proponent, result['process_id'], run_id


@pytest.mark.asyncio
async def test_in_progress_then_completed_negative_returns_to_proponent(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, run_id = await _scenario(
        client, session, ai_eval_admin, severity='critical'
    )

    authenticate(client, proponent)
    in_progress = client.get(f'/processes/{process_id}/pre-evaluation')
    assert in_progress.json()['status'] == 'in_progress'

    await svc._execute(session, run_id)

    done = client.get(f'/processes/{process_id}/pre-evaluation').json()
    assert done['status'] == 'completed'
    assert done['consolidated_result'] == 'negative'
    assert done['summary']['total'] == 1
    assert done['attention_points']

    process = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == process_id)
    )
    assert process.status == 'SUBMISSION'


@pytest.mark.asyncio
async def test_completed_positive_advances_to_triage(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, run_id = await _scenario(
        client, session, ai_eval_admin, severity='low'
    )

    await svc._execute(session, run_id)

    authenticate(client, proponent)
    done = client.get(f'/processes/{process_id}/pre-evaluation').json()
    assert done['consolidated_result'] == 'positive'

    process = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == process_id)
    )
    assert process.status == 'TRIAGE'


@pytest.mark.asyncio
async def test_attention_points_include_low_severity_blocking_reason(
    client, ai_eval_admin, session, fake_provider
):
    """Spec 026, FR-008: motivo do bloqueio aparece mesmo em severidade
    baixa.
    """
    del fake_provider
    proponent, process_id, run_id = await _scenario(
        client,
        session,
        ai_eval_admin,
        severity='low',
        statement=NON_COMPLIANT_STATEMENT,
    )

    await svc._execute(session, run_id)

    authenticate(client, proponent)
    done = client.get(f'/processes/{process_id}/pre-evaluation').json()
    assert done['consolidated_result'] == 'negative'
    assert len(done['attention_points']) == 1

    point = done['attention_points'][0]
    assert point['severity'] == 'low'
    assert point['conclusion'] == 'non_compliant'
    assert point['justification']


@pytest.mark.asyncio
async def test_failed_run_returns_to_proponent(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, run_id = await _scenario(
        client, session, ai_eval_admin, severity='critical'
    )

    await svc._mark_failed(session, run_id)

    authenticate(client, proponent)
    done = client.get(f'/processes/{process_id}/pre-evaluation').json()
    assert done['status'] == 'failed'
    assert done['error_summary']

    process = await session.scalar(
        select(ProcessInstance).where(ProcessInstance.id == process_id)
    )
    assert process.status == 'SUBMISSION'


@pytest.mark.asyncio
async def test_payload_carries_evaluated_content(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, run_id = await _scenario(
        client, session, ai_eval_admin, severity='critical'
    )
    await svc._execute(session, run_id)

    authenticate(client, proponent)
    body = client.get(f'/processes/{process_id}/pre-evaluation').json()

    content = {c['field_key']: c['value'] for c in body['evaluated_content']}
    assert AI_FIELD in content
    assert content[AI_FIELD] == FULL_VALUES[AI_FIELD]


@pytest.mark.asyncio
async def test_outsider_cannot_read_pre_evaluation(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    _, process_id, run_id = await _scenario(
        client, session, ai_eval_admin, severity='critical'
    )
    await svc._execute(session, run_id)

    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    resp = client.get(f'/processes/{process_id}/pre-evaluation')
    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_status_is_ai_pre_evaluation_and_form_locked_while_pending(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    proponent, process_id, _ = await _scenario(
        client, session, ai_eval_admin, severity='critical'
    )
    authenticate(client, proponent)

    # Antes de a IA concluir: AI_PRE_EVALUATION e formulário travado.
    detail = client.get(f'/processes/{process_id}')
    assert detail.status_code == HTTPStatus.OK
    assert detail.json()['status'] == 'AI_PRE_EVALUATION'

    resubmit = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': FULL_VALUES},
    )
    assert resubmit.status_code == HTTPStatus.CONFLICT

    draft = client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': FULL_VALUES},
    )
    assert draft.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_outsider_cannot_see_process_during_ai_pre_evaluation(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    _, process_id, _ = await _scenario(
        client, session, ai_eval_admin, severity='critical'
    )

    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    assert (
        client.get(f'/processes/{process_id}').status_code
        == HTTPStatus.NOT_FOUND
    )
