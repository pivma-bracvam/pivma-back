---

description: "Task list — Spec 030: ciclo de vida do processo e acesso por atividade"
---

# Tasks: Ciclo de vida do processo e acesso por atividade

**Input**: Design documents from `specs/030-process-lifecycle-activity-access/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [quickstart.md](quickstart.md)

**Tests**: Obrigatórios (AGENTS.md). Seguem `.agents/skills/fastapi-testing-methodology/`: um comportamento observável por tarefa, testes antes da implementação de cada história, sucesso, cada erro, autorização, isolamento, auditoria e concorrência separados. Risco: **crítico** para acesso por atividade e visibilidade (unit + integração + API + segurança), **alto** para ciclo de vida, revisão do retorno e migração, **médio** para leitura de fases.

**Organization**: Por user story. A ordem das fases segue a dependência, não o número da história: US3 → US2 → US1 → US4 → US5 → US6 (ver [Dependencies](#dependencies--execution-order)).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: user story da spec (US1…US6)
- Comandos com `poetry run`; testes isolados com `--no-cov`

## Convenções de teste desta feature

- Autenticação nos testes de API: `authenticate(client, user)` de `tests/api/routers/test_rbac_router.py`.
- Usuários BraCVAM/Admin: fixtures `bracvam_user` e `ai_eval_admin` de `tests/conftest.py`; para perfis canônicos use `sync_canonical_profiles`/`sync_canonical_permissions`/`sync_profile_permissions` de `pivma.bootstrap_system`.
- Cargo de processo: `AssignmentFactory` de `tests/factories/participant_factory.py`.
- Templates: `bootstrap_all_templates(session)` de `pivma.bootstrap_process_templates`.
- Endpoints mutáveis exigem header `Origin: https://testserver`.
- Pré-avaliação por IA: fixture `fake_provider` e chamada explícita de `pre_evaluation_service._execute` (o background é stubado em `tests/conftest.py`).

---

## Phase 1: Setup

**Purpose**: linha de base e branch.

- [X] T001 Criar a branch `feat/030-process-lifecycle-activity-access` a partir de `develop` (`git switch -c`), que já contém o commit `50d8983` (jornada do processo 1 e reorganização de `tests/integration/bootstrap/`). Os artefatos de `specs/030-process-lifecycle-activity-access/` entram no primeiro commit da branch.
- [X] T002 Rodar `poetry run pytest -q` e `poetry run ruff check .` e anotar em `specs/030-process-lifecycle-activity-access/tasks.md` (seção Notes, ao final) a contagem de testes passando/falhando, para comparar na Phase 9. Falhas pré-existentes ficam listadas e não são atribuídas a esta feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: infraestrutura de teste compartilhada pelas jornadas e pela matriz de acesso.

