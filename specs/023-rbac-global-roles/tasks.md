---

description: "Tarefas executáveis para a simplificação de cargos globais (RBAC)"
---

# Tasks: Simplificação de Cargos Globais (RBAC)

**Input**: Artefatos de design em `specs/023-rbac-global-roles/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `quickstart.md`

**Contexto**: Dependência externa registrada pela Spec 022. Reduz os perfis globais atribuíveis a Padrão (nenhum perfil)/Administrador/BraCVAM, com Admin/BraCVAM cobrindo dinamicamente toda `Permission` ativa (presente e futura), e descontinua os 8 perfis globais sem função hoje semeados. Não altera papéis locais por processo (Feature 018).

**Tests**: Obrigatórios (autorização e migração de dados são risco alto). A suíte de testes cria schema via ORM (`table_registry.metadata.create_all`), não roda as migrations Alembic — os testes de deprecação dos 8 perfis só podem ser verificados no nível de migração (`tests/integration/migrations/`), não na suíte de API/unit geral.

**Sem tabela/coluna nova**: apenas uma migration de dados (soft-delete) sobre `access_profiles`/`user_access_profiles` já existentes.

## Formato

Cada linha de tarefa usa `- [ ] T### [P?] [US?] descrição com caminho`. `[P]` indica arquivos distintos e ausência de dependência entre as tarefas.

## Phase 1: Fundamentos

**Purpose**: Confirmar o ponto de encadeamento da migração antes de criar qualquer arquivo novo.

- [X] T001 Rodar `PYTHONPATH=src poetry run alembic heads` e confirmar que a revisão atual é `617f10506acc`, para usar como `down_revision` da migração desta feature

**Checkpoint**: Revisão de encadeamento confirmada; nenhum arquivo ainda foi criado.

---

## Phase 2: User Story 1 - Administrador e BraCVAM operam sem barreira de permissão (Priority: P1) 🎯 MVP

**Goal**: `effective_permission_codes` e `active_profile_permissions` retornam toda `Permission` ativa para usuários/perfis `administrator`/`bracvam`, calculada dinamicamente (sem depender de composição em `AccessProfilePermission`).

**Independent Test**: Criar uma `Permission` nova dentro do próprio teste (simulando uma feature futura) e confirmar que o efetivo de permissões de um usuário Administrador e de um usuário BraCVAM já a inclui, sem nenhuma composição manual.

### Tests for User Story 1

- [X] T002 [P] [US1] Criar `tests/unit/core/test_rbac_global_roles.py` com teste: `effective_permission_codes` de um usuário com perfil `administrator` retorna todo `Permission.code` ativo cadastrado (incluindo uma `Permission` criada no próprio teste, sem nenhuma linha em `AccessProfilePermission` para ela)
- [X] T003 [P] [US1] Em `tests/unit/core/test_rbac_global_roles.py`, mesmo teste para um usuário com perfil `bracvam`
- [X] T004 [US1] Em `tests/unit/core/test_rbac_global_roles.py`, adicionar teste: um usuário com um perfil customizado (`system_key=None`, via `AccessProfileFactory`) continua recebendo somente as permissões explicitamente compostas nesse perfil (comportamento atual preservado para perfis não-plataforma)
- [X] T005 [US1] Em `tests/unit/core/test_rbac_global_roles.py`, adicionar teste: `active_profile_permissions` do perfil `administrator` (por id) retorna todo `Permission.code` ativo, mesmo sem composição explícita para uma permissão nova
- [X] T006 [US1] Em `tests/api/routers/test_rbac_router.py`, adicionar teste: `GET /rbac/profiles` inclui, no item do perfil `administrator`/`bracvam`, `permission_codes` contendo uma permissão criada via fixture sem composição explícita
- [X] T007 [US1] Em `tests/api/routers/test_rbac_router.py`, adicionar teste: um usuário com perfil `bracvam` passa a ser aceito por `can_manage_process_templates` (ex.: via a rota que o exige), refletindo FR-001 (BraCVAM ganha `rbac.read` dinamicamente e, com ele, gestão de templates)

### Implementation for User Story 1

