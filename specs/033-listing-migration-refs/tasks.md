---

description: "Task list — Spec 033: Migração das listagens para o padrão e referências resumidas"
---

# Tasks: Migração das listagens para o padrão e referências resumidas

**Input**: Design documents from `specs/033-listing-migration-refs/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [quickstart.md](quickstart.md)

**Tests**: Obrigatórios (AGENTS.md). Seguem `.agents/skills/fastapi-testing-methodology/`: cada tarefa de teste cobre um comportamento observável, e os testes vêm antes da implementação de cada grupo. Níveis de risco:
- **Crítico:** totais e itens iguais por perfil, principalmente onde o filtro de acesso roda em Python (convites, linha do tempo), e nenhum e-mail em referência de pessoa. Camadas: integração e API.
- **Alto:** paginação e ordem estável em cada listagem, e carregamento de referências sem N+1. Camadas: unidade, integração e API.
- **Médio:** documentação OpenAPI. Camada: API.

**Organization**: Por user story, e dentro da US1 por domínio (catálogo/RBAC, processos, participantes, IA, amostras), com um ponto de verificação por domínio. Ordem: Foundational → US1 → US2 → US3 → US4. Cada história muda o formato que a seguinte verifica.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: user story da spec (US1…US4)
- Comandos com `poetry run`; testes isolados com `--no-cov`

## Convenções de teste desta feature

- Autenticação: `authenticate(client, user)` de `tests/api/routers/test_rbac_router.py`.
- Perfis:
  - `bracvam_user` e `ai_eval_admin` de `tests/conftest.py`;
  - usuário com permissões específicas por `_make_rbac_user(session, system_key=..., name=..., codes=(...))` de `tests/conftest.py`: `users.read` para `/users`, `rbac.read` para `/rbac/*`, `institutional.read` para `/institutional/*`, `ai_evaluations.read` para `/ai-evaluations`.
- Dados:
  - catálogo com `InstitutionFactory`, `LaboratoryFactory` e `UserInstitutionalAffiliationFactory` de `tests/factories/institutional_factory.py`;
  - processos com `bootstrap_all_templates` e `POST /processes`, ou `listing_process` de `tests/factories/task_listing_factory.py`;
  - participantes com `grant_cargo` e `assign_lab` de `tests/factories/sample_factory.py`;
  - convites com os helpers de `tests/factories/invite_factory.py`;
  - amostras com `sample_process` e `substance_payload` de `tests/factories/sample_factory.py`.
- Asserção de envelope: em cada arquivo novo, um helper `_assert_envelope(body, *, sort, filters)` confere as chaves `{'data', 'pagination', 'filters_applied', 'sort'}`, `pagination.page == 1`, `pagination.per_page == 20`, e `sort` e `filters_applied` iguais aos esperados.
- Endpoints mutáveis exigem o header `Origin: https://testserver`.

---

## Phase 1: Setup

- [X] T001 Rodar `poetry run pytest -q` e `poetry run ruff check .` na branch `feat/033-listing-migration-refs` e anotar em `specs/033-listing-migration-refs/tasks.md` (Notes) quantos testes passaram e falharam.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `ListPage`, filtros, helpers de paginação e as referências com carregamento em lote.

### Tests

- [X] T002 [P] Em `tests/unit/core/test_listing.py`, `test_paginate_items_second_page`: `paginate_items(list(range(25)), page=2, per_page=20)` devolve `([20, 21, 22, 23, 24], 25)`.
- [X] T003 Mesmo arquivo, `test_paginate_items_beyond_last`: `page=3` com 25 itens devolve `([], 25)`.
- [X] T004 Mesmo arquivo, `test_list_page_has_no_optional_blocks`: um `ListPage` concreto serializado tem exatamente `{'data', 'pagination', 'filters_applied', 'sort'}`, e `NoFilters()` serializa `{}`.
- [X] T005 [P] Em `tests/integration/database/test_references.py`, `test_user_refs_batch_has_no_email`: `user_refs(session, [u1.id, u2.id])` devolve um `UserRef` por id, com `id`, `username` e `full_name`; `'email'` não aparece em `model_dump()`.
- [X] T006 Mesmo arquivo, `test_user_refs_include_deactivated_user`: um usuário com `deleted_at` preenchido aparece em `user_refs`.
- [X] T007 Mesmo arquivo, `test_laboratory_refs_embed_institution`: `laboratory_refs(session, [lab.id])[lab.id].institution` é o `InstitutionRef` da instituição do laboratório.
- [X] T008 Mesmo arquivo, `test_laboratory_refs_mark_inactive`: laboratório desativado aparece com `active=False`; instituição desativada aparece com `institution.active=False`.
- [X] T009 Mesmo arquivo, `test_refs_ignore_unknown_ids_and_empty_input`: lista vazia devolve `{}` sem consulta; id inexistente não aparece no dicionário.

### Implementation

- [X] T010 Em `src/pivma/schemas.py`, seção "Listagens":
  - criar `ListPage(BaseModel, Generic[ItemT, FiltersT])` com `data`, `pagination`, `filters_applied` e `sort` (mesmas descrições da Spec 032);
  - fazer `ListEnvelope` estender `ListPage` e acrescentar só `facets`, `summary` e o serializer;
  - criar `class NoFilters(BaseModel)` vazio, com docstring "Listagem sem filtros".

  O JSON de `GET /tasks` não pode mudar (research R1).
- [X] T011 Em `src/pivma/core/listing.py`:
  - `PageQuery = Annotated[int, Query(ge=1)]` e `PerPageQuery = Annotated[int, Query(ge=1, le=100)]`;
  - `async def paginate_query(session, stmt, *, order_by, page, per_page) -> tuple[list, int]`: total via `select(func.count()).select_from(stmt.order_by(None).subquery())` e itens com `order_by(*order_by).offset((page - 1) * per_page).limit(per_page)`, usando `session.scalars`;
  - `def paginate_items(items, page, per_page) -> tuple[list, int]` (research R2, R3).
- [X] T012 Em `src/pivma/schemas.py`, seção "Referências", criar com `Field(description=...)` em todos os campos:
  - `UserRef` (`id`, `username`, `full_name`);
  - `ProfileRef` (`id`, `name`, `active`, `extra='forbid'`);
  - `InstitutionRef` (`id`, `name`, `active`, `extra='forbid'`);
  - `LaboratoryRef` (`id`, `name`, `active`, `institution: InstitutionRef`, `extra='forbid'`);
  - `TemplateRef` (`key`, `name`, `version`).

  Substituir os usos de `ProfileSummary` e `InstitutionSummary` por `ProfileRef` e `InstitutionRef` em `src/pivma/schemas.py`, `src/pivma/routers/auth.py`, `src/pivma/routers/users.py`, `src/pivma/routers/rbac.py` e `src/pivma/routers/institutional.py`, e remover as classes antigas. O JSON não muda: são os mesmos campos.
- [X] T013 Criar `src/pivma/core/references.py`:
  - `async def user_refs(session, ids) -> dict[UUID, UserRef]`;
  - `async def laboratory_refs(session, ids) -> dict[UUID, LaboratoryRef]` (join `Laboratory` → `Institution`);
  - as duas com `.execution_options(skip_soft_delete_filter=True)` e `active = deleted_at is None`; `ids` vazio devolve `{}` sem consulta (research R6).

**Checkpoint**: T002–T009 verdes; `poetry run pytest tests/api/routers/test_tasks_listing.py tests/api/routers/test_tasks_openapi.py -q --no-cov` continua verde (o JSON de `/tasks` não mudou).

---

## Phase 3: User Story 1 - Toda listagem no mesmo formato (Priority: P1) 🎯 MVP

**Goal**: as 19 listagens no envelope, com paginação por página, filtros ecoados e ordem estável.

**Independent Test**: cada listagem sem parâmetros responde com os 4 blocos, página 1 e 20 por página, e recusa `per_page=101`.

### 3a. Catálogo e RBAC

Testes (`tests/api/routers/test_listing_catalog.py`):
- [X] T014 [P] [US1] `test_users_list_envelope`: `GET /users` com `users.read` passa em `_assert_envelope(sort={'by': 'username', 'order': 'asc'}, filters={'search': None, 'active': True, 'profile_id': None})`.
- [X] T015 [US1] `test_users_list_second_page_with_search`: 25 usuários com `search` em comum; `search=<termo>&page=2&per_page=20` devolve 5, `total_items=25`, e `filters_applied.search == <termo>`.
- [X] T016 [US1] `test_rbac_permissions_envelope`: `GET /rbac/permissions` com `rbac.read`; `sort == {'by': 'code', 'order': 'asc'}`, `filters_applied == {}`.
- [X] T017 [US1] `test_rbac_profiles_envelope`: `GET /rbac/profiles`; `sort == {'by': 'name', 'order': 'asc'}`.
- [X] T018 [US1] `test_rbac_changes_envelope_and_page`: `GET /rbac/changes?per_page=1&page=2` devolve 1 item, `has_prev=True`, `sort == {'by': 'occurred_at', 'order': 'desc'}`.
- [X] T019 [US1] `test_institutions_envelope`: `GET /institutional/institutions` com `institutional.read`; `sort == {'by': 'name', 'order': 'asc'}`.
- [X] T020 [US1] `test_laboratories_envelope`: `GET /institutional/laboratories`; `sort == {'by': 'institution', 'order': 'asc'}`.
- [X] T021 [US1] `test_user_affiliations_envelope`: `GET /institutional/users/{user_id}/affiliations`; `sort == {'by': 'created_at', 'order': 'desc'}`.
- [X] T022 [US1] `test_my_affiliations_envelope`: `GET /institutional/me/affiliations` como usuário comum com 2 afiliações ativas; 2 itens, `sort == {'by': 'created_at', 'order': 'desc'}`.
- [X] T023 [US1] `test_institutional_changes_envelope_and_page`: `GET /institutional/changes?per_page=1&page=2` devolve 1 item e `has_prev=True`.
- [X] T024 [US1] `test_catalog_lists_reject_per_page_above_100`: parametrizado nas 9 rotas do catálogo/RBAC; `per_page=101` → `422`.

Implementação:
- [X] T025 [US1] Em `src/pivma/schemas.py`, criar `UserListFilters` (`search: str | None`, `active: bool`, `profile_id: UUID | None`) e as especializações nomeadas: `UserListResponse(ListPage[AdminUser, UserListFilters])`, `PermissionListResponse`, `ProfileListResponse`, `RbacChangeListResponse`, `InstitutionListResponse`, `LaboratoryListResponse`, `AffiliationListResponse`, `SelfAffiliationListResponse` e `InstitutionalChangeListResponse` (as demais com `NoFilters`). Remover `FilterPage`, `AdminUserPage`, `RbacChangePage` e `InstitutionalChangePage`.
- [X] T026 [US1] Em `src/pivma/routers/users.py`, `list_users`: trocar `offset`/`limit` por `page: PageQuery = 1`, `per_page: PerPageQuery = 20`; usar `paginate_query` com `order_by=(func.lower(User.username).asc(), User.id.asc())`, mantendo `skip_soft_delete_filter`; devolver `UserListResponse`.
- [X] T027 [US1] Em `src/pivma/routers/rbac.py`: `list_permissions` e `list_profiles` paginados no banco (`Permission.code`; `AccessProfile.name, AccessProfile.id`), e `profile_public` só nos itens da página. `list_changes` com `page`/`per_page`, sem a validação manual nem `MAX_CHANGE_LIMIT` (remover a constante se ficar sem uso).
- [X] T028 [US1] Em `src/pivma/routers/institutional.py`: as 5 listagens no envelope, com as ordens do research R4. `list_my_affiliations` pagina em memória (`paginate_items`) sobre a lista do serviço, ordenada por `created_at desc, id desc`. `list_changes` sem `MAX_HISTORY_LIMIT` manual (remover a constante se ficar sem uso).
- [X] T029 [US1] Ajustar ao envelope, sem mudar o que verificam: `tests/api/routers/test_institutional_router.py`, `tests/api/routers/test_institutional_security.py`, `tests/api/routers/test_rbac_router.py`, `tests/api/routers/test_rbac_security.py`, `tests/api/routers/test_user_listing.py`, `tests/api/routers/test_user_listing_security.py`, `tests/api/routers/test_user_router.py` e `tests/api/routers/test_user_update.py`. Testes de `offset`/`limit` passam a `page`/`per_page`, com o mesmo comportamento verificado. Registrar em Notes os casos reescritos.

**Checkpoint 3a**: T014–T024 verdes e `poetry run pytest tests/api/routers/test_institutional* tests/api/routers/test_rbac* tests/api/routers/test_user* -q --no-cov` verde.

### 3b. Processos

Testes (`tests/api/routers/test_listing_processes.py`):
- [X] T030 [P] [US1] `test_templates_envelope_ordered_by_name`: `GET /processes/templates` com os 5 templates reais; `data` ordenado por `name`, `sort == {'by': 'name', 'order': 'asc'}`.
- [X] T031 [US1] `test_processes_envelope_default_filters`: `GET /processes`; `filters_applied == {'status': None}`, `sort == {'by': 'created_at', 'order': 'desc'}`.
- [X] T032 [US1] `test_processes_second_page`: 3 processos do usuário; `per_page=2&page=2` devolve 1, `total_items=3`, `has_prev=True`.
- [X] T033 [US1] `test_processes_status_filter_echoed`: `status=CLOSED` filtra e aparece em `filters_applied.status`.
- [X] T034 [US1] `test_processes_ignores_legacy_size_param`: `size=1` é ignorado e `per_page` padrão (20) vale; `pagination.per_page == 20`.
- [X] T035 [US1] `test_submission_versions_envelope`: processo com 2 revisões devolvidas; `GET /processes/{id}/submission-versions` com 2 itens e `sort == {'by': 'returned_at', 'order': 'desc'}`.
- [X] T036 [US1] `test_timeline_envelope`: `GET /processes/{id}/timeline` responde no envelope, sem `process_id` nem `code` no primeiro nível, e `sort == {'by': 'occurred_at', 'order': 'asc'}`.
- [X] T037 [US1] `test_timeline_total_counts_only_visible_events`: o proponente e o BraCVAM consultam o mesmo processo depois da triagem. O `total_items` de cada um é igual ao número de eventos que cada um via antes da migração (eventos de atividades sem concessão de ver ficam de fora do total).
- [X] T038 [US1] `test_timeline_second_page_keeps_order`: com mais de 2 eventos visíveis, `per_page=2&page=2` devolve os eventos seguintes em ordem cronológica, sem repetir os da página 1.
- [X] T039 [US1] `test_timeline_invisible_process_404`: um usuário sem acesso recebe `404` antes da paginação.
- [X] T040 [US1] `test_process_lists_reject_per_page_above_100`: parametrizado nas 4 rotas; `per_page=101` → `422`.

Implementação:
- [X] T041 [US1] Em `src/pivma/schemas.py`:
  - `ProcessListFilters` (`status: ProcessLifecycle | None`, com a descrição "Nulo = todos, menos os arquivados");
  - especializações `ProcessTemplateListResponse`, `ProcessListResponse`, `SubmissionVersionListResponse` e `TimelineListResponse(ListPage[TimelineEvent, NoFilters])`;
  - remover `ProcessInstanceListResponse` e `ProcessTimelineResponse`.
- [X] T042 [US1] Em `src/pivma/routers/processes.py`:
  - `list_templates` paginado no banco com `order_by(ProcessTemplate.name, ProcessTemplate.key)`;
  - `list_processes` com `page`/`per_page` (sai `size`) e `paginate_query` com `order_by=(ProcessInstance.created_at.desc(), ProcessInstance.id.desc())`;
  - `list_submission_versions` com `paginate_items`;
  - `get_process_timeline` com `paginate_items` depois de `_visible_events` (research R2, R9).
- [X] T043 [US1] Ajustar ao envelope: `tests/api/routers/test_activity_access.py`, `tests/api/routers/test_form_submission.py`, `tests/api/routers/test_participant_timeline.py`, `tests/api/routers/test_process_lifecycle.py`, `tests/api/routers/test_process_retirement.py`, `tests/api/routers/test_process_router.py`, `tests/api/routers/test_process_submission_update.py`, `tests/api/routers/test_process_visibility.py`, `tests/api/routers/test_samples_access.py` e `tests/api/routers/test_timeline_router.py` (`['items']` → `['data']`, `['total']` → `['pagination']['total_items']`, `['events']` → `['data']`, `size` → `per_page`).

**Checkpoint 3b**: T030–T040 verdes e os 10 arquivos ajustados verdes.

### 3c. Participantes e convites

Testes (`tests/api/routers/test_listing_participants.py`):
- [X] T044 [P] [US1] `test_participants_envelope`: `GET /processes/{id}/participants` como gestor; `sort == {'by': 'assigned_at', 'order': 'desc'}`.
- [X] T045 [US1] `test_participants_self_scope_total`: quem só vê a própria designação recebe `total_items == 1`, com 3 participantes no processo.
- [X] T046 [US1] `test_participant_history_second_page`: 3 designações; `per_page=2&page=2` devolve 1 item.
- [X] T047 [US1] `test_invites_envelope`: `GET /processes/{id}/participants/invites`; `sort == {'by': 'created_at', 'order': 'desc'}`.
- [X] T048 [US1] `test_invites_total_counts_only_manageable`: o proponente, que só gere convites de `sponsor` e `group_manager`, vê `total_items` igual aos convites desses cargos. Convites de `statistician` criados pelo Grupo Gestor não contam.
- [X] T049 [US1] `test_participant_lists_reject_per_page_above_100`: parametrizado nas 3 rotas; `per_page=101` → `422`.

Implementação:
- [X] T050 [US1] Em `src/pivma/schemas.py`, `ParticipantListResponse`, `ParticipantHistoryListResponse` e `InviteListResponse` (`NoFilters`); remover `ParticipantHistoryPage`.
- [X] T051 [US1] Em `src/pivma/routers/process_participants.py`:
  - `list_participants` e `get_participant_history` com `paginate_query` (`Assignment.assigned_at.desc(), Assignment.id.desc()`); o histórico perde `offset`/`limit`;
  - `list_participant_invites` com ordem `created_at desc, id desc` e `paginate_items` depois do filtro `can_manage_role_assignment` (research R2).
- [X] T052 [US1] Ajustar ao envelope: `tests/api/routers/test_invite_acceptance.py`, `tests/api/routers/test_invites_router.py`, `tests/api/routers/test_participant_concurrency.py`, `tests/api/routers/test_participant_router.py`, `tests/api/routers/test_participant_security.py`, `tests/api/routers/test_participant_task_blocking.py`, `tests/api/routers/test_participant_timed_acceptance.py` e `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sample_definition_journey.py`.

**Checkpoint 3c**: T044–T049 verdes e os arquivos ajustados verdes.

### 3d. Avaliações de IA

Testes (`tests/api/routers/test_listing_ai.py`):
- [X] T053 [P] [US1] `test_evaluations_envelope_with_search`: `GET /ai-evaluations?search=<termo>`; `filters_applied == {'search': <termo>}` e `sort == {'by': 'name', 'order': 'asc'}`.
- [X] T054 [US1] `test_evaluations_second_page_total`: 3 avaliações; `per_page=2&page=2` devolve 1 e `total_items=3`.
- [X] T055 [US1] `test_references_envelope`: `GET /ai-evaluations/references`; `sort == {'by': 'identifier', 'order': 'asc'}`.
- [X] T056 [US1] `test_ai_lists_reject_per_page_above_100`: parametrizado nas 2 rotas; `per_page=101` → `422`.

Implementação:
- [X] T057 [US1] Em `src/pivma/core/evaluation_service.py`:
  - `list_definitions(session, *, search, page, per_page)` devolve `(items, total)` com `order_by(func.lower(EvaluationDefinition.name), EvaluationDefinition.id)`;
  - `list_references` com desempate `EvaluationReference.id`.
- [X] T058 [US1] Em `src/pivma/schemas.py`, `EvaluationListFilters` (`search: str | None`), `EvaluationListResponse` e `ReferenceListResponse`; remover `EvaluationDefinitionPage`. Em `src/pivma/routers/ai_evaluations.py`, as duas rotas no envelope (referências com `paginate_items` sobre a lista do serviço); remover `MAX_LIMIT` se ficar sem uso.
- [X] T059 [US1] Ajustar ao envelope: `tests/api/routers/test_ai_evaluations_config.py`, `tests/api/routers/test_evaluation_library.py` e `tests/api/routers/test_evaluation_references.py`.

### 3e. Etiquetas de amostra

Testes (`tests/api/routers/test_listing_labels.py`):
- [X] T060 [P] [US1] `test_labels_envelope`: `sample_process(lab_count=3)` com 2 substâncias; `GET /processes/{id}/samples/labels` como Grupo de Seleção devolve 6 itens e `sort == {'by': 'laboratory', 'order': 'asc'}`.
- [X] T061 [US1] `test_labels_second_page`: com as mesmas 6 etiquetas, `per_page=4&page=2` devolve 2, cada uma com `qr_svg`.
- [X] T062 [US1] `test_labels_access_unchanged`: um laboratório participante continua recebendo `404` (regressão da Spec 031).

Implementação:
- [X] T063 [US1] Em `src/pivma/core/sample_service.py`, `list_labels(session, settings, process_id, user_id, *, page, per_page)` devolve `(labels, total)`: total pela mesma consulta, e página com `order_by(Laboratory.name, BlindSampleCode.code)` e `offset`/`limit`. `segno` só roda nos itens da página.
- [X] T064 [US1] Em `src/pivma/schemas.py`, `SampleLabelListResponse`; em `src/pivma/routers/samples.py`, `list_sample_labels` com `page`/`per_page`. Rodar `grep -rn "labels" tests` e ajustar ao envelope os testes que leem etiquetas.

**Checkpoint US1**: `poetry run pytest -q --no-cov` verde.

---

## Phase 4: User Story 2 - Participantes e vínculos com nomes (Priority: P1)

**Goal**: designações e convites com `process`, `user` e `laboratory` como referências.

**Independent Test**: a lista de participantes com um laboratório participante traz `user` com nome e `laboratory.institution`.

### Tests (`tests/api/routers/test_participant_references.py`)

- [X] T065 [P] [US2] `test_participant_item_has_user_and_laboratory_refs`: com `assign_lab`, o item traz `user == {'id', 'username', 'full_name'}`, `laboratory.institution.name` preenchido e `process == {'id', 'code', 'title'}`; `user_id`, `laboratory_id` e `process_id` não existem.
- [X] T066 [US2] `test_participant_without_laboratory_has_null_laboratory`: designação `group_manager` tem `laboratory is None`.
- [X] T067 [US2] `test_participant_refs_never_include_email`: `json.dumps(response.json())` não contém o e-mail de nenhum participante (SC-003).
- [X] T068 [US2] `test_create_participant_response_has_refs`: `POST /processes/{id}/participants` devolve o item com `user` e `laboratory` (FR-016).
- [X] T069 [US2] `test_history_items_use_refs`: `GET .../participants/history` traz `assignment.user` e `assignment.laboratory` como referências.
- [X] T070 [US2] `test_self_scope_still_sees_only_own_assignment`: com referências, quem tem escopo próprio continua vendo só a própria designação (regressão de FR-006).
- [X] T071 [US2] `test_invite_item_has_laboratory_ref`: convite para `participating_laboratory` traz `laboratory.institution` e `process`; `laboratory_id` e `process_id` não existem.
- [X] T072 [US2] `test_invite_accept_response_has_refs`: `POST /invites/{token}/accept` devolve `invite.process` e `invite.laboratory` como referências.
- [X] T073 [US2] `test_participant_list_queries_do_not_grow_with_items`: com 1 e com 10 participantes de laboratório, o número de `SELECT` emitidos (contados por `sqlalchemy.event.listen(engine.sync_engine, 'before_cursor_execute', ...)`) é o mesmo.

### Implementation

- [X] T074 [US2] Em `src/pivma/schemas.py`:
  - `ParticipantAssignmentPublic`: troca `process_id`, `user_id` e `laboratory_id` por `process: ProcessRef`, `user: UserRef` e `laboratory: LaboratoryRef | None`;
  - `InvitePublic` e `InviteCreatedResponse`: trocam `process_id` e `laboratory_id` por `process: ProcessRef` e `laboratory: LaboratoryRef | None`.
- [X] T075 [US2] Em `src/pivma/routers/process_participants.py`, `_build_participant_publics` carrega em lote `user_refs` e `laboratory_refs` para a página e monta `ProcessRef` a partir do processo. Todas as rotas que devolvem `ParticipantAssignmentPublic` (lista, histórico, criação) passam por ele.
- [X] T076 [US2] Em `src/pivma/core/invite_service.py` e `src/pivma/routers/process_participants.py`, `_invite_public` recebe o processo e o dicionário de `laboratory_refs` da página, ou os carrega para um convite só. O mesmo vale para criação, reenvio, revogação e aceite (`src/pivma/routers/invites.py`).
- [X] T077 [US2] Ajustar às referências (`['user_id']` → `['user']['id']`, `['laboratory_id']` → `['laboratory']['id']`, `['process_id']` → `['process']['id']`): `tests/api/routers/test_participant_router.py`, `tests/api/routers/test_invites_router.py`, `tests/api/routers/test_invite_acceptance.py` e os demais arquivos que `grep -rnE "\['(user_id|laboratory_id|process_id)'\]" tests` apontar em respostas de participante ou convite.

**Checkpoint**: T065–T073 verdes e suíte verde.

---

## Phase 5: User Story 3 - Referências no catálogo, processos e etiquetas (Priority: P2)

**Goal**: laboratórios, afiliações, processos, etiquetas e perfis com referências.

**Independent Test**: laboratório com `institution`; afiliação com `user`, `institution` e `laboratory.institution`; processo com `template`; etiqueta com `laboratory`.

### Tests (`tests/api/routers/test_catalog_references.py`)

- [X] T078 [P] [US3] `test_laboratory_list_and_detail_have_institution_ref`: listagem e `GET /institutional/laboratories/{id}` trazem `institution == {'id', 'name', 'active'}`, sem `institution_id`.
- [X] T079 [US3] `test_create_laboratory_response_has_institution_ref`: `POST /institutional/laboratories` devolve `institution`.
- [X] T080 [US3] `test_user_affiliations_have_refs`: item com `user` (`id`, `username`, `full_name`), `institution` e `laboratory.institution`; sem `user_id`.
- [X] T081 [US3] `test_my_affiliations_laboratory_has_institution`: `GET /institutional/me/affiliations` traz `laboratory.institution`.
- [X] T082 [US3] `test_inactive_laboratory_ref_still_listed`: afiliação a laboratório desativado aparece com `laboratory.active is False`.
- [X] T083 [US3] `test_admin_user_profiles_json_unchanged`: `GET /users` traz `profiles` com exatamente `{'id', 'name', 'active'}` (mesmo JSON de antes).

Testes (`tests/api/routers/test_process_references.py`):
- [X] T084 [P] [US3] `test_process_list_has_template_ref`: item de `GET /processes` traz `template == {'key': 'pre_validated_method', 'name': <nome do template>, 'version': 3}`, sem `template_key` nem `version_number`.
- [X] T085 [US3] `test_process_detail_and_create_have_template_ref`: `POST /processes` e `GET /processes/{id}` trazem `template`.
- [X] T086 [US3] `test_label_has_laboratory_ref_without_identity`: etiqueta traz `laboratory` como referência, sem `laboratory_id` e `laboratory_name`. `json.dumps` da resposta não contém `chemical_name` nem `cas_number` das substâncias (regressão da Spec 031).

### Implementation

- [X] T087 [US3] Em `src/pivma/schemas.py`:
  - `LaboratoryPublic`: troca `institution_id` por `institution: InstitutionRef`;
  - `AffiliationPublic`: troca `user_id` por `user: UserRef`, e `institution`/`laboratory` passam a `InstitutionRef`/`LaboratoryRef | None`;
  - `SelfAffiliationPublic`: `institution`/`laboratory` como referências;
  - remover `LaboratorySummary`.
- [X] T088 [US3] Em `src/pivma/routers/institutional.py`:
  - `laboratory_public` monta `InstitutionRef` a partir da instituição (carregada em lote na listagem, individualmente no detalhe e na criação);
  - `affiliation_public` usa `user_refs` e `laboratory_refs`;
  - as listagens de afiliações carregam as referências da página em lote.
- [X] T089 [US3] Em `src/pivma/schemas.py`, `ProcessInstanceDetail` troca `template_key` e `version_number` por `template: TemplateRef`. Em `src/pivma/routers/processes.py`, montar `TemplateRef(key=template.key, name=template.name, version=template_version.version_number)` em todos os pontos que constroem `ProcessInstanceDetail` (`grep -n "ProcessInstanceDetail(" src/pivma`).
- [X] T090 [US3] Em `src/pivma/schemas.py`, `SampleLabel` troca `laboratory_id` e `laboratory_name` por `laboratory: LaboratoryRef`; em `src/pivma/core/sample_service.py`, `list_labels` monta a referência com `laboratory_refs` da página.
- [X] T091 [US3] Ajustar às referências os testes que `grep -rnE "\['(institution_id|template_key|version_number|laboratory_name)'\]|\['user_id'\]" tests` apontar em respostas de laboratório, afiliação, processo ou etiqueta. Registrar os arquivos em Notes.

**Checkpoint**: T078–T086 verdes e suíte verde.

---

## Phase 6: User Story 4 - Referências documentadas (Priority: P3)

### Tests (`tests/api/routers/test_references_openapi.py`)

- [X] T092 [P] [US4] `test_listings_are_documented_as_envelopes`: parametrizado nas 19 rotas do contrato; a resposta `200` em `app.openapi()` é um objeto com `data`, `pagination`, `filters_applied` e `sort` obrigatórios, e a operação não declara `offset`, `limit` nem `size`.
- [X] T093 [US4] `test_reference_schemas_have_descriptions`: `UserRef`, `ProfileRef`, `InstitutionRef`, `LaboratoryRef`, `TemplateRef` e `ProcessRef` existem em `components.schemas`, com `description` em todos os campos.
- [X] T094 [US4] `test_admin_logs_hidden_from_openapi`: `/admin/logs/operational` e `/admin/logs/ai` não estão em `app.openapi()['paths']`.
- [X] T095 [US4] `test_admin_logs_still_respond`: `GET /admin/logs/operational` como `ai_eval_admin` responde `200` (comportamento inalterado, FR-018).

### Implementation

- [X] T096 [US4] Em `src/pivma/routers/admin_logs.py`, `include_in_schema=False` nas duas rotas (research R8).
- [X] T097 [US4] Conferir que as descrições dos campos de `ListPage`, das referências e dos filtros aparecem no OpenAPI; completar as que faltarem em `src/pivma/schemas.py`.

**Checkpoint**: T092–T095 verdes.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T098 [P] Atualizar `README.md`:
  - "Padrão de Listagem" passa a valer para todas as listagens, com a lista de referências e seus campos;
  - "Tarefas" permanece;
  - "Participantes e Conflito de Interesses" menciona `user` e `laboratory` como referências;
  - "Amostras Cegas" troca `laboratory_id`/`laboratory_name` por `laboratory` nas etiquetas;
  - a seção "Observabilidade de Logs" é reduzida a uma nota de que as consultas existem, mas estão fora da documentação e serão removidas. Sem citar as páginas `demos/`, que não existem mais.
- [X] T099 Rodar `poetry run pytest -q` com cobertura e `poetry run ruff check . && poetry run ruff format --check .`; comparar com a linha de base de T001 e registrar em Notes o resultado e a cobertura de `src/pivma/core/listing.py` e `src/pivma/core/references.py`.
- [ ] T100 Executar o roteiro manual de `specs/033-listing-migration-refs/quickstart.md` no Swagger local e registrar em Notes o que foi executado. Se não for possível, registrar o motivo.
- [X] T101 Registrar em Notes as mudanças de contrato para o changelog único (Specs 032–034): as 19 listagens, os parâmetros removidos, as referências por schema e a nova ordem dos templates. **Sem mencionar os logs administrativos.**

---

## Dependencies & Execution Order

- **Setup → Foundational**: bloqueiam tudo.
- **US1**: depende da Foundational. Os grupos 3a–3e são independentes entre si (roteadores e arquivos de teste diferentes); em `src/pivma/schemas.py` as edições precisam ser coordenadas.
- **US2**: depende da US1 (participantes e convites já no envelope).
- **US3**: depende da US1. É independente da US2, exceto pelas edições em `src/pivma/schemas.py`.
- **US4**: depende da US1–US3 (verifica os schemas finais).
- **Polish**: depende de todas.

### Parallel Opportunities

- T002 (unidade) e T005 (integração) em paralelo.
- Os primeiros testes de cada grupo da US1 (T014, T030, T044, T053, T060), em arquivos diferentes.
- T065 e T078/T084 em paralelo, se US2 e US3 correrem juntas.
- T092 e T098 em paralelo.

## Parallel Example: User Story 1

```text
3a  tests/api/routers/test_listing_catalog.py       + routers users/rbac/institutional
3b  tests/api/routers/test_listing_processes.py     + routers/processes.py
3c  tests/api/routers/test_listing_participants.py  + routers/process_participants.py
3d  tests/api/routers/test_listing_ai.py            + routers/ai_evaluations.py + evaluation_service
3e  tests/api/routers/test_listing_labels.py        + routers/samples.py + sample_service
```

## Implementation Strategy

### MVP First

A US1 inteira, com as 19 listagens no envelope, é o MVP: é o que permite ao frontend um componente de listagem só. A US2 destrava a tela de participantes.

### Incremental Delivery

1. Foundational.
2. US1 grupo a grupo, com a suíte verde em cada checkpoint.
3. US2 (participantes e convites).
4. US3 (catálogo, processos, etiquetas).
5. US4 (documentação e logs ocultos).
6. README e notas do changelog.

Um PR único na `develop`, como na Spec 032.

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- Commit após cada grupo; mensagens `feat(listing): ...` / `test(listing): ...`.
- **Linha de base (T001)**: 1082 passaram, 1 pulado. O `ruff check` acusou 3 erros porque rodou no meio das edições da Phase 2; na `develop` depois do #62, o lint estava limpo.
- **T011**: `paginate_query` repassa ao total as opções de execução da consulta (`skip_soft_delete_filter`). Sem isso, `GET /users?active=false` contaria as contas inativas com o filtro global de exclusão lógica ligado.
- **T012**: as referências foram para o topo de `schemas.py` (junto com `ProcessRef`/`PhaseRef`, que saíram da seção da Spec 032), porque schemas do início do arquivo (`CurrentUserAccess`, `AdminUser`, `AffiliationPublic`) passaram a usá-las. `ProfileSummary` virou `ProfileRef` com o mesmo JSON; o teste de contrato de `/auth/me` só troca o nome do schema referenciado.
- **T029**: `tests/unit/schemas/test_institutional_schemas.py::test_institutional_change_page_limits_pagination_values` foi removido (o schema `InstitutionalChangePage` deixou de existir; os limites valem nos parâmetros e são cobertos por T024). Em `tests/api/routers/test_user_listing.py`, os testes de `offset`/`limit` viraram testes de `page`/`per_page` com o mesmo comportamento; o teste de contrato da Spec 007 continua comparando operação e item, e o envelope passou a ser conferido como `UserListResponse`.
- **T030**: `test_timeline_second_page_keeps_order` envia a submissão para ter mais de 2 eventos.
- **T043**: `test_timeline_router.py::test_process_timeline_events_recorded_and_ordered` deixou de conferir `process_id` na raiz da resposta (campo removido pela Q1 da spec).
- **T051**: o histórico de participantes aceitava até 200 itens por página; passa ao limite comum de 100.
- **T064**: o helper `_labels` de `tests/api/routers/test_samples_router.py` pede `per_page=100`; a jornada da Spec 031 lê `['data']`.
- **T076**: `invite_public_kwargs` virou assíncrona e carrega processo e laboratório; a listagem de convites usa `invite_publics`, em lote. Duas mudanças só de formatação que o `ruff format` local fez em `invite_service.py` foram desfeitas. O mesmo aconteceu antes com o arquivo inteiro, também desfeito.
- **T077/T091**: ajustados às referências: `test_participant_router.py`, `test_invite_acceptance.py`, `test_institutional_router.py` (incluindo o JSON esperado da afiliação própria, agora com `laboratory.institution`), `test_samples_router.py` (etiquetas) e `test_activity_type_extension.py` (`template.version`). Leituras de `laboratory_id`/`laboratory_name` em `blind_codes` continuam, porque a lista de substâncias está fora do escopo (FR-019).
- **T088**: `affiliation_public` monta as referências por item (uma consulta de pessoa e, se o laboratório for de outra instituição, uma de instituição), mantendo o padrão por item que já existia. A lista de laboratórios carrega as instituições da página em lote.
- **T100**: não executada. O roteiro é conferir o Swagger de uma API local; os mesmos pontos são verificados automaticamente por T092–T095 (envelope e parâmetros nas 19 listagens, descrições das referências, logs fora do OpenAPI e ainda respondendo).
- **T101 — mudanças de contrato para o changelog único (Specs 032–034)**:
  - 19 listagens no envelope `data`/`pagination`/`filters_applied`/`sort`: usuários, permissões, perfis, alterações do RBAC, instituições, laboratórios, afiliações (de um usuário e próprias), alterações do catálogo, templates, processos, versões de submissão, linha do tempo, participantes, histórico de participantes, convites, avaliações de IA, referências de IA e etiquetas. **Quebra.**
  - Paginação por `page`/`per_page` (1–100, padrão 20). Saem `offset`, `limit` e `size`. O histórico de participantes aceitava até 200 e passa a 100.
  - Linha do tempo: saem `process_id` e `code` da raiz; os eventos ficam em `data`.
  - Referências: designações (`process`, `user`, `laboratory`), convites (`process`, `laboratory`), laboratórios (`institution`), afiliações (`user`, `institution`, `laboratory.institution`), processos (`template` no lugar de `template_key`/`version_number`), etiquetas (`laboratory` no lugar de `laboratory_id`/`laboratory_name`). **Quebra.** Perfis (`/users`, `/auth/me`, `/rbac`) mantêm o JSON.
  - Templates passam a vir ordenados por nome (antes sem ordem definida).
  - Paginação inválida em `/rbac/changes` e `/institutional/changes` deixa de responder `'Invalid pagination'` e passa ao `422` de validação padrão.
- **T099**: suíte final com `--cov`: **1184 passaram, 1 pulado, 0 falhas** (102 a mais que a linha de base). Cobertura total 93%; `core/listing.py` e `core/references.py` com 100%. `ruff check .` limpo depois de formatar 3 arquivos de teste editados nesta feature. `ruff format --check` acusa só `src/pivma/core/invite_service.py` (linha original de `accept_invite`, restaurada de propósito) e `tests/api/routers/test_user_router.py`, os mesmos já registrados nas Specs 031/032 (versão do ruff local).