- [X] T003 Criar `tests/integration/journeys/conftest.py` movendo de `tests/integration/journeys/test_pre_validated_method_triage.py` os helpers `_bootstrap_fresh_deploy`, `_sign_up`, `_log_in`, `_log_out` e `_process_tasks` como funções públicas (`bootstrap_fresh_deploy`, `sign_up`, `log_in`, `log_out`, `process_tasks`) e as constantes `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `PASSWORD`. Acrescentar a fixture `journey_client(client)` que define `client.headers['Origin'] = 'https://testserver'`. Atualizar o import no teste existente. `poetry run pytest tests/integration/journeys -q --no-cov` continua verde.
- [X] T004 [P] Em `tests/factories/participant_factory.py`, acrescentar o helper `async def grant_cargo(session, *, process_id, user, role_key)` que cria e commita uma `AssignmentFactory` ativa (sem `revoked_at`) e devolve a `Assignment`. Documentar no docstring que é o jeito padrão desta feature de dar cargo de processo a um usuário nos testes.

**Checkpoint**: jornadas verdes com os helpers compartilhados.

---

## Phase 3: User Story 3 - Toda atividade de todo template declara as concessões (Priority: P1)

**Goal**: toda `ActivityInstance` nasce com `view_roles` e `edit_roles` válidos, vindos do template.

**Independent Test**: `poetry run pytest tests/unit/core/test_activity_access_definition.py tests/integration/database/test_activity_access_columns.py -q --no-cov` verde; carregar os 5 templates e instanciar um processo de cada deixa todas as atividades com `edit_roles` não vazio e `admin`/`bracvam` em `view_roles`.

### Tests for User Story 3

> Escrever primeiro e confirmar que falham.

- [X] T005 [P] [US3] Em `tests/unit/core/test_activity_access_definition.py`, `test_access_defaults_to_assigned_role_for_edit_and_view`: `resolve_activity_access({'key': 'x', 'assigned_role': 'proponent'})` devolve `edit == ['proponent']` e `view` contendo `proponent`, `admin`, `bracvam` (FR-012, data-model "Regra `edit_roles`: na ausência, `[assigned_role]`").
- [X] T006 [P] [US3] No mesmo arquivo, `test_access_view_always_includes_admin_and_bracvam`: com `access: {edit: ['bracvam'], view: []}`, `view` é exatamente `{'bracvam', 'admin'}` (FR-016, R3).
- [X] T007 [P] [US3] No mesmo arquivo, `test_access_edit_implies_view`: com `access: {edit: ['group_manager'], view: ['sponsor']}`, `view ⊇ {'group_manager', 'sponsor', 'admin', 'bracvam'}` (FR-009).
- [X] T008 [P] [US3] No mesmo arquivo, `test_access_rejects_empty_edit`: `access: {edit: []}` levanta `ValidationError` cuja mensagem cita a chave da atividade (FR-013).
- [X] T009 [P] [US3] No mesmo arquivo, `test_access_rejects_unknown_cargo`: `access: {edit: ['reviewer_x']}` levanta `ValidationError` cuja mensagem cita `reviewer_x` e a atividade (FR-013).
- [X] T010 [P] [US3] No mesmo arquivo, `test_access_result_is_deterministic_sorted`: `view` e `edit` retornam listas ordenadas e sem duplicatas (estabilidade para comparação e para o banco).
- [X] T011 [P] [US3] Em `tests/integration/database/test_activity_access_columns.py`, `test_template_load_rejects_activity_without_edit`: `sync_template_from_dict` com um dicionário mínimo cuja atividade tem `access: {edit: []}` levanta `ValidationError` citando template e atividade, e nenhuma `ProcessTemplateVersion` é criada (FR-013, cenário US3-2).
- [X] T012 [P] [US3] No mesmo arquivo, `test_template_load_rejects_unknown_cargo`: idem com cargo fora de `ACTIVITY_CARGOS` (cenário US3-3).
- [X] T013 [P] [US3] No mesmo arquivo, `test_canonical_templates_instantiate_with_access_on_every_activity`: `bootstrap_all_templates`, instancia um processo de cada um dos 5 templates via `instantiate_process` e verifica que **toda** `ActivityInstance` tem `edit_roles` não vazio e `{'admin','bracvam'} ⊆ set(view_roles)` (FR-014, SC-002).
- [X] T014 [P] [US3] No mesmo arquivo, `test_phase1_access_matrix_on_instantiation`: para `pre_validated_method`, `proposal_submission.edit_roles == ['proponent']`, `triage_evaluation.edit_roles == ['bracvam']` e `'proponent' not in triage_evaluation.view_roles` (data-model, matriz da fase 1; FR-023, FR-026, FR-029).
- [X] T015 [P] [US3] No mesmo arquivo, `test_template_resync_does_not_change_existing_activity_access`: instancia um processo, altera em memória o `access` de `triage_evaluation` no dicionário do template e roda `sync_template_from_dict` com a mesma versão; as colunas da atividade já instanciada não mudam (premissa da spec; R2).

### Implementation for User Story 3

- [X] T016 [US3] Em `src/pivma/core/database/models.py`, acrescentar a `ActivityInstance` os campos `view_roles: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default_factory=list)` e `edit_roles` idem, ambos `nullable=False` (data-model: "`ARRAY(String(64))`, `NOT NULL`"). Importar `ARRAY` de `sqlalchemy.dialects.postgresql`. A migração fica para T099.
- [X] T017 [US3] Em `src/pivma/core/process_engine.py`, ao lado de `_resolve_activity_cargo`, criar `resolve_activity_access(a_data) -> tuple[list[str], list[str]]` (view, edit) com as regras de T005–T010: `edit = access.edit` ou `[assigned_role resolvido]`; `edit` não vazio; todo cargo em `ACTIVITY_CARGOS`; `view = sorted(set(edit) | set(access.view) | GLOBAL_ACTIVITY_CARGOS)`. Erros como `ValidationError` citando a chave da atividade e o cargo.
- [X] T018 [US3] Em `src/pivma/core/process_engine.py`, `_create_phases_and_activities`: preencher `view_roles`/`edit_roles` de cada `ActivityInstance` com `resolve_activity_access(a_data)`.
- [X] T019 [US3] Em `src/pivma/bootstrap_process_templates.py`, `sync_template_from_dict`: antes de gravar, percorrer todas as atividades de `data['phases']` e chamar `resolve_activity_access`, deixando a `ValidationError` subir com o nome do template (`data['process_template']['key']`) acrescentado à mensagem.
- [X] T020 [P] [US3] Declarar `access` em toda atividade de `src/pivma/templates_data/01_pre_validated_method.yaml`, `02_scope_extension.yaml`, `03_me_too_validation.yaml` e `05_proof_of_concept.yaml` conforme a matriz da fase 1 de `data-model.md`: `proposal_submission` → `edit: ["proponent"]`, `view: []`; `triage_evaluation` → `edit: ["bracvam"]`, `view: []`.
- [X] T021 [P] [US3] Declarar `access` em toda atividade de `src/pivma/templates_data/04_validated_method_dossier.yaml`: fase 1 como T020; atividades da fase 2 com `edit: [<assigned_role da própria atividade>]`, `view: []`.
- [X] T022 [US3] Documentar a chave `access` em `src/pivma/templates_data/README.md` (formato, padrão quando omitida, `admin`/`bracvam` sempre com ver, erros de carga).
- [X] T023 [US3] Rodar os testes de T005–T015 e confirmar verde.

**Checkpoint**: concessões existem e são válidas; nada as usa ainda.

---

## Phase 4: User Story 2 - Cada usuário vê e edita só as atividades concedidas ao seu cargo (Priority: P1)

**Goal**: autorização de leitura e escrita por atividade, visibilidade de processo sem status, tarefas e timeline filtradas.

**Independent Test**: `poetry run pytest tests/integration/database/test_user_cargos.py tests/api/routers/test_activity_access.py -q --no-cov` verde; a matriz da US2 vale para proponente, `sponsor`, BraCVAM e Admin.

### Tests for User Story 2

**Cargos efetivos** (`tests/integration/database/test_user_cargos.py`):

- [X] T024 [P] [US2] `test_user_cargos_includes_active_assignment_role`: usuário com `grant_cargo(role_key='proponent')` → `user_cargos(...) == {'proponent'}`.
- [X] T025 [P] [US2] `test_user_cargos_excludes_revoked_assignment`: atribuição com `revoked_at` preenchido não entra (US2-4).
- [X] T026 [P] [US2] `test_user_cargos_excludes_deleted_user`: usuário com `deleted_at` → conjunto vazio.
- [X] T027 [P] [US2] `test_user_cargos_adds_admin_for_administrator_profile` e `test_user_cargos_adds_bracvam_for_bracvam_profile`: perfis canônicos → `'admin'`/`'bracvam'` no conjunto, sem atribuição no processo (R3).
- [X] T028 [P] [US2] `test_user_cargos_scoped_to_process`: atribuição em outro processo não entra (isolamento).
- [X] T029 [P] [US2] `test_user_cargos_union_of_multiple_roles`: duas atribuições (`proponent`, `sponsor`) → ambos (edge case "vale a união").

**Matriz de acesso via API** (`tests/api/routers/test_activity_access.py`; fixture local que cria processo `pre_validated_method` com proponente, `sponsor`, BraCVAM e Admin):

- [X] T030 [P] [US2] `test_proponent_reads_submission_form`: `GET .../activities/proposal_submission/form` → 200 (US2-1).
- [X] T031 [P] [US2] `test_proponent_saves_submission_draft`: `PUT .../form` → 200 (US2-1).
- [X] T032 [P] [US2] `test_sponsor_gets_404_on_submission_form`: `sponsor` com atribuição → `GET .../form` 404 (US2-2, FR-017).
- [X] T033 [P] [US2] `test_sponsor_gets_404_on_submission_draft_save`: `PUT .../form` → 404, não 403 (não revela existência).
- [X] T034 [P] [US2] `test_second_proponent_edits_submission`: segundo usuário com cargo `proponent` → `PUT .../form` 200 (US2-3: concessão ao cargo).
- [X] T035 [P] [US2] `test_revoked_proponent_loses_access_immediately`: revoga a atribuição e `GET .../form` → 404 (US2-4).
- [X] T036 [P] [US2] `test_bracvam_reads_submission_draft`: BraCVAM `GET .../form` em rascunho → 200 (US2-10, FR-016).
- [X] T037 [P] [US2] `test_bracvam_cannot_save_submission_draft`: BraCVAM `PUT .../form` → 403 (US2-10, FR-018).
- [X] T038 [P] [US2] `test_admin_reads_submission_draft_but_cannot_submit`: Admin `GET` 200 e `POST .../form` 403.
- [X] T039 [P] [US2] `test_proponent_reads_submitted_form_but_cannot_edit`: depois do envio, proponente `GET` 200 e `PUT` 409 (formulário enviado; US2-5, FR-019).
- [X] T040 [P] [US2] `test_proponent_cannot_decide_triage`: `POST .../triage/decision` → 403 (US2-8, FR-029). *Ajuste na implementação*: a dependência `triage.review` do roteador responde antes da checagem de concessão, então o proponente recebe 403, não 404.
- [X] T041 [P] [US2] `test_admin_cannot_decide_triage`: Admin com `triage.review` → 403 (FR-026, Clarifications Q5).
- [X] T042 [P] [US2] `test_admin_cannot_save_triage_field_reviews`: Admin `POST .../triage/reviews` → 403.
- [X] T043 [P] [US2] `test_bracvam_decides_triage`: BraCVAM → 200 (US2-7).
- [X] T044 [P] [US2] `test_conflict_of_interest_blocks_bracvam_despite_grant`: BraCVAM com conflito declarado no processo → decisão 403 (FR-022).
- [X] T045 [P] [US2] `test_attachment_upload_requires_edit_grant`: `sponsor` → 404 e BraCVAM → 403 em `POST .../form/fields/{field}/attachment` (usar o template 5, que tem `file_upload`).
- [X] T046 [P] [US2] `test_submission_versions_require_view_grant`: `sponsor` → `GET /processes/{id}/submission-versions` 404; proponente 200.
- [X] T047 [P] [US2] `test_pre_evaluation_read_requires_view_on_submission`: `sponsor` → `GET /processes/{id}/pre-evaluation` 404; proponente e BraCVAM não recebem 404 (contrato: 404 no lugar do 403).

**Visibilidade de processo** (`tests/api/routers/test_process_visibility.py`, reescrever):

- [X] T048 [US2] Substituir `test_submission_status_stays_locked_to_the_proponent` por `test_participant_sees_process_header_during_submission`: `sponsor` com atribuição → `GET /processes/{id}` 200 com processo ainda em submissão (FR-015, Q1=B).
- [X] T049 [US2] `test_user_without_assignment_gets_404_on_process`: usuário comum sem atribuição → 404 em `GET /processes/{id}` e ausente de `GET /processes`.
- [X] T050 [US2] Manter `test_bracvam_user_sees_any_process_without_assignment` e acrescentar `test_admin_sees_any_process_without_assignment`.

**Tarefas e timeline**:

- [X] T051 [P] [US2] Em `tests/api/routers/test_tasks_visibility.py`, `test_task_list_hides_tasks_of_activities_without_view`: `sponsor` com atribuição → `GET /tasks?process_id=` não traz a tarefa de `proposal_submission` (US2-9, FR-020).
- [X] T052 [P] [US2] No mesmo arquivo, `test_task_list_shows_triage_task_to_bracvam_not_to_proponent`: após o envio, BraCVAM vê a tarefa `bracvam`; proponente não.
- [X] T053 [P] [US2] No mesmo arquivo, `test_task_detail_404_without_view`: `GET /tasks/{id}` da tarefa de triagem pelo proponente → 404.
- [X] T054 [P] [US2] Em `tests/api/routers/test_timeline_router.py`, `test_timeline_hides_events_of_activities_without_view`: após a decisão de triagem, o proponente não recebe eventos cujo `activity_run_id` pertence a `triage_evaluation`; BraCVAM recebe (FR-021).

### Implementation for User Story 2

- [X] T055 [US2] Em `src/pivma/core/authorization.py`, criar `async def user_cargos(session, user_id, process_id) -> set[str]` conforme data-model ("Cargos efetivos de um usuário num processo"), reaproveitando os filtros de `active_participant_process_scope` e `active_profiles_for_user` (`administrator` → `'admin'`, `bracvam` → `'bracvam'`).
- [X] T056 [US2] No mesmo arquivo, criar `async def require_activity_view(session, user_id, activity)` (sem interseção com `view_roles` → `NotFoundError`) e `async def require_activity_edit(session, user_id, activity)` (sem ver → `NotFoundError`; vê sem `edit_roles` → `AuthorizationError`). Conflito de interesse vigente (`has_current_conflict`) → `AuthorizationError` antes das concessões (FR-022). Importar `NotFoundError`/`AuthorizationError` sem criar import circular com `process_engine` (se necessário, mover as exceções para um módulo `core/errors.py` e reexportar em `process_engine`).
- [X] T057 [US2] Em `src/pivma/core/process_engine.py`, `get_current_form_instance` e `get_current_activity_run`: trocar o bloco `PROPONENT_SCOPED_STATUSES`/`is_active_effective_proponent` por um parâmetro `access: Literal['view', 'edit'] | None = None`; com `user_id` informado, chamar `require_activity_view` ou `require_activity_edit` sobre a atividade carregada. Verificar primeiro que o processo existe e não está removido (404).
- [X] T058 [US2] Atualizar os chamadores com o nível certo: leituras (`routers/forms.py` `get_activity_form`, download de anexo) → `'view'`; `save_form_values_draft`, `submit_proposal_form`, upload e remoção de anexo → `'edit'`; `save_field_reviews` e `execute_triage_decision` → `'edit'` em `triage_evaluation` (e leitura da submissão sem `user_id`, como hoje).
- [X] T059 [US2] Em `src/pivma/routers/forms.py` e `src/pivma/routers/triage.py`, mapear `AuthorizationError` → 403 onde ainda não houver o `except`.
- [X] T060 [US2] Em `src/pivma/core/process_engine.py`, `process_visibility_clause`: sem restrição para `has_platform_wide_access`; demais → `ProcessInstance.id.in_(active_participant_process_scope(user_id))`. Remover o ramo por status e o uso de `has_process_review_access` aqui (R5). Remover `active_proponent_process_scope` do import se ficar sem uso.
- [X] T061 [US2] Em `src/pivma/core/process_engine.py`, `list_returned_submission_versions` e `get_returned_submission_version`: além de `_visible_process`, exigir `require_activity_view` em `proposal_submission`.
- [X] T062 [US2] Em `src/pivma/routers/pre_evaluation.py`, `_ensure_can_read`: trocar a regra proponente/`triage.review` por `require_activity_view` em `proposal_submission`, com `NotFoundError` → 404.
- [X] T063 [US2] Em `src/pivma/routers/tasks.py`, `list_tasks`: acrescentar o filtro de `view_roles` — `or_(ActivityInstance.view_roles.overlap(<cargos globais do usuário>), ActivityInstance.view_roles.overlap(<array de role_key das atribuições ativas do usuário naquele processo>))`, com a segunda parte como subquery correlacionada por `ActivityInstance.process_instance_id` (R12). `get_task_detail`: `require_activity_view` → 404.
- [X] T064 [US2] Em `src/pivma/routers/processes.py`, `_visible_events`: descartar eventos com `activity_run_id` cuja atividade o usuário não vê (carregar as atividades das execuções em uma query e calcular `user_cargos` uma vez).
- [X] T065 [US2] Revisar e ajustar os testes existentes que dependiam da regra antiga, um arquivo por vez, sem afrouxar asserções de segurança: `tests/api/routers/test_triage_authorization.py`, `test_triage_review.py`, `test_form_submission.py`, `test_form_attachments.py`, `test_pre_evaluation_get.py`, `test_tasks_router.py`, `test_timeline_router.py`, `tests/unit/core/test_authorization_participant_scope.py`. Onde um usuário precisava agir como proponente, dar a ele o cargo com `grant_cargo`.
- [X] T066 [US2] Rodar T024–T054 e a suíte `tests/api/routers` e confirmar verde.

**Checkpoint**: acesso por atividade no ar; o status de fluxo ainda existe mas não decide mais acesso.

---

## Phase 5: User Story 1 - O processo expõe só o ciclo de vida (Priority: P1) 🎯 MVP (junto com US3 e US2)

**Goal**: `status` com domínio `OPEN | CLOSED | CANCELLED | ARCHIVED`, sem escrita de fluxo; guardas por execução; trava da IA na `EvaluationRun`.

**Independent Test**: `poetry run pytest tests/api/routers/test_process_lifecycle.py tests/integration/database/test_process_lifecycle_constraint.py tests/integration/journeys -q --no-cov` verde.

### Tests for User Story 1

- [X] T067 [P] [US1] Em `tests/integration/database/test_process_lifecycle_constraint.py`, `test_process_status_rejects_flow_value`: gravar `ProcessInstance` com `status='TRIAGE'` e `flush` levanta `IntegrityError` (FR-004, "`CHECK (status IN ('OPEN','CLOSED','CANCELLED','ARCHIVED'))`").
- [X] T068 [P] [US1] No mesmo arquivo, `test_process_status_defaults_to_open`: `ProcessInstance` sem `status` → `'OPEN'` após `flush` (FR-002).
- [X] T069 [P] [US1] Em `tests/unit/core/test_process_lifecycle.py`, `test_available_actions_for_open`: `lifecycle_available_actions(status='OPEN', can_delete=True, can_review=True) == ['DELETE']`.
- [X] T070 [P] [US1] No mesmo arquivo, `test_available_actions_for_closed_and_cancelled` (`['ARCHIVE']` com `can_review`) e `test_available_actions_for_archived` (`[]`).
- [X] T071 [P] [US1] Em `tests/api/routers/test_process_lifecycle.py`, `test_create_process_returns_open` (US1-1).
- [X] T072 [P] [US1] No mesmo arquivo, `test_process_stays_open_after_submission` (US1-2).
- [X] T073 [P] [US1] No mesmo arquivo, `test_triage_approval_response_reports_open`: resposta com `process_status == 'OPEN'`, sem `new_process_status`, e `next_activity_run is None` (US1-3; `return_review_run` só existe a partir do PR 2).
- [X] T074 [P] [US1] No mesmo arquivo, `test_triage_rejection_closes_process`: `process_status == 'CLOSED'` na resposta e em `GET /processes/{id}` (US1-4).
- [X] T075 [P] [US1] No mesmo arquivo, `test_list_filters_by_lifecycle`: processos `OPEN` e `CLOSED`; `?status=CLOSED` só traz o fechado (US1-5).
- [X] T076 [P] [US1] No mesmo arquivo, `test_list_rejects_flow_status_filter`: `?status=TRIAGE` → 422 (US1-6).
- [X] T077 [P] [US1] No mesmo arquivo, `test_triage_decision_before_submission_is_conflict`: BraCVAM decide com a triagem ainda `BLOCKED` → 409 `invalid_transition` (FR-027).
- [X] T078 [P] [US1] No mesmo arquivo, `test_submission_update_after_submit_is_conflict`: `PATCH /processes/{id}` depois do envio → 409 (FR-028).
- [X] T079 [P] [US1] No mesmo arquivo, `test_no_response_contains_flow_status`: percorre criação, detalhe, listagem, envio e decisão e verifica que nenhum JSON contém `SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE` ou `PLANNING` como valor de `status`/`process_status` (SC-001).
- [X] T080 [P] [US1] Em `tests/api/routers/test_process_lifecycle.py`, `test_delete_and_archive_audit_record_lifecycle_statuses`: excluir um processo `OPEN` grava `PROCESS_DELETED` com `previous_status='OPEN'` e `result_status='CANCELLED'`; arquivá-lo grava `PROCESS_ARCHIVED` com `previous_status='CANCELLED'` e `result_status='ARCHIVED'` (FR-032).
- [X] T081 [P] [US1] Em `tests/integration/ai/test_run_pre_evaluation.py`, `test_execute_skips_when_run_no_longer_in_progress`: marcar a `EvaluationRun` como `completed` antes de `_execute` → nada é gravado e o processo continua `OPEN` (R8).
- [X] T082 [US1] **Teste de concorrência adiado por decisão do usuário.** Na implementação de T086, acrescentar em `src/pivma/core/pre_evaluation_service.py`, acima do `SELECT ... FOR UPDATE` da `EvaluationRun` em `_execute`, o comentário `# TODO(spec-030): teste de concorrência adiado — provar que _execute, retry_run e a contestação da IA sobre a mesma EvaluationRun têm um único vencedor (FR-031), com duas sessões reais como em tests/integration/database/test_process_retirement_concurrency.py.` Não criar o arquivo de teste.

