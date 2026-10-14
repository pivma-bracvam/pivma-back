# ruff: noqa: PLR2004
"""Painel e aprovação da homologação da estrutura (Spec 042, US1).

Cada teste parte de um processo do template real com a equipe designada
(`structure_process`). A recusa confere o `code` do erro e que nada mudou.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import Phase
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.structure_approval_factory import (
    ORIGIN,
    activity,
    decide,
    decisions,
    events,
    panel,
    run_tasks,
    runs,
    snapshot,
    structure_process,
)

APPROVE = {'outcome': 'APPROVED', 'justification': 'Estrutura conferida.'}
POINT_KEYS = [
    'assign_sponsor',
    'assign_group_manager',
    'assign_sample_selection_group',
    'assign_lead_laboratory',
    'assign_participating_laboratory',
    'assign_statistician',
    'assign_collaborator',
    'assign_adhoc_evaluator',
    'sample_definition',
]


async def _approved(client, session, bracvam_user, **kwargs):
    ctx = await structure_process(session, bracvam_user, **kwargs)
    authenticate(client, bracvam_user)
    ctx.response = decide(client, ctx.process_id, **APPROVE)
    return ctx


@pytest.mark.asyncio
async def test_factory_opens_approval_after_the_nine_points(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)

    for key in POINT_KEYS:
        assert (await activity(session, ctx.process_id, key)).status == (
            'COMPLETED'
        ), key
    approval = await activity(session, ctx.process_id)
    [run] = await runs(session, ctx.process_id)
    [task] = await run_tasks(session, run.id)
    assert approval.status == 'IN_PROGRESS'
    assert (task.status, task.assigned_role) == ('READY', 'bracvam')


@pytest.mark.asyncio
async def test_panel_lists_points_designations_and_sample_counts(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)

    response = panel(client, ctx.process_id)

    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert (body['status'], body['run_number']) == ('IN_PROGRESS', 1)
    assert body['blocked_reason'] is None
    assert [p['activity_key'] for p in body['points']] == POINT_KEYS
    points = {p['activity_key']: p for p in body['points']}
    labs = points['assign_participating_laboratory']['designations']
    assert {d['laboratory']['id'] for d in labs} == {
        str(lab.id) for lab in ctx.laboratories
    }
    assert {d['user']['id'] for d in labs} == {
        str(user.id) for user in ctx.lab_users
    }
    assert all(d['is_effective'] for d in labs)
    [sponsor] = points['assign_sponsor']['designations']
    assert sponsor['user']['id'] == str(ctx.sponsor.id)
    assert sponsor['laboratory'] is None
    assert all(
        p['samples'] is None
        for k, p in points.items()
        if k.startswith('assign')
    )
    assert points['sample_definition']['designations'] is None
    assert points['sample_definition']['samples'] == {
        'substance_count': 1,
        'laboratory_count': 2,
        'code_count': 2,
    }
    assert body['decisions'] == []


@pytest.mark.asyncio
async def test_panel_before_opening_shows_blocked_without_run(
    client, session, bracvam_user
):
    ctx = await structure_process(
        session, bracvam_user, complete_samples=False
    )
    authenticate(client, bracvam_user)

    body = panel(client, ctx.process_id).json()

    assert (body['status'], body['run_number']) == ('BLOCKED', None)


@pytest.mark.asyncio
async def test_approval_responds_completed_without_reopened_points(
    client, session, bracvam_user
):
    ctx = await _approved(client, session, bracvam_user)

    assert ctx.response.status_code == HTTPStatus.OK, ctx.response.text
    body = ctx.response.json()
    assert body['outcome'] == 'APPROVED'
    assert body['status'] == 'COMPLETED'
    assert body['reopened'] == []
    assert body['decision_id'] == str(
        (await decisions(session, ctx.process_id))[0].id
    )


@pytest.mark.asyncio
async def test_approval_completes_phase_2_and_opens_receipt_per_laboratory(
    client, session, bracvam_user
):
    ctx = await _approved(client, session, bracvam_user)

    approval = await activity(session, ctx.process_id)
    phase = await session.scalar(
        select(Phase)
        .where(Phase.id == approval.phase_id)
        .execution_options(populate_existing=True)
    )
    [run] = await runs(session, ctx.process_id)
    receipts = await runs(session, ctx.process_id, 'sample_receipt')
    assert approval.status == 'COMPLETED'
    assert phase.status == 'COMPLETED'
    assert [t.status for t in await run_tasks(session, run.id)] == [
        'COMPLETED'
    ]
    assert {r.laboratory_id for r in receipts} == {
        lab.id for lab in ctx.laboratories
    }
    assert {r.status for r in receipts} == {'IN_PROGRESS'}


@pytest.mark.asyncio
async def test_approval_records_the_decision(client, session, bracvam_user):
    ctx = await _approved(client, session, bracvam_user)

    [decision] = await decisions(session, ctx.process_id)
    [run] = await runs(session, ctx.process_id)
    assert decision.outcome == 'APPROVED'
    assert decision.justification == APPROVE['justification']
    assert decision.decided_by == bracvam_user.id
    assert decision.activity_run_id == run.id
    assert decision.rejected_points is None


@pytest.mark.asyncio
async def test_approval_records_structure_approved_event(
    client, session, bracvam_user
):
    ctx = await _approved(client, session, bracvam_user)

    [decision] = await decisions(session, ctx.process_id)
    [run] = await runs(session, ctx.process_id)
    [event] = await events(session, ctx.process_id, 'STRUCTURE_APPROVED')
    assert event.activity_run_id == run.id
    assert event.user_id == bracvam_user.id
    assert event.context_data == {
        'decision_id': str(decision.id),
        'justification': APPROVE['justification'],
    }


@pytest.mark.asyncio
async def test_panel_after_approval_lists_the_decision(
    client, session, bracvam_user
):
    ctx = await _approved(client, session, bracvam_user)

    body = panel(client, ctx.process_id).json()

    assert body['status'] == 'COMPLETED'
    [decision] = body['decisions']
    assert decision['run_number'] == 1
    assert decision['outcome'] == 'APPROVED'
    assert decision['justification'] == APPROVE['justification']
    assert decision['rejected_points'] is None
    assert decision['decided_by']['id'] == str(bracvam_user.id)
    assert decision['decided_at']


@pytest.mark.asyncio
async def test_second_approval_is_refused(client, session, bracvam_user):
    ctx = await _approved(client, session, bracvam_user)
    before = await snapshot(session, ctx.process_id)

    response = decide(client, ctx.process_id, **APPROVE)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'
    assert await snapshot(session, ctx.process_id) == before


@pytest.mark.asyncio
async def test_previous_template_version_opens_receipt_on_sample_completion(
    client, session, bracvam_user
):
    """FR-003: processos das versões anteriores seguem o fluxo antigo."""
    ctx = await structure_process(session, bracvam_user, previous_version=True)

    receipts = await runs(session, ctx.process_id, 'sample_receipt')
    assert await activity(session, ctx.process_id) is None
    assert {r.laboratory_id for r in receipts} == {
        lab.id for lab in ctx.laboratories
    }
    assert {r.status for r in receipts} == {'IN_PROGRESS'}


@pytest.mark.asyncio
async def test_decision_on_cancelled_process_is_refused(
    client, session, bracvam_user
):
    """US3, cenário 6: o processo excluído fica `CANCELLED`."""
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)
    deleted = client.delete(f'/processes/{ctx.process_id}', headers=ORIGIN)
    assert deleted.status_code == HTTPStatus.NO_CONTENT, deleted.text

    response = decide(client, ctx.process_id, **APPROVE)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'invalid_transition'
    assert await decisions(session, ctx.process_id) == []
    assert await runs(session, ctx.process_id, 'sample_receipt') == []
