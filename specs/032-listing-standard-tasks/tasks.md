---

description: "Task list — Spec 032: Padrão de listagens e lista de tarefas para o quadro de atividades"
---

# Tasks: Padrão de listagens e lista de tarefas para o quadro de atividades

**Input**: Design documents from `specs/032-listing-standard-tasks/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [quickstart.md](quickstart.md)

**Tests**: Obrigatórios (AGENTS.md). Seguem `.agents/skills/fastapi-testing-methodology/`: cada tarefa de teste cobre um comportamento observável, e os testes vêm antes da implementação de cada história. Sucesso, cada erro/status, autorização, isolamento, ordenação e paginação ficam em tarefas separadas.

Níveis de risco:
- **Crítico:** visibilidade em `data`, `facets` e `summary`, e coerência de `can_act` com a autorização real. Camadas: integração da cláusula SQL, API e segurança.
- **Alto:** rodada vigente, paginação e ordem estável. Camadas: unidade e API.
- **Médio:** envelope, referências e OpenAPI. Camada: API.

**Organization**: Por user story. As fases seguem a dependência, não o número da história: US5 → US4 → US3 → US1 → US2. O envelope e as referências mudam o formato que as outras histórias verificam (ver [Dependencies](#dependencies--execution-order)).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: user story da spec (US1…US5)
- Comandos com `poetry run`; testes isolados com `--no-cov`

## Convenções de teste desta feature

- Autenticação nos testes de API: `authenticate(client, user)` de `tests/api/routers/test_rbac_router.py`.
- Perfis: fixtures `bracvam_user` (cargo global `bracvam`) e `ai_eval_admin` (perfil Administrador, cargo global `admin`) de `tests/conftest.py`. Cargos no processo: `grant_cargo(session, process_id=..., user=..., role_key=...)` de `tests/factories/participant_factory.py`. Conflito: `ConflictInterestDeclarationFactory` do mesmo arquivo.
- Dados da lista: helpers de `tests/factories/task_listing_factory.py` (T003). Eles criam tarefas com status, prazo e rodada controlados, sem depender do fluxo real.
- Pré-avaliação por IA em andamento: fluxo real com `publish_evaluation_and_assign` e `create_and_submit_process` de `tests/ai_eval_helpers.py` (template `validated_method_dossier`). O background fica desligado nos testes (`tests/conftest.py`), então a execução fica `in_progress` até alguém chamar `pre_evaluation_service._execute`. Fixture `fake_provider` quando o `_execute` for necessário.
- "Agora" nos testes de atrasadas: prazos a ±2 dias de `datetime.now(UTC).replace(tzinfo=None)`, sem congelar o relógio.
- Endpoints mutáveis exigem o header `Origin: https://testserver`. `GET /tasks` não exige.

---

## Phase 1: Setup

**Purpose**: linha de base.

- [X] T001 Rodar `poetry run pytest -q` e `poetry run ruff check .` na branch `feat/032-listing-standard-tasks` e anotar em `specs/032-listing-standard-tasks/tasks.md` (seção Notes) quantos testes passaram e falharam. Falhas pré-existentes ficam listadas e não são atribuídas a esta feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: cálculo da paginação, envelope genérico, referências e helper de dados de teste.

- [X] T002 [P] Em `tests/unit/core/test_listing.py`, `test_pagination_middle_page`: `build_pagination(page=2, per_page=20, total=45)` devolve `total_pages=3`, `has_next=True`, `has_prev=True`.
- [X] T003 [P] Criar `tests/factories/task_listing_factory.py` com:
  - `LISTING_TEMPLATE` (dicionário no formato de `SAMPLE_TEMPLATE` de `tests/factories/sample_factory.py`), com duas fases e cinco atividades:
    - `phase_1_submission_triage` (`order_index: 1`): `proposal_submission` (`access.edit: ['proponent']`), `triage_evaluation` (`access.edit: ['bracvam']`) e `submission_return_review` (`access.edit: ['proponent']`);
    - `phase_2_role_assignment` (`order_index: 2`): `assign_group_manager` (`access.edit: ['proponent']`) e `sample_definition` (`access.edit: ['sample_selection_group']`, `activity_type: 'sample_definition'`);
    - todas com `access.view: []` e sem dependências.
  - `async def listing_process(session, *, proponent, title='Processo')`: sincroniza o template com `sync_template_from_dict`, instancia com `instantiate_process`, dá ao `proponent` o cargo `proponent` (`grant_cargo`), marca `deleted_at` em toda `Task` criada automaticamente e devolve o `ProcessInstance`.
  - `async def add_task(session, process, activity_key, *, run_number=1, status='READY', due_date=None)`: cria `ActivityRun` e `Task` na atividade (título = nome da atividade, `assigned_role` = primeiro cargo de `edit_roles`) e devolve a `Task`.
