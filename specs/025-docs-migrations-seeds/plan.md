# Implementation Plan: Documentação MkDocs, Migrações DDL Puras e Separação de Seeds

**Branch**: `025-docs-migrations-seeds` | **Date**: 2026-09-17 | **Spec**: [specs/025-docs-migrations-seeds/spec.md](spec.md)

**Input**: Feature specification from `specs/025-docs-migrations-seeds/spec.md`

## Summary

Refatoração estrutural da governança do PIVMA abrangendo:
1. Implementação de documentação viva, estruturada e em português com **Material for MkDocs**, contendo a visão geral do sistema, guias de onboarding, o ciclo de vida do processo, a matriz de governança RBAC consolidada, o guia da funcionalidade do Kanban (`GET /activities/kanban`) e o catálogo das implementações de referência em `/demos/`.
2. Saneamento das 7 migrações do Alembic, removendo operações de `bulk_insert` e restringindo o Alembic a operações DDL puras.
3. Criação do script de provisionamento de produção (`pivma.bootstrap_system`), idempotente e executado no `entrypoint.sh` entre as migrações e o servidor HTTP.
4. Desacoplamento dos seeds de demonstração com a introdução de uma CLI (`scripts/seeds/runner.py`) com perfis `dev` (enxuto, 6 processos no kanban), `kanban` (carga de estresse) e `--clean` (limpeza segura sem afetar produção).

## Technical Context

**Language/Version**: Python 3.14  
**Primary Dependencies**: FastAPI 0.141, SQLAlchemy 2.0 (asyncio), Alembic 1.19, MkDocs 1.6, MkDocs Material 9.5  
**Storage**: PostgreSQL 17 (via Docker / Testcontainers)  
**Testing**: pytest 9.1, pytest-asyncio, pytest-cov, factory-boy, testcontainers  
**Target Platform**: Linux / Docker containers / Cloud deployment  
**Project Type**: Web API (Backend) + Portal de Documentação Estática (MkDocs)  
**Performance Goals**: Seed `dev` executa em < 5 segundos; MkDocs compila em < 3 segundos  
**Constraints**: Zero dados de demonstração em produção; DDL estritamente limpo; Idempotência estrita  
**Scale/Scope**: 17 migrações Alembic saneadas, 10 páginas de documentação MkDocs, 1 módulo de bootstrap de produção, 1 CLI de seeds reorganizada  

## Constitution Check

*GATE: Todas as mudanças respeitam o princípio de testabilidade contínua, governança estrita e separação de responsabilidades.*

- [x] Princípio I: Bibliotecas e módulos autocontidos e testáveis.
- [x] Princípio II: Sem atalhos ou hacks de demonstração na API real.
- [x] Princípio III: Test-First mantido (testes de migração adaptados para DDL puro e testes de bootstrap adicionados).
- [x] Princípio IV: Idempotência de scripts e preservação de integridade referencial.

## Project Structure

### Documentation (this feature)

```text
specs/025-docs-migrations-seeds/
├── plan.md              # Este plano
├── research.md          # Pesquisa técnica e decisões de arquitetura
├── data-model.md        # Catálogo de dados do baseline e namespaces de seed
├── quickstart.md        # Cenários de validação rápida
├── contracts/           # Contratos de interface
│   ├── entrypoint.md    # Contrato do ciclo de vida no container
│   ├── seeds-cli.md     # Contrato da CLI de seeds
│   └── docs-structure.md# Estrutura do portal MkDocs
└── checklists/
    └── requirements.md  # Checklist de qualidade da especificação
```

### Source Code (repository root)

```text
mkdocs.yml                           # Configuração do Material for MkDocs
docs/                                # Documentação técnica viva
├── index.md
├── onboarding/
│   ├── local-setup.md
│   └── seed-architecture.md
├── domain/
│   ├── process-lifecycle.md
│   └── rbac.md
├── features/
│   ├── kanban.md
│   ├── triage-and-ai.md
│   └── dynamic-forms.md
└── frontend-recipes/
    ├── auth-session.md
    └── demos-as-reference.md

entrypoint.sh                        # Orquestrador do container (Migrações -> Bootstrap -> Uvicorn)

src/pivma/
├── bootstrap_system.py              # [NOVO] Provisionamento idempotente de produção
├── bootstrap_process_templates.py   # Sincronizador de templates canônicos
└── bootstrap_rbac.py                # Atribuição administrativa

migrations/versions/                 # Migrações DDL puras (sem bulk_insert)
├── c1e4a9f8b312_user_authorization_rbac.py
├── 5e31a8c7d204_institutional_affiliations.py
├── 6f2c9a1d4e70_process_participant_designations.py
├── 7a3e1c9b4d82_admin_user_listing_permission.py
├── 8c5e7a1b9d02_user_management_permission.py
├── 8b701d7bfeae_configurable_ai_evaluation.py
└── d3f9a1c47b28_bracvam_profile_triage_permission.py

scripts/seeds/                       # Seeds de demonstração e desenvolvimento local
├── __init__.py
├── __main__.py                      # Ponto de entrada CLI (python -m scripts.seeds)
├── runner.py                        # Orquestrador de perfis e flags (--profile, --clean)
├── common.py
├── seed_users.py
├── seed_forms.py                    # Saneado: sem WHERE title NOT IN
├── seed_triage.py                   # Saneado: sem WHERE title NOT IN
├── seed_kanban.py                   # Parametrizado (default 6 processos, stress 300)
├── seed_ai_evaluations.py
├── seed_submission_update.py
└── seed_process_retirement.py
```

## Complexity Tracking

Nenhuma violação identificada. O plano remove complexidade acidental (limpa migrações poluídas, elimina queries destrutivas mútuas e desacopla a carga de estresse de 300 processos).
