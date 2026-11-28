"""Alert de tarefa nova (Spec 047, US1).

Os testes leem os alerts gravados direto do banco: o que o usuário vê pela
rota está coberto em `test_alerts_router.py` e nas jornadas.
"""

from datetime import datetime
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import alert_service
from pivma.core.database.models import ActivityInstance, ActivityRun, Task
from tests.ai_eval_helpers import (
    COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_return_review import (
    ORIGIN,
    VALUES,
    _ai_return,
    _created_process,
)
from tests.api.routers.test_sample_receipt_router import lab_ready, register
from tests.factories.alert_factory import alerts_for, same_profile_user
from tests.factories.laboratory_run_factory import (
    complete_lab,
    freeze_samples,
    frozen_lab_process,
    lab_view_only,
    reopen,
    runs_by_lab,
    tasks_of,
    waive,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.structure_approval_factory import planning_process

TASK_PARAMS = {
    'process_code',
    'process_title',
    'activity_key',
    'activity_name',
    'run_number',
    'due_date',
}
TASK_OPENED = alert_service.TASK_OPENED


async def _task_of(session, process_id, key):
    return await session.scalar(
        select(Task)
        .join(ActivityRun)
        .join(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == key,
        )
        .order_by(ActivityRun.run_number.desc())
        .limit(1)
    )


def _submit(client, pid):
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text


def _keys(alerts):
    return [alert.params['activity_key'] for alert in alerts]


@pytest.mark.asyncio
async def test_triage_task_alerts_each_bracvam_with_task_params(
    client, session, bracvam_user
):
    """FR-010."""
    colleague = await same_profile_user(session, bracvam_user)
    _, pid = await _created_process(client, session)

    _submit(client, pid)

    task = await _task_of(session, pid, 'triage_evaluation')
    for person in (bracvam_user, colleague):
        [alert] = await alerts_for(session, person, TASK_OPENED)
        assert alert.target_type == alert_service.TARGET_TASK
        assert alert.target_id == task.id
        assert set(alert.params) == TASK_PARAMS
        assert alert.params['activity_key'] == 'triage_evaluation'
        assert alert.params['run_number'] == 1


@pytest.mark.asyncio
async def test_creator_gets_no_alert_for_own_submission(client, session):
    """FR-006."""
    proponent, _ = await _created_process(client, session)

    assert await alerts_for(session, proponent) == []


@pytest.mark.asyncio
async def test_bracvam_who_unlocks_designations_gets_none_colleague_does(
    session, bracvam_user
):
    """US1, cenário 5: a aprovação da triagem libera as designações."""
    colleague = await same_profile_user(session, bracvam_user)

    await planning_process(session, bracvam_user)

    own = _keys(await alerts_for(session, bracvam_user, TASK_OPENED))
    assert own == ['triage_evaluation']
    unlocked = _keys(await alerts_for(session, colleague, TASK_OPENED))
    assert {'assign_sponsor', 'assign_group_manager'} <= set(unlocked)


@pytest.mark.asyncio
async def test_ai_negative_return_alerts_proponent_without_author(
    client, session, ai_eval_admin
):
    """Research R5."""
    proponent, pid, _ = await _ai_return(client, session, ai_eval_admin)

    [alert] = await alerts_for(session, proponent, TASK_OPENED)
    assert alert.params['activity_key'] == 'submission_return_review'
    assert alert.created_by is None
    task = await _task_of(session, pid, 'submission_return_review')
    assert alert.target_id == task.id


@pytest.mark.asyncio
async def test_ai_failure_return_gives_same_alert(
    client, session, ai_eval_admin
):
    """Edge Cases: a falha da IA não aparece no alert."""
    proponent, _, _ = await _ai_return(
        client, session, ai_eval_admin, failed=True
    )

    [alert] = await alerts_for(session, proponent, TASK_OPENED)
    assert alert.params['activity_key'] == 'submission_return_review'
    assert set(alert.params) == TASK_PARAMS


@pytest.mark.asyncio
async def test_proponent_with_bracvam_profile_gets_triage_opened_by_ai(
    client, session, ai_eval_admin, bracvam_user, fake_provider
):
    """Research R5: a IA não conta como autor do proponente."""
    del fake_provider
    from pivma.core import pre_evaluation_service as svc  # noqa: PLC0415

    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=COMPLIANT_STATEMENT
    )
    proponent = await same_profile_user(session, bracvam_user)
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    run_id = result['body']['pre_evaluation']['run_id']

    await svc._execute(session, run_id)

    keys = _keys(await alerts_for(session, proponent, TASK_OPENED))
    assert keys == ['triage_evaluation']


@pytest.mark.asyncio
async def test_two_qualifying_cargos_give_one_alert(session):
    """FR-005: laboratório e Grupo Gestor na mesma execução."""
    ctx = await frozen_lab_process(session, lab_count=1, freeze=False)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.lab_users[0],
        role_key='group_manager',
    )
    from tests.factories.laboratory_run_factory import (  # noqa: PLC0415
        freeze_samples,
    )

    await freeze_samples(session, ctx)

    keys = _keys(await alerts_for(session, ctx.lab_users[0], TASK_OPENED))
    assert keys.count('receipt') == 1


