"""Predicado único de designação efetiva (Spec 035, FR-001, research R2)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from pivma.core.authorization import (
    effective_assignment_clause,
    has_active_laboratory_affiliation,
)
from pivma.core.database.models import Assignment
from tests.factories import (
    AssignmentFactory,
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
)
from tests.integration.database.test_participant_authorization import (
    create_process,
)


async def lab_with_affiliation(session, user):
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
    return institution, laboratory, affiliation


async def designate(session, user, role_key, laboratory=None):
    process = await create_process(session)
    assignment = AssignmentFactory(
        process=process, user=user, role_key=role_key, laboratory=laboratory
    )
    session.add(assignment)
    await session.commit()
    return assignment


async def is_effective(session, assignment) -> bool:
    found = await session.scalar(
        select(Assignment.id).where(
            Assignment.id == assignment.id, effective_assignment_clause()
        )
    )
    return found is not None


async def deactivate(session, entity):
    entity.deleted_at = datetime.now(timezone.utc)
    await session.commit()


@pytest.mark.asyncio
async def test_non_laboratory_designation_is_effective_without_affiliation(
    session, user
):
    assignment = await designate(session, user, 'study_manager')

    assert await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_laboratory_designation_with_active_chain_is_effective(
    session, user
):
    _, laboratory, _ = await lab_with_affiliation(session, user)
    assignment = await designate(
        session, user, 'participating_laboratory', laboratory
    )

    assert await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_lab_designation_after_affiliation_ended_is_not_effective(
    session, user
):
    _, laboratory, affiliation = await lab_with_affiliation(session, user)
    assignment = await designate(
        session, user, 'participating_laboratory', laboratory
    )

    await deactivate(session, affiliation)

    assert not await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_lab_designation_with_inactive_laboratory_is_not_effective(
    session, user
):
    _, laboratory, _ = await lab_with_affiliation(session, user)
    assignment = await designate(
        session, user, 'participating_laboratory', laboratory
    )

    await deactivate(session, laboratory)

    assert not await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_lab_designation_with_inactive_institution_is_not_effective(
    session, user
):
    institution, laboratory, _ = await lab_with_affiliation(session, user)
    assignment = await designate(
        session, user, 'participating_laboratory', laboratory
    )

    await deactivate(session, institution)

    assert not await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_affiliation_with_other_lab_does_not_make_designation_effective(
    session, user
):
    _, laboratory_a, affiliation_a = await lab_with_affiliation(session, user)
    await lab_with_affiliation(session, user)
    assignment = await designate(
        session, user, 'participating_laboratory', laboratory_a
    )

    await deactivate(session, affiliation_a)

    assert not await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_lead_laboratory_follows_the_same_rule(session, user):
    _, laboratory, affiliation = await lab_with_affiliation(session, user)
    assignment = await designate(session, user, 'lead_laboratory', laboratory)
    assert await is_effective(session, assignment)

    await deactivate(session, affiliation)

    assert not await is_effective(session, assignment)


@pytest.mark.asyncio
async def test_affiliation_check_rejects_inactive_laboratory(session, user):
    _, laboratory, _ = await lab_with_affiliation(session, user)

    await deactivate(session, laboratory)

    assert not await has_active_laboratory_affiliation(
        session, user.id, laboratory.id
    )
