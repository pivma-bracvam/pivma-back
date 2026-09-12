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
            'template_key': 'pre_validated_method',
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
    assert form_data['template_key'] == 'submission_pre_validated_v1'
    assert len(form_data['fields']) == 1
    assert not form_data['is_submitted']

    # 3. Save draft
    draft_payload = {'values': {'method_title': 'Título em Rascunho'}}
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

    # 5. Try submitting incomplete form (should fail)
    incomplete_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json={'values': {}},
    )
    assert incomplete_resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 6. Submit complete form
    full_payload = {'values': {'method_title': 'Método de Ensaio Concluído'}}
    submit_resp = client.post(
        f'/processes/{process_id}/activities/proposal_submission/form',
        json=full_payload,
    )
    assert submit_resp.status_code == HTTPStatus.OK
    submit_data = submit_resp.json()
    assert submit_data['status'] == 'COMPLETED'
    assert submit_data['artifact_id'] is not None

    dossier = await session.scalar(
        select(Artifact).where(
            Artifact.process_instance_id == process_id,
            Artifact.key == 'proposal_dossier',
        )
    )
    assert dossier.metadata_payload['title'] == 'Estudo de Irritação Cutânea'

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
            'template_key': 'pre_validated_method',
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
            endpoint, json={'values': {'method_title': 'Anterior'}}
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


async def _add_typed_fields(session):
    """Adiciona campos tipados ao formulário simples para exercitar as regras
    de validação de rascunho (o formulário de demo tem apenas `method_title`).
    """
    form_template = (
        await session.execute(
            select(FormTemplate).where(
                FormTemplate.key == 'submission_pre_validated_v1'
            )
        )
    ).scalar_one()
    session.add_all([
        FormField(
            form_template_id=form_template.id,
            field_key='demo_count',
            label='Contagem demo',
            field_type='integer',
            order_index=10,
            validation_rules={'min': 1, 'max': 50},
        ),
        FormField(
            form_template_id=form_template.id,
            field_key='demo_choice',
            label='Escolha demo',
            field_type='select',
            order_index=11,
            options=[
                {'value': 'a', 'label': 'A'},
                {'value': 'b', 'label': 'B'},
            ],
        ),
    ])
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('field_key', 'value', 'error_code'),
    [
        ('demo_count', 'many', 'invalid_type'),
        ('demo_choice', 'unknown', 'invalid_option'),
        ('demo_count', 0, 'min_value'),
        ('demo_count', 51, 'max_value'),
    ],
)
async def test_draft_rejects_incompatible_values(
    client, session, field_key, value, error_code
):
    user = UserFactory()
    process_id = await _create_submission(client, session, user)
    await _add_typed_fields(session)
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
                FormTemplate.key == 'submission_pre_validated_v1'
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
async def test_draft_rejects_inline_file_upload_value_without_persisting(
    client, session
):
    user = UserFactory()
    process_id = await _create_submission(client, session, user)
    form_template = (
        await session.execute(
            select(FormTemplate).where(
                FormTemplate.key == 'submission_pre_validated_v1'
            )
        )
    ).scalar_one()
    session.add(
        FormField(
            form_template_id=form_template.id,
            field_key='protocol_file',
            label='Protocolo (PDF)',
            field_type='file_upload',
            order_index=12,
        )
    )
    await session.commit()
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'

    response = client.put(
        endpoint,
        json={'values': {'protocol_file': 'protocol.pdf'}},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        response.json()['detail']['errors'][0]['code']
        == 'file_upload_uses_attachment_endpoint'
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
        select(AuditEvent)
        .where(
            AuditEvent.process_instance_id == process_id,
            AuditEvent.event_type == 'FORM_DRAFT_SAVED',
        )
        .order_by(AuditEvent.occurred_at.desc())
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('template_key', 'expected_form_key', 'valid_values'),
    [
        (
            'pre_validated_method',
            'submission_pre_validated_v1',
            {
                'method_title': 'Método Pré-Validado Teste',
                'endpoint_target': 'ocular_irritation',
                'scientific_justification': (
                    'Justificativa científica detalhada com mais de'
                    ' cinquenta caracteres.'
                ),
                'pre_validation_evidence': (
                    'Evidências prévias de repetibilidade com mais de'
                    ' cinquenta caracteres.'
                ),
                'study_protocol_file': 'protocolo.pdf',
            },
        ),
        (
            'scope_extension',
            'submission_scope_extension_v1',
            {
                'method_title': 'Extensão de Escopo Teste',
                'base_validated_method': 'OECD TG 492',
                'new_application_endpoint': 'medical_devices',
                'scope_extension_justification': (
                    'Justificativa de extensão com mais de cinquenta'
                    ' caracteres biológicos.'
                ),
                'applicability_domain_data': (
                    'Dados de domínio de aplicabilidade com mais de cinquenta'
                    ' caracteres.'
                ),
                'adapted_protocol_file': 'protocolo_adaptado.pdf',
            },
        ),
        (
            'me_too_validation',
            'submission_me_too_v1',
            {
                'method_title': 'Validação Me-Too Teste',
                'reference_validated_method': 'EpiOcular',
                'target_test_system': 'Tecido Reconstruído Nacional',
                'mechanistic_similarity_rationale': (
                    'Fundamentação da semelhança mecanística com mais de'
                    ' cinquenta caracteres.'
                ),
                'functional_equivalence_evidence': (
                    'Evidências de equivalência funcional com mais de'
                    ' cinquenta caracteres.'
                ),
                'comparative_protocol_file': 'comparativo.pdf',
            },
        ),
        (
            'validated_method_dossier',
            'submission_validated_dossier_v1',
            {
                'method_title': 'Dossiê Completo Teste',
                'terminology_notes': (
                    'Conceito descrito com nomenclatura atual da OCDE e mais'
                    ' de trinta caracteres.'
                ),
            },
        ),
        (
            'proof_of_concept',
            'submission_proof_of_concept_v1',
            {
                'proponent_organization': 'Instituto de Testes Alternativos',
                'contact_first_name': 'Ana',
                'contact_last_name': 'Souza',
                'contact_email': 'ana.souza@exemplo.org',
                'method_name': 'Modelo conceitual órgão-em-chip',
            },
        ),
    ],
)
async def test_all_five_process_forms_definitions_and_submissions(
    client, session, template_key, expected_form_key, valid_values
):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    authenticate(client, user)

    # 1. Create process
    resp = client.post(
        '/processes',
        json={
            'template_key': template_key,
            'title': f'Processo {template_key}',
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    process_id = resp.json()['id']

    # 2. Get form
    endpoint = f'/processes/{process_id}/activities/proposal_submission/form'
    form_resp = client.get(endpoint)
    assert form_resp.status_code == HTTPStatus.OK
    form_data = form_resp.json()
    assert form_data['template_key'] == expected_form_key

    # 3. Submit form
    submit_resp = client.post(endpoint, json={'values': valid_values})
    assert submit_resp.status_code == HTTPStatus.OK
    submit_data = submit_resp.json()
    assert submit_data['status'] == 'COMPLETED'
    assert submit_data['artifact_id'] is not None
    # Spec 014: sem esteira legada. Templates padrão não têm avaliações por IA
    # associadas → sem `ai_evaluation`, sem pré-avaliação.
    assert 'ai_evaluation' not in submit_data
    assert submit_data['pre_evaluation'] is None