- [X] T008 [US1] Em `src/pivma/core/authorization.py`, alterar `effective_permission_codes(session, user_id)`: antes da consulta de composição, checar `await has_platform_wide_access(session, user_id)`; se verdadeiro, retornar `select(Permission.code).where(Permission.deleted_at.is_(None)).order_by(Permission.code)` diretamente, sem os `JOIN`s existentes
- [X] T009 [US1] Em `src/pivma/core/authorization.py`, alterar a assinatura de `active_profile_permissions(session, profile_id)` para `active_profile_permissions(session, profile_id, *, system_key=None)`; se `system_key in PLATFORM_WIDE_SYSTEM_KEYS`, retornar todo `Permission.code` ativo, sem os `JOIN`s existentes
- [X] T010 [US1] Em `src/pivma/routers/rbac.py`, `profile_public()`: passar `system_key=profile.system_key` na chamada a `active_profile_permissions`

**Checkpoint**: Administrador e BraCVAM têm, de forma dinâmica, toda `Permission` ativa — verificado tanto no efetivo de permissões do usuário quanto na listagem de composição do perfil.

---

## Phase 3: User Story 2 - Perfis globais sem função são descontinuados (Priority: P1)

**Goal**: Os 8 perfis globais sem `Permission` vinculada (`management_group`, `study_manager`, `participating_laboratory`, `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst`, `proponent`) deixam de existir como `AccessProfile` ativos; qualquer `UserAccessProfile` ativo apontando para eles é revogado; o histórico (`rbac_changes`) é preservado.

**Independent Test**: Aplicar a migração contra um banco com um usuário atribuído a `management_group`; confirmar que o perfil e a atribuição ficam soft-deletados, e que a reversão (`downgrade`) restaura ambos.

### Tests for User Story 2

- [X] T011 [US2] Criar `tests/integration/migrations/test_deprecate_legacy_global_profiles.py` (seguindo o padrão de `test_bracvam_rbac_migration.py`): aplicar migrações até `617f10506acc`, inserir via SQL direto os 8 perfis descontinuados com um `UserAccessProfile` ativo apontando para `management_group`, então `run_migration('head')` e confirmar via SQL que os 8 perfis e a atribuição ficam com `deleted_at IS NOT NULL`
- [X] T012 [US2] No mesmo arquivo, adicionar teste: perfis não listados para descontinuação (ex.: `administrator`, `bracvam`, ou um perfil customizado inserido no teste) permanecem com `deleted_at IS NULL` após a migração
- [X] T013 [US2] No mesmo arquivo, adicionar teste: `run_downgrade` da nova revisão restaura os 8 perfis e a atribuição (`deleted_at IS NULL` de novo), sem duplicar linhas
- [X] T014 [US2] Em `tests/unit/core/test_rbac_global_roles.py`, adicionar teste unitário para `can_manage_process_templates`: um usuário cujo único perfil ativo tem `name='Grupo Gestor'` (mas `system_key` diferente de `administrator`/`bracvam` e sem `rbac.read`) NÃO é mais aceito (a checagem por nome foi removida)

### Implementation for User Story 2

- [X] T015 [US2] Criar a migração Alembic (`PYTHONPATH=src poetry run alembic revision -m "deprecate_legacy_global_profiles"`) em `migrations/versions/`, com `down_revision = '617f10506acc'`; `upgrade()` executa `UPDATE access_profiles SET deleted_at = now() WHERE system_key IN ('management_group', 'study_manager', 'participating_laboratory', 'ad_hoc_evaluator', 'reviewer', 'specialist', 'statistical_analyst', 'proponent') AND deleted_at IS NULL` seguido de `UPDATE user_access_profiles SET deleted_at = now() WHERE profile_id IN (SELECT id FROM access_profiles WHERE system_key IN (...)) AND deleted_at IS NULL`
- [X] T016 [US2] Na mesma migração, `downgrade()` reverte ambos os `UPDATE`s (`deleted_at = NULL`) para os mesmos `system_key`s, restaurando o estado anterior
- [X] T017 [US2] Em `src/pivma/core/authorization.py`, `can_manage_process_templates`: remover `'Grupo Gestor'` do conjunto final `any(p.name in {...} for p in profiles)`, mantendo apenas `'Administrador'`

**Checkpoint**: Os 8 perfis sem função saem de circulação com histórico preservado; nenhum código de produção ainda reconhece "Grupo Gestor" por nome.

---

## Phase 4: User Story 3 - "Padrão" é o estado sem perfil global (Priority: P2)

