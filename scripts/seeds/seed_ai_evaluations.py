"""Carga da Spec 013 — avaliação configurável por IA.

Provisiona, sobre a massa padrão (`seed_users` + `seed_forms`):
- uma avaliação publicada ("Verificação de estrutura de POP") associada ao
  campo `scope_extension_justification` do formulário de Extensão de Escopo;
- uma referência normativa;
- o DEMO 2 (Extensão de Escopo) submetido, com a pré-avaliação já executada
  (provedor fake) e encaminhado à triagem por intervenção direta — de modo
  que a demo de Triagem tenha um painel de pré-avaliação real para inspecionar.

Não cria usuários próprios: reutiliza `admin`, `proponent_user`,
`triage_evaluator` de `seed_users`.
"""

import asyncio
import os

# A execução da pré-avaliação no seed usa o provedor determinístico para não
# depender de OPENAI_API_KEY. O runtime da API mantém o provedor configurado.
os.environ.setdefault('AI_PROVIDER', 'fake')

from sqlalchemy import func, select

from pivma.core import evaluation_service as evsvc
from pivma.core import pre_evaluation_service as presvc
from pivma.core.database.models import (
    Assignment,
    ProcessInstance,
    ProcessTemplateVersion,
    User,
)
from pivma.core.database.models import ProcessTemplate as PT
from pivma.core.process_engine import (
    instantiate_process,
    submit_proposal_form,
)
from scripts.seeds.common import get_session

FORM_TEMPLATE_KEY = 'submission_scope_extension_v1'
AI_FIELD = 'scope_extension_justification'
EVAL_NAME = 'Verificação de estrutura de POP'
DEMO_TITLE = '[DEMO IA] Extensão de Escopo com Pré-avaliação'

POP_CRITERIA = [
    ('Deve possuir identificação e versão do documento', 'presence', 'low'),
    ('Deve apresentar objetivo e escopo do procedimento', 'conformity',
     'medium'),
    ('O procedimento deve permitir reprodução por outro laboratório',
     'quality', 'critical'),
    ('Deve definir critérios de aceitação dos resultados', 'conformity',
     'critical'),
    ('Deve apresentar referências bibliográficas ou normativas', 'presence',
     'low'),
]

FORM_VALUES = {
    'method_title': 'Extensão do BCOP para dispositivos médicos',
    'base_validated_method': 'OECD TG 437 (BCOP)',
    'new_application_endpoint': 'medical_devices',
    'scope_extension_justification': (
        'Este texto resume a finalidade da extensão pretendida e a base '
        'científica que a sustenta, sem anexar o documento operacional '
        'completo com todas as seções exigidas.'
    ),
    'applicability_domain_data': (
        'Dados preliminares de aplicabilidade para a nova classe.'
    ),
    'adapted_protocol_file': 'protocolo_adaptado.pdf',
}


