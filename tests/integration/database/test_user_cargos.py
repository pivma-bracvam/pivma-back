"""Cargos efetivos de um usuário num processo (Spec 030, R4)."""

from datetime import datetime

import pytest

from pivma.core.authorization import user_cargos
from tests.conftest import _make_rbac_user
from tests.factories.participant_factory import grant_cargo
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
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


async def _make_user(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_user_cargos_includes_active_assignment_role(session):
    process = await _make_process(session)
    user = await _make_user(session)
    await grant_cargo(
        session, process_id=process.id, user=user, role_key='proponent'
    )

    assert await user_cargos(session, user.id, process.id) == {'proponent'}


@pytest.mark.asyncio
async def test_user_cargos_excludes_revoked_assignment(session):
    process = await _make_process(session)
    user = await _make_user(session)
    assignment = await grant_cargo(
        session, process_id=process.id, user=user, role_key='proponent'
    )
    assignment.revoked_at = datetime(2026, 9, 1)
    await session.commit()

    assert await user_cargos(session, user.id, process.id) == set()


@pytest.mark.asyncio
async def test_user_cargos_excludes_deleted_user(session):
    process = await _make_process(session)
    user = await _make_user(session)
    await grant_cargo(
        session, process_id=process.id, user=user, role_key='proponent'
    )
    user.deleted_at = datetime(2026, 9, 1)
    await session.commit()

    assert await user_cargos(session, user.id, process.id) == set()


@pytest.mark.asyncio
async def test_user_cargos_adds_admin_for_administrator_profile(session):
    process = await _make_process(session)
    admin = await _make_rbac_user(
        session, system_key='administrator', name='Administrador', codes=()
    )

    assert await user_cargos(session, admin.id, process.id) == {'admin'}


@pytest.mark.asyncio
async def test_user_cargos_adds_bracvam_for_bracvam_profile(session):
    process = await _make_process(session)
    bracvam = await _make_rbac_user(
        session, system_key='bracvam', name='BraCVAM', codes=()
    )

    assert await user_cargos(session, bracvam.id, process.id) == {'bracvam'}


@pytest.mark.asyncio
async def test_user_cargos_scoped_to_process(session):
    process = await _make_process(session)
    other_process = await _make_process(session)
    user = await _make_user(session)
    await grant_cargo(
        session, process_id=other_process.id, user=user, role_key='proponent'
    )

    assert await user_cargos(session, user.id, process.id) == set()


@pytest.mark.asyncio
async def test_user_cargos_union_of_multiple_roles(session):
    process = await _make_process(session)
    user = await _make_user(session)
    await grant_cargo(
        session, process_id=process.id, user=user, role_key='proponent'
    )
    await grant_cargo(
        session, process_id=process.id, user=user, role_key='sponsor'
    )

    assert await user_cargos(session, user.id, process.id) == {
        'proponent',
        'sponsor',
    }
