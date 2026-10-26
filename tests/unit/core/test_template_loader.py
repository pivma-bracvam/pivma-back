import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    sync_template_from_dict,
    validate_display_order,
)
from pivma.core.database.models import (
    FormField,
    FormTemplate,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import ValidationError


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
                        'assigned_role': 'proponent',
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
async def test_bootstrap_all_templates_loads_official_processes(session):
    await bootstrap_all_templates(session)

    expected_keys = [
        (
            'pre_validated_method',
            'Método Novo',
            'submission_pre_validated_v1',
        ),
        (
            'validated_method_dossier',
            'Método Novo – Dossiê Completo',
            'submission_validated_dossier_v1',
        ),
        (
            'scope_extension',
            'Extensão do Domínio de Aplicação',
            'submission_scope_extension_v1',
        ),
        ('me_too_validation', 'Método Similar', 'submission_me_too_v1'),
    ]

    for p_key, p_name, f_key in expected_keys:
        stmt = select(ProcessTemplate).where(
            ProcessTemplate.key == p_key,
            ProcessTemplate.deleted_at.is_(None),
            ProcessTemplate.is_active.is_(True),
        )
        pt = (await session.execute(stmt)).scalar_one_or_none()
        assert pt is not None, f'Template {p_key} não encontrado no banco.'
        assert pt.name == p_name

        v_stmt = select(ProcessTemplateVersion).where(
            ProcessTemplateVersion.template_id == pt.id
        )
        versions = (await session.execute(v_stmt)).scalars().all()
        assert len(versions) >= 1

        f_stmt = select(FormTemplate).where(
            FormTemplate.key == f_key,
            FormTemplate.deleted_at.is_(None),
        )
        form = (await session.execute(f_stmt)).scalar_one_or_none()
        assert form is not None, f'Formulário {f_key} não encontrado no banco.'
        assert form.name == f'Formulário de Submissão - {p_name}'

    # Garantir que full_validation não está ativo
    old_stmt = select(ProcessTemplate).where(
        ProcessTemplate.key == 'full_validation',
        ProcessTemplate.deleted_at.is_(None),
        ProcessTemplate.is_active.is_(True),
    )
    old_pt = (await session.execute(old_stmt)).scalar_one_or_none()
    assert old_pt is None


@pytest.mark.parametrize(
    'process_template',
    [
        {'key': 'sem_ordem'},
        {'key': 'sem_ordem', 'display_order': 0},
        {'key': 'sem_ordem', 'display_order': -1},
        {'key': 'sem_ordem', 'display_order': '1'},
        {'key': 'sem_ordem', 'display_order': True},
    ],
)
def test_validate_display_order_refuses_missing_or_invalid_order(
    process_template,
):
    with pytest.raises(ValidationError, match="'sem_ordem'"):
        validate_display_order({'process_template': process_template})


def test_validate_display_order_accepts_positive_integer():
    validate_display_order({
        'process_template': {'key': 'com_ordem', 'display_order': 1}
    })
