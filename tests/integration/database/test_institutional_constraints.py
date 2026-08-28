from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from tests.factories import (
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
)


@pytest.mark.asyncio
async def test_active_names_and_affiliations_can_be_reused_after_inactivation(
    session, user
):
    institution = InstitutionFactory(name='Fiocruz')
    session.add(institution)
    await session.commit()

    duplicate = InstitutionFactory(name='fiocruz')
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    await session.refresh(institution)
    await session.refresh(user)
    institution.deleted_at = datetime.now()
    session.add(institution)
    await session.commit()
    replacement = InstitutionFactory(name='FIOCRUZ')
    session.add(replacement)
    await session.commit()
    await session.refresh(replacement)

    affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=replacement
    )
    session.add(affiliation)
    await session.commit()
    duplicate_affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=replacement
    )
    session.add(duplicate_affiliation)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_active_affiliation_with_laboratory_rejects_duplicate(
    session, user
):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.commit()

    affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=institution, laboratory=laboratory
    )
    session.add(affiliation)
    await session.commit()

    duplicate = UserInstitutionalAffiliationFactory(
        user=user, institution=institution, laboratory=laboratory
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_affiliation_rejects_laboratory_from_other_institution(
    session, user
):
    first = InstitutionFactory()
    second = InstitutionFactory()
    session.add_all([first, second])
    await session.flush()
    laboratory = LaboratoryFactory(institution=first)
    session.add(laboratory)
    await session.commit()
    affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=second, laboratory=laboratory
    )
    session.add(affiliation)
    with pytest.raises(IntegrityError):
        await session.flush()
