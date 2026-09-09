import pytest
from uuid import uuid4

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.process_engine import (
    NotFoundError,
    ValidationError,
    update_form_template_definition,
)


from tests.factories.user_factory import UserFactory


@pytest.mark.asyncio
async def test_update_form_template_sync_and_validation(session):
    await bootstrap_all_templates(session)
    user = UserFactory()
    session.add(user)
    await session.commit()
    user_id = user.id

    # 1. Sucesso na atualização
    fields_data = [
        {
            'field_key': 'new_protocol_field',
            'label': 'Novo Protocolo',
            'field_type': 'text',
            'is_required': True,
            'order_index': 1,
            'section': 'Dados Básicos',
        },
        {
            'field_key': 'study_protocol_file',
            'label': 'Protocolo em PDF',
            'field_type': 'file_upload',
            'is_required': False,
            'order_index': 2,
            'section': 'Anexos',
        },
    ]
    template, fields = await update_form_template_definition(
        session=session,
        process_template_key='pre_validated_method',
        form_template_key='submission_pre_validated_v1',
        fields_data=fields_data,
        user_id=user_id,
        name='Formulário Atualizado Teste',
        description='Descrição atualizada',
    )

    assert template.name == 'Formulário Atualizado Teste'
    assert len(fields) == 2
    f_map = {f.field_key: f for f in fields}
    assert 'new_protocol_field' in f_map
    assert f_map['new_protocol_field'].validation_rules.get('section') == 'Dados Básicos'

    # 2. Erro de chaves duplicadas
    with pytest.raises(ValidationError, match='duplicadas'):
        await update_form_template_definition(
            session=session,
            process_template_key='pre_validated_method',
            form_template_key='submission_pre_validated_v1',
            fields_data=[
                {'field_key': 'dup', 'label': 'A'},
                {'field_key': 'dup', 'label': 'B'},
            ],
            user_id=user_id,
        )

    # 3. Erro de template de processo inexistente
    with pytest.raises(NotFoundError, match='Template de processo'):
        await update_form_template_definition(
            session=session,
            process_template_key='non_existent_key',
            form_template_key='submission_pre_validated_v1',
            fields_data=fields_data,
            user_id=user_id,
        )
