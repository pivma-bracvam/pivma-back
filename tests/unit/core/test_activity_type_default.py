"""Spec 017 - default retrocompatível de ActivityInstance.activity_type."""

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import sync_template_from_dict
from pivma.core.database.models import ActivityInstance
from pivma.core.process_engine import instantiate_process
from tests.factories.user_factory import UserFactory

SAMPLE_TEMPLATE = {
    'process_template': {
        'key': 'activity_type_sample',
        'name': 'Pipeline de Teste de Tipos',
        'description': 'Descrição teste',
        'version': 1,
    },
    'phases': [
        {
            'key': 'phase_1',
            'name': 'Fase 1',
            'order_index': 1,
            'activities': [
                {
                    'key': 'legacy_activity',
                    'name': 'Atividade sem tipo declarado',
                    'order_index': 1,
                    'assigned_role': 'PROPONENT',
                    'form_template_key': 'form_1',
                    'dependencies': [],
                },
                {
                    'key': 'typed_activity',
                    'name': 'Atividade com tipo declarado',
                    'order_index': 2,
                    'assigned_role': 'BRACVAM_ADMIN',
                    'activity_type': 'decision',
                    'dependencies': [],
                },
            ],
        }
    ],
    'forms': [
        {
            'key': 'form_1',
            'name': 'Formulário 1',
            'version': 1,
            'fields': [
                {
                    'field_key': 'name_field',
                    'label': 'Nome',
                    'field_type': 'text',
                    'is_required': True,
                }
            ],
        }
    ],
}


@pytest.mark.asyncio
async def test_activity_defaults_to_form_when_type_is_omitted(session):
    _pt, ptv, _forms = await sync_template_from_dict(session, SAMPLE_TEMPLATE)
    user = UserFactory()
    session.add(user)
    await session.commit()

    process = await instantiate_process(
        session=session,
        template_version=ptv,
        title='Instância de teste',
        creator_user_id=user.id,
    )

    stmt = select(ActivityInstance).where(
        ActivityInstance.process_instance_id == process.id
    )
    activities = {a.key: a for a in (await session.execute(stmt)).scalars()}

    assert activities['legacy_activity'].activity_type == 'form'
    assert activities['typed_activity'].activity_type == 'decision'
