"""Plano estatístico como ponto da homologação (Spec 042, US4).

O Estatístico envia o plano pelo formulário da atividade
`statistical_plan`, que abre quando a atribuição do estatístico conclui. O
envio conclui a atividade sem os efeitos da proposta (dossiê, IA e
triagem). A reprovação do ponto abre um formulário novo e guarda o
anterior (research R13).
"""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import (
    Artifact,
    EvaluationAssignment,
    EvaluationRun,
    FormInstance,
    FormTemplate,
    FormValue,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.evaluation_factory import EvaluationDefinitionFactory
from tests.factories.structure_approval_factory import (
    ORIGIN,
    PLAN_KEY,
    activity,
    attach_plan,
    decide,
    events,
    finish_samples,
    panel,
    runs,
    structure_process,
    submit_plan,
)

FORM_URL = '/processes/{pid}/activities/statistical_plan/form'


async def _plan_open(session, bracvam_user, **kwargs):
    """Estatístico designado, plano ainda não enviado."""
    return await structure_process(
        session, bracvam_user, send_plan=False, **kwargs
    )


def _submit(client, process_id, values=None):
    return client.post(
        FORM_URL.format(pid=process_id),
        json={'values': values or {}},
        headers=ORIGIN,
    )


@pytest.mark.asyncio
async def test_statistician_designation_opens_the_plan_task(
    client, session, bracvam_user
):
    ctx = await _plan_open(session, bracvam_user, complete_samples=False)

    authenticate(client, ctx.statistician)
    tasks = client.get(
        '/tasks',
        params={'process_id': ctx.process_id, 'activity_key': PLAN_KEY},
    )
    form = client.get(FORM_URL.format(pid=ctx.process_id))

    assert tasks.status_code == HTTPStatus.OK, tasks.text
    [task] = tasks.json()['data']
    assert task['status'] == 'READY'
    assert form.status_code == HTTPStatus.OK, form.text
    assert form.json()['is_submitted'] is False
    assert [f['field_key'] for f in form.json()['fields']] == [
        'plan_file',
        'summary',
    ]


@pytest.mark.asyncio
async def test_plan_without_attachment_is_refused(
    client, session, bracvam_user
):
    ctx = await _plan_open(session, bracvam_user, complete_samples=False)
    authenticate(client, ctx.statistician)

    response = _submit(client, ctx.process_id, {'summary': 'Resumo.'})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    detail = response.json()['detail']
    assert detail['code'] == 'invalid_form_values'
    assert [(f['field'], f['code']) for f in detail['fields']] == [
        ('values.plan_file', 'attachment_required')
    ]
    assert (await activity(session, ctx.process_id, PLAN_KEY)).status == (
        'IN_PROGRESS'
    )


@pytest.mark.asyncio
async def test_plan_submission_completes_the_activity_and_records_it(
    client, session, bracvam_user
):
    ctx = await _plan_open(session, bracvam_user, complete_samples=False)
    await attach_plan(session, ctx)
    authenticate(client, ctx.statistician)

    response = _submit(client, ctx.process_id, {'summary': 'Resumo.'})

    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()['status'] == 'COMPLETED'
    assert response.json()['artifact_id'] is None
    assert response.json()['pre_evaluation'] is None
    [run] = await runs(session, ctx.process_id, PLAN_KEY)
    [event] = await events(session, ctx.process_id, 'FORM_SUBMITTED')
    assert (await activity(session, ctx.process_id, PLAN_KEY)).status == (
        'COMPLETED'
    )
    assert event.activity_run_id == run.id
    assert event.user_id == ctx.statistician.id
    assert event.context_data == {'activity_key': PLAN_KEY, 'run_number': 1}


@pytest.mark.asyncio
async def test_plan_submission_skips_proposal_effects_even_with_ai_enabled(
    client, session, bracvam_user
):
    ctx = await _plan_open(session, bracvam_user, complete_samples=False)
    plan_form = await session.scalar(
        select(FormTemplate).where(FormTemplate.key == 'statistical_plan_v1')
    )
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    session.add(
        EvaluationAssignment(
            form_template_id=plan_form.id,
            definition_id=definition.id,
            target_type='form',
            field_keys=[],
        )
    )
    await session.commit()
    await attach_plan(session, ctx)
    authenticate(client, ctx.statistician)

    response = _submit(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK, response.text
    triage = await activity(session, ctx.process_id, 'triage_evaluation')
    dossiers = await session.scalar(
        select(func.count()).where(
            Artifact.process_instance_id == ctx.process_id,
            Artifact.key == 'proposal_dossier',
        )
    )
    evaluations = await session.scalar(
        select(func.count()).where(
            EvaluationRun.process_instance_id == ctx.process_id
        )
    )
    assert dossiers == 1  # só o da proposta
    assert evaluations == 0
    assert (
        len(await events(session, ctx.process_id, 'SUBMISSION_SUBMITTED')) == 1
    )
    assert (
        await events(session, ctx.process_id, 'AI_PRE_EVALUATION_STARTED')
        == []
    )
    assert (triage.status, triage.blocked_reason) == ('COMPLETED', None)


@pytest.mark.asyncio
async def test_pending_plan_is_a_point_and_keeps_the_approval_closed(
    client, session, bracvam_user
):
    ctx = await _plan_open(session, bracvam_user)

    authenticate(client, bracvam_user)
    body = panel(client, ctx.process_id).json()

    point = next(p for p in body['points'] if p['activity_key'] == PLAN_KEY)
    assert body['status'] == 'BLOCKED'
    assert (point['status'], point['activity_type']) == ('IN_PROGRESS', 'form')
    assert [p['code'] for p in point['pending']] == ['activity_not_completed']
    assert (point['designations'], point['samples']) == (None, None)


@pytest.mark.asyncio
async def test_plan_submission_opens_the_approval_when_it_is_the_last_point(
    session, bracvam_user
):
    ctx = await _plan_open(session, bracvam_user, complete_samples=False)
    await finish_samples(session, ctx)
    assert (await activity(session, ctx.process_id)).status == 'BLOCKED'

    await submit_plan(session, ctx)

    assert (await activity(session, ctx.process_id)).status == 'IN_PROGRESS'


async def _form_of(session, run_id) -> FormInstance:
    return await session.scalar(
        select(FormInstance)
        .where(FormInstance.activity_run_id == run_id)
        .execution_options(populate_existing=True)
    )


@pytest.mark.asyncio
async def test_rejected_plan_gets_a_new_form_and_keeps_the_previous(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)

    response = decide(
        client,
        ctx.process_id,
        outcome='REJECTED',
        justification='Plano incompleto.',
        rejected_points=[
            {'activity_key': PLAN_KEY, 'reason': 'Falta o tamanho amostral.'}
        ],
    )

    assert response.status_code == HTTPStatus.OK, response.text
    historical = client.get(
        f'{FORM_URL.format(pid=ctx.process_id)}?run_number=1'
    )
    assert historical.status_code == HTTPStatus.OK, historical.text
    assert historical.json()['is_submitted'] is True
    assert historical.json()['fields'][0]['attachment']['filename'] == (
        'plano.pdf'
    )
    first, second = await runs(session, ctx.process_id, PLAN_KEY)
    previous = await _form_of(session, first.id)
    current = await _form_of(session, second.id)
    previous_files = await session.scalar(
        select(func.count()).where(
            FormValue.form_instance_id == previous.id,
            FormValue.file_attachment_id.is_not(None),
        )
    )
    assert (first.status, previous.is_submitted) == ('COMPLETED', True)
    assert previous_files == 1
    assert (second.status, current.is_submitted) == ('IN_PROGRESS', False)
    assert second.execution_reason == 'Falta o tamanho amostral.'
    authenticate(client, ctx.statistician)
    form = client.get(FORM_URL.format(pid=ctx.process_id)).json()
    assert form['form_instance_id'] == str(current.id)
    assert form['fields'][0]['attachment'] is None


@pytest.mark.asyncio
async def test_historical_plan_form_rejects_an_unknown_run(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)

    response = client.get(
        f'{FORM_URL.format(pid=ctx.process_id)}?run_number=99'
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
