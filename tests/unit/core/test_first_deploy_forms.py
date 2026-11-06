"""Forma dos formulários de submissão do baseline de primeiro deploy.

Valida o bootstrap dos formulários oficiais do BraCVAM nos quatro templates
de processo. A triagem foi desacoplada de formulário próprio.
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


REQUIRED_FIELDS = {
    'institution_name',
    'institution_nature',
    'proposal_owner',
    'owner_position',
    'contact_email',
    'contact_phone',
    'country',
    'method_title',
    'method_kind',
    'application_area',
    'method_description',
    'submission_objective',
}


@pytest.mark.parametrize(
    ('form_key', 'field_count'),
    [
        ('submission_pre_validated_v1', 56),
        ('submission_scope_extension_v1', 56),
        ('submission_me_too_v1', 56),
        ('submission_validated_dossier_v1', 64),
    ],
)
@pytest.mark.asyncio
async def test_official_form_declares_its_fields_and_required_ones(
    session, form_key, field_count
):
    await bootstrap_all_templates(session)

    fields = await _fields(session, form_key)

    assert len(fields) == field_count
    assert {f.field_key for f in fields if f.is_required} == REQUIRED_FIELDS
    assert not any(
        f.is_required for f in fields if f.field_type == 'file_upload'
    )
    assert all(f.validation_rules.get('section') for f in fields)
    assert [f.order_index for f in fields] == list(range(1, field_count + 1))


@pytest.mark.asyncio
async def test_official_forms_share_the_same_questions(session):
    await bootstrap_all_templates(session)

    def shape(fields):
        return [
            (f.field_key, f.label, f.field_type, f.is_required, f.options)
            for f in fields
        ]

    base = shape(await _fields(session, 'submission_pre_validated_v1'))
    extension = await _fields(session, 'submission_scope_extension_v1')
    similar = await _fields(session, 'submission_me_too_v1')
    dossier = await _fields(session, 'submission_validated_dossier_v1')

    assert shape(extension) == base
    assert shape(similar) == base
    assert shape(dossier)[: len(base)] == base


@pytest.mark.asyncio
async def test_only_dossier_description_accepts_ai_evaluation(session):
    await bootstrap_all_templates(session)

    dossier = await _fields(session, 'submission_validated_dossier_v1')
    method_new = await _fields(session, 'submission_pre_validated_v1')

    assert [f.field_key for f in dossier if f.ai_evaluation_enabled] == [
        'method_description'
    ]
    assert not any(f.ai_evaluation_enabled for f in method_new)


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
