"""Script mestre de carga de dados para demonstrações do PIVMA."""

import asyncio
import sys

from scripts.seeds.seed_ai_evaluations import run_seed_ai_evaluations
from scripts.seeds.seed_forms import run_seed_forms
from scripts.seeds.seed_triage import run_seed_triage
from scripts.seeds.seed_users import run_seed_users


async def run_all_seeds() -> None:
    print('=====================================================')
    print('PIVMA-Back: Executando Carga Completa de Dados (Seeds)')
    print('=====================================================\n')

    print('[1/4] Semeando Usuários e Perfis RBAC...')
    await run_seed_users()
    print()

    print('[2/4] Semeando Templates de Processo e Formulários...')
    await run_seed_forms()
    print()

    print('[3/4] Semeando Processos em Triagem e Ciclo de Vida...')
    await run_seed_triage()
    print()

    print('[4/4] Semeando Avaliação Configurável por IA (Spec 013)...')
    await run_seed_ai_evaluations()
    print()

    print('=====================================================')
    print('Carga concluída com sucesso! Informações para Testes:')
    print('=====================================================')
    print('Hub de Demonstrações: http://localhost:8000/demos/')
    print('Ciclo básico (4 módulos):')
    print('  1. Editor de Formulário + IA: http://localhost:8000/demos/forms/')
    print(
        '  2. Submissão + Pré-avaliação: http://localhost:8000/demos/submission/'
    )
    print(
        '  3. Triagem + Feedback de IA:  http://localhost:8000/demos/triage/'
    )
    print(
        '  4. Observabilidade de IA:     http://localhost:8000/demos/ai-pipeline/'
    )
    print('Apoio: /demos/users/  |  /demos/operational-index/')
    print('\nContas Pré-Configuradas (login: /auth/login):')
    print(
        '  - admin / Admin@123456            (BraCVAM: edita formulário,'
        ' configura avaliações por IA)'
    )
    print(
        '  - proponent_user / Proponent@123456 (Proponente: submete e'
        ' acompanha a pré-avaliação)'
    )
    print(
        '  - triage_evaluator / Triage@123456 (Avaliador: triagem e feedback'
        ' por critério)'
    )
    print('\nSpec 013: DEMO 2 "[DEMO IA] Extensão de Escopo" já está em')
    print('triagem com pré-avaliação executada + intervenção direta.')
    print('=====================================================\n')


def main() -> None:
    try:
        asyncio.run(run_all_seeds())
    except Exception as exc:
        print(f'\n❌ Erro na execução dos seeds: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
