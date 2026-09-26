# ruff: noqa: PLR2004, PLR0914, PLR0915
"""API tests for the process submission update and history contract."""

from http import HTTPStatus

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    AuditEvent,
    FormField,
    FormTemplate,
    ProcessInstance,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory

SUBMISSION_URL = '/processes/{pid}/activities/proposal_submission/form'


async def _draft_context(client, session, *, owner=None, with_file=True):
    await bootstrap_all_templates(session)
    owner = owner or UserFactory()
    session.add(owner)
    await session.commit()
    authenticate(client, owner)
    response = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Título original da proposta',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    process_id = response.json()['id']

    template = await session.scalar(
        select(FormTemplate).where(
            FormTemplate.key == 'submission_pre_validated_v1'
        )
    )
    fields = [
        FormField(
            form_template_id=template.id,
            field_key='summary',
            label='Resumo',
            field_type='textarea',
            order_index=10,
        ),
        FormField(
            form_template_id=template.id,
            field_key='choice',
            label='Escolha',
            field_type='select',
            options=[{'value': 'a', 'label': 'Opção A'}],
            order_index=11,
        ),
        FormField(
            form_template_id=template.id,
            field_key='count',
            label='Contagem',
            field_type='integer',
            validation_rules={'min': 1, 'max': 10},
            order_index=12,
        ),
        FormField(
            form_template_id=template.id,
            field_key='ratio',
            label='Razão',
            field_type='float',
            validation_rules={'min': 0.1, 'max': 10.0},
            order_index=13,
        ),
        FormField(
            form_template_id=template.id,
            field_key='reference_date',
            label='Data de referência',
            field_type='date',
            order_index=14,
        ),
        FormField(
            form_template_id=template.id,
            field_key='active',
            label='Ativo',
            field_type='boolean',
            order_index=15,
        ),
        FormField(
            form_template_id=template.id,
            field_key='optional_note',
            label='Observação opcional',
            field_type='text',
            order_index=16,
        ),
    ]
    if with_file:
        fields.append(
            FormField(
                form_template_id=template.id,
                field_key='protocol_file',
                label='Protocolo',
                field_type='file_upload',
                order_index=17,
            )
        )
    session.add_all(fields)
    await session.commit()
    return owner, process_id


def _complete_values(*, optional_note='nota inicial'):
    return {
        'method_title': 'Método atualizado',
        'summary': 'Resumo atualizado da proposta',
        'choice': 'a',
        'count': 3,
        'ratio': 1.5,
        'reference_date': '2026-09-11',
        'active': False,
        'optional_note': optional_note,
    }


def _url(process_id):
    return SUBMISSION_URL.format(pid=process_id)


def _process_title(client, process_id):
    processes = client.get('/processes', params={'size': 100}).json()['items']
    return next(
        item['title'] for item in processes if item['id'] == process_id
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'field_key',
    [
        'method_title',
        'summary',
        'choice',
        'count',
        'ratio',
        'reference_date',
        'active',
    ],
)
async def test_put_persists_each_supported_dynamic_type(
    client, session, field_key
):
    values = _complete_values()
    _, process_id = await _draft_context(client, session)
    response = client.put(
        f'/processes/{process_id}',
        json={
            'title': 'Título integral atualizado',
            'values': values,
        },
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['title'] == 'Título integral atualizado'
    assert body['template_key'] == 'submission_pre_validated_v1'
    assert body['run_number'] == 1
    assert body['values'][field_key] == values[field_key]
    assert client.get(_url(process_id)).json()['values'] == values


@pytest.mark.asyncio
async def test_put_null_clears_optional_value(client, session):
    _, process_id = await _draft_context(client, session)
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título integral', 'values': _complete_values()},
    )
    values = _complete_values(optional_note=None)
    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título integral 2', 'values': values},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['values']['optional_note'] is None
    assert (
        client.get(_url(process_id)).json()['values']['optional_note'] is None
    )


