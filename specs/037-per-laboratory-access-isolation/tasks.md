# Tasks: Isolamento de acesso por laboratório

**Input**: Design documents from `specs/037-per-laboratory-access-isolation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/access-matrix.md, quickstart.md

**Tests**: obrigatórios (AGENTS.md); metodologia `fastapi-testing-methodology`.
Cada teste novo falha antes da mudança de código que ele cobre, ou registra
um comportamento existente que a spec torna regra (marcado "regra existente").

## Phase 1: Setup

- [X] T001 Adicionar o parâmetro opcional `template` a `frozen_lab_process` (padrão `LAB_RUN_TEMPLATE`) e o template `LAB_ACCESS_TEMPLATE` (chave `lab_access_probe`, cópia de `LAB_RUN_TEMPLATE` em que `receipt` concede ver a `statistician`, `lead_laboratory` e `sample_selection_group`) em tests/factories/laboratory_run_factory.py

## Phase 2: Foundational

- [X] T002 Adicionar `is_process_manager(session, user_id, process_id)` (Admin, BraCVAM ou `group_manager` efetivo; research R1) em src/pivma/core/authorization.py, com docstring que aponta `laboratory_run_visibility_clause` como a versão SQL da mesma regra (e vice-versa)
- [X] T003 Trocar a dupla verificação `has_platform_wide_access`/`is_effective_group_manager` por `is_process_manager` em `_events_of_visible_laboratories` (src/pivma/routers/processes.py) e em `_require_process_manager` (src/pivma/routers/laboratory_runs.py); remover imports que ficarem sem uso
- [X] T004 Rodar tests/api/routers/test_laboratory_isolation.py, test_laboratory_waivers.py e test_laboratory_reopen.py: nenhuma expectativa muda (FR-009, FR-010)

**Checkpoint**: definição única de gestão; suíte da Spec 036 verde.

## Phase 3: User Story 1 - Laboratório não alcança dados de outro laboratório (P1) 🎯 MVP

**Goal**: toda negação entre laboratórios responde "não encontrado", igual a execução inexistente.

**Independent Test**: laboratório A tenta ler e concluir a execução de B e a de um laboratório sem execução; as respostas são iguais.

- [X] T005 [US1] Ajustar `test_lab_a_cannot_complete_lab_b_run` para esperar `NotFoundError` em tests/integration/database/test_laboratory_run_access.py (falha antes de T009)
- [X] T006 [P] [US1] Criar tests/integration/database/test_laboratory_access_matrix.py com: mensagem idêntica entre "execução de B" e "laboratório sem execução" ao concluir (SC-002); laboratório A lendo a execução de B com `level='view'` → `NotFoundError`; execução de B já concluída continua 404 para A e o status não aparece na mensagem
- [X] T007 [P] [US1] Criar tests/api/routers/test_laboratory_access_matrix.py com `/tasks/{id}` e linha do tempo de A sem nada de B, usando `LAB_ACCESS_TEMPLATE`
- [X] T008 [US1] Adicionar a constante `LABORATORY_RUN_NOT_FOUND = 'Execução do laboratório não encontrada.'` e usá-la em `complete_laboratory_run` em src/pivma/core/process_engine.py
- [X] T009 [US1] Reescrever `require_laboratory_run_access(session, user_id, act, run, level='edit')` em src/pivma/core/process_engine.py na ordem de research R2: `require_activity_access(level)`; execução sem laboratório concede; participante efetivo pelo laboratório concede; `is_process_manager` concede `view` e concede `edit` só com cargo global em `edit_roles` (senão `AuthorizationError`); demais → `NotFoundError(LABORATORY_RUN_NOT_FOUND)`
- [X] T010 [US1] Rodar T005–T007 e a suíte tests/integration/database/test_laboratory_*.py

**Checkpoint**: SC-001 e SC-002.

## Phase 4: User Story 2 - Laboratório segue trabalhando nos próprios dados (P1)

**Goal**: o dono lê e conclui a própria execução.

**Independent Test**: laboratório A lê e conclui a execução de A.

- [X] T011 [P] [US2] Em tests/integration/database/test_laboratory_access_matrix.py: dono lê a própria execução (`level='view'`) e a conclui; execução sem laboratório (`statistics`) lida pelo estatístico com `level='view'`
- [X] T012 [P] [US2] Em tests/api/routers/test_laboratory_access_matrix.py: dono abre `/tasks/{id}` da própria tarefa (200)

**Checkpoint**: SC-003.

## Phase 5: User Story 3 - Regras por perfil (P2)

**Goal**: matriz de contracts/access-matrix.md coberta.

**Independent Test**: matriz de perfil por operação sobre `LAB_ACCESS_TEMPLATE`.

- [X] T013 [P] [US3] Em tests/integration/database/test_laboratory_access_matrix.py, ler a execução de B (`level='view'`), parametrizado: laboratório líder designado pelo próprio laboratório B (FR-007), Grupo de Seleção de Amostras, estatístico e participante por B sem vínculo ativo → `NotFoundError`; `group_manager`, Admin, BraCVAM → concede
- [X] T014 [P] [US3] Em tests/integration/database/test_laboratory_access_matrix.py, concluir a execução de B: laboratório líder, Grupo de Seleção de Amostras e estatístico → `AuthorizationError` da atividade sem citar laboratório; BraCVAM sem `bracvam` em `edit_roles` → `AuthorizationError`; `group_manager` com conflito de interesse vigente lê a execução de B e recebe `AuthorizationError` ao concluir
- [X] T015 [P] [US3] Em tests/integration/database/test_laboratory_access_matrix.py, usuário líder por B e participante por A: lê e conclui a execução de A; ler ou concluir a de B → `NotFoundError`
- [X] T016 [P] [US3] Em tests/api/routers/test_laboratory_access_matrix.py, parametrizado por perfil (laboratório líder, líder por B e participante por A, Grupo de Seleção de Amostras, estatístico): `/tasks?activity_key=receipt` só com tarefas próprias, `/tasks/{id}` da tarefa de B → 404, linha do tempo sem `LABORATORY_RUN_COMPLETED` de B
- [X] T017 [P] [US3] Em tests/api/routers/test_laboratory_access_matrix.py, gestão: Admin e BraCVAM listam as 3 tarefas, abrem `/tasks/{id}` de B (200) e veem a conclusão de B na linha do tempo; `group_manager` abre `/tasks/{id}` de B (200)
- [X] T018 [US3] Rodar a matriz completa

**Checkpoint**: SC-004.

## Phase 6: User Story 4 - Uma designação de participante por usuário no processo (P2)

**Goal**: FR-008 registrado em teste (regra existente, research R3).

**Independent Test**: designar o mesmo usuário participante por A e por B.

- [X] T019 [P] [US4] Em tests/api/routers/test_laboratory_access_matrix.py: `POST /processes/{id}/participants` com `participating_laboratory` por B para usuário já participante por A (com vínculo com os dois) → 409 `duplicate` e nenhuma designação nova; após revogar a de A → 201; usuário líder por A designado participante por B → 201 (regra existente)
- [X] T020 [P] [US4] Em tests/integration/database/test_laboratory_access_matrix.py: aceite de convite de `participating_laboratory` por B para usuário já participante por A → `ConflictError` com `code='duplicate'` (regra existente)

## Phase 7: Polish

- [X] T021 Atualizar a seção "Arquitetura de Permissões e Acesso" do README.md com as regras de contracts/access-matrix.md (skill `stop-slop`)
- [X] T022 `ruff check` e `ruff format --check` só nos arquivos alterados pela branch
- [X] T023 Rodar a suíte completa (1539 passed, 1 skipped). A validação exigiu dois ajustes fora das tarefas: a jornada tests/integration/journeys/etapa_3_execucao_validacao/test_per_laboratory_journey.py passa a esperar `NotFoundError` (FR-001), e a migração de merge migrations/versions/5af69c71be3c_merge_notifications_and_lab_runs.py une as duas heads que a develop herdou dos PRs #67 e #68
- [X] T024 Atualizar checklists/requirements.md com as notas de validação e marcar as tarefas concluídas

## Dependencies

- T001 antes dos testes de matriz (T006, T007, T011–T020).
- T002 antes de T003 e T009.
- US1 (T005–T010) antes de US3: a matriz depende da regra de R2.
- US2 e US4 independem de US1 no código; rodam depois de T001.

## Parallel Example

```text
T006, T007 (arquivos diferentes) em paralelo; depois T008 → T009.
T013–T017 escrevem nos dois arquivos de matriz: paralelos entre arquivos, sequenciais dentro do mesmo arquivo.
```

## Implementation Strategy

MVP = Phases 1–3 (resposta 404 uniforme). Depois US2 e US3 (matriz), US4
(registro da regra de designação), Polish.
