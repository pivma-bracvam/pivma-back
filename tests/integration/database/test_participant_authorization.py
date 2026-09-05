from datetime import datetime, timezone
from uuid import UUID

import pytest

from pivma.core.authorization import (
    PROCESS_PARTICIPANTS_MANAGE,
    can_manage_participants,
    has_current_conflict,
    is_active_effective_proponent,
    participant_read_scope,
)
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from tests.factories import (
    AssignmentFactory,
    ConflictInterestDeclarationFactory,
)
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
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


async def grant_global_participants_management(session, user):
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


# --- I-A: autorização de gestão ---


@pytest.mark.asyncio
async def test_global_permission_authorizes_management_in_any_process(
    session, user
):
    await grant_global_participants_management(session, user)
    first_process = await create_process(session)
    second_process = await create_process(session)

    assert await can_manage_participants(session, user.id, first_process.id)
    assert await can_manage_participants(session, user.id, second_process.id)


@pytest.mark.asyncio
async def test_effective_group_manager_authorizes_only_own_process(
    session, user
):
    own_process = await create_process(session)
    other_process = await create_process(session)
    assignment = AssignmentFactory(
        process=own_process,
        user=user,
        assigner=user,
        role_key='group_manager',
    )
    session.add(assignment)
    await session.commit()

    assert await can_manage_participants(session, user.id, own_process.id)
    assert not await can_manage_participants(
        session, user.id, other_process.id
    )


@pytest.mark.asyncio
async def test_revoked_group_manager_does_not_authorize_management(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='group_manager',
        revoked_at=datetime.now(timezone.utc),
    )
    session.add(assignment)
    await session.commit()

    assert not await can_manage_participants(session, user.id, process.id)


@pytest.mark.asyncio
async def test_group_manager_cycle_of_inactive_user_does_not_authorize(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='group_manager'
    )
    session.add(assignment)
    user.deleted_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()

    assert not await can_manage_participants(session, user.id, process.id)


@pytest.mark.asyncio
async def test_common_participant_receives_self_scope_without_management(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.commit()

    assert await participant_read_scope(session, user.id, process.id) == 'self'
    assert not await can_manage_participants(session, user.id, process.id)


@pytest.mark.asyncio
async def test_outsider_has_no_participant_scope(session, user):
    process = await create_process(session)
    assert await participant_read_scope(session, user.id, process.id) is None


@pytest.mark.asyncio
async def test_active_proponent_assignment_authorizes_submission_scope(
    session, user
):
    process = await create_process(session)
    session.add(
        AssignmentFactory(
            process=process,
            user=user,
            assigner=user,
            role_key='proponent',
        )
    )
    await session.commit()

    assert await is_active_effective_proponent(session, user.id, process.id)


@pytest.mark.asyncio
async def test_revoked_proponent_assignment_denies_submission_scope(
    session, user
):
    process = await create_process(session)
    session.add(
        AssignmentFactory(
            process=process,
            user=user,
            assigner=user,
            role_key='proponent',
            revoked_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()

    assert not await is_active_effective_proponent(
        session, user.id, process.id
    )


@pytest.mark.asyncio
async def test_non_proponent_assignment_denies_submission_scope(session, user):
    process = await create_process(session)
    session.add(
        AssignmentFactory(
            process=process,
            user=user,
            assigner=user,
            role_key='study_manager',
        )
    )
    await session.commit()

    assert not await is_active_effective_proponent(
        session, user.id, process.id
    )


# --- I-C: estado de conflito vigente ---


@pytest.mark.asyncio
async def test_absence_of_declaration_does_not_generate_conflict(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.commit()

    assert not await has_current_conflict(session, user.id, process.id)


@pytest.mark.asyncio
async def test_latest_true_declaration_of_active_cycle_generates_conflict(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.flush()
    declaration = ConflictInterestDeclarationFactory(
        assignment=assignment, has_conflict=True
    )
    session.add(declaration)
    await session.commit()

    assert await has_current_conflict(session, user.id, process.id)


@pytest.mark.asyncio
async def test_later_false_declaration_removes_conflict_of_same_cycle(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.flush()
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment,
            has_conflict=True,
            declared_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment,
            has_conflict=False,
            declared_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )
    await session.commit()

    assert not await has_current_conflict(session, user.id, process.id)


@pytest.mark.asyncio
async def test_true_conflict_in_other_active_cycle_prevails_over_false(
    session, user
):
    process = await create_process(session)
    false_assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    true_assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='statistician'
    )
    session.add_all([false_assignment, true_assignment])
    await session.flush()
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=false_assignment, has_conflict=False
        )
    )
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=true_assignment, has_conflict=True
        )
    )
    await session.commit()

    assert await has_current_conflict(session, user.id, process.id)


@pytest.mark.asyncio
async def test_conflict_of_revoked_cycle_is_ignored_by_calculation(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='study_manager',
        revoked_at=datetime.now(timezone.utc),
    )
    session.add(assignment)
    await session.flush()
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    assert not await has_current_conflict(session, user.id, process.id)


@pytest.mark.asyncio
async def test_declared_at_tie_uses_greater_id_as_most_recent(session, user):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.flush()

    tie_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    older_id_true = ConflictInterestDeclarationFactory(
        assignment=assignment, has_conflict=True, declared_at=tie_time
    )
    older_id_true.id = UUID('00000000-0000-0000-0000-000000000001')
    newer_id_false = ConflictInterestDeclarationFactory(
        assignment=assignment, has_conflict=False, declared_at=tie_time
    )
    newer_id_false.id = UUID('00000000-0000-0000-0000-000000000002')
    session.add_all([older_id_true, newer_id_false])
    await session.commit()

    assert not await has_current_conflict(session, user.id, process.id)
