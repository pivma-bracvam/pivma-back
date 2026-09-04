from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import Assignment, AuditEvent
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_list_and_get_process_templates(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. List templates
    resp = client.get("/processes/templates")
    assert resp.status_code == HTTPStatus.OK
    templates = resp.json()
    assert len(templates) >= 1
    assert any(t["key"] == "full_validation" for t in templates)

    # 2. Get detail
    resp_detail = client.get("/processes/templates/full_validation")
    assert resp_detail.status_code == HTTPStatus.OK
    detail = resp_detail.json()
    assert detail["key"] == "full_validation"
    assert "phases" in detail["definition"]


@pytest.mark.asyncio
async def test_create_and_list_process_instances(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # Create process
    create_payload = {
        "template_key": "full_validation",
        "title": "Validação de Teste In Vitro",
    }
    resp = client.post("/processes", json=create_payload)
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data["code"].startswith("VAL-")
    assert data["status"] == "SUBMISSION"
    process_id = data["id"]

    # Get single process
    resp_get = client.get(f"/processes/{process_id}")
    assert resp_get.status_code == HTTPStatus.OK
    assert resp_get.json()["id"] == process_id

    # List processes
    resp_list = client.get("/processes")
    assert resp_list.status_code == HTTPStatus.OK
    list_data = resp_list.json()
    assert list_data["total"] >= 1
    assert any(p["id"] == process_id for p in list_data["items"])


@pytest.mark.asyncio
async def test_process_creation_keeps_a_single_local_proponent_assignment(
    client, session
):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.post(
        "/processes",
        json={
            "template_key": "full_validation",
            "title": "Processo com proponente local",
        },
    )
    process_id = UUID(resp.json()["id"])

    count = await session.scalar(
        select(func.count())
        .select_from(Assignment)
        .where(
            Assignment.process_instance_id == process_id,
            Assignment.role_key == "proponent",
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_process_creation_records_participant_assigned_for_proponent(
    client, session
):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    resp = client.post(
        "/processes",
        json={
            "template_key": "full_validation",
            "title": "Processo com evento de designação",
        },
    )
    process_id = UUID(resp.json()["id"])

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process_id,
            AuditEvent.event_type == "PARTICIPANT_ASSIGNED",
        )
    )
    assert event.context_data["participant_user_id"] == str(user.id)
    assert event.context_data["role_key"] == "proponent"
    assert event.context_data["source"] == "process_creation"


@pytest.mark.asyncio
async def test_process_list_is_scoped_to_active_proponent(client, session):
    await bootstrap_all_templates(session)
    owner = UserFactory()
    outsider = UserFactory()
    session.add_all([owner, outsider])
    await session.commit()
    authenticate(client, owner)
    created = client.post(
        '/processes',
        json={'template_key': 'full_validation', 'title': 'Processo do dono'},
    )
    process_id = created.json()['id']

    authenticate(client, outsider)
    response = client.get('/processes')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['total'] == 0
    assert all(item['id'] != process_id for item in response.json()['items'])
    assert (
        client.get(f'/processes/{process_id}').status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        client.get(f'/processes/{process_id}/timeline').status_code
        == HTTPStatus.NOT_FOUND
    )
