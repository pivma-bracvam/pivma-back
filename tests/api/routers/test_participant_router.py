# ruff: noqa: PLR2004, PLR0914, PLR0915

from datetime import datetime, timezone
from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    AuditEvent,
    Permission,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.factories import (
    AssignmentFactory,
    InstitutionFactory,
    LaboratoryFactory,
    UserFactory,
    UserInstitutionalAffiliationFactory,
)
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)

ORIGIN = {'Origin': 'https://testserver'}


def authenticate(client, user):
    client.cookies.set(
        'access_token', create_access_token(user.id, Settings().JWT_SECRET_KEY)
    )


async def create_process(session):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.flush()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.flush()
    process = ProcessInstanceFactory(template_version=version)
    session.add(process)
    await session.commit()
    await session.refresh(process)
    return process


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


async def create_active_laboratory_affiliation(session, target_user):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.flush()
    affiliation = UserInstitutionalAffiliationFactory(
        user=target_user, institution=institution, laboratory=laboratory
    )
    session.add(affiliation)
    await session.commit()
    await session.refresh(laboratory)
    await session.refresh(affiliation)
    return laboratory, affiliation


def create_participant(
    client, process_id, user_id, role_key, laboratory_id=None
):
    payload = {'user_id': str(user_id), 'role_key': role_key}
    if laboratory_id is not None:
        payload['laboratory_id'] = str(laboratory_id)
    return client.post(
        f'/processes/{process_id}/participants', headers=ORIGIN, json=payload
    )


def revoke_participant(client, process_id, assignment_id):
    return client.delete(
        f'/processes/{process_id}/participants/{assignment_id}',
        headers=ORIGIN,
    )


def declare_conflict(
    client, process_id, assignment_id, has_conflict, justification='Válida'
):
    return client.post(
        f'/processes/{process_id}/participants/{assignment_id}/conflicts',
        headers=ORIGIN,
        json={'has_conflict': has_conflict, 'justification': justification},
    )


# --- A-D: designações ---


@pytest.mark.asyncio
async def test_administrator_creates_valid_individual_assignment(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)

    response = create_participant(
        client, process.id, other_user.id, 'study_manager'
    )
    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body['user_id'] == str(other_user.id)
    assert body['role_key'] == 'study_manager'
    assert body['active'] is True


@pytest.mark.asyncio
async def test_group_manager_creates_valid_assignment_in_own_process(
    session, client, user, other_user
):
    process = await create_process(session)
    manager_assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='group_manager'
    )
    session.add(manager_assignment)
    await session.commit()
    authenticate(client, user)

    response = create_participant(
        client, process.id, other_user.id, 'study_manager'
    )
    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_manager_creates_laboratory_assignment_with_current_affiliation(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    laboratory, _ = await create_active_laboratory_affiliation(
        session, other_user
    )
    authenticate(client, user)

    response = create_participant(
        client, process.id, other_user.id, 'lead_laboratory', laboratory.id
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['laboratory_id'] == str(laboratory.id)


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['user', 'laboratory'])
async def test_unknown_target_returns_404_for_authorized_manager(
    session, client, user, other_user, target
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)

    if target == 'user':
        response = create_participant(
            client, process.id, uuid4(), 'study_manager'
        )
    else:
        response = create_participant(
            client, process.id, other_user.id, 'lead_laboratory', uuid4()
        )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['user', 'laboratory'])
