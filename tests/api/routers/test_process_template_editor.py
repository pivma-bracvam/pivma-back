from http import HTTPStatus

import pytest

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    AccessProfile,
    AccessProfilePermission,
    Permission,
    UserAccessProfile,
)
from tests.api.routers.test_rbac_router import authenticate
from tests.factories.user_factory import UserFactory


async def _user_with_profile(
    session, *, system_key=None, name='Perfil de Teste', permission_code=None
):
    """Cria um usuário com um perfil de acesso customizado (Issue #39).

    `permission_code`, quando informado, concede essa única permissão ao
    perfil — usado para reproduzir cenários de escalada de privilégio
    (`rbac.read`) e o caminho legítimo novo (`form_templates.manage`).
    """
    user = UserFactory()
    session.add(user)
    profile = AccessProfile(
        system_key=system_key, name=name, description='Perfil de teste'
    )
    session.add(profile)
    await session.flush()
    if permission_code is not None:
        permission = Permission(
            code=permission_code, description=f'Permissão {permission_code}'
        )
        session.add(permission)
        await session.flush()
        session.add(
            AccessProfilePermission(
                profile_id=profile.id, permission_id=permission.id
            )
        )
    session.add(UserAccessProfile(user_id=user.id, profile_id=profile.id))
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_get_and_update_form_template_definition(  # noqa: PLR0914, PLR0915
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

    # 2. Usuário Proponente comum (sem perfil de admin)
    proponent = UserFactory()
    session.add(proponent)
    await session.commit()

    # 3. GET /processes/templates/{key}/forms/{form_key} com autenticação
    authenticate(client, admin)
    res_get = client.get(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1'
    )
    assert res_get.status_code == HTTPStatus.OK
    data = res_get.json()
    assert data['key'] == 'submission_pre_validated_v1'
    assert len(data['fields']) > 0

    # 4. Proponente comum tenta fazer PUT -> deve receber 403 Forbidden
    authenticate(client, proponent)
    update_payload = {
        'name': 'Formulário Editado pelo Proponente (Ilegal)',
        'fields': [
            {
                'field_key': 'custom_field_1',
                'label': 'Campo Customizado',
                'field_type': 'text',
                'is_required': True,
                'section': 'Identificação',
            }
        ],
    }
    res_forbidden = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json=update_payload,
    )
    assert res_forbidden.status_code == HTTPStatus.FORBIDDEN

    # 5. Admin BraCVAM faz PUT com campos válidos -> 200 OK
    authenticate(client, admin)
    valid_update_payload = {
        'name': 'Formulário de Submissão Customizado v2',
        'description': 'Atualizado com novo campo regulatório BPL',
        'fields': [
            {
                'field_key': 'method_title',
                'label': 'Título Oficial do Método',
                'field_type': 'text',
                'is_required': True,
                'order_index': 1,
                'section': 'Identificação Geral',
            },
            {
                'field_key': 'glp_audit_dossier',
                'label': 'Dossiê de Auditoria BPL',
                'field_type': 'file_upload',
                'is_required': True,
                'order_index': 2,
                'section': 'Conformidade Regulatória',
                'ai_evaluation_enabled': True,
                'ai_context_instructions': (
                    'Verificar carimbo de auditor BPL credenciado.'
                ),
            },
        ],
    }
    res_put = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json=valid_update_payload,
    )
    assert res_put.status_code == HTTPStatus.OK
    saved = res_put.json()
    assert saved['name'] == 'Formulário de Submissão Customizado v2'
    expected_fields_count = 2
    assert len(saved['fields']) == expected_fields_count
    f_keys = [f['field_key'] for f in saved['fields']]
    assert 'method_title' in f_keys
    assert 'glp_audit_dossier' in f_keys

    # 6. Validar que GET agora reflete os novos campos salvos
    res_get_updated = client.get(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1'
    )
    assert res_get_updated.status_code == HTTPStatus.OK
    updated_data = res_get_updated.json()
    assert len(updated_data['fields']) == expected_fields_count

    # 7. Validar erro 422 para chaves duplicadas
    dup_payload = {
        'fields': [
            {
                'field_key': 'duplicate_key',
                'label': 'Campo 1',
                'field_type': 'text',
            },
            {
                'field_key': 'duplicate_key',
                'label': 'Campo 2',
                'field_type': 'text',
            },
        ]
    }
    res_dup = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json=dup_payload,
    )
    assert res_dup.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # 8. Validar 404 para template inexistente
    res_404 = client.get(
        '/processes/templates/inexistente/forms/submission_pre_validated_v1'
    )
    assert res_404.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_rbac_read_only_cannot_update_form_template(client, session):
    """Issue #39: `rbac.read` é permissão de leitura do RBAC, não prova de

    administrador — não deve autorizar edição de template.
    """
    await bootstrap_all_templates(session)
    user = await _user_with_profile(
        session, name='Consulta RBAC', permission_code='rbac.read'
    )
    authenticate(client, user)

    res = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json={'fields': []},
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_profile_named_administrador_without_system_key_cannot_update(
    client, session
):
    """Issue #39: o nome de exibição do perfil é texto livre — só

    `system_key == 'administrator'` prova que o perfil é o Administrador
    oficial.
    """
    await bootstrap_all_templates(session)
    user = await _user_with_profile(
        session, system_key=None, name='Administrador'
    )
    authenticate(client, user)

    res = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json={'fields': []},
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_form_templates_manage_permission_can_update(client, session):
    """Issue #39 (pós-clarify): a permissão discreta `form_templates.manage`

    é o caminho legítimo para o BraCVAM editar formulários — precisa
    autorizar mesmo sem `system_key == 'administrator'`.
    """
    await bootstrap_all_templates(session)
    user = await _user_with_profile(
        session,
        name='Equipe BraCVAM (teste)',
        permission_code='form_templates.manage',
    )
    authenticate(client, user)

    res = client.put(
        '/processes/templates/pre_validated_method/forms/submission_pre_validated_v1',
        json={
            'name': 'Formulário Editado pelo BraCVAM',
            'fields': [
                {
                    'field_key': 'method_title',
                    'label': 'Título do Método',
                    'field_type': 'text',
                    'is_required': True,
                }
            ],
        },
    )
    assert res.status_code == HTTPStatus.OK
    assert res.json()['name'] == 'Formulário Editado pelo BraCVAM'
