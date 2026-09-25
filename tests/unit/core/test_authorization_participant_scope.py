"""Spec 018 - `active_participant_process_scope`.

Irmã de `active_proponent_process_scope`, mas sem filtrar por `role_key`:
qualquer atribuição ativa (Proponente, Gestor etc.) conta para o cargo
contextual `Padrão` enxergar o processo.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from pivma.core.authorization import active_participant_process_scope
from pivma.core.database.models import ProcessInstance
from tests.factories.participant_factory import AssignmentFactory
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)
from tests.factories.user_factory import UserFactory


async def _make_process(session, *, status='OPEN'):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.commit()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.commit()
    process = ProcessInstanceFactory(template_version=version, status=status)
    session.add(process)
    await session.commit()
    return process


@pytest.mark.asyncio
async def test_scope_includes_process_with_any_active_role_key(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    process = await _make_process(session)

    session.add(
        AssignmentFactory(process=process, user=user, role_key='group_manager')
    )
    await session.commit()

    scope_stmt = select(ProcessInstance.id).where(
        ProcessInstance.id.in_(active_participant_process_scope(user.id))
    )
    ids = set((await session.execute(scope_stmt)).scalars().all())
    assert process.id in ids


@pytest.mark.asyncio
async def test_scope_excludes_revoked_assignment(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    process = await _make_process(session)

    assignment = AssignmentFactory(
        process=process, user=user, role_key='study_manager'
    )
    assignment.revoked_at = datetime.now(UTC)
    session.add(assignment)
    await session.commit()

    scope_stmt = select(ProcessInstance.id).where(
        ProcessInstance.id.in_(active_participant_process_scope(user.id))
    )
    ids = set((await session.execute(scope_stmt)).scalars().all())
    assert process.id not in ids


@pytest.mark.asyncio
async def test_scope_excludes_process_without_assignment(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    await _make_process(session)  # nenhuma atribuição para `user`

    scope_stmt = select(ProcessInstance.id).where(
        ProcessInstance.id.in_(active_participant_process_scope(user.id))
    )
    ids = set((await session.execute(scope_stmt)).scalars().all())
    assert ids == set()
