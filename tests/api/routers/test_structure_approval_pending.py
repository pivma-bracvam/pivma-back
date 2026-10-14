"""Pendências da homologação, calculadas na hora (Spec 042, research R3).

Um teste por regra de data-model.md ("Pendências"). Com a homologação
aberta, cada pendência também recusa a aprovação sem mudar nada.
"""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import Assignment, Laboratory
from tests.api.routers.test_invites_router import create_invite, list_invites
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.sample_factory import _user, lab_user, new_laboratory
from tests.factories.structure_approval_factory import (
    activity,
    decide,
    designate,
    finish_samples,
    panel,
    runs,
    snapshot,
    structure_process,
)

APPROVE = {'outcome': 'APPROVED', 'justification': 'Estrutura conferida.'}


@pytest.mark.asyncio
async def test_late_additional_invite_does_not_block_structure_approval(
    client, session, bracvam_user
):
    """FR-008: convite adicional não impede homologar o cargo preenchido."""
    ctx = await structure_process(session, bracvam_user)
    key = 'assign_statistician'
    previous_runs = [r.id for r in await runs(session, ctx.process_id, key)]
    authenticate(client, ctx.manager)
    invited = create_invite(
        client, ctx.process_id, 'outro.estatistico@example.com', 'statistician'
    )
    assert invited.status_code == HTTPStatus.CREATED, invited.text
    assert invited.json()['status'] == 'pending'

    authenticate(client, bracvam_user)
    assert (await activity(session, ctx.process_id, key)).status == 'COMPLETED'
    assert [
        r.id for r in await runs(session, ctx.process_id, key)
    ] == previous_runs
    assert _pending(client, ctx.process_id, key) == []
    approved = decide(client, ctx.process_id, **APPROVE)
    assert approved.status_code == HTTPStatus.OK, approved.text
    assert approved.json()['status'] == 'COMPLETED'

    authenticate(client, ctx.manager)
    [invite] = list_invites(client, ctx.process_id).json()['data']
    assert invite['id'] == invited.json()['id']
    assert invite['status'] == 'pending'


def _pending(client, process_id, activity_key):
    points = panel(client, process_id).json()['points']
    point = next(p for p in points if p['activity_key'] == activity_key)
    return [
        (
            item['code'],
            item['laboratory']['id'] if item['laboratory'] else None,
        )
        for item in point['pending']
    ]


async def _assert_approval_refused(client, session, ctx):
    before = await snapshot(session, ctx.process_id)

    response = decide(client, ctx.process_id, **APPROVE)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['detail']['code'] == 'structure_pending'
    assert await snapshot(session, ctx.process_id) == before


async def _revoke(session, assignment_id):
    assignment = await session.get(Assignment, assignment_id)
    assignment.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()


async def _collaborator(session, ctx):
    return await session.scalar(
        select(Assignment.id).where(
            Assignment.process_instance_id == ctx.process_id,
            Assignment.role_key == 'collaborator',
            Assignment.revoked_at.is_(None),
        )
    )


@pytest.mark.asyncio
async def test_point_not_completed_is_pending(client, session, bracvam_user):
    ctx = await structure_process(
        session, bracvam_user, complete_samples=False
    )
    authenticate(client, bracvam_user)

    assert _pending(client, ctx.process_id, 'sample_definition') == [
        ('activity_not_completed', None)
    ]


@pytest.mark.asyncio
async def test_role_without_designation_is_pending(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    await _revoke(session, await _collaborator(session, ctx))
    authenticate(client, bracvam_user)

    assert _pending(client, ctx.process_id, 'assign_collaborator') == [
        ('role_without_designation', None)
    ]
    await _assert_approval_refused(client, session, ctx)


@pytest.mark.asyncio
async def test_laboratory_without_codes_is_pending(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    added = await new_laboratory(session)
    await designate(
        session,
        ctx,
        await lab_user(session, added),
        'participating_laboratory',
        added,
    )
    authenticate(client, bracvam_user)

    assert _pending(client, ctx.process_id, 'sample_definition') == [
        ('laboratory_without_codes', str(added.id))
    ]
    await _assert_approval_refused(client, session, ctx)


@pytest.mark.asyncio
async def test_codes_without_laboratory_is_pending(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    await _revoke(session, ctx.lab_assignments[1].id)
    authenticate(client, bracvam_user)

    assert _pending(client, ctx.process_id, 'sample_definition') == [
        ('codes_without_laboratory', str(ctx.laboratories[1].id))
    ]
    await _assert_approval_refused(client, session, ctx)


@pytest.mark.asyncio
async def test_deleted_laboratory_is_pending_until_samples_are_redone(
    client, session, bracvam_user
):
    """O laboratório excluído do cadastro sai dos participantes ativos,
    mesmo com a designação ativa (research R3)."""
    ctx = await structure_process(session, bracvam_user)
    deleted = await session.get(Laboratory, ctx.laboratories[1].id)
    deleted.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    authenticate(client, bracvam_user)

    assert _pending(client, ctx.process_id, 'sample_definition') == [
        ('codes_without_laboratory', str(deleted.id))
    ]
    await _assert_approval_refused(client, session, ctx)

    rejected = decide(
        client,
        ctx.process_id,
        outcome='REJECTED',
        justification='Laboratório excluído.',
        rejected_points=[
            {'activity_key': 'sample_definition', 'reason': 'Refazer.'}
        ],
    )
    assert rejected.status_code == HTTPStatus.OK, rejected.text
    await finish_samples(session, ctx)

    assert _pending(client, ctx.process_id, 'sample_definition') == []


@pytest.mark.asyncio
async def test_pending_is_recomputed_at_decision_time(
    client, session, bracvam_user
):
    ctx = await structure_process(session, bracvam_user)
    await _revoke(session, await _collaborator(session, ctx))
    await designate(session, ctx, await _user(session), 'collaborator')
    authenticate(client, bracvam_user)

    response = decide(client, ctx.process_id, **APPROVE)

    assert response.status_code == HTTPStatus.OK, response.text
