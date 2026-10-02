"""Cenário de aceite da issue #58 (Spec 036, quickstart passos 0 a 8)."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.core.database.models import ActivityRun
from pivma.core.process_engine import (
    AuthorizationError,
    complete_laboratory_run,
    delete_process,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    activity,
    complete_chain,
    complete_lab,
    freeze_samples,
    frozen_lab_process,
    runs_by_lab,
)

ORIGIN = {'Origin': 'https://testserver'}


def _waive(client, ctx, index):
    return client.post(
        f'/processes/{ctx.process_id}/phases/phase_execution/'
        'laboratory-waivers',
        json={'laboratory_id': str(ctx.labs[index].id), 'reason': 'Quebra.'},
        headers=ORIGIN,
    )


def _event_types(client, user, process_id):
    authenticate(client, user)
    resp = client.get(
        f'/processes/{process_id}/timeline', params={'per_page': 100}
    )
    return [e['event_type'] for e in resp.json()['data']]


@pytest.mark.asyncio
async def test_three_labs_waiver_reopen_and_deletion(  # noqa: PLR0915
    client, session, bracvam_user
):
    ctx = await frozen_lab_process(session, freeze=False)
    lab_a, lab_b, lab_c = (lab.id for lab in ctx.labs)

    # 0. Dispensa antes do congelamento é recusada.
    authenticate(client, ctx.group_manager)
    resp = _waive(client, ctx, 2)
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail']['code'] == 'sample_definition_not_frozen'

    # 1. Congelamento: recebimento aberto para os três; cadeia bloqueada.
    await freeze_samples(session, ctx)
    receipt = await runs_by_lab(session, ctx.process_id, 'receipt')
    assert {r.status for r in receipt.values()} == {'IN_PROGRESS'}
    for key in ('upload', 'material_return'):
        runs = await runs_by_lab(session, ctx.process_id, key)
        assert {r.status for r in runs.values()} == {'BLOCKED'}

    # 2. Lab A recebe: o envio de resultados abre só para ele.
    await complete_lab(session, ctx, 'receipt', 0)
    upload = await runs_by_lab(session, ctx.process_id, 'upload')
    assert upload[lab_a].status == 'IN_PROGRESS'
    assert {upload[lab_b].status, upload[lab_c].status} == {'BLOCKED'}

    # 3. Lab A não age pelo Lab B nem enxerga o Lab B.
    with pytest.raises(AuthorizationError):
        await complete_laboratory_run(
            session, ctx.process_id, 'receipt', lab_b, ctx.lab_users[0].id
        )
    authenticate(client, ctx.lab_users[0])
    tasks = client.get('/tasks').json()['data']
    assert {t['laboratory']['id'] for t in tasks} == {str(lab_a)}

    # 4. Labs A e B concluem: a estatística espera o Lab C.
    await complete_lab(session, ctx, 'upload', 0)
    await complete_chain(session, ctx, 1)
    statistics = await activity(session, ctx.process_id, 'statistics')
    assert statistics.status == 'BLOCKED'

    # 5. Dispensa do Lab C: etapa avança e a devolução abre para ele.
    authenticate(client, ctx.group_manager)
    assert _waive(client, ctx, 2).status_code == HTTPStatus.CREATED
    assert (await activity(session, ctx.process_id, 'upload')).status == (
        'COMPLETED'
    )
    assert (await activity(session, ctx.process_id, 'statistics')).status == (
        'IN_PROGRESS'
    )
    returns = await runs_by_lab(session, ctx.process_id, 'material_return')
    assert returns[lab_c].status == 'IN_PROGRESS'

    # 6. Reabertura do Lab B.
    resp = client.post(
        f'/processes/{ctx.process_id}/activities/upload/laboratories/'
        f'{lab_b}/reopen',
        json={'reason': 'Placa 2 inválida.'},
        headers=ORIGIN,
    )
    assert resp.status_code == HTTPStatus.CREATED
    upload = await runs_by_lab(session, ctx.process_id, 'upload')
    assert (upload[lab_b].run_number, upload[lab_b].status) == (
        2,
        'IN_PROGRESS',
    )
    assert upload[lab_a].status == 'COMPLETED'
    assert (await activity(session, ctx.process_id, 'statistics')).status == (
        'BLOCKED'
    )

    # 7. Acompanhamento do Grupo Gestor; a trilha do dispensado não mostra
    # a dispensa.
    tasks = client.get('/tasks', params={'activity_key': 'upload'}).json()
    statuses = {
        t['laboratory']['id']: t['activity_run_status'] for t in tasks['data']
    }
    assert statuses == {
        str(lab_a): 'COMPLETED',
        str(lab_b): 'IN_PROGRESS',
        str(lab_c): 'WAIVED',
    }
    assert 'LABORATORY_WAIVED' in _event_types(
        client, ctx.group_manager, ctx.process_id
    )
    assert 'LABORATORY_WAIVED' not in _event_types(
        client, ctx.lab_users[2], ctx.process_id
    )

    # 8. Exclusão: execuções terminais ficam como estavam.
    terminal = {
        r.id: r.status
        for r in await session.scalars(select(ActivityRun))
        if r.status in {'WAIVED', 'SUPERSEDED', 'COMPLETED'}
    }
    await delete_process(session, ctx.process_id, bracvam_user.id)
    for run_id, status in terminal.items():
        run = await session.scalar(
            select(ActivityRun)
            .where(ActivityRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        assert run.status == status
