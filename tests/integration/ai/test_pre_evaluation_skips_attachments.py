# ruff: noqa: PLR2004
"""Integração — pré-avaliação por IA ignora campos de anexo (Spec 016, US4)."""

from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import pre_evaluation_service as svc
from pivma.core.database.models import (
    ActivityInstance,
    EvaluationRun,
    EvaluationRunItem,
    FormField,
    FormTemplate,
)
from tests.ai_eval_helpers import (
    FULL_VALUES,
    SUBMISSION_TEMPLATE,
    TRUSTED_ORIGIN,
    create_and_submit_process,
    publish_evaluation_and_assign,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.fixture(autouse=True)
def _attachments_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'attach'))


async def _add_file_field(session):
    template = (
        await session.execute(
            select(FormTemplate).where(FormTemplate.key == SUBMISSION_TEMPLATE)
        )
    ).scalar_one()
    session.add(
        FormField(
            form_template_id=template.id,
            field_key='pop_document',
            label='POP do Método',
            field_type='file_upload',
            is_required=False,
            order_index=30,
        )
    )
    await session.commit()


def _assign_fields(client, definition_id, field_keys):
    client.put(
        f'/form-templates/{SUBMISSION_TEMPLATE}/evaluation-assignments',
        json={
            'assignments': [
                {
                    'definition_id': definition_id,
                    'target_type': 'field',
                    'field_keys': field_keys,
                }
            ]
        },
        headers=TRUSTED_ORIGIN,
    )


@pytest.mark.asyncio
async def test_attachment_only_assignment_is_recorded_not_evaluated(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    await bootstrap_all_templates(session)
    await _add_file_field(session)
    authenticate(client, ai_eval_admin)
    definition_id = publish_evaluation_and_assign(client, severity='low')
    _assign_fields(client, definition_id, ['pop_document'])

    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client)
    assert result['status_code'] == HTTPStatus.OK
    run_id = UUID(result['body']['pre_evaluation']['run_id'])

    await svc._execute(session, run_id)

    run = await session.get(EvaluationRun, run_id)
    assert run.status == 'completed'
    assert run.consolidated_result == 'positive'
    assert run.real_cost == 0

    items = list(
        await session.scalars(
            select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
        )
    )
    assert items == []

    skipped = [
        entry
        for entry in run.evaluated_content_snapshot
        if entry.get('ai_status') == 'not_evaluated'
    ]
    assert skipped == [
        {
            'field_key': 'pop_document',
            'label': 'POP do Método',
            'ai_status': 'not_evaluated',
            'reason': 'attachment_not_ai_evaluable',
        }
    ]

    triage = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.process_instance_id == run.process_instance_id,
            ActivityInstance.key == 'triage_evaluation',
        )
    )
    assert triage.status == 'READY'


@pytest.mark.asyncio
async def test_text_field_still_evaluated_when_attachment_in_same_assignment(
    client, ai_eval_admin, session, fake_provider
):
    del fake_provider
    await bootstrap_all_templates(session)
    await _add_file_field(session)
    authenticate(client, ai_eval_admin)
    definition_id = publish_evaluation_and_assign(client, severity='low')
    _assign_fields(
        client, definition_id, ['terminology_notes', 'pop_document']
    )

    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    authenticate(client, proponent)
    result = create_and_submit_process(client, values=FULL_VALUES)
    run_id = UUID(result['body']['pre_evaluation']['run_id'])

    await svc._execute(session, run_id)

    run = await session.get(EvaluationRun, run_id)
    assert run.status == 'completed'
    items = list(
        await session.scalars(
            select(EvaluationRunItem).where(EvaluationRunItem.run_id == run_id)
        )
    )
    assert len(items) == 1

    statuses = {
        entry['field_key']: entry.get('ai_status')
        for entry in run.evaluated_content_snapshot
    }
    assert statuses['pop_document'] == 'not_evaluated'
    assert 'terminology_notes' in statuses
