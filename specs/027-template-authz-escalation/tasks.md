---

description: "Task list for Fechar Escalada de Privilégio (Issue #39)"
---

# Tasks: Fechar Escalada de Privilégio em Templates e Endpoints Administrativos (Issue #39)

**Input**: Design documents from `/specs/027-template-authz-escalation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (contracts/ vazio deliberadamente)

**Tests**: Incluídos e obrigatórios (spec.md FR-006 exige cobertura de teste
automatizado explícita). Antes de qualquer tarefa de teste abaixo, chame
`Skill({skill: "fastapi-testing-methodology"})` — exigido pelo
`AGENTS.md`/`CLAUDE.md` deste projeto.

**Organization**: US1 (correção de `can_manage_process_templates` +
permissão nova) e US2 (correção de `require_admin`) tocam funções e
arquivos completamente diferentes — são independentes e podem ser feitas em
qualquer ordem ou em paralelo.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Projeto único (backend FastAPI): `src/pivma/`, `migrations/versions/`,
`tests/` na raiz do repositório.

---

## Phase 1: Setup

Nenhuma tarefa de setup necessária — branch
(`fix/027-template-authz-escalation`) e ambiente já existentes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: A permissão nova (`form_templates.manage`) precisa existir no
banco antes de qualquer teste de US1 que a exercite. Bloqueia só a parte de
teste de US1 — a correção de código de US1 e toda a US2 não dependem desta
fase, mas ela é rápida e de baixo risco, então vai primeiro por
conveniência.

- [X] T001 Criar a migração Alembic
  `migrations/versions/fa506675d3f9_form_templates_manage_permission.py`,
  `down_revision = '6ca4dd19c8fb'` (head atual confirmado em
  `research.md` #3), seguindo **exatamente** o padrão de
  `migrations/versions/d3f9a1c47b28_bracvam_profile_triage_permission.py`:
  `op.bulk_insert` em `permissions` com uma linha (`id =
  UUID('00000000-0000-0000-0000-00000000010d')`, `code =
  'form_templates.manage'`, `description = 'Gerir a definição de
  formulários de processo (campos, nome, descrição).'`); `op.bulk_insert`
  em `access_profile_permissions` com duas linhas, compondo essa permissão
  a `BRACVAM_PROFILE_ID` (`UUID('00000000-0000-0000-0000-00000000000a')`) e
  a `ADMIN_PROFILE_ID` (`UUID('00000000-0000-0000-0000-000000000009')`);
  `downgrade()` remove as duas composições e a permissão por `DELETE`
  explícito, no mesmo padrão da referência.
- [X] T002 [P] Criar
  `tests/integration/migrations/test_form_templates_manage_migration.py`,
  seguindo exatamente o padrão de
  `tests/integration/migrations/test_bracvam_rbac_migration.py`: importar
  `migration_database`/`run_migration`/`run_downgrade` de
  `tests.integration.migrations.test_secure_user_registration`, `PREVIOUS =
  '6ca4dd19c8fb'`, testar `run_migration('fa506675d3f9')` →
  `run_downgrade(PREVIOUS)` → `run_migration('head')`.

**Checkpoint**: Permissão `form_templates.manage` existe no banco e é
composta a `bracvam`/`administrator`; migração tem teste de
upgrade/downgrade próprio.

---

## Phase 3: User Story 1 - Editar template sem quebrar a necessidade do BraCVAM (Priority: P1) 🎯 MVP

**Goal**: `can_manage_process_templates` para de aceitar `rbac.read` e
perfil nomeado "Administrador" como prova de admin, e passa a aceitar a
permissão `form_templates.manage` — preservando a edição de formulário para
o BraCVAM.

**Independent Test**: Usuário só-`rbac.read` recusado (403); perfil
"Administrador" falso recusado (403); usuário com `form_templates.manage`
(perfil `bracvam`) autorizado (200); administrador oficial autorizado
(200) — tudo em `PUT /processes/templates/{key}/forms/{form_key}`.

### Tests for User Story 1 ⚠️

> Chame `Skill({skill: "fastapi-testing-methodology"})` antes desta
> subfase, se ainda não foi chamada nesta sessão de implementação.

- [X] T003 [P] [US1] Em `tests/api/routers/test_process_template_editor.py`,
  adicionar `test_rbac_read_only_cannot_update_form_template`: usuário com
  perfil customizado só com `rbac.read` chama `PUT
  /processes/templates/{key}/forms/{form_key}` → 403.
- [X] T004 [P] [US1] No mesmo arquivo, adicionar
  `test_profile_named_administrador_without_system_key_cannot_update`:
  usuário com perfil `name='Administrador'`, `system_key=None` chama o
  mesmo endpoint → 403.
- [X] T005 [P] [US1] No mesmo arquivo, adicionar
  `test_form_templates_manage_permission_can_update`: usuário com um
  perfil que só tenha a permissão `form_templates.manage` (fabricado no
  teste, sem depender do seed canônico) chama o mesmo endpoint → 200, e a
  definição é efetivamente atualizada (mesmo assert já usado no teste
  existente `test_get_and_update_form_template_definition` para o
  administrador).
