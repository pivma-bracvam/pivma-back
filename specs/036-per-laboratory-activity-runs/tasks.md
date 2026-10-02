---
description: "Tarefas da Spec 036: execução de atividades por laboratório participante"
---

# Tasks: Execução de atividades por laboratório participante

**Input**: `specs/036-per-laboratory-activity-runs/` (spec.md, plan.md, research.md, data-model.md, contracts/http-api.md, quickstart.md)

**Tests**: obrigatórios (`AGENTS.md`), planejados com `fastapi-testing-methodology`.

**Risco**:
- **Crítico** (integração, API e segurança): autorização e isolamento entre
  laboratórios (US2), preservação de dados na reabertura (US5) e estados
  terminais no cancelamento (Phase 2).
- **Alto** (integração e API): ativação, avanço e conclusão contra a lista
  congelada (US1, US3), dispensa (US4), migração e concorrência.
- **Médio**: validação de template (US6, unitário mais carga real) e
  exposição em `/tasks` (US7, API).

Cada tarefa de teste cobre um comportamento observável e vem antes da
implementação da sua história.

**Organization**: por história da spec. US1 a US4 são P1; US5 a US7 são P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: história da spec (US1 a US7)

## Arquivos de teste

- `tests/integration/migrations/test_per_laboratory_migration.py`: migração (R4, data-model)
- `tests/integration/database/test_run_terminal_statuses.py`: cancelamento do processo e estados terminais (R14)
- `tests/integration/database/test_per_laboratory_opening.py`: ativação, conclusão e regra de conclusão (US1)
- `tests/integration/database/test_laboratory_run_access.py`: autorização por laboratório no motor (US2)
- `tests/integration/database/test_per_laboratory_chain.py`: desbloqueio por laboratório (US3)
- `tests/integration/database/test_laboratory_waiver_engine.py`: efeitos da dispensa (US4)
- `tests/integration/database/test_laboratory_reopen_engine.py`: reabertura e cascata (US5)
- `tests/integration/database/test_per_laboratory_concurrency.py`: conclusões e dispensas simultâneas (R12)
- `tests/unit/core/test_execution_scope_validation.py`: regras do template (US6)
- `tests/integration/bootstrap/test_execution_scope_bootstrap.py`: carga real de template (US6)
- `tests/api/routers/test_form_per_laboratory_guard.py`: rotas de formulário em atividade por laboratório (FR-034)
- `tests/api/routers/test_laboratory_isolation.py`: `/tasks`, `/tasks/{id}` e trilha entre laboratórios (R13)
- `tests/api/routers/test_laboratory_waivers.py`: rota de dispensa (US4)
- `tests/api/routers/test_laboratory_reopen.py`: rota de reabertura (US5)
- `tests/api/routers/test_tasks_laboratory.py`: `can_act`, laboratório e status em `/tasks` (US2, US7)

**Fixture compartilhada**: `tests/factories/laboratory_run_factory.py`
(T012).

**Template de teste `LAB_RUN_TEMPLATE`**, com duas fases:
- `phase_samples`: `sample_definition` sem dependências.
- `phase_execution`:
  - `receipt`: `per_laboratory`. `access.edit` = `participating_laboratory`,
    `group_manager` e `admin`; `access.view` = `statistician`. Depende de
    `sample_definition`.
  - `upload`: `per_laboratory`. `access.edit` = `participating_laboratory`.
    `form_template_key: "lab_results_v1"`, com um campo de texto obrigatório
    `result_note` e um campo `file_upload` opcional `raw_data`. Depende de
    `receipt`.
  - `material_return`: `per_laboratory`, `custody: true`. `access.edit` =
    `participating_laboratory`. Depende de `receipt` e de `upload`.
  - `statistics`: execução única. `assigned_role: "statistician"`.
    Depende de `upload`.
  - `lab_feedback`: `per_laboratory`. `access.edit` =
    `participating_laboratory`. Depende de `statistics` (ativada só depois
    do congelamento; usada para FR-007).

**Helper `frozen_lab_process(session, lab_count=3, freeze=True)`**:
1. Reaproveita `sample_process` (com o template como parâmetro).
2. Designa um `group_manager` e um `statistician`.
3. Com `freeze=True`, cria uma substância com SDS e conclui `sample_definition`
   por `sample_service.complete_sample_definition`, como em
   `_substance_with_sds` de `tests/integration/database/test_sample_concurrency.py`.
4. Devolve `process_id`, `labs`, `lab_users`, `group_manager`,
   `statistician` e `creator`.

Rotas de mutação usam `Origin: https://testserver`. O `bracvam_user` e o
`admin_user` vêm de `tests/conftest.py`.

---

## Phase 1: Setup

- [ ] T001 Confirmar a linha de base: `poetry run pytest tests/api/routers/test_samples_router.py tests/api/routers/test_tasks_router.py tests/api/routers/test_tasks_actionable.py tests/api/routers/test_tasks_visibility.py tests/api/routers/test_timeline_router.py tests/api/routers/test_form_submission.py tests/api/routers/test_form_attachments.py tests/api/routers/test_process_retirement.py tests/api/routers/test_activity_type_extension.py tests/integration/database/test_sample_concurrency.py -q` passa na branch antes de qualquer mudança

---

## Phase 2: Foundational (modelo, migração, estados terminais, cópia do template, fixture)

**Purpose**: colunas, tabela, estados terminais e fixture usados por todas as histórias.

### Testes (antes da implementação)