- [X] T004 Em `tests/unit/core/test_listing.py`, `test_pagination_empty`: `total=0` devolve `total_pages=0`, `has_next=False`, `has_prev=False`.
- [X] T005 Em `tests/unit/core/test_listing.py`, `test_pagination_page_beyond_last`: `page=5, per_page=20, total=45` devolve `total_pages=3`, `has_next=False`, `has_prev=True`.
- [X] T006 Em `tests/unit/core/test_listing.py`, `test_pagination_exact_multiple`: `page=2, per_page=20, total=40` devolve `total_pages=2`, `has_next=False`.
- [X] T007 Criar `src/pivma/core/listing.py` com `build_pagination(page: int, per_page: int, total: int) -> Pagination`. Regras de data-model: "`total_pages` = `ceil(total_items / per_page)`; 0 sem itens"; "`has_next` = `page < total_pages`"; "`has_prev` = `page > 1 and total_pages > 0`". Sem consulta ao banco (research R4).
- [X] T008 Em `src/pivma/schemas.py`, criar a seção "Listagens" com:
  - `Pagination` (`page`, `per_page`, `total_items`, `total_pages`, `has_next`, `has_prev`);
  - `SortApplied` (`by: str`, `order: Literal['asc', 'desc']`);
  - `ListEnvelope(BaseModel, Generic[ItemT, FiltersT, FacetsT, SummaryT])` com `data: list[ItemT]`, `pagination`, `filters_applied: FiltersT`, `sort: SortApplied`, `facets: FacetsT | None = None` e `summary: SummaryT | None = None`;
  - um `@model_serializer(mode='wrap')` que remove só as chaves `facets` e `summary` quando forem `None` (research R4).

  Todos os campos com `Field(description=...)`.
- [X] T009 Em `tests/unit/core/test_listing.py`, `test_envelope_omits_facets_and_summary_when_none`: um `ListEnvelope` concreto sem `facets`/`summary`, serializado com `model_dump(mode='json')`, não tem essas chaves, e um item com campo `None` mantém a chave com `null`.
- [X] T010 Em `tests/unit/core/test_listing.py`, `test_envelope_keeps_facets_and_summary_when_set`: com `facets` e `summary` preenchidos, as duas chaves aparecem.
- [X] T011 Em `src/pivma/schemas.py`, criar a seção "Referências" com:
  - `ProcessRef`: `id: UUID` ("Identificador do processo"), `code: str` ("Código do processo"), `title: str` ("Título do processo");
  - `PhaseRef`: `key: str` ("Chave da fase no template"), `order: int` ("Ordem da fase no processo").

  Todo campo com `Field(description=...)` (FR-011).

**Checkpoint**: `poetry run pytest tests/unit/core/test_listing.py -q --no-cov` verde.

---

## Phase 3: User Story 5 - Envelope único de listagem (Priority: P2)

**Goal**: `GET /tasks` responde no envelope com paginação por página e ordem padrão.

**Independent Test**: a resposta tem exatamente `data`, `pagination`, `filters_applied` e `sort`, e o OpenAPI descreve o envelope.

### Tests for User Story 5

- [X] T012 [P] [US5] Em `tests/api/routers/test_tasks_listing.py`, `test_task_list_returns_envelope_blocks`: sem `include`, as chaves de primeiro nível são exatamente `{'data', 'pagination', 'filters_applied', 'sort'}`.
- [X] T013 [US5] Mesmo arquivo, `test_task_list_filters_applied_echoes_defaults`: sem parâmetros, `filters_applied == {'status': [], 'activity_key': [], 'phase_order': None, 'process_id': None, 'role': None, 'actionable': False, 'current_run': True, 'overdue': False}` e `sort == {'by': 'due_date', 'order': 'asc'}`.
- [X] T014 [US5] Mesmo arquivo, `test_task_list_default_pagination`: sem `page`/`per_page`, `pagination.page == 1` e `pagination.per_page == 20`.
- [X] T015 [US5] Mesmo arquivo, `test_task_list_requires_authentication`: sem sessão, `401`.
- [X] T016 [P] [US5] Em `tests/api/routers/test_tasks_openapi.py`, `test_openapi_task_list_is_envelope`: `app.openapi()` descreve a resposta `200` de `GET /tasks` como objeto (não array) com `data` (itens `TaskSummary`), `pagination`, `filters_applied` e `sort` obrigatórios, e `facets`/`summary` opcionais.

### Implementation for User Story 5

