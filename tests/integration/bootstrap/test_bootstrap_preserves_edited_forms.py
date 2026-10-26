"""O bootstrap preserva o formulário que o editor alterou.

Regra: quando a versão do formulário no banco é maior que a do YAML, o
bootstrap não mexe nele nem na entrada dele na definição da versão do
template. Subir a `version` no YAML acima da do banco faz o YAML prevalecer.
"""

import pytest
from sqlalchemy import select

from pivma import bootstrap_process_templates
from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    EvaluationAssignment,
    FormField,
    FormTemplate,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import update_form_template_definition
from tests.factories.evaluation_factory import EvaluationDefinitionFactory

TEMPLATE = 'pre_validated_method'
SUBMISSION = 'submission_pre_validated_v1'
PLAN = 'statistical_plan_v1'


async def _edit(session, form_key, fields, user_id, name=None):
    await update_form_template_definition(
        session, TEMPLATE, form_key, fields, user_id, name=name
    )


def _yaml_changing_form(monkeypatch, form_key, change):
    """Faz o bootstrap ler o YAML do Método Novo com `change` aplicado ao
    formulário `form_key`."""
    load = bootstrap_process_templates.load_yaml_template

    def load_changed(file_path):
        data = load(file_path)
        for form in data.get('forms', []):
            if form['key'] == form_key:
                change(form)
        return data

    monkeypatch.setattr(
        bootstrap_process_templates, 'load_yaml_template', load_changed
    )


async def _form(session, form_key):
    return await session.scalar(
        select(FormTemplate)
        .where(FormTemplate.key == form_key)
        .execution_options(populate_existing=True)
    )


async def _active_fields(session, form_key):
    form = await _form(session, form_key)
    fields = await session.scalars(
        select(FormField)
        .where(
            FormField.form_template_id == form.id,
            FormField.deleted_at.is_(None),
        )
        .execution_options(populate_existing=True)
    )
    return {field.field_key: field for field in fields}


async def _payload_form(session, form_key):
    version = await session.scalar(
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(ProcessTemplate.key == TEMPLATE)
        .execution_options(populate_existing=True)
    )
    return next(
        form
        for form in version.definition_payload['forms']
        if form['key'] == form_key
    )


@pytest.mark.asyncio
async def test_formulario_editado_mantem_o_campo_removido_fora(session, user):
    await bootstrap_all_templates(session)
    await _edit(
        session,
        PLAN,
        [
            {
                'field_key': 'plan_file',
                'label': 'Plano estatístico',
                'field_type': 'file',
                'is_required': True,
            }
        ],
        user.id,
    )

    await bootstrap_all_templates(session)

    assert set(await _active_fields(session, PLAN)) == {'plan_file'}
    assert [
        field['field_key']
        for field in (await _payload_form(session, PLAN))['fields']
    ] == ['plan_file']


@pytest.mark.asyncio
async def test_formulario_nao_editado_segue_o_yaml(session, user, monkeypatch):
    await bootstrap_all_templates(session)
    await _edit(
        session,
        SUBMISSION,
        [{'field_key': 'method_title', 'label': 'Nome do método'}],
        user.id,
    )

    def rename_summary(form):
        form['fields'][1]['label'] = 'Resumo (YAML novo)'

    _yaml_changing_form(monkeypatch, PLAN, rename_summary)
    await bootstrap_all_templates(session)

    plan_fields = await _active_fields(session, PLAN)
    assert plan_fields['summary'].label == 'Resumo (YAML novo)'
    payload_summary = (await _payload_form(session, PLAN))['fields'][1]
    assert payload_summary['label'] == 'Resumo (YAML novo)'
    submission_fields = await _active_fields(session, SUBMISSION)
    assert submission_fields['method_title'].label == 'Nome do método'


@pytest.mark.asyncio
async def test_yaml_com_versao_maior_prevalece_sobre_a_edicao(
    session, user, monkeypatch
):
    await bootstrap_all_templates(session)
    await _edit(
        session,
        SUBMISSION,
        [
            {'field_key': 'method_title', 'label': 'Nome do método'},
            {'field_key': 'extra_notes', 'label': 'Observações'},
        ],
        user.id,
        name='Formulário editado',
    )
    edited = await _form(session, SUBMISSION)
    assert edited.version == 2  # noqa: PLR2004

    def bump_version(form):
        form['version'] = 3

    _yaml_changing_form(monkeypatch, SUBMISSION, bump_version)
    await bootstrap_all_templates(session)

    form = await _form(session, SUBMISSION)
    assert (form.name, form.version) == (
        'Formulário de Submissão - Método Novo',
        3,
    )
    fields = await _active_fields(session, SUBMISSION)
    assert set(fields) == {'method_title'}
    assert fields['method_title'].label == 'Título do método'
    payload = await _payload_form(session, SUBMISSION)
    assert [field['field_key'] for field in payload['fields']] == [
        'method_title'
    ]


@pytest.mark.asyncio
async def test_yaml_que_prevalece_desativa_avaliacao_do_campo_removido(
    session, user, monkeypatch
):
    await bootstrap_all_templates(session)
    await _edit(
        session,
        SUBMISSION,
        [
            {'field_key': 'method_title', 'label': 'Nome do método'},
            {'field_key': 'extra_notes', 'label': 'Observações'},
        ],
        user.id,
    )
    definition = EvaluationDefinitionFactory()
    session.add(definition)
    await session.flush()
    assignment = EvaluationAssignment(
        form_template_id=(await _form(session, SUBMISSION)).id,
        definition_id=definition.id,
        target_type='field',
        field_keys=['extra_notes'],
    )
    session.add(assignment)
    await session.commit()

    def bump_version(form):
        form['version'] = 3

    _yaml_changing_form(monkeypatch, SUBMISSION, bump_version)
    await bootstrap_all_templates(session)

    assignment = await session.scalar(
        select(EvaluationAssignment)
        .where(EvaluationAssignment.id == assignment.id)
        .execution_options(
            skip_soft_delete_filter=True, populate_existing=True
        )
    )
    assert assignment.field_keys == []
    assert assignment.deleted_at is not None