- [ ] T002 [P] Teste: após `upgrade`, toda `activity_instances` existente tem `execution_scope = 'process'` e `is_custody = false`, e toda `activity_runs` existente tem `laboratory_id` nulo, em `tests/integration/migrations/test_per_laboratory_migration.py`
- [ ] T003 [P] Teste: o índice `uq_activity_runs_number_active` recusa duas execuções ativas com o mesmo `(activity_instance_id, run_number)` e `laboratory_id` nulo (`NULLS NOT DISTINCT`), em `tests/integration/migrations/test_per_laboratory_migration.py`
- [ ] T004 [P] Teste: o mesmo índice aceita duas execuções com o mesmo `(activity_instance_id, run_number)` e laboratórios diferentes, em `tests/integration/migrations/test_per_laboratory_migration.py`
- [ ] T005 [P] Teste: `laboratory_waivers` recusa uma segunda linha ativa com o mesmo `(phase_id, laboratory_id)`, em `tests/integration/migrations/test_per_laboratory_migration.py`
- [ ] T006 [P] Teste: `downgrade` seguido de `upgrade` sem dados por laboratório termina sem erro e restaura o esquema, em `tests/integration/migrations/test_per_laboratory_migration.py`
- [ ] T007 [P] Teste: a instanciação copia `execution_scope: "per_laboratory"` e `custody: true` do template para `ActivityInstance.execution_scope`/`is_custody`; atividade sem as chaves fica `'process'`/`False`, em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T008 [P] Teste: arquivar o processo (`archive_process`) com execuções em `WAIVED`, `SUPERSEDED` e `COMPLETED` (gravadas direto no modelo) não muda nenhuma delas (FR-039, SC-010), em `tests/integration/database/test_run_terminal_statuses.py`
- [ ] T009 [P] Teste: excluir o processo (`delete_process`) com as mesmas execuções não muda nenhuma delas, em `tests/integration/database/test_run_terminal_statuses.py`
- [ ] T010 [P] Teste: o cancelamento do processo muda para `CANCELLED` as execuções `IN_PROGRESS` e `BLOCKED` e as tarefas abertas delas, em `tests/integration/database/test_run_terminal_statuses.py`

### Implementação

- [ ] T011 Modelos em `src/pivma/core/database/models.py`:
  - `ActivityInstance.execution_scope`: `String(32)`, `NOT NULL`, padrão `'process'`.
  - `ActivityInstance.is_custody`: `Boolean`, `NOT NULL`, padrão `False`.
  - `ActivityRun.laboratory_id`: `ForeignKey('laboratories.id')`, nulo, padrão `None`.
  - Índice `uq_activity_runs_number_active` passa a `(activity_instance_id, laboratory_id, run_number)` com `postgresql_nulls_not_distinct=True` e `deleted_at IS NULL`.
  - Modelo novo `LaboratoryWaiver` (`laboratory_waivers`): `process_instance_id`, `phase_id`, `laboratory_id` (todos FK `NOT NULL`), `reason` (`Text NOT NULL`), `AuditMixin` e índice único parcial `(phase_id, laboratory_id)` com `deleted_at IS NULL`.
- [ ] T012 [P] Criar `tests/factories/laboratory_run_factory.py` com `LAB_RUN_TEMPLATE` e `frozen_lab_process` (cabeçalho deste arquivo). Adicionar o parâmetro `template=SAMPLE_TEMPLATE` em `sample_process` de `tests/factories/sample_factory.py`, sem mudar o comportamento padrão.
- [ ] T013 Migração Alembic encadeada em `cc6c65843305`, em `migrations/versions/<rev>_per_laboratory_activity_runs.py`. Usar `server_default` para as colunas novas e recriar o índice no `upgrade` e no `downgrade` (data-model.md).
- [ ] T014 `IMMUTABLE_RUN_STATUSES = frozenset({'COMPLETED', 'CANCELLED', 'WAIVED', 'SUPERSEDED'})` e `_cancel_pending_children` passa a cancelar só execuções fora desse conjunto (R14), em `src/pivma/core/process_engine.py`
- [ ] T015 Copiar `execution_scope` (padrão `'process'`) e `custody` (padrão `False`) de `a_data` para a `ActivityInstance` em `_create_phases_and_activities`, em `src/pivma/core/process_engine.py`

**Checkpoint**: T002–T010 passam; suíte da linha de base (T001) continua verde.

---

## Phase 3: User Story 1 - Cada laboratório recebe a própria execução (Priority: P1) 🎯 MVP

**Goal**: ativação com uma execução por laboratório congelado; conclusão por laboratório; atividade conclui contra a lista congelada.

**Independent Test**: `frozen_lab_process(lab_count=3)` → `receipt` com 3 execuções `IN_PROGRESS`; concluir 2 → `receipt` `IN_PROGRESS`; concluir a 3ª → `COMPLETED`.

### Testes (antes da implementação)

- [ ] T016 [P] [US1] Teste: concluir `sample_definition` ativa `receipt` com exatamente N `ActivityRun` `IN_PROGRESS`, uma por laboratório congelado, `run_number = 1`, cada uma com uma `Task` `READY` (SC-001, FR-004), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T017 [P] [US1] Teste: na mesma conclusão, `upload` e `material_return` são ativadas (`IN_PROGRESS`) com N execuções `BLOCKED` cada, sem `Task` nem `FormInstance`; `statistics` fica `BLOCKED` sem execução (FR-004a, FR-012), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T018 [P] [US1] Teste: laboratório designado depois de concluir `sample_definition` não recebe execução em nenhuma atividade por laboratório (FR-005), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T019 [P] [US1] Teste: laboratório com designação revogada depois do congelamento recebe execução em `receipt` (FR-005), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T020 [P] [US1] Teste: `complete_laboratory_run` do Lab A em `receipt` conclui só a execução e a tarefa do Lab A; execuções e tarefas dos Labs B e C ficam `IN_PROGRESS`/`READY`; `receipt` fica `IN_PROGRESS` (história 1, cenário 2), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T021 [P] [US1] Teste: com `upload` concluído só pelo Lab A e as execuções dos Labs B e C ainda `BLOCKED`, `upload` **não** conclui (regra contra a lista congelada, FR-013), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T022 [P] [US1] Teste: com `upload` concluído por 2 de 3 laboratórios, `upload` fica `IN_PROGRESS` e `statistics` fica `BLOCKED` sem execução (SC-003), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T023 [P] [US1] Teste: concluir `upload` do último laboratório deixa `upload` `COMPLETED` e abre `statistics` com uma única execução `run_number = 1` e evento `ACTIVITY_UNBLOCKED` (FR-013, FR-014), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T024 [P] [US1] Teste: com `sample_definition` concluída e nenhum `BlindSampleCode` ativo, `_advance_dependent_activities` levanta `ConflictError` e, após rollback, `receipt` continua `BLOCKED` sem execução (FR-006), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T025 [P] [US1] Teste: `complete_laboratory_run` sobre execução já `COMPLETED` levanta `ConflictError` e não altera nada, em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T026 [P] [US1] Teste: `complete_laboratory_run` sobre execução `BLOCKED` levanta `ConflictError` e não altera nada, em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T027 [P] [US1] Teste: `complete_laboratory_run` em processo arquivado levanta `ConflictError` (FR-031), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T028 [P] [US1] Teste: a conclusão grava `LABORATORY_RUN_COMPLETED` com `activity_run_id` da execução e `context_data` com `activity_key`, `laboratory_id` e `run_number` (FR-030), em `tests/integration/database/test_per_laboratory_opening.py`
- [ ] T029 [P] [US1] Teste de concorrência: os dois últimos laboratórios concluem `upload` ao mesmo tempo (duas sessões); `upload` fica `COMPLETED` e `statistics` tem exatamente uma execução e um `ACTIVITY_UNBLOCKED` (FR-015), em `tests/integration/database/test_per_laboratory_concurrency.py`