- [X] T006 [US1] No mesmo arquivo, confirmar que o teste já existente
  `test_get_and_update_form_template_definition` (usuário
  `system_key='administrator'`) continua passando sem alteração — não é
  uma tarefa de escrita, é o gate de não-regressão desta fase.

### Implementation for User Story 1

- [X] T007 [US1] Adicionar a constante `FORM_TEMPLATES_MANAGE =
  'form_templates.manage'` em `src/pivma/core/authorization.py`, ao lado
  das outras constantes de permissão (ex. logo após `TRIAGE_REVIEW`, linha
  ~31).
- [X] T008 [US1] Reescrever `can_manage_process_templates` em
  `src/pivma/core/authorization.py:632-644`: remover o `if await
  has_permission(session, user_id, RBAC_READ): return True` (linhas
  642-643) e o `return any(p.name == 'Administrador' for p in profiles)`
  (linha 644); substituir por `return await has_permission(session,
  user_id, FORM_TEMPLATES_MANAGE)` — depende de T001 (permissão precisa
  existir) e T007.

**Checkpoint**: User Story 1 completa e testável de ponta a ponta — já é um
incremento entregável (MVP) por si só.

---

## Phase 4: User Story 2 - Bloquear endpoints administrativos por `rbac.read` (Priority: P1)

**Goal**: `require_admin` para de aceitar `rbac.read` como prova de admin;
continua estrito a `system_key == 'administrator'`, sem a permissão nova
(o BraCVAM não pediu isso).

**Independent Test**: Usuário só-`rbac.read` recusado (403) em
`GET /admin/logs/operational`, `GET /admin/logs/ai` e `POST
/pre-evaluations/{run_id}/retry`; administrador oficial continua autorizado
nos três.

### Tests for User Story 2 ⚠️

- [X] T009 [P] [US2] Em `tests/integration/test_admin_logs_sse.py`,
  adicionar `test_admin_logs_forbidden_for_rbac_read_only_user`: usuário
  com perfil customizado só com `rbac.read` chama `GET
  /admin/logs/operational` e `GET /admin/logs/ai` → 403 nos dois (hoje
  passam, é o bug).
- [X] T010 [P] [US2] Criado
  `tests/api/routers/test_pre_evaluation_retry_authorization.py` (nenhum
  teste de autorização existia para esse endpoint). **Correções ao
  executar**: o path real é `POST /admin/pre-evaluations/{run_id}/retry`
  (prefixo `admin_router`, não `/pre-evaluations/` como o plano supôs); em
  vez de fabricar uma `EvaluationRun` real via `_completed_run` (custoso, e
  a lógica de retry em si já é testada em
  `test_process_retirement_pre_evaluation.py`), usei um `run_id` aleatório
  e distingui autorização por status: `rbac.read` → 403 (barrado antes do
  `session.get`); administrador → 404 (passou a autorização, execução
  inexistente) — prova a mesma coisa com uma fixture bem mais simples.

### Implementation for User Story 2

- [X] T011 [US2] Em `src/pivma/dependencies.py:104-124`, remover o `from
  pivma.core.authorization import (... RBAC_READ ... has_permission)` do
  import local (linhas 109-114, manter só `ADMINISTRATOR_SYSTEM_KEY` e
  `active_profiles_for_user`) e remover o bloco `if await
  has_permission(session, user.id, RBAC_READ): return user` (linhas
  119-120).

**Checkpoint**: User Stories 1 e 2 completas e testáveis independentemente.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Fechamento da entrega — suíte completa, lint e preparação do
PR.

- [X] T012 Rodar a suíte completa (`pytest`) e confirmar 100% de sucesso
  (spec, SC-001 a SC-004), incluindo a migração nova e os testes das fases
  2-4. **712 passed, 1 skipped** na rodada final. **Achados importantes
  durante a execução**:
  1. A working tree tinha 8 migrations de RBAC (incl. `d3f9a1c47b28`)
     gutadas para `pass` por um WIP não commitado e alheio — isso quebra
     `run_migration('head')` para *qualquer* migração (inclusive a minha,
     que depende dos perfis `bracvam`/`administrator` existirem). Resolvido
     com `git stash push -- <arquivos específicos>` (reversível) para obter
     um sinal limpo, restaurado depois com `git stash pop`.
  2. **Achado arquitetural que mudou a migração**: `core/authorization.py`
     tem um mecanismo dinâmico da Spec 023 — `effective_permission_codes`
     dá a Administrador e BraCVAM **toda** `Permission` ativa do catálogo,
     mesmo sem composição explícita (`has_platform_wide_access` →
     `_all_active_permission_codes`), justamente para que uma permissão
     nova "nunca precise de migration adicional para alcançá-los" (docstring
     já existente). Isso tornou as composições explícitas que T001 previu
     redundantes — simplifiquei a migração para só inserir a `Permission`,
     sem `access_profile_permissions`. Descoberto porque
     `tests/integration/migrations/test_bracvam_rbac_migration.py` trava o
     conjunto **exato** de composições explícitas do catálogo e acusou
     `('bracvam', 'form_templates.manage')` como item extra indevido.
  3. Consequência do achado 2: atualizei
     `tests/integration/migrations/test_rbac_migration.py` (contagem
     `permission_count` de 12→13, sem mudar `composition_count`) e
     `tests/unit/core/test_rbac_global_roles.py::test_bracvam_user_can_manage_process_templates`
     (esse teste **já testava a brecha como se fosse comportamento
     esperado** — usava `rbac.read` como permissão de prova; trocado para
     `form_templates.manage`, o critério correto agora). Isso invalida a
     conclusão de `research.md` #6 desta feature ("nenhum teste depende do
     comportamento indevido") — havia um teste unitário que dependia, só
     não apareceu no grep porque testava via `can_manage_process_templates`
     sem mencionar `rbac.read` no nome do teste.