### Implementation for User Story 1

- [X] T083 [US1] Em `src/pivma/core/database/models.py`, `ProcessInstance.status`: `default='OPEN'` e `CheckConstraint("status IN ('OPEN','CLOSED','CANCELLED','ARCHIVED')", name='ck_process_instances_status')` em `__table_args__`.
- [X] T084 [US1] Em `src/pivma/core/process_engine.py`: criar `STATUS_OPEN = 'OPEN'`; remover `STATUS_SUBMISSION`, `STATUS_AI_PRE_EVALUATION` e `PROPONENT_SCOPED_STATUSES`; remover as escritas `process.status = STATUS_AI_PRE_EVALUATION`, `'TRIAGE'`, `'SUBMISSION'`, `'PLANNING'` (hoje nas linhas ~2027, 2061, 2232, 2259); `'CLOSED'` passa a `STATUS_CLOSED`. `ensure_process_mutable` passa a exigir `status == STATUS_OPEN`.
- [X] T085 [US1] No mesmo arquivo, guardas por execução (R7): `execute_triage_decision` troca `process.status != 'TRIAGE'` por "`triage_evaluation` com execução `IN_PROGRESS`" (senão `ConflictError`); a edição da submissão (`status != STATUS_SUBMISSION`, ~linha 1087) passa a exigir execução `IN_PROGRESS` de `proposal_submission` com formulário não enviado. `execute_triage_decision` devolve `process.status` (ciclo de vida).
- [X] T086 [US1] Em `src/pivma/core/pre_evaluation_service.py` (R8): remover `_set_process_status` e suas 4 chamadas; `_execute` passa a travar a `EvaluationRun` (`SELECT ... FOR UPDATE WHERE id = run_id AND status = 'in_progress'`) e a checar `ProcessInstance.status == 'OPEN'`, no lugar da trava no processo; a checagem inicial (linhas ~88-93) e a varredura de execuções presas (~158) passam a filtrar pela `EvaluationRun`. Checagens de cancelado/arquivado usam `ensure_process_mutable` ou `status != 'OPEN'`.
- [X] T087 [US1] Em `src/pivma/schemas.py`: `ProcessLifecycle = Literal['OPEN','CLOSED','CANCELLED','ARCHIVED']`; aplicar em `ProcessInstanceDetail.status`, no item da listagem, em `ProcessSubmissionResponse.status` e `ProcessLifecycleResponse.status`/`previous_status`; `TriageDecisionResponse`: `new_process_status` → `process_status: ProcessLifecycle`. *Ajuste na implementação*: `next_activity_run` fica como está no PR 1 (no PR 1 o pedido de revisão ainda reabre a submissão, e o campo traz esse número); a troca por `return_review_run` entra no PR 2, com a revisão do retorno.
- [X] T088 [US1] Em `src/pivma/routers/processes.py`, `list_processes`: parâmetro `status: ProcessLifecycle | None`; manter a regra de arquivados (ocultos por padrão e só para acesso de revisão). Em `src/pivma/routers/triage.py`, montar a nova resposta.
- [X] T089 [US1] Atualizar os testes que assertam valores de fluxo, um arquivo por tarefa lógica, trocando por ciclo de vida ou por estado de atividade/fase conforme o que o teste prova: `tests/api/routers/test_process_router.py`, `test_process_submission_update.py`, `test_process_retirement.py`, `test_triage_decision.py`, `test_pre_evaluation_submit.py`, `test_activity_type_extension.py`, `test_ai_evaluations_config.py`, `test_evaluation_library.py`, `test_invite_acceptance.py`, `test_invites_router.py`, `test_participant_router.py`, `test_direct_review.py` (no PR 1 o endpoint ainda existe: trocar as asserções de status `TRIAGE` pelo estado `IN_PROGRESS` da atividade `triage_evaluation`; o arquivo é substituído depois por T125).
- [X] T090 [US1] Idem para `tests/unit/core/test_process_engine.py`, `test_process_retirement.py`, `test_triage_decoupled_form.py`, `tests/unit/test_structured_logging.py`, `tests/integration/ai/test_run_pre_evaluation.py`, `test_process_retirement_pre_evaluation.py`, `tests/integration/database/test_process_retirement_concurrency.py`, `tests/factories/process_factory.py` (`status = 'OPEN'`) e `tests/factories/process_retirement_factory.py`.
- [X] T091 [US1] Atualizar `tests/integration/journeys/test_pre_validated_method_triage.py`: `status == 'OPEN'` em todos os passos, `process_status == 'OPEN'` na decisão, e o proponente tentando decidir a triagem continua recebendo 403 (SC-004).
- [X] T092 [US1] Rodar T067–T082, a jornada e `grep -rnE "'(SUBMISSION|AI_PRE_EVALUATION|TRIAGE|PLANNING)'" src/pivma` — só podem sobrar ocorrências que não sejam status de processo (por exemplo, chave de atividade ou `condition_type`).

