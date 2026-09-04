# ruff: noqa: PLR2004, PLR0914, PLR0915

from datetime import datetime, timezone
from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    Artifact,
    Assignment,
    AuditEvent,
    FormField,
    FormTemplate,
    FormValue,
    ProcessInstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.participant_factory import AssignmentFactory
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_form_draft_and_submission_flow(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. Create process
    resp = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Estudo de Irritação Cutânea',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']

    # 2. Get form definition
    form_resp = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert form_resp.status_code == HTTPStatus.OK
    form_data = form_resp.json()
    assert form_data['template_key'] == 'submission_full_validation_v1'
    assert len(form_data['fields']) >= 4
    assert not form_data['is_submitted']

    # 3. Save draft
    draft_payload = {
        'values': {
            'method_title': 'Título em Rascunho',
            'endpoint_target': 'skin_sensitization',
        }
    }
    draft_resp = client.put(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=draft_payload,
    )
    assert draft_resp.status_code == HTTPStatus.OK

    # 4. Check form values after draft
    form_resp_2 = client.get(
        f'/processes/{process_id}/activities/proposal_submission/form'
    )
    assert form_resp_2.json()['values']['method_title'] == 'Título em Rascunho'

    # 5. Fail formal submit when required fields are missing
    invalid_submit_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=draft_payload,
    )
    assert invalid_submit_resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 6. Formal submit with all required fields
    full_payload = {
        'values': {
            'method_title': 'Método de Ensaio Concluído',
            'endpoint_target': 'skin_sensitization',
            'scientific_justification': 'Fundamentação completa do método.',
            'study_protocol_file': 'protocolo.pdf',
        }
    }
    submit_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=full_payload,
    )
    assert submit_resp.status_code == HTTPStatus.OK
    submit_data = submit_resp.json()
    assert submit_data['status'] == 'COMPLETED'
    assert submit_data['artifact_id'] is not None

    # 7. Check process status changed to TRIAGE
    p_resp = client.get(f'/processes/{process_id}')
    assert p_resp.json()['status'] == 'TRIAGE'

    # 8. Check timeline
    tl_resp = client.get(f'/processes/{process_id}/timeline')
    assert tl_resp.status_code == HTTPStatus.OK
    events = tl_resp.json()['events']
    event_types = [e['event_type'] for e in events]
    assert 'PROCESS_CREATED' in event_types
    assert 'FORM_DRAFT_SAVED' in event_types
    assert 'SUBMISSION_SUBMITTED' in event_types


