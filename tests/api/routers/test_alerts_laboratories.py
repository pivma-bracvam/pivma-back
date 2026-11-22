"""Alerts da execução nos laboratórios (Spec 047, US5).

Os alerts são lidos do banco; as ações passam pela API pública ou pelas
factories de laboratório que as outras suítes usam.
"""

from http import HTTPStatus

import pytest

from pivma.core import alert_service
from pivma.core.database.models import User
from tests.api.routers.test_sample_nonconformity_decision import (
    with_problem,
)
from tests.api.routers.test_sample_nonconformity_router import nc_url
from tests.api.routers.test_sample_receipt_router import ORIGIN
from tests.factories.alert_factory import alerts_for
from tests.factories.laboratory_run_factory import (
    complete_lab,
    end_affiliation,
    frozen_lab_process,
    waive,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import _user  # noqa: PLC2701

COMPLETED = alert_service.LABORATORY_RUN_COMPLETED
WAIVED = alert_service.LABORATORY_RUN_WAIVED
DECIDED = alert_service.SAMPLE_NONCONFORMITY_DECIDED
DECISION_PARAMS = {
    'process_code',
    'process_title',
    'laboratory_name',
    'blind_code',
    'vial_status',
}


def _decide(client, ctx, item, decision='disqualify', guidance=None):
    response = client.post(
        nc_url(ctx.process_id, f'/{item["id"]}/decision'),
        json={
            'decision': decision,
            'justification': 'Justificativa do Grupo.',
            'lab_guidance': guidance,
        },
        headers=ORIGIN,
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


@pytest.mark.asyncio
async def test_completion_reaches_effective_managers_not_laboratories(session):
    ctx = await frozen_lab_process(session, lab_count=2)
    study_manager = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=study_manager,
        role_key='study_manager',
    )

    await complete_lab(session, ctx, 'receipt', 0)

    for person in (ctx.group_manager, study_manager):
        [alert] = await alerts_for(session, person, COMPLETED)
        assert alert.params['laboratory_name'] == ctx.labs[0].name
        assert alert.params['activity_name'] == 'Recebimento das Amostras'
    for person in ctx.lab_users:
        assert await alerts_for(session, person, COMPLETED) == []


@pytest.mark.asyncio
async def test_waiver_reaches_only_the_waived_laboratory(session):
    ctx = await frozen_lab_process(session, lab_count=2)

    await waive(session, ctx, 1)

    [alert] = await alerts_for(session, ctx.lab_users[1], WAIVED)
    assert alert.params == {
        'process_code': alert.params['process_code'],
        'process_title': alert.params['process_title'],
        'phase_name': 'Execução',
        'laboratory_name': ctx.labs[1].name,
    }
    assert await alerts_for(session, ctx.lab_users[0], WAIVED) == []
    assert await alerts_for(session, ctx.group_manager, WAIVED) == []


@pytest.mark.asyncio
async def test_waiver_skips_laboratory_member_without_effectiveness(session):
    ctx = await frozen_lab_process(session, lab_count=2)
    await end_affiliation(session, ctx.lab_users[1])

    await waive(session, ctx, 1)

    assert await alerts_for(session, ctx.lab_users[1], WAIVED) == []


@pytest.mark.asyncio
async def test_decision_alert_has_only_blind_code_and_status(session, client):
    """SC-002: sem orientação, justificativa, frasco novo nem identidade."""
    ctx = await with_problem(session, client)

    _decide(client, ctx, ctx.items[0], guidance='Use luvas nitrílicas.')

    [alert] = await alerts_for(session, ctx.lab_users[0], DECIDED)
    assert set(alert.params) == DECISION_PARAMS
    assert alert.params['blind_code'] == ctx.codes[0]
    assert alert.params['vial_status'] == 'disqualified'
    assert alert.target_type == alert_service.TARGET_SAMPLE_RECEIPT
    text = str(alert.params)
    for secret in ('Use luvas', 'Justificativa', 'Substância', 'CAS'):
        assert secret not in text
    assert await alerts_for(session, ctx.lab_users[1], DECIDED) == []


@pytest.mark.asyncio
async def test_each_decided_vial_gets_its_own_alert(session, client):
    """Uma decisão vale para os frascos do lote; um alert por frasco."""
    ctx = await with_problem(session, client, broken=(0, 1))

    _decide(client, ctx, ctx.items[0])

    alerts = await alerts_for(session, ctx.lab_users[0], DECIDED)
    assert sorted(a.params['blind_code'] for a in alerts) == sorted(
        ctx.codes[:2]
    )
    assert len({a.target_id for a in alerts}) == len(alerts)


@pytest.mark.asyncio
async def test_selection_group_who_decides_gets_no_decision_alert(
    session, client
):
    """FR-006."""
    ctx = await with_problem(session, client)

    _decide(client, ctx, ctx.items[0])

    selector = await session.get(User, ctx.selector.id)
    assert await alerts_for(session, selector, DECIDED) == []
