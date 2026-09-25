"""Spec 028 — constraints de `role_assignment_invites` em PostgreSQL real."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from pivma.core.database.models import RoleAssignmentInvite
from tests.factories.invite_factory import InviteFactory
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)


async def create_process(session):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.flush()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.flush()
    process = ProcessInstanceFactory(template_version=version)
    session.add(process)
    await session.commit()
    await session.refresh(process)
    return process


@pytest.mark.asyncio
async def test_partial_unique_index_rejects_duplicate_pending(session):
    """F-D01: duas linhas `pending` para (processo, papel, e-mail) colidem."""
    process = await create_process(session)
    session.add(
        InviteFactory(
            process=process, role_key='sponsor', email='dup@exemplo.org'
        )
    )
    await session.commit()

    session.add(
        InviteFactory(
            process=process, role_key='sponsor', email='dup@exemplo.org'
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_pending_invites_same_role_different_emails_are_accepted(
    session,
):
    """F-D02: sem titularidade única (FR-019) — e-mails diferentes convivem."""
    process = await create_process(session)
    session.add(
        InviteFactory(
            process=process, role_key='sponsor', email='a@exemplo.org'
        )
    )
    session.add(
        InviteFactory(
            process=process, role_key='sponsor', email='b@exemplo.org'
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_revoked_invite_frees_the_partial_index(session):
    """F-D03: revogar libera (processo, papel, e-mail) para um novo convite."""
    process = await create_process(session)
    first = InviteFactory(
        process=process, role_key='sponsor', email='c@exemplo.org'
    )
    session.add(first)
    await session.commit()

    first.status = 'revoked'
    first.revoked_at = datetime.utcnow()
    await session.commit()

    session.add(
        InviteFactory(
            process=process, role_key='sponsor', email='c@exemplo.org'
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_foreign_key_rejects_nonexistent_laboratory(session):
    """F-D04: `laboratory_id` inexistente é rejeitado pela FK."""
    process = await create_process(session)
    session.add(
        RoleAssignmentInvite(
            process_instance_id=process.id,
            role_key='lead_laboratory',
            email='lab@exemplo.org',
            token_hash='fk-test-token-hash',
            expires_at=datetime.utcnow() + timedelta(hours=1),
            laboratory_id=uuid4(),
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_token_hash_unique_index_rejects_duplicate_across_processes(
    session,
):
    """F-D05: `token_hash` duplicado entre processos diferentes é rejeitado."""
    process_a = await create_process(session)
    process_b = await create_process(session)
    session.add(
        InviteFactory(
            process=process_a,
            role_key='sponsor',
            email='x@exemplo.org',
            token_hash='shared-hash',
        )
    )
    await session.commit()

    session.add(
        InviteFactory(
            process=process_b,
            role_key='statistician',
            email='y@exemplo.org',
            token_hash='shared-hash',
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
