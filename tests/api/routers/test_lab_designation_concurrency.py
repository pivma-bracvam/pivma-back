"""Ações institucionais simultâneas sobre a mesma designação (Spec 035, R4).

Encerrar o vínculo e inativar o laboratório ao mesmo tempo tornam não
efetiva a mesma designação. A trava nas designações candidatas faz a segunda
ação ler o estado já confirmado pela primeira: só um evento de perda.
"""

import asyncio
from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma import app
from pivma.core.authorization import (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
)
from pivma.core.database import get_session
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Assignment,
    AuditEvent,
    Institution,
    InstitutionalChange,
    Laboratory,
    Permission,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
    User,
    UserAccessProfile,
    UserInstitutionalAffiliation,
)
from pivma.core.security import create_access_token
from pivma.core.settings import Settings
from tests.api.routers.test_participant_concurrency import run_concurrently

PERMISSION_CODES = (
    INSTITUTIONAL_AFFILIATIONS_MANAGE,
    INSTITUTIONAL_CATALOGS_MANAGE,
)


def _user(kind: str, suffix: str) -> User:
    return User(
        username=f'lab-validity-{kind}-{suffix}',
        email=f'lab-validity-{kind}-{suffix}@test.com',
        password_hash='unused',
        full_name=f'Lab validity {kind} {suffix}',
    )


async def setup(engine) -> dict[str, UUID]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        suffix = uuid4().hex
        actor = _user('actor', suffix)
        target = _user('target', suffix)
        profile = AccessProfile(name=f'Lab validity {suffix}', description='')
        permissions = [
            Permission(code=code, description=code)
            for code in PERMISSION_CODES
        ]
        institution = Institution(name=f'Instituição {suffix}')
        template = ProcessTemplate(
            key=f'lab-validity-{suffix}', name='Lab validity template'
        )
        session.add_all([
            actor,
            target,
            profile,
            *permissions,
            institution,
            template,
        ])
        await session.flush()
        laboratory = Laboratory(
            institution_id=institution.id, name=f'Laboratório {suffix}'
        )
        version = ProcessTemplateVersion(
            template_id=template.id, version_number=1, definition_payload={}
        )
        session.add_all([laboratory, version])
        await session.flush()
        affiliation = UserInstitutionalAffiliation(
            user_id=target.id,
            institution_id=institution.id,
            laboratory_id=laboratory.id,
        )
        process = ProcessInstance(
            template_version_id=version.id,
            code=f'LABV-{suffix[:20]}',
            title='Processo de concorrência',
        )
        session.add_all([
            affiliation,
            process,
            *(
                AccessProfilePermission(
                    profile_id=profile.id, permission_id=permission.id
                )
                for permission in permissions
            ),
            UserAccessProfile(user_id=actor.id, profile_id=profile.id),
        ])
        await session.flush()
        session.add(
            Assignment(
                process_instance_id=process.id,
                user_id=target.id,
                assigned_by=actor.id,
                role_key='participating_laboratory',
                laboratory_id=laboratory.id,
            )
        )
        await session.commit()
        return {
            'actor': actor.id,
            'target': target.id,
            'profile': profile.id,
            'permissions': [permission.id for permission in permissions],
            'institution': institution.id,
            'laboratory': laboratory.id,
            'affiliation': affiliation.id,
            'process': process.id,
            'version': version.id,
            'template': template.id,
        }


async def cleanup(engine, ids: dict) -> None:
    async with AsyncSession(engine) as session:
        for statement in (
            delete(AuditEvent).where(
                AuditEvent.process_instance_id == ids['process']
            ),
            delete(Assignment).where(
                Assignment.process_instance_id == ids['process']
            ),
            delete(ProcessInstance).where(
                ProcessInstance.id == ids['process']
            ),
            delete(ProcessTemplateVersion).where(
                ProcessTemplateVersion.id == ids['version']
            ),
            delete(ProcessTemplate).where(
                ProcessTemplate.id == ids['template']
            ),
            delete(InstitutionalChange).where(
                InstitutionalChange.created_by == ids['actor']
            ),
            delete(UserInstitutionalAffiliation).where(
                UserInstitutionalAffiliation.id == ids['affiliation']
            ),
            delete(Laboratory).where(Laboratory.id == ids['laboratory']),
            delete(Institution).where(Institution.id == ids['institution']),
            delete(UserAccessProfile).where(
                UserAccessProfile.user_id == ids['actor']
            ),
            delete(AccessProfilePermission).where(
                AccessProfilePermission.profile_id == ids['profile']
            ),
            delete(AccessProfile).where(AccessProfile.id == ids['profile']),
            delete(Permission).where(Permission.id.in_(ids['permissions'])),
            delete(User).where(User.id.in_([ids['actor'], ids['target']])),
        ):
            await session.execute(
                statement.execution_options(skip_soft_delete_filter=True)
            )
        await session.commit()


async def lost_events(engine, process_id: UUID) -> list[AuditEvent]:
    async with AsyncSession(engine) as session:
        return list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.process_instance_id == process_id,
                    AuditEvent.event_type == 'PARTICIPANT_EFFECTIVENESS_LOST',
                )
            )
        )


def test_concurrent_affiliation_end_and_lab_deactivation_record_one_event(
    engine,
):
    ids = asyncio.run(setup(engine))

    async def independent_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = independent_session
    try:
        headers = {
            'Cookie': 'access_token='
            + create_access_token(ids['actor'], Settings().JWT_SECRET_KEY),
            'Origin': 'https://testserver',
        }
        with TestClient(app, base_url='https://testserver') as client:
            responses = run_concurrently(
                client,
                (
                    lambda current: current.delete(
                        f'/institutional/users/{ids["target"]}/affiliations/'
                        f'{ids["affiliation"]}',
                        headers=headers,
                    ),
                    lambda current: current.delete(
                        f'/institutional/laboratories/{ids["laboratory"]}',
                        headers=headers,
                    ),
                ),
            )
        assert [item.status_code for item in responses] == [
            HTTPStatus.NO_CONTENT,
            HTTPStatus.NO_CONTENT,
        ]
        assert len(asyncio.run(lost_events(engine, ids['process']))) == 1
    finally:
        app.dependency_overrides.clear()
        asyncio.run(cleanup(engine, ids))