### Implementação

- [ ] T030 [US1] `_frozen_laboratory_ids(session, process_id) -> list[UUID]`: `laboratory_id` distinto dos `BlindSampleCode` ativos, ordenado por `Laboratory.name` e `Laboratory.id` (R3), em `src/pivma/core/process_engine.py`
- [ ] T031 [US1] `_lock_process(session, process_id)`: `SELECT ... FOR UPDATE` em `process_instances` (R12), em `src/pivma/core/process_engine.py`
- [ ] T032 [US1] `_current_laboratory_run(session, act_id, laboratory_id)`, `_laboratory_dependencies_resolved(session, act, laboratory_id)` (R6) e `_refresh_laboratory_activity(session, process, act, user_id)`, em `src/pivma/core/process_engine.py`. A última aplica a regra do data-model: `COMPLETED` se e somente se **todo** laboratório de `_frozen_laboratory_ids` tem execução vigente `COMPLETED` ou `WAIVED`; ao chegar a `COMPLETED`, chama `_advance_dependent_activities`.
- [ ] T033 [US1] `_activate_laboratory_activity(session, process, act, a_data, user_id, reason)` em `src/pivma/core/process_engine.py` (R6). Cria uma execução por laboratório congelado na ordem de decisão da R6 (`WAIVED` entra na US4), com `run_number` = máximo do laboratório + 1. Cria `Task` e `FormInstance` só para `IN_PROGRESS`. Levanta `ConflictError` com conjunto congelado vazio. Depois ativa em cascata os dependentes por laboratório que ficaram ativáveis (FR-004a) e chama `_refresh_laboratory_activity`.
- [ ] T034 [US1] `_advance_dependent_activities`: se o dependente é `per_laboratory` e está `BLOCKED`, chama `_activate_laboratory_activity` quando FR-004a se cumpre; atividade única segue como hoje (FR-016), em `src/pivma/core/process_engine.py`
- [ ] T035 [US1] `complete_laboratory_run(session, process_id, activity_key, laboratory_id, user_id) -> ActivityRun` em `src/pivma/core/process_engine.py`, sem commit. Faz, em ordem:
  1. `ensure_process_mutable` e `_lock_process`;
  2. `require_activity_access(..., 'edit')` (endurecido na US2);
  3. execução vigente `IN_PROGRESS`, senão `ConflictError` (inclui `BLOCKED`);
  4. conclui a execução e as tarefas;
  5. grava `LABORATORY_RUN_COMPLETED`;
  6. `_refresh_laboratory_activity`.

**Checkpoint**: T016–T029 passam; T001 continua verde.

---

## Phase 4: User Story 2 - Só o próprio laboratório age e vê a sua execução (Priority: P1)

**Goal**: autorização por laboratório no motor e em `can_act`; isolamento em `/tasks`, `/tasks/{id}` e na trilha; rotas de formulário recusam atividade por laboratório.

**Independent Test**: usuário do Lab A tenta concluir a execução do Lab B → recusado; `GET /tasks` do Lab A traz só tarefas do Lab A; a trilha do Lab A não mostra eventos do Lab B.

### Testes de autorização (antes da implementação)

- [ ] T036 [P] [US2] Teste: usuário do Lab A em `complete_laboratory_run` para o Lab B levanta `AuthorizationError` e a execução do Lab B continua `IN_PROGRESS` (SC-007), em `tests/integration/database/test_laboratory_run_access.py`
- [ ] T037 [P] [US2] Teste: usuário do Lab A com vínculo institucional encerrado (designação não efetiva, Spec 035) levanta `AuthorizationError` na execução do Lab A, que continua `IN_PROGRESS`, em `tests/integration/database/test_laboratory_run_access.py`
- [ ] T038 [P] [US2] Teste: `group_manager` efetivo, embora em `edit_roles` de `receipt`, levanta `AuthorizationError` ao concluir a execução de um laboratório (FR-008), em `tests/integration/database/test_laboratory_run_access.py`
- [ ] T039 [P] [US2] Teste: `admin_user` (cargo global em `edit_roles` de `receipt`) conclui a execução de qualquer laboratório, em `tests/integration/database/test_laboratory_run_access.py`
- [ ] T040 [P] [US2] Teste: usuário do Lab A com conflito de interesse vigente no processo levanta `AuthorizationError`, em `tests/integration/database/test_laboratory_run_access.py`
- [ ] T041 [P] [US2] Teste: usuário sem nenhum cargo que veja `receipt` levanta `NotFoundError`, em `tests/integration/database/test_laboratory_run_access.py`
- [ ] T042 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como `group_manager` traz `can_act = false` nas tarefas de laboratório (FR-009), em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T043 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como usuário do Lab A traz `can_act = true` na tarefa do Lab A, em `tests/api/routers/test_tasks_laboratory.py`

### Testes de isolamento (antes da implementação)

- [ ] T044 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como usuário do Lab A traz só a tarefa do Lab A; as dos Labs B e C não aparecem e `pagination.total = 1` (FR-036, SC-009), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T045 [P] [US2] Teste: `GET /tasks?include=facets` como usuário do Lab A conta só as tarefas do Lab A nas facetas, em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T046 [P] [US2] Teste: `GET /tasks/{id}` da tarefa do Lab B como usuário do Lab A → 404 "Tarefa não encontrada." (FR-036), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T047 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como `statistician` (tem visão de `receipt`) não traz nenhuma tarefa de laboratório, em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T048 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como usuário `lead_laboratory` de outro laboratório não traz tarefas de laboratório (FR-035), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T049 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como `group_manager` traz as tarefas dos três laboratórios, em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T050 [P] [US2] Teste: `GET /tasks?activity_key=receipt` como `bracvam_user` traz as tarefas dos três laboratórios, em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T051 [P] [US2] Teste: pessoa com `participating_laboratory` pelo Lab A e `group_manager` no mesmo processo vê as tarefas dos três laboratórios (FR-035), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T052 [P] [US2] Teste: usuário do Lab A com vínculo encerrado (Spec 035) não recebe nem a tarefa do Lab A, em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T053 [P] [US2] Teste: tarefas de `statistics` (execução única) continuam visíveis ao `statistician` como hoje (FR-032), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T054 [P] [US2] Teste: depois de o Lab B concluir `receipt`, `GET /processes/{id}/timeline` como usuário do Lab A não traz o `LABORATORY_RUN_COMPLETED` do Lab B e traz o do Lab A (FR-037), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T055 [P] [US2] Teste: a mesma trilha como `group_manager` traz os eventos de conclusão dos três laboratórios, em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T056 [P] [US2] Teste: eventos `PARTICIPANT_ASSIGNED` com `laboratory_id` no contexto seguem a regra atual (gestor de participantes vê todos; a pessoa vê o próprio) (FR-037), em `tests/api/routers/test_laboratory_isolation.py`

