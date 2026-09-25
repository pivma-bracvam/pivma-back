"""Script de carga para Atribuição de Cargo por Convite (Spec 028).

Cria um processo já na Fase 2 (Composição da Governança) do método
`validated_method_dossier`, com o Grupo Gestor já designado (destrava as 6
atividades que dependem dele) e um convite pendente para `sponsor` — massa
mínima para exercitar o convite por link pela API sem nenhum passo manual
de preparação (Issue #23).
"""

import argparse
import asyncio

from sqlalchemy import select

from pivma.core import pre_evaluation_service as presvc
from pivma.core.database.models import (
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
from pivma.core.invite_service import create_invite
from pivma.core.participant_service import create_assignment
from pivma.core.process_engine import (
    execute_triage_decision,
    instantiate_process,
    submit_proposal_form,
)
from scripts.seeds.common import (
    ensure_profile_by_name,
    get_or_create_user,
    get_session,
)

DEMO_MARKER = '[DEMO ROLE ASSIGNMENT]'
TEMPLATE_KEY = 'validated_method_dossier'
INVITE_EXPIRATION_HOURS = 1

SUBMISSION_VALUES = {
    'method_title': 'Método de demonstração — Atribuição de Cargo',
    'terminology_notes': (
        'Conceito-chave descrito com terminologia científica e regulatória '
        'atual (OCDE/IATA/NAM) para fins de demonstração da Fase 2.'
    ),
}


async def run_seed_role_assignment_invites() -> None:
    async with get_session() as session:
        proponent, _ = await get_or_create_user(
            session,
            username='role_assignment_demo_proponent',
            email='role.assignment.proponente@bracvam.fiocruz.br',
            full_name='Proponente de Demonstração — Atribuição de Cargo',
            password='RoleAssignDemo@123456',
        )
        bracvam_user, _ = await get_or_create_user(
            session,
            username='role_assignment_demo_bracvam',
            email='role.assignment.bracvam@bracvam.fiocruz.br',
            full_name='Equipe BraCVAM de Demonstração — Atribuição de Cargo',
            password='RoleAssignDemo@123456',
        )
        gestor, _ = await get_or_create_user(
            session,
            username='role_assignment_demo_gestor',
            email='role.assignment.gestor@bracvam.fiocruz.br',
            full_name='Grupo Gestor de Demonstração — Atribuição de Cargo',
            password='RoleAssignDemo@123456',
        )
        await ensure_profile_by_name(session, bracvam_user.id, 'BraCVAM')
        await session.commit()

        title = f'{DEMO_MARKER} Composição da Governança'
        existing = await session.scalar(
            select(ProcessInstance).where(
                ProcessInstance.title == title,
                ProcessInstance.deleted_at.is_(None),
            )
        )
        if existing is not None:
            print(
                f'✓ Já existe o processo de demo {title!r} '
                f'({existing.id}) — nada a fazer.'
            )
            return

        version = await session.scalar(
            select(ProcessTemplateVersion)
            .join(ProcessTemplate)
            .where(
                ProcessTemplate.key == TEMPLATE_KEY,
                ProcessTemplate.deleted_at.is_(None),
                ProcessTemplateVersion.is_published.is_(True),
            )
            .order_by(ProcessTemplateVersion.version_number.desc())
        )
        if version is None:
            print(
                f'! Template {TEMPLATE_KEY!r} não encontrado. '
                'Rode seed_forms.py primeiro.'
            )
            return

        process = await instantiate_process(
            session=session,
            template_version=version,
            title=title,
            creator_user_id=proponent.id,
        )
        await session.commit()

        _, _, _, pending_run = await submit_proposal_form(
            session=session,
            process_id=process.id,
            activity_key='proposal_submission',
            values_dict=SUBMISSION_VALUES,
            user_id=proponent.id,
        )
        await session.commit()

        # O campo `terminology_notes` tem `ai_evaluation_enabled` — a
        # submissão real dispara a pré-avaliação como BackgroundTask do
        # FastAPI, que não existe fora de uma requisição HTTP. Executa aqui
        # de forma síncrona (mesmo padrão de `seed_kanban.py`). O provedor
        # fake (sem `OPENAI_API_KEY`) nunca conclui positivo por design
        # (`core/settings.py`), então a pré-avaliação sempre devolve ao
        # proponente — força a ida à triagem via `request_direct_review`,
        # best-effort (silenciosamente ignorado se já não for necessário).
        if pending_run is not None:
            await presvc._execute(session, pending_run.id)
            await session.commit()
            try:
                await presvc.request_direct_review(
                    session,
                    process.id,
                    proponent.id,
                    'Encaminhado à triagem na demonstração de '
                    'Atribuição de Cargo.',
                )
                await session.commit()
            except Exception:  # noqa: BLE001 - best-effort, ver seed_kanban.py
                await session.rollback()

        await execute_triage_decision(
            session=session,
            process_id=process.id,
            outcome='APPROVED',
            justification='Aprovado na demonstração de Atribuição de Cargo.',
            user_id=bracvam_user.id,
        )
        await session.commit()

        # Grupo Gestor já designado: destrava as 6 atividades que dependem
        # dele (amostras, labs, estatístico, colaborador, ADHOC) — o roteiro
        # fica parcialmente preenchido, não só o ponto inicial.
        await create_assignment(
            session,
            process,
            user_id=gestor.id,
            role_key='group_manager',
            laboratory_id=None,
            actor_id=proponent.id,
            source='seed',
        )
        await session.commit()

        # Convite pendente para `sponsor` — o link fica disponível
        # sem precisar criar um convite manualmente.
        _invite, token = await create_invite(
            session,
            process,
            email='patrocinador.demo@exemplo.org',
            role_key='sponsor',
            laboratory_id=None,
            channel='link',
            actor_id=proponent.id,
            expiration_hours=INVITE_EXPIRATION_HOURS,
        )
        await session.commit()

        print(
            f'✓ Seed de Atribuição de Cargo concluído: processo {process.id} '
            f'({process.code}) na Fase 2, Grupo Gestor já designado '
            f'({gestor.username}), convite pendente de sponsor com token '
            f'{token!r} (válido por {INVITE_EXPIRATION_HOURS}h). '
            f'Proponente: {proponent.username}; BraCVAM: '
            f'{bracvam_user.username}.'
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Seed de demonstração de Atribuição de Cargo (Spec 028)'
    )
    parser.parse_args()
    asyncio.run(run_seed_role_assignment_invites())


if __name__ == '__main__':
    main()
