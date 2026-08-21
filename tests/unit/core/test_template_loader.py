import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    sync_template_from_dict,
)
from pivma.core.database.models import (
    FormField,
    FormTemplate,
    ProcessTemplate,
    ProcessTemplateVersion,
)


@pytest.mark.asyncio
async def test_sync_template_from_dict(session):
    sample_data = {
        'process_template': {
            'key': 'test_pipeline',
            'name': 'Pipeline de Teste',
            'description': 'Descrição teste',
            'version': 1,
        },
        'phases': [
            {
                'key': 'phase_1',
                'name': 'Fase 1',
                'order_index': 1,
                'activities': [
                    {
                        'key': 'act_1',
                        'name': 'Atividade 1',
                        'order_index': 1,
                        'assigned_role': 'PROPONENT',
                        'form_template_key': 'form_1',
                        'dependencies': [],
                    }
                ],
            }
        ],
        'forms': [
            {
                'key': 'form_1',
                'name': 'Formulário 1',
                'version': 1,
                'fields': [
                    {
                        'field_key': 'name_field',
                        'label': 'Nome',
                        'field_type': 'text',
                        'is_required': True,
                    }
                ],
            }
        ],
    }

    pt, ptv, forms = await sync_template_from_dict(session, sample_data)

    assert pt.key == 'test_pipeline'
    assert ptv.version_number == 1
    assert len(forms) == 1
    assert forms[0].key == 'form_1'

    # Verify querying DB
    f_res = await session.execute(
        select(FormField).where(FormField.form_template_id == forms[0].id)
    )
    fields = f_res.scalars().all()
    assert len(fields) == 1
    assert fields[0].field_key == 'name_field'


@pytest.mark.asyncio
async def test_bootstrap_all_templates_loads_full_validation(session):
    await bootstrap_all_templates(session)

    stmt = select(ProcessTemplate).where(
        ProcessTemplate.key == 'full_validation'
    )
    pt = (await session.execute(stmt)).scalar_one_or_none()
    assert pt is not None
    assert pt.name == 'Validação Completa'

    v_stmt = select(ProcessTemplateVersion).where(
        ProcessTemplateVersion.template_id == pt.id
    )
    versions = (await session.execute(v_stmt)).scalars().all()
    assert len(versions) >= 1

    f_stmt = select(FormTemplate).where(
        FormTemplate.key == 'submission_full_validation_v1'
    )
    form = (await session.execute(f_stmt)).scalar_one_or_none()
    assert form is not None
