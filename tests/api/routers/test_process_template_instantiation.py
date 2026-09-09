from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import AccessProfile, UserAccessProfile
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_process_instantiation_reflects_updated_form_template(  # noqa: PLR0914, PLR0915
    client, session
):
    await bootstrap_all_templates(session)

    # 1. Usuário Administrador BraCVAM
    admin = UserFactory()
    session.add(admin)
    admin_prof = AccessProfile(
        system_key='administrator',
        name='Administrador',
        description='RBAC administrator',
    )
    session.add(admin_prof)
    await session.flush()
    session.add(UserAccessProfile(user_id=admin.id, profile_id=admin_prof.id))
    await session.commit()

    # 2. Usuário Proponente
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()

    # 3. Proponente cria Processo Legado ANTES da edição
    authenticate(client, proponent)
    res_p1 = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo Legado 1',
        },
    )
    assert res_p1.status_code == HTTPStatus.CREATED
    p1_id = res_p1.json()['id']

    res_p1_form_before = client.get(
        f'/processes/{p1_id}/activities/proposal_submission/form'
    )
    assert res_p1_form_before.status_code == HTTPStatus.OK
    p1_keys_before = {
        f['field_key'] for f in res_p1_form_before.json()['fields']
    }
    assert 'regulatory_bpl_dossier' not in p1_keys_before

    # 4. BraCVAM Admin customiza o template do formulário
    authenticate(client, admin)
    update_payload = {
        'name': 'Formulário com Novo Campo Regulatório BPL',
        'fields': [
            {
                'field_key': 'method_title',
                'label': 'Título Oficial do Ensaio',
                'field_type': 'text',
                'is_required': True,
                'order_index': 1,
                'section': 'Identificação',
            },
            {
                'field_key': 'regulatory_bpl_dossier',
                'label': 'Dossiê Regulatório BPL Certificado',
                'field_type': 'textarea',
                'help_text': 'Sumário executivo do laudo BPL oficial',
                'is_required': True,
                'order_index': 2,
                'section': 'Conformidade Regulatória',
                'ai_evaluation_enabled': True,
                'ai_context_instructions': (
                    'Verificar credenciamento OECD GLP.'
                ),
            },
        ],
    }
    res_update = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json=update_payload,
    )
    assert res_update.status_code == HTTPStatus.OK

    # 5. Proponente instancia NOVO processo após a edição
    authenticate(client, proponent)
    res_p2 = client.post(
        '/processes',
        json={
            'template_key': 'pre_validated_method',
            'title': 'Processo Novo Pós-Customização',
        },
    )
    assert res_p2.status_code == HTTPStatus.CREATED
    p2_id = res_p2.json()['id']

    # 6. Conferir que o novo processo renderiza o novo campo customizado
    res_p2_form = client.get(
        f'/processes/{p2_id}/activities/proposal_submission/form'
    )
    assert res_p2_form.status_code == HTTPStatus.OK
    p2_fields = res_p2_form.json()['fields']
    p2_keys = {f['field_key']: f for f in p2_fields}

    assert 'regulatory_bpl_dossier' in p2_keys
    custom_field = p2_keys['regulatory_bpl_dossier']
    assert custom_field['label'] == 'Dossiê Regulatório BPL Certificado'
    assert custom_field['is_required'] is True
    assert custom_field['section'] == 'Conformidade Regulatória'
    assert custom_field['ai_evaluation_enabled'] is True

    # 7. Salvar rascunho com o novo campo na nova instância
    bpl_text = 'Dossiê aprovado conforme princípios BPL.'
    res_draft = client.put(
        f'/processes/{p2_id}/activities/proposal_submission/form',
        json={
            'values': {
                'method_title': 'Novo Ensaio Validado 2026',
                'regulatory_bpl_dossier': bpl_text,
            }
        },
    )
    assert res_draft.status_code == HTTPStatus.OK

    res_p2_form_after = client.get(
        f'/processes/{p2_id}/activities/proposal_submission/form'
    )
    assert res_p2_form_after.status_code == HTTPStatus.OK
    assert res_p2_form_after.json()['values']['regulatory_bpl_dossier'] == (
        'Dossiê aprovado conforme princípios BPL.'
    )