**Checkpoint**: US3 + US2 + US1 entregam o modelo novo com a fase 1 funcionando; o retorno ainda reabre a submissão diretamente, como hoje.

---

## Phase 6: User Story 6 - Processos existentes migram sem perder o ciclo de vida (Priority: P2) — parte 1, entra no PR 1

**Goal**: 1ª revisão Alembic (ciclo de vida e concessões), com upgrade e downgrade. Sem ela o MVP não roda num banco existente. A criação da revisão do retorno nos processos existentes fica na Phase 7 (T138, PR 2).

**Independent Test**: `poetry run pytest tests/integration/migrations/test_process_lifecycle_migration.py -q --no-cov` verde.

### Tests for User Story 6

Seguir o padrão de `tests/integration/migrations/test_task_assigned_role_normalization_migration.py` (upgrade até a revisão anterior, inserir dados, upgrade, verificar, downgrade).

- [X] T093 [P] [US6] `test_upgrade_maps_flow_statuses_to_open`: processos em `SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE`, `PLANNING` → `OPEN` (US6-1, FR-033).
- [X] T094 [P] [US6] `test_upgrade_preserves_terminal_statuses`: `CLOSED`, `CANCELLED`, `ARCHIVED` inalterados (US6-2).
- [X] T095 [P] [US6] `test_upgrade_backfills_activity_access`: atividades `proposal_submission` e `triage_evaluation` recebem a matriz da fase 1; chave desconhecida recebe `edit_roles = [assigned_role da tarefa mais recente]` e `view_roles` com `admin`/`bracvam` (R10).
- [X] T096 [P] [US6] `test_upgrade_adds_status_check_constraint`: depois do upgrade, inserir `status='TRIAGE'` falha.
- [X] T097 [P] [US6] `test_downgrade_rebuilds_flow_status_from_activities`: triagem `IN_PROGRESS` → `TRIAGE`; `EvaluationRun in_progress` → `AI_PRE_EVALUATION`; fase 1 `COMPLETED` → `PLANNING`; demais `OPEN` → `SUBMISSION`; colunas `view_roles`/`edit_roles` e `CHECK` removidos (US6-3, FR-034).
- [X] T098 [P] [US6] `test_pending_triage_still_decidable_after_upgrade`: processo em `TRIAGE` antes do upgrade → depois, BraCVAM decide via API com 200 (US6-4, SC-006).

