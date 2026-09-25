"""Domínio do ciclo de vida do processo no banco (Spec 030, FR-002/FR-004)."""

import pytest
from sqlalchemy.exc import IntegrityError

from pivma.core.database.models import ProcessInstance
from tests.factories.process_factory import (
    ProcessInstanceFactory,
    ProcessTemplateFactory,
    ProcessTemplateVersionFactory,
)


async def _version(session):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.commit()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.commit()
    return version


@pytest.mark.asyncio
async def test_process_status_rejects_flow_value(session):
    version = await _version(session)
    session.add(
        ProcessInstanceFactory(template_version=version, status='TRIAGE')
    )

    with pytest.raises(IntegrityError, match='ck_process_instances_status'):
        await session.flush()


@pytest.mark.asyncio
async def test_process_status_defaults_to_open(session):
    version = await _version(session)
    process = ProcessInstance(
        template_version_id=version.id, code='VAL-DEFAULT', title='Padrão'
    )
    session.add(process)
    await session.flush()

    assert process.status == 'OPEN'
