"""Processo com o recebimento de amostras em andamento (Spec 040).

``RECEIPT_TEMPLATE`` junta a atividade de amostras do template mínimo da
Spec 031 à Etapa 3 real dos templates padrão (recebimento por laboratório e
resolução de problemas). As substâncias nascem com faixa de 2 °C a 8 °C.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from pivma.bootstrap_process_templates import load_yaml_template
from pivma.core import sample_service
from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Artifact,
    BlindSampleCode,
    StudySubstance,
)
from tests.factories.participant_factory import grant_cargo
from tests.factories.sample_factory import (
    SAMPLE_TEMPLATE,
    VALID_CAS,
    _user,
    sample_process,
    substance_payload,
)

TEMPLATES_DIR = Path(__file__).parents[2] / 'src/pivma/templates_data'
PHASE_3_KEY = 'phase_3_validation_execution'


def _phase_3() -> dict:
    data = load_yaml_template(TEMPLATES_DIR / '01_pre_validated_method.yaml')
    phase = next(p for p in data['phases'] if p['key'] == PHASE_3_KEY)
    return {**deepcopy(phase), 'order_index': 2}


RECEIPT_TEMPLATE = {
    'process_template': {
        'key': 'sample_receipt_probe',
        'name': 'Recebimento de amostras',
        'version': 1,
    },
    'phases': [SAMPLE_TEMPLATE['phases'][0], _phase_3()],
    'forms': [],
}


def receipt_payload(**overrides) -> dict:
    """Registro em ordem: 4,5 °C, embalagem íntegra, aberto há 1 hora."""
    payload = {
        'opened_at': (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        'temperature_celsius': 4.5,
        'package_state': 'intact',
        'notes': 'Recebido dentro do prazo e com gelo preservado.',
    }
    payload.update(overrides)
    return payload


async def _attach_sds(session, process_id, substance_id) -> None:
    run = await session.scalar(
        select(ActivityRun)
        .join(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityInstance.key == 'sample_definition',
        )
    )
    artifact = Artifact(
        process_instance_id=process_id,
        activity_run_id=run.id,
        key='sample_sds',
        name='sds.pdf',
    )
    session.add(artifact)
    await session.flush()
    substance = await session.get(StudySubstance, substance_id)
    substance.sds_artifact_id = artifact.id
    await session.commit()


async def receipt_process(
    session,
    *,
    lab_count: int = 2,
    substance_count: int = 2,
    reserve: int = 2,
    freeze: bool = True,
    **substance_overrides,
) -> SimpleNamespace:
    """Processo com substâncias, laboratórios, gestor e recebimento aberto.

    Com `freeze`, conclui a definição das amostras: cada laboratório fica
    com uma execução de recebimento em andamento.
    """
    ctx = await sample_process(
        session, lab_count=lab_count, template=RECEIPT_TEMPLATE
    )
    ctx.group_manager = await _user(session)
    await grant_cargo(
        session,
        process_id=ctx.process_id,
        user=ctx.group_manager,
        role_key='group_manager',
    )
    ctx.substances = []
    for index in range(substance_count):
        data = substance_payload(
            chemical_name=f'Substância {index}',
            cas_number=VALID_CAS[index],
            reference_classification='Não irritante',
            storage_temperature_regime='refrigerated',
            storage_temperature_min=2.0,
            storage_temperature_max=8.0,
            reserve_vials_count=reserve,
            ghs_hazard_pictograms=['GHS07'],
        )
        data.update(substance_overrides)
        created = await sample_service.create_substance(
            session, ctx.process_id, ctx.selector.id, data
        )
        await _attach_sds(session, ctx.process_id, created['id'])
        ctx.substances.append(created)
    if freeze:
        await sample_service.complete_sample_definition(
            session, ctx.process_id, ctx.selector.id
        )
    return ctx


async def codes_of(session, ctx, index) -> list[str]:
    """Códigos ativos do laboratório `index`, em ordem alfabética."""
    return sorted(
        await session.scalars(
            select(BlindSampleCode.code).where(
                BlindSampleCode.process_instance_id == ctx.process_id,
                BlindSampleCode.laboratory_id == ctx.labs[index].id,
                BlindSampleCode.deleted_at.is_(None),
            )
        )
    )