### Implementation for User Story 6

- [X] T099 [US6] Criar `migrations/versions/<rev>_process_lifecycle_activity_access.py` com `down_revision = '1b1772b71863'` (1ª revisão, PR 1), implementando os passos 1, 2 e 4 de R10: update de status, default e `CHECK ck_process_instances_status`; colunas `view_roles`/`edit_roles` (`ARRAY(String(64))`, primeiro `nullable=True`, backfill, depois `NOT NULL`); matriz de backfill embutida na migração (não importar os YAMLs); `downgrade` na ordem inversa, reconstruindo o status de fluxo. **Não** cria `submission_return_review` (fica em T138, PR 2).
- [X] T100 [US6] Verificar que os testes de migração antigos que inserem status de fluxo em revisões anteriores (`tests/integration/migrations/test_configurable_ai_evaluation_migration.py`, `test_participant_migration.py`, `test_task_assigned_role_normalization_migration.py`) continuam verdes; ajustar só se fizerem upgrade até `head` com dados que o `CHECK` recusa.
- [X] T101 [US6] Rodar `poetry run alembic upgrade head` e `poetry run alembic downgrade -1` num banco limpo e confirmar sem erro. *Execução*: coberto pelos testes de migração, que partem de schema vazio no container, sobem até `head` (`3c9a1f2d7e40`) e descem para `1b1772b71863`; `alembic heads` confirma `3c9a1f2d7e40` como única head.

**Checkpoint (fim do PR 1)**: MVP com a 1ª revisão Alembic; roda num banco existente.

---

## Phase 7: User Story 4 - O proponente revisa o retorno da IA ou do BraCVAM (Priority: P2)

