"""Script mestre de carga de dados para demonstrações do PIVMA."""

import asyncio
import sys

from scripts.seeds.seed_ai_evaluations import run_seed_ai_evaluations
from scripts.seeds.seed_forms import run_seed_forms
from scripts.seeds.seed_kanban import run_seed_kanban
from scripts.seeds.seed_submission_update import run_seed_submission_update
from scripts.seeds.seed_triage import run_seed_triage
from scripts.seeds.seed_users import run_seed_users


async def run_all_seeds() -> None:
    print('=====================================================')
    print('PIVMA-Back: Executando Carga Completa de Dados (Seeds)')
    print('=====================================================\n')

    print('[1/6] Semeando Usuários e Perfis RBAC...')
    await run_seed_users()
    print()

    print('[2/6] Semeando Templates de Processo e Formulários...')
    await run_seed_forms()
    print()

    print('[3/6] Semeando Processos em Triagem e Ciclo de Vida...')
    await run_seed_triage()
    print()

    print('[4/6] Semeando Avaliação por IA e processo em triagem...')
    await run_seed_ai_evaluations()
    print()

    print('[5/6] Semeando Kanban de pendências (Spec 018, ~300 métodos)...')
    await run_seed_kanban()
    print()

    print('[6/6] Semeando atualização de submissão (Spec 021)...')
    await run_seed_submission_update()
    print()

    print('=====================================================')
    print('Carga concluída com sucesso!')
    print('=====================================================')
    print('Comando de carga: uv run python -m scripts.seeds.seed_all')
    print('Hub de demonstrações: http://localhost:8000/demos/')
    print('Ciclo principal:')
    print('  1. Editor de formulário + IA: http://localhost:8000/demos/forms/')
    print(
        '  2. Submissão + pré-avaliação:  http://localhost:8000/demos/submission/'
    )
    print(
        '  3. Triagem + feedback de IA:   http://localhost:8000/demos/triage/'
    )
    print(
        '  4. Observabilidade de IA:      http://localhost:8000/demos/ai-pipeline/'
    )
    print(
        '  5. Roteiro em duas fases:      http://localhost:8000/demos/roadmap/'
    )
    print(
        '  6. Kanban de pendências:       http://localhost:8000/demos/kanban/'
    )
    print(
        '  7. Atualização de submissão:   http://localhost:8000/demos/submission-update/'
    )
    print('Apoio:')
    print(
        '  8. Usuários e RBAC:            http://localhost:8000/demos/users/'
    )
    print(
        '  9. Índice operacional:        '
        'http://localhost:8000/demos/operational-index/'
    )
    print('\nContas pré-configuradas (login: /auth/login):')
    print(
        '  - admin / Password123!              '
        '(BraCVAM: edita formulário, configura IA)'
    )
    print(
        '  - proponent_user / Password123! '
        '(Proponente: submete e acompanha a pré-avaliação)'
    )
    print(
        '  - triage_evaluator / Password123!  '
        '(Avaliador: triagem e feedback por critério)'
    )
    print(
        '  - kanban_demo_bracvam / KanbanDemo@123456 '
        '(BraCVAM: vê todos os ~300 métodos no Kanban)'
    )
    print(
        '  - kanban_demo_padrao_a / KanbanDemo@123456 '
        '(Padrão: Proponente no Método A, Gestor no Método B)'
    )
    print(
        '\n"[DEMO 4] Dossiê Validado — Exemplo de IA" já está em triagem com'
    )
    print('pré-avaliação executada, pronto para as demos 3 e 4.')
    print('=====================================================\n')


def main() -> None:
    try:
        asyncio.run(run_all_seeds())
    except Exception as exc:
        print(f'\n❌ Erro na execução dos seeds: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
