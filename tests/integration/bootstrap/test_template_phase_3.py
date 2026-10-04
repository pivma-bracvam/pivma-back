"""Etapa 3 nos cinco templates: recebimento e resolução (Spec 040, FR-017)."""

from pathlib import Path

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import (
    bootstrap_all_templates,
    load_yaml_template,
)
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import (
    instantiate_process,
    validate_execution_scopes,
)
from tests.factories.user_factory import UserFactory

TEMPLATES_DIR = Path(__file__).parents[3] / 'src/pivma/templates_data'
TEMPLATE_FILES = {
    'pre_validated_method': '01_pre_validated_method.yaml',
    'scope_extension': '02_scope_extension.yaml',
    'me_too_validation': '03_me_too_validation.yaml',
    'validated_method_dossier': '04_validated_method_dossier.yaml',
    'proof_of_concept': '05_proof_of_concept.yaml',
}
PHASE_3 = 'phase_3_validation_execution'


def _phase_3(template_key):
    data = load_yaml_template(TEMPLATES_DIR / TEMPLATE_FILES[template_key])
    return next(p for p in data['phases'] if p['key'] == PHASE_3)


def test_all_templates_share_the_same_phase_3():
    reference = _phase_3('validated_method_dossier')
    for key in TEMPLATE_FILES:
        assert _phase_3(key) == reference, key


def test_phase_3_declares_receipt_and_resolution():
    activities = {
        a['key']: a for a in _phase_3('pre_validated_method')['activities']
    }

    receipt = activities['sample_receipt']
    assert receipt['execution_scope'] == 'per_laboratory'
    assert receipt['access']['edit'] == ['participating_laboratory']
    assert [d['required_activity_key'] for d in receipt['dependencies']] == [
        'sample_definition'
    ]

    resolution = activities['sample_receipt_resolution']
    assert resolution['activity_type'] == 'sample_receipt_resolution'
    assert resolution['access']['edit'] == ['sample_selection_group']
    assert resolution['dependencies'] == []


@pytest.mark.parametrize('template_key', list(TEMPLATE_FILES))
def test_phase_3_passes_execution_scope_validation(template_key):
    data = load_yaml_template(TEMPLATES_DIR / TEMPLATE_FILES[template_key])
    validate_execution_scopes(data)


@pytest.mark.asyncio
async def test_new_process_starts_with_resolution_blocked_and_no_run(
    session,
):
    await bootstrap_all_templates(session)
    creator = UserFactory()
    session.add(creator)
    await session.commit()
    version = await session.scalar(
        select(ProcessTemplateVersion)
        .join(
            ProcessTemplate,
            ProcessTemplate.id == ProcessTemplateVersion.template_id,
        )
        .where(ProcessTemplate.key == 'pre_validated_method')
        .order_by(ProcessTemplateVersion.version_number.desc())
        .limit(1)
    )
    process = await instantiate_process(
        session, version, 'Processo', creator.id
    )

    acts = {
        a.key: a
        for a in await session.scalars(
            select(ActivityInstance).where(
                ActivityInstance.process_instance_id == process.id,
                ActivityInstance.key.in_([
                    'sample_receipt',
                    'sample_receipt_resolution',
                ]),
            )
        )
    }
    assert acts['sample_receipt'].status == 'BLOCKED'
    assert acts['sample_receipt'].execution_scope == 'per_laboratory'
    assert acts['sample_receipt_resolution'].status == 'BLOCKED'
    runs = await session.scalar(
        select(ActivityRun.id).where(
            ActivityRun.activity_instance_id
            == acts['sample_receipt_resolution'].id
        )
    )
    assert runs is None