### Testes das rotas de formulário (antes da implementação)

- [ ] T057 [P] [US2] Teste: `GET /processes/{id}/activities/upload/form` responde 409 `invalid_transition` (FR-034), em `tests/api/routers/test_form_per_laboratory_guard.py`
- [ ] T058 [P] [US2] Teste: `POST /processes/{id}/activities/upload/form` responde 409 `invalid_transition` e nenhuma execução ou `FormInstance` muda (FR-034), em `tests/api/routers/test_form_per_laboratory_guard.py`
- [ ] T059 [P] [US2] Teste: `PUT /processes/{id}/activities/upload/form` (rascunho) responde 409 `invalid_transition`, em `tests/api/routers/test_form_per_laboratory_guard.py`
- [ ] T060 [P] [US2] Teste: `POST .../activities/upload/form/fields/raw_data/attachment` responde 409 `invalid_transition`, em `tests/api/routers/test_form_per_laboratory_guard.py`

### Implementação

- [ ] T061 [US2] `require_laboratory_run_access(session, user_id, act, run)`. Aplica `require_activity_access(..., 'edit')`; com `run.laboratory_id`, exige cargo global em `edit_roles` ou designação efetiva `participating_laboratory` com `Assignment.laboratory_id == run.laboratory_id` via `process_cargos_scope` (R8). Usar em `complete_laboratory_run`. Arquivo: `src/pivma/core/process_engine.py`.
- [ ] T062 [US2] `_can_act_clause`: com `ActivityRun.laboratory_id` não nulo, a concessão por designação exige `role_key = 'participating_laboratory'` e `Assignment.laboratory_id = ActivityRun.laboratory_id`; cargo global em `edit_roles` mantém a concessão (R8), em `src/pivma/routers/tasks.py`
- [ ] T063 [US2] `laboratory_run_visibility_clause(session, user_id)` em `src/pivma/core/authorization.py` (R13): `None` para `has_platform_wide_access`; senão `ActivityRun.laboratory_id IS NULL` ou `group_manager` efetivo no processo da atividade ou `participating_laboratory` efetivo com o mesmo `laboratory_id`, via `process_cargos_scope`
- [ ] T064 [US2] Aplicar `laboratory_run_visibility_clause` em `list_tasks` (no conjunto filtrado, antes de paginação, facetas e `summary`) e em `get_task_detail` (404 se não passar), em `src/pivma/routers/tasks.py`
- [ ] T065 [US2] Em `_visible_events`, depois do filtro de visão da atividade: `LABORATORY_WAIVED` só para gestor do processo; evento com `activity_run_id` de execução com laboratório, `LABORATORY_RUN_COMPLETED` e `LABORATORY_RUN_REOPENED` só para gestor do processo ou `participating_laboratory` efetivo pelo `laboratory_id`; demais eventos como hoje (R13), em `src/pivma/routers/processes.py`
- [ ] T066 [US2] `get_current_form_instance` e `get_current_activity_run` levantam `ConflictError` quando `act.execution_scope == 'per_laboratory'`, depois da checagem de acesso, em `src/pivma/core/process_engine.py`
- [ ] T067 [US2] Mapear esse `ConflictError` para 409 `invalid_transition` nas rotas de formulário e de anexos que ainda não o mapeiam, em `src/pivma/routers/forms.py`

**Checkpoint**: T036–T060 passam; `tests/api/routers/test_tasks_actionable.py`, `test_tasks_visibility.py`, `test_timeline_router.py`, `test_participant_timeline.py`, `test_form_submission.py` e `test_form_attachments.py` continuam verdes (FR-016, FR-032, FR-034).

---

## Phase 5: User Story 3 - Cada laboratório avança na própria cadeia (Priority: P1)

**Goal**: execução `BLOCKED` do laboratório passa a `IN_PROGRESS` quando a cadeia dele se resolve.

**Independent Test**: Lab A conclui `receipt` → a execução do Lab A em `upload` passa a `IN_PROGRESS`; as dos Labs B e C continuam `BLOCKED`.

### Testes (antes da implementação)

- [ ] T068 [P] [US3] Teste: Lab A conclui `receipt` → execução do Lab A em `upload` vira `IN_PROGRESS` com `Task` `READY` e `FormInstance`; as dos Labs B e C continuam `BLOCKED`, sem tarefa (FR-011), em `tests/integration/database/test_per_laboratory_chain.py`
- [ ] T069 [P] [US3] Teste: a execução do Lab A em `upload` mantém o mesmo `id` e `run_number` ao passar de `BLOCKED` a `IN_PROGRESS` (sem execução nova), em `tests/integration/database/test_per_laboratory_chain.py`
- [ ] T070 [P] [US3] Teste: Lab A conclui `receipt` mas não `upload` → execução do Lab A em `material_return` continua `BLOCKED`, em `tests/integration/database/test_per_laboratory_chain.py`
- [ ] T071 [P] [US3] Teste: Lab A conclui `receipt` e `upload` → execução do Lab A em `material_return` vira `IN_PROGRESS`, sem esperar os Labs B e C, em `tests/integration/database/test_per_laboratory_chain.py`
- [ ] T072 [P] [US3] Teste: chamar `_unblock_laboratory` duas vezes seguidas para o mesmo laboratório não duplica tarefa nem `FormInstance`, em `tests/integration/database/test_per_laboratory_chain.py`

### Implementação

