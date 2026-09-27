"""Fase 2 em todos os templates e atividade de amostras (Spec 031, US6)."""

import copy
from pathlib import Path

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    load_yaml_template,
    sync_template_from_dict,
)
from pivma.core.database.models import (
    ActivityInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import instantiate_process
from tests.factories.user_factory import UserFactory

TEMPLATES_DIR = Path(__file__).parents[3] / 'src/pivma/templates_data'
TEMPLATE_FILES = {
    'pre_validated_method': '01_pre_validated_method.yaml',
    'scope_extension': '02_scope_extension.yaml',
    'me_too_validation': '03_me_too_validation.yaml',
    'validated_method_dossier': '04_validated_method_dossier.yaml',
    'proof_of_concept': '05_proof_of_concept.yaml',
}
NEW_VERSIONS = {
    'pre_validated_method': 3,
    'scope_extension': 3,
    'me_too_validation': 3,
    'validated_method_dossier': 5,
    'proof_of_concept': 3,
}
PHASE_2 = 'phase_2_role_assignment'
COMPARED_KEYS = (
    'key',
    'assigned_role',
    'access',
    'activity_type',
    'target_role_key',
    'dependencies',
)


def _template(key):
    return load_yaml_template(TEMPLATES_DIR / TEMPLATE_FILES[key])


def _phase_2(data):
    return next(p for p in data['phases'] if p['key'] == PHASE_2)


def _assign_activities(data):
    return {
        a['key']: {k: a.get(k) for k in COMPARED_KEYS}
        for a in _phase_2(data)['activities']
        if a['key'].startswith('assign_')
    }


def test_all_templates_share_the_same_phase_2_role_assignments():
    reference = _assign_activities(_template('validated_method_dossier'))
    assert len(reference) == 8  # noqa: PLR2004 (as oito atribuições)

    for key in TEMPLATE_FILES:
        assert _assign_activities(_template(key)) == reference, key


@pytest.mark.parametrize('template_key', list(TEMPLATE_FILES))
def test_all_templates_declare_sample_definition_in_phase_2(template_key):
    activities = {
        a['key']: a for a in _phase_2(_template(template_key))['activities']
    }

    sample = activities['sample_definition']
    assert sample['activity_type'] == 'sample_definition'
    assert sample['assigned_role'] == 'sample_selection_group'
    assert sample['access'] == {
        'edit': ['sample_selection_group'],
        'view': [],
    }
    assert sorted(
        (
            d['required_activity_key'],
            d['required_status'],
            d['condition_type'],
        )
        for d in sample['dependencies']
    ) == [
        (
            'assign_participating_laboratory',
            'COMPLETED',
            'ACTIVITY_COMPLETED',
        ),
        ('assign_sample_selection_group', 'COMPLETED', 'ACTIVITY_COMPLETED'),
    ]


async def _creator(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _latest_version(session, template_key):
    return await session.scalar(
        select(ProcessTemplateVersion)
        .join(
            ProcessTemplate,
            ProcessTemplate.id == ProcessTemplateVersion.template_id,
        )
        .where(ProcessTemplate.key == template_key)
        .order_by(ProcessTemplateVersion.version_number.desc())
        .limit(1)
    )


@pytest.mark.asyncio
async def test_sample_definition_instantiates_with_edit_only_for_sample_group(
    session,
):
    await bootstrap_all_templates(session)
    creator = await _creator(session)

    for template_key in TEMPLATE_FILES:
        version = await _latest_version(session, template_key)
        process = await instantiate_process(
            session, version, f'Processo {template_key}', creator.id
        )
        act = await session.scalar(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process.id,
                ActivityInstance.key == 'sample_definition',
            )
        )
        assert act.status == 'BLOCKED', template_key
        assert act.edit_roles == ['sample_selection_group']
        assert act.view_roles == ['admin', 'bracvam', 'sample_selection_group']


def _previous_version(template_key):
    data = copy.deepcopy(_template(template_key))
    data['process_template']['version'] = NEW_VERSIONS[template_key] - 1
    data['phases'] = [p for p in data['phases'] if p['key'] != PHASE_2]
    return data


@pytest.mark.asyncio
async def test_bootstrap_publishes_new_versions_and_keeps_previous(session):
    for template_key in TEMPLATE_FILES:
        await sync_template_from_dict(session, _previous_version(template_key))

    await bootstrap_all_templates(session)

    for template_key, new_version in NEW_VERSIONS.items():
        versions = {
            v.version_number: v
            for v in await session.scalars(
                select(ProcessTemplateVersion)
                .join(
                    ProcessTemplate,
                    ProcessTemplate.id == ProcessTemplateVersion.template_id,
                )
                .where(ProcessTemplate.key == template_key)
            )
        }
        assert new_version in versions, template_key
        previous = versions[new_version - 1]
        assert previous.deleted_at is None
        assert PHASE_2 not in {
            p['key'] for p in previous.definition_payload['phases']
        }


@pytest.mark.asyncio
async def test_existing_process_keeps_its_template_version_structure(
    session,
):
    _, old_version, _ = await sync_template_from_dict(
        session, _previous_version('pre_validated_method')
    )
    creator = await _creator(session)
    process = await instantiate_process(
        session, old_version, 'Processo antigo', creator.id
    )

    await bootstrap_all_templates(session)

    keys = set(
        await session.scalars(
            select(ActivityInstance.key).where(
                ActivityInstance.process_instance_id == process.id
            )
        )
    )
    assert 'sample_definition' not in keys
    assert not any(key.startswith('assign_') for key in keys)
