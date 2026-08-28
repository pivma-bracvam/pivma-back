import asyncio
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.authorization import PROCESS_PARTICIPANTS_MANAGE
from pivma.core.database import get_session
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Assignment,
    AuditEvent,
    Permission,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
    UserAccessProfile,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings


def run_concurrently(client: TestClient, requests):
    barrier = Barrier(2)

    def run(request):
        barrier.wait()
        return request(client)

    with ThreadPoolExecutor(2) as executor:
        return list(executor.map(run, requests))


async def setup_actor(engine) -> tuple[UUID, UUID, UUID]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        suffix = uuid4().hex
        actor = User(
            username=f'participant-actor-{suffix}',
            email=f'participant-actor-{suffix}@test.com',
            password_hash='unused',
        )
        permission = Permission(
            code=PROCESS_PARTICIPANTS_MANAGE,
            description='Concurrent participant management',
        )
        profile = AccessProfile(name=f'Participants {suffix}', description='')
        session.add_all([actor, permission, profile])
        await session.flush()
        session.add_all([
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            ),
            UserAccessProfile(user_id=actor.id, profile_id=profile.id),
        ])
        await session.commit()
        return actor.id, profile.id, permission.id


async def setup_process_and_target(engine) -> tuple[UUID, UUID]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        suffix = uuid4().hex
        target = User(
            username=f'participant-target-{suffix}',
            email=f'participant-target-{suffix}@test.com',
            password_hash='unused',
        )
        template = ProcessTemplate(
            key=f'concurrency-{suffix}', name='Concurrency template'
        )
        session.add_all([target, template])
        await session.flush()
        version = ProcessTemplateVersion(
            template_id=template.id, version_number=1, definition_payload={}
        )
        session.add(version)
        await session.flush()
        process = ProcessInstance(
            template_version_id=version.id,
            code=f'CONC-{suffix[:20]}',
            title='Processo de concorrência',
        )
        session.add(process)
        await session.commit()
        return target.id, process.id


async def cleanup(
    engine,
    actor: tuple[UUID, UUID, UUID],
    target: tuple[UUID, UUID],
):
    actor_id, profile_id, permission_id = actor
    target_id, process_id = target
    async with AsyncSession(engine) as session:
        await session.execute(
            delete(AuditEvent).where(
                AuditEvent.process_instance_id == process_id
            )
        )
        await session.execute(
            delete(Assignment).where(
                Assignment.process_instance_id == process_id
            )
        )
        process = await session.get(ProcessInstance, process_id)
        version_id = process.template_version_id if process else None
        await session.execute(
            delete(ProcessInstance).where(ProcessInstance.id == process_id)
        )
        if version_id is not None:
            version = await session.get(ProcessTemplateVersion, version_id)
            template_id = version.template_id if version else None
            await session.execute(
                delete(ProcessTemplateVersion).where(
                    ProcessTemplateVersion.id == version_id
                )
            )
            if template_id is not None:
                await session.execute(
                    delete(ProcessTemplate).where(
                        ProcessTemplate.id == template_id
                    )
                )
        await session.execute(
            delete(UserAccessProfile).where(
                UserAccessProfile.user_id == actor_id
            )
        )
        await session.execute(
            delete(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == profile_id
            )
        )
        await session.execute(
            delete(AccessProfile).where(AccessProfile.id == profile_id)
        )
        await session.execute(
            delete(Permission).where(Permission.id == permission_id)
        )
        await session.execute(
            delete(User).where(User.id.in_([actor_id, target_id]))
        )
        await session.commit()


def test_concurrent_equivalent_assignments_create_one_active_cycle(engine):
    actor_id, profile_id, permission_id = asyncio.run(setup_actor(engine))
    target_id, process_id = asyncio.run(setup_process_and_target(engine))

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = independent_session
    try:
        headers = {
            'Cookie': 'access_token='
            + create_access_token(actor_id, Settings().JWT_SECRET_KEY),
            'Origin': 'https://testserver',
        }
        path = f'/processes/{process_id}/participants'
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                (
                    lambda current: current.post(
                        path,
                        headers=headers,
                        json={
                            'user_id': str(target_id),
                            'role_key': 'study_manager',
                        },
                    ),
                    lambda current: current.post(
                        path,
                        headers=headers,
                        json={
                            'user_id': str(target_id),
                            'role_key': 'study_manager',
                        },
                    ),
                ),
            )
        assert sorted(item.status_code for item in responses) == [
            HTTPStatus.CREATED,
            HTTPStatus.CONFLICT,
        ]

        async def count_active():
            async with AsyncSession(engine) as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(Assignment)
                    .where(
                        Assignment.process_instance_id == process_id,
                        Assignment.user_id == target_id,
                        Assignment.role_key == 'study_manager',
                        Assignment.revoked_at.is_(None),
                        Assignment.deleted_at.is_(None),
                    )
                )

        assert asyncio.run(count_active()) == 1
    finally:
        app.dependency_overrides.clear()
        asyncio.run(
            cleanup(
                engine,
                (actor_id, profile_id, permission_id),
                (target_id, process_id),
            )
        )
