from uuid import uuid4

import pytest
from pydantic import ValidationError

from pivma.schemas import (
    AffiliationCreate,
    InstitutionalChangePage,
    InstitutionCreate,
    LaboratoryCreate,
)

MAX_HISTORY_LIMIT = 100


def test_catalog_schemas_normalize_names_and_forbid_extra_fields():
    assert InstitutionCreate(name='  Fiocruz  ').name == 'Fiocruz'
    assert (
        LaboratoryCreate(institution_id=uuid4(), name='  Lab A  ').name
        == 'Lab A'
    )
    with pytest.raises(ValidationError):
        InstitutionCreate(name='Valid', unexpected=True)


@pytest.mark.parametrize('name', ['', 'x' * 256])
def test_catalog_schemas_reject_invalid_names(name):
    with pytest.raises(ValidationError):
        InstitutionCreate(name=name)


def test_affiliation_schema_accepts_optional_laboratory_and_forbids_extra():
    institution_id = uuid4()
    assert (
        AffiliationCreate(institution_id=institution_id).laboratory_id is None
    )
    with pytest.raises(ValidationError):
        AffiliationCreate(institution_id=institution_id, extra='value')


def test_institutional_change_page_limits_pagination_values():
    assert (
        InstitutionalChangePage(
            offset=0, limit=MAX_HISTORY_LIMIT, items=[]
        ).limit
        == MAX_HISTORY_LIMIT
    )
    with pytest.raises(ValidationError):
        InstitutionalChangePage(offset=-1, items=[])
