"""Isolamento, conflito e acesso nos alerts (Spec 047).

Os alerts são lidos do banco; o acesso ao destino passa pela API pública.
"""

from datetime import datetime
from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core import alert_service
from pivma.core.database.models import Alert, Assignment, Notification
from pivma.core.process_engine import waive_laboratory
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_return_review import _triage_return
from tests.api.routers.test_sample_nonconformity_decision import (
    with_problem,
)
from tests.api.routers.test_sample_nonconformity_router import nc_url
from tests.api.routers.test_sample_receipt_router import ORIGIN
from tests.factories.alert_factory import alerts_for
from tests.factories.laboratory_run_factory import (
    freeze_samples,
    frozen_lab_process,
)
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
)
from tests.factories.sample_receipt_factory import PHASE_3_KEY
from tests.factories.structure_approval_factory import (
    decide,
    structure_process,
)

TASK_OPENED = alert_service.TASK_OPENED
RECEIPT = 'receipt'
APPROVE = {'outcome': 'APPROVED', 'justification': 'Estrutura conferida.'}


def _headers(user):
    token = create_access_token(user.id, Settings().JWT_SECRET_KEY)
    return {'Authorization': f'Bearer {token}'}


async def _lab_assignment(session, ctx, index):
    return await session.scalar(
        select(Assignment).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.user_id == ctx.lab_users[index].id,
        )
    )


@pytest.mark.asyncio
async def test_each_laboratory_gets_only_its_own_run_alert(session):
    """US1, cenário 3; SC-002."""
    ctx = await frozen_lab_process(session, lab_count=2)

    for index, laboratory in enumerate(ctx.labs):
        alerts = await alerts_for(session, ctx.lab_users[index], TASK_OPENED)
        assert alerts
        assert {a.params['laboratory_name'] for a in alerts} == {
            laboratory.name
        }


@pytest.mark.asyncio
async def test_current_conflict_blocks_task_alert(session):
    """US1, cenário 4."""
    ctx = await frozen_lab_process(session, lab_count=1, freeze=False)
    assignment = await _lab_assignment(session, ctx, 0)
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    await freeze_samples(session, ctx)

    assert await alerts_for(session, ctx.lab_users[0], TASK_OPENED) == []


@pytest.mark.asyncio
async def test_task_alert_recipients_match_can_act_in_task_list(
    client, session
):
    """SC-001: recebe o alert quem vê a tarefa com `can_act` em /tasks.

    Compara as tarefas de recebimento, que abrem depois de todas as
    designações. As anteriores abriram antes de alguns cargos existirem.
    """
    ctx = await frozen_lab_process(session, lab_count=2)
    people = [
        ctx.creator,
        ctx.selector,
        ctx.group_manager,
        ctx.statistician,
        *ctx.lab_users,
    ]

    for person in people:
        response = client.get(
            '/tasks',
            params={'process_id': str(ctx.process_id), 'per_page': 100},
            headers=_headers(person),
        )
        assert response.status_code == HTTPStatus.OK, response.text
        actionable = {
            task['id']
            for task in response.json()['data']
            if task['can_act'] and task['activity_key'] == RECEIPT
        }
        alerted = {
            str(alert.target_id)
            for alert in await alerts_for(session, person, TASK_OPENED)
            if alert.params['activity_key'] == RECEIPT
        }
        assert alerted == actionable, person.username


