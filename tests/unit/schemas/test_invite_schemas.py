import pytest
from pydantic import ValidationError

from pivma.schemas import InviteCreate

LABORATORY_ROLES = ('lead_laboratory', 'participating_laboratory')
NON_LABORATORY_ROLES = (
    'group_manager',
    'study_manager',
    'statistician',
    'adhoc_evaluator',
    'peer_reviewer',
    'proponent',
    'sponsor',
    'sample_selection_group',
    'regulatory_observer',
    'collaborator',
)


def test_invite_create_accepts_default_channel():
    invite = InviteCreate(email='a@exemplo.org', role_key='statistician')
    assert invite.channel == 'link'


def test_invite_create_rejects_channel_outside_link():
    """U-I01"""
    with pytest.raises(ValidationError):
        InviteCreate(
            email='a@exemplo.org',
            role_key='statistician',
            channel='email',
        )


@pytest.mark.parametrize('role_key', LABORATORY_ROLES)
def test_invite_create_rejects_missing_laboratory_id(role_key):
    """U-I02"""
    with pytest.raises(ValidationError):
        InviteCreate(email='a@exemplo.org', role_key=role_key)


@pytest.mark.parametrize('role_key', NON_LABORATORY_ROLES)
def test_invite_create_rejects_laboratory_id_for_non_lab_roles(role_key):
    """U-I03"""
    from uuid import uuid4  # noqa: PLC0415

    with pytest.raises(ValidationError):
        InviteCreate(
            email='a@exemplo.org', role_key=role_key, laboratory_id=uuid4()
        )


def test_invite_create_rejects_malformed_email():
    """U-I04"""
    with pytest.raises(ValidationError):
        InviteCreate(email='not-an-email', role_key='statistician')


def test_invite_create_rejects_missing_email():
    """U-I04"""
    with pytest.raises(ValidationError):
        InviteCreate(role_key='statistician')


def test_invite_create_preserves_email_case():
    invite = InviteCreate(email='Joana@Exemplo.ORG', role_key='statistician')
    assert invite.email == 'Joana@Exemplo.ORG'


def test_invite_create_rejects_extra_field():
    with pytest.raises(ValidationError):
        InviteCreate(
            email='a@exemplo.org', role_key='statistician', extra_field=1
        )
