"""Referências resumidas carregadas em lote (Spec 033, research R6)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pivma.core.references import laboratory_refs, user_refs
from tests.factories.institutional_factory import (
    InstitutionFactory,
    LaboratoryFactory,
)
from tests.factories.user_factory import UserFactory


def _utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


async def _users(session, count):
    users = [UserFactory() for _ in range(count)]
    session.add_all(users)
    await session.commit()
    return users


async def _laboratory(session):
    institution = InstitutionFactory()
    session.add(institution)
    await session.commit()
    laboratory = LaboratoryFactory(institution=institution)
    session.add(laboratory)
    await session.commit()
    return institution, laboratory


@pytest.mark.asyncio
async def test_user_refs_batch_has_no_email(session):
    first, second = await _users(session, 2)

    refs = await user_refs(session, [first.id, second.id])

    assert set(refs) == {first.id, second.id}
    dumped = refs[first.id].model_dump()
    assert dumped == {
        'id': first.id,
        'username': first.username,
        'full_name': first.full_name,
    }
    assert 'email' not in dumped


@pytest.mark.asyncio
async def test_user_refs_include_deactivated_user(session):
    [user] = await _users(session, 1)
    user.deleted_at = _utc_now()
    await session.commit()

    refs = await user_refs(session, [user.id])

    assert refs[user.id].full_name == user.full_name


@pytest.mark.asyncio
async def test_laboratory_refs_embed_institution(session):
    institution, laboratory = await _laboratory(session)

    ref = (await laboratory_refs(session, [laboratory.id]))[laboratory.id]

    assert ref.name == laboratory.name
    assert ref.active is True
    assert ref.institution.model_dump() == {
        'id': institution.id,
        'name': institution.name,
        'active': True,
    }


@pytest.mark.asyncio
async def test_laboratory_refs_mark_inactive(session):
    institution, laboratory = await _laboratory(session)
    laboratory.deleted_at = _utc_now()
    institution.deleted_at = _utc_now()
    await session.commit()

    ref = (await laboratory_refs(session, [laboratory.id]))[laboratory.id]

    assert ref.active is False
    assert ref.institution.active is False


@pytest.mark.asyncio
async def test_refs_ignore_unknown_ids_and_empty_input(session):
    assert await user_refs(session, []) == {}
    assert await laboratory_refs(session, []) == {}
    assert await user_refs(session, [uuid4()]) == {}
    assert await laboratory_refs(session, [uuid4()]) == {}