- [X] T017 [US5] Em `src/pivma/schemas.py`, criar:
  - `TaskStatus = Literal['READY', 'COMPLETED', 'CANCELLED']`;
  - `TaskFiltersApplied`: `status: list[TaskStatus]`, `activity_key: list[str]`, `phase_order: int | None`, `process_id: UUID | None`, `role: str | None`, `actionable: bool`, `current_run: bool`, `overdue: bool`;
  - `TaskFacets`: `activity_key: dict[str, int]`, `status: dict[str, int]`;
  - `TaskListSummary`: `ai_pre_evaluation_in_progress: int`;
  - `TaskListResponse = ListEnvelope[TaskSummary, TaskFiltersApplied, TaskFacets, TaskListSummary]`.

  Todos com descrição. Se o OpenAPI gerar nome ilegível para a especialização, declarar `class TaskListResponse(ListEnvelope[...])` (plan, re-check).
- [X] T018 [US5] Em `src/pivma/routers/tasks.py`, mudar `list_tasks` para `response_model=TaskListResponse`:
  - novos parâmetros `page: int = Query(1, ge=1)` e `per_page: int = Query(20, ge=1, le=100)`;
  - separar a consulta filtrada (sem ordem) da página;
  - `total_items` via `select(func.count()).select_from(filtered.subquery())`;
  - ordem padrão `Task.due_date.asc().nulls_last(), Task.created_at.asc(), Task.id.asc()` (research R7);
  - página com `offset((page - 1) * per_page).limit(per_page)`;
  - `pagination` via `build_pagination` e `filters_applied` e `sort` preenchidos.

  Manter os filtros `status`, `role` e `process_id` como estão até a US3.
- [X] T019 [US5] Em `tests/integration/journeys/conftest.py`, `process_tasks` lê `response.json()['data']`.

**Checkpoint**: T012–T016 verdes.

---

## Phase 4: User Story 4 - Referências resumidas (Priority: P2)

**Goal**: o processo e a etapa de cada tarefa vêm como `ProcessRef` e `PhaseRef`.

**Independent Test**: um item tem `process` com `{id, code, title}`, `phase` com `{key, order}` e nenhum dos campos achatados antigos.

### Tests for User Story 4

- [X] T020 [P] [US4] Em `tests/api/routers/test_tasks_listing.py`, `test_task_item_process_is_reference`: `item['process'] == {'id', 'code', 'title'}` com os valores do processo, e `process_id`, `process_code` e `process_title` não estão no item.
- [X] T021 [US4] Mesmo arquivo, `test_task_item_phase_is_reference`: `item['phase'] == {'key': 'phase_1_submission_triage', 'order': 1}`, e `phase_key` e `phase_order` não estão no item.
- [X] T022 [P] [US4] Em `tests/api/routers/test_tasks_openapi.py`, `test_openapi_reference_fields_have_descriptions`: todo campo de `ProcessRef` e `PhaseRef` em `components.schemas` tem `description` não vazio.

### Implementation for User Story 4

- [X] T023 [US4] Em `src/pivma/schemas.py`, `TaskSummary`:
  - troca `process_id`, `process_code` e `process_title` por `process: ProcessRef`;
  - troca `phase_key` e `phase_order` por `phase: PhaseRef`;
  - `status` passa a `TaskStatus`;
  - os demais campos ficam como estão (data-model, "TaskSummary").

  `TaskDetail` não muda (FR-026).
- [X] T024 [US4] Em `src/pivma/routers/tasks.py`, `_task_summary` monta `ProcessRef` e `PhaseRef`.

### Ajuste dos testes existentes (envelope + referências)

Cada tarefa troca `response.json()` por `response.json()['data']` e os campos achatados por `process`/`phase`, sem mudar o que o teste verifica.

- [X] T025 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_tasks_router.py`
- [X] T026 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_tasks_visibility.py`
- [X] T027 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_tasks_summary_fields.py`
- [X] T028 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_activity_type_extension.py`
- [X] T029 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_triage_decision.py`
- [X] T030 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_invites_router.py`
- [X] T031 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_activity_parallel_visibility.py`
- [X] T032 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_sample_activity_unlock.py`
- [X] T033 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_samples_access.py`
- [X] T034 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_participant_router.py`
- [X] T035 [P] [US4] Ajustar ao envelope e às referências `tests/api/routers/test_invite_acceptance.py`
- [X] T036 [P] [US4] Ajustar ao envelope e às referências `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_via_ai.py`
- [X] T037 [P] [US4] Ajustar ao envelope e às referências `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sample_definition_journey.py`
- [X] T038 [US4] Rodar `grep -rn "/tasks" tests` e ajustar qualquer outro arquivo que ainda leia a lista antiga. Registrar em Notes os arquivos a mais.

