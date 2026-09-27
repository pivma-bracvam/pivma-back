"""Spec 032, US2 - resumo de pré-avaliação por IA em `GET /tasks`.

Usa o fluxo real: com o background desligado nos testes, a submissão deixa a
execução da pré-avaliação `in_progress` até alguém chamar `_execute`.
"""

from http import HTTPStatus
from uuid import UUID

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import EvaluationRun
from tests.ai_eval_helpers import (
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.evaluation_run_factory import EvaluationRunFactory
from tests.factories.user_factory import UserFactory

SUMMARY = [('include', 'summary')]


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _publish(client, session, ai_eval_admin):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(client, severity='critical')


def _submit(client, proponent, count):
    """Submete `count` processos; devolve (process_id, run_id) de cada um."""
    authenticate(client, proponent)
    submitted = []
    for _ in range(count):
        result = create_and_submit_process(client)
        assert result['status_code'] == HTTPStatus.OK, result['body']
        submitted.append((
            result['process_id'],
            UUID(result['body']['pre_evaluation']['run_id']),
        ))
    return submitted


def _in_progress(client, params=()):
    response = client.get('/tasks', params=[*SUMMARY, *params])
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()['summary']['ai_pre_evaluation_in_progress']


@pytest.mark.asyncio
async def test_summary_counts_ai_in_progress(
    client, session, ai_eval_admin, bracvam_user
):
    await _publish(client, session, ai_eval_admin)
    _submit(client, await _user(session), 4)

    authenticate(client, bracvam_user)

    assert _in_progress(client) == 4  # noqa: PLR2004


@pytest.mark.asyncio
async def test_summary_absent_without_include(
    client, session, ai_eval_admin, bracvam_user
):
    await _publish(client, session, ai_eval_admin)
    _submit(client, await _user(session), 1)

    authenticate(client, bracvam_user)
    body = client.get('/tasks').json()

    assert 'summary' not in body


@pytest.mark.asyncio
async def test_summary_ignores_finished_runs(
    client, session, ai_eval_admin, bracvam_user, fake_provider
):
    del fake_provider
    await _publish(client, session, ai_eval_admin)
    submitted = _submit(client, await _user(session), 4)
    await svc._execute(session, submitted[0][1])

    authenticate(client, bracvam_user)

    assert _in_progress(client) == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_summary_counts_process_once(
    client, session, ai_eval_admin, bracvam_user
):
    await _publish(client, session, ai_eval_admin)
    [(_, run_id)] = _submit(client, await _user(session), 1)
    # Como no reprocessamento administrativo: a execução antiga falhou e uma
    # nova está em andamento no mesmo processo.
    failed = await session.get(EvaluationRun, run_id)
    failed.status = 'failed'
    session.add(
        EvaluationRunFactory(
            process_instance_id=failed.process_instance_id,
            activity_run_id=failed.activity_run_id,
            form_instance_id=failed.form_instance_id,
        )
    )
    await session.commit()

    authenticate(client, bracvam_user)

    assert _in_progress(client) == 1


@pytest.mark.asyncio
async def test_summary_respects_visibility(client, session, ai_eval_admin):
    await _publish(client, session, ai_eval_admin)
    owner = await _user(session)
    _submit(client, owner, 2)
    _submit(client, await _user(session), 1)

    authenticate(client, owner)

    assert _in_progress(client) == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_summary_respects_process_id(
    client, session, ai_eval_admin, bracvam_user
):
    await _publish(client, session, ai_eval_admin)
    submitted = _submit(client, await _user(session), 3)

    authenticate(client, bracvam_user)

    assert _in_progress(client, [('process_id', submitted[0][0])]) == 1


@pytest.mark.asyncio
async def test_summary_ignores_other_task_filters(
    client, session, ai_eval_admin, bracvam_user
):
    await _publish(client, session, ai_eval_admin)
    _submit(client, await _user(session), 4)

    authenticate(client, bracvam_user)
    filters = [('phase_order', 2), ('status', 'COMPLETED')]

    assert _in_progress(client, filters) == 4  # noqa: PLR2004


@pytest.mark.asyncio
async def test_summary_ignores_deleted_runs(
    client, session, ai_eval_admin, bracvam_user
):
    await _publish(client, session, ai_eval_admin)
    [(_, run_id)] = _submit(client, await _user(session), 1)
    run = await session.get(EvaluationRun, run_id)
    run.set_deletion_audit(bracvam_user.id)
    await session.commit()

    authenticate(client, bracvam_user)

    assert _in_progress(client) == 0
