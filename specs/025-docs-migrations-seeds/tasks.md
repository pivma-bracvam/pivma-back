# Tasks: Spec 025 — Documentação MkDocs, Migrações DDL Puras e Separação de Seeds

**Branch**: `025-docs-migrations-seeds` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup & Dependencies

**Purpose**: Configurar dependências e scripts de automação para a documentação MkDocs e ferramentas da plataforma.

- [x] T001 Adicionar dependências `mkdocs`, `mkdocs-material` e `pymdown-extensions` no grupo `docs` em `pyproject.toml`
- [x] T002 [P] Adicionar tarefas de automação poe `docs-serve` e `docs-build` em `pyproject.toml`

---

## Phase 2: Foundational — Saneamento de Migrações Alembic (DDL Puro)

**Purpose**: Remover todos os `op.bulk_insert` e manipulações de dados de domínio das migrações, tornando-as estritamente DDL.

**⚠️ CRITICAL**: Pré-requisito para isolar a estrutura física do banco do provisionamento de catálogo.

- [x] T003 [P] Remover `op.bulk_insert` de perfis e permissões em `migrations/versions/c1e4a9f8b312_user_authorization_rbac.py`
- [x] T004 [P] Remover `op.bulk_insert` de permissões em `migrations/versions/5e31a8c7d204_institutional_affiliations.py`
- [x] T005 [P] Remover `op.bulk_insert` de permissões em `migrations/versions/6f2c9a1d4e70_process_participant_designations.py`
- [x] T006 [P] Remover `op.bulk_insert` de permissões em `migrations/versions/7a3e1c9b4d82_admin_user_listing_permission.py`
- [x] T007 [P] Remover `op.bulk_insert` de permissões em `migrations/versions/8c5e7a1b9d02_user_management_permission.py`
- [x] T008 [P] Remover `op.bulk_insert` de permissões em `migrations/versions/8b701d7bfeae_configurable_ai_evaluation.py`
- [x] T009 [P] Remover `op.bulk_insert` de permissões em `migrations/versions/d3f9a1c47b28_bracvam_profile_triage_permission.py`
- [x] T010 Ajustar migração de descontinuação para no-op seguro em `migrations/versions/6ca4dd19c8fb_deprecate_legacy_global_profiles.py`
- [x] T011 Ajustar testes de integração de migração em `tests/integration/migrations/` para refletir DDL puro

**Checkpoint**: Migrações executam do zero gerando 100% das tabelas sem inserir linhas em `access_profiles` ou `permissions`.

---

## Phase 3: User Story 1 — Documentação Viva com MkDocs (Priority: P1)

**Goal**: Criar o portal de documentação com tema Material, guias de onboarding, ciclo de vida de validação, matriz consolidada de RBAC e especificação da funcionalidade do Kanban.

**Independent Test**: Executar `uv run mkdocs build --strict` com sucesso e inspecionar visualmente via `uv run mkdocs serve`.

- [x] T012 [US1] Criar arquivo de configuração central `mkdocs.yml` com tema Material, paleta de cores, busca em pt-BR e extensões markdown
- [x] T013 [P] [US1] Criar página inicial e visão geral da plataforma em `docs/index.md`
- [x] T014 [P] [US1] Criar guia de onboarding e ambiente local em `docs/onboarding/local-setup.md`
- [x] T015 [P] [US1] Criar guia da arquitetura de seeds e comandos de reset em `docs/onboarding/seed-architecture.md`
- [x] T016 [P] [US1] Criar documentação do ciclo de vida dos processos e máquina de estados em `docs/domain/process-lifecycle.md`
- [x] T017 [P] [US1] Criar matriz de governança RBAC consolidada (Perfis Globais vs Cargos Locais) em `docs/domain/rbac.md`
- [x] T018 [P] [US1] Criar especificação técnica da funcionalidade do Kanban (`GET /activities/kanban`) em `docs/features/kanban.md`
- [x] T019 [P] [US1] Criar documentação do fluxo de triagem e IA assistiva em `docs/features/triage-and-ai.md`
- [x] T020 [P] [US1] Criar documentação dos formulários dinâmicos em `docs/features/dynamic-forms.md`
- [x] T021 [P] [US1] Criar guia de autenticação e sessão para frontend em `docs/frontend-recipes/auth-session.md`
- [x] T022 [P] [US1] Criar guia de referência técnica sobre o catálogo das demos em `docs/frontend-recipes/demos-as-reference.md`

**Checkpoint**: Portal MkDocs compila estritamente sem erros e fornece referência completa para frontend e backend.

---

## Phase 4: User Stories 2 & 3 — Provisionamento de Produção (`bootstrap_system`) (Priority: P1)

**Goal**: Criar módulo de provisionamento idempotente de produção para perfis, permissões e templates canônicos, e integrá-lo ao `entrypoint.sh`.

**Independent Test**: Executar `python -m pivma.bootstrap_system` consecutivamente em banco migrado e validar presença de perfis e ausência de processos.

- [x] T023 [US3] Implementar script de provisionamento de produção em `src/pivma/bootstrap_system.py`
- [x] T024 [US3] Atualizar `entrypoint.sh` para invocar sequencialmente `alembic upgrade head` e `python -m pivma.bootstrap_system`
- [x] T025 [P] [US3] Criar testes de integração para idempotência e catálogo do bootstrap em `tests/integration/test_bootstrap_system.py`

**Checkpoint**: Inicialização da aplicação em container sobe automaticamente com o baseline de produção pronto.

---

## Phase 5: User Story 4 — Reestruturação dos Seeds de Demonstração (Priority: P2)

**Goal**: Desacoplar a carga de estresse do Kanban, eliminar deleções destrutivas cruzadas e fornecer CLI com perfis determinísticos (`dev`, `kanban`) e limpeza (`--clean`).

**Independent Test**: Executar `python -m scripts.seeds --profile dev` (gera 6 processos no kanban) e `python -m scripts.seeds --clean` (expurga dados de teste).

- [x] T026 [US4] Implementar CLI unificada com suporte a perfis e flags em `scripts/seeds/runner.py` e `scripts/seeds/__main__.py`
- [x] T027 [P] [US4] Remover query destrutiva `WHERE title NOT IN (...)` em `scripts/seeds/seed_forms.py`
- [x] T028 [P] [US4] Remover query destrutiva `WHERE title NOT IN (...)` em `scripts/seeds/seed_triage.py`
- [x] T029 [US4] Parametrizar contagem de processos em `scripts/seeds/seed_kanban.py` (default 6 processos para `dev`, 300 para `kanban`)
- [x] T030 [US4] Atualizar script mestre legado `scripts/seeds/seed_all.py` para delegar à nova CLI
- [x] T031 [US4] Implementar rotina de expurgo seguro (`--clean`) em `scripts/seeds/runner.py`

**Checkpoint**: O desenvolvedor de frontend executa a carga padrão em segundos com banco despoluído.

---

## Phase 6: Polish & Verification

**Purpose**: Verificação completa de integridade de ponta a ponta.

- [x] T032 Executar suite completa de testes unitários (`uv run pytest tests/unit/ -v`)
- [x] T033 Executar suite completa de testes de integração (`uv run pytest tests/integration/ -v`)
- [x] T034 Executar build estrito da documentação (`uv run mkdocs build --strict`)
- [x] T035 Executar validação dos cenários do quickstart em `specs/025-docs-migrations-seeds/quickstart.md`
