"""Gravação de alerts na sessão da operação (Spec 047, base)."""

from datetime import datetime

import pytest
from sqlalchemy import select

from pivma.core import alert_service
from pivma.core.database.models import Alert
from tests.factories.alert_factory import make_process, make_user


async def _add(session, process, user_ids, actor_id=None):
    await alert_service.add_alerts(
        session,
        kind=alert_service.SUBMISSION_STATUS_CHANGED,
        user_ids=user_ids,
        process_id=process.id,
        target_type=alert_service.TARGET_PROCESS,
        params={'process_code': process.code, 'status': 'approved'},
        actor_id=actor_id,
    )


async def _alerts(session, process):
    return (
        await session.scalars(
            select(Alert).where(Alert.process_instance_id == process.id)
        )
    ).all()


@pytest.mark.asyncio
async def test_same_user_twice_gets_one_alert(session):
    """FR-005."""
    process = await make_process(session)
    user = await make_user(session)

    await _add(session, process, [user.id, user.id])
    await session.commit()

    assert [a.user_id for a in await _alerts(session, process)] == [user.id]


@pytest.mark.asyncio
async def test_actor_does_not_get_alert(session):
    """FR-006."""
    process = await make_process(session)
    actor = await make_user(session)
    other = await make_user(session)

    await _add(session, process, [actor.id, other.id], actor_id=actor.id)
    await session.commit()

    assert [a.user_id for a in await _alerts(session, process)] == [other.id]


@pytest.mark.asyncio
async def test_deactivated_user_does_not_get_alert(session):
    """FR-004, research R7."""
    process = await make_process(session)
    active = await make_user(session)
    deactivated = await make_user(session)
    deactivated.deleted_at = datetime(2026, 11, 1)
    await session.commit()

    await _add(session, process, [active.id, deactivated.id])
    await session.commit()

    assert [a.user_id for a in await _alerts(session, process)] == [active.id]


@pytest.mark.asyncio
async def test_rollback_leaves_no_alert(session):
    """FR-003, SC-004: o alert vive e morre com a operação."""
    process = await make_process(session)
    user = await make_user(session)

    process_id = process.id
    await _add(session, process, [user.id])
    await session.rollback()

    remaining = await session.scalars(
        select(Alert).where(Alert.process_instance_id == process_id)
    )
    assert remaining.all() == []


@pytest.mark.asyncio
async def test_created_by_is_actor_or_null(session):
    """Research R11."""
    process = await make_process(session)
    actor = await make_user(session)
    first = await make_user(session)
    second = await make_user(session)

    await _add(session, process, [first.id], actor_id=actor.id)
    await _add(session, process, [second.id], actor_id=None)
    await session.commit()

    by_user = {
        a.user_id: a.created_by for a in await _alerts(session, process)
    }
    assert by_user == {first.id: actor.id, second.id: None}