**Goal**: Confirmar e documentar que um usuário sem `UserAccessProfile` ativo já é identificável de forma estável como "Padrão", sem exigir mudança de código.

**Independent Test**: Um usuário recém-criado, sem nenhum perfil atribuído, aparece com `profiles: []` em `GET /users`.

### Tests for User Story 3

- [X] T018 [US3] Em `tests/api/routers/test_user_listing.py` (ou arquivo equivalente já existente para `GET /users`), confirmar/adicionar teste: um usuário sem nenhum `UserAccessProfile` ativo aparece com `profiles: []` — sem exigir nenhuma mudança de código, apenas fixar o contrato como parte desta feature

### Implementation for User Story 3

- [X] T019 [US3] Nenhuma mudança de código necessária (ver `research.md`, decisão "Padrão como estado observável"); se o teste do T018 já passar sem alteração, apenas confirmar e não modificar `src/`

**Checkpoint**: "Padrão" está documentado e coberto por teste como o estado de ausência de perfil, sem introduzir uma linha ou campo novo.

---

## Phase 5: Validação transversal

**Purpose**: Fechar a qualidade da entrega.

- [X] T020 Executar `poetry run ruff check src tests` e corrigir problemas — **correção sobre o texto original desta tarefa**: `migrations/` é excluído do lint por configuração do projeto (`pyproject.toml`, `extend-exclude`); checado à parte só o arquivo novo (`6ca4dd19c8fb_deprecate_legacy_global_profiles.py`), que também passa limpo
- [X] T021 Executar `poetry run pytest -q tests/unit/core/test_rbac_global_roles.py tests/api/routers/test_rbac_router.py tests/integration/migrations/test_deprecate_legacy_global_profiles.py` — 7+12 testes, todos verdes
- [X] T022 Executar a suíte completa (`poetry run pytest -q`) — 661 passed, 1 skipped, **1 failed pré-existente e não relacionado**: `test_first_deploy_forms.py::test_triage_form_deactivated_and_submission_forms_active` já falha em `origin/develop` antes de qualquer mudança desta feature (confirmado com `git stash`); é sobre um template de demo (`submission_demo_update_v1`) de uma PR anterior, fora do escopo da Spec 023 — não corrigido aqui
- [ ] T023 Reexecutar os passos de `specs/023-rbac-global-roles/quickstart.md` contra a API local (com a migração aplicada) — **não executado nesta sessão**; a suíte automatizada (T021/T022) cobre o equivalente via testes de migração e API, mas a validação manual ponta a ponta fica pendente

---

## Dependencies & Execution Order

```text
Fundamentos (T001) → US1 (MVP) → US2 → US3 → Validação transversal
```

- T001 é um lookup, não bloqueia US1; bloqueia apenas a criação do arquivo de migração em US2 (T015).
- US1 e US2 são tecnicamente independentes entre si (funções e arquivos diferentes), mas US2's T014/T017 assumem o raciocínio de US1 (BraCVAM ganha `rbac.read` dinamicamente, então `can_manage_process_templates` não perde cobertura ao remover "Grupo Gestor") — por isso US1 vem primeiro.
- US3 não depende de código de US1/US2; só confirma um contrato já existente.

## Parallel Opportunities

```text
T002 e T003 (mesmo arquivo, casos de teste distintos) podem ser escritos em sequência rápida; T004 e T005 idem.
T011-T013 (arquivo de migração) são independentes de T002-T010 (arquivo de authorization.py) e podem ocorrer em paralelo.
Após T017:
  T020, T021 podem ocorrer em paralelo; T022 depende de ambos.
```

## Implementation Strategy

### MVP

1. Execute T001.
2. Execute os testes de US1 (T002-T007) antes da implementação (T008-T010) para confirmar que falham no comportamento atual.
3. Valide que Admin/BraCVAM cobrem toda permissão, inclusive uma criada no próprio teste, antes de seguir para a descontinuação dos perfis.

### Incremental delivery

1. US1 entrega a concessão dinâmica de permissões — já resolve a maior dor relatada ("sem grandes problemas" para Admin/BraCVAM).
2. US2 descontinua os perfis sem função, com migração testada em upgrade e downgrade.
3. US3 fecha a documentação do estado "Padrão".
4. A fase final roda lint e a suíte completa do repositório.
