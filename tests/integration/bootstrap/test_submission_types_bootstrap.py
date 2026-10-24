"""Bootstrap dos tipos de submissão (Spec 043): ordem obrigatória e saída
da Prova de Conceito."""

import pytest
from sqlalchemy import func, select

from pivma import bootstrap_process_templates
from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    sync_template_from_dict,
)
from pivma.core.database.models import FormTemplate, ProcessTemplate
from pivma.core.process_engine import ValidationError

PROOF_OF_CONCEPT = {
    'process_template': {
        'key': 'proof_of_concept',
        'name': 'Prova de Conceito (PoC)',
        'version': 1,
    },
    'phases': [{'key': 'phase_1', 'name': 'Fase 1', 'order_index': 1}],
    'forms': [
        {
            'key': 'submission_proof_of_concept_v1',
            'name': 'Formulário Preliminar',
            'version': 1,
            'fields': [
                {
                    'field_key': 'method_title',
                    'label': 'Título',
                    'field_type': 'text',
                }
            ],
        }
    ],
}


async def _including_deleted(session, statement):
    return await session.scalar(
        statement.execution_options(skip_soft_delete_filter=True)
    )


@pytest.mark.asyncio
async def test_bootstrap_deactivates_existing_proof_of_concept(session):
    await sync_template_from_dict(session, PROOF_OF_CONCEPT)

    await bootstrap_all_templates(session)

    template = await _including_deleted(
        session,
        select(ProcessTemplate).where(
            ProcessTemplate.key == 'proof_of_concept'
        ),
    )
    assert template.is_active is False
    assert template.deleted_at is not None


@pytest.mark.asyncio
async def test_bootstrap_deletes_existing_proof_of_concept_form(session):
    await sync_template_from_dict(session, PROOF_OF_CONCEPT)

    await bootstrap_all_templates(session)

    form = await _including_deleted(
        session,
        select(FormTemplate).where(
            FormTemplate.key == 'submission_proof_of_concept_v1'
        ),
    )
    assert form.deleted_at is not None


@pytest.mark.asyncio
async def test_bootstrap_records_display_order_of_the_four_types(session):
    await bootstrap_all_templates(session)

    rows = await session.execute(
        select(ProcessTemplate.key, ProcessTemplate.display_order)
        .where(ProcessTemplate.deleted_at.is_(None))
        .order_by(ProcessTemplate.display_order)
    )
    assert rows.all() == [
        ('pre_validated_method', 1),
        ('validated_method_dossier', 2),
        ('scope_extension', 3),
        ('me_too_validation', 4),
    ]


@pytest.mark.asyncio
async def test_bootstrap_refuses_yaml_without_order_and_records_nothing(
    session, monkeypatch
):
    load = bootstrap_process_templates.load_yaml_template

    def load_without_order(file_path):
        data = load(file_path)
        if data['process_template']['key'] == 'me_too_validation':
            del data['process_template']['display_order']
        return data

    monkeypatch.setattr(
        bootstrap_process_templates, 'load_yaml_template', load_without_order
    )

    with pytest.raises(ValidationError, match="'me_too_validation'"):
        await bootstrap_all_templates(session)

    # Os YAMLs lidos antes do inválido também não foram gravados.
    assert await session.scalar(select(func.count(ProcessTemplate.id))) == 0
