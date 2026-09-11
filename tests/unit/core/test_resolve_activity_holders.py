"""Spec 018 - `resolve_activity_holders`.

Quem ocupa hoje o cargo de uma atividade: cargo global (`admin`/`bracvam`)
resolve via `AccessProfile`; cargo contextual resolve via `Assignment`
ativa naquele processo (User Story 1/2).
"""

import pytest

from pivma.core.authorization import (
    BRACVAM_SYSTEM_KEY,
    resolve_activity_holders,
)
from tests.factories.participant_factory import AssignmentFactory
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)
from tests.factories.rbac_factory import (
    AccessProfileFactory,
    UserAccessProfileFactory,
)
from tests.factories.user_factory import UserFactory


async def _make_process(session):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.commit()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.commit()
    process = ProcessInstanceFactory(template_version=version)
    session.add(process)
    await session.commit()
    return process


@pytest.mark.asyncio
async def test_global_cargo_resolves_via_access_profile(session):
    process = await _make_process(session)
    holder = UserFactory()
    profile = AccessProfileFactory(system_key=BRACVAM_SYSTEM_KEY)
    session.add_all([holder, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=holder, profile=profile))
    await session.commit()

    holders = await resolve_activity_holders(session, process.id, 'bracvam')
    assert {h.id for h in holders} == {holder.id}


@pytest.mark.asyncio
async def test_contextual_cargo_resolves_via_assignment_in_process(session):
    process_a = await _make_process(session)
    process_b = await _make_process(session)
    holder = UserFactory()
    session.add(holder)
    await session.commit()
    session.add(
        AssignmentFactory(
            process=process_a, user=holder, role_key='group_manager'
        )
    )
    await session.commit()

    holders_a = await resolve_activity_holders(
        session, process_a.id, 'group_manager'
    )
    assert {h.id for h in holders_a} == {holder.id}

    # A mesma pessoa não ocupa o cargo no Método B — a atribuição é por
    # processo, nunca global.
    holders_b = await resolve_activity_holders(
        session, process_b.id, 'group_manager'
    )
    assert holders_b == []


@pytest.mark.asyncio
async def test_cargo_without_any_holder_returns_empty_list(session):
    process = await _make_process(session)

    holders = await resolve_activity_holders(
        session, process.id, 'peer_reviewer'
    )
    assert holders == []


@pytest.mark.asyncio
async def test_two_people_in_same_contextual_cargo_are_both_holders(
    session,
):
    process = await _make_process(session)
    first = UserFactory()
    second = UserFactory()
    session.add_all([first, second])
    await session.commit()
    session.add(
        AssignmentFactory(process=process, user=first, role_key='proponent')
    )
    session.add(
        AssignmentFactory(process=process, user=second, role_key='proponent')
    )
    await session.commit()

    holders = await resolve_activity_holders(session, process.id, 'proponent')
    assert {h.id for h in holders} == {first.id, second.id}
