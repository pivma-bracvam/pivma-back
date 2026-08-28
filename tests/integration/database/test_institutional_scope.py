from datetime import datetime

import pytest

from pivma.core.authorization import active_institutional_affiliations
from tests.factories import (
    InstitutionFactory,
    LaboratoryFactory,
    UserInstitutionalAffiliationFactory,
)


@pytest.mark.asyncio
async def test_active_scope_excludes_inactive_records(
    session, user, other_user
):
    institution = InstitutionFactory()
    other_institution = InstitutionFactory()
    session.add_all([institution, other_institution])
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.flush()
    active = UserInstitutionalAffiliationFactory(
        user=user, institution=institution
    )
    inactive_lab = UserInstitutionalAffiliationFactory(
        user=user, institution=institution, laboratory=laboratory
    )
    inactive_lab.deleted_at = datetime.now()
    other = UserInstitutionalAffiliationFactory(
        user=other_user, institution=other_institution
    )
    session.add_all([active, inactive_lab, other])
    await session.commit()

    result = await active_institutional_affiliations(session, user.id)

    assert [item.id for item in result] == [active.id]


@pytest.mark.asyncio
async def test_active_scope_excludes_records_after_each_parent_inactivation(
    session, user
):
    institution = InstitutionFactory()
    session.add(institution)
    await session.flush()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.flush()
    institution_affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=institution
    )
    laboratory_affiliation = UserInstitutionalAffiliationFactory(
        user=user, institution=institution, laboratory=laboratory
    )
    session.add_all([institution_affiliation, laboratory_affiliation])
    await session.commit()

    laboratory.deleted_at = datetime.now()
    await session.commit()
    assert [
        item.id
        for item in await active_institutional_affiliations(session, user.id)
    ] == [institution_affiliation.id]

    institution.deleted_at = datetime.now()
    await session.commit()
    assert await active_institutional_affiliations(session, user.id) == []

    institution.deleted_at = None
    laboratory.deleted_at = None
    user.deleted_at = datetime.now()
    await session.commit()
    assert await active_institutional_affiliations(session, user.id) == []