**Checkpoint**: `poetry run pytest -q --no-cov` verde, com a suíte inteira no formato novo.

---

## Phase 5: User Story 3 - Filtrar, ordenar e paginar (Priority: P1)

**Goal**: filtros novos, rodada vigente como padrão, ordenação configurável e paginação validada.

**Independent Test**: com 45 tarefas, a página 2 de 20 devolve os itens 21–40 com os totais corretos, e a ordem se repete.

### Tests for User Story 3 (`tests/api/routers/test_tasks_listing.py`)

Paginação:
- [X] T039 [US3] `test_task_list_second_page_of_45`: 45 tarefas `READY` visíveis ao BraCVAM; `page=2&per_page=20` devolve 20 itens, `total_items=45`, `total_pages=3`, `has_next=True`, `has_prev=True`.
- [X] T040 [US3] `test_task_list_page_beyond_last_is_empty`: com as mesmas 45 tarefas, `page=5` responde `200`, `data=[]`, `total_items=45`, `has_next=False`.
- [X] T041 [US3] `test_task_list_rejects_per_page_above_100`: `per_page=101` → `422`.
- [X] T042 [US3] `test_task_list_rejects_page_zero`: `page=0` → `422`.
- [X] T043 [US3] `test_task_list_pages_have_no_gaps_or_repeats`: 5 tarefas com o mesmo `due_date`; percorrer `per_page=2` (3 páginas) devolve os 5 ids, sem repetição.
- [X] T044 [US3] `test_task_list_total_ignores_invisible_tasks`: tarefas de um processo em que o proponente não tem atribuição não entram em `total_items` para ele.

Ordenação:
- [X] T045 [US3] `test_task_list_default_order_due_date_nulls_last`: tarefas com prazos D+2, D+1 e sem prazo vêm na ordem D+1, D+2, sem prazo.
- [X] T046 [US3] `test_task_list_desc_keeps_nulls_last`: `sort_order=desc` devolve D+2, D+1, sem prazo; `sort == {'by': 'due_date', 'order': 'desc'}`.
- [X] T047 [US3] `test_task_list_sort_by_created_at`: `sort_by=created_at` ordena pela criação; `sort.by == 'created_at'`.
- [X] T048 [US3] `test_task_list_rejects_unknown_sort_by`: `sort_by=title` → `422`.
- [X] T049 [US3] `test_task_list_rejects_unknown_sort_order`: `sort_order=up` → `422`.

Rodada vigente:
- [X] T050 [US3] `test_task_list_defaults_to_current_run`: `triage_evaluation` com rodadas 1 (`COMPLETED`) e 2 (`READY`); sem parâmetro, só a rodada 2 aparece e `filters_applied.current_run is True`.
- [X] T051 [US3] `test_task_list_current_run_false_includes_history`: `current_run=false` devolve as rodadas 1 e 2.

Filtros:
- [X] T052 [US3] `test_task_list_filters_multiple_status`: `status=READY&status=CANCELLED` devolve as duas e não a `COMPLETED`.
- [X] T053 [US3] `test_task_list_rejects_unknown_status`: `status=FOO` → `422` (antes, lista vazia).
- [X] T054 [US3] `test_task_list_filters_multiple_activity_keys`: `activity_key=proposal_submission&activity_key=triage_evaluation` exclui `submission_return_review`.
- [X] T055 [US3] `test_task_list_filters_phase_order`: `phase_order=2` devolve só as tarefas da fase 2.
- [X] T056 [US3] `test_task_list_overdue_only_open_past_due`: com `READY` vencida, `READY` no prazo, `READY` sem prazo e `COMPLETED` vencida, `overdue=true` devolve só a `READY` vencida.
- [X] T057 [US3] `test_task_list_keeps_process_and_role_filters`: `process_id` e `role` filtram como antes (regressão).

### Implementation for User Story 3

- [X] T058 [US3] Em `src/pivma/routers/tasks.py`, novos parâmetros:
  - `status: list[TaskStatus] = Query([])`;
  - `activity_key: list[str] = Query([])`;
  - `phase_order: int | None = Query(None, ge=1)`;
  - `current_run: bool = True`;
  - `overdue: bool = False`;
  - `sort_by: Literal['due_date', 'created_at'] = 'due_date'`;
  - `sort_order: Literal['asc', 'desc'] = 'asc'`.

  Aplicar `Task.status.in_(status)` e `ActivityInstance.key.in_(activity_key)` quando não vazios, e `Phase.order_index == phase_order` com join em `ActivityInstance.phase`.
