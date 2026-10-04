"""Carga real de template com execução por laboratório (Spec 036, US6)."""

import copy

import pytest
from sqlalchemy import func, select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    sync_template_from_dict,
)
from pivma.core.database.models import (
    ActivityInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import ValidationError
from tests.factories.laboratory_run_factory import LAB_RUN_TEMPLATE


@pytest.mark.asyncio
async def test_invalid_template_is_refused_without_writing(session):
    data = copy.deepcopy(LAB_RUN_TEMPLATE)
    data['process_template']['key'] = 'invalid_lab_probe'
    data['phases'][1]['activities'][0]['execution_scope'] = 'per_lab'

    with pytest.raises(ValidationError):
        await sync_template_from_dict(session, data)
    await session.rollback()

    count = await session.scalar(
        select(func.count())
        .select_from(ProcessTemplate)
        .where(ProcessTemplate.key == 'invalid_lab_probe')
    )
    assert count == 0


@pytest.mark.asyncio
async def test_standard_templates_declare_only_receipt_per_laboratory(session):
    """Spec 040: a Etapa 3 traz a primeira atividade por laboratório."""
    await bootstrap_all_templates(session)

    payloads = await session.scalars(
        select(ProcessTemplateVersion.definition_payload)
    )
    for payload in payloads:
        lab_keys = [
            activity['key']
            for phase in payload.get('phases', [])
            for activity in phase.get('activities', [])
            if activity.get('execution_scope', 'process') != 'process'
        ]
        assert lab_keys == ['sample_receipt']
    lab_activities = await session.scalar(
        select(func.count())
        .select_from(ActivityInstance)
        .where(ActivityInstance.execution_scope == 'per_laboratory')
    )
    assert lab_activities == 0