**Goal**: atividade `submission_return_review` com leitura do retorno e três escolhas; `direct-review` removido.

**Independent Test**: `poetry run pytest tests/api/routers/test_return_review.py tests/integration/journeys/test_return_review_via_triage.py tests/integration/journeys/test_return_review_via_ai.py -q --no-cov` verde.

### Tests for User Story 4

**Abertura** (`tests/api/routers/test_return_review.py`):

- [X] T102 [P] [US4] `test_new_process_has_blocked_return_review_without_run`: após criar o processo, a atividade `submission_return_review` existe, `BLOCKED`, sem `ActivityRun` e sem tarefa.
- [X] T103 [P] [US4] `test_triage_needs_revision_opens_return_review`: decisão `NEEDS_REVISION` → execução 1 `IN_PROGRESS`, tarefa `READY` com `assigned_role='proponent'`, `return_review_run == 1` na resposta; submissão **não** ganha nova execução ainda (US4-2, FR-036, FR-038).
- [X] T104 [P] [US4] `test_triage_rejection_does_not_open_return_review` e `test_triage_approval_does_not_open_return_review` (US4-8).
- [X] T105 [P] [US4] Em `tests/integration/ai/test_run_pre_evaluation.py`, ajustar `test_execute_persists_items_and_report_and_routes_negative`: negativo abre a revisão do retorno com `execution_reason='AI_PRE_EVALUATION'` e não abre nova execução da submissão (US4-1).
- [X] T106 [P] [US4] No mesmo arquivo, `test_failed_run_opens_return_review` (falha no provedor → mesma abertura).
- [X] T107 [P] [US4] No mesmo arquivo, `test_positive_result_does_not_open_return_review`.
- [X] T108 [P] [US4] `test_return_review_opened_event_is_audited`: `AuditEvent` `RETURN_REVIEW_OPENED` com `source` no `context_data` (data-model, audit_events).

**Leitura**:

- [X] T109 [P] [US4] `test_get_return_review_from_triage_shows_decision`: proponente → 200 com `source='TRIAGE'`, `triage_decision.justification` igual à da decisão, `available_choices == ['REVISE','WITHDRAW']` (FR-037).
- [X] T110 [P] [US4] `test_get_return_review_from_ai_shows_pre_evaluation`: `source='AI_PRE_EVALUATION'`, `ai_pre_evaluation` presente, `available_choices` inclui `CONTEST_AI`.
- [X] T111 [P] [US4] `test_get_return_review_404_when_none_open`.
- [X] T112 [P] [US4] `test_get_return_review_404_for_sponsor` e `test_get_return_review_200_for_bracvam_and_admin` (US4-7).

**Escolhas**:

- [X] T113 [P] [US4] `test_revise_opens_new_submission_draft_with_previous_values`: `REVISE` → 200, `submission_run == 2`; `GET .../proposal_submission/form` traz os valores anteriores e `is_submitted is False`; revisão do retorno `COMPLETED` e atividade `BLOCKED` (US4-3).
- [X] T114 [P] [US4] `test_contest_ai_moves_to_triage`: com origem IA, `CONTEST_AI` → `triage_evaluation` `IN_PROGRESS` e tarefa `bracvam` `READY`; `DirectReviewRequest` gravado (US4-4).
- [X] T115 [P] [US4] `test_contest_ai_rejected_for_triage_source`: origem triagem → 422.
- [X] T116 [P] [US4] `test_withdraw_closes_process`: `WITHDRAW` → `process_status == 'CLOSED'`, `closure_reason` preenchido, tarefas pendentes `CANCELLED` (US4-5).
- [X] T117 [P] [US4] `test_choice_is_audited`: `RETURN_REVIEW_DECIDED` com `choice`, `source` e `justification` (FR-040).
- [X] T118 [P] [US4] `test_bracvam_cannot_choose` e `test_admin_cannot_choose`: 403; `test_sponsor_choice_is_404` (US4-6).
- [X] T119 [P] [US4] `test_second_choice_is_conflict`: segunda escolha na mesma execução → 409 `invalid_transition` (FR-040).
- [X] T120 [P] [US4] `test_choice_on_closed_process_is_conflict`: processo `CANCELLED` com revisão aberta → 409.
- [X] T121 [P] [US4] `test_choice_requires_trusted_origin`: sem `Origin` → 403.
- [X] T122 [P] [US4] `test_submission_locked_while_return_review_open`: com revisão aberta, `PUT .../proposal_submission/form` → 409 (FR-038).
- [X] T123 [P] [US4] `test_admin_retry_cancels_open_return_review`: falha → revisão aberta; `POST /admin/pre-evaluations/{run_id}/retry` → execução da revisão `CANCELLED`, tarefa `CANCELLED`, atividade `BLOCKED` (R9).

**Concorrência e contrato removido**:

- [X] T124 [US4] **Teste de concorrência adiado por decisão do usuário.** Na implementação de T134, acrescentar em `src/pivma/core/return_review_service.py`, acima do `SELECT ... FOR UPDATE` da `ActivityRun` em `decide_return_review`, o comentário `# TODO(spec-030): teste de concorrência adiado — provar que duas escolhas simultâneas na mesma execução da revisão do retorno têm um único vencedor e a outra recebe ConflictError (FR-040), com duas sessões reais.` Não criar o arquivo de teste. A escolha repetida em sequência continua coberta por T119.
- [X] T125 [P] [US4] Em `tests/api/routers/test_direct_review.py`, substituir o conteúdo por `test_direct_review_route_is_removed`: `POST /processes/{id}/submission/direct-review` → 404 e o caminho não está em `/openapi.json`. Os comportamentos antigos migram para T114 e T115.

**Jornadas**:

- [X] T126 [P] [US4] `tests/integration/journeys/test_return_review_via_triage.py`: cadastro → criar → enviar → BraCVAM `NEEDS_REVISION` → proponente lê o retorno → `REVISE` → reenvia → BraCVAM aprova; `status == 'OPEN'` ao final e fase 1 `COMPLETED`.
- [X] T127 [P] [US4] `tests/integration/journeys/test_return_review_via_ai.py`: template com avaliação de IA configurada (template 4 ou configuração via `/ai-evaluations`, seguindo `tests/ai_eval_helpers.py`), `fake_provider` negativo, `_execute` explícito → proponente `CONTEST_AI` → BraCVAM aprova.
- [X] T128 [P] [US4] Em `tests/integration/migrations/test_process_lifecycle_migration.py`, `test_second_revision_adds_blocked_return_review_to_existing_processes`: aplicada a 2ª revisão, cada processo existente ganha `submission_return_review` `BLOCKED`, sem execução, com `edit_roles=['proponent']` e `view_roles=['admin','bracvam','proponent']`; o `downgrade` remove a atividade.

### Implementation for User Story 4

