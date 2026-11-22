"""Isolamento, conflito e acesso nos alerts (Spec 047).

Os alerts são lidos do banco; o acesso ao destino passa pela API pública.
"""

from datetime import datetime
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core import alert_service
from pivma.core.database.models import Assignment
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.alert_factory import alerts_for
from tests.factories.laboratory_run_factory import (
    freeze_samples,
    frozen_lab_process,
)
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
)

TASK_OPENED = alert_service.TASK_OPENED
RECEIPT = 'receipt'


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
