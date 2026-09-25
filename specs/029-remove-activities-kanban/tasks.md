---

description: "Tarefas para remover o Kanban de Pendências (Spec 029)"
---

# Tasks: Remover o Kanban de Pendências (`GET /activities/kanban`)

**Input**: Design documents from `specs/029-remove-activities-kanban/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/removed-endpoints.md, quickstart.md

**Tests**: Incluídos, conforme `AGENTS.md` (vigente na `develop`) e
`.agents/skills/fastapi-testing-methodology`. Risco da mudança: **baixo**
(remoção de um endpoint de leitura sem consumidor). A matriz de risco pede
teste de API para o comportamento observável novo (404 e contrato OpenAPI) e
a suíte existente como regressão para o que não muda. A leitura do código
mostrou que nenhum teste cobre hoje a rejeição de `assigned_role` inválido
(cenário 3 da US2), e a remoção edita o docstring dessa função. Por isso há
testes de guarda para ela.

**Organization**: Tarefas agrupadas por user story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1, US2)

---

## Phase 1: Setup

**Purpose**: registrar a linha de base antes de qualquer remoção.

- [X] T001 Rodar `uv run pytest` e `uv run ruff check` na branch `chore/029-remove-activities-kanban` antes de qualquer mudança e anotar o resultado (quantidade de testes passando/falhando) para comparar no fim (SC-002). Se já houver falhas, registrar quais são para não atribuí-las a esta feature.

---

## Phase 2: Foundational

Nenhuma tarefa. Não há infraestrutura, migration ou fixture nova: o teste de
regressão usa `client` de `tests/conftest.py`, `authenticate` de
`tests/api/routers/test_rbac_router.py` e `UserFactory`.

---

## Phase 3: User Story 1 - A API deixa de oferecer o Kanban (Priority: P1) 🎯 MVP

**Goal**: `GET /activities/kanban` deixa de existir, e o código usado só por ele sai do repositório.

**Independent Test**: `uv run pytest tests/api/routers/test_activities_kanban_removed.py -v` passa, e `grep -rniE "kanban|resolve_activity_holders|ActivityCargo" src tests` só encontra o próprio arquivo de regressão.

### Tests for User Story 1

> Escrever primeiro. T002-T005 DEVEM falhar antes de T007, porque a rota e os schemas ainda existem.

- [X] T002 [US1] Criar `tests/api/routers/test_activities_kanban_removed.py` com docstring de módulo citando Spec 029 / FR-007 e o teste `test_kanban_route_returns_404_for_authenticated_user`: cria `UserFactory()`, faz `session.add` + `await session.commit()`, chama `authenticate(client, user)` (de `tests.api.routers.test_rbac_router`) e verifica que `client.get('/activities/kanban').status_code == HTTPStatus.NOT_FOUND`. Marcar com `@pytest.mark.asyncio` (padrão dos testes de router com `session`).
- [X] T003 [US1] No mesmo arquivo `tests/api/routers/test_activities_kanban_removed.py`, adicionar `test_kanban_route_returns_404_without_authentication`: sem cookie, `client.get('/activities/kanban')` responde `HTTPStatus.NOT_FOUND` (e não 401), o que prova que a rota não existe, não só que exige login.
- [X] T004 [US1] No mesmo arquivo, adicionar `test_openapi_does_not_expose_kanban_path_or_activities_tag`: `spec = client.get('/openapi.json').json()`; verifica que `'/activities/kanban'` não está em `spec['paths']`, que nenhum caminho começa com `'/activities'` e que nenhuma operação em `spec['paths']` tem `'Activities'` em `tags`.
- [X] T005 [US1] No mesmo arquivo, adicionar `test_openapi_does_not_expose_kanban_schemas`: verifica que nenhuma chave de `spec.get('components', {}).get('schemas', {})` começa com `'Kanban'` (cobre `KanbanPage`, `KanbanCardItem`, `KanbanCardProcess`).
- [X] T006 [US1] Rodar `uv run pytest tests/api/routers/test_activities_kanban_removed.py -v` e confirmar que T002, T003, T004 e T005 falham neste momento. Se algum passar antes da remoção, o teste está errado; corrigir antes de seguir.

### Implementation for User Story 1

- [X] T007 [US1] Em `src/pivma/__init__.py`, remover `activities` do import de routers e a linha `app.include_router(activities.router)`.
- [X] T008 [US1] Apagar `src/pivma/routers/activities.py` (`git rm`).
- [X] T009 [US1] Em `src/pivma/schemas.py`, remover o bloco `# KANBAN DE PENDÊNCIAS (Spec 018)` inteiro: o cabeçalho de comentário, `KanbanColumn`, `KanbanCardProcess`, `KanbanCardItem` e `KanbanPage`.
- [X] T010 [US1] Em `src/pivma/schemas.py` (depois de T009, mesmo arquivo), remover `ActivityCargo` com o comentário que o precede ("Cargo declarado por uma atividade de processo...") e a constante `GLOBAL_ACTIVITY_CARGOS = frozenset({'admin', 'bracvam'})` logo abaixo. Manter `ParticipantRole` e `LABORATORY_ROLE_KEYS`.
- [X] T011 [P] [US1] Em `src/pivma/core/process_engine.py`: remover o comentário `# Colunas do Kanban de pendências (Spec 018, FR-002).`, as constantes `KANBAN_NAO_INICIADO`, `KANBAN_EM_ANDAMENTO`, `KANBAN_EM_ATRASO`, `KANBAN_CONCLUIDO` e a função `classify_kanban_column`. No docstring de `_compute_activity_due_date`, trocar a frase "Mesma fórmula (soma de horas) já usada por `classify_kanban_column` para que as duas nunca divirjam (Spec 024, FR-003) — mas sem a normalização para timezone-aware que aquela função faz:" por um texto sem referência ao Kanban que preserve a explicação de por que `run_started_at` fica naive. No docstring de `_resolve_activity_cargo`, trocar "(na instanciação/ativação, não na leitura do Kanban)" por "(na instanciação/ativação)". Não alterar nenhuma linha de lógica além da função removida; `timedelta` e `utc_now` continuam em uso.
- [X] T012 [P] [US1] Em `src/pivma/core/authorization.py`: remover a função `resolve_activity_holders` e o dicionário `_GLOBAL_CARGO_SYSTEM_KEYS`. Reescrever o comentário acima de `GLOBAL_ACTIVITY_CARGOS`/`ACTIVITY_CARGOS` para não citar `ActivityCargo` de `schemas.py` (que deixa de existir), mantendo a descrição do vocabulário de cargos. Manter `ACTIVITY_CARGOS`, `GLOBAL_ACTIVITY_CARGOS`, `ADMINISTRATOR_SYSTEM_KEY` e `BRACVAM_SYSTEM_KEY`. Remover do import de `pivma.core.database.models` só o que `uv run ruff check src/pivma/core/authorization.py` apontar como sem uso.
- [X] T013 [P] [US1] Apagar os testes de API exclusivos do Kanban (`git rm`): `tests/api/routers/test_activities_kanban.py`, `tests/api/routers/test_kanban_blocking_context.py`, `tests/api/routers/test_kanban_role_scoping.py`.
- [X] T014 [P] [US1] Apagar os testes unitários exclusivos do Kanban (`git rm`): `tests/unit/core/test_kanban_column_classification.py`, `tests/unit/core/test_resolve_activity_holders.py`.
- [X] T015 [US1] Rodar `uv run pytest tests/api/routers/test_activities_kanban_removed.py -v` e confirmar que T002-T005 passam.

