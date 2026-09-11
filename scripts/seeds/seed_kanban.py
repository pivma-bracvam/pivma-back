"""Script de carga para o Kanban de pendências (Spec 018).

Cria uma massa de processos suficiente para provar, na demonstração
(`demos/kanban/`), que um usuário BraCVAM consegue abrir o Kanban e ver
todas as pendências de centenas de métodos associados sem abrir método por
método — sem nenhum endpoint criado exclusivamente para viabilizar a demo
(Constituição, Princípio II).
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from pivma.core.database.models import (
    ActivityInstance,
    ActivityRun,
    Assignment,
    ProcessInstance,
    ProcessTemplate,
    ProcessTemplateVersion,
)
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

DEMO_MARKER = '[DEMO KANBAN]'
TARGET_PROCESS_COUNT = 300

TEMPLATE_KEYS = [
    'pre_validated_method',
    'scope_extension',
    'me_too_validation',
    'validated_method_dossier',
    'proof_of_concept',
]

# Valores mínimos exigidos pelo formulário de submissão de cada template
# (Spec 011/015) — só o necessário para `submit_proposal_form` aceitar.
REQUIRED_VALUES = {
    'pre_validated_method': {'method_title': 'Método pré-validado de demo'},
    'scope_extension': {'method_title': 'Extensão de escopo de demo'},
    'me_too_validation': {'method_title': 'Validação me-too de demo'},
    'validated_method_dossier': {
        'method_title': 'Método validado de demo',
        'terminology_notes': (
            'Conceito-chave descrito com terminologia científica e '
            'regulatória atual (OCDE/IATA/NAM) para fins de demonstração '
            'do Kanban de pendências.'
        ),
    },
    'proof_of_concept': {
        'proponent_organization': 'Laboratório de Demonstração BraCVAM',
        'contact_first_name': 'Demo',
        'contact_last_name': 'BraCVAM',
        'contact_email': 'demo@bracvam.fiocruz.br',
        'method_name': 'Prova de conceito de demo',
    },
}


async def _backdate_current_run(session, process_id, *, days) -> None:
    """Envelhece a `ActivityRun` em andamento para forçar `Em Atraso`."""
    run_stmt = (
        select(ActivityRun)
        .join(ActivityInstance)
        .where(
            ActivityInstance.process_instance_id == process_id,
            ActivityRun.status == 'IN_PROGRESS',
            ActivityRun.deleted_at.is_(None),
        )
    )
    run = (await session.execute(run_stmt)).scalars().first()
    if run is None:
        return
    await session.execute(
        update(ActivityRun)
        .where(ActivityRun.id == run.id)
        .values(started_at=datetime.now(UTC) - timedelta(days=days))
    )


async def _advance_process(
    session, process, *, stage, creator_id, template_key
) -> None:
    values = REQUIRED_VALUES[template_key]

    if stage == 'submission_fresh':
        return

    if stage == 'submission_overdue':
        await _backdate_current_run(session, process.id, days=10)
        return

    await submit_proposal_form(
        session=session,
        process_id=process.id,
        activity_key='proposal_submission',
        values_dict=values,
        user_id=creator_id,
    )

    if stage == 'triage_fresh':
        return
    if stage == 'triage_overdue':
        await _backdate_current_run(session, process.id, days=5)
        return
    if stage == 'approved':
        await execute_triage_decision(
            session=session,
            process_id=process.id,
            outcome='APPROVED',
            justification='Aprovado na demonstração do Kanban.',
            user_id=creator_id,
        )
        return
    if stage == 'rejected':
        await execute_triage_decision(
            session=session,
            process_id=process.id,
            outcome='REJECTED',
            justification='Rejeitado na demonstração do Kanban.',
            user_id=creator_id,
        )
        return


# Distribuição determinística de estágios por `i % 10` (reprodutível entre
# execuções): 40% recém-submetido, 10% submissão atrasada, 20% em triagem,
# 10% triagem atrasada, 10% aprovado, 10% rejeitado.
STAGE_BY_BUCKET = (
    'submission_fresh',
    'submission_fresh',
    'submission_fresh',
    'submission_fresh',
    'submission_overdue',
    'triage_fresh',
    'triage_fresh',
    'triage_overdue',
    'approved',
    'rejected',
)


def _stage_for_index(i: int) -> str:
    return STAGE_BY_BUCKET[i % len(STAGE_BY_BUCKET)]


ROLE_SCOPING_METHOD_A = f'{DEMO_MARKER} Método A (cargo: Proponente)'
ROLE_SCOPING_METHOD_B = f'{DEMO_MARKER} Método B (cargo: Gestor)'


async def _seed_role_scoping_demo(
    session, versions_by_key: dict, proponent
) -> None:
    """User Story 2: um usuário `Padrão` com cargos diferentes por método.

    `kanban_demo_padrao_a` é Proponente no Método A e Gestor no Método B;
    `kanban_demo_padrao_b` não tem nenhuma atribuição em lugar nenhum —
    prova o estado vazio (spec, quickstart.md Cenário 2).
    """
    padrao_a, created_a = await get_or_create_user(
        session,
        username='kanban_demo_padrao_a',
        email='kanban.padrao.a@bracvam.fiocruz.br',
        full_name='Usuário Padrão A (cargos cruzados) — Demo Kanban',
        password='KanbanDemo@123456',
    )
    padrao_b, _ = await get_or_create_user(
        session,
        username='kanban_demo_padrao_b',
        email='kanban.padrao.b@bracvam.fiocruz.br',
        full_name='Usuário Padrão B (sem atribuição) — Demo Kanban',
        password='KanbanDemo@123456',
    )
    await session.commit()

    if not created_a:
        existing = await session.execute(
            select(ProcessInstance).where(
                ProcessInstance.title == ROLE_SCOPING_METHOD_A,
                ProcessInstance.deleted_at.is_(None),
            )
        )
        if existing.scalars().first() is not None:
            return  # já semeado em execução anterior

    template_key = 'pre_validated_method'
    await instantiate_process(
        session=session,
        template_version=versions_by_key[template_key],
        title=ROLE_SCOPING_METHOD_A,
        creator_user_id=padrao_a.id,  # cria como Proponente do Método A
    )
    await session.commit()

    method_b = await instantiate_process(
        session=session,
        template_version=versions_by_key[template_key],
        title=ROLE_SCOPING_METHOD_B,
        creator_user_id=proponent.id,
    )
    await session.commit()

    # A trava por proponente (Spec 009) restringe SUBMISSION/AI_PRE_EVALUATION
    # só a quem é Proponente — o cargo de Gestor de `padrao_a` só passa a
    # valer depois que o Método B sai de SUBMISSION.
    await submit_proposal_form(
        session=session,
        process_id=method_b.id,
        activity_key='proposal_submission',
        values_dict=REQUIRED_VALUES[template_key],
        user_id=proponent.id,
    )
    await session.commit()

    manager_assignment = Assignment(
        process_instance_id=method_b.id,
        user_id=padrao_a.id,
        role_key='group_manager',
        assigned_by=proponent.id,
    )
    manager_assignment.set_creation_audit(proponent.id)
    session.add(manager_assignment)
    await session.commit()

    print(
        '✓ Cenário de cargos cruzados semeado: '
        f'{padrao_a.username} é Proponente em {ROLE_SCOPING_METHOD_A!r} e '
        f'Gestor em {ROLE_SCOPING_METHOD_B!r}; {padrao_b.username} não tem '
        'nenhuma atribuição.'
    )


async def _load_versions_by_key(session) -> dict | None:
    versions_by_key = {}
    for key in TEMPLATE_KEYS:
        tv = (
            (
                await session.execute(
                    select(ProcessTemplateVersion)
                    .join(ProcessTemplate)
                    .where(
                        ProcessTemplate.key == key,
                        ProcessTemplate.deleted_at.is_(None),
                        ProcessTemplateVersion.is_published.is_(True),
                    )
                    .order_by(ProcessTemplateVersion.version_number.desc())
                )
            )
            .scalars()
            .first()
        )
        if tv is None:
            print(f'! Template {key!r} não encontrado. Rode seed_forms.py.')
            return None
        versions_by_key[key] = tv
    return versions_by_key


async def run_seed_kanban(
    target_count: int = TARGET_PROCESS_COUNT,
) -> None:
    async with get_session() as session:
        proponent, _ = await get_or_create_user(
            session,
            username='kanban_demo_proponent',
            email='kanban.proponente@bracvam.fiocruz.br',
            full_name='Proponente de Demonstração do Kanban',
            password='KanbanDemo@123456',
        )

        bracvam_user, _ = await get_or_create_user(
            session,
            username='kanban_demo_bracvam',
            email='kanban.bracvam@bracvam.fiocruz.br',
            full_name='Equipe BraCVAM de Demonstração do Kanban',
            password='KanbanDemo@123456',
        )
        await ensure_profile_by_name(session, bracvam_user.id, 'BraCVAM')
        await session.commit()

        versions_by_key = await _load_versions_by_key(session)
        if versions_by_key is None:
            return

        await _seed_role_scoping_demo(session, versions_by_key, proponent)

        existing_count = (
            await session.execute(
                select(func.count())
                .select_from(ProcessInstance)
                .where(
                    ProcessInstance.title.like(f'{DEMO_MARKER}%'),
                    ProcessInstance.deleted_at.is_(None),
                )
            )
        ).scalar() or 0

        missing = max(target_count - existing_count, 0)
        if missing == 0:
            print(
                f'✓ Já existem {existing_count} processos de demo do '
                'Kanban — nada a fazer.'
            )
            return

        for i in range(existing_count, existing_count + missing):
            template_key = TEMPLATE_KEYS[i % len(TEMPLATE_KEYS)]
            title = f'{DEMO_MARKER} #{i + 1:04d} — {template_key}'
            process = await instantiate_process(
                session=session,
                template_version=versions_by_key[template_key],
                title=title,
                creator_user_id=proponent.id,
            )
            await session.commit()

            stage = _stage_for_index(i)
            await _advance_process(
                session,
                process,
                stage=stage,
                creator_id=proponent.id,
                template_key=template_key,
            )
            await session.commit()

            if (i + 1) % 50 == 0:
                print(f'  ... {i + 1}/{existing_count + missing} processos')

        print(
            f'✓ Seed do Kanban concluído: {missing} processos novos '
            f'(total ~{existing_count + missing}), usuário BraCVAM: '
            f'{bracvam_user.username}.'
        )


def main() -> None:
    asyncio.run(run_seed_kanban())


if __name__ == '__main__':
    main()