- [X] T129 [US4] Acrescentar `submission_return_review` à fase 1 dos 5 YAMLs em `src/pivma/templates_data/`: `name: "Revisão do Retorno"`, `assigned_role: "proponent"`, `activity_type: "return_review"`, `sla_hours: 168`, sem `form_template_key`, sem `dependencies`, `access: {edit: ["proponent"], view: []}`. `order_index` após `triage_evaluation`.
- [X] T130 [US4] Em `src/pivma/core/process_engine.py`, `instantiate_process` e `_advance_dependent_activities`: pular atividades com `activity_type == 'return_review'` (nascem `BLOCKED`, `blocked_reason='Sem retorno pendente.'`, sem execução nem tarefa) (R9).
- [X] T131 [US4] No mesmo arquivo, criar `open_return_review(session, process_id, *, source, user_id) -> int` (nova `ActivityRun` com `run_number` incremental e `execution_reason=source`, `Task` `READY` para `proponent` com `due_date` por `sla_hours`, atividade `IN_PROGRESS`, `AuditEvent RETURN_REVIEW_OPENED`); devolve o `run_number`.
- [X] T132 [US4] No mesmo arquivo, `_handle_needs_revision`: trocar `_open_new_submission_run` por `open_return_review(source='TRIAGE')`; manter `REVISION_REQUESTED`; devolver o número da execução para `return_review_run`.
- [X] T133 [US4] Em `src/pivma/core/pre_evaluation_service.py`, `_return_to_proponent`: trocar `_open_new_submission_run` por `open_return_review(source='AI_PRE_EVALUATION')`; `retry_run`: cancelar execução e tarefa abertas da revisão do retorno antes de criar a nova `EvaluationRun`.
- [X] T134 [US4] Criar `src/pivma/core/return_review_service.py` com `get_open_return_review(session, process_id, user_id)` (exige ver; monta o conteúdo por `source`) e `decide_return_review(session, process_id, user_id, choice, justification)`: trava a `ActivityRun` aberta (`FOR UPDATE`), exige editar, valida `choice` contra `source`, aplica `REVISE` (`_open_new_submission_run`), `CONTEST_AI` (`request_direct_review`) ou `WITHDRAW` (`CLOSED` + `closed_at` + `closure_reason` + `_cancel_pending_children` + `PROCESS_WITHDRAWN`), conclui execução e tarefa, grava `RETURN_REVIEW_DECIDED` e faz `commit`.
- [X] T135 [US4] Em `src/pivma/schemas.py`, criar `ReturnReviewChoice = Literal['REVISE','CONTEST_AI','WITHDRAW']`, `ReturnReviewResponse`, `ReturnReviewDecisionRequest` (`extra='forbid'`) e `ReturnReviewDecisionResponse` conforme `contracts/http-api.md`. Remover `DirectReviewResponse` e `DirectReviewRequestBody`.
- [X] T136 [US4] Criar `src/pivma/routers/return_review.py` com `GET` e `POST /processes/{id}/return-review` (`TrustedOrigin` no POST; `NotFoundError` 404, `AuthorizationError` 403, `ConflictError` 409 `invalid_transition`, `ValidationError` 422) e registrar em `src/pivma/__init__.py`.
- [X] T137 [US4] Em `src/pivma/routers/pre_evaluation.py`, remover a rota `request_direct_review`. Manter `pre_evaluation_service.request_direct_review` (usado por T134).
- [X] T138 [US4] Criar `migrations/versions/<rev>_return_review_activity.py` (2ª revisão, PR 2) com `down_revision` = revisão de T099: insere `submission_return_review` (`BLOCKED`, `activity_type='return_review'`, `blocked_reason='Sem retorno pendente.'`, concessões de `data-model.md`) na fase 1 de cada processo que não a tenha; `downgrade` remove essas atividades (passo 3 de R10).
- [ ] T139 [US4] Rodar T102–T127 e confirmar verde.

**Checkpoint**: retorno pela IA e pela triagem passa pela revisão do retorno.

---

## Phase 8: User Story 5 - Fases e atividades guardam onde o processo está (Priority: P2)

**Goal**: provar que fases e atividades bastam para a posição no fluxo e que `/tasks` respeita as concessões com paralelismo. Nenhum endpoint expõe fases (o processo expõe só o ciclo de vida); o estado de fase e atividade é verificado no banco pela `session` do teste.

**Independent Test**: `poetry run pytest tests/api/routers/test_activity_parallel_visibility.py -q --no-cov` verde.

### Tests for User Story 5

- [ ] T140 [P] [US5] Em `tests/api/routers/test_activity_parallel_visibility.py`, `test_phase1_completed_after_triage_approval`: após aprovar via API, consultar `Phase` na `session` e verificar `status == 'COMPLETED'` na fase 1; `GET /processes/{id}` segue `OPEN` (US5-1).
- [ ] T141 [P] [US5] No mesmo arquivo, `test_parallel_activities_both_in_progress_for_user_with_both_grants`: no template 4, após a aprovação, liberar duas atividades da fase 2 com cargos diferentes; um usuário com os dois cargos recebe as duas tarefas em `GET /tasks?process_id=`, e as duas `ActivityInstance`, consultadas na `session`, estão `IN_PROGRESS` (US5-2). Se o template não tiver duas atividades liberadas ao mesmo tempo, montar o cenário com um dicionário de template de teste via `sync_template_from_dict`.
- [ ] T142 [P] [US5] No mesmo arquivo, `test_parallel_activities_filtered_by_grant`: usuário com só um dos cargos recebe só a tarefa da atividade concedida em `GET /tasks?process_id=` (US5-3, SC-005).

### Implementation for User Story 5

- [ ] T143 [US5] Nenhum código novo esperado. Se T140–T142 falharem, corrigir apenas o ponto específico (fase não marcada como concluída ou filtro de tarefa) em `src/pivma/core/process_engine.py` ou `src/pivma/routers/tasks.py`, registrando a causa na descrição do commit.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T144 Atualizar `README.md`: ciclo de vida do processo, acesso por atividade (`access` nos templates), revisão do retorno e rotas novas, remoção de `direct-review`, mudança incompatível para o frontend (seção de contratos de API).
- [X] T145 [P] Atualizar docstrings e comentários que citam os status removidos (`grep -rnE "SUBMISSION|AI_PRE_EVALUATION|PROPONENT_SCOPED|PLANNING" src/pivma`), sem mudar lógica.
- [X] T146 Rodar `poetry run pytest -q` e `poetry run ruff check . && poetry run ruff format --check .`; comparar com a linha de base de T002 e registrar o resultado real em Notes.
- [X] T147 Rodar os cenários de `quickstart.md` e marcar os que foram realmente executados.

---

## Dependencies & Execution Order

```text
Setup (T001–T002)
   └─▶ Foundational (T003–T004)
          └─▶ US3 concessões (T005–T023)
                 └─▶ US2 acesso por atividade (T024–T066)
                        └─▶ US1 ciclo de vida + trava IA (T067–T092)
                               └─▶ US6 parte 1: 1ª revisão Alembic (T093–T101)   ← fim do PR 1 (MVP)
                                      └─▶ US4 revisão do retorno + 2ª revisão Alembic (T102–T139)   ← PR 2
                                             └─▶ US5 fases/paralelismo (T140–T143)   ← PR 3
Polish (T144–T147) ao fim de cada PR
```

