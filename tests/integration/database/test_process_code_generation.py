import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    ActivityRun,
    Assignment,
    AuditEvent,
    FormInstance,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
)
from pivma.core.process_engine import instantiate_process
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_concurrent_process_creation_yields_distinct_crcodes(engine):
    """Duas instanciações concorrentes, em sessões e conexões distintas,
    devem gravar `code` distintos sem violar a restrição única do banco."""
    suffix = uuid4().hex
    async with AsyncSession(engine, expire_on_commit=False) as setup_session:
        user = User(
            username=f'crcode-actor-{suffix}',
            email=f'crcode-actor-{suffix}@test.com',
            password_hash='unused',
        )
        template = ProcessTemplate(
            key=f'crcode-{suffix}', name='Concurrency crCode template'
        )
        setup_session.add_all([user, template])
        await setup_session.flush()
        version = ProcessTemplateVersion(
            template_id=template.id, version_number=1, definition_payload={}
        )
        setup_session.add(version)
        await setup_session.commit()
        user_id, version_id, template_id = user.id, version.id, template.id

    async def create_process():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            template_version = await session.get(
                ProcessTemplateVersion, version_id
            )
            process = await instantiate_process(
                session, template_version, 'Processo concorrente', user_id
            )
            return process.id, process.code

    process_ids: list = []
    try:
        results = await asyncio.gather(create_process(), create_process())
        process_ids = [pid for pid, _ in results]
        codes = [code for _, code in results]

        assert len(set(codes)) == len(codes)
        year_prefix = f'VAL-{datetime.now(UTC).year}-'
        assert all(code.startswith(year_prefix) for code in codes)
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as cleanup:
            await cleanup.execute(
                delete(AuditEvent).where(
                    AuditEvent.process_instance_id.in_(process_ids)
                )
            )
            await cleanup.execute(
                delete(Assignment).where(
                    Assignment.process_instance_id.in_(process_ids)
                )
            )
            await cleanup.execute(
                delete(ProcessInstance).where(
                    ProcessInstance.id.in_(process_ids)
                )
            )
            await cleanup.execute(
                delete(ProcessTemplateVersion).where(
                    ProcessTemplateVersion.id == version_id
                )
            )
            await cleanup.execute(
                delete(ProcessTemplate).where(
                    ProcessTemplate.id == template_id
                )
            )
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_failed_instantiation_rolls_back_all_process_records(
    session, monkeypatch
):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    version = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(ProcessTemplate.key == 'full_validation')
        )
    ).scalar_one()

    async def fail_after_process_flush(*args, **kwargs):
        raise RuntimeError('falha simulada na preparação da atividade')

    monkeypatch.setattr(
        'pivma.core.process_engine._create_phases_and_activities',
        fail_after_process_flush,
    )

    with pytest.raises(RuntimeError, match='falha simulada'):
        await instantiate_process(session, version, 'Falha atômica', user.id)

    process_count = await session.scalar(select(ProcessInstance.id))
    assignment_count = await session.scalar(select(Assignment.id))
    run_count = await session.scalar(select(ActivityRun.id))
    form_count = await session.scalar(select(FormInstance.id))

    assert process_count is None
    assert assignment_count is None
    assert run_count is None
    assert form_count is None