- [ ] T073 [US3] `_unblock_laboratory(session, process, act, laboratory_id, user_id)` em `src/pivma/core/process_engine.py` (R6): para cada dependente `per_laboratory` de `act` em que a execução vigente do laboratório está `BLOCKED` e `_laboratory_dependencies_resolved` é verdadeiro, passa a `IN_PROGRESS` com `Task` `READY` e `FormInstance`; propaga para os dependentes dele; chama `_refresh_laboratory_activity` em cada atividade tocada
- [ ] T074 [US3] Em `complete_laboratory_run`, chamar `_unblock_laboratory` depois de concluir e antes de `_refresh_laboratory_activity`, em `src/pivma/core/process_engine.py`

**Checkpoint**: T068–T072 passam; US1 e US2 continuam verdes.

---

## Phase 6: User Story 4 - Dispensar um laboratório (Priority: P1)

**Goal**: dispensa por fase, irreversível, só depois do congelamento, com custódia obrigatória e eventos restritos à governança.

**Independent Test**: com 2 de 3 laboratórios concluídos em `upload`, dispensar o 3º → `upload` `COMPLETED`, `statistics` abre, `material_return` do dispensado vira `IN_PROGRESS`.

### Testes do motor (antes da implementação)

- [ ] T075 [P] [US4] Teste: com Labs A e B concluídos em `receipt` e `upload`, dispensar o Lab C na `phase_execution` deixa as execuções do Lab C em `receipt` (`IN_PROGRESS`) e `upload` (`BLOCKED`) como `WAIVED`, `upload` `COMPLETED` e `statistics` aberta (história 4, cenário 1), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T076 [P] [US4] Teste: na mesma dispensa, a tarefa do Lab C em `receipt` fica `CANCELLED` e a execução do Lab C em `upload` (que não tinha tarefa) ganha uma `Task` `CANCELLED` (FR-007, FR-018), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T077 [P] [US4] Teste: após a dispensa do Lab C, a execução do Lab C em `material_return` (custódia) passa de `BLOCKED` a `IN_PROGRESS` com `Task` `READY` (FR-019, SC-005), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T078 [P] [US4] Teste: `material_return` só fica `COMPLETED` depois que o Lab C dispensado conclui a própria devolução (FR-019), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T079 [P] [US4] Teste: execução do Lab C já `COMPLETED` em `receipt` continua `COMPLETED` após a dispensa, com tarefa e eventos intactos (FR-018), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T080 [P] [US4] Teste: com o Lab C dispensado antes de `lab_feedback` ser ativada, concluir `statistics` ativa `lab_feedback` com a execução do Lab C `WAIVED` e `Task` `CANCELLED`, e as dos Labs A e B `IN_PROGRESS` (FR-007), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T081 [P] [US4] Teste: dispensar os três laboratórios (três chamadas) conclui `receipt` e `upload`, abre `statistics` e deixa `material_return` `IN_PROGRESS` para todos (Edge Cases, M1), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T082 [P] [US4] Teste: a dispensa grava um `LABORATORY_WAIVED` por execução marcada, cada um com o `activity_run_id` dela e `context_data` com `phase_key`, `activity_key`, `laboratory_id` e `reason` (FR-021), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T083 [P] [US4] Teste: dispensa do Lab A depois de ele concluir `receipt` e `upload` (`lab_feedback` ainda não ativada) não marca nenhuma execução e grava um único `LABORATORY_WAIVED` sem `activity_run_id`; `waived_activity_keys` vem vazio (FR-021), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T084 [P] [US4] Teste: `BlindSampleCode` do processo ficam idênticos antes e depois da dispensa (FR-033), em `tests/integration/database/test_laboratory_waiver_engine.py`
- [ ] T085 [P] [US4] Teste de concorrência: duas dispensas simultâneas do mesmo laboratório e fase → uma grava, a outra recebe conflito; uma única `LaboratoryWaiver` ativa (FR-020), em `tests/integration/database/test_per_laboratory_concurrency.py`

### Testes de API (antes da implementação)

- [ ] T086 [P] [US4] Teste: `POST /processes/{id}/phases/phase_execution/laboratory-waivers` como `group_manager` → 201 com o corpo `LaboratoryWaiver` do contrato, `waived_activity_keys = ["receipt", "upload"]` (M3), em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T087 [P] [US4] Teste: a mesma rota como `bracvam_user` → 201, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T088 [P] [US4] Teste: a mesma rota como `admin_user` → 201, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T089 [P] [US4] Teste: como usuário `participating_laboratory` → 403 e nenhuma linha em `laboratory_waivers` (FR-017), em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T090 [P] [US4] Teste: como `statistician` → 403, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T091 [P] [US4] Teste: como proponente (`creator`) → 403, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T092 [P] [US4] Teste: `group_manager` com designação revogada → 403, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T093 [P] [US4] Teste: usuário sem nenhuma designação no processo → 404, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T094 [P] [US4] Teste: sem login → 401, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T095 [P] [US4] Teste: com `frozen_lab_process(freeze=False)`, a dispensa → 409 `sample_definition_not_frozen` com a mensagem do contrato, e nenhuma linha em `laboratory_waivers` (FR-017a), em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T096 [P] [US4] Teste: `reason` ausente → 422 `validation_error`, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T097 [P] [US4] Teste: `reason` só com espaços → 422 `validation_error`, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T098 [P] [US4] Teste: laboratório designado depois do congelamento → 422 `laboratory_not_frozen`, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T099 [P] [US4] Teste: `phase_key` inexistente no processo → 404, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T100 [P] [US4] Teste: segunda dispensa do mesmo laboratório e fase → 409 `already_waived`, em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T101 [P] [US4] Teste: processo arquivado → 409 `invalid_transition` (FR-031), em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T102 [P] [US4] Teste: `DELETE` na rota de dispensas → 405, sem forma de reverter (FR-020a), em `tests/api/routers/test_laboratory_waivers.py`
- [ ] T103 [P] [US4] Teste: após a dispensa, `GET /processes/{id}/timeline` como `group_manager` traz os `LABORATORY_WAIVED` (FR-038), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T104 [P] [US4] Teste: a mesma trilha como usuário do Lab C (dispensado) não traz nenhum `LABORATORY_WAIVED` (FR-038), em `tests/api/routers/test_laboratory_isolation.py`
- [ ] T105 [P] [US4] Teste: a mesma trilha como usuário do Lab A não traz nenhum `LABORATORY_WAIVED` (FR-038), em `tests/api/routers/test_laboratory_isolation.py`

### Implementação

