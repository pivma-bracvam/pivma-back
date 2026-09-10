# ruff: noqa: PLR2004
"""Integração — imutabilidade e versionamento de avaliações (Spec 013)."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pivma.core import evaluation_service as svc
from pivma.core.database.models import (
    EvaluationCriterion,
    EvaluationVersion,
)
from pivma.core.process_engine import ConflictError
from tests.factories.evaluation_factory import (
    EvaluationCriterionFactory,
    EvaluationDefinitionFactory,
    EvaluationVersionFactory,
)


@pytest.mark.asyncio
async def test_single_draft_per_definition_is_enforced(session, user):
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    session.add(
        EvaluationVersionFactory(
            definition=definition, version_number=1, status='draft'
        )
    )
    await session.flush()

    session.add(
        EvaluationVersionFactory(
            definition=definition, version_number=2, status='draft'
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_new_version_requires_no_open_draft(session, user):
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    version = EvaluationVersionFactory(
        definition=definition, version_number=1, status='draft'
    )
    session.add(version)
    await session.flush()
    session.add(
        EvaluationCriterionFactory(version=version, severity='critical')
    )
    await session.commit()

    with pytest.raises(ConflictError):
        await svc.create_new_version(session, definition.id, user.id)


@pytest.mark.asyncio
async def test_publish_freezes_criteria_and_new_version_snapshots(
    session, user
):
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

    published, warning = await svc.publish_version(
        session, definition.id, 1, user.id
    )
    assert published.status == 'published'
    assert warning is True

    v2 = await svc.create_new_version(session, definition.id, user.id)
    assert v2.version_number == 2
    assert v2.status == 'draft'

    await svc.patch_draft_version(
        session,
        definition.id,
        2,
        objective=None,
        reference_ids=None,
        criteria=[
            {
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
        ],
        user_id=user.id,
    )

    v1 = await svc.get_version(session, definition.id, 1)
    assert [c.statement for c in svc._active_criteria(v1)] == ['original']
    assert svc._active_criteria(v1)[0].severity == 'high'


@pytest.mark.asyncio
async def test_soft_deleted_definition_keeps_versions_and_criteria(
    session, user
):
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    version = EvaluationVersionFactory(
        definition=definition, version_number=1, status='draft'
    )
    session.add(version)
    await session.flush()
    session.add(EvaluationCriterionFactory(version=version))
    await session.commit()

    await svc.soft_delete_definition(
        session, definition.id, force=True, user_id=user.id
    )

    versions = list(
        await session.scalars(
            select(EvaluationVersion).where(
                EvaluationVersion.definition_id == definition.id
            )
        )
    )
    criteria = list(
        await session.scalars(
            select(EvaluationCriterion).where(
                EvaluationCriterion.version_id == version.id
            )
        )
    )
    assert len(versions) == 1
    assert len(criteria) == 1
