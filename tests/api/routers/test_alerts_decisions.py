"""Alerts de decisão sobre a submissão, homologação e desistência
(Spec 047, US3 e US6).

Os alerts são lidos do banco; as ações passam pela API pública ou pelas
factories que as outras suítes usam.
"""

from datetime import datetime
from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import alert_service
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import User
from tests.ai_eval_helpers import (
    COMPLIANT_STATEMENT,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.api.routers.test_return_review import (
    ORIGIN,
    VALUES,
    _choose,
    _created_process,
    _triage_return,
)
from tests.factories.alert_factory import alerts_for, same_profile_user
from tests.factories.laboratory_run_factory import end_affiliation
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import _user, lab_user  # noqa: PLC2701
from tests.factories.structure_approval_factory import (
    decide,
    designate,
    structure_process,
)
from tests.factories.user_factory import UserFactory

STATUS = alert_service.SUBMISSION_STATUS_CHANGED
STRUCTURE = alert_service.STRUCTURE_APPROVED
WITHDRAWN = alert_service.PROCESS_WITHDRAWN
PROCESS_PARAMS = {'process_code', 'process_title'}
APPROVE = {'outcome': 'APPROVED', 'justification': 'Estrutura conferida.'}
REJECT = {
    'outcome': 'REJECTED',
    'justification': 'Equipe incompleta.',
    'rejected_points': [
        {'activity_key': 'assign_sponsor', 'reason': 'Patrocinador errado.'}
    ],
}


def _submit(client, pid):
    response = client.post(
        f'/processes/{pid}/activities/proposal_submission/form',
        json={'values': VALUES},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text


def _triage(client, pid, bracvam, outcome):
    authenticate(client, bracvam)
    response = client.post(
        f'/processes/{pid}/triage/decision',
        json={'outcome': outcome, 'justification': 'Justificativa interna.'},
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text


# --- US3: situação da submissão ---------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('outcome', 'status'),
    [('APPROVED', 'approved'), ('REJECTED', 'rejected')],
)
async def test_triage_decision_alerts_proponent_without_justification(
    client, session, bracvam_user, outcome, status
):
    """FR-009, FR-010."""
    proponent, pid = await _created_process(client, session)
    _submit(client, pid)

    _triage(client, pid, bracvam_user, outcome)

    [alert] = await alerts_for(session, proponent, STATUS)
    assert alert.params == {
        'process_code': alert.params['process_code'],
        'process_title': 'Processo 1',
        'status': status,
    }
    assert alert.target_type == alert_service.TARGET_PROCESS
    assert str(alert.process_instance_id) == pid


@pytest.mark.asyncio
async def test_revision_request_reaches_proponent_only_as_task(
    client, session, bracvam_user
):
    """FR-011."""
    proponent, _, _ = await _triage_return(client, session, bracvam_user)

    assert await alerts_for(session, proponent, STATUS) == []
    kinds = {a.kind for a in await alerts_for(session, proponent)}
    assert kinds == {alert_service.TASK_OPENED}


@pytest.mark.asyncio
async def test_deactivated_proponent_gets_no_decision_alert(
    client, session, bracvam_user
):
    """US3, cenário 4."""
    proponent, pid = await _created_process(client, session)
    _submit(client, pid)
    proponent.deleted_at = datetime(2026, 11, 21)
    await session.commit()

    _triage(client, pid, bracvam_user, 'REJECTED')

    assert await alerts_for(session, proponent, STATUS) == []


@pytest.mark.asyncio
async def test_ai_approval_tells_proponent_submission_went_to_triage(
    client, session, ai_eval_admin, fake_provider
):
    """Research R5: a IA não conta como autor."""
    del fake_provider
    await bootstrap_all_templates(session)
    authenticate(client, ai_eval_admin)
    publish_evaluation_and_assign(
        client, severity='critical', statement=COMPLIANT_STATEMENT
    )
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)

    await svc._execute(session, result['body']['pre_evaluation']['run_id'])

    [alert] = await alerts_for(session, proponent, STATUS)
    assert alert.params['status'] == 'in_triage'
    assert alert.created_by is None


# --- US3: homologação da estrutura ------------------------------------------


@pytest.mark.asyncio
async def test_structure_approval_reaches_effective_participants_only(
    client, session, bracvam_user
):
    """US3, cenário 3: revogada e sem efetividade ficam de fora."""
    ctx = await structure_process(session, bracvam_user)
    revoked = await designate(
        session, ctx, await _user(session), 'collaborator'
    )
    revoked.revoked_at = datetime(2026, 11, 21)
    await session.commit()
    stale = await lab_user(session, ctx.laboratories[1])
    await designate(
        session, ctx, stale, 'participating_laboratory', ctx.laboratories[1]
    )
    await end_affiliation(session, stale)
    authenticate(client, bracvam_user)

    response = decide(client, ctx.process_id, **APPROVE)

    assert response.status_code == HTTPStatus.OK, response.text
    for person in (ctx.proponent, ctx.statistician, *ctx.lab_users):
        [alert] = await alerts_for(session, person, STRUCTURE)
        assert set(alert.params) == PROCESS_PARAMS
    revoked_user = await session.get(User, revoked.user_id)
    for person in (revoked_user, stale):
        assert await alerts_for(session, person, STRUCTURE) == []


@pytest.mark.asyncio
async def test_structure_rejection_alerts_reopened_tasks_not_approval(
    client, session, bracvam_user
):
    """FR-011."""
    ctx = await structure_process(session, bracvam_user)
    colleague = await same_profile_user(session, bracvam_user)
    authenticate(client, bracvam_user)

    response = decide(client, ctx.process_id, **REJECT)

    assert response.status_code == HTTPStatus.OK, response.text
    assert await alerts_for(session, ctx.proponent, STRUCTURE) == []
    reopened = [
        a.params['activity_key']
        for a in await alerts_for(
            session, colleague, alert_service.TASK_OPENED
        )
        if a.params['run_number'] > 1
    ]
    assert 'assign_sponsor' in reopened


@pytest.mark.asyncio
async def test_bracvam_who_approves_structure_gets_no_alert(
    client, session, bracvam_user
):
    """FR-006."""
    ctx = await structure_process(session, bracvam_user)
    authenticate(client, bracvam_user)

    decide(client, ctx.process_id, **APPROVE)

    assert await alerts_for(session, bracvam_user, STRUCTURE) == []


# --- US6: desistência --------------------------------------------------------


@pytest.mark.asyncio
async def test_withdrawal_alerts_bracvam_and_active_participants(
    client, session, bracvam_user
):
    """US6; FR-006: o proponente que desiste não recebe."""
    colleague = await same_profile_user(session, bracvam_user)
    proponent, pid, _ = await _triage_return(client, session, bracvam_user)
    active = UserFactory()
    revoked = UserFactory()
    session.add_all([active, revoked])
    await session.commit()
    await grant_cargo(session, process_id=pid, user=active, role_key='sponsor')
    gone = await grant_cargo(
        session, process_id=pid, user=revoked, role_key='collaborator'
    )
    gone.revoked_at = datetime(2026, 11, 21)
    await session.commit()
    authenticate(client, proponent)

    response = _choose(client, pid, 'WITHDRAW', 'Mudamos de estratégia.')

    assert response.status_code == HTTPStatus.OK, response.text
    for person in (bracvam_user, colleague, active):
        [alert] = await alerts_for(session, person, WITHDRAWN)
        assert set(alert.params) == PROCESS_PARAMS
    for person in (proponent, revoked):
        assert await alerts_for(session, person, WITHDRAWN) == []
