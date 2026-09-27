"""Conflito de interesse vigente em SQL correlacionado (Spec 032, R2).

A cláusula precisa dar o mesmo resultado que `has_current_conflict`, usada
pela autorização das ações, para que `can_act` não prometa o que a ação
recusa.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from pivma.core.authorization import (
    current_conflict_clause,
    has_current_conflict,
)
from pivma.core.database.models import ActivityInstance
from tests.factories.participant_factory import (
    ConflictInterestDeclarationFactory,
    grant_cargo,
)
from tests.factories.task_listing_factory import listing_process
from tests.factories.user_factory import UserFactory


def _utc_now():
    # Colunas de data do projeto são naive em UTC.
    return datetime.now(UTC).replace(tzinfo=None)


async def _user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _declare(session, assignment, *, has_conflict, declared_at=None):
    declaration = ConflictInterestDeclarationFactory(
        assignment=assignment, has_conflict=has_conflict
    )
    if declared_at is not None:
        declaration.declared_at = declared_at
    session.add(declaration)
    await session.commit()
    return declaration


async def _clause_holds(session, process, user):
    rows = await session.scalars(
        select(ActivityInstance.id).where(
            ActivityInstance.process_instance_id == process.id,
            current_conflict_clause(user.id),
        )
    )
    return bool(rows.all())


async def _process_with_member(session):
    proponent = await _user(session)
    member = await _user(session)
    process = await listing_process(session, proponent=proponent)
    assignment = await grant_cargo(
        session, process_id=process.id, user=member, role_key='group_manager'
    )
    return process, member, assignment


@pytest.mark.asyncio
async def test_conflict_clause_matches_active_conflict(session):
    process, member, assignment = await _process_with_member(session)
    await _declare(session, assignment, has_conflict=True)

    assert await _clause_holds(session, process, member) is True
    assert await has_current_conflict(session, member.id, process.id) is True


@pytest.mark.asyncio
async def test_conflict_clause_ignores_superseded_declaration(session):
    process, member, assignment = await _process_with_member(session)
    base = _utc_now()
    await _declare(
        session,
        assignment,
        has_conflict=True,
        declared_at=base - timedelta(hours=1),
    )
    await _declare(session, assignment, has_conflict=False, declared_at=base)

    assert await _clause_holds(session, process, member) is False
    assert await has_current_conflict(session, member.id, process.id) is False


@pytest.mark.asyncio
async def test_conflict_clause_ignores_revoked_assignment(session):
    process, member, assignment = await _process_with_member(session)
    await _declare(session, assignment, has_conflict=True)
    assignment.revoked_at = _utc_now()
    await session.commit()

    assert await _clause_holds(session, process, member) is False
    assert await has_current_conflict(session, member.id, process.id) is False


@pytest.mark.asyncio
async def test_conflict_clause_is_scoped_to_user_and_process(session):
    process, member, assignment = await _process_with_member(session)
    await _declare(session, assignment, has_conflict=True)
    other_user = await _user(session)
    other_process = await listing_process(session, proponent=other_user)
    await grant_cargo(
        session,
        process_id=other_process.id,
        user=member,
        role_key='group_manager',
    )

    assert await _clause_holds(session, process, other_user) is False
    assert await _clause_holds(session, other_process, member) is False