async def test_inactive_target_returns_409(
    session, client, user, other_user, target
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)

    if target == 'user':
        other_user.deleted_at = datetime.now(timezone.utc)
        session.add(other_user)
        await session.commit()
        response = create_participant(
            client, process.id, other_user.id, 'study_manager'
        )
    else:
        laboratory, _ = await create_active_laboratory_affiliation(
            session, other_user
        )
        laboratory.deleted_at = datetime.now(timezone.utc)
        session.add(laboratory)
        await session.commit()
        response = create_participant(
            client,
            process.id,
            other_user.id,
            'lead_laboratory',
            laboratory.id,
        )
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_unknown_process_returns_404_for_global_manager(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    authenticate(client, user)

    response = create_participant(
        client, uuid4(), other_user.id, 'study_manager'
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_logically_deleted_process_returns_409(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    process.deleted_at = datetime.now(timezone.utc)
    session.add(process)
    await session.commit()
    authenticate(client, user)

    response = create_participant(
        client, process.id, other_user.id, 'study_manager'
    )
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_missing_current_laboratory_affiliation_returns_409(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.commit()
    authenticate(client, user)

    response = create_participant(
        client, process.id, other_user.id, 'lead_laboratory', laboratory.id
    )
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_sequential_active_duplicate_returns_409(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)

    first = create_participant(
        client, process.id, other_user.id, 'study_manager'
    )
    assert first.status_code == HTTPStatus.CREATED
    duplicate = create_participant(
        client, process.id, other_user.id, 'study_manager'
    )
    assert duplicate.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_effective_group_manager_completes_valid_revocation(
    session, client, user, other_user
):
    process = await create_process(session)
    manager_assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='group_manager'
    )
    session.add(manager_assignment)
    await session.commit()
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    response = revoke_participant(client, process.id, created['id'])
    assert response.status_code == HTTPStatus.NO_CONTENT


@pytest.mark.asyncio
async def test_repeated_revocation_returns_409(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    revoke_participant(client, process.id, created['id'])

    second = revoke_participant(client, process.id, created['id'])
    assert second.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_new_equivalent_assignment_after_revocation_returns_201(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    first = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    revoke_participant(client, process.id, first['id'])

    second = create_participant(
        client, process.id, other_user.id, 'study_manager'
    )
    assert second.status_code == HTTPStatus.CREATED
    assert second.json()['id'] != first['id']


@pytest.mark.asyncio
async def test_manager_listing_returns_all_active_cycles(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    create_participant(client, process.id, other_user.id, 'study_manager')
    create_participant(client, process.id, user.id, 'statistician')

    listed = client.get(f'/processes/{process.id}/participants')
    assert listed.status_code == HTTPStatus.OK
    assert {item['role_key'] for item in listed.json()} == {
        'study_manager',
        'statistician',
    }


@pytest.mark.asyncio
async def test_participant_listing_returns_only_own_cycles(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    create_participant(client, process.id, other_user.id, 'study_manager')
    create_participant(client, process.id, user.id, 'statistician')

    authenticate(client, other_user)
    listed = client.get(f'/processes/{process.id}/participants')
    assert listed.status_code == HTTPStatus.OK
    assert [item['user_id'] for item in listed.json()] == [str(other_user.id)]


@pytest.mark.asyncio
async def test_listing_signals_null_conflict_without_declaration(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    create_participant(client, process.id, other_user.id, 'study_manager')

    listed = client.get(f'/processes/{process.id}/participants')
    assert listed.json()[0]['has_conflict'] is None


@pytest.mark.asyncio
async def test_listing_signals_ineffective_after_losing_affiliation(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    laboratory, affiliation = await create_active_laboratory_affiliation(
        session, other_user
    )
    authenticate(client, user)
    create_participant(
        client, process.id, other_user.id, 'lead_laboratory', laboratory.id
    )

    affiliation.deleted_at = datetime.now(timezone.utc)
    session.add(affiliation)
    await session.commit()

    listed = client.get(f'/processes/{process.id}/participants')
    assert listed.json()[0]['effective'] is False


@pytest.mark.asyncio
async def test_manager_listing_signals_true_conflict_after_current_declaration(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    declare_conflict(client, process.id, created['id'], True)

    authenticate(client, user)
    listed = client.get(f'/processes/{process.id}/participants')
    assert listed.json()[0]['has_conflict'] is True


# --- A-C: conflito e histórico ---


@pytest.mark.asyncio
async def test_owner_declares_conflict_on_active_assignment(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    response = declare_conflict(client, process.id, created['id'], True)
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['has_conflict'] is True


@pytest.mark.asyncio
async def test_owner_declares_absence_of_conflict_preserving_previous(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    first = declare_conflict(client, process.id, created['id'], True)
    second = declare_conflict(client, process.id, created['id'], False)
    assert second.status_code == HTTPStatus.CREATED

    authenticate(client, user)
    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    item = next(
        i for i in history['items'] if i['assignment']['id'] == created['id']
    )
    assert len(item['declarations']) == 2
    assert item['declarations'][0]['id'] == first.json()['id']


@pytest.mark.asyncio
async def test_other_user_cannot_declare_on_behalf_of_owner(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    third_user = UserFactory()
    session.add(third_user)
    await session.commit()
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, third_user)
    response = declare_conflict(client, process.id, created['id'], True)
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_owner_cannot_declare_on_revoked_cycle(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    revoke_participant(client, process.id, created['id'])

    authenticate(client, other_user)
    response = declare_conflict(client, process.id, created['id'], True)
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_manager_history_exposes_declaration_justification(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    declare_conflict(client, process.id, created['id'], True, 'Motivo claro')

    authenticate(client, user)
    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    item = next(
        i for i in history['items'] if i['assignment']['id'] == created['id']
    )
    assert item['declarations'][0]['justification'] == 'Motivo claro'


@pytest.mark.asyncio
async def test_owner_history_exposes_own_declaration_justification(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    declare_conflict(
        client, process.id, created['id'], True, 'Motivo do titular'
    )
    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    item = next(
        i for i in history['items'] if i['assignment']['id'] == created['id']
    )
    assert item['declarations'][0]['justification'] == 'Motivo do titular'


@pytest.mark.asyncio
async def test_manager_history_includes_active_and_revoked_cycles(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    first = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    revoke_participant(client, process.id, first['id'])
    second = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    ids = {item['assignment']['id'] for item in history['items']}
    assert {first['id'], second['id']}.issubset(ids)


@pytest.mark.asyncio
async def test_participant_history_includes_only_own_cycles(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    other_cycle = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    create_participant(client, process.id, user.id, 'statistician')

    authenticate(client, other_user)
    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    ids = {item['assignment']['id'] for item in history['items']}
    assert ids == {other_cycle['id']}


@pytest.mark.asyncio
async def test_history_orders_cycles_by_assignment_descending(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    create_participant(client, process.id, other_user.id, 'study_manager')
    create_participant(client, process.id, other_user.id, 'statistician')

    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    assert history['items'][0]['assignment']['role_key'] == 'statistician'
    assert history['items'][1]['assignment']['role_key'] == 'study_manager'


@pytest.mark.asyncio
async def test_history_orders_declarations_ascending(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    declare_conflict(client, process.id, created['id'], True, 'Primeira')
    declare_conflict(client, process.id, created['id'], False, 'Segunda')

    authenticate(client, user)
    history = client.get(
        f'/processes/{process.id}/participants/history'
    ).json()
    item = next(
        i for i in history['items'] if i['assignment']['id'] == created['id']
    )
    assert [d['justification'] for d in item['declarations']] == [
        'Primeira',
        'Segunda',
    ]


@pytest.mark.asyncio
async def test_history_pagination_rejects_limit_above_maximum(
    session, client, user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)

    response = client.get(
        f'/processes/{process.id}/participants/history?limit=201'
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_history_pagination_applies_offset_and_limit_without_repeats(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    for role in ('study_manager', 'statistician', 'peer_reviewer'):
        create_participant(client, process.id, other_user.id, role)

    first_page = client.get(
        f'/processes/{process.id}/participants/history?offset=0&limit=1'
    ).json()
    second_page = client.get(
        f'/processes/{process.id}/participants/history?offset=1&limit=1'
    ).json()
    all_items = client.get(
        f'/processes/{process.id}/participants/history?offset=0&limit=100'
    ).json()

    combined_ids = [
        first_page['items'][0]['assignment']['id'],
        second_page['items'][0]['assignment']['id'],
    ]
    assert combined_ids == [
        item['assignment']['id'] for item in all_items['items'][:2]
    ]
    assert len(set(combined_ids)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'scenario', ['foreign_assignment', 'unknown_assignment']
)
async def test_owner_forbidden_response_matches_for_foreign_and_unknown(
    session, client, user, other_user, scenario
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, user.id, 'statistician'
    ).json()

    authenticate(client, other_user)
    if scenario == 'foreign_assignment':
        response = declare_conflict(client, process.id, created['id'], True)
    else:
        response = declare_conflict(client, process.id, uuid4(), True)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {'detail': 'Forbidden'}


# --- A-A: auditoria das mutações ---


@pytest.mark.asyncio
async def test_assignment_creation_records_required_event_context(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == 'PARTICIPANT_ASSIGNED',
            AuditEvent.process_instance_id == process.id,
        )
    )
    assert event.context_data['assignment_id'] == created['id']
    assert event.context_data['participant_user_id'] == str(other_user.id)
    assert event.context_data['role_key'] == 'study_manager'
    assert event.context_data['result'] == 'success'
    assert event.context_data['source'] == 'api'


@pytest.mark.asyncio
async def test_revocation_records_required_event_context(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    revoke_participant(client, process.id, created['id'])

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == 'PARTICIPANT_REVOKED',
            AuditEvent.process_instance_id == process.id,
        )
    )
    assert event.context_data['assignment_id'] == created['id']
    assert event.context_data['result'] == 'success'
    assert event.context_data['source'] == 'api'


@pytest.mark.asyncio
async def test_conflict_declaration_records_required_event_context(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, other_user)
    declare_conflict(client, process.id, created['id'], True, 'Motivo')

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == 'CONFLICT_DECLARED',
            AuditEvent.process_instance_id == process.id,
        )
    )
    assert event.context_data['assignment_id'] == created['id']
    assert event.context_data['has_conflict'] is True
    assert event.context_data['justification'] == 'Motivo'


@pytest.mark.asyncio
async def test_rejected_duplicate_assignment_does_not_record_new_event(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    process_id = process.id
    authenticate(client, user)
    create_participant(client, process_id, other_user.id, 'study_manager')
    create_participant(client, process_id, other_user.id, 'study_manager')

    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'PARTICIPANT_ASSIGNED',
            AuditEvent.process_instance_id == process_id,
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_rejected_repeated_revocation_does_not_record_new_event(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()
    revoke_participant(client, process.id, created['id'])
    revoke_participant(client, process.id, created['id'])

    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'PARTICIPANT_REVOKED',
            AuditEvent.process_instance_id == process.id,
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_rejected_third_party_declaration_does_not_record_event(
    session, client, user, other_user
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    third_user = UserFactory()
    session.add(third_user)
    await session.commit()
    authenticate(client, user)
    created = create_participant(
        client, process.id, other_user.id, 'study_manager'
    ).json()

    authenticate(client, third_user)
    declare_conflict(client, process.id, created['id'], True)

    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'CONFLICT_DECLARED',
            AuditEvent.process_instance_id == process.id,
        )
    )
    assert count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('cause', ['unknown_target', 'missing_affiliation'])
async def test_rejected_assignment_does_not_record_event(
    session, client, user, other_user, cause
):
    await grant_participants_management(session, user)
    process = await create_process(session)
    authenticate(client, user)

    if cause == 'unknown_target':
        create_participant(client, process.id, uuid4(), 'study_manager')
    else:
        institution = InstitutionFactory()
        session.add(institution)
        await session.flush()
        laboratory = LaboratoryFactory(institution=institution)
        session.add(laboratory)
        await session.commit()
        create_participant(
            client,
            process.id,
            other_user.id,
            'lead_laboratory',
            laboratory.id,
        )

    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.event_type == 'PARTICIPANT_ASSIGNED',
            AuditEvent.process_instance_id == process.id,
        )
    )
    assert count == 0