- [ ] T106 [US4] Em `_activate_laboratory_activity` e `_unblock_laboratory`, laboratório com `LaboratoryWaiver` ativa na fase e atividade sem `is_custody` recebe execução `WAIVED` com `Task` `CANCELLED` (FR-007). Na ativação em cadeia, decidir as atividades a montante antes das a jusante, para que a custódia do dispensado nasça `IN_PROGRESS` (M1). Arquivo: `src/pivma/core/process_engine.py`.
- [ ] T107 [US4] `waive_laboratory(session, process_id, phase_key, laboratory_id, reason, user_id) -> tuple[LaboratoryWaiver, list[str]]` em `src/pivma/core/process_engine.py`, sem commit. Faz, em ordem:
  1. `ensure_process_mutable` e `_lock_process`;
  2. busca a fase (`NotFoundError`);
  3. exige a atividade `activity_type == 'sample_definition'` do processo em `COMPLETED`, senão conflito `sample_definition_not_frozen` (FR-017a);
  4. confere que o laboratório está no conjunto congelado;
  5. grava a `LaboratoryWaiver` (`IntegrityError` → conflito `already_waived`);
  6. marca `WAIVED` as execuções vigentes `IN_PROGRESS` ou `BLOCKED` do laboratório nas atividades `per_laboratory` sem custódia da fase; tarefas abertas `CANCELLED`; execução sem tarefa ganha uma `CANCELLED`;
  7. grava um `LABORATORY_WAIVED` por execução marcada, ou um sem execução se nenhuma (FR-021);
  8. roda `_unblock_laboratory` e `_refresh_laboratory_activity` nas atividades tocadas;
  9. devolve a dispensa e as chaves das atividades marcadas (`waived_activity_keys`, M3).
- [ ] T108 [P] [US4] Schemas `LaboratoryWaiverCreate` (`laboratory_id: UUID`; `reason: str` com `strip` e `min_length=1`, `extra='forbid'`) e `LaboratoryWaiverPublic` (contrato, com `waived_activity_keys: list[str]`), em `src/pivma/schemas.py`
- [ ] T109 [US4] Roteador `src/pivma/routers/laboratory_runs.py` (prefixo `/processes`) com `POST /{id}/phases/{phase_key}/laboratory-waivers`. Autoriza gestor do processo (`is_effective_group_manager` ou `has_platform_wide_access`, 403); quem não vê o processo recebe 404 por `process_visibility_clause`. Exige `TrustedOrigin`, faz commit e mapeia os erros do contrato, incluindo `sample_definition_not_frozen` com a mensagem dele. Registrar em `src/pivma/__init__.py`.

**Checkpoint**: T075–T105 passam; US1–US3 continuam verdes.

---

## Phase 7: User Story 5 - Reabrir a execução de um laboratório (Priority: P2)

**Goal**: execução nova só para o laboratório, anterior preservada, cascata de bloqueio com execução `BLOCKED` de reposição.

**Independent Test**: com tudo concluído, reabrir o Lab B em `upload` → nova execução do Lab B, anterior `SUPERSEDED` intacta, `statistics` `BLOCKED`, Labs A e C intactos.

### Testes do motor (antes da implementação)

- [ ] T110 [P] [US5] Teste: `reopen_laboratory_run` do Lab B em `upload` marca a execução 1 `SUPERSEDED` e cria a execução 2 `IN_PROGRESS` do Lab B com `Task` `READY` (FR-023), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T111 [P] [US5] Teste: os `FormValue`, a `FormInstance` submetida, o `Artifact` do anexo `raw_data` (com arquivo gravado em disco) e os `AuditEvent` da execução 1 do Lab B ficam idênticos aos de antes da reabertura, e o arquivo continua no disco (SC-006, M2), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T112 [P] [US5] Teste: a execução 2 do Lab B tem uma `FormInstance` nova, não submetida e sem valores nem anexos, em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T113 [P] [US5] Teste: execuções e tarefas dos Labs A e C em `upload` não mudam (SC-002), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T114 [P] [US5] Teste: `upload` `COMPLETED` volta a `IN_PROGRESS` (FR-025), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T115 [P] [US5] Teste: `statistics` `IN_PROGRESS` volta a `BLOCKED` com `blocked_reason` preenchido e a execução aberta dela fica `CANCELLED` com tarefas `CANCELLED` (FR-025), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T116 [P] [US5] Teste: `statistics` `COMPLETED` volta a `BLOCKED` e a execução concluída continua `COMPLETED`; quando o Lab B conclui a execução 2, `statistics` abre a execução `run_number = 2`, em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T117 [P] [US5] Teste: execução do Lab B em `material_return` `IN_PROGRESS` vira `CANCELLED` e uma execução `n + 1` `BLOCKED` do Lab B, sem tarefa, toma o lugar; as dos Labs A e C não mudam (FR-025), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T118 [P] [US5] Teste: execução do Lab B em `material_return` `COMPLETED` vira `SUPERSEDED` e uma `n + 1` `BLOCKED` toma o lugar; quando o Lab B conclui `upload` de novo, ela passa a `IN_PROGRESS`, em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T119 [P] [US5] Teste: reabrir execução vigente `IN_PROGRESS` levanta `ConflictError` (FR-026), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T120 [P] [US5] Teste: reabrir execução vigente `BLOCKED` (ex.: Lab B em `material_return` antes de concluir `upload`) levanta `ConflictError` (FR-026), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T121 [P] [US5] Teste: reabrir para laboratório sem execução na atividade (designado após o congelamento) levanta `ConflictError` (FR-026, L3), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T122 [P] [US5] Teste: reabrir em `statistics` (execução única) levanta `ConflictError` (FR-026), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T123 [P] [US5] Teste: reabrir `upload` de laboratório dispensado na fase levanta `ConflictError` com código `laboratory_waived` (FR-026), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T124 [P] [US5] Teste: reabrir `material_return` (custódia) concluída por laboratório dispensado é aceito, em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T125 [P] [US5] Teste: a reabertura grava `LABORATORY_RUN_REOPENED` com `activity_run_id` da execução nova e `context_data` com `laboratory_id`, `previous_run_number`, `run_number`, `reason` e `reblocked_activity_keys` (FR-027), em `tests/integration/database/test_laboratory_reopen_engine.py`
- [ ] T126 [P] [US5] Teste: `BlindSampleCode` do processo ficam idênticos antes e depois da reabertura (FR-033), em `tests/integration/database/test_laboratory_reopen_engine.py`

### Testes de API (antes da implementação)

