"""Script mestre de carga de dados para demonstrações do PIVMA."""

import asyncio
import sys

from scripts.seeds.seed_forms import run_seed_forms
from scripts.seeds.seed_triage import run_seed_triage
from scripts.seeds.seed_users import run_seed_users


async def run_all_seeds() -> None:
    print('=====================================================')
    print('PIVMA-Back: Executando Carga Completa de Dados (Seeds)')
    print('=====================================================\n')

    print('[1/3] Semeando Usuários e Perfis RBAC...')
    await run_seed_users()
    print()

    print('[2/3] Semeando Templates de Processo e Formulários...')
    await run_seed_forms()
    print()

    print('[3/3] Semeando Processos em Triagem e Ciclo de Vida...')
    await run_seed_triage()
    print()

    print('=====================================================')
    print('Carga concluída com sucesso! Informações para Testes:')
    print('=====================================================')
    print('Hub de Demonstrações: http://localhost:8000/demos/')
    print('Páginas de Demonstração:')
    print('  1. Gestão de Usuários:  http://localhost:8000/demos/users/')
    print('  2. Form. Dinâmicos:     http://localhost:8000/demos/forms/')
    print('  3. Submissão Proposta:  http://localhost:8000/demos/submission/')
    print('  4. Triagem e Decisão:   http://localhost:8000/demos/triage/')
    print('\nContas Pré-Configuradas:')
    print(
        '  - admin / Admin@123456           (Administrador - Gestão de'
        ' Usuários & RBAC)'
    )
    print(
        '  - proponent_user / Proponent@123456 (Proponente - Submissão de'
        ' Propostas)'
    )
    print(
        '  - triage_evaluator / Triage@123456 (Avaliador - Triagem Técnica &'
        ' Decisão)'
    )
    print('=====================================================\n')


def main() -> None:
    try:
        asyncio.run(run_all_seeds())
    except Exception as exc:
        print(f'\n❌ Erro na execução dos seeds: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