async def _user(session, username: str) -> User | None:
    return (
        await session.execute(
            select(User).where(
                func.lower(User.username) == username,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _publish_evaluation(session, admin_id) -> None:
    slug = evsvc._slugify(EVAL_NAME)
    exists = (
        await session.execute(
            select(evsvc.EvaluationDefinition).where(
                evsvc.EvaluationDefinition.slug == slug,
                evsvc.EvaluationDefinition.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        return

    try:
        await evsvc.create_reference(
            session,
            identifier='OECD 442D',
            label='OECD Test Guideline 442D',
            version_label='2018',
            reference_date=None,
            user_id=admin_id,
        )
    except Exception:
        await session.rollback()

    definition, _ = await evsvc.create_definition(
        session,
        name=EVAL_NAME,
        description='Estrutura mínima de um POP para reprodução do método.',
        mode='simple',
        objective=(
            'Verificar se o POP permite a execução do método por outro '
            'laboratório.'
        ),
        user_id=admin_id,
    )
    await evsvc.patch_draft_version(
        session,
        definition.id,
        1,
        objective=None,
        reference_ids=None,
        criteria=[
            {
                'id': None,
                'order_index': i,
                'statement': statement,
                'check_type': check_type,
                'polarity': 'positive',
                'required_evidence': (
                    'A informação deve constar no conteúdo do documento.'
                ),
                'severity': severity,
                'on_missing_info': 'non_compliant',
                'recommendation_hint': None,
            }
            for i, (statement, check_type, severity) in enumerate(POP_CRITERIA)
        ],
        user_id=admin_id,
    )
    await evsvc.publish_version(session, definition.id, 1, admin_id)
    await evsvc.replace_assignments(
        session,
        FORM_TEMPLATE_KEY,
        [
            {
                'definition_id': definition.id,
                'pinned_version_id': None,
                'target_type': 'field',
                'field_keys': [AI_FIELD],
                'enabled': True,
            }
        ],
        admin_id,
    )
    await session.commit()


async def _grant_group_manager(session, process_id, user, granted_by) -> None:
    """O revisor de triagem do BraCVAM atua como gestor do processo.

    A leitura da pré-avaliação e o registro de feedback por critério são
    restritos, na API, a proponente / gestor do processo / perfil
    Administrador (permissão ``ai_evaluations.read``). Para a demo de
    Triagem funcionar com a conta ``triage_evaluator`` (perfil Revisor),
    ela recebe a designação ``group_manager`` neste processo — o mesmo
    mecanismo que o endpoint ``POST /processes/{id}/participants`` usa.
    """
    exists = (
        await session.execute(
            select(Assignment).where(
                Assignment.process_instance_id == process_id,
                Assignment.user_id == user.id,
                Assignment.role_key == 'group_manager',
                Assignment.revoked_at.is_(None),
                Assignment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        return
    assignment = Assignment(
        process_instance_id=process_id,
        user_id=user.id,
        role_key='group_manager',
        assigned_by=granted_by.id,
    )
    assignment.set_creation_audit(granted_by.id)
    session.add(assignment)


async def _demo_process_in_triage(
    session, admin, proponent, evaluator
) -> None:
    exists = (
        await session.execute(
            select(ProcessInstance).where(
                ProcessInstance.title == DEMO_TITLE,
                ProcessInstance.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if exists is not None:
        if evaluator is not None:
            await _grant_group_manager(
                session, exists.id, evaluator, admin
            )
            await session.commit()
        return

    ptv = (
        await session.execute(
            select(ProcessTemplateVersion)
            .join(PT)
            .where(
                PT.key == 'scope_extension',
                ProcessTemplateVersion.deleted_at.is_(None),
            )
            .order_by(ProcessTemplateVersion.version_number.desc())
        )
    ).scalars().first()
    process = await instantiate_process(
        session,
        template_version=ptv,
        title=DEMO_TITLE,
        creator_user_id=proponent.id,
    )
    await session.commit()

    if evaluator is not None:
        await _grant_group_manager(session, process.id, evaluator, admin)
        await session.commit()

    _, _, _, pending_run = await submit_proposal_form(
        session, process.id, 'proposal_submission', FORM_VALUES, proponent.id
    )
    if pending_run is not None:
        await presvc._execute(session, pending_run.id)
        # Se a pré-avaliação retornou o proponente, ele contesta e envia ao
        # BraCVAM — deixando o processo em triagem com o relatório da IA.
        try:
            await presvc.request_direct_review(
                session,
                process.id,
                proponent.id,
                'Discordo da avaliação automática; solicito análise humana.',
            )
        except Exception:
            await session.rollback()
    await session.commit()


async def run_seed_ai_evaluations() -> None:
    async with get_session() as session:
        admin = await _user(session, 'admin')
        proponent = await _user(session, 'proponent_user')
        evaluator = await _user(session, 'triage_evaluator')
        if admin is None or proponent is None:
            print('! Usuários ausentes. Execute seed_users.py primeiro.')
            return

        await _publish_evaluation(session, admin.id)
        await _demo_process_in_triage(session, admin, proponent, evaluator)
        print('✓ Seed de Avaliação por IA (Spec 013) concluído.')


def main() -> None:
    asyncio.run(run_seed_ai_evaluations())


if __name__ == '__main__':
    main()