- [X] T059 [US3] No mesmo arquivo, filtro de rodada vigente quando `current_run`: `ActivityRun.run_number == select(func.max(r.run_number)).where(r.activity_instance_id == ActivityRun.activity_instance_id, r.deleted_at.is_(None)).scalar_subquery()` com `r = aliased(ActivityRun)` (research R3).
- [X] T060 [US3] No mesmo arquivo, filtro `overdue`: `Task.status == 'READY'` e `Task.due_date < datetime.now(UTC).replace(tzinfo=None)`. A comparação é naive em UTC, "Tarefa sem prazo nunca está atrasada" (research R8).
- [X] T061 [US3] No mesmo arquivo, ordenação por `sort_by`/`sort_order` com `nulls_last()` nas duas direções e desempate `Task.created_at.asc(), Task.id.asc()`. `sort` e `filters_applied` refletem os valores efetivos (research R7).
- [X] T062 [US3] Em `tests/api/routers/test_tasks_summary_fields.py`, `test_task_summary_distinguishes_current_run_after_revision` passa `current_run=false`, porque depende do histórico. Registrar em Notes qualquer outro teste que precisou do mesmo ajuste.

**Checkpoint**: T039–T057 verdes e suíte completa verde.

---

## Phase 6: User Story 1 - Só as tarefas em que posso agir (Priority: P1) 🎯 MVP

**Goal**: `can_act` em cada item e o filtro `actionable`, com a regra de `require_activity_access(..., 'edit')`.

**Independent Test**: o BraCVAM com 3 triagens e 2 submissões recebe só as 3 triagens com `actionable=true`, e a lista completa marca 3 `can_act: true` e 2 `false`.

### Tests for User Story 1

Cláusula de conflito (`tests/integration/database/test_conflict_clause.py`):
- [X] T063 [P] [US1] `test_conflict_clause_matches_active_conflict`: usuário com atribuição ativa e última declaração `has_conflict=True` no processo A; a cláusula aplicada a uma atividade de A é verdadeira e bate com `has_current_conflict`.
- [X] T064 [US1] `test_conflict_clause_ignores_superseded_declaration`: a declaração com conflito é seguida de outra sem conflito na mesma atribuição; a cláusula é falsa.
- [X] T065 [US1] `test_conflict_clause_ignores_revoked_assignment`: conflito numa atribuição revogada; a cláusula é falsa.
- [X] T066 [US1] `test_conflict_clause_is_scoped_to_user_and_process`: o conflito de outro usuário, ou do mesmo usuário em outro processo, não torna a cláusula verdadeira.

API (`tests/api/routers/test_tasks_actionable.py`):
- [X] T067 [P] [US1] `test_bracvam_actionable_returns_only_triage`: 3 processos com `triage_evaluation` `READY` e 2 com `proposal_submission` `READY`; `actionable=true` como `bracvam_user` devolve só as 3 triagens, todas com `can_act: true`.
- [X] T068 [US1] `test_bracvam_full_list_flags_can_act`: mesmo cenário sem `actionable`; 5 itens, `can_act` verdadeiro só nas triagens.
- [X] T069 [US1] `test_proponent_actionable_returns_own_submission`: o proponente vê só a própria submissão, com `can_act: true`.
- [X] T070 [US1] `test_admin_sees_triage_but_cannot_act`: `ai_eval_admin` vê a triagem com `can_act: false`, e `actionable=true` não a devolve.
- [X] T071 [US1] `test_conflict_removes_can_act`: `bracvam_user` com atribuição no processo A (`grant_cargo`) e conflito vigente declarado; a triagem de A tem `can_act: false` e sai de `actionable=true`, e a triagem do processo B continua com `can_act: true`.
- [X] T072 [US1] `test_process_cargo_grants_can_act`: usuário com cargo `sample_selection_group` no processo tem `can_act: true` em `sample_definition`, e o `bracvam_user` vê a mesma tarefa com `can_act: false`.
- [X] T073 [US1] `test_actionable_total_counts_only_actionable`: `actionable=true&per_page=1` informa `total_items` igual ao número de tarefas em que o usuário pode agir.
- [X] T074 [US1] `test_can_act_agrees_with_activity_authorization`: para cada item devolvido a `bracvam_user`, `ai_eval_admin` e ao proponente, `require_activity_access(session, user.id, activity, 'edit')` não lança exceção se e somente se `can_act` é verdadeiro (SC-002).

### Implementation for User Story 1

