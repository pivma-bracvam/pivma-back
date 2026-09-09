from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import FormField
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}


@pytest.mark.asyncio
async def test_form_ai_evaluation_endpoint(client, session):
    await bootstrap_all_templates(session)

    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.post(
        '/processes',
        headers=TRUSTED_ORIGIN,
        json={
            'template_key': 'pre_validated_method',
            'title': 'Estudo de Teste IA',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']

    form_resp = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form',
        headers=TRUSTED_ORIGIN,
    )
    assert form_resp.status_code == HTTPStatus.OK
    form_instance_id = form_resp.json()['form_instance_id']

    field_stmt = select(FormField).where(
        FormField.field_key == 'scientific_justification',
        FormField.deleted_at.is_(None),
    )
    field_res = await session.execute(field_stmt)
    fld = field_res.scalar_one()
    fld.ai_evaluation_enabled = True
    fld.ai_context_instructions = 'Verificar fundamentação biológica.'
    await session.commit()

    sample_val = (
        'Proposta detalhada de método alternativo para avaliação cutânea.'
    )
    client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        headers=TRUSTED_ORIGIN,
        json={'values': {'scientific_justification': sample_val}},
    )

    eval_url = f'/forms/instances/{form_instance_id}/evaluate-ai'
    eval_resp = client.post(eval_url, headers=TRUSTED_ORIGIN)
    assert eval_resp.status_code == HTTPStatus.OK
    data = eval_resp.json()
    assert data['form_instance_id'] == str(form_instance_id)
    assert data['status'] == 'COMPLETED'
    assert 'correlation_id' in data
    assert len(data['evaluations']) >= 1

    ev = next(
        e
        for e in data['evaluations']
        if e['field_key'] == 'scientific_justification'
    )
    assert ev['status'] in {'REPROVED', 'NEEDS_ADJUSTMENT'}
    assert len(ev['issues']) > 0
    assert len(ev['recommendations']) > 0


@pytest.mark.asyncio
async def test_form_ai_evaluation_not_found(client, session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    fake_id = uuid4()
    response = client.post(
        f'/forms/instances/{fake_id}/evaluate-ai',
        headers=TRUSTED_ORIGIN,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
