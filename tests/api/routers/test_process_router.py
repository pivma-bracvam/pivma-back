from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import func, select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    Assignment,
    AuditEvent,
    ProcessInstance,
    ProcessTemplate,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

TRUSTED_ORIGIN = {'Origin': 'https://testserver'}
SUBMISSION_TYPE_KEYS = [
    'pre_validated_method',
    'validated_method_dossier',
    'scope_extension',
    'me_too_validation',
]


@pytest.mark.asyncio
async def test_list_and_get_process_templates(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. List templates
    resp = client.get('/processes/templates')
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert [t['key'] for t in body['data']] == SUBMISSION_TYPE_KEYS
    assert body['sort'] == {'by': 'display_order', 'order': 'asc'}

    # 2. Get detail
    resp_detail = client.get('/processes/templates/pre_validated_method')
    assert resp_detail.status_code == HTTPStatus.OK
    detail = resp_detail.json()
    assert detail['key'] == 'pre_validated_method'
    assert detail['name'] == 'Método Novo'
    assert 'phases' in detail['definition']

    # 3. Ensure legacy full_validation returns 404
    resp_legacy = client.get('/processes/templates/full_validation')
    assert resp_legacy.status_code == HTTPStatus.NOT_FOUND


async def _authenticated_with_templates(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)


@pytest.mark.asyncio
async def test_template_names_and_descriptions_have_no_english_terms(
    client, session
):
    await _authenticated_with_templates(client, session)

    templates = client.get('/processes/templates').json()['data']

    texts = ' '.join(f'{t["name"]} {t["description"]}' for t in templates)
    for term in ('Fitness', 'Me-Too', 'Peer-Review', 'Validation-Ready'):
        assert term not in texts


@pytest.mark.asyncio
async def test_template_without_display_order_comes_after_the_four_types(
    client, session
):
    await _authenticated_with_templates(client, session)
    session.add(ProcessTemplate(key='aaa_sem_ordem', name='AAA sem ordem'))
    await session.commit()

    templates = client.get('/processes/templates').json()['data']

    assert [t['key'] for t in templates] == [
        *SUBMISSION_TYPE_KEYS,
        'aaa_sem_ordem',
    ]


@pytest.mark.asyncio
async def test_templates_with_same_display_order_are_sorted_by_key(
    client, session
):
    await _authenticated_with_templates(client, session)
    session.add_all([
        ProcessTemplate(key='zz_empate', name='A', display_order=99),
        ProcessTemplate(key='yy_empate', name='B', display_order=99),
    ])
    await session.commit()

    templates = client.get('/processes/templates').json()['data']

    assert [t['key'] for t in templates][-2:] == ['yy_empate', 'zz_empate']


@pytest.mark.asyncio
async def test_proof_of_concept_template_detail_is_not_found(client, session):
    await _authenticated_with_templates(client, session)

    resp = client.get('/processes/templates/proof_of_concept')

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail']['code'] == 'not_found'


@pytest.mark.asyncio
async def test_create_proof_of_concept_process_is_not_found(client, session):
    await _authenticated_with_templates(client, session)

    resp = client.post(
        '/processes',
        json={'template_key': 'proof_of_concept', 'title': 'Prova'},
        headers=TRUSTED_ORIGIN,
    )

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json()['detail']['code'] == 'not_found'
    assert await session.scalar(select(func.count(ProcessInstance.id))) == 0


@pytest.mark.asyncio
async def test_create_and_list_process_instances(client, session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # Create process
    create_payload = {
        'template_key': 'pre_validated_method',
        'title': 'Validação de Teste In Vitro',
    }
    resp = client.post(
        '/processes', json=create_payload, headers=TRUSTED_ORIGIN
    )
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['code'].startswith('VAL-')
    assert data['status'] == 'OPEN'
    process_id = data['id']

    # Get single process
    resp_get = client.get(f'/processes/{process_id}')
    assert resp_get.status_code == HTTPStatus.OK
    assert resp_get.json()['id'] == process_id

    # List processes
    resp_list = client.get('/processes')
    assert resp_list.status_code == HTTPStatus.OK
    list_data = resp_list.json()
    assert list_data['pagination']['total_items'] >= 1
    assert any(p['id'] == process_id for p in list_data['data'])


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
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo com proponente local',
        },
        headers=TRUSTED_ORIGIN,
    )
    process_id = UUID(resp.json()['id'])

    count = await session.scalar(
        select(func.count())
        .select_from(Assignment)
        .where(
            Assignment.process_instance_id == process_id,
            Assignment.role_key == 'proponent',
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
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo com evento de designação',
        },
        headers=TRUSTED_ORIGIN,
    )
    process_id = UUID(resp.json()['id'])

    event = await session.scalar(
        select(AuditEvent).where(
            AuditEvent.process_instance_id == process_id,
            AuditEvent.event_type == 'PARTICIPANT_ASSIGNED',
        )
    )
    assert event.context_data['participant_user_id'] == str(user.id)
    assert event.context_data['role_key'] == 'proponent'
    assert event.context_data['source'] == 'process_creation'


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
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo do dono',
        },
        headers=TRUSTED_ORIGIN,
    )
    process_id = created.json()['id']

    authenticate(client, outsider)
    response = client.get('/processes')

    assert response.status_code == HTTPStatus.OK
    assert response.json()['pagination']['total_items'] == 0
    assert all(item['id'] != process_id for item in response.json()['data'])
    assert (
        client.get(f'/processes/{process_id}').status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        client.get(f'/processes/{process_id}/timeline').status_code
        == HTTPStatus.NOT_FOUND
    )