async def _create_submission(client, session, user):
    await bootstrap_all_templates(session)
    session.add(user)
    await session.commit()
    authenticate(client, user)
    response = client.post(
        '/processes',
        json={
            'template_key': 'full_validation',
            'title': 'Submissão de teste',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()['id']


@pytest.mark.asyncio
async def test_draft_rejects_unknown_field_atomically(client, session):
    user = UserFactory()
    process_id = await _create_submission(client, session, user)
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    assert (
        client.put(
            endpoint, json={'values': {'method_title': 'Anterior'}
        }
        ).status_code
        == HTTPStatus.OK
    )
    response = client.put(
        endpoint,
        json={'values': {'method_title': 'Novo', 'unknown_field': 'x'}},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    error = response.json()['detail']
    assert error['code'] == 'invalid_form_values'
    assert error['errors'][0]['field_key'] == 'unknown_field'
    values = client.get(endpoint).json()['values']
    assert values['method_title'] == 'Anterior'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('field_key', 'value', 'error_code'),
    [
        ('expected_laboratories_count', 'many', 'invalid_type'),
        ('endpoint_target', 'unknown', 'invalid_option'),
        ('expected_laboratories_count', 0, 'min_value'),
        ('expected_laboratories_count', 51, 'max_value'),
    ],
)
async def test_draft_rejects_incompatible_values(
    client, session, field_key, value, error_code
):
    user = UserFactory()
    process_id = await _create_submission(client, session, user)
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    response = client.put(endpoint, json={'values': {field_key: value}})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['errors'][0]['code'] == error_code


@pytest.mark.asyncio
async def test_draft_persists_false_and_zero_from_dynamic_fields(
    client, session
):
    user = UserFactory()
    process_id = await _create_submission(client, session, user)
    form_template = (
        await session.execute(
            select(FormTemplate).where(
                FormTemplate.key == 'submission_full_validation_v1'
            )
        )
    ).scalar_one()
    session.add_all([
        FormField(
            form_template_id=form_template.id,
            field_key='is_reproducible',
            label='Reprodutível',
            field_type='boolean',
            order_index=6,
        ),
        FormField(
            form_template_id=form_template.id,
            field_key='optional_count',
            label='Contagem opcional',
            field_type='integer',
            order_index=7,
        ),
    ])
    await session.commit()
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    response = client.put(
        endpoint,
        json={'values': {'is_reproducible': False, 'optional_count': 0}},
    )

    assert response.status_code == HTTPStatus.OK
    values = client.get(endpoint).json()['values']
    assert values['is_reproducible'] is False
    assert values['optional_count'] == 0


@pytest.mark.asyncio
async def test_draft_rejects_file_upload_without_persisting_artifact(
    client, session
):
    user = UserFactory()
    process_id = await _create_submission(client, session, user)
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    response = client.put(
        endpoint,
        json={'values': {'study_protocol_file': 'protocol.pdf'}},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        response.json()['detail']['errors'][0]['code']
        == 'file_upload_not_supported'
    )
    assert await session.scalar(select(FormValue.id)) is None
    assert await session.scalar(select(Artifact.id)) is None


@pytest.mark.asyncio
async def test_submission_resources_are_hidden_from_non_proponent(
    client, session, other_user
):
    owner = UserFactory()
    process_id = await _create_submission(client, session, owner)
    authenticate(client, other_user)

    urls = [
        f'/processes/{process_id}',
        f'/processes/{process_id}/timeline',
        f'/processes/{process_id}/activities/proposal_submission/form',
    ]
    responses = [client.get(url) for url in urls]
    responses.append(client.put(urls[-1], json={'values': {}}))
    responses.append(client.post(urls[-1], json={'values': {}}))

    assert [response.status_code for response in responses] == [
        HTTPStatus.NOT_FOUND
    ] * len(responses)


@pytest.mark.asyncio
async def test_revoked_proponent_cannot_read_or_write_form(client, session):
    owner = UserFactory()
    process_id = await _create_submission(client, session, owner)
    assignment = (
        await session.execute(
            select(Assignment).where(
                Assignment.process_instance_id == process_id,
                Assignment.role_key == 'proponent',
            )
        )
    ).scalar_one()
    assignment.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    assert client.get(endpoint).status_code == HTTPStatus.NOT_FOUND
    assert (
        client.put(endpoint, json={'values': {}}).status_code
        == HTTPStatus.NOT_FOUND
    )


@pytest.mark.asyncio
async def test_draft_replaces_existing_value_and_records_author(
    client, session
):
    owner = UserFactory()
    process_id = await _create_submission(client, session, owner)
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    client.put(endpoint, json={'values': {'method_title': 'Versão 1'}})
    client.put(endpoint, json={'values': {'method_title': 'Versão 2'}})

    values = client.get(endpoint).json()['values']
    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process_id,
            AuditEvent.event_type == 'FORM_DRAFT_SAVED',
        ).order_by(AuditEvent.occurred_at.desc())
    )
    assert values['method_title'] == 'Versão 2'
    assert event.user_id == owner.id


@pytest.mark.asyncio
async def test_draft_null_clears_existing_value(client, session):
    owner = UserFactory()
    process_id = await _create_submission(client, session, owner)
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    client.put(endpoint, json={'values': {'method_title': 'A limpar'}})
    response = client.put(endpoint, json={'values': {'method_title': None}})

    assert response.status_code == HTTPStatus.OK
    assert client.get(endpoint).json()['values']['method_title'] is None


@pytest.mark.asyncio
async def test_active_participant_with_other_role_cannot_read_form(
    client, session, other_user
):
    owner = UserFactory()
    process_id = await _create_submission(client, session, owner)
    process = await session.get(ProcessInstance, process_id)
    session.add(
        AssignmentFactory(
            process=process,
            user=other_user,
            assigner=owner,
            role_key='study_manager',
        )
    )
    await session.commit()
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    authenticate(client, other_user)

    assert client.get(endpoint).status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_active_participant_with_other_role_cannot_save_draft(
    client, session, other_user
):
    owner = UserFactory()
    process_id = await _create_submission(client, session, owner)
    process = await session.get(ProcessInstance, process_id)
    session.add(
        AssignmentFactory(
            process=process,
            user=other_user,
            assigner=owner,
            role_key='study_manager',
        )
    )
    await session.commit()
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    authenticate(client, other_user)

    response = client.put(endpoint, json={'values': {}})
    assert response.status_code == HTTPStatus.NOT_FOUND