- [ ] T127 [P] [US5] Teste: `POST /processes/{id}/activities/upload/laboratories/{lab_b}/reopen` como `group_manager` → 201 com o corpo `LaboratoryRunReopened` do contrato, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T128 [P] [US5] Teste: a mesma rota como `bracvam_user` → 201, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T129 [P] [US5] Teste: a mesma rota como `admin_user` → 201, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T130 [P] [US5] Teste: como `statistician` → 403 e nenhuma execução muda (FR-022), em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T131 [P] [US5] Teste: como usuário do próprio Lab B → 403, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T132 [P] [US5] Teste: usuário sem designação no processo → 404, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T133 [P] [US5] Teste: sem login → 401, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T134 [P] [US5] Teste: `reason` só com espaços → 422 `validation_error`, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T135 [P] [US5] Teste: `activity_key` inexistente → 404, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T136 [P] [US5] Teste: execução vigente `IN_PROGRESS` → 409 `invalid_transition`, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T137 [P] [US5] Teste: laboratório sem execução na atividade → 409 `invalid_transition` (L3), em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T138 [P] [US5] Teste: laboratório dispensado em atividade sem custódia → 409 `laboratory_waived`, em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T139 [P] [US5] Teste: processo arquivado → 409 `invalid_transition` (FR-031), em `tests/api/routers/test_laboratory_reopen.py`
- [ ] T140 [P] [US5] Teste: após a reabertura do Lab B, a trilha do Lab A não traz o `LABORATORY_RUN_REOPENED` e a do Lab B traz (FR-037), em `tests/api/routers/test_laboratory_isolation.py`

### Implementação

- [ ] T141 [US5] `_reblock_dependents(session, process, act, laboratory_id, user_id) -> list[str]` em `src/pivma/core/process_engine.py`, em cadeia (R10):
  - dependente `per_laboratory`: só a execução vigente do laboratório muda (`IN_PROGRESS` → `CANCELLED` com tarefas `CANCELLED`; `COMPLETED` → `SUPERSEDED`), e nos dois casos uma execução `n + 1` `BLOCKED` do laboratório toma o lugar; `BLOCKED` e `WAIVED` ficam; a cadeia continua para o mesmo laboratório;
  - dependente único em `IN_PROGRESS`/`COMPLETED`: vira `BLOCKED` com `blocked_reason`, a execução aberta dele vira `CANCELLED` e a cadeia continua para todos os laboratórios;
  - devolve as chaves reabloqueadas.
- [ ] T142 [US5] `reopen_laboratory_run(session, process_id, activity_key, laboratory_id, reason, user_id) -> ActivityRun` em `src/pivma/core/process_engine.py`, sem autorização e sem commit. Faz, em ordem:
  1. `ensure_process_mutable` e `_lock_process`;
  2. as recusas de FR-026 (código `laboratory_waived` no caso da dispensa);
  3. `SUPERSEDED` na execução vigente;
  4. a execução `n + 1` `IN_PROGRESS` com `Task` e `FormInstance` nova;
  5. atividade `IN_PROGRESS`;
  6. `_reblock_dependents` e `_refresh_laboratory_activity` nas atividades tocadas;
  7. `LABORATORY_RUN_REOPENED`.
- [ ] T143 [P] [US5] Schemas `LaboratoryRunReopenRequest` (`reason: str` com `strip` e `min_length=1`, `extra='forbid'`) e `LaboratoryRunReopened` (contrato), em `src/pivma/schemas.py`
- [ ] T144 [US5] Rota `POST /{id}/activities/{activity_key}/laboratories/{laboratory_id}/reopen` em `src/pivma/routers/laboratory_runs.py`, com a mesma autorização, `TrustedOrigin`, commit e mapeamento de erros da dispensa

**Checkpoint**: T110–T140 passam; US1–US4 continuam verdes.

---

## Phase 8: User Story 6 - O template declara a execução por laboratório (Priority: P2)

**Goal**: validação das chaves novas na carga do template.

**Independent Test**: `sync_template_from_dict` com cada declaração inválida levanta `ValidationError`; os cinco templates padrão carregam.

### Testes (antes da implementação)

- [ ] T145 [P] [US6] Teste: template sem `execution_scope` nem `custody` passa em `validate_execution_scopes`, em `tests/unit/core/test_execution_scope_validation.py`
- [ ] T146 [P] [US6] Teste: `execution_scope: "per_lab"` levanta `ValidationError` com a chave do template e da atividade na mensagem, em `tests/unit/core/test_execution_scope_validation.py`
- [ ] T147 [P] [US6] Teste: atividade `per_laboratory` sem caminho de dependências até uma atividade `activity_type: "sample_definition"` levanta `ValidationError`, em `tests/unit/core/test_execution_scope_validation.py`
- [ ] T148 [P] [US6] Teste: atividade `per_laboratory` com caminho transitivo até `sample_definition` (via outra atividade) passa, em `tests/unit/core/test_execution_scope_validation.py`
- [ ] T149 [P] [US6] Teste: atividade `per_laboratory` sem `participating_laboratory` em `access.edit` levanta `ValidationError`, em `tests/unit/core/test_execution_scope_validation.py`
- [ ] T150 [P] [US6] Teste: `custody: true` em atividade de execução única levanta `ValidationError`, em `tests/unit/core/test_execution_scope_validation.py`
- [ ] T151 [P] [US6] Teste: `sync_template_from_dict` com template inválido levanta `ValidationError` e não grava `ProcessTemplate` nem versão nova, em `tests/integration/bootstrap/test_execution_scope_bootstrap.py`
- [ ] T152 [P] [US6] Teste: `bootstrap_all_templates` carrega os cinco templates padrão sem erro e nenhuma atividade deles é `per_laboratory` (SC-008), em `tests/integration/bootstrap/test_execution_scope_bootstrap.py`

### Implementação

- [ ] T153 [US6] `validate_execution_scopes(data)` pura, com as quatro regras de R2, reaproveitando `resolve_activity_access` para o conjunto de edição, em `src/pivma/core/process_engine.py`
- [ ] T154 [US6] Chamar `validate_execution_scopes` em `sync_template_from_dict`, logo após `_validate_activity_access`, em `src/pivma/bootstrap_process_templates.py`

**Checkpoint**: T145–T152 passam; `LAB_RUN_TEMPLATE` continua válido.

---

## Phase 9: User Story 7 - Acompanhar cada laboratório (Priority: P2)

**Goal**: `GET /tasks` com laboratório e status da execução para o gestor; rodada vigente por laboratório.

**Independent Test**: com Labs em estados diferentes, `GET /tasks?activity_key=upload` como `group_manager` traz laboratório e status de cada um.

