# ruff: noqa: PLR2004
"""API — autorização da triagem (Spec 014, US1).

Matriz em `contracts/triage-authorization.md` da feature.
"""

from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from tests.activity_state import in_triage
from tests.ai_eval_helpers import (
    NON_COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import (
    AssignmentFactory,
    ConflictInterestDeclarationFactory,
)
from tests.factories.user_factory import UserFactory

ORIGIN = {'Origin': 'https://testserver'}
SUBMISSION = {
    'method_title': 'Título',
    'endpoint_target': 'corrosivity',
    'scientific_justification': 'Justificativa.',
    'pre_validation_evidence': 'Evidências.',
    'study_protocol_file': 'p.pdf',
}


async def _process_in_triage(client, session) -> str:
    await bootstrap_all_templates(session)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    pid = client.post(
        '/processes',
        json={'template_key': 'pre_validated_method', 'title': 'Triagem'},
    ).json()['id']
    client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': SUBMISSION},
    )
    assert await in_triage(session, pid)
    return pid


def _reviews(client, pid):
    return client.post(
        f'/processes/{pid}/triage/reviews',
        json={'reviews': []},
        headers=ORIGIN,
    )


def _decision(client, pid):
    return client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': 'APPROVED', 'justification': 'parecer favorável'},
        headers=ORIGIN,
    )


@pytest.mark.asyncio
async def test_bracvam_can_triage_and_admin_only_reads(
    client, session, bracvam_user, ai_eval_admin
):
    """Spec 030 (FR-026): só o cargo `bracvam` edita a triagem; o Admin

    tem `triage.review` mas só a concessão de ver.
    """
    pid = await _process_in_triage(client, session)

    authenticate(client, ai_eval_admin)
    assert _reviews(client, pid).status_code == HTTPStatus.FORBIDDEN
    assert _decision(client, pid).status_code == HTTPStatus.FORBIDDEN

    authenticate(client, bracvam_user)
    assert _reviews(client, pid).status_code == HTTPStatus.OK
    assert client.get(f'/processes/{pid}/pre-evaluation').status_code in {
        HTTPStatus.OK,
        HTTPStatus.NOT_FOUND,
    }
    assert _decision(client, pid).status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_group_manager_and_reviewer_cannot_triage(
    client, session, non_triage_user
):
    pid = await _process_in_triage(client, session)

    authenticate(client, non_triage_user)
    assert _reviews(client, pid).status_code == HTTPStatus.FORBIDDEN
    assert _decision(client, pid).status_code == HTTPStatus.FORBIDDEN
    # Spec 030: sem concessão de ver na submissão → 404.
    assert (
        client.get(f'/processes/{pid}/pre-evaluation').status_code
        == HTTPStatus.NOT_FOUND
    )

    reviewer = await _rbac_user(session, 'reviewer', 'Revisor', ())
    authenticate(client, reviewer)
    assert _reviews(client, pid).status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_proponent_reads_own_pre_evaluation_only(
    client, session, ai_eval_admin
):
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=NON_COMPLIANT_STATEMENT
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    pid = result['process_id']

    assert (
        client.get(f'/processes/{pid}/pre-evaluation').status_code
        == HTTPStatus.OK
    )
    assert _reviews(client, pid).status_code == HTTPStatus.FORBIDDEN
    assert _decision(client, pid).status_code == HTTPStatus.FORBIDDEN

    other = UserFactory()
    session.add(other)
    await session.commit()
    authenticate(client, other)
    assert (
        client.get(f'/processes/{pid}/pre-evaluation').status_code
        == HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_conflict_of_interest_blocks_triage_despite_permission(
    client, session, bracvam_user
):
    pid = await _process_in_triage(client, session)

    assignment = AssignmentFactory(
        process_instance_id=pid,
        user_id=bracvam_user.id,
        assigned_by=bracvam_user.id,
        role_key='adhoc_evaluator',
    )
    session.add(assignment)
    await session.flush()
    session.add(
        ConflictInterestDeclarationFactory(
            assignment=assignment, has_conflict=True
        )
    )
    await session.commit()

    authenticate(client, bracvam_user)
    assert _reviews(client, pid).status_code == HTTPStatus.FORBIDDEN
    assert _decision(client, pid).status_code == HTTPStatus.FORBIDDEN
    # Leitura da pré-avaliação não é bloqueada por conflito.
    assert client.get(f'/processes/{pid}/pre-evaluation').status_code in {
        HTTPStatus.OK,
        HTTPStatus.NOT_FOUND,
    }


async def _rbac_user(session, system_key, name, codes):
    from tests.conftest import _make_rbac_user  # noqa: PLC0415

    return await _make_rbac_user(
        session, system_key=system_key, name=name, codes=codes
    )