- [X] T075 [US1] Em `src/pivma/core/authorization.py`, criar `current_conflict_clause(user_id) -> ColumnElement[bool]`: `EXISTS` de `ConflictInterestDeclaration` com `has_conflict` verdadeiro, ligada a uma `Assignment` do usuário, ativa (`revoked_at` e `deleted_at` nulos), com `process_instance_id == ActivityInstance.process_instance_id`, e `NOT EXISTS` de declaração mais recente (`declared_at` maior, ou igual com `id` maior) para a mesma atribuição (research R2).
- [X] T076 [US1] Em `src/pivma/routers/tasks.py`, montar a expressão `can_act` uma vez por pedido (research R1): `(ActivityInstance.edit_roles.overlap(array(global_cargos)) OR EXISTS(process_cargos_scope(user_id).where(Assignment.process_instance_id == ActivityInstance.process_instance_id, Assignment.role_key == any_(ActivityInstance.edit_roles)))) AND NOT current_conflict_clause(user_id)`. Com `global_cargos` vazio, omitir o `overlap`.
- [X] T077 [US1] No mesmo arquivo, selecionar `can_act` como coluna rotulada junto com `Task` na consulta da página e passar o valor para `_task_summary`. Parâmetro `actionable: bool = False`, que, quando verdadeiro, aplica a mesma expressão como filtro.
- [X] T078 [US1] Em `src/pivma/schemas.py`, `TaskSummary` ganha `can_act: bool = Field(description='O usuário pode agir nesta tarefa: tem concessão de editar a atividade e não tem conflito de interesse vigente no processo')`.

**Checkpoint**: T063–T074 verdes.

---

## Phase 7: User Story 2 - Quadro com contagens em uma chamada (Priority: P1)

**Goal**: `include=facets` e `include=summary`.

**Independent Test**: com 4 processos em avaliação pela IA, 2 submissões, 3 triagens e 1 revisão abertas, uma chamada devolve contagens 2/3/1 e resumo 4.

### Tests for User Story 2

Contagens (`tests/api/routers/test_tasks_facets.py`):
- [X] T079 [P] [US2] `test_facets_count_by_activity_key`: com 2 `proposal_submission`, 3 `triage_evaluation` e 1 `submission_return_review` `READY`, `phase_order=1&status=READY&include=facets` como BraCVAM devolve `facets.activity_key == {'proposal_submission': 2, 'triage_evaluation': 3, 'submission_return_review': 1}`.
- [X] T080 [US2] `test_facets_count_by_status`: `facets.status` conta `READY`, `COMPLETED` e `CANCELLED` do conjunto filtrado; status sem itens não aparecem.
- [X] T081 [US2] `test_facets_ignore_pagination`: `per_page=2&include=facets` traz 2 itens e as mesmas contagens do T079.
- [X] T082 [US2] `test_facets_absent_without_include`: sem `include`, a chave `facets` não existe.
- [X] T083 [US2] `test_facets_respect_visibility`: tarefas de processos em que o proponente não tem atribuição não entram nas contagens dele.
- [X] T084 [US2] `test_facets_respect_current_run`: uma triagem com rodadas 1 e 2 conta 1 no padrão e 2 com `current_run=false`.
- [X] T085 [US2] `test_facets_apply_own_dimension_filter`: `activity_key=triage_evaluation&include=facets` devolve `facets.activity_key == {'triage_evaluation': 3}` (spec, Assumptions).
- [X] T086 [US2] `test_task_list_rejects_unknown_include`: `include=meta` → `422`.

Resumo (`tests/api/routers/test_tasks_summary.py`, fluxo real de IA; ver Convenções):
- [X] T087 [P] [US2] `test_summary_counts_ai_in_progress`: 4 processos submetidos com execução `in_progress`; `include=summary` como BraCVAM devolve `summary.ai_pre_evaluation_in_progress == 4`.
- [X] T088 [US2] `test_summary_absent_without_include`: sem `include`, a chave `summary` não existe.
- [X] T089 [US2] `test_summary_ignores_finished_runs`: executar `pre_evaluation_service._execute` num dos processos (`fake_provider`) reduz a contagem para 3.
- [X] T090 [US2] `test_summary_counts_process_once`: processo com uma execução `failed` e uma `in_progress` (criada com `EvaluationRunFactory` na mesma `activity_run`) conta 1.
- [X] T091 [US2] `test_summary_respects_visibility`: proponente A com 2 processos em avaliação e proponente B com 1; `include=summary` como A devolve 2.
- [X] T092 [US2] `test_summary_respects_process_id`: `process_id=<um deles>&include=summary` devolve 1.
- [X] T093 [US2] `test_summary_ignores_other_task_filters`: `phase_order=2&status=COMPLETED&include=summary` ainda devolve os 4 processos.
- [X] T094 [US2] `test_summary_ignores_deleted_runs`: execução `in_progress` com `deleted_at` preenchido não conta.

### Implementation for User Story 2