### Testes (antes da implementação)

- [ ] T155 [P] [US7] Teste: `GET /tasks?activity_key=receipt` como `group_manager` traz em cada tarefa `laboratory` com `id`, `name`, `active` e `institution` do laboratório certo (FR-028), em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T156 [P] [US7] Teste: tarefa de `statistics` traz `laboratory: null`, em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T157 [P] [US7] Teste: com Lab A concluído, Lab B em andamento e Lab C dispensado em `receipt`, `activity_run_status` vem `COMPLETED`, `IN_PROGRESS` e `WAIVED`, em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T158 [P] [US7] Teste: após reabrir o Lab B em `upload`, `GET /tasks?activity_key=upload` (rodada vigente, padrão) traz a execução 2 do Lab B e a 1 dos Labs A e C (FR-029), em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T159 [P] [US7] Teste: com `current_run=false`, a tarefa da execução 1 do Lab B aparece com `activity_run_status: "SUPERSEDED"`, em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T160 [P] [US7] Teste: com a execução vigente do Lab B em `material_return` `BLOCKED` após a reabertura, a rodada vigente não traz tarefa do Lab B em `material_return`, em `tests/api/routers/test_tasks_laboratory.py`
- [ ] T161 [P] [US7] Teste: `GET /tasks/{id}` de tarefa de laboratório como `group_manager` traz `laboratory` e `activity_run_status`, em `tests/api/routers/test_tasks_laboratory.py`

### Implementação

- [ ] T162 [P] [US7] `TaskSummary` e `TaskDetail` ganham `laboratory: LaboratoryRef | None = None` e `activity_run_status: Literal['IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'WAIVED', 'SUPERSEDED']` (L5), com `Field(description=...)`, em `src/pivma/schemas.py`
- [ ] T163 [US7] `_current_run_clause` compara com o máximo por `(activity_instance_id, laboratory_id)` usando `is_not_distinct_from` (R11), em `src/pivma/routers/tasks.py`
- [ ] T164 [US7] `_task_summary` e `get_task_detail` preenchem `activity_run_status` e `laboratory`; a listagem monta os laboratórios da página em lote com `references.laboratory_refs`, em `src/pivma/routers/tasks.py`

**Checkpoint**: T155–T161 passam; `tests/api/routers/test_tasks_*.py` continuam verdes.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T165 Rodar o cenário de aceite de `specs/036-per-laboratory-activity-runs/quickstart.md` (passos 0 a 8) como teste de jornada em `tests/integration/journeys/test_per_laboratory_journey.py`
- [ ] T166 Suíte completa sem regressão: `poetry run pytest` (SC-008)
- [ ] T167 `poetry run ruff check . && poetry run ruff format --check .`
- [ ] T168 Atualizar `README.md`: o motor por laboratório (`execution_scope`, `custody`, estados da execução), as duas rotas novas, os campos novos de `/tasks`, a visibilidade entre laboratórios, os eventos novos e a recusa das rotas de formulário em atividade por laboratório. Revisar o texto com a skill `stop-slop`.
- [ ] T169 Marcar as tarefas concluídas em `specs/036-per-laboratory-activity-runs/tasks.md` e registrar em `specs/036-per-laboratory-activity-runs/checklists/requirements.md` o que foi validado

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende do Setup; bloqueia todas as histórias.
- **US1 (Phase 3)**: depende da Phase 2. Base de US2 a US5 e US7.
- **US2 (Phase 4)**: depende de US1 (`complete_laboratory_run`). T054–T056 precisam só de US1; os testes de dispensa e reabertura na trilha ficam em US4 e US5.
- **US3 (Phase 5)**: depende de US1.
- **US4 (Phase 6)**: depende de US1, US2 (filtro da trilha) e US3 (desbloqueio da custódia).
- **US5 (Phase 7)**: depende de US1, US3 e US4 (recusa por dispensa).
- **US6 (Phase 8)**: depende só da Phase 2; pode rodar em paralelo com US1 a US5.
- **US7 (Phase 9)**: depende de US1 e US2; T157 a T160 usam dispensa (US4) e reabertura (US5).
- **Polish (Phase 10)**: depois de todas as histórias.

### Within Each User Story

- Testes escritos e falhando antes da implementação.
- No motor: helpers antes das funções públicas; funções do motor antes das rotas.
- Commit ao fim de cada fase com o checkpoint verde.

### Parallel Opportunities

- T002–T010 em paralelo (arquivos de teste diferentes); T012 em paralelo com T011/T013.
- Testes de cada história marcados [P] em paralelo entre si.
- US6 inteira em paralelo com US1 a US5 (arquivos diferentes: `bootstrap_process_templates.py` e uma função pura).
- T108/T143/T162 (schemas) em paralelo com a implementação do motor da mesma história.
- T063 (predicado em `authorization.py`) em paralelo com T061 (motor).

---

## Parallel Example: User Story 2

```bash
# Arquivos de teste diferentes, sem dependência entre si:
T036–T041 em tests/integration/database/test_laboratory_run_access.py
T044–T056 em tests/api/routers/test_laboratory_isolation.py
T057–T060 em tests/api/routers/test_form_per_laboratory_guard.py
# Implementação em arquivos diferentes:
T061 em src/pivma/core/process_engine.py
T063 em src/pivma/core/authorization.py
```

## Parallel Example: User Story 4

```bash
# Motor e API em arquivos diferentes:
T075–T084 em tests/integration/database/test_laboratory_waiver_engine.py
T086–T102 em tests/api/routers/test_laboratory_waivers.py
# Schemas enquanto o motor é implementado:
T108 em src/pivma/schemas.py
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 e Phase 2 (inclui estados terminais no cancelamento).
2. US1: ativação, conclusão por laboratório e regra contra a lista congelada.
3. **Validar**: T016–T029 verdes e linha de base intacta.

### Incremental Delivery

1. US1 → US2 (segurança e isolamento antes de expor qualquer coisa) → US3 → US4: entrega P1 completa.
2. US6 em paralelo a qualquer momento depois da Phase 2.
3. US5 → US7 → Polish.
4. Cada fase termina com commit e suíte da fase verde.

### Notes

- Nenhum template padrão muda nesta entrega; tudo é exercitado por `LAB_RUN_TEMPLATE`.
- `complete_laboratory_run` não tem rota HTTP; os testes chamam o motor direto (research R7).
- Verificar que cada teste falha antes da implementação.
