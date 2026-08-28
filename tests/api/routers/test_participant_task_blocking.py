# ruff: noqa: PLR2004, PLR0914, PLR0915

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    AuditEvent,
    Decision,
    FieldReview,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
REVIEW_PAYLOAD = {
    'reviews': [{'field_key': 'method_title', 'status': 'CONFORME'}]
}
DECISION_PAYLOAD = {'outcome': 'APPROVED', 'justification': 'Aprovado.'}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


async def grant_participants_management(session, user):
    permission = Permission(
        code=PROCESS_PARTICIPANTS_MANAGE,
        description=PROCESS_PARTICIPANTS_MANAGE,
    )
    profile = AccessProfile(
        name=f'Participants admin {user.id}', description='admin'
    )
    session.add_all([permission, profile])
    await session.flush()
    session.add_all([
        AccessProfilePermission(
            profile_id=profile.id, permission_id=permission.id
        ),
        UserAccessProfile(user_id=user.id, profile_id=profile.id),
    ])
    await session.commit()


def create_participant(client, process_id, user_id, role_key):
    return client.post(
        f'/processes/{process_id}/participants',
        headers=ORIGIN,
        json={'user_id': str(user_id), 'role_key': role_key},
    )


def revoke_participant(client, process_id, assignment_id):
    return client.delete(
        f'/processes/{process_id}/participants/{assignment_id}',
        headers=ORIGIN,
    )


def declare_conflict(client, process_id, assignment_id, has_conflict):
    return client.post(
        f'/processes/{process_id}/participants/{assignment_id}/conflicts',
        headers=ORIGIN,
        json={'has_conflict': has_conflict, 'justification': 'Justificativa'},
    )


async def submit_to_triage(client, session):
    admin = UserFactory()
    session.add(admin)
    await session.commit()
    await grant_participants_management(session, admin)
    await bootstrap_all_templates(session)

    authenticate(client, admin)
    created = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Processo bloqueio de conflito',
        },
    )
    process_id = created.json()['id']
    client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {'method_title': 'Rascunho'}},
    )
    client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Método',
                'endpoint_target': 'phototoxicity',
                'scientific_justification': 'Justificativa suficiente.',
                'study_protocol_file': 'protocolo.pdf',
            }
        },
    )
    return admin, process_id


async def setup_reviewer(session, client, admin, process_id, role_key):
    reviewer = UserFactory()
    session.add(reviewer)
    await session.commit()
    authenticate(client, admin)
    assignment = create_participant(
        client, process_id, reviewer.id, role_key
    ).json()
    return reviewer, assignment


@pytest.mark.asyncio
async def test_current_conflict_blocks_field_review_with_403(session, client):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, assignment = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )

    authenticate(client, reviewer)
    declare_conflict(client, process_id, assignment['id'], True)
    response = client.post(
        f'/processes/{process_id}/triage/reviews', json=REVIEW_PAYLOAD
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_current_conflict_blocks_triage_decision_with_403(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, assignment = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )

    authenticate(client, reviewer)
    declare_conflict(client, process_id, assignment['id'], True)
    response = client.post(
        f'/processes/{process_id}/triage/decision', json=DECISION_PAYLOAD
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_absence_of_conflict_preserves_existing_review_path(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, _assignment = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )

    authenticate(client, reviewer)
    response = client.post(
        f'/processes/{process_id}/triage/reviews', json=REVIEW_PAYLOAD
    )
    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_later_false_declaration_restores_triage_decision(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, assignment = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )

    authenticate(client, reviewer)
    declare_conflict(client, process_id, assignment['id'], True)
    blocked = client.post(
        f'/processes/{process_id}/triage/decision', json=DECISION_PAYLOAD
    )
    assert blocked.status_code == HTTPStatus.FORBIDDEN

    declare_conflict(client, process_id, assignment['id'], False)
    restored = client.post(
        f'/processes/{process_id}/triage/decision', json=DECISION_PAYLOAD
    )
    assert restored.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_blocked_review_does_not_create_or_alter_field_review(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, assignment = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )

    authenticate(client, reviewer)
    declare_conflict(client, process_id, assignment['id'], True)
    client.post(f'/processes/{process_id}/triage/reviews', json=REVIEW_PAYLOAD)

    review_count = await session.scalar(
        select(func.count()).select_from(FieldReview)
    )
    event_count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'FIELD_REVIEWED',
            AuditEvent.process_instance_id == UUID(process_id),
        )
    )
    assert (review_count, event_count) == (0, 0)


@pytest.mark.asyncio
async def test_blocked_decision_does_not_create_decision_or_event(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, assignment = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )

    authenticate(client, reviewer)
    declare_conflict(client, process_id, assignment['id'], True)
    client.post(
        f'/processes/{process_id}/triage/decision', json=DECISION_PAYLOAD
    )

    decision_count = await session.scalar(
        select(func.count())
        .select_from(Decision)
        .where(Decision.process_instance_id == UUID(process_id))
    )
    event_count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type.in_(['TRIAGE_APPROVED', 'TRIAGE_REJECTED']),
            AuditEvent.process_instance_id == UUID(process_id),
        )
    )
    assert (decision_count, event_count) == (0, 0)


@pytest.mark.asyncio
async def test_conflict_in_one_role_blocks_action_authorized_by_another_role(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, first_role = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )
    authenticate(client, admin)
    create_participant(client, process_id, reviewer.id, 'statistician')

    authenticate(client, reviewer)
    declare_conflict(client, process_id, first_role['id'], True)
    response = client.post(
        f'/processes/{process_id}/triage/reviews', json=REVIEW_PAYLOAD
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_revoking_conflicted_cycle_restores_action_via_other_cycle(
    session, client
):
    admin, process_id = await submit_to_triage(client, session)
    reviewer, first_role = await setup_reviewer(
        session, client, admin, process_id, 'peer_reviewer'
    )
    authenticate(client, admin)
    create_participant(client, process_id, reviewer.id, 'statistician')

    authenticate(client, reviewer)
    declare_conflict(client, process_id, first_role['id'], True)
    blocked = client.post(
        f'/processes/{process_id}/triage/reviews', json=REVIEW_PAYLOAD
    )
    assert blocked.status_code == HTTPStatus.FORBIDDEN

    authenticate(client, admin)
    revoke_participant(client, process_id, first_role['id'])

    authenticate(client, reviewer)
    restored = client.post(
        f'/processes/{process_id}/triage/reviews', json=REVIEW_PAYLOAD
    )
    assert restored.status_code == HTTPStatus.OK
