"""Testes unitários para a atividade de triagem desacoplada de formulário.

Spec 020. Valida que a atividade de triagem não instancia FormInstance,
permite registro de FieldReview e conclusão via Decision.
"""

import pytest
from sqlalchemy import select

from pivma.bootstrap_process_templates import bootstrap_all_templates
from pivma.core.database.models import (
    FormInstance,
    ProcessTemplateVersion,
)
from pivma.core.process_engine import (
    NotFoundError,
    execute_triage_decision,
    get_current_activity_run,
    get_current_form_instance,
    instantiate_process,
    save_field_reviews,
    submit_proposal_form,
)
from tests.conftest import _make_rbac_user
from tests.factories.user_factory import UserFactory


async def _make_bracvam(session):
    """Triador com perfil BraCVAM: só ele edita a triagem (Spec 030)."""
    return await _make_rbac_user(
        session, system_key='bracvam', name='BraCVAM', codes=()
    )


@pytest.mark.asyncio
async def test_triage_activity_has_no_form_instance(session):
    """Garante que a atividade de triagem não cria FormInstance."""
    await bootstrap_all_templates(session)

    proponent = UserFactory()
    session.add(proponent)
    await session.commit()
    triador = await _make_bracvam(session)

    # Obter template pré-validado
    ptv = (
        (
            await session.execute(
                select(ProcessTemplateVersion).where(
                    ProcessTemplateVersion.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .first()
    )

    process = await instantiate_process(
        session, ptv, 'Estudo Sem Form Triagem', proponent.id
    )

    # Submeter proposta para desbloquear triagem
    await submit_proposal_form(
        session=session,
        process_id=process.id,
        activity_key='proposal_submission',
        values_dict={'method_title': 'Método Teste Desacoplado'},
        user_id=proponent.id,
    )

    # 1. Verificar estado da atividade de triagem
    triage_act, triage_run = await get_current_activity_run(
        session, process.id, 'triage_evaluation'
    )
    assert triage_act.status == 'IN_PROGRESS'
    assert triage_run.status == 'IN_PROGRESS'

    # 2. Verificar que NÃO existe FormInstance vinculada à execução de triagem
    form_instances = (
        (
            await session.execute(
                select(FormInstance).where(
                    FormInstance.activity_run_id == triage_run.id,
                    FormInstance.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(form_instances) == 0

    # 3. get_current_form_instance na triagem deve falhar com NotFoundError
    with pytest.raises(NotFoundError, match='Sem formulário na atividade'):
        await get_current_form_instance(
            session, process.id, 'triage_evaluation'
        )

    # 4. Gravar avaliação pericial de campo (FieldReview)
    await save_field_reviews(
        session=session,
        process_id=process.id,
        reviews_list=[
            {
                'field_key': 'method_title',
                'status': 'APPROVED',
                'comments': 'Título adequado e conciso.',
            }
        ],
        user_id=triador.id,
    )

    # 5. Executar decisão de triagem
    decision, status, _ = await execute_triage_decision(
        session=session,
        process_id=process.id,
        outcome='APPROVED',
        justification='Proposta formalmente aprovada na triagem.',
        user_id=triador.id,
    )

    assert decision.outcome == 'APPROVED'
    assert status == 'OPEN'
    assert triage_run.status == 'COMPLETED'
