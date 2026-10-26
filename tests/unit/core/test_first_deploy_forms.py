"""Forma dos formulários de submissão do baseline de primeiro deploy.

Spec 015, 020 e 043. Valida o bootstrap dos quatro templates de processo:
formulários 1-3 mínimos e formulário 4 com campo de IA. A triagem foi
desacoplada de formulário próprio.
"""

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import FormField, FormTemplate


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
async def test_triage_form_deactivated_and_submission_forms_active(
    session,
):
    await bootstrap_all_templates(session)

    active_forms = (
        (
            await session.execute(
                select(FormTemplate).where(FormTemplate.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )

    active_keys = {f.key for f in active_forms}
    assert 'triage_review_v1' not in active_keys
    assert active_keys == {
        'submission_pre_validated_v1',
        'submission_scope_extension_v1',
        'submission_me_too_v1',
        'submission_validated_dossier_v1',
        'statistical_plan_v1',
    }
