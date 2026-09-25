import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    AuditEvent,
    Permission,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
    UserAccessProfile,
)
from pivma.core.process_engine import ConflictError, delete_process
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_second_lifecycle_action_has_no_success_audit(
    session, user, bracvam_user, process_retirement_factory
):
    """Duas ações sequenciais sobre o mesmo processo (FR-020), na mesma
    sessão/transação. Complementa `test_concurrent_delete_race`
    (abaixo), que exercita o lock `with_for_update()` de verdade em duas
    conexões reais e concorrentes.
    """
    process = await process_retirement_factory.submitted(user, status='OPEN')
    await delete_process(session, process.id, bracvam_user.id)

    with pytest.raises(ConflictError):
        await delete_process(session, process.id, bracvam_user.id)

    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.process_instance_id == process.id,
            AuditEvent.event_type == 'PROCESS_DELETED',
        )
    )
    assert count == 1


@dataclass
class _RaceFixture:
    process_id: UUID
    user_id: UUID
    template_id: UUID
    version_id: UUID
    profile_id: UUID


async def _create_race_fixture(engine: AsyncEngine) -> _RaceFixture:
    """Processo submetido + ator BraCVAM, persistidos com commit real.

    Precisa ser visível a duas conexões independentes, então não pode usar
    a fixture `session` (isolada por savepoint nunca commitado).
    """
    suffix = uuid4().hex
    async with AsyncSession(engine, expire_on_commit=False) as setup:
        owner = UserFactory(
            username=f'lifecycle-race-actor-{suffix}',
            email=f'lifecycle-race-actor-{suffix}@test.com',
        )
        profile = AccessProfile(
            system_key='bracvam',
            name='BraCVAM (teste de corrida)',
            description='BraCVAM (teste de corrida)',
        )
        template = ProcessTemplate(
            key=f'lifecycle-race-{suffix}', name='Race template'
        )
        setup.add_all([owner, profile, template])
        await setup.flush()
        setup.add(UserAccessProfile(user_id=owner.id, profile_id=profile.id))
        permission = Permission(
            code='triage.review', description='Triage review'
        )
        setup.add(permission)
        await setup.flush()
        setup.add(
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
        )
        version = ProcessTemplateVersion(
            template_id=template.id, version_number=1, definition_payload={}
        )
        setup.add(version)
        await setup.flush()
        process = ProcessInstance(
            template_version_id=version.id,
            code=f'RACE-{suffix[:24]}',
            title='Processo em disputa',
            status='OPEN',
        )
        process.set_creation_audit(owner.id)
        setup.add(process)
        await setup.flush()
        setup.add(
            AuditEvent(
                process_instance_id=process.id,
                user_id=owner.id,
                event_type='SUBMISSION_SUBMITTED',
                context_data={'run_number': 1},
            )
        )
        await setup.commit()
        return _RaceFixture(
            process_id=process.id,
            user_id=owner.id,
            template_id=template.id,
            version_id=version.id,
            profile_id=profile.id,
        )


async def _delete_race_fixture(
    engine: AsyncEngine, fixture: _RaceFixture
) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as cleanup:
        await cleanup.execute(
            delete(AuditEvent).where(
                AuditEvent.process_instance_id == fixture.process_id
            )
        )
        await cleanup.execute(
            delete(ProcessInstance).where(
                ProcessInstance.id == fixture.process_id
            )
        )
        await cleanup.execute(
            delete(ProcessTemplateVersion).where(
                ProcessTemplateVersion.id == fixture.version_id
            )
        )
        await cleanup.execute(
            delete(ProcessTemplate).where(
                ProcessTemplate.id == fixture.template_id
            )
        )
        await cleanup.execute(
            delete(UserAccessProfile).where(
                UserAccessProfile.profile_id == fixture.profile_id
            )
        )
        await cleanup.execute(
            delete(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == fixture.profile_id
            )
        )
        await cleanup.execute(
            delete(Permission).where(Permission.code == 'triage.review')
        )
        await cleanup.execute(
            delete(AccessProfile).where(AccessProfile.id == fixture.profile_id)
        )
        await cleanup.execute(delete(User).where(User.id == fixture.user_id))
        await cleanup.commit()


@pytest.mark.asyncio
async def test_concurrent_delete_race(engine):
    """Duas transações reais, em conexões distintas, disputam a mesma linha.

    Ao contrário do teste anterior, este não usa a fixture `session`: abre
    duas conexões de verdade a partir de `engine` e dispara dois `DELETE`
    concorrentes via `asyncio.gather`, validando que o `with_for_update()`
    de `delete_process` serializa a disputa em vez de deixar as duas lerem
    o mesmo estado pré-transição (as duas partem do mesmo status válido
    para exclusão, então só a ordem de chegada à linha decide quem vence).
    Exatamente uma deve vencer; a outra deve ser rejeitada contra o estado
    `CANCELLED` já confirmado pela vencedora.
    """
    fixture = await _create_race_fixture(engine)
    try:

        async def delete():
            async with AsyncSession(engine, expire_on_commit=False) as sess:
                return await delete_process(
                    sess, fixture.process_id, fixture.user_id
                )

        results = await asyncio.gather(
            delete(),
            delete(),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], ConflictError)
        assert successes[0]['status'] == 'CANCELLED'

        async with AsyncSession(engine, expire_on_commit=False) as check:
            final_status = await check.scalar(
                select(ProcessInstance.status)
                .where(ProcessInstance.id == fixture.process_id)
                .execution_options(skip_soft_delete_filter=True)
            )
            success_audit_count = await check.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.process_instance_id == fixture.process_id,
                    AuditEvent.event_type == 'PROCESS_DELETED',
                )
            )

        assert final_status == 'CANCELLED'
        assert success_audit_count == 1
    finally:
        await _delete_race_fixture(engine, fixture)
