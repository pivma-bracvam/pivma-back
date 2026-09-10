"""Forma dos formulários de submissão do baseline de primeiro deploy.

Spec 015. Valida o bootstrap declarativo dos cinco templates de processo:
formulários 1-3 mínimos, formulário 4 com campo de IA e formulário 5 (FP)
cobrindo as nove seções. O formulário de triagem permanece intocado.
"""

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import FormField, FormTemplate

FP_SECTION_COUNT = 9


async def _fields(session, form_key: str) -> list[FormField]:
    form = (
        await session.execute(
            select(FormTemplate).where(
                FormTemplate.key == form_key,
                FormTemplate.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    return list(
        await session.scalars(
            select(FormField)
            .where(
                FormField.form_template_id == form.id,
                FormField.deleted_at.is_(None),
            )
            .order_by(FormField.order_index)
        )
    )


@pytest.mark.parametrize(
    'form_key',
    [
        'submission_pre_validated_v1',
        'submission_scope_extension_v1',
        'submission_me_too_v1',
    ],
)
@pytest.mark.asyncio
async def test_simple_forms_have_single_required_method_title(
    session, form_key
):
    await bootstrap_all_templates(session)

    fields = await _fields(session, form_key)

    assert len(fields) == 1
    assert fields[0].field_key == 'method_title'
    assert fields[0].field_type == 'text'
    assert fields[0].is_required is True


@pytest.mark.asyncio
async def test_dossier_form_exposes_ai_terminology_field(session):
    await bootstrap_all_templates(session)

    fields = {
        f.field_key: f
        for f in await _fields(session, 'submission_validated_dossier_v1')
    }

    assert set(fields) == {'method_title', 'terminology_notes'}
    ai_field = fields['terminology_notes']
    assert ai_field.field_type == 'textarea'
    assert ai_field.ai_evaluation_enabled is True
    assert ai_field.ai_context_instructions
    assert ai_field.is_required is True


@pytest.mark.asyncio
async def test_preliminary_form_covers_all_nine_sections(session):
    await bootstrap_all_templates(session)

    fields = await _fields(session, 'submission_proof_of_concept_v1')

    sections = [(f.validation_rules or {}).get('section') for f in fields]
    assert None not in sections, 'todo campo do FP deve declarar uma seção'
    assert len(set(sections)) == FP_SECTION_COUNT

    keys = {f.field_key for f in fields}
    # elementos representativos de seções distintas
    for expected in (
        'proponent_organization',
        'method_name',
        'mechanistic_relevance',
        'protocol_stepwise_described',
        'within_lab_reproducibility',
        'predictions_possible',
        'bibliographic_references',
        'contains_confidential',
        'bracvam_validation_request',
    ):
        assert expected in keys

    required = {f.field_key for f in fields if f.is_required}
    assert required == {
        'proponent_organization',
        'contact_first_name',
        'contact_last_name',
        'contact_email',
        'method_name',
    }

    sop = next(f for f in fields if f.field_key == 'sop_files')
    assert sop.field_type == 'file_upload'
    assert (sop.validation_rules or {}).get('allowed_extensions') == ['pdf']


@pytest.mark.parametrize(
    'form_key',
    [
        'submission_pre_validated_v1',
        'submission_scope_extension_v1',
        'submission_me_too_v1',
        'submission_validated_dossier_v1',
        'submission_proof_of_concept_v1',
    ],
)
@pytest.mark.asyncio
async def test_triage_review_form_is_untouched(session, form_key):
    await bootstrap_all_templates(session)

    fields = {f.field_key for f in await _fields(session, 'triage_review_v1')}

    assert fields == {'regulatory_adherence_score', 'triage_summary_notes'}