@pytest.mark.asyncio
async def test_alert_stays_after_revocation_and_target_is_not_found(
    client, session
):
    """FR-018, Edge Cases: o alert não dá acesso."""
    ctx = await frozen_lab_process(session, lab_count=1)
    [alert] = await alerts_for(session, ctx.lab_users[0], TASK_OPENED)
    assignment = await _lab_assignment(session, ctx, 0)
    assignment.revoked_at = datetime(2026, 11, 21)
    await session.commit()

    response = client.get(
        f'/tasks/{alert.target_id}', headers=_headers(ctx.lab_users[0])
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail']['code'] == 'not_found'
    assert [a.id for a in await alerts_for(session, ctx.lab_users[0])] == [
        alert.id
    ]


# --- Polish: chaves fixas por tipo e independência do e-mail ---------------

PROCESS_KEYS = {'process_code', 'process_title'}
ALLOWED_PARAMS = {
    alert_service.TASK_OPENED: {
        *PROCESS_KEYS,
        'activity_key',
        'activity_name',
        'run_number',
        'due_date',
    },
    alert_service.SUBMISSION_STATUS_CHANGED: {*PROCESS_KEYS, 'status'},
    alert_service.STRUCTURE_APPROVED: PROCESS_KEYS,
    alert_service.PROCESS_WITHDRAWN: PROCESS_KEYS,
    alert_service.ASSIGNMENT_CREATED: {
        *PROCESS_KEYS,
        'role_key',
        'laboratory_name',
    },
    alert_service.ASSIGNMENT_REVOKED: {
        *PROCESS_KEYS,
        'role_key',
        'laboratory_name',
    },
    alert_service.ASSIGNMENT_EFFECTIVENESS_CHANGED: {
        *PROCESS_KEYS,
        'role_key',
        'laboratory_name',
        'effective',
    },
    alert_service.LABORATORY_RUN_COMPLETED: {
        *PROCESS_KEYS,
        'activity_name',
        'laboratory_name',
    },
    alert_service.LABORATORY_RUN_WAIVED: {
        *PROCESS_KEYS,
        'phase_name',
        'laboratory_name',
    },
    alert_service.SAMPLE_NONCONFORMITY_DECIDED: {
        *PROCESS_KEYS,
        'laboratory_name',
        'blind_code',
        'vial_status',
    },
}


async def _process_alerts(session, process_id):
    return list(
        await session.scalars(
            select(Alert).where(Alert.process_instance_id == process_id)
        )
    )


def _assert_fixed_keys(alerts):
    assert alerts
    for alert in alerts:
        allowed = ALLOWED_PARAMS[alert.kind]
        if alert.kind == alert_service.TASK_OPENED:
            # O laboratório só entra em execução por laboratório.
            allowed = {*allowed, 'laboratory_name'}
        assert set(alert.params) <= allowed, (alert.kind, alert.params)
        assert PROCESS_KEYS <= set(alert.params), alert.kind


@pytest.mark.asyncio
async def test_planning_alerts_carry_only_their_kind_keys(
    client, session, bracvam_user
):
    """SC-002, research R12: triagem, designações e homologação."""
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)
    decide(client, ctx.process_id, **APPROVE)

    alerts = await _process_alerts(session, ctx.process_id)

    _assert_fixed_keys(alerts)
    assert {a.kind for a in alerts} >= {
        alert_service.TASK_OPENED,
        alert_service.SUBMISSION_STATUS_CHANGED,
        alert_service.ASSIGNMENT_CREATED,
        alert_service.STRUCTURE_APPROVED,
    }


@pytest.mark.asyncio
async def test_laboratory_alerts_carry_only_their_kind_keys(session, client):
    """SC-002, research R12: recebimento, conclusão, decisão e dispensa."""
    ctx = await with_problem(session, client)
    item = ctx.items[0]
    client.post(
        nc_url(ctx.process_id, f'/{item["id"]}/decision'),
        json={'decision': 'accept_with_caveat', 'justification': 'Ok.'},
        headers=ORIGIN,
    )
    await waive_laboratory(
        session,
        ctx.process_id,
        PHASE_3_KEY,
        ctx.labs[1].id,
        'Equipamento quebrado.',
        ctx.group_manager.id,
    )
    await session.commit()

    alerts = await _process_alerts(session, ctx.process_id)

    _assert_fixed_keys(alerts)
    assert {a.kind for a in alerts} >= {
        alert_service.TASK_OPENED,
        alert_service.SAMPLE_NONCONFORMITY_DECIDED,
        alert_service.LABORATORY_RUN_COMPLETED,
        alert_service.LABORATORY_RUN_WAIVED,
    }


@pytest.mark.asyncio
async def test_alerts_do_not_depend_on_email_channel(
    client, session, bracvam_user, no_email_channel, use_settings
):
    """FR-007: sem e-mail, devolução e decisão do frasco geram alert."""
    use_settings(no_email_channel)
    proponent, pid, _ = await _triage_return(client, session, bracvam_user)
    ctx = await with_problem(session, client)
    client.post(
        nc_url(ctx.process_id, f'/{ctx.items[0]["id"]}/decision'),
        json={'decision': 'accept_with_caveat', 'justification': 'Ok.'},
        headers=ORIGIN,
    )

    returned = await alerts_for(session, proponent, TASK_OPENED)
    assert [a.params['activity_key'] for a in returned] == [
        'submission_return_review'
    ]
    assert await alerts_for(
        session, ctx.lab_users[0], alert_service.SAMPLE_NONCONFORMITY_DECIDED
    )
    notifications = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.process_instance_id.in_([pid, ctx.process_id]))
    )
    assert notifications == 0