**Checkpoint**: rota e contrato removidos, com regressão verde.

---

## Phase 4: User Story 2 - O fluxo de atividades e tarefas continua igual (Priority: P1)

**Goal**: provar que motor, `/tasks`, prazo e validação de cargo não mudaram.

**Independent Test**: os arquivos de teste existentes listados em T019 passam sem edição, e os testes de guarda de T016-T018 passam antes e depois da remoção.

### Tests for User Story 2

> Testes de guarda de comportamento que já existe. Devem passar antes **e** depois de T011, porque T011 mexe no docstring da mesma função.

- [X] T016 [US2] Criar `tests/unit/core/test_resolve_activity_cargo.py` (docstring citando Spec 029, US2 cenário 3) com `test_unknown_assigned_role_raises_validation_error`: `_resolve_activity_cargo({'assigned_role': 'cargo_inexistente'})` levanta `ValidationError` de `pivma.core.process_engine`, com `match='Cargo de atividade inválido'`.
- [X] T017 [US2] No mesmo arquivo, adicionar `test_missing_assigned_role_defaults_to_proponent`: `_resolve_activity_cargo({}) == 'proponent'`.
- [X] T018 [US2] No mesmo arquivo, adicionar `test_global_cargo_is_accepted`: `_resolve_activity_cargo({'assigned_role': 'bracvam'}) == 'bracvam'`.

### Verification for User Story 2

- [X] T019 [US2] Rodar, sem editar nenhum deles, `uv run pytest tests/unit/core/test_resolve_activity_cargo.py tests/unit/core/test_process_engine.py tests/unit/core/test_activity_due_date.py tests/unit/core/test_activity_type_default.py tests/unit/core/test_template_loader.py tests/api/routers/test_tasks_router.py tests/api/routers/test_tasks_visibility.py tests/api/routers/test_process_visibility.py -v` e confirmar que todos passam (FR-004; US2 cenários 1-3).

