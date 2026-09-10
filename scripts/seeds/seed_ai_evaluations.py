"""Carga da avaliação configurável por IA (Specs 013/014).

Provisiona, sobre a massa padrão (`seed_users` + `seed_forms`):
- uma avaliação publicada ("Atualidade da terminologia") associada ao campo
  `terminology_notes` do formulário do processo 4 (Método Validado – Dossiê);
- uma referência normativa;
- a instância oficial `[DEMO 4]` (criada por `seed_forms`) submetida, com a
  pré-avaliação já executada (provedor fake) e encaminhada à triagem — de modo
  que as demos de Triagem e de Observabilidade de IA tenham um painel real para
  inspecionar.

Não cria usuários nem processos próprios: reutiliza `admin`, `proponent_user`
e a instância `[DEMO 4]` de `seed_forms`.
"""

import asyncio
import os

# A execução da pré-avaliação no seed usa o provedor determinístico para não
# depender de OPENAI_API_KEY. O runtime da API mantém o provedor configurado.
os.environ.setdefault('AI_PROVIDER', 'fake')

from sqlalchemy import func, select

from pivma.core import evaluation_service as evsvc
from pivma.core import pre_evaluation_service as presvc
from pivma.core.database.models import ProcessInstance, User
from pivma.core.process_engine import submit_proposal_form
from scripts.seeds.common import get_session
from scripts.seeds.seed_forms import OFFICIAL_DEMO_PROCESSES

FORM_TEMPLATE_KEY = 'submission_validated_dossier_v1'
AI_FIELD = 'terminology_notes'
EVAL_NAME = 'Atualidade da terminologia'

DEMO_TITLE = next(
    item['title']
    for item in OFFICIAL_DEMO_PROCESSES
    if item['key'] == 'validated_method_dossier'
)

# (enunciado, tipo, severidade). O provedor fake marca "compliant" quando
# alguma palavra-chave do enunciado aparece no conteúdo submetido — a massa
# abaixo é calibrada para produzir um relatório com pontos de atenção.
TERMINOLOGY_CRITERIA = [
    (
        'Deve usar nomenclatura alinhada às diretrizes da OCDE',
        'conformity',
        'medium',
    ),
    (
        'Deve citar o conceito de novas abordagens metodológicas (NAM)',
        'presence',
        'low',
    ),
    (
        'Deve descrever o desfecho com terminologia atual de toxicologia',
        'quality',
        'high',
    ),
    (
        'Deve evitar termos obsoletos para modelos alternativos',
        'conformity',
        'medium',
    ),
]

FORM_VALUES = {
    'method_title': 'Ensaio de micronúcleos in vitro',
    'terminology_notes': (
        'O método usa nomenclatura alinhada às diretrizes da OCDE para '
        'genotoxicidade e descreve o desfecho como formação de micronúcleos '
        'em células binucleadas. O texto ainda emprega a expressão "teste '
        'in vitro alternativo ao animal" em vez do conceito atual de novas '
        'abordagens metodológicas.'
    ),
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
            identifier='OECD GD 34',
            label='OECD Guidance Document 34 (validação de métodos)',
            version_label='2005',
            reference_date=None,
            user_id=admin_id,
        )
    except Exception:
        await session.rollback()

    definition, _ = await evsvc.create_definition(
        session,
        name=EVAL_NAME,
        description=(
            'Verifica se a terminologia do conceito está atualizada com a '
            'nomenclatura científica e regulatória atual.'
        ),
        mode='simple',
        objective=(
            'Confirmar que os termos usados para descrever o método seguem '
            'a nomenclatura moderna (OCDE, IATA, NAM).'
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
                    'A informação deve constar no texto submetido.'
                ),
                'severity': severity,
                'on_missing_info': 'non_compliant',
                'recommendation_hint': None,
            }
            for i, (statement, check_type, severity) in enumerate(
                TERMINOLOGY_CRITERIA
            )
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


async def _demo_process_in_triage(session, proponent) -> None:
    process = (
        await session.execute(
            select(ProcessInstance).where(
                ProcessInstance.title == DEMO_TITLE,
                ProcessInstance.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if process is None:
        print(
            f"! Processo '{DEMO_TITLE}' ausente. Execute seed_forms primeiro."
        )
        return
    if process.status != 'SUBMISSION':
        print(f'✓ {DEMO_TITLE} já preparado (status: {process.status}).')
        return

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
        if admin is None or proponent is None:
            print('! Usuários ausentes. Execute seed_users.py primeiro.')
            return

        await _publish_evaluation(session, admin.id)
        await _demo_process_in_triage(session, proponent)
        print('✓ Seed de Avaliação por IA concluído.')


def main() -> None:
    asyncio.run(run_seed_ai_evaluations())


if __name__ == '__main__':
    main()
