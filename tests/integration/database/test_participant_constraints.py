from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from pivma.core.authorization import (
    compute_effectiveness_map,
    latest_declarations_map,
)
from tests.factories import (
    AssignmentFactory,
    ConflictInterestDeclarationFactory,
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
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


async def create_active_laboratory_affiliation(session, user):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.flush()
    affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=institution, laboratory=laboratory
    )
    session.add(affiliation)
    await session.commit()
    await session.refresh(laboratory)
    await session.refresh(affiliation)
    return laboratory, affiliation


# --- I-D: persistência ---


@pytest.mark.asyncio
async def test_foreign_key_rejects_nonexistent_laboratory(session, user):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='lead_laboratory',
        laboratory_id=uuid4(),
    )
    session.add(assignment)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_partial_unique_index_rejects_active_duplicate_across_labs(
    session, user
):
    process = await create_process(session)
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    first_lab = LaboratoryFactory(institution=institution)
    second_lab = LaboratoryFactory(institution=institution)
    session.add_all([first_lab, second_lab])
    await session.commit()

    first_assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='lead_laboratory',
        laboratory=first_lab,
    )
    session.add(first_assignment)
    await session.commit()

    duplicate_assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='lead_laboratory',
        laboratory=second_lab,
    )
    session.add(duplicate_assignment)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_new_equivalent_cycle_is_accepted_after_revocation(
    session, user
):
    process = await create_process(session)
    first_cycle = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(first_cycle)
    await session.commit()

    first_cycle.revoked_at = datetime.now(timezone.utc)
    session.add(first_cycle)
    await session.commit()

    second_cycle = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(second_cycle)
    await session.commit()

    assert second_cycle.id != first_cycle.id


@pytest.mark.asyncio
async def test_physical_deletion_of_referenced_assignment_is_rejected(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.flush()
    declaration = ConflictInterestDeclarationFactory(
        assignment=assignment, has_conflict=False
    )
    session.add(declaration)
    await session.commit()

    await session.delete(assignment)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


# --- I-Q: consultas de efetividade e histórico ---


@pytest.mark.asyncio
async def test_laboratory_assignment_is_effective_with_current_affiliation(
    session, user
):
    process = await create_process(session)
    laboratory, _ = await create_active_laboratory_affiliation(session, user)
    assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='lead_laboratory',
        laboratory=laboratory,
    )
    session.add(assignment)
    await session.commit()

    effectiveness = await compute_effectiveness_map(session, [assignment])
    assert effectiveness[assignment.id] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('origin', ['affiliation', 'laboratory', 'user'])
async def test_laboratory_assignment_becomes_ineffective_after_losing_scope(
    session, user, origin
):
    process = await create_process(session)
    laboratory, affiliation = await create_active_laboratory_affiliation(
        session, user
    )
    assignment = AssignmentFactory(
        process=process,
        user=user,
        assigner=user,
        role_key='lead_laboratory',
        laboratory=laboratory,
    )
    session.add(assignment)
    await session.commit()

    now = datetime.now(timezone.utc)
    if origin == 'affiliation':
        affiliation.deleted_at = now
        session.add(affiliation)
    elif origin == 'laboratory':
        laboratory.deleted_at = now
        session.add(laboratory)
    else:
        user.deleted_at = now
        session.add(user)
    await session.commit()

    effectiveness = await compute_effectiveness_map(session, [assignment])
    assert effectiveness[assignment.id] is False


@pytest.mark.asyncio
async def test_latest_declaration_query_orders_by_moment_and_identifier(
    session, user
):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, assigner=user, role_key='study_manager'
    )
    session.add(assignment)
    await session.flush()

    earlier = ConflictInterestDeclarationFactory(
        assignment=assignment,
        has_conflict=False,
        declared_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    tie_lower_id = ConflictInterestDeclarationFactory(
        assignment=assignment,
        has_conflict=True,
        declared_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    tie_lower_id.id = UUID('00000000-0000-0000-0000-000000000001')
    tie_higher_id = ConflictInterestDeclarationFactory(
        assignment=assignment,
        has_conflict=False,
        declared_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    tie_higher_id.id = UUID('00000000-0000-0000-0000-000000000002')
    session.add_all([earlier, tie_lower_id, tie_higher_id])
    await session.commit()

    latest = await latest_declarations_map(session, [assignment.id])
    assert latest[assignment.id].id == tie_higher_id.id
    assert latest[assignment.id].has_conflict is False