@pytest.mark.asyncio
async def test_put_requires_all_non_file_fields(client, session):
    _, process_id = await _draft_context(client, session)
    values = _complete_values()
    values.pop('summary')

    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título integral', 'values': values},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['errors'][0]['field_key'] == 'summary'


@pytest.mark.asyncio
async def test_put_rejects_blank_required_field(client, session):
    _, process_id = await _draft_context(client, session)
    values = _complete_values()
    values['method_title'] = '   '

    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título integral', 'values': values},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()['detail']['errors'][0]['field_key'] == (
        'method_title'
    )


@pytest.mark.asyncio
async def test_put_rejects_unknown_field_atomically(client, session):
    _, process_id = await _draft_context(client, session)
    original = _complete_values()
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título anterior', 'values': original},
    )
    invalid = {**original, 'unknown_field': 'não permitido'}
    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título que não deve gravar', 'values': invalid},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _process_title(client, process_id) == 'Título anterior'
    assert client.get(_url(process_id)).json()['values'] == original


@pytest.mark.asyncio
async def test_put_rejects_incompatible_value_atomically(client, session):
    _, process_id = await _draft_context(client, session)
    original = _complete_values()
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título anterior', 'values': original},
    )
    invalid = {**original, 'count': 'três'}
    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título inválido', 'values': invalid},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert _process_title(client, process_id) == 'Título anterior'
    assert client.get(_url(process_id)).json()['values'] == original


@pytest.mark.asyncio
async def test_put_rejects_inline_file_value(client, session):
    _, process_id = await _draft_context(client, session)
    values = {**_complete_values(), 'protocol_file': 'protocolo.pdf'}

    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título integral', 'values': values},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        response.json()['detail']['errors'][0]['code']
        == 'file_upload_uses_attachment_endpoint'
    )


@pytest.mark.asyncio
async def test_patch_preserves_omitted_values(client, session):
    _, process_id = await _draft_context(client, session)
    original = _complete_values()
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título anterior', 'values': original},
    )

    response = client.patch(
        f'/processes/{process_id}', json={'values': {'count': 8}}
    )

    assert response.status_code == HTTPStatus.OK
    values = response.json()['values']
    assert values['count'] == 8
    for key, value in original.items():
        if key != 'count':
            assert values[key] == value