- **Por que US3 → US2 → US1**: remover `SUBMISSION`/`AI_PRE_EVALUATION` (US1) apaga a regra de visibilidade atual; a regra por atividade (US2) precisa estar no ar antes, e ela depende das colunas preenchidas (US3). Entregar US1 sozinho abriria ou fecharia acesso errado.
- **US6** tem duas partes: a 1ª revisão Alembic (Phase 6) fecha o PR 1; a 2ª revisão, que cria `submission_return_review` nos processos existentes (T128 e T138), fica na Phase 7 junto com a US4, porque depende da atividade nova nos YAMLs (T129).
- Dentro de cada história: testes → modelo → serviço → rota → ajuste de testes antigos.

## Parallel Opportunities

- **US3**: T005–T010 (mesmo arquivo, funções independentes; escrever juntos) em paralelo com T011–T015; T020 e T021 em paralelo.
- **US2**: T024–T029, T030–T047 e T051–T054 são arquivos distintos e podem ser escritos em paralelo; a implementação T055→T058 é sequencial (mesmos módulos), T062–T064 em paralelo depois de T056.
- **US1**: T067–T081 em paralelo; T083 e T087 em paralelo; T089 e T090 divididos entre pessoas.
- **US4**: os testes T102–T123 e T125–T128 em paralelo; T129 em paralelo com T135.
- **US6**: T093–T098 em paralelo.

### Exemplo: US2

```text
Em paralelo:
  T024–T029  tests/integration/database/test_user_cargos.py
  T030–T047  tests/api/routers/test_activity_access.py
  T051–T053  tests/api/routers/test_tasks_visibility.py
  T054       tests/api/routers/test_timeline_router.py
Depois, em sequência: T055 → T056 → T057 → T058 → T059 → T060
Em paralelo: T061, T062, T063, T064
```

## Implementation Strategy

**Decidido pelo usuário: três PRs, na ordem abaixo.** Cada PR sai da branch
anterior já mergeada na `develop`, nunca empilhado sobre uma branch aberta
(ver o incidente do #53/#54).

1. **PR 1 — MVP (Phases 1–6)**: US3 + US2 + US1 + a **primeira revisão
   Alembic** (T093–T101: status, `CHECK`, `view_roles`/`edit_roles` e
   backfill). Entrega o ciclo de vida exposto e o acesso por atividade/cargo,
   com a fase 1 funcionando. O retorno ainda reabre a submissão direto, mas já
   protegido pela concessão.
2. **PR 2 — Revisão do retorno (Phase 7)**: US4, com a remoção de
   `direct-review` e a **segunda revisão Alembic**, que só cria
   `submission_return_review` nos processos existentes (T128, T138).
3. **PR 3 — Paralelismo (Phase 8)**: US5.
4. **Polish (Phase 9)**: README e varredura de comentários em cada PR que muda
   contrato; T146/T147 ao fim de cada PR.

Testes de concorrência novos ficam fora dos três PRs (T082, T124): o código
recebe TODOs marcados `TODO(spec-030)` para retomar depois.

## Notes

- Linha de base (T002), em `develop` + branch recém-criada, antes de qualquer mudança: `pytest` → 809 passed, 0 failed; `ruff check .` → sem erros.
- Resultado do PR 1 (T146), em `feat/030-process-lifecycle-activity-access`: `pytest` → 870 passed, 1 skipped, 0 failed (cobertura 92%); `ruff check .` sem erros; `ruff format --check` limpo nos arquivos desta feature (os avisos restantes são de arquivos anteriores à branch, como `migrations/versions/*` e `specs/028-*/data-model.md`, e não foram tocados). Depois dessa rodada houve só formatação e reversão de formatação alheia; os arquivos afetados foram re-testados (67 passed).
- Cenários do quickstart executados no PR 1 (T147): 1 (jornada), 2 (triagem rejeita), 6 (matriz de acesso), 7 (Admin não decide), 8 (`sponsor` vê cabeçalho e não a submissão), 9 (`?status=TRIAGE` → 422), 11 (migração) e 12 (sem status de fluxo nas respostas), todos por testes automatizados. 3, 4 e 5 dependem da revisão do retorno (PR 2); 10 foi adiado (`TODO(spec-030)`). A checagem manual no app (seção 4) não foi feita.
- Polish (T144–T147) marcado para o PR 1; repetir T146/T147 ao fim do PR 2 e do PR 3.
- Decisões tomadas durante a implementação do PR 2 (branch `feat/030-return-review`):
  - `REVISION_REQUESTED` continua sendo gravado no momento do retorno, com `new_run_number` = execução da submissão que abrirá se o proponente escolher revisar. É o que `GET /processes/{id}/submission-versions` usa para projetar as versões devolvidas.
  - `get_current_form_instance`, `get_current_activity_run` e `_open_triage_run` passaram a recarregar a coleção `runs` (`populate_existing`). Sem isso, uma sessão que já tinha carregado a atividade não via a execução nova aberta pelo `REVISE`.
  - A escolha `CONTEST_AI` chama `pre_evaluation_service.request_direct_review`, que faz o `commit`; em `ConflictError` a sessão é revertida antes de propagar.
  - Os testes que simulavam "retorno reabre a submissão" ganharam o passo `REVISE` (`test_triage_decision`, `test_form_attachments`, `test_process_submission_update`, `test_process_engine`, `test_activity_due_date`); `back_with_proponent` passou a significar "revisão do retorno aberta".
- Resultado do PR 2 (T146): `pytest` → 893 passed, 1 skipped, 0 failed (cobertura 92%); `ruff check .` sem erros. Cenários do quickstart executados por testes automatizados (T147): 3 (retorno pela triagem → `REVISE`), 4 (IA negativa → `CONTEST_AI`) e 5 (`WITHDRAW`); a checagem manual no app não foi feita.
- Decisões tomadas durante a implementação do PR 1:
  - `require_activity_access` e `activity_view_clause` ficaram em `core/process_engine.py` (não em `authorization.py`), para usar as exceções do motor sem import circular; `user_cargos`, `global_cargos` e `process_cargos_scope` ficaram em `authorization.py`.
  - Conflito de interesse bloqueia a **edição** acima das concessões; a leitura continua como antes (não havia bloqueio de leitura por conflito).
  - `process_visibility_clause` deixou de liberar quem só tem `triage.review` sem perfil de plataforma (R5). Testes de exclusão por "revisor sem acesso de plataforma" passaram de 403 para 404.
  - `POST /processes/{id}/submission/direct-review` continua no PR 1, mas responde `process_status: 'OPEN'`.
  - O BraCVAM deixou de poder editar o rascunho do proponente via `PATCH /processes/{id}` (antes permitido); `test_bracvam_can_patch_draft` virou `test_bracvam_cannot_patch_draft`.
