import pytest
from pydantic import ValidationError

from pivma.schemas import ProfileCreate, ProfileUpdate


def test_profile_create_trims_values_and_rejects_repeated_permissions():
    profile = ProfileCreate(
        name='  Data reader  ',
        description='  Reads RBAC state  ',
        permission_codes=['rbac.read'],
    )

    assert profile.name == 'Data reader'
    assert profile.description == 'Reads RBAC state'

    with pytest.raises(ValidationError):
        ProfileCreate(
            name='Data reader',
            description='Reads RBAC state',
            permission_codes=['rbac.read', 'rbac.read'],
        )


@pytest.mark.parametrize('payload', [{}, {'unexpected': 'field'}])
def test_profile_update_requires_a_known_field(payload):
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate(payload)
