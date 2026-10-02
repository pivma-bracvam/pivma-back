"""Rotas de formulário recusam atividade por laboratório (Spec 036, FR-034)."""

from http import HTTPStatus

import pytest
from sqlalchemy import func, select

from pivma.core.database.models import ActivityRun, FormInstance
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.laboratory_run_factory import (
    activity,
    complete_lab,
    frozen_lab_process,
)

ORIGIN = {'Origin': 'https://testserver'}


async def _ready(session, client):
    ctx = await frozen_lab_process(session)
    await complete_lab(session, ctx, 'receipt', 0)
    authenticate(client, ctx.lab_users[0])
    return ctx, f'/processes/{ctx.process_id}/activities/upload/form'


def _assert_invalid_transition(resp):
    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail']['code'] == 'invalid_transition'


@pytest.mark.asyncio
async def test_get_form_of_per_laboratory_activity_is_refused(client, session):
    _, url = await _ready(session, client)

    _assert_invalid_transition(client.get(url))


@pytest.mark.asyncio
async def test_submit_form_of_per_laboratory_activity_changes_nothing(
    client, session
):
    ctx, url = await _ready(session, client)
    upload = await activity(session, ctx.process_id, 'upload')

    async def snapshot():
        runs = (
            await session.execute(
                select(ActivityRun.id, ActivityRun.status)
                .where(ActivityRun.activity_instance_id == upload.id)
                .execution_options(populate_existing=True)
            )
        ).all()
        submitted = await session.scalar(
            select(func.count())
            .select_from(FormInstance)
            .join(ActivityRun)
            .where(
                ActivityRun.activity_instance_id == upload.id,
                FormInstance.is_submitted.is_(True),
            )
        )
        return sorted(runs), submitted

    before = await snapshot()

    resp = client.post(
        url, json={'values': {'result_note': 'ok'}}, headers=ORIGIN
    )

    _assert_invalid_transition(resp)
    assert await snapshot() == before


@pytest.mark.asyncio
async def test_save_draft_of_per_laboratory_activity_is_refused(
    client, session
):
    _, url = await _ready(session, client)

    resp = client.put(
        url, json={'values': {'result_note': 'rascunho'}}, headers=ORIGIN
    )

    _assert_invalid_transition(resp)


@pytest.mark.asyncio
async def test_attachment_of_per_laboratory_activity_is_refused(
    client, session
):
    _, url = await _ready(session, client)

    resp = client.post(
        f'{url}/fields/raw_data/attachment',
        files={'file': ('dados.csv', b'a,b\n1,2\n', 'text/csv')},
        headers=ORIGIN,
    )

    _assert_invalid_transition(resp)