@pytest.mark.asyncio
async def test_lab_user_without_edit_role_gets_no_task_alert(session):
    """Issue #86: o alert segue `edit_roles` na execução do laboratório."""
    ctx = await frozen_lab_process(session, lab_count=1, freeze=False)
    await lab_view_only(session, ctx.process_id)
    await freeze_samples(session, ctx)

    keys = _keys(await alerts_for(session, ctx.lab_users[0], TASK_OPENED))
    assert 'receipt' not in keys


@pytest.mark.asyncio
async def test_deactivated_account_gets_no_task_alert(session):
    """FR-004."""
    ctx = await frozen_lab_process(session, lab_count=1, freeze=False)
    ctx.lab_users[0].deleted_at = datetime(2026, 11, 1)
    await session.commit()
    from tests.factories.laboratory_run_factory import (  # noqa: PLC0415
        freeze_samples,
    )

    await freeze_samples(session, ctx)

    assert await alerts_for(session, ctx.lab_users[0], TASK_OPENED) == []


@pytest.mark.asyncio
async def test_reopened_run_gives_new_alert_with_run_number_2(session):
    """Edge Cases."""
    ctx = await frozen_lab_process(session, lab_count=1)
    await complete_lab(session, ctx, 'receipt', 0)

    await reopen(session, ctx, 'receipt', 0)

    receipts = [
        alert
        for alert in await alerts_for(session, ctx.lab_users[0], TASK_OPENED)
        if alert.params['activity_key'] == 'receipt'
    ]
    assert sorted(alert.params['run_number'] for alert in receipts) == [1, 2]


@pytest.mark.asyncio
async def test_waiver_cancelled_task_gets_no_alert(session):
    """Research R4: a tarefa que já nasce cancelada não vira alert.

    A dispensa abre a devolução do material, que tem alert, e cancela o
    recebimento, cujo alert de abertura continua (FR-020). Sobram as
    execuções que ainda não tinham começado: a tarefa delas nasce cancelada.
    """
    ctx = await frozen_lab_process(session, lab_count=2)

    await waive(session, ctx, 1)

    cancelled = set(
        await session.scalars(
            select(Task.id)
            .join(ActivityRun)
            .join(ActivityInstance)
            .where(
                ActivityInstance.process_instance_id == ctx.process_id,
                ActivityRun.laboratory_id == ctx.labs[1].id,
                ActivityInstance.key != 'receipt',
                Task.status == 'CANCELLED',
            )
        )
    )
    assert cancelled
    alerted = {
        alert.target_id
        for alert in await alerts_for(session, ctx.lab_users[1], TASK_OPENED)
    }
    assert not alerted & cancelled


@pytest.mark.asyncio
async def test_completing_task_leaves_its_alerts_untouched(session):
    """FR-020."""
    ctx = await frozen_lab_process(session, lab_count=1)
    run = (await runs_by_lab(session, ctx.process_id, 'receipt'))[
        ctx.labs[0].id
    ]
    [task] = await tasks_of(session, run.id)
    [before] = [
        a
        for a in await alerts_for(session, ctx.lab_users[0], TASK_OPENED)
        if a.target_id == task.id
    ]

    await complete_lab(session, ctx, 'receipt', 0)

    [after] = [
        a
        for a in await alerts_for(session, ctx.lab_users[0], TASK_OPENED)
        if a.target_id == task.id
    ]
    assert after.id == before.id
    assert after.read_at is None


@pytest.mark.asyncio
async def test_receipt_problem_alerts_selection_group_once(session, client):
    """FR-011: o problema chega pela tarefa de resolução."""
    ctx = await lab_ready(session, client)

    register(client, ctx.process_id, ctx.codes[0], package_state='damaged')

    alerts = await alerts_for(session, ctx.selector, TASK_OPENED)
    resolution = [
        a
        for a in alerts
        if a.params['activity_key'] == 'sample_receipt_resolution'
    ]
    assert len(resolution) == 1
    task = await _task_of(session, ctx.process_id, 'sample_receipt_resolution')
    assert resolution[0].target_id == task.id


@pytest.mark.asyncio
async def test_proponent_gets_no_alert_for_triage_task_they_only_view(
    client, session, bracvam_user
):
    """Spec 049: o alert segue `edit_roles`, não a visão da triagem."""
    proponent, pid = await _created_process(client, session)

    _submit(client, pid)

    assert 'triage_evaluation' not in _keys(
        await alerts_for(session, proponent, TASK_OPENED)
    )
