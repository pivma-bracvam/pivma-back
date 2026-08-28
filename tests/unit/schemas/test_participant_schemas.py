from uuid import uuid4

import pytest
from pydantic import ValidationError

from pivma.schemas import (
    ConflictDeclarationCreate,
    ParticipantAssignmentCreate,
)

LABORATORY_ROLES = ('lead_laboratory', 'participating_laboratory')
NON_LABORATORY_ROLES = (
    'group_manager',
    'study_manager',
    'statistician',
    'adhoc_evaluator',
    'peer_reviewer',
    'proponent',
)
ALL_ROLES = LABORATORY_ROLES + NON_LABORATORY_ROLES


@pytest.mark.parametrize('role_key', ALL_ROLES)
def test_assignment_schema_accepts_each_approved_role(role_key):
    laboratory_id = uuid4() if role_key in LABORATORY_ROLES else None
    schema = ParticipantAssignmentCreate(
        user_id=uuid4(), role_key=role_key, laboratory_id=laboratory_id
    )
    assert schema.role_key == role_key


def test_assignment_schema_rejects_role_outside_catalog():
    with pytest.raises(ValidationError):
        ParticipantAssignmentCreate(user_id=uuid4(), role_key='specialist')


@pytest.mark.parametrize('role_key', LABORATORY_ROLES)
def test_assignment_schema_rejects_laboratory_role_without_laboratory_id(
    role_key,
):
    with pytest.raises(ValidationError):
        ParticipantAssignmentCreate(user_id=uuid4(), role_key=role_key)


@pytest.mark.parametrize('role_key', NON_LABORATORY_ROLES)
def test_assignment_schema_rejects_non_laboratory_role_with_laboratory_id(
    role_key,
):
    with pytest.raises(ValidationError):
        ParticipantAssignmentCreate(
            user_id=uuid4(), role_key=role_key, laboratory_id=uuid4()
        )


def test_conflict_declaration_schema_rejects_whitespace_only_justification():
    with pytest.raises(ValidationError):
        ConflictDeclarationCreate(has_conflict=True, justification='   ')


@pytest.mark.parametrize(
    ('schema_cls', 'payload'),
    [
        (
            ParticipantAssignmentCreate,
            {
                'user_id': uuid4(),
                'role_key': 'study_manager',
                'unexpected': 'value',
            },
        ),
        (
            ConflictDeclarationCreate,
            {
                'has_conflict': True,
                'justification': 'Justificativa válida',
                'unexpected': 'value',
            },
        ),
    ],
)
def test_participant_schemas_reject_extra_field(schema_cls, payload):
    with pytest.raises(ValidationError):
        schema_cls(**payload)
