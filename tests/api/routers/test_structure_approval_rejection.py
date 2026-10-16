# ruff: noqa: PLR2004
"""Reprovação da homologação e reexecução dos pontos (Spec 042, US2).

A reprovação conclui a execução da homologação, a deixa bloqueada e abre
uma execução nova em cada ponto reprovado, sem tocar na anterior. A
homologação reabre sozinha quando o último ponto reprovado conclui.
"""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core import sample_service
from pivma.core.database.models import Assignment, BlindSampleCode
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import _user, lab_user, new_laboratory
from tests.factories.structure_approval_factory import (
    activity,
    complete_role,
    decide,
    decisions,
    designate,
    events,
    finish_samples,
    run_tasks,
    runs,
    structure_process,
)

LABS = 'assign_participating_laboratory'
REASON = 'Laboratório errado.'


def _reject(client, process_id, *keys):
    return decide(
        client,
        process_id,
        outcome='REJECTED',
        justification='Equipe incompleta.',
        rejected_points=[
            {'activity_key': key, 'reason': f'{REASON} ({key})'}
            for key in keys
        ],
    )


async def _rejected(client, session, bracvam_user, *keys):
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)
    ctx.response = _reject(client, ctx.process_id, *keys)
    assert ctx.response.status_code == HTTPStatus.OK, ctx.response.text
    return ctx


async def _codes(session, process_id) -> dict:
    """Códigos ativos por laboratório."""
    rows = await session.execute(
        select(BlindSampleCode.laboratory_id, BlindSampleCode.code).where(
            BlindSampleCode.process_instance_id == process_id,
            BlindSampleCode.deleted_at.is_(None),
        )
    )
    codes = {}
    for laboratory_id, code in rows:
        codes.setdefault(laboratory_id, set()).add(code)
    return codes


