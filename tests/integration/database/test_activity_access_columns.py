"""Concessões copiadas do template para cada atividade (Spec 030)."""

from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import func, select

import pivma.bootstrap_process_templates as template_bootstrap
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
from pivma.core.process_engine import ValidationError, instantiate_process
from tests.factories.user_factory import UserFactory

TEMPLATES_DIR = Path(template_bootstrap.__file__).parent / 'templates_data'
CANONICAL_TEMPLATE_KEYS = (
    'pre_validated_method',
    'scope_extension',
    'me_too_validation',
    'validated_method_dossier',
    'proof_of_concept',
)


def _minimal_template(access):
    return {
        'process_template': {
            'key': 'access_probe',
            'name': 'Access probe',
            'version': 1,
        },
        'phases': [
            {
                'key': 'phase_1',
                'name': 'Fase 1',
                'order_index': 1,
                'activities': [
                    {
                        'key': 'only_activity',
                        'name': 'Única',
                        'order_index': 1,
                        'assigned_role': 'proponent',
                        'access': access,
                        'dependencies': [],
                    }
                ],
            }
        ],
        'forms': [],
    }


async def _latest_version(session, template_key):
    return await session.scalar(
        select(ProcessTemplateVersion)
        .join(ProcessTemplate)
        .where(ProcessTemplate.key == template_key)
        .order_by(ProcessTemplateVersion.version_number.desc())
        .limit(1)
    )


async def _creator(session):
    user = UserFactory()
    session.add(user)
    await session.commit()
    return user


async def _activities(session, process_id):
    return {
        act.key: act
        for act in await session.scalars(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process_id
            )
        )
    }


@pytest.mark.asyncio
async def test_template_load_rejects_activity_without_edit(session):
    with pytest.raises(ValidationError, match='only_activity') as exc:
        await sync_template_from_dict(session, _minimal_template({'edit': []}))

    assert 'access_probe' in str(exc.value)
    await session.rollback()
    assert (
        await session.scalar(
            select(func.count())
            .select_from(ProcessTemplate)
            .where(ProcessTemplate.key == 'access_probe')
        )
        == 0
    )


@pytest.mark.asyncio
async def test_template_load_rejects_unknown_cargo(session):
    with pytest.raises(ValidationError, match='reviewer_x') as exc:
        await sync_template_from_dict(
            session, _minimal_template({'edit': ['reviewer_x']})
        )

    assert 'access_probe' in str(exc.value)
    assert 'only_activity' in str(exc.value)


@pytest.mark.asyncio
async def test_canonical_templates_instantiate_with_access_on_every_activity(
    session,
):
    await bootstrap_all_templates(session)
    creator = await _creator(session)

    for template_key in CANONICAL_TEMPLATE_KEYS:
        version = await _latest_version(session, template_key)
        process = await instantiate_process(
            session, version, f'Processo {template_key}', creator.id
        )
        activities = await _activities(session, process.id)

        assert activities, template_key
        for key, act in activities.items():
            assert act.edit_roles, (template_key, key)
            assert {'admin', 'bracvam'} <= set(act.view_roles), (
                template_key,
                key,
            )


@pytest.mark.asyncio
async def test_phase1_access_matrix_on_instantiation(session):
    await bootstrap_all_templates(session)
    creator = await _creator(session)
    version = await _latest_version(session, 'pre_validated_method')

    process = await instantiate_process(
        session, version, 'Processo 1', creator.id
    )
    activities = await _activities(session, process.id)

    assert activities['proposal_submission'].edit_roles == ['proponent']
    assert activities['triage_evaluation'].edit_roles == ['bracvam']
    assert 'proponent' not in activities['triage_evaluation'].view_roles


@pytest.mark.asyncio
async def test_template_resync_does_not_change_existing_activity_access(
    session,
):
    data = load_yaml_template(TEMPLATES_DIR / '01_pre_validated_method.yaml')
    await sync_template_from_dict(session, data)
    creator = await _creator(session)
    version = await _latest_version(session, 'pre_validated_method')
    process = await instantiate_process(
        session, version, 'Processo 1', creator.id
    )
    process_id = process.id

    changed = deepcopy(data)
    for phase in changed['phases']:
        for activity in phase['activities']:
            if activity['key'] == 'triage_evaluation':
                activity['access'] = {'edit': ['group_manager'], 'view': []}
    await sync_template_from_dict(session, changed)

    session.expire_all()
    triage = (await _activities(session, process_id))['triage_evaluation']
    assert triage.edit_roles == ['bracvam']
