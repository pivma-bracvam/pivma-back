"""Orquestrador CLI de dados de demonstração e expurgo (Spec 025)."""

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ruff: noqa: E402
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pivma.bootstrap_system import run_system_bootstrap
from pivma.core.attachment_service import attachment_abspath
from pivma.core.database.models import (
    ActivityDependency,
    ActivityInstance,
    ActivityRun,
    Artifact,
    Assignment,
    AuditEvent,
    ConflictInterestDeclaration,
    Decision,
    DirectReviewRequest,
    EvaluationRun,
    EvaluationRunItem,
    FieldReview,
    FormInstance,
    FormValue,
    Phase,
    ProcessInstance,
    ReviewerFeedback,
    Task,
)
from pivma.core.settings import Settings
from scripts.seeds.common import get_session
from scripts.seeds.seed_ai_evaluations import run_seed_ai_evaluations
from scripts.seeds.seed_forms import run_seed_forms
from scripts.seeds.seed_triage import run_seed_triage
from scripts.seeds.seed_users import run_seed_users


async def _execute_clean_demo_data(  # noqa: PLR0912, PLR0914, PLR0915
    session: AsyncSession,
) -> int:
    stmt = select(ProcessInstance.id).where(
        ProcessInstance.title.like('[DEMO%')
    )
    process_ids = list((await session.scalars(stmt)).all())

    if not process_ids:
        print('✓ Nenhum processo de demonstração encontrado para limpeza.')
        return 0

    print(f'  Localizados {len(process_ids)} processos de demonstração.')

    # 1. Direct review requests e avaliações de IA
    eval_runs_stmt = select(EvaluationRun.id).where(
        EvaluationRun.process_instance_id.in_(process_ids)
    )
    eval_run_ids = list((await session.scalars(eval_runs_stmt)).all())

    if eval_run_ids:
        await session.execute(
            delete(DirectReviewRequest).where(
                (DirectReviewRequest.process_instance_id.in_(process_ids))
                | (DirectReviewRequest.evaluation_run_id.in_(eval_run_ids))
            )
        )
        items_stmt = select(EvaluationRunItem.id).where(
            EvaluationRunItem.run_id.in_(eval_run_ids)
        )
        item_ids = list((await session.scalars(items_stmt)).all())
        if item_ids:
            await session.execute(
                delete(ReviewerFeedback).where(
                    ReviewerFeedback.run_item_id.in_(item_ids)
                )
            )
            await session.execute(
                delete(EvaluationRunItem).where(
                    EvaluationRunItem.id.in_(item_ids)
                )
            )
        await session.execute(
            delete(EvaluationRun).where(EvaluationRun.id.in_(eval_run_ids))
        )
    else:
        await session.execute(
            delete(DirectReviewRequest).where(
                DirectReviewRequest.process_instance_id.in_(process_ids)
            )
        )

    # 2. Eventos de auditoria vinculados aos processos de demonstração
    await session.execute(
        delete(AuditEvent).where(
            AuditEvent.process_instance_id.in_(process_ids)
        )
    )

    # 3. Activity Instances e dependências
    act_inst_stmt = select(ActivityInstance.id).where(
        ActivityInstance.process_instance_id.in_(process_ids)
    )
    act_inst_ids = list((await session.scalars(act_inst_stmt)).all())

    if act_inst_ids:  # noqa: PLR1702
        await session.execute(
            delete(ActivityDependency).where(
                (ActivityDependency.dependent_activity_id.in_(act_inst_ids))
                | (ActivityDependency.required_activity_id.in_(act_inst_ids))
            )
        )
        act_runs_stmt = select(ActivityRun.id).where(
            ActivityRun.activity_instance_id.in_(act_inst_ids)
        )
        act_run_ids = list((await session.scalars(act_runs_stmt)).all())

        if act_run_ids:
            form_inst_stmt = select(FormInstance.id).where(
                FormInstance.activity_run_id.in_(act_run_ids)
            )
            form_inst_ids = list((await session.scalars(form_inst_stmt)).all())

            if form_inst_ids:
                await session.execute(
                    delete(FieldReview).where(
                        FieldReview.form_instance_id.in_(form_inst_ids)
                    )
                )
                await session.execute(
                    delete(FormValue).where(
                        FormValue.form_instance_id.in_(form_inst_ids)
                    )
                )
                await session.execute(
                    delete(FormInstance).where(
                        FormInstance.id.in_(form_inst_ids)
                    )
                )

            await session.execute(
                delete(Task).where(Task.activity_run_id.in_(act_run_ids))
            )

            # Coletar caminhos de anexos físicos para deleção em disco
            artifacts_stmt = select(Artifact).where(
                (Artifact.process_instance_id.in_(process_ids))
                | (Artifact.activity_run_id.in_(act_run_ids))
            )
            artifacts = list((await session.scalars(artifacts_stmt)).all())
            settings = Settings()
            for art in artifacts:
                if art.file_path:
                    try:
                        fpath = attachment_abspath(settings, art.file_path)
                        if fpath.exists():
                            fpath.unlink()
                    except Exception:
                        pass

            await session.execute(
                delete(Artifact).where(
                    (Artifact.process_instance_id.in_(process_ids))
                    | (Artifact.activity_run_id.in_(act_run_ids))
                )
            )
            await session.execute(
                delete(Decision).where(
                    (Decision.process_instance_id.in_(process_ids))
                    | (Decision.activity_run_id.in_(act_run_ids))
                )
            )
            await session.execute(
                delete(ActivityRun).where(ActivityRun.id.in_(act_run_ids))
            )

    # 4. Artifacts e Decisions diretamente do processo (se houver)
    await session.execute(
        delete(Artifact).where(Artifact.process_instance_id.in_(process_ids))
    )
    await session.execute(
        delete(Decision).where(Decision.process_instance_id.in_(process_ids))
    )

    # 5. Atribuições e declarações de conflito de interesse
    assignments_stmt = select(Assignment.id).where(
        Assignment.process_instance_id.in_(process_ids)
    )
    assignment_ids = list((await session.scalars(assignments_stmt)).all())
    if assignment_ids:
        await session.execute(
            delete(ConflictInterestDeclaration).where(
                ConflictInterestDeclaration.assignment_id.in_(assignment_ids)
            )
        )
        await session.execute(
            delete(Assignment).where(Assignment.id.in_(assignment_ids))
        )

    # 6. Atividades e fases
    if act_inst_ids:
        await session.execute(
            delete(ActivityInstance).where(
                ActivityInstance.id.in_(act_inst_ids)
            )
        )
    await session.execute(
        delete(Phase).where(Phase.process_instance_id.in_(process_ids))
    )

    # 7. Processos
    await session.execute(
        delete(ProcessInstance).where(ProcessInstance.id.in_(process_ids))
    )

    await session.commit()
    print(
        f'✓ Limpeza concluída: {len(process_ids)} processos de demonstração '
        'e seus dados vinculados foram expurgados.'
    )
    return len(process_ids)


