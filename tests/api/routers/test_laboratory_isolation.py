# ruff: noqa: PLR2004
"""Isolamento entre laboratórios em `/tasks` e na trilha (Spec 036, R13)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import AuditEvent, Task
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    complete_chain,
    complete_lab,
    end_affiliation,
    frozen_lab_process,
    reopen,
    runs_by_lab,
    waive,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import assign_lab, new_laboratory


def _tasks(client, user, **params):
    authenticate(client, user)
    resp = client.get('/tasks', params=params)
    assert resp.status_code == HTTPStatus.OK
    return resp.json()


def _timeline(client, user, process_id):
    authenticate(client, user)
    resp = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert resp.status_code == HTTPStatus.OK
    return resp.json()['data']


async def _task_of_lab(session, ctx, key, index):
    run = (await runs_by_lab(session, ctx.process_id, key))[ctx.labs[index].id]
    return await session.scalar(
        select(Task).where(Task.activity_run_id == run.id)
    )


def _completed_labs(events):
    return {
        e['context_data']['laboratory_id']
        for e in events
        if e['event_type'] == 'LABORATORY_RUN_COMPLETED'
    }


@pytest.mark.asyncio
async def test_lab_user_lists_only_own_lab_task(client, session):
    ctx = await frozen_lab_process(session)
    own = await _task_of_lab(session, ctx, 'receipt', 0)

    body = _tasks(client, ctx.lab_users[0], activity_key='receipt')

    assert [task['id'] for task in body['data']] == [str(own.id)]
    assert body['pagination']['total_items'] == 1


@pytest.mark.asyncio
async def test_facets_count_only_own_lab_tasks(client, session):
    ctx = await frozen_lab_process(session)

    body = _tasks(client, ctx.lab_users[0], include='facets')

    assert body['facets']['activity_key'] == {'receipt': 1}


@pytest.mark.asyncio
async def test_lab_user_gets_404_for_other_lab_task_detail(client, session):
    ctx = await frozen_lab_process(session)
    other = await _task_of_lab(session, ctx, 'receipt', 1)
    authenticate(client, ctx.lab_users[0])

    resp = client.get(f'/tasks/{other.id}')

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail']['message'] == 'Tarefa não encontrada.'


@pytest.mark.asyncio
async def test_statistician_sees_no_lab_task(client, session):
    ctx = await frozen_lab_process(session)

    body = _tasks(client, ctx.statistician, activity_key='receipt')

    assert body['data'] == []


@pytest.mark.asyncio
async def test_lead_laboratory_of_other_lab_sees_no_lab_task(client, session):
    ctx = await frozen_lab_process(session)
    lead = await assign_lab(
        session,
        ctx.process_id,
        await new_laboratory(session),
        role_key='lead_laboratory',
    )
    from pivma.core.database.models import User  # noqa: PLC0415

    lead_user = await session.get(User, lead.user_id)

    body = _tasks(client, lead_user, activity_key='receipt')

    assert body['data'] == []


@pytest.mark.asyncio
async def test_group_manager_sees_every_lab_task(client, session):
    ctx = await frozen_lab_process(session)

    body = _tasks(client, ctx.group_manager, activity_key='receipt')

    assert body['pagination']['total_items'] == 3


@pytest.mark.asyncio
async def test_bracvam_sees_every_lab_task(client, session, bracvam_user):
    ctx = await frozen_lab_process(session)

    body = _tasks(
        client,
        bracvam_user,
        activity_key='receipt',
        process_id=str(ctx.process_id),
    )

    assert body['pagination']['total_items'] == 3


@pytest.mark.asyncio
async def test_lab_user_who_is_also_group_manager_sees_every_lab(
    client, session
):
    ctx = await frozen_lab_process(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.lab_users[0],
        role_key='group_manager',
    )

    body = _tasks(client, ctx.lab_users[0], activity_key='receipt')

    assert body['pagination']['total_items'] == 3


@pytest.mark.asyncio
async def test_lab_user_without_effective_designation_sees_no_task(
    client, session
):
    ctx = await frozen_lab_process(session)
    await end_affiliation(session, ctx.lab_users[0])

    body = _tasks(client, ctx.lab_users[0], activity_key='receipt')

    assert body['data'] == []


@pytest.mark.asyncio
async def test_single_activity_tasks_unchanged_for_statistician(
    client, session
):
    ctx = await frozen_lab_process(session)
    for index in range(3):
        await complete_chain(session, ctx, index)

    body = _tasks(client, ctx.statistician, activity_key='statistics')

    assert body['pagination']['total_items'] == 1
    assert body['data'][0]['can_act'] is True


@pytest.mark.asyncio
async def test_timeline_hides_other_lab_completion(client, session):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', 0)
    await complete_lab(session, ctx, 'receipt', 1)

    events = _timeline(client, ctx.lab_users[0], ctx.process_id)

    assert _completed_labs(events) == {str(ctx.labs[0].id)}


@pytest.mark.asyncio
async def test_timeline_shows_every_completion_to_group_manager(
    client, session
):
    ctx = await frozen_lab_process(session)
    for index in range(3):
        await complete_lab(session, ctx, 'receipt', index)

    events = _timeline(client, ctx.group_manager, ctx.process_id)

    assert _completed_labs(events) == {str(lab.id) for lab in ctx.labs}


@pytest.mark.asyncio
async def test_participant_events_with_laboratory_keep_current_rule(
    client, session
):
    ctx = await frozen_lab_process(session)
    lab_b_user = ctx.lab_users[1]
    session.add(
        AuditEvent(
            process_instance_id=ctx.process_id,
            user_id=ctx.creator.id,
            event_type='PARTICIPANT_ASSIGNED',
            context_data={
                'participant_user_id': str(lab_b_user.id),
                'role_key': 'participating_laboratory',
                'laboratory_id': str(ctx.labs[1].id),
            },
        )
    )
    await session.commit()

    def assigned(user):
        return [
            e
            for e in _timeline(client, user, ctx.process_id)
            if e['event_type'] == 'PARTICIPANT_ASSIGNED'
            and e['context_data'].get('laboratory_id')
        ]

    assert len(assigned(lab_b_user)) == 1
    assert assigned(ctx.lab_users[0]) == []


def _waived(events):
    return [e for e in events if e['event_type'] == 'LABORATORY_WAIVED']


@pytest.mark.asyncio
async def test_group_manager_sees_waiver_events(client, session):
    ctx = await frozen_lab_process(session)
    await waive(session, ctx, 2)

    events = _waived(_timeline(client, ctx.group_manager, ctx.process_id))

    assert len(events) == 2
    assert {e['activity_run_id'] for e in events} != {None}


@pytest.mark.asyncio
async def test_waived_lab_does_not_see_waiver_events(client, session):
    ctx = await frozen_lab_process(session)
    await waive(session, ctx, 2)

    assert _waived(_timeline(client, ctx.lab_users[2], ctx.process_id)) == []


@pytest.mark.asyncio
async def test_other_lab_does_not_see_waiver_events(client, session):
    ctx = await frozen_lab_process(session)
    await waive(session, ctx, 2)

    assert _waived(_timeline(client, ctx.lab_users[0], ctx.process_id)) == []


@pytest.mark.asyncio
async def test_reopen_event_reaches_only_reopened_lab_and_managers(
    client, session
):
    ctx = await frozen_lab_process(session)
    for index in range(3):
        await complete_chain(session, ctx, index)
    await reopen(session, ctx, 'upload', 1)

    def reopened(user):
        return [
            e
            for e in _timeline(client, user, ctx.process_id)
            if e['event_type'] == 'LABORATORY_RUN_REOPENED'
        ]

    assert reopened(ctx.lab_users[0]) == []
    assert len(reopened(ctx.lab_users[1])) == 1
    assert len(reopened(ctx.group_manager)) == 1