- [X] T013 Rodar `ruff check` e `ruff format --check` sobre
  `src/pivma/core/authorization.py`, `src/pivma/dependencies.py`, a
  migração nova e os arquivos de teste alterados/criados. `ruff check`
  limpo (1 linha longa corrigida). `ruff format --check` aponta
  `test_rbac_migration.py` como fora do padrão (aspas duplas em todo o
  arquivo) — pré-existente no HEAD, confirmado via `git show HEAD:...`,
  não introduzido por mim; fora de escopo, não corrigido (mesmo critério da
  Issue #22).
- [~] T014 Rodar manualmente os 7 passos de `quickstart.md` contra a API
  local (`poe serve`, com `alembic upgrade head` aplicado) — em especial o
  passo 4 (BraCVAM consegue editar formulário), que é a prova de que a
  correção não introduziu a regressão de negócio que motivou a
  clarificação. **Não executado manualmente** (sem navegador disponível no
  ambiente, mesma limitação já registrada na Issue #22) — os passos 1-5 são
  reproduzidos automaticamente pelos testes das fases 2-4
  (`test_process_template_editor.py`, `test_admin_logs_sse.py`,
  `test_pre_evaluation_retry_authorization.py`); recomendo a passada manual
  pelas demos (passos 6-7) antes do merge.
- [X] T015 Preparar o commit/PR: `git status` e `git add` seletivo,
  incluindo **só** os arquivos desta feature (`src/pivma/core/authorization.py`,
  `src/pivma/dependencies.py`, a migração nova, os arquivos de teste
  alterados/criados e `specs/027-template-authz-escalation/`) — a branch
  foi criada a partir de `develop`, que tem um WIP não commitado e alheio
  (specs/025, migrations modificadas, `docs/`, etc.) que não deve entrar
  neste PR (mesmo cuidado já registrado no PR da Issue #22). Staged
  confirmado sem nenhum arquivo alheio antes do commit.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: Sem dependência de Setup — bloqueia só as
  tarefas de teste de US1 que exercitam `form_templates.manage` (T005);
  não bloqueia a correção de código de US1 (T007-T008) nem nenhuma parte
  de US2.
- **User Stories (Fases 3-4)**: Totalmente independentes entre si (arquivos
  diferentes: `core/authorization.py` vs `dependencies.py`) — podem ser
  feitas em paralelo por pessoas diferentes, em qualquer ordem.
- **Polish (Fase 5)**: Depende de Fases 2-4 completas.

### Parallel Opportunities

- T002 (teste de migração) pode rodar em paralelo com T003-T006 (uma vez
  que T001 esteja pronta).
- T003, T004, T005 tocam o mesmo arquivo de teste mas blocos de teste
  independentes — marcadas `[P]` por não terem dependência lógica entre si,
  mas exigem cuidado ao aplicar (mesma seção do arquivo); se preferir
  serializar por segurança de merge, sem problema.
- Fases 3 e 4 inteiras podem ser feitas em paralelo por pessoas diferentes.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Completar Fase 2 (Foundational) — migração + teste de migração.
2. Completar Fase 3 (US1) — a brecha de maior impacto (SC-001).
3. **Parar e validar**: rodar `quickstart.md` passos 1, 3, 4, 5, 6.
4. Já é um incremento entregável — a brecha de edição de template está
   fechada e a necessidade do BraCVAM preservada.

### Incremental Delivery

1. Fase 2 → Fase 3 (US1, MVP) → Fase 4 (US2) → Fase 5 (Polish/PR). Como as
   duas user stories são independentes, também podem ser entregues em
   qualquer ordem ou juntas no mesmo PR (dado que ambas vêm da mesma issue
   de segurança crítica).

## Notes

- `[P]` = arquivos diferentes ou blocos de teste independentes.
- Antes de tocar em qualquer arquivo de teste, chamar
  `Skill({skill: "fastapi-testing-methodology"})`.
- Ao final (T015), lembrar que a branch tem WIP não commitado e alheio a
  esta feature na working tree — só adicionar ao commit os arquivos
  listados.