@pytest.mark.asyncio
async def test_patch_only_title_preserves_form_values(client, session):
    _, process_id = await _draft_context(client, session)
    original = _complete_values()
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título anterior', 'values': original},
    )

    response = client.patch(
        f'/processes/{process_id}', json={'title': 'Somente novo título'}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['title'] == 'Somente novo título'
    assert response.json()['values'] == original


@pytest.mark.asyncio
async def test_patch_rejects_unknown_field_atomically(client, session):
    _, process_id = await _draft_context(client, session)
    original = _complete_values()
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título anterior', 'values': original},
    )

    response = client.patch(
        f'/processes/{process_id}',
        json={'values': {'count': 9, 'unknown_field': 'x'}},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get(_url(process_id)).json()['values'] == original


@pytest.mark.asyncio
async def test_patch_rejects_empty_payload_and_numeric_limit_atomically(
    client, session
):
    _, process_id = await _draft_context(client, session)
    original = _complete_values()
    client.put(
        f'/processes/{process_id}',
        json={'title': 'Título anterior', 'values': original},
    )

    empty = client.patch(f'/processes/{process_id}', json={})
    invalid = client.patch(
        f'/processes/{process_id}', json={'values': {'count': 0}}
    )

    assert empty.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get(_url(process_id)).json()['values'] == original


@pytest.mark.asyncio
async def test_bracvam_cannot_patch_draft(client, session, bracvam_user):
    """Spec 030 (FR-016/FR-018): o BraCVAM vê o rascunho, mas só o cargo

    `proponent` edita a submissão.
    """
    _, process_id = await _draft_context(client, session)
    authenticate(client, bracvam_user)

    response = client.patch(
        f'/processes/{process_id}', json={'title': 'Gestão corrigiu o título'}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_unauthenticated_put_is_rejected(client, session):
    _, process_id = await _draft_context(client, session)
    client.cookies.clear()

    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título sem sessão', 'values': _complete_values()},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_non_owner_cannot_update_or_learn_submission(client, session):
    owner, process_id = await _draft_context(client, session)
    outsider = UserFactory()
    session.add(outsider)
    await session.commit()
    authenticate(client, outsider)

    response = client.patch(
        f'/processes/{process_id}', json={'title': 'Acesso indevido'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    process = await session.get(ProcessInstance, process_id)
    assert process.title == 'Título original da proposta'
    assert owner.id != outsider.id


@pytest.mark.asyncio
async def test_update_after_formal_submission_returns_conflict(
    client, session
):
    _, process_id = await _draft_context(client, session)
    client.post(
        _url(process_id), json={'values': {'method_title': 'Método enviado'}}
    )

    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Não pode alterar', 'values': _complete_values()},
    )

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_patch_after_formal_submission_returns_conflict(client, session):
    _, process_id = await _draft_context(client, session)
    client.post(
        _url(process_id), json={'values': {'method_title': 'Método enviado'}}
    )

    response = client.patch(
        f'/processes/{process_id}', json={'title': 'Não pode alterar'}
    )

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_update_closed_process_returns_conflict(client, session):
    _, process_id = await _draft_context(client, session)
    process = await session.get(ProcessInstance, process_id)
    process.status = 'CLOSED'
    await session.commit()

    response = client.patch(
        f'/processes/{process_id}', json={'title': 'Não pode alterar'}
    )

    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_draft_update_does_not_create_history_or_change_flow(
    client, session
):
    _, process_id = await _draft_context(client, session)
    process_before = await session.get(ProcessInstance, process_id)
    run_before = client.get(_url(process_id)).json()['form_instance_id']

    response = client.put(
        f'/processes/{process_id}',
        json={'title': 'Título atualizado', 'values': _complete_values()},
    )

    assert response.status_code == HTTPStatus.OK
    process_after = await session.get(ProcessInstance, process_id)
    assert process_after.status == process_before.status == 'OPEN'
    assert response.json()['form_instance_id'] == run_before
    assert (
        client.get(f'/processes/{process_id}/submission-versions').json() == []
    )


@pytest.mark.asyncio
async def test_patch_draft_does_not_create_history(client, session):
    _, process_id = await _draft_context(client, session)

    response = client.patch(
        f'/processes/{process_id}',
        json={'title': 'Título parcial'},
    )

    assert response.status_code == HTTPStatus.OK
    assert (
        client.get(f'/processes/{process_id}/submission-versions').json() == []
    )


@pytest.mark.asyncio
async def test_patch_draft_does_not_change_status_or_run(client, session):
    _, process_id = await _draft_context(client, session)
    before = client.get(_url(process_id)).json()

    response = client.patch(
        f'/processes/{process_id}',
        json={'values': {'count': 7}},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['status'] == 'OPEN'
    assert response.json()['run_number'] == 1
    assert response.json()['form_instance_id'] == before['form_instance_id']


@pytest.mark.asyncio
async def test_update_rejects_immutable_process_attribute(client, session):
    _, process_id = await _draft_context(client, session)

    response = client.patch(
        f'/processes/{process_id}',
        json={'status': 'TRIAGE', 'title': 'Título válido'},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_update_audit_records_mode_and_attributes_without_values(
    client, session
):
    _, process_id = await _draft_context(client, session)

    response = client.patch(
        f'/processes/{process_id}',
        json={'title': 'Título auditado', 'values': {'count': 4}},
    )

    assert response.status_code == HTTPStatus.OK
    event = await session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.process_instance_id == process_id,
            AuditEvent.event_type == 'SUBMISSION_UPDATED',
        )
        .order_by(AuditEvent.occurred_at.desc())
    )
    assert event.user_id is not None
    assert event.context_data['mode'] == 'PATCH'
    assert set(event.context_data['attributes']) == {'title', 'count'}
    assert 'values' not in event.context_data


@pytest.mark.asyncio
async def test_history_is_frozen_and_latest_form_is_current(
    client, session, bracvam_user
):
    owner, process_id = await _draft_context(client, session)
    first_values = {'method_title': 'Método versão 1'}
    client.post(_url(process_id), json={'values': first_values})

    authenticate(client, bracvam_user)
    decision = client.post(
        f'/processes/{process_id}/triage/decision',
        headers={'Origin': 'https://testserver'},
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Atualizar evidências da proposta.',
        },
    )
    assert decision.status_code == HTTPStatus.OK

    authenticate(client, owner)
    # Spec 030: o proponente escolhe revisar antes de a submissão reabrir.
    client.post(
        f'/processes/{process_id}/return-review',
        json={'choice': 'REVISE'},
        headers={'Origin': 'https://testserver'},
    )
    second_values = {'method_title': 'Método versão 2'}
    client.patch(
        f'/processes/{process_id}',
        json={'title': 'Título versão 2'},
    )
    client.post(_url(process_id), json={'values': second_values})

    authenticate(client, bracvam_user)
    second_revision = client.post(
        f'/processes/{process_id}/triage/decision',
        headers={'Origin': 'https://testserver'},
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Ajustar novamente a descrição.',
        },
    )
    assert second_revision.status_code == HTTPStatus.OK

    authenticate(client, owner)
    client.post(
        f'/processes/{process_id}/return-review',
        json={'choice': 'REVISE'},
        headers={'Origin': 'https://testserver'},
    )
    client.patch(
        f'/processes/{process_id}',
        json={'title': 'Título versão 3'},
    )
    client.post(
        _url(process_id), json={'values': {'method_title': 'Método versão 3'}}
    )

    current = client.get(_url(process_id))
    history = client.get(f'/processes/{process_id}/submission-versions')
    detail = client.get(f'/processes/{process_id}/submission-versions/1')

    assert current.status_code == HTTPStatus.OK
    assert current.json()['values']['method_title'] == 'Método versão 3'
    assert history.status_code == HTTPStatus.OK
    assert [item['run_number'] for item in history.json()] == [2, 1]
    assert detail.status_code == HTTPStatus.OK
    assert detail.json()['title'] == 'Título original da proposta'
    assert detail.json()['values'] == first_values
    assert detail.json()['return_justification'] == (
        'Atualizar evidências da proposta.'
    )
    detail_two = client.get(f'/processes/{process_id}/submission-versions/2')
    assert detail_two.status_code == HTTPStatus.OK
    assert detail_two.json()['title'] == 'Título versão 2'
    assert detail_two.json()['values'] == second_values


@pytest.mark.asyncio
async def test_history_is_hidden_from_outsider_and_not_editable(
    client, session, bracvam_user, other_user
):
    owner, process_id = await _draft_context(client, session)
    client.post(_url(process_id), json={'values': {'method_title': 'Enviado'}})
    authenticate(client, bracvam_user)
    decision = client.post(
        f'/processes/{process_id}/triage/decision',
        headers={'Origin': 'https://testserver'},
        json={
            'outcome': 'NEEDS_REVISION',
            'justification': 'Necessita correção.',
        },
    )
    assert decision.status_code == HTTPStatus.OK

    authenticate(client, other_user)
    assert (
        client.get(f'/processes/{process_id}/submission-versions').status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        client.get(
            f'/processes/{process_id}/submission-versions/1'
        ).status_code
        == HTTPStatus.NOT_FOUND
    )
    authenticate(client, owner)
    assert (
        client.patch(
            f'/processes/{process_id}/submission-versions/1',
            json={'title': 'Não permitido'},
        ).status_code
        == HTTPStatus.METHOD_NOT_ALLOWED
    )