- [X] T095 [US2] Em `src/pivma/routers/tasks.py`, parâmetro `include: list[Literal['facets', 'summary']] = Query([])`. Com `facets`, dois `GROUP BY` sobre a subconsulta filtrada (a mesma de `total_items`), por `ActivityInstance.key` e por `Task.status`, que preenchem `TaskFacets` (research R5).
- [X] T096 [US2] No mesmo arquivo, com `summary`: `count(distinct EvaluationRun.process_instance_id)` com `EvaluationRun.status == 'in_progress'` e `EvaluationRun.deleted_at` nulo, join `ActivityRun` → `ActivityInstance` → `ProcessInstance`, aplicando `process_visibility_clause`, `activity_view_clause` e o filtro `process_id` quando houver. Os demais filtros de tarefa não entram (research R6).

**Checkpoint**: T079–T094 verdes.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T097 [P] Em `tests/integration/journeys/etapa_1_submissao_triagem/test_stage_one_board.py`, `test_bracvam_builds_stage_one_board_in_one_call` (SC-001), a partir de um deploy novo e pela API pública, com os helpers de `tests/integration/journeys/conftest.py`:
  - 2 processos do template 1 com submissão em rascunho;
  - 2 processos do template 4 submetidos com a avaliação de IA publicada, que ficam `in_progress`;
  - 1 processo do template 1 submetido e aguardando triagem.

  O triador BraCVAM chama `GET /tasks?phase_order=1&status=READY&include=facets&include=summary`: `facets.activity_key` traz `proposal_submission: 2` e `triage_evaluation: 1`, e `summary.ai_pre_evaluation_in_progress == 2`. Com `actionable=true`, só a triagem.
- [X] T098 [P] Atualizar `README.md`:
  - na seção "Processos, Formulários e Triagem", o item **Tarefas** passa a descrever o envelope, os filtros, `current_run` como padrão, `can_act`/`actionable`, a ordenação, `include=facets|summary` e o limite de 100 por página;
  - nova subseção em "Diretrizes de Integração (Frontend)" com o padrão de listagem (envelope, paginação por página, referências resumidas), avisando que as demais listagens migram na Spec 033.
- [X] T099 Rodar `poetry run pytest -q` com cobertura e `poetry run ruff check . && poetry run ruff format --check .`, e comparar com a linha de base de T001. Registrar em Notes o resultado e a cobertura de `src/pivma/routers/tasks.py` e `src/pivma/core/listing.py`.
- [ ] T100 Executar o roteiro manual de `specs/032-listing-standard-tasks/quickstart.md` numa API local e registrar em Notes o que foi executado. Se não for possível, registrar o motivo.
- [X] T101 Registrar em Notes as mudanças de contrato para o changelog único do frontend (Specs 032–034): envelope, `process`/`phase` como referências, `current_run` padrão, `status` inválido → `422`, `can_act`, filtros e `include`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependência.
- **Foundational (Phase 2)**: depende da Phase 1; bloqueia todas as histórias.
- **US5 (Phase 3)**: depende da Phase 2. Muda o formato da resposta.
- **US4 (Phase 4)**: depende da US5. Os ajustes dos testes existentes (T025–T038) tratam envelope e referências de uma vez, para cada arquivo ser alterado uma só vez.
- **US3 (Phase 5)**: depende da US4, porque os testes verificam o formato final.
- **US1 (Phase 6)**: depende da US3, porque `actionable` e `total_items` usam a consulta filtrada separada.
- **US2 (Phase 7)**: depende da US3 (conjunto filtrado e rodada vigente). Independe da US1.
- **Polish (Phase 8)**: depende de todas.

### Within Each User Story

- Os testes são escritos antes e falham sem a implementação.
- Primeiro schemas, depois o roteador.

### Parallel Opportunities

- T002 e T003 em paralelo (arquivos diferentes).
- T012 e T016 em paralelo; T020 e T022 em paralelo.
- T025–T037: um arquivo cada, todos em paralelo.
- T063 (arquivo de integração) e T067 (arquivo de API) em paralelo.
- US1 e US2 podem correr em paralelo depois da US3. As duas mexem em `src/pivma/routers/tasks.py`: coordenar a edição ou fazer em sequência.
- T097 e T098 em paralelo.

## Parallel Example: User Story 4

```text
T025 test_tasks_router.py        T031 test_activity_parallel_visibility.py
T026 test_tasks_visibility.py    T032 test_sample_activity_unlock.py
T027 test_tasks_summary_fields.py T033 test_samples_access.py
T028 test_activity_type_extension.py T034 test_participant_router.py
T029 test_triage_decision.py     T035 test_invite_acceptance.py
T030 test_invites_router.py      T036/T037 jornadas
```

