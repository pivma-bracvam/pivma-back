"""Matriz de acesso por laboratório na API (Spec 037).

Completa `test_laboratory_isolation.py` (Spec 036) com os perfis e as
operações que ele não cobre. Laboratório A é `labs[0]`, B é `labs[1]`.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import Assignment, Task
from tests.api.routers.test_participant_router import (
    create_participant,
    revoke_participant,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    LAB_ACCESS_TEMPLATE,
    affiliate,
    complete_lab,
    frozen_lab_process,
    lead_and_participant,
    lead_of_lab,
    runs_by_lab,
)

LAB_A, LAB_B = 0, 1


async def _process(session):
    return await frozen_lab_process(session, template=LAB_ACCESS_TEMPLATE)


async def _task_id(session, ctx, index, key='receipt'):
    run = (await runs_by_lab(session, ctx.process_id, key))[ctx.labs[index].id]
    return str(
        await session.scalar(
            select(Task.id).where(Task.activity_run_id == run.id)
        )
    )


def _listed(client, user, process_id):
    authenticate(client, user)
    resp = client.get(
        '/tasks',
        params={'activity_key': 'receipt', 'process_id': str(process_id)},
    )
    assert resp.status_code == HTTPStatus.OK
    return {task['id'] for task in resp.json()['data']}


def _detail_status(client, user, task_id):
    authenticate(client, user)
    return client.get(f'/tasks/{task_id}').status_code


def _completed_labs(client, user, process_id):
    authenticate(client, user)
    resp = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    assert resp.status_code == HTTPStatus.OK
    return {
        e['context_data']['laboratory_id']
        for e in resp.json()['data']
        if e['event_type'] == 'LABORATORY_RUN_COMPLETED'
    }


async def _profile(session, ctx, name):
    if name == 'lead_of_b':
        return await lead_of_lab(session, ctx, LAB_B)
    if name == 'lead_of_b_participant_of_a':
        return await lead_and_participant(session, ctx, LAB_B, LAB_A)
    return {
        'sample_selection_group': ctx.selector,
        'statistician': ctx.statistician,
    }[name]


# --- US1 e US3: perfis sem acesso ao laboratório B --------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('profile', 'own_lab'),
    [
        ('lead_of_b', None),
        ('lead_of_b_participant_of_a', LAB_A),
        ('sample_selection_group', None),
        ('statistician', None),
    ],
)
async def test_profile_lists_only_own_lab_tasks(
    client, session, profile, own_lab
):
    ctx = await _process(session)
    user = await _profile(session, ctx, profile)
    expected = (
        set() if own_lab is None else {await _task_id(session, ctx, own_lab)}
    )

    assert _listed(client, user, ctx.process_id) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'profile',
    [
        'lead_of_b',
        'lead_of_b_participant_of_a',
        'sample_selection_group',
        'statistician',
    ],
)
async def test_profile_gets_404_for_lab_b_task(client, session, profile):
    ctx = await _process(session)
    user = await _profile(session, ctx, profile)
    task_b = await _task_id(session, ctx, LAB_B)

    assert _detail_status(client, user, task_b) == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'profile',
    [
        'lead_of_b',
        'lead_of_b_participant_of_a',
        'sample_selection_group',
        'statistician',
    ],
)
async def test_profile_does_not_see_lab_b_completion(client, session, profile):
    ctx = await _process(session)
    user = await _profile(session, ctx, profile)
    lab_b = str(ctx.labs[LAB_B].id)
    await complete_lab(session, ctx, 'receipt', LAB_B)

    assert lab_b not in _completed_labs(client, user, ctx.process_id)


@pytest.mark.asyncio
async def test_lead_and_participant_sees_own_lab_completion(client, session):
    ctx = await _process(session)
    user = await lead_and_participant(session, ctx, LAB_B, LAB_A)
    lab_a = str(ctx.labs[LAB_A].id)
    await complete_lab(session, ctx, 'receipt', LAB_A)

    assert _completed_labs(client, user, ctx.process_id) == {lab_a}


# --- US2: o próprio laboratório ---------------------------------------------


@pytest.mark.asyncio
async def test_owner_opens_own_task(client, session):
    ctx = await _process(session)
    task_a = await _task_id(session, ctx, LAB_A)

    assert (
        _detail_status(client, ctx.lab_users[LAB_A], task_a) == HTTPStatus.OK
    )


# --- US3: gestão do processo ------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize('profile', ['admin', 'bracvam'])
async def test_platform_profile_lists_every_lab_task(
    client, session, profile, ai_eval_admin, bracvam_user
):
    ctx = await _process(session)
    user = {'admin': ai_eval_admin, 'bracvam': bracvam_user}[profile]

    assert len(_listed(client, user, ctx.process_id)) == len(ctx.labs)


@pytest.mark.asyncio
@pytest.mark.parametrize('profile', ['group_manager', 'admin', 'bracvam'])
async def test_process_manager_opens_lab_b_task(
    client, session, profile, ai_eval_admin, bracvam_user
):
    ctx = await _process(session)
    user = {'admin': ai_eval_admin, 'bracvam': bracvam_user}.get(
        profile, ctx.group_manager
    )
    task_b = await _task_id(session, ctx, LAB_B)

    assert _detail_status(client, user, task_b) == HTTPStatus.OK


@pytest.mark.asyncio
@pytest.mark.parametrize('profile', ['admin', 'bracvam'])
async def test_platform_profile_sees_lab_b_completion(
    client, session, profile, ai_eval_admin, bracvam_user
):
    ctx = await _process(session)
    user = {'admin': ai_eval_admin, 'bracvam': bracvam_user}[profile]
    lab_b = str(ctx.labs[LAB_B].id)
    await complete_lab(session, ctx, 'receipt', LAB_B)

    assert lab_b in _completed_labs(client, user, ctx.process_id)


# --- US4: uma designação de participante por usuário no processo ------------


async def _participant_of_a_affiliated_to_b(session, ctx):
    user = ctx.lab_users[LAB_A]
    await affiliate(session, user, ctx.labs[LAB_B])
    return user


@pytest.mark.asyncio
async def test_second_participating_lab_designation_returns_409(
    client, session
):
    """Regra existente: o índice único de designação ativa (research R3)."""
    ctx = await _process(session)
    user = await _participant_of_a_affiliated_to_b(session, ctx)
    process_id, user_id = ctx.process_id, user.id
    lab_a, lab_b = ctx.labs[LAB_A].id, ctx.labs[LAB_B].id
    authenticate(client, ctx.group_manager)

    resp = create_participant(
        client, process_id, user_id, 'participating_laboratory', lab_b
    )

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail']['code'] == 'duplicate'
    labs = await session.scalars(
        select(Assignment.laboratory_id).where(
            Assignment.process_instance_id == process_id,
            Assignment.user_id == user_id,
        )
    )
    assert list(labs) == [lab_a]


@pytest.mark.asyncio
async def test_participating_lab_designation_after_revocation_returns_201(
    client, session
):
    ctx = await _process(session)
    user = await _participant_of_a_affiliated_to_b(session, ctx)
    assignment_id = await session.scalar(
        select(Assignment.id).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.user_id == user.id,
        )
    )
    authenticate(client, ctx.group_manager)
    revoked = revoke_participant(client, ctx.process_id, assignment_id)
    assert revoked.status_code == HTTPStatus.NO_CONTENT

    resp = create_participant(
        client,
        ctx.process_id,
        user.id,
        'participating_laboratory',
        ctx.labs[LAB_B].id,
    )

    assert resp.status_code == HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_lead_of_a_can_be_designated_participant_of_b(client, session):
    ctx = await _process(session)
    lead = await lead_of_lab(session, ctx, LAB_A)
    await affiliate(session, lead, ctx.labs[LAB_B])
    authenticate(client, ctx.group_manager)

    resp = create_participant(
        client,
        ctx.process_id,
        lead.id,
        'participating_laboratory',
        ctx.labs[LAB_B].id,
    )

    assert resp.status_code == HTTPStatus.CREATED