@pytest.mark.asyncio
async def test_rejection_responds_blocked_with_reopened_point(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    body = ctx.response.json()
    assert body['outcome'] == 'REJECTED'
    assert body['status'] == 'BLOCKED'
    assert body['reopened'] == [{'activity_key': LABS, 'run_number': 2}]


@pytest.mark.asyncio
async def test_rejected_point_gets_a_new_run_with_the_reason(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    point = await activity(session, ctx.process_id, LABS)
    second = (await runs(session, ctx.process_id, LABS))[1]
    [task] = await run_tasks(session, second.id)
    assert point.status == 'IN_PROGRESS'
    assert (second.run_number, second.status) == (2, 'IN_PROGRESS')
    assert second.execution_reason == f'{REASON} ({LABS})'
    assert (task.status, task.assigned_role) == ('READY', 'group_manager')


@pytest.mark.asyncio
async def test_previous_run_of_the_point_stays_completed(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    [first] = await runs(session, ctx.process_id, LABS)
    completed_at = first.completed_at
    authenticate(client, bracvam_user)

    _reject(client, ctx.process_id, LABS)

    first = (await runs(session, ctx.process_id, LABS))[0]
    assert first.status == 'COMPLETED'
    assert first.completed_at == completed_at


@pytest.mark.asyncio
async def test_rejection_blocks_the_approval_and_closes_its_run(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    approval = await activity(session, ctx.process_id)
    [run] = await runs(session, ctx.process_id)
    [task] = await run_tasks(session, run.id)
    assert approval.status == 'BLOCKED'
    assert approval.blocked_reason == (
        'Aguardando a reexecução dos pontos reprovados.'
    )
    assert (run.status, task.status) == ('COMPLETED', 'COMPLETED')


@pytest.mark.asyncio
async def test_rejection_records_the_decision_with_the_points(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    [decision] = await decisions(session, ctx.process_id)
    assert decision.outcome == 'REJECTED'
    assert decision.justification == 'Equipe incompleta.'
    assert decision.rejected_points == [
        {'activity_key': LABS, 'reason': f'{REASON} ({LABS})'}
    ]


@pytest.mark.asyncio
async def test_rejection_records_rejected_and_reopened_events(
    client, session, bracvam_user
):
    keys = (LABS, 'sample_definition')
    ctx = await _rejected(client, session, bracvam_user, *keys)

    [decision] = await decisions(session, ctx.process_id)
    [rejected] = await events(session, ctx.process_id, 'STRUCTURE_REJECTED')
    reopened = await events(session, ctx.process_id, 'ACTIVITY_REOPENED')
    assert rejected.activity_run_id == decision.activity_run_id
    assert rejected.context_data == {
        'decision_id': str(decision.id),
        'justification': 'Equipe incompleta.',
        'rejected_points': decision.rejected_points,
    }
    by_key = {e.context_data['activity_key']: e for e in reopened}
    assert set(by_key) == set(keys)
    for key in keys:
        second = (await runs(session, ctx.process_id, key))[1]
        assert by_key[key].activity_run_id == second.id
        assert by_key[key].context_data == {
            'activity_key': key,
            'previous_run_number': 1,
            'run_number': 2,
            'reason': f'{REASON} ({key})',
        }


@pytest.mark.asyncio
async def test_approval_reopens_only_when_the_last_rejected_point_completes(
    client, session, bracvam_user
):
    ctx = await _rejected(
        client, session, bracvam_user, 'assign_statistician', 'assign_sponsor'
    )

    await designate(session, ctx, await _user(session), 'statistician')
    await complete_role(session, ctx, 'statistician')
    assert (await activity(session, ctx.process_id)).status == 'BLOCKED'
    assert len(await runs(session, ctx.process_id)) == 1

    await complete_role(session, ctx, 'sponsor')
    approval = await activity(session, ctx.process_id)
    second = (await runs(session, ctx.process_id))[1]
    [task] = await run_tasks(session, second.id)
    [unblocked] = [
        e
        for e in await events(session, ctx.process_id, 'ACTIVITY_UNBLOCKED')
        if e.activity_run_id == second.id
    ]
    assert approval.status == 'IN_PROGRESS'
    assert (second.run_number, task.status) == (2, 'READY')
    assert unblocked.context_data['activity_key'] == 'structure_approval'


@pytest.mark.asyncio
async def test_rejecting_group_manager_keeps_its_dependents_completed(
    client, session, bracvam_user
):
    ctx = await _rejected(
        client, session, bracvam_user, 'assign_group_manager'
    )

    for key in ('assign_sample_selection_group', LABS, 'assign_statistician'):
        assert (await activity(session, ctx.process_id, key)).status == (
            'COMPLETED'
        ), key
        assert len(await runs(session, ctx.process_id, key)) == 1


@pytest.mark.asyncio
async def test_reopened_samples_accept_changes_and_regenerate_codes(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, 'sample_definition')
    before = await _codes(session, ctx.process_id)
    kept, gone = ctx.laboratories
    revoked = await session.get(Assignment, ctx.lab_assignments[1].id)
    revoked.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    added = await new_laboratory(session)
    await designate(
        session,
        ctx,
        await lab_user(session, added),
        'participating_laboratory',
        added,
    )

    await sample_service.update_substance(
        session,
        ctx.process_id,
        ctx.substance['id'],
        ctx.selector.id,
        {'lot': 'L-2026-10'},
    )
    await finish_samples(session, ctx)

    after = await _codes(session, ctx.process_id)
    assert (
        await activity(session, ctx.process_id, 'sample_definition')
    ).status == ('COMPLETED')
    assert after[kept.id] == before[kept.id]
    assert gone.id not in after
    assert len(after[added.id]) == 1


@pytest.mark.asyncio
async def test_rejection_keeps_sample_receipt_closed(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    receipt = await activity(session, ctx.process_id, 'sample_receipt')
    assert receipt.status == 'BLOCKED'
    assert await runs(session, ctx.process_id, 'sample_receipt') == []


def _timeline(client, process_id, event_type):
    response = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return [
        e for e in response.json()['data'] if e['event_type'] == event_type
    ]


@pytest.mark.asyncio
async def test_point_owner_reads_the_reason_in_the_timeline(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    authenticate(client, ctx.manager)
    [reopened] = _timeline(client, ctx.process_id, 'ACTIVITY_REOPENED')
    assert reopened['context_data']['reason'] == f'{REASON} ({LABS})'


@pytest.mark.asyncio
async def test_only_bracvam_sees_the_rejection_in_the_timeline(
    client, session, bracvam_user
):
    ctx = await _rejected(client, session, bracvam_user, LABS)

    authenticate(client, ctx.manager)
    assert _timeline(client, ctx.process_id, 'STRUCTURE_REJECTED') == []
    authenticate(client, bracvam_user)
    assert len(_timeline(client, ctx.process_id, 'STRUCTURE_REJECTED')) == 1
