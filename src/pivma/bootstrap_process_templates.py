import asyncio
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from pivma.core.database.models import (
    FormField,
    FormTemplate,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.settings import get_settings


def load_yaml_template(file_path: Path | str) -> dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def _sync_form_fields(
    session: AsyncSession,
    form_template_id: Any,
    fields_data: list[dict[str, Any]],
) -> None:
    for fld in fields_data:
        field_stmt = select(FormField).where(
            FormField.form_template_id == form_template_id,
            FormField.field_key == fld['field_key'],
            FormField.deleted_at.is_(None),
        )
        f_res = await session.execute(field_stmt)
        field = f_res.scalar_one_or_none()

        if field is None:
            field = FormField(
                form_template_id=form_template_id,
                field_key=fld['field_key'],
                label=fld['label'],
                field_type=fld['field_type'],
                help_text=fld.get('help_text'),
                is_required=fld.get('is_required', False),
                order_index=fld.get('order_index', 0),
                options=fld.get('options'),
                validation_rules=fld.get('validation_rules'),
            )
            session.add(field)
        else:
            field.label = fld['label']
            field.field_type = fld['field_type']
            field.help_text = fld.get('help_text')
            field.is_required = fld.get('is_required', False)
            field.order_index = fld.get('order_index', 0)
            field.options = fld.get('options')
            field.validation_rules = fld.get('validation_rules')


async def _sync_forms(
    session: AsyncSession, forms_data: list[dict[str, Any]]
) -> list[FormTemplate]:
    synced = []
    for f_data in forms_data:
        f_key = f_data['key']
        stmt = select(FormTemplate).where(
            FormTemplate.key == f_key, FormTemplate.deleted_at.is_(None)
        )
        res = await session.execute(stmt)
        form = res.scalar_one_or_none()

        if form is None:
            form = FormTemplate(
                key=f_key,
                name=f_data['name'],
                version=f_data.get('version', 1),
                description=f_data.get('description'),
            )
            session.add(form)
            await session.flush()
        else:
            form.name = f_data['name']
            form.version = f_data.get('version', 1)
            form.description = f_data.get('description')

        await _sync_form_fields(session, form.id, f_data.get('fields', []))
        synced.append(form)
    return synced


async def _sync_process_template_and_version(
    session: AsyncSession, data: dict[str, Any]
) -> tuple[ProcessTemplate, ProcessTemplateVersion]:
    pt_data = data['process_template']
    p_key = pt_data['key']
    stmt = select(ProcessTemplate).where(
        ProcessTemplate.key == p_key, ProcessTemplate.deleted_at.is_(None)
    )
    res = await session.execute(stmt)
    process_template = res.scalar_one_or_none()

    if process_template is None:
        process_template = ProcessTemplate(
            key=p_key,
            name=pt_data['name'],
            description=pt_data.get('description'),
            is_active=pt_data.get('is_active', True),
        )
        session.add(process_template)
        await session.flush()
    else:
        process_template.name = pt_data['name']
        process_template.description = pt_data.get('description')
        process_template.is_active = pt_data.get('is_active', True)

    version_num = pt_data.get('version', 1)
    v_stmt = select(ProcessTemplateVersion).where(
        ProcessTemplateVersion.template_id == process_template.id,
        ProcessTemplateVersion.version_number == version_num,
        ProcessTemplateVersion.deleted_at.is_(None),
    )
    v_res = await session.execute(v_stmt)
    version = v_res.scalar_one_or_none()

    if version is None:
        version = ProcessTemplateVersion(
            template_id=process_template.id,
            version_number=version_num,
            definition_payload=data,
            is_published=True,
        )
        session.add(version)
        await session.flush()
    else:
        version.definition_payload = data

    return process_template, version


async def sync_template_from_dict(
    session: AsyncSession, data: dict[str, Any]
) -> tuple[ProcessTemplate, ProcessTemplateVersion, list[FormTemplate]]:
    synced_forms = await _sync_forms(session, data.get('forms', []))
    process_template, version = await _sync_process_template_and_version(
        session, data
    )
    await session.commit()
    return process_template, version, synced_forms


async def bootstrap_all_templates(session: AsyncSession) -> None:
    templates_dir = Path(__file__).parent / 'templates_data'
    if not templates_dir.exists():
        return

    for yaml_file in templates_dir.glob('*.yaml'):
        data = load_yaml_template(yaml_file)
        await sync_template_from_dict(session, data)


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        await bootstrap_all_templates(session)
    await engine.dispose()
    print('Process templates bootstrap completed successfully.')


if __name__ == '__main__':
    asyncio.run(main())
