# ruff: noqa: PLR2004
"""Integração — reuso na biblioteca e imutabilidade (Spec 013, US5)."""

import pytest
from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core import evaluation_service as svc
from pivma.core.database.models import (
    EvaluationAssignment,
    EvaluationDefinition,
    EvaluationVersion,
    FormTemplate,
)
from pivma.core.process_engine import ConflictError
from tests.factories.evaluation_factory import (
    EvaluationCriterionFactory,
    EvaluationDefinitionFactory,
    EvaluationVersionFactory,
)

_V2_CRITERION = {
    'id': None,
    'order_index': 0,
    'statement': 'reescrito na v2',
    'check_type': 'quality',
    'polarity': 'positive',
    'required_evidence': None,
    'severity': 'low',
    'on_missing_info': 'indeterminate',
    'recommendation_hint': None,
}


async def _published_definition(session, user) -> EvaluationDefinition:
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    version = EvaluationVersionFactory(
        definition=definition, version_number=1, status='draft'
    )
    session.add(version)
    await session.flush()
    session.add(
        EvaluationCriterionFactory(
            version=version, statement='original', severity='high'
        )
    )
    await session.commit()
    await svc.publish_version(session, definition.id, 1, user.id)
    return definition


async def _assign_to(session, definition_id, *template_keys):
    templates = list(
        await session.scalars(
            select(FormTemplate).where(FormTemplate.key.in_(template_keys))
        )
    )
    for template in templates:
        session.add(
            EvaluationAssignment(
                form_template_id=template.id,
                definition_id=definition_id,
                target_type='form',
                field_keys=[],
            )
        )
    await session.commit()
    return templates


@pytest.mark.asyncio
async def test_one_definition_serves_two_templates_without_copy(session, user):
    await bootstrap_all_templates(session)
    definition = await _published_definition(session, user)

    await _assign_to(
        session,
        definition.id,
        'submission_pre_validated_v1',
        'submission_scope_extension_v1',
    )

    version_count = await session.scalar(
        select(func.count())
        .select_from(EvaluationVersion)
        .where(EvaluationVersion.definition_id == definition.id)
    )
    assignments = await session.scalar(
        select(func.count())
        .select_from(EvaluationAssignment)
        .where(EvaluationAssignment.definition_id == definition.id)
    )
    assert version_count == 1  # sem cópia por template
    assert assignments == 2


@pytest.mark.asyncio
async def test_editing_published_creates_v2_and_freezes_v1(session, user):
    definition = await _published_definition(session, user)

    v2 = await svc.create_new_version(session, definition.id, user.id)
    await svc.patch_draft_version(
        session,
        definition.id,
        2,
        objective=None,
        reference_ids=None,
        criteria=[_V2_CRITERION],
        user_id=user.id,
    )

    v1_after = await svc.get_version(session, definition.id, 1)
    assert v2.version_number == 2
    assert v1_after.status == 'published'
    assert [c.statement for c in svc._active_criteria(v1_after)] == [
        'original'
    ]
    assert svc._active_criteria(v1_after)[0].severity == 'high'


@pytest.mark.asyncio
async def test_removed_definition_with_active_assignment_is_logical_delete(
    session, user
):
    await bootstrap_all_templates(session)
    definition = await _published_definition(session, user)
    await _assign_to(session, definition.id, 'submission_pre_validated_v1')

    with pytest.raises(ConflictError):
        await svc.soft_delete_definition(
            session, definition.id, force=False, user_id=user.id
        )

    await svc.soft_delete_definition(
        session, definition.id, force=True, user_id=user.id
    )
    stored = await session.get(EvaluationDefinition, definition.id)
    assert stored.deleted_at is not None