async def clean_demo_data(session: AsyncSession | None = None) -> int:
    """Expurga com segurança todos os dados com marcador de demonstração

    (`[DEMO%`).
    """
    print('🧹 Iniciando limpeza segura dos dados de demonstração...')
    if session is not None:
        return await _execute_clean_demo_data(session)
    async with get_session() as s:
        return await _execute_clean_demo_data(s)


async def run_seeds(
    clean: bool = False,
    reset: bool = False,
) -> None:
    if clean or reset:
        await clean_demo_data()
        if clean:
            return

    print('=====================================================')
    print('PIVMA-Back: Executando Seed de Demonstração')
    print('=====================================================\n')

    print('[1] Garantindo baseline de produção (bootstrap_system)...')
    await run_system_bootstrap()
    print()

    print('[2] Semeando Usuários e Perfis RBAC...')
    await run_seed_users()
    print()

    print('[3] Semeando Templates canônicos e Processos da Fase 1...')
    await run_seed_forms()
    print()

    print('[4] Semeando Processos em Triagem Técnica...')
    await run_seed_triage()
    print()

    print('[5] Semeando Avaliação por IA simulada...')
    await run_seed_ai_evaluations()
    print()

    print('=====================================================')
    print('Seed de demonstração concluído com sucesso!')
    print('=====================================================\n')


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            'CLI de carga e expurgo dos dados de demonstração do PIVMA'
        ),
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        default=False,
        help='Expurga todos os dados de demonstração sem semear nada',
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        default=False,
        help=(
            'Expurga os dados de demonstração e em seguida executa o '
            'perfil selecionado'
        ),
    )

    args = parser.parse_args(argv)

    try:
        asyncio.run(
            run_seeds(
                clean=args.clean,
                reset=args.reset,
            )
        )
    except Exception as exc:
        print(f'\n❌ Erro na execução dos seeds: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