## Parallel Example: User Story 1

```text
T063–T066  tests/integration/database/test_conflict_clause.py
T067–T074  tests/api/routers/test_tasks_actionable.py
```

## Implementation Strategy

### MVP First

A US1 é o MVP de produto, mas depende do formato novo. O caminho mínimo é:

1. Phase 1 e Phase 2.
2. US5 e US4, que entregam o formato novo com a suíte verde.
3. US3, com a rodada vigente e a paginação.
4. US1, que entrega `actionable` e `can_act`, o pedido original do BraCVAM.

### Incremental Delivery

1. US5 + US4: formato final e testes antigos ajustados.
2. US3: filtros, ordem e paginação.
3. US1: `can_act` e `actionable` (MVP).
4. US2: contagens e resumo, que completam o quadro.
5. Jornada, README e notas do changelog.

Um PR único na `develop` ao final, como combinado. O frontend recebe o changelog junto com as Specs 033 e 034.

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- Commit após cada tarefa ou grupo lógico; mensagens em português no padrão `feat(tasks): ...` / `test(tasks): ...`.
- **Linha de base (T001)**: 1020 passaram, 1 pulado, 0 falhas; `ruff check .` limpo. A suíte rodou em paralelo com o início da implementação, mas os módulos foram carregados antes das edições; o número bate com o da `develop` depois do PR #61.
- **T003**: `instantiate_process` já dá ao criador o cargo `proponent`, então `listing_process` não chama `grant_cargo` para ele. O helper também marca como excluídas as execuções criadas pela instanciação, e não só as tarefas: sem isso, `add_task(run_number=1)` violaria `uq_activity_runs_number_active`.
- **T008**: o `model_serializer(mode='wrap')` do envelope ficou **sem anotação de retorno**. Com `-> dict[str, Any]`, o OpenAPI trocava o schema do envelope por um objeto genérico (`additionalProperties: true`); T016 detectou.
- **T025–T038**: além dos 13 arquivos listados, nenhum outro lia `GET /tasks` (`grep -rn "/tasks" tests`). O `ruff format` local (0.16.2) reformatou `tests/api/routers/test_user_router.py`, que não é desta feature; a alteração foi desfeita.
- **T062**: só `test_task_summary_distinguishes_current_run_after_revision` dependia do histórico e passou a usar `current_run=false`.
- **T047**: dentro da transação do teste, `now()` devolve o mesmo valor para todas as tarefas; o teste de `sort_by=created_at` grava `created_at` explicitamente.
- **T100**: não executada. O roteiro exige criar processos, usuários e submissões numa API local ligada ao banco de desenvolvimento, o que altera dados do ambiente do usuário. A jornada automatizada T097 cobre o mesmo roteiro pela API pública (quadro da etapa 1, contagens, resumo da IA e `actionable`), e os passos 3–7 do quickstart têm testes de API dedicados (T070, T081, T051, T041/T048/T053, T091).
- **T101 — mudanças de contrato para o changelog único (Specs 032–034)**:
  - `GET /tasks` responde num envelope (`data`, `pagination`, `filters_applied`, `sort`; `facets`/`summary` com `include`), não mais numa lista. **Quebra.**
  - Item: `process_id`/`process_code`/`process_title` viram `process {id, code, title}`; `phase_key`/`phase_order` viram `phase {key, order}`. **Quebra.** Novo campo `can_act`.
  - Por padrão, só a rodada vigente de cada atividade (`current_run=true`); o histórico exige `current_run=false`. **Muda comportamento.**
  - `status` desconhecido responde `422` (antes, lista vazia); `status` aceita vários valores.
  - Filtros novos: `activity_key` (repetível), `phase_order`, `actionable`, `overdue`. Ordenação: `sort_by` (`due_date`, `created_at`), `sort_order`. Paginação: `page`, `per_page` (1–100, padrão 20).
  - `include=facets` (contagens por `activity_key` e `status`) e `include=summary` (`ai_pre_evaluation_in_progress`).
  - `GET /tasks/{id}` não muda.
- **T099**: suíte final com `--cov`: **1082 passaram, 1 pulado, 0 falhas** (62 testes a mais que a linha de base). `ruff check .` limpo. Cobertura total 92%; `routers/tasks.py` 100%, `core/listing.py` 100%; em `core/authorization.py` (97%), as linhas descobertas são anteriores a esta feature, e `current_conflict_clause` está coberta. `ruff format --check` acusa só `src/pivma/core/invite_service.py` e `tests/api/routers/test_user_router.py`, os mesmos arquivos fora desta feature já registrados na Spec 031 (diferença de versão do ruff local).
