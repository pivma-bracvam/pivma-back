"""Spec 018 - correção de visibilidade em `GET /processes`.

Antes desta spec, qualquer usuário autenticado via um status fora de
`PROPONENT_SCOPED_STATUSES` (ex.: `TRIAGE`). Agora só quem tem acesso de
plataforma (`Admin`/`BraCVAM`) ou atribuição ativa naquele processo enxerga.
"""

from http import HTTPStatus

import pytest

from pivma.core.authorization import (
    ADMINISTRATOR_SYSTEM_KEY,
    BRACVAM_SYSTEM_KEY,
)
from tests.api.routers.test_rbac_router import authenticate
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


async def _make_process(session, *, status):
    template = ProcessTemplateFactory()
    session.add(template)
    await session.commit()
    version = ProcessTemplateVersionFactory(template=template)
    session.add(version)
    await session.commit()
    process = ProcessInstanceFactory(template_version=version, status=status)
    session.add(process)
    await session.commit()
    return process


@pytest.mark.asyncio
async def test_padrao_user_without_assignment_cannot_see_triage_process(
    client, session
):
    process = await _make_process(session, status='OPEN')
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    resp = client.get(f'/processes/{process.id}')
    assert resp.status_code == HTTPStatus.NOT_FOUND

    resp_list = client.get('/processes', params={'size': 100})
    assert resp_list.status_code == HTTPStatus.OK
    assert str(process.id) not in {
        item['id'] for item in resp_list.json()['items']
    }


@pytest.mark.asyncio
async def test_padrao_user_with_active_assignment_sees_triage_process(
    client, session
):
    process = await _make_process(session, status='OPEN')
    manager = UserFactory()
    session.add(manager)
    await session.commit()
    session.add(
        AssignmentFactory(
            process=process, user=manager, role_key='group_manager'
        )
    )
    await session.commit()
    authenticate(client, manager)

    resp = client.get(f'/processes/{process.id}')
    assert resp.status_code == HTTPStatus.OK

    resp_list = client.get('/processes', params={'size': 100})
    assert str(process.id) in {
        item['id'] for item in resp_list.json()['items']
    }


@pytest.mark.asyncio
async def test_bracvam_user_sees_any_process_without_assignment(
    client, session
):
    process = await _make_process(session, status='CLOSED')
    bracvam_user = UserFactory()
    profile = AccessProfileFactory(system_key=BRACVAM_SYSTEM_KEY)
    session.add_all([bracvam_user, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=bracvam_user, profile=profile))
    await session.commit()
    authenticate(client, bracvam_user)

    resp = client.get(f'/processes/{process.id}')
    assert resp.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_participant_sees_process_header_during_submission(
    client, session
):
    """Spec 030 (FR-015): o participante vê o cabeçalho do processo em

    qualquer momento; o conteúdo da submissão segue a concessão da atividade.
    """
    process = await _make_process(session, status='OPEN')
    other_role_holder = UserFactory()
    session.add(other_role_holder)
    await session.commit()
    session.add(
        AssignmentFactory(
            process=process, user=other_role_holder, role_key='sponsor'
        )
    )
    await session.commit()

    authenticate(client, other_role_holder)
    assert client.get(f'/processes/{process.id}').status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_user_without_assignment_gets_404_on_process(client, session):
    process = await _make_process(session, status='OPEN')
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    assert (
        client.get(f'/processes/{process.id}').status_code
        == HTTPStatus.NOT_FOUND
    )
    items = client.get('/processes', params={'size': 100}).json()['items']
    assert str(process.id) not in {item['id'] for item in items}


@pytest.mark.asyncio
async def test_admin_sees_any_process_without_assignment(client, session):
    process = await _make_process(session, status='OPEN')
    admin = UserFactory()
    profile = AccessProfileFactory(system_key=ADMINISTRATOR_SYSTEM_KEY)
    session.add_all([admin, profile])
    await session.commit()
    session.add(UserAccessProfileFactory(user=admin, profile=profile))
    await session.commit()
    authenticate(client, admin)

    assert client.get(f'/processes/{process.id}').status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_timeline_endpoint_applies_the_same_visibility(client, session):
    process = await _make_process(session, status='OPEN')
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    resp = client.get(f'/processes/{process.id}/timeline')
    assert resp.status_code == HTTPStatus.NOT_FOUND