**Checkpoint**: comportamento preservado comprovado.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T020 Rodar `grep -rniE "kanban|resolve_activity_holders|ActivityCargo|_GLOBAL_CARGO_SYSTEM_KEYS" src tests` e confirmar que só sobram ocorrências em `tests/api/routers/test_activities_kanban_removed.py` (SC-001).
- [X] T021 Rodar `uv run ruff check` e `uv run ruff format --check` e corrigir só o que vier dos arquivos tocados nesta feature.
- [X] T022 Rodar `uv run pytest` completo e comparar com a linha de base de T001 (SC-002). A diferença esperada é só a saída dos testes removidos em T013/T014 e a entrada dos testes novos de T002-T005 e T016-T018.
- [X] T023 Rodar `git diff --stat origin/028-role-assignment-invites...HEAD -- tests` (ou contra a ponta local de `028-role-assignment-invites`) e confirmar que os únicos arquivos de teste alterados são os 5 removidos (FR-005) e os 2 criados (SC-002).
- [X] T024 Revisar `README.md` conforme `AGENTS.md` ("revise e atualize o README após cada implementação") e confirmar que ele não cita o Kanban nem `/activities`. Nenhuma edição é esperada; registrar a conferência no resumo da entrega.
- [X] T025 Executar os passos de `specs/029-remove-activities-kanban/quickstart.md` e registrar o resultado.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: vazia.
- **US1 (Phase 3)**: depende de T001.
- **US2 (Phase 4)**: T016-T018 podem rodar logo após T001, em paralelo à US1. T019 depende de T011 e T012, porque precisa rodar depois das mudanças em `process_engine.py` e `authorization.py`.
- **Polish (Phase 5)**: depende de US1 e US2 completas.

### Within User Story 1

- T002 → T003 → T004 → T005 (mesmo arquivo) → T006 (falha confirmada).
- T007 → T008 (o import precisa sair antes de o arquivo sumir, para a app continuar importável).
- T009 → T010 (mesmo arquivo).
- T011, T012, T013 e T014 são independentes entre si e dos demais após T006.
- T015 depende de T007-T014.

### Parallel Opportunities

- T011, T012, T013 e T014 tocam arquivos diferentes.
- A escrita de T016-T018 (US2) pode acontecer em paralelo à US1.

---

## Parallel Example: User Story 1

```bash
# Depois de T006 (testes falhando), em paralelo:
Task: "T011 Remover KANBAN_* e classify_kanban_column em src/pivma/core/process_engine.py"
Task: "T012 Remover resolve_activity_holders e _GLOBAL_CARGO_SYSTEM_KEYS em src/pivma/core/authorization.py"
Task: "T013 git rm dos 3 testes de API do Kanban em tests/api/routers/"
Task: "T014 git rm dos 2 testes unitários do Kanban em tests/unit/core/"
```

---

## Implementation Strategy

### MVP (User Story 1)

1. T001 (linha de base).
2. T002-T006: testes de regressão escritos e falhando.
3. T007-T015: remoção e regressão verde.
4. **Validar**: rota fora e contrato limpo.

### Entrega completa

1. US2 (T016-T019): testes de guarda e regressão da suíte existente.
2. Polish (T020-T025): varredura, lint, suíte completa, diff de testes, README, quickstart.

Commit sugerido: um commit por fase (testes de regressão; remoção; testes de guarda; polish), seguindo o padrão `chore(kanban): ...` do histórico.

---

## Notes

- **Resultado da implementação (2026-09-25)**: linha de base (T001) com 804
  passed, 1 skipped e `ruff check` limpo. Depois da remoção (T022): 788
  passed, 1 skipped (−23 testes removidos, +7 novos). `ruff format --check`
  acusa 6 arquivos herdados da 028 (`invite_service.py`, testes de convite,
  participantes, tasks, due date e `specs/028.../data-model.md`); nenhum foi
  tocado por esta feature e ficaram fora do escopo. Os 6 arquivos alterados
  aqui estão formatados.

- A skill `fastapi-testing-methodology` não está registrada para o Claude Code nesta sessão (a pasta `.claude/skills` não tem o symlink). O `SKILL.md` e as referências 03 (matriz de risco) e 04 (Definition of Done) foram lidos direto de `.agents/skills/fastapi-testing-methodology/`.
- Nenhuma migration é criada. Não editar `migrations/versions/617f10506acc_normalize_task_assigned_role.py` nem outra migration.
- Não editar `specs/018-kanban-activities-roles/` (registro histórico).
