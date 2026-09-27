---

description: "Task list — Spec 031: Definição e Preparação das Amostras (estudo cego)"
---

# Tasks: Definição e Preparação das Amostras — estudo cego

**Input**: Design documents from `specs/031-blind-sample-coding/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [quickstart.md](quickstart.md)

**Tests**: Obrigatórios (AGENTS.md). Seguem `.agents/skills/fastapi-testing-methodology/`: um comportamento observável por tarefa, testes antes da implementação de cada história; sucesso, cada erro/status, autorização, isolamento, auditoria e concorrência separados. Risco: **crítico** para isolamento do conteúdo de amostras e ausência de identidade química no QR/visão cega/auditoria (unit + integração + API + segurança); **alto** para geração de códigos, conclusão/congelamento, templates e migração (unit + integração + API); **médio** para listagem e etiquetas (API).

**Organization**: Por user story. A ordem das fases segue a dependência, não o número da história: US6 → US1 → US2 → US5 → US3 → US4 (ver [Dependencies](#dependencies--execution-order)).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: user story da spec (US1…US6)
- Comandos com `poetry run`; testes isolados com `--no-cov`

## Convenções de teste desta feature

- Autenticação nos testes de API: `authenticate(client, user)` de `tests/api/routers/test_rbac_router.py`.
- Usuários BraCVAM/Admin: fixtures `bracvam_user` e `ai_eval_admin` de `tests/conftest.py`.
- Cargo sem laboratório: `grant_cargo` de `tests/factories/participant_factory.py`. Cargo de laboratório: `AssignmentFactory(process=..., user=..., role_key='participating_laboratory', laboratory=lab)` com `LaboratoryFactory`/`InstitutionFactory` de `tests/factories/institutional_factory.py`.
- Processo de amostras pronto para uso: helpers de `tests/factories/sample_factory.py` (T005), que usam um template mínimo com `sample_definition` sem dependências (já `IN_PROGRESS`) para não depender da Fase 2 nos testes de US1–US4.
- Templates reais: `bootstrap_all_templates(session)` de `pivma.bootstrap_process_templates`; jornadas com helpers de `tests/integration/journeys/conftest.py`.
- Endpoints mutáveis exigem header `Origin: https://testserver`.
- Asserções de "sem identidade": serializar a resposta/QR/`context_data` com `json.dumps` e verificar que `chemical_name`, `cas_number`, `lot` e os códigos cegos (quando aplicável) não aparecem como substring.

---

## Phase 1: Setup

**Purpose**: linha de base e dependência nova.

- [X] T001 Rodar `poetry run pytest -q` e `poetry run ruff check .` na branch `feat/031-blind-sample-coding` e anotar em `specs/031-blind-sample-coding/tasks.md` (seção Notes) a contagem de testes passando/falhando. Falhas pré-existentes ficam listadas e não são atribuídas a esta feature.
- [X] T002 Adicionar `segno` com `poetry add segno` (atualiza `pyproject.toml` e `poetry.lock`); conferir `poetry run python -c "import segno; segno.make('x').svg_data_uri()"` (research R8).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: modelos, migração, setting, helpers de teste e o guarda de acesso usados por todas as histórias.

- [X] T003 Em `src/pivma/core/database/models.py`, criar `StudySubstance` (`__tablename__ = 'study_substances'`, `AuditMixin`) com: `id` UUID PK; `process_instance_id` FK `process_instances.id`; `chemical_name: String(255)` obrigatório; `cas_number: String(12)` obrigatório; `lot: String(64)` obrigatório; `purity: String(64)` opcional; `solubility: Text` opcional; `safe_handling_instructions: Text` obrigatório; `sds_artifact_id` FK `artifacts.id` nullable. Índice `uq_study_substances_process_cas_active` único em `(process_instance_id, cas_number)` com `postgresql_where` `deleted_at IS NULL` (mesmo padrão de `uq_assignments_active`).
- [X] T004 No mesmo arquivo, criar `BlindSampleCode` (`__tablename__ = 'blind_sample_codes'`, `AuditMixin`) com: `id` UUID PK; `process_instance_id` FK `process_instances.id`; `substance_id` FK `study_substances.id`; `laboratory_id` FK `laboratories.id`; `code: String(8)`. Índices parciais (`deleted_at IS NULL`): `uq_blind_sample_codes_process_code_active` em `(process_instance_id, code)` e `uq_blind_sample_codes_substance_lab_active` em `(substance_id, laboratory_id)`.
- [X] T005 [P] Criar `tests/factories/sample_factory.py` com: `SAMPLE_TEMPLATE` (dicionário mínimo: 1 fase, 1 atividade `sample_definition`, `activity_type: 'sample_definition'`, `assigned_role: 'sample_selection_group'`, `access: {edit: ['sample_selection_group'], view: []}`, `dependencies: []`); `async def sample_process(session, *, lab_count=3)` que sincroniza o template via `sync_template_from_dict`, instancia com `instantiate_process`, cria o usuário do Grupo de Seleção (`grant_cargo(..., role_key='sample_selection_group')`) e `lab_count` laboratórios participantes (instituição, laboratório, usuário, afiliação, `Assignment` com `laboratory_id`) e devolve um `SimpleNamespace(process_id, selector, labs, lab_users)`; `async def add_participating_lab(session, process_id)` para vincular mais um; `def substance_payload(**overrides)` com valores válidos (CAS padrão `50-00-0`) e um contador para CAS únicos válidos (`7732-18-5`, `64-17-5`, `67-64-1`, `71-43-2`, …).
- [X] T006 Criar a migração `migrations/versions/<rev>_blind_sample_coding.py` com `down_revision = '7e21b4c0a9d3'`: cria `study_substances` e `blind_sample_codes` com as FKs de auditoria (`fk_<tabela>_created_by/updated_by/deleted_by`) e os três índices parciais de T003/T004; `downgrade` remove índices e tabelas. Conferir com `poetry run alembic upgrade head` e `poetry run alembic downgrade -1` num banco local.
- [X] T007 [P] Em `tests/integration/migrations/test_blind_sample_migration.py`, `test_upgrade_creates_sample_tables_and_partial_indexes`: após `run_migration` até a nova revisão, as duas tabelas e os três índices existem e os índices são parciais (`indexdef` contém `WHERE (deleted_at IS NULL)`). Seguir o padrão de `tests/integration/migrations/test_process_lifecycle_migration.py`.
- [X] T008 [P] No mesmo arquivo, `test_downgrade_drops_sample_tables`: após `run_downgrade` para `7e21b4c0a9d3`, as duas tabelas não existem.
- [X] T009 [P] Em `src/pivma/core/settings.py`, acrescentar `SAMPLE_QR_BASE_URL: str | None = Field(default=None)` com comentário "Spec 031: base da URL do frontend gravada no QR code; sem valor, usa a primeira origem de `AUTH_ALLOWED_ORIGINS`" (research R8).
- [X] T010 Criar `src/pivma/core/sample_service.py` com docstring da Spec 031, a constante `SAMPLE_ACTIVITY_KEY = 'sample_definition'` e `async def _sample_activity(session, process_id, user_id, *, lock=False) -> ActivityInstance`: busca a `ActivityInstance` do processo com essa chave (`deleted_at IS NULL`, processo não excluído; `NotFoundError` se não existir), aplica `with_for_update()` quando `lock=True` e chama `require_activity_access(session, user_id, act, 'edit')` — **sempre edição, também nas leituras** (research R3). Erros de domínio de `process_engine` (`NotFoundError`, `AuthorizationError`, `ConflictError`, `ValidationError`), sem `HTTPException`.
- [X] T011 Criar `src/pivma/routers/samples.py` com `router = APIRouter(prefix='/processes', tags=['Samples'])` e a função `_http_error(exc)` que traduz `NotFoundError`→404, `AuthorizationError`→403, `ConflictError`→409 (`detail={'code': exc.code or 'invalid_transition', 'message': ...}`), `ValidationError`→422 (`detail={'code': ..., 'message': ..., **extra}`), e `AttachmentError` via o mesmo mapeamento de `_ATTACHMENT_ERROR_STATUS` de `routers/forms.py`. Registrar com `app.include_router(samples.router)` em `src/pivma/__init__.py`. Se `ConflictError`/`ValidationError` não aceitarem `code`, definir em `sample_service.py` subclasses `SampleConflictError(ConflictError)`/`SampleValidationError(ValidationError)` com atributos `code` e `extra`.

**Checkpoint**: `poetry run pytest tests/integration/migrations/test_blind_sample_migration.py -q --no-cov` verde; app sobe com o roteador vazio.

---

## Phase 3: User Story 6 - Fase 2 em todos os templates (Priority: P1)

**Goal**: os cinco templates têm a Fase 2 com as oito atribuições e a atividade `sample_definition`, que abre só depois das atribuições do Grupo de Seleção e dos laboratórios participantes.

**Independent Test**: `poetry run pytest tests/integration/bootstrap/test_template_phase_2.py tests/api/routers/test_sample_activity_unlock.py tests/api/routers/test_activity_type_extension.py -q --no-cov` verde.

### Tests for User Story 6

> Escrever primeiro e confirmar que falham.

- [X] T012 [P] [US6] Em `tests/integration/bootstrap/test_template_phase_2.py`, `test_all_templates_share_the_same_phase_2_role_assignments`: carrega os 5 YAMLs com `load_yaml_template`; a fase `phase_2_role_assignment` existe em todos e, para as oito atividades `assign_*`, `key`, `assigned_role`, `access`, `activity_type`, `target_role_key` e `dependencies` são idênticos aos do template 04 (FR-001; risco de divergência apontado no plan).
- [X] T013 [P] [US6] No mesmo arquivo, `test_all_templates_declare_sample_definition_in_phase_2`: em cada YAML, `sample_definition` está na Fase 2 com `activity_type == 'sample_definition'`, `assigned_role == 'sample_selection_group'`, `access == {'edit': ['sample_selection_group'], 'view': []}` e dependências `ACTIVITY_COMPLETED`/`COMPLETED` exatamente em `assign_sample_selection_group` e `assign_participating_laboratory` (FR-002, FR-003).
- [X] T014 [P] [US6] No mesmo arquivo, `test_sample_definition_instantiates_with_edit_only_for_sample_group`: `bootstrap_all_templates` + `instantiate_process` em cada template; a `ActivityInstance` `sample_definition` nasce `BLOCKED`, com `edit_roles == ['sample_selection_group']` e `view_roles == ['admin', 'bracvam', 'sample_selection_group']` (data-model, FR-003).
- [X] T015 [P] [US6] No mesmo arquivo, `test_bootstrap_publishes_new_versions_and_keeps_previous`: após sincronizar, para cada template, um dicionário com a mesma `key` e a `version` anterior (2, ou 4 no template 04) e rodar `bootstrap_all_templates`, `pre_validated_method`, `scope_extension`, `me_too_validation` e `proof_of_concept` têm a versão 3 e `validated_method_dossier` a versão 5, e a `ProcessTemplateVersion` antiga continua existindo sem exclusão lógica (FR-004).
- [X] T016 [P] [US6] No mesmo arquivo, `test_existing_process_keeps_its_template_version_structure`: processo instanciado numa versão antiga (dicionário sem Fase 2) continua sem atividades da Fase 2 depois de `bootstrap_all_templates` (FR-004, cenário US6-4).
- [X] T017 [P] [US6] Em `tests/api/routers/test_sample_activity_unlock.py`, fixture que cria um processo `pre_validated_method` e aprova a triagem (seguir `test_role_assignment_activities_unlock_on_triage_approval` de `tests/api/routers/test_activity_type_extension.py` e os helpers de jornada), e `test_phase_2_opens_for_template_01_after_triage_approval`: após a aprovação, `assign_sponsor` e `assign_group_manager` estão `IN_PROGRESS` e `sample_definition` está `BLOCKED` (cenário US6-1).
- [X] T018 [P] [US6] No mesmo arquivo, `test_sample_activity_stays_blocked_with_only_sample_group_assigned`: com Grupo Gestor atribuído e só o Grupo de Seleção designado (`POST /processes/{id}/participants`), `sample_definition` continua `BLOCKED` (cenário US6-2).
- [X] T019 [P] [US6] No mesmo arquivo, `test_sample_activity_stays_blocked_with_only_participating_lab_assigned`: só um laboratório participante designado → `sample_definition` `BLOCKED`.
- [X] T020 [P] [US6] No mesmo arquivo, `test_sample_activity_opens_after_both_assignments`: Grupo de Seleção e um laboratório participante designados → `sample_definition` `IN_PROGRESS` e `GET /tasks?process_id=` do usuário do Grupo de Seleção traz a tarefa "Definição e Preparação das Amostras" (cenário US6-3, SC-005).
- [X] T021 [P] [US6] No mesmo arquivo, `test_sample_activity_opens_for_every_template`: parametrizado pelos 5 `template_key`, repetir o fluxo mínimo de T020 e verificar `sample_definition` `IN_PROGRESS` (SC-005). Usar os payloads de submissão de cada formulário já usados nos testes existentes (ver `tests/integration/journeys/`).

### Implementation for User Story 6

- [X] T022 [P] [US6] Em `src/pivma/templates_data/04_validated_method_dossier.yaml`, `version: 4` → `5`; acrescentar à Fase 2, após `assign_adhoc_evaluator`, a atividade `sample_definition` (`name: "Definição e Preparação das Amostras"`, `order_index: 9`, `assigned_role: "sample_selection_group"`, `access: {edit: ["sample_selection_group"], view: []}`, `activity_type: "sample_definition"`, dependências `assign_sample_selection_group` e `assign_participating_laboratory` com `required_status: "COMPLETED"`, `condition_type: "ACTIVITY_COMPLETED"`) com comentário citando a Spec 031.
- [X] T023 [P] [US6] Em `src/pivma/templates_data/01_pre_validated_method.yaml`, `version: 2` → `3` e acrescentar a fase `phase_2_role_assignment` idêntica à do template 04 (as oito `assign_*` e `sample_definition` de T022), com o comentário de origem (Spec 028 + Spec 031).
- [X] T024 [P] [US6] Idem T023 em `src/pivma/templates_data/02_scope_extension.yaml`.
- [X] T025 [P] [US6] Idem T023 em `src/pivma/templates_data/03_me_too_validation.yaml`.
- [X] T026 [P] [US6] Idem T023 em `src/pivma/templates_data/05_proof_of_concept.yaml`.
- [X] T027 [US6] Em `tests/api/routers/test_activity_type_extension.py`, ajustar `test_template_detail_defaults_activity_type_for_legacy_templates` para aceitar `role_assignment` nas `assign_*` e `sample_definition` em `sample_definition` (as demais continuam `form`), e `test_role_assignment_activities_unlock_on_triage_approval` para `version_number == 5` e a atividade nova na Fase 2 (research R2).
- [X] T028 [US6] Rodar `poetry run pytest -q --no-cov` e corrigir outros testes que dependam do número de versão ou da contagem de atividades dos templates (ex.: `grep -rn "version_number\|'version'" tests/`), registrando em Notes cada arquivo ajustado.

**Checkpoint**: US6 verde; a suíte completa não regrediu.

---

## Phase 4: User Story 1 - Cadastrar substâncias e gerar códigos cegos (Priority: P1) 🎯 MVP

**Goal**: o Grupo de Seleção cadastra, altera, remove e lista substâncias; cada cadastro gera um código opaco por laboratório participante ativo.

**Independent Test**: `poetry run pytest tests/unit/core/test_sample_service.py tests/api/routers/test_samples_router.py -k "substance or code or cas" tests/integration/database/test_sample_concurrency.py -q --no-cov` verde; 4 substâncias × 3 laboratórios → 12 códigos únicos.

### Tests for User Story 1

> Escrever primeiro e confirmar que falham.

**Unitários — `tests/unit/core/test_sample_service.py`**

- [X] T029 [P] [US1] `test_validate_cas_accepts_valid_numbers`: parametrizado com `50-00-0`, `7732-18-5`, `64-17-5`, `1310-73-2` → `validate_cas` devolve o número normalizado (sem espaços nas pontas) (FR-006).
- [X] T030 [P] [US1] `test_validate_cas_rejects_wrong_check_digit`: `50-00-1` e `7732-18-4` levantam `ValidationError` com `code='invalid_cas'` (FR-006).
- [X] T031 [P] [US1] `test_validate_cas_rejects_bad_format`: parametrizado com `''`, `'5-00-0'` (1º grupo com menos de 2 dígitos), `'12345678-00-0'` (mais de 7), `'50-0-0'`, `'50000'`, `'ab-cd-e'` → `ValidationError` `code='invalid_cas'` (formato `^\d{2,7}-\d{2}-\d$`).
- [X] T032 [P] [US1] `test_generate_code_has_eight_chars_from_safe_alphabet`: 1.000 chamadas a `generate_code()` produzem strings de 8 caracteres, todas contidas em `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (FR-011, research R5).
- [X] T033 [P] [US1] `test_generate_code_never_uses_ambiguous_characters`: nas mesmas 1.000 chamadas, nenhum código contém `0`, `O`, `1`, `I` ou `L`.
- [X] T034 [P] [US1] `test_unique_code_retries_on_collision`: com `secrets.choice` monkeypatchado para produzir primeiro um código já presente no conjunto `taken` e depois outro, `unique_code(taken)` devolve o segundo (research R5, edge case de colisão).
- [X] T035 [P] [US1] `test_unique_code_gives_up_after_ten_collisions`: com `secrets.choice` sempre produzindo um código em `taken`, `unique_code` levanta `RuntimeError` após 10 tentativas.

**API — `tests/api/routers/test_samples_router.py`** (usar `sample_process` de T005)

- [X] T036 [P] [US1] `test_create_substance_returns_201_with_one_code_per_lab`: com 3 laboratórios, `POST /processes/{id}/samples` → **201**, corpo com os campos enviados, `sds: null` e 3 `blind_codes` com `laboratory_id` distintos, códigos distintos e `laboratory_name` preenchido (cenário US1-1, FR-010).
- [X] T037 [P] [US1] `test_four_substances_three_labs_yield_twelve_unique_codes`: 4 cadastros → `GET /processes/{id}/samples` traz 12 códigos únicos no processo (cenário US1-2, SC-001).
- [X] T038 [P] [US1] `test_create_substance_without_labs_returns_empty_codes`: `sample_process(lab_count=0)` → **201** com `blind_codes == []`.
- [X] T039 [P] [US1] `test_lab_with_two_users_gets_single_code`: um laboratório com dois usuários designados como participantes → a substância recebe 1 código para esse laboratório (FR-012).
- [X] T040 [P] [US1] `test_revoked_lab_assignment_gets_no_code`: laboratório cuja única designação tem `revoked_at` preenchido não recebe código (research R4).
- [X] T041 [P] [US1] `test_deleted_laboratory_gets_no_code`: laboratório com `deleted_at` preenchido não recebe código (research R4).
- [X] T042 [P] [US1] `test_lead_laboratory_gets_no_code`: laboratório designado só como `lead_laboratory` não recebe código (Assumptions).
- [X] T043 [P] [US1] `test_create_duplicate_cas_in_same_process_returns_409`: segundo cadastro com o mesmo CAS → **409** `detail.code == 'duplicate_cas'` (cenário US1-3, FR-005).
- [X] T044 [P] [US1] `test_same_cas_in_another_process_is_accepted`: o mesmo CAS em outro `sample_process` → **201** (cenário US1-4).
- [X] T045 [P] [US1] `test_create_with_invalid_cas_returns_422`: CAS `50-00-1` → **422** `detail.code == 'invalid_cas'`, nenhuma substância gravada (cenário US1-5).
- [X] T046 [P] [US1] `test_create_missing_required_field_returns_422`: parametrizado removendo `chemical_name`, `cas_number`, `lot` e `safe_handling_instructions` (e com cada um como string só de espaços) → **422** (FR-005).
- [X] T047 [P] [US1] `test_create_rejects_field_over_max_length`: `chemical_name` com 256 caracteres, `lot` com 65 e `purity` com 65 → **422** (limites `String(255)`/`String(64)` do data-model).
- [X] T048 [P] [US1] `test_list_substances_ordered_by_creation`: três cadastros → `GET` devolve `activity_status == 'IN_PROGRESS'` e `substances` na ordem de criação (contrato).
- [X] T049 [P] [US1] `test_patch_substance_updates_data_and_keeps_codes`: `PATCH` alterando `lot` e `purity` → **200** com os novos valores e os mesmos códigos (cenário US1-6, FR-008).
- [X] T050 [P] [US1] `test_patch_to_duplicate_cas_returns_409`: `PATCH` para o CAS de outra substância do processo → **409** `duplicate_cas`.
- [X] T051 [P] [US1] `test_patch_substance_of_other_process_returns_404`: `PATCH` em `substance_id` de outro processo (onde o usuário também é Grupo de Seleção) pela rota deste processo → **404**.
- [X] T052 [P] [US1] `test_delete_substance_removes_it_and_its_codes`: `DELETE` → **204**; `GET` não traz a substância; no banco, a substância e seus `BlindSampleCode` têm `deleted_at` preenchido (cenário US1-7).
- [X] T053 [P] [US1] `test_cas_can_be_reused_after_delete`: remover e cadastrar de novo o mesmo CAS → **201** (índice parcial).
- [X] T054 [P] [US1] `test_mutation_on_blocked_activity_returns_409`: com `sample_definition` `BLOCKED` (processo de template real antes das atribuições), `POST` → **409** `invalid_transition` e `GET` → **200** com `substances == []` e `activity_status == 'BLOCKED'` (data-model, tabela de status).
- [X] T055 [P] [US1] `test_mutation_on_closed_process_returns_409`: processo com `status='CLOSED'` → `POST`, `PATCH` e `DELETE` → **409** `invalid_transition` (FR-009, edge case).
- [X] T056 [P] [US1] `test_create_emits_audit_events_without_identity`: após `POST`, existem `SAMPLE_SUBSTANCE_REGISTERED` (com `substance_id`) e `SAMPLE_CODES_GENERATED` (com `substance_id`, `code_count == 3` e `laboratory_ids`), ambos com `activity_run_id` da execução e `user_id` do autor; `json.dumps(context_data)` não contém nome químico, CAS, lote nem nenhum código (FR-025, research R9).
- [X] T057 [P] [US1] `test_update_and_delete_emit_audit_events_without_identity`: `PATCH` gera `SAMPLE_SUBSTANCE_UPDATED` e `DELETE` gera `SAMPLE_SUBSTANCE_REMOVED`, cada um com `substance_id` e sem identidade química.

**Concorrência — `tests/integration/database/test_sample_concurrency.py`**

- [X] T058 [P] [US1] `test_concurrent_creates_with_same_cas_accept_only_one`: duas sessões independentes chamam `sample_service.create_substance` com o mesmo CAS em paralelo (`asyncio.gather`); uma retorna e a outra levanta `ConflictError` `code='duplicate_cas'`; o banco tem uma substância ativa (edge case, research R6). Seguir o padrão de sessões de `tests/integration/database/test_process_retirement_concurrency.py`.

### Implementation for User Story 1

- [X] T059 [US1] Em `src/pivma/core/sample_service.py`, implementar `validate_cas(value: str) -> str` (strip, regex `^\d{2,7}-\d{2}-\d$`, dígito verificador conforme data-model), `CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'`, `generate_code()` com `secrets.choice` (8 caracteres) e `unique_code(taken: set[str], attempts: int = 10)` (T029–T035).
- [X] T060 [US1] No mesmo arquivo, `async def active_laboratories(session, process_id) -> list[Laboratory]`: laboratórios distintos das `Assignment` `participating_laboratory` com `revoked_at`/`deleted_at` nulos e `Laboratory.deleted_at` nulo, ordenados por nome (research R4; T039–T042).
- [X] T061 [US1] No mesmo arquivo, `async def _generate_missing_codes(session, process_id, substance_ids, laboratories, actor_id) -> int`: carrega os códigos ativos do processo, cria `BlindSampleCode` para cada combinação faltante com `unique_code`, faz `flush` e devolve a quantidade criada.
- [X] T062 [US1] No mesmo arquivo, `create_substance(session, process_id, user_id, data)`: `ensure_process_mutable`; `_sample_activity(..., lock=True)`; exige `status == 'IN_PROGRESS'` (senão `ConflictError` `invalid_transition`); `validate_cas`; grava `StudySubstance`; gera códigos (T061); `AuditEvent`s `SAMPLE_SUBSTANCE_REGISTERED` e `SAMPLE_CODES_GENERATED` com `activity_run_id` da execução aberta e `context_data` só com ids/contagens; converte `IntegrityError` de `uq_study_substances_process_cas_active` em `ConflictError` `duplicate_cas` após rollback; `commit` (T036–T047, T056, T058).
- [X] T063 [US1] No mesmo arquivo, `update_substance` (mesmas guardas; substância do processo e ativa, senão `NotFoundError`; revalida CAS; não mexe nos códigos; evento `SAMPLE_SUBSTANCE_UPDATED`) e `delete_substance` (exclusão lógica da substância, dos códigos e do artefato SDS se houver; evento `SAMPLE_SUBSTANCE_REMOVED`) (T049–T053, T057).
- [X] T064 [US1] No mesmo arquivo, `list_substances(session, process_id, user_id)`: `_sample_activity` (sem lock); substâncias ativas por `created_at, id` com os códigos e nomes de laboratório carregados em uma consulta por tabela (sem N+1); devolve `activity_status` e a lista (T048, T054).
- [X] T065 [P] [US1] Em `src/pivma/schemas.py`, criar `SampleSubstanceCreate` (`chemical_name: str` 1–255 após strip, `cas_number: str` até 12, `lot: str` 1–64, `purity: str | None` até 64, `solubility: str | None`, `safe_handling_instructions: str` não vazio), `SampleSubstanceUpdate` (mesmos campos opcionais), `SampleBlindCode` (`code`, `laboratory_id`, `laboratory_name`), `SampleSds` (`filename`, `size`, `uploaded_at`), `SampleSubstance` e `SampleSubstanceList` (`activity_status`, `substances`) conforme `contracts/http-api.md`.
- [X] T066 [US1] Em `src/pivma/routers/samples.py`, rotas `GET /{id}/samples`, `POST /{id}/samples` (201), `PATCH /{id}/samples/{substance_id}`, `DELETE /{id}/samples/{substance_id}` (204), com `TrustedOrigin` nas mutações, chamando o serviço e traduzindo erros com `_http_error` (T011).

**Checkpoint**: US1 verde isoladamente — MVP de cadastro e codificação.

---

## Phase 5: User Story 2 - Concluir o cadastro e congelar os códigos (Priority: P1)

**Goal**: SDS anexada a cada substância; conclusão completa as combinações, descarta laboratórios que saíram e congela.

**Independent Test**: `poetry run pytest tests/api/routers/test_samples_router.py -k "sds or complete" tests/integration/database/test_sample_concurrency.py -q --no-cov` verde.

### Tests for User Story 2

> Escrever primeiro e confirmar que falham.

**SDS — `tests/api/routers/test_samples_router.py`**

- [X] T067 [P] [US2] `test_upload_sds_pdf_returns_substance_with_sds`: `PUT /processes/{id}/samples/{sid}/sds` com `sds.pdf` → **200**, `sds.filename == 'sds.pdf'`, `sds.size` igual ao tamanho enviado; existe `Artifact` `key='sample_sds'` com `activity_run_id` da execução e arquivo em `ATTACHMENTS_DIR` (FR-007, research R7). Usar `tmp_path` para `ATTACHMENTS_DIR` como em `tests/api/routers/test_form_attachments.py`.
- [X] T068 [P] [US2] `test_upload_non_pdf_returns_422`: `sds.docx` → **422** `extension_not_allowed`; nenhum `Artifact` criado.
- [X] T069 [P] [US2] `test_upload_empty_file_returns_400`: arquivo vazio `.pdf` → **400** `empty_file` (mesmo status de `_ATTACHMENT_ERROR_STATUS` em `routers/forms.py`).
- [X] T070 [P] [US2] `test_upload_over_size_limit_returns_413`: com `ATTACHMENT_MAX_SIZE_MB` reduzido pela sobrescrita de settings usada em `test_form_attachments.py` → **413** `file_too_large`; nenhum arquivo parcial em disco.
- [X] T071 [P] [US2] `test_replacing_sds_soft_deletes_previous_artifact_and_file`: segundo upload → o `Artifact` anterior tem `deleted_at` preenchido e seu arquivo não existe mais; a substância aponta para o novo.
- [X] T072 [P] [US2] `test_download_sds_returns_pdf`: `GET .../sds` → **200**, bytes iguais ao enviado, `content-type` `application/pdf` e `content-disposition` com o nome original.
- [X] T073 [P] [US2] `test_download_sds_without_upload_returns_404`.
- [X] T074 [P] [US2] `test_sds_upload_and_download_emit_audit_without_identity`: eventos `SAMPLE_SDS_UPLOADED` e `SAMPLE_SDS_DOWNLOADED` com `substance_id` e sem nome químico, CAS, lote ou nome do arquivo (FR-025).

**Conclusão — `tests/api/routers/test_samples_router.py`**

- [X] T075 [P] [US2] `test_complete_fills_codes_for_lab_added_later`: 2 substâncias com SDS e 2 laboratórios; `add_participating_lab`; `POST /processes/{id}/samples/complete` → **200** `{activity_status: 'COMPLETED', substance_count: 2, laboratory_count: 3, code_count: 6}` e `GET` mostra 6 códigos únicos (cenário US2-1, FR-013).
- [X] T076 [P] [US2] `test_complete_marks_activity_run_and_task_completed`: após concluir, a `ActivityInstance`, a `ActivityRun` aberta e sua `Task` estão `COMPLETED` (research R10).
- [X] T077 [P] [US2] `test_complete_discards_codes_of_lab_that_left`: laboratório com códigos cuja designação foi revogada antes da conclusão → seus códigos ficam com `deleted_at` preenchido e não aparecem no `GET` (cenário US2-2).
- [X] T078 [P] [US2] `test_complete_without_substances_returns_422`: **422** `no_substances`; atividade continua `IN_PROGRESS` (cenário US2-3).
- [X] T079 [P] [US2] `test_complete_with_substance_missing_sds_returns_422`: **422** `missing_sds` com `substance_ids` contendo exatamente as substâncias sem SDS (cenário US2-4).
- [X] T080 [P] [US2] `test_complete_without_participating_labs_returns_422`: `sample_process(lab_count=0)` com substância e SDS → **422** `no_laboratories` (cenário US2-5).
- [X] T081 [P] [US2] `test_mutations_after_completion_return_409`: parametrizado com `POST` substância, `PATCH`, `DELETE` e `PUT .../sds` → **409** `invalid_transition` (cenário US2-6, FR-009).
- [X] T082 [P] [US2] `test_complete_twice_returns_409`: segunda conclusão → **409** `invalid_transition`.
- [X] T083 [P] [US2] `test_reads_still_work_after_completion`: após concluir, `GET` lista e `GET .../sds` → **200** (FR-019).
- [X] T084 [P] [US2] `test_complete_emits_audit_with_counts_only`: `SAMPLE_DEFINITION_COMPLETED` com `substance_count`, `laboratory_count`, `code_count`, `discarded_code_count`, e `SAMPLE_CODES_GENERATED` para as combinações novas, sem identidade química nem códigos (FR-025).

**Concorrência — `tests/integration/database/test_sample_concurrency.py`**

- [X] T085 [P] [US2] `test_create_concurrent_with_complete_never_adds_codes_after_freeze`: `create_substance` e `complete_sample_definition` em sessões paralelas; ao final, ou a substância entrou antes da conclusão (e tem códigos para todos os laboratórios) ou o cadastro falhou com `ConflictError` `invalid_transition`; nunca há substância ativa criada depois do `COMPLETED` (research R6).
- [X] T086 [P] [US2] `test_concurrent_completions_generate_codes_once`: duas conclusões paralelas → uma conclui, a outra recebe `ConflictError`; não há dois códigos ativos para a mesma combinação.

### Implementation for User Story 2

- [X] T087 [US2] Em `src/pivma/core/sample_service.py`, `upload_sds(session, settings, process_id, substance_id, user_id, upload)`: guardas de mutação (processo `OPEN`, atividade `IN_PROGRESS` com lock, substância do processo); `validate_extension(upload.filename, {'pdf'})`; cria `Artifact` (`key='sample_sds'`, `status='SUBMITTED'`, `metadata_payload` com `original_filename`, `extension`, `substance_id`); grava com `store_upload` em `attachment_relpath`; limite `settings.ATTACHMENT_MAX_SIZE_MB`; exclui logicamente o artefato anterior e remove o arquivo após o commit com `remove_file_best_effort`; evento `SAMPLE_SDS_UPLOADED` (T067–T071, T074).
- [X] T088 [US2] No mesmo arquivo, `get_sds(session, settings, process_id, substance_id, user_id) -> (Artifact, Path)` com `_sample_activity` (sem exigir `IN_PROGRESS`), `NotFoundError` sem SDS ou sem arquivo em disco, e evento `SAMPLE_SDS_DOWNLOADED` com commit (T072–T074).
- [X] T089 [US2] No mesmo arquivo, `complete_sample_definition(session, process_id, user_id)`: guardas com lock; validações na ordem `no_substances` → `missing_sds` (com `substance_ids`) → `no_laboratories` como `ValidationError` com `code`; `_generate_missing_codes`; exclusão lógica dos códigos de laboratórios fora de `active_laboratories`; `_complete_activity_run` + `_advance_dependent_activities` sobre a execução aberta; eventos `SAMPLE_CODES_GENERATED` (se houver novos) e `SAMPLE_DEFINITION_COMPLETED`; commit; devolve as contagens (T075–T086).
- [X] T090 [P] [US2] Em `src/pivma/schemas.py`, `SampleCompletionResponse` (`activity_status`, `substance_count`, `laboratory_count`, `code_count`).
- [X] T091 [US2] Em `src/pivma/routers/samples.py`, rotas `PUT /{id}/samples/{substance_id}/sds` (multipart `file`, `SettingsDependency`, `TrustedOrigin`), `GET /{id}/samples/{substance_id}/sds` (`FileResponse` com `media_type='application/pdf'` e `filename` original) e `POST /{id}/samples/complete`.

**Checkpoint**: US1 + US2 verdes; conjunto congelado após a conclusão.

---

## Phase 6: User Story 5 - Nenhum outro perfil vê o conteúdo das amostras (Priority: P1)

**Goal**: toda rota de amostras responde só ao Grupo de Seleção do processo; admin e BraCVAM veem só a atividade e seu status.

**Independent Test**: `poetry run pytest tests/api/routers/test_samples_access.py -q --no-cov` verde.

### Tests for User Story 5

> Com US1/US2 prontas, a maior parte deve passar de imediato pelo guarda de T010; cada teste que falhar vira correção em T105. Parametrizar cada teste pelas rotas de amostras existentes até aqui (lista, cadastro, alteração, remoção, upload e download da SDS, conclusão); etiquetas e frasco entram na parametrização em T108 e T120.

- [X] T092 [P] [US5] Em `tests/api/routers/test_samples_access.py`, `test_participating_lab_gets_404_on_every_sample_route`: usuário de laboratório participante do processo → **404** em todas as rotas (cenário US5-1, FR-024).
- [X] T093 [P] [US5] No mesmo arquivo, `test_lead_lab_gets_404_on_every_sample_route` (FR-024).
- [X] T094 [P] [US5] No mesmo arquivo, `test_group_manager_gets_404_on_every_sample_route` (cenário US5-2, FR-024).
- [X] T095 [P] [US5] No mesmo arquivo, `test_admin_gets_403_on_every_sample_route`: fixture `ai_eval_admin` → **403** (cenário US5-2, FR-023, research R3).
- [X] T096 [P] [US5] No mesmo arquivo, `test_bracvam_gets_403_on_every_sample_route`: fixture `bracvam_user` → **403**.
- [X] T097 [P] [US5] No mesmo arquivo, `test_unauthenticated_gets_401_on_every_sample_route`.
- [X] T098 [P] [US5] No mesmo arquivo, `test_sample_group_of_other_process_gets_404`: Grupo de Seleção do processo A acessando rotas do processo B → **404** (cenário US5-4).
- [X] T099 [P] [US5] No mesmo arquivo, `test_sample_group_member_with_conflict_gets_403`: `ConflictInterestDeclarationFactory(has_conflict=True)` na designação do Grupo de Seleção → **403** em leitura e mutação (research R3, consequência aceita).
- [X] T100 [P] [US5] No mesmo arquivo, `test_sds_download_denied_to_everyone_but_sample_group`: download da SDS → **404** para laboratório e Grupo Gestor, **403** para admin e BraCVAM, **200** para o Grupo de Seleção (cenário US5-3).
- [X] T101 [P] [US5] No mesmo arquivo, `test_admin_and_bracvam_see_sample_task_status_only`: `GET /tasks?process_id=` como admin e como BraCVAM traz a tarefa "Definição e Preparação das Amostras" com seu status; `json.dumps` da resposta não contém nome químico, CAS nem códigos (cenário US5-5, FR-023).
- [X] T102 [P] [US5] No mesmo arquivo, `test_participating_lab_does_not_see_sample_task`: `GET /tasks?process_id=` do laboratório não traz a tarefa de amostras.
- [X] T103 [P] [US5] No mesmo arquivo, `test_timeline_sample_events_carry_no_identity`: após cadastro, SDS e conclusão, `GET /processes/{id}/timeline` como admin traz os eventos `SAMPLE_*` e `json.dumps` da resposta não contém nome químico, CAS, lote nem códigos (FR-025, research R9).
- [X] T104 [P] [US5] No mesmo arquivo, `test_timeline_hides_sample_events_from_participating_lab`: a timeline do laboratório participante não traz eventos `SAMPLE_*` (a atividade não concede ver a ele).

### Implementation for User Story 5

- [X] T105 [US5] Para cada teste de T092–T104 que falhar, corrigir a rota ou o serviço para passar por `_sample_activity` antes de qualquer consulta ao conteúdo (em `src/pivma/core/sample_service.py` e `src/pivma/routers/samples.py`), sem criar regra de autorização nova. Registrar em Notes o que foi corrigido (ou "nenhuma correção necessária").

**Checkpoint**: matriz de acesso verde para todas as rotas existentes.

---

## Phase 7: User Story 3 - Emitir os dados das etiquetas (Priority: P2)

**Goal**: dados de etiqueta com QR code em SVG para cada frasco.

**Independent Test**: `poetry run pytest tests/unit/core/test_sample_service.py -k qr tests/api/routers/test_samples_router.py -k label -q --no-cov` verde.

### Tests for User Story 3

> Escrever primeiro e confirmar que falham.

- [X] T106 [P] [US3] Em `tests/unit/core/test_sample_service.py`, `test_qr_url_uses_configured_base_url`: `vial_qr_url(settings, process_id, code)` com `SAMPLE_QR_BASE_URL='https://front.exemplo'` → `'https://front.exemplo/amostras/{process_id}/frascos/{code}'` (research R8).
- [X] T107 [P] [US3] No mesmo arquivo, `test_qr_url_falls_back_to_first_allowed_origin`: sem `SAMPLE_QR_BASE_URL`, usa `AUTH_ALLOWED_ORIGINS[0]`; barra final da base não duplica.
- [X] T108 [P] [US3] Em `tests/api/routers/test_samples_router.py`, `test_labels_return_one_per_vial`: 4 substâncias × 3 laboratórios → `GET /processes/{id}/samples/labels` → **200** com 12 itens, cada um com `code`, `study_code` (= `ProcessInstance.code`), `laboratory_id`, `laboratory_name`, `lot`, `qr_url`, `qr_svg`, ordenados por `laboratory_name` e `code` (cenário US3-1, FR-015). Acrescentar a rota de etiquetas à parametrização de `tests/api/routers/test_samples_access.py`.
- [X] T109 [P] [US3] No mesmo arquivo, `test_label_qr_svg_is_valid_svg_data_uri`: `qr_svg` começa com `data:image/svg+xml` e decodifica para um documento que contém `<svg` (FR-018).
- [X] T110 [P] [US3] No mesmo arquivo, `test_label_qr_contains_only_vial_url`: `qr_url` contém apenas o id do processo e o código; `json.dumps` de `qr_url` e o SVG decodificado não contêm nome químico, CAS, lote nem `substance_id` (cenário US3-2, FR-016, FR-017, SC-004).
- [X] T111 [P] [US3] No mesmo arquivo, `test_labels_available_after_completion`: após concluir, `GET .../labels` → **200** com os mesmos 12 itens (FR-019).
- [X] T112 [P] [US3] No mesmo arquivo, `test_labels_empty_without_codes`: sem substâncias → **200** `[]`.

### Implementation for User Story 3

- [X] T113 [US3] Em `src/pivma/core/sample_service.py`, `vial_qr_url(settings, process_id, code)` e `list_labels(session, settings, process_id, user_id)`: `_sample_activity`; carrega códigos ativos com substância e laboratório; gera `qr_svg` com `segno.make(url, error='m').svg_data_uri()`; ordena por nome do laboratório e código (T106–T112).
- [X] T114 [P] [US3] Em `src/pivma/schemas.py`, `SampleLabel` conforme o contrato.
- [X] T115 [US3] Em `src/pivma/routers/samples.py`, rota `GET /{id}/samples/labels` (declarada antes de `/{id}/samples/{substance_id}` para não colidir com o parâmetro de caminho) com `response_model=list[SampleLabel]` e `SettingsDependency`.

**Checkpoint**: etiquetas emitidas com QR legível.

---

## Phase 8: User Story 4 - Consultar o frasco pelo QR code sem quebrar o cegamento (Priority: P2)

**Goal**: rota autenticada de visão cega do frasco, só para o Grupo de Seleção nesta feature.

**Independent Test**: `poetry run pytest tests/api/routers/test_samples_router.py -k vial tests/api/routers/test_samples_access.py -q --no-cov` verde.

### Tests for User Story 4

> Escrever primeiro e confirmar que falham.

- [X] T116 [P] [US4] Em `tests/api/routers/test_samples_router.py`, `test_vial_returns_blind_view_only`: `GET /processes/{id}/samples/vials/{code}` como Grupo de Seleção → **200** com exatamente as chaves `code`, `lot`, `safe_handling_instructions`; `json.dumps` da resposta não contém nome químico nem CAS (cenário US4-2, FR-021, SC-004).
- [X] T117 [P] [US4] No mesmo arquivo, `test_vial_unknown_code_returns_404`: código inexistente no processo → **404**.
- [X] T118 [P] [US4] No mesmo arquivo, `test_vial_code_of_other_process_returns_404`: código válido do processo B pela rota do processo A → **404**.
- [X] T119 [P] [US4] No mesmo arquivo, `test_vial_code_of_removed_substance_returns_404`.
- [X] T120 [P] [US4] Em `tests/api/routers/test_samples_access.py`, acrescentar a rota do frasco à parametrização de T092–T099, cobrindo: sem login → **401** (cenário US4-1); laboratório participante e Grupo Gestor → **404**; admin e BraCVAM → **403** (cenário US4-3).

### Implementation for User Story 4

- [X] T121 [US4] Em `src/pivma/core/sample_service.py`, `get_blind_vial(session, process_id, code, user_id)`: `_sample_activity`; busca o código ativo do processo cuja substância está ativa (`NotFoundError` senão); devolve só `code`, `lot`, `safe_handling_instructions` (T116–T119).
- [X] T122 [P] [US4] Em `src/pivma/schemas.py`, `BlindVial` com `model_config = ConfigDict(extra='forbid')` e só os três campos do contrato.
- [X] T123 [US4] Em `src/pivma/routers/samples.py`, rota `GET /{id}/samples/vials/{code}` (declarada antes de `/{id}/samples/{substance_id}`).

**Checkpoint**: todas as histórias verdes.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T124 Em `tests/integration/journeys/test_sample_definition_journey.py`, `test_blind_sample_journey_four_substances_three_labs`: jornada por HTTP num template real (`pre_validated_method`): submissão, triagem aprovada, Grupo Gestor, Grupo de Seleção e 3 laboratórios designados, 4 substâncias com SDS, conclusão → 12 códigos únicos, 12 etiquetas, visão cega sem identidade, laboratório participante com **404** (SC-001, SC-003, SC-004, SC-005, SC-006).
- [X] T125 [P] Em `tests/unit/core/test_sample_service.py`, `test_thousand_codes_are_unique_and_unpatterned`: 1.000 códigos de `unique_code` acumulando `taken` são únicos, e nenhum prefixo ou sufixo de 3 caracteres se repete em mais de 1% dos códigos (SC-002).
- [X] T126 Rodar `poetry run pytest -q` (com cobertura) e `poetry run ruff check . && poetry run ruff format --check .`; comparar com a linha de base de T001 e registrar o resultado em Notes. Cobertura de `src/pivma/core/sample_service.py` e `src/pivma/routers/samples.py` sem ramos críticos (acesso, conclusão, CAS) descobertos.
- [X] T127 Atualizar `README.md`: módulo de amostras, rotas `/processes/{id}/samples/...`, Fase 2 em todos os templates e versões novas, dependência `segno`, setting `SAMPLE_QR_BASE_URL`, regra de acesso (só o Grupo de Seleção vê o conteúdo) e rota do frontend combinada para o QR (AGENTS.md, "Documentação do repositório").
- [ ] T128 Executar o roteiro manual de `specs/031-blind-sample-coding/quickstart.md` contra a API local e registrar em Notes os passos verificados e qualquer divergência.
- [ ] T129 [P] Atualizar a issue #24 no GitHub com o link para `specs/031-blind-sample-coding/` e a nota de que o acesso dos laboratórios aos próprios códigos ficou para a #28 (somente após confirmação do usuário, por ser ação externa).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → histórias.
- **US6 (Phase 3)** depende só da Foundational (mexe nos YAMLs e no motor já existente). As demais histórias **não** dependem de US6 nos testes, porque usam o template mínimo de T005; T054 e T017–T021 usam templates reais.
- **US1 (Phase 4)** depende da Foundational.
- **US2 (Phase 5)** depende de US1 (substâncias e geração de códigos).
- **US5 (Phase 6)** depende de US1 e US2 (parametriza as rotas delas).
- **US3 (Phase 7)** depende de US1 (códigos); estende a parametrização de US5.
- **US4 (Phase 8)** depende de US1; estende a parametrização de US5.
- **Polish (Phase 9)** depende de todas.

### Within Each User Story

- Testes escritos e falhando antes da implementação.
- Serviço antes do roteador; schemas em paralelo com o serviço.

### Parallel Opportunities

- T005, T007, T008, T009 em paralelo depois de T003/T004.
- US6 (T012–T026) pode correr em paralelo com US1 inteira: arquivos diferentes (YAMLs e testes de bootstrap vs. serviço e roteador de amostras).
- Dentro de cada história, todos os testes marcados [P] podem ser escritos em paralelo; T022–T026 (um YAML cada) em paralelo.
- US3 e US4 podem correr em paralelo após US1 (tocam funções diferentes de `sample_service.py`, mas o mesmo arquivo — coordenar a edição ou fazer em sequência).

## Parallel Example: User Story 1

```text
# Testes unitários e de API em paralelo:
T029–T035  tests/unit/core/test_sample_service.py
T036–T057  tests/api/routers/test_samples_router.py
T058       tests/integration/database/test_sample_concurrency.py

# Implementação:
T065 (schemas.py) em paralelo com T059–T064 (sample_service.py); T066 por último.
```

## Parallel Example: User Story 6

```text
T022 04_validated_method_dossier.yaml
T023 01_pre_validated_method.yaml
T024 02_scope_extension.yaml
T025 03_me_too_validation.yaml
T026 05_proof_of_concept.yaml
```

## Implementation Strategy

### MVP First

1. Phase 1 e Phase 2.
2. Phase 4 (US1): cadastro e códigos cegos com o template mínimo.
3. Validar: 4 × 3 → 12 códigos únicos; matriz básica de acesso já vale pelo guarda de T010.

### Incremental Delivery

1. US6 (templates) → processos novos chegam à atividade.
2. US1 → cadastro e códigos (MVP).
3. US2 → SDS e congelamento.
4. US5 → matriz de acesso completa.
5. US3 → etiquetas; US4 → visão cega do frasco.
6. Jornada, README, quickstart.

Sugestão de PRs (como na Spec 030): PR 1 = Phases 1–4 + US6; PR 2 = US2 + US5; PR 3 = US3 + US4 + Polish.

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- Commit após cada tarefa ou grupo lógico; mensagens em português no padrão `feat(samples): ...`/`test(samples): ...`.
- **Linha de base (T001)**: a suíte rodou com os YAMLs já sendo alterados, então o resultado ficou contaminado: 898 passaram, 1 pulado, 1 falhou (`test_pre_validated_method_triage`, efeito desta feature, corrigido em T028). Ruff na `develop`: sem erros.
- **T002**: `poetry add segno` (1.6.6) sincronizou o ambiente com o `poetry.lock` e trocou ruff 0.16.7→0.16.2 e typos 1.50.2→1.49.0 no venv local. Com o 0.16.2, `ruff format --check` acusa 4 arquivos que esta feature não toca (`specs/028-.../data-model.md`, `src/pivma/core/invite_service.py`, `tests/api/routers/test_tasks_router.py`, `tests/api/routers/test_user_router.py`); ficaram como estão.
- **Contrato**: `empty_file` responde **400** (mapa de `_ATTACHMENT_ERROR_STATUS` já existente), não 422; contrato e T069 corrigidos.
- **Alfabeto do código**: a versão inicial (`…JKLMN…`) continha `L`; T033 detectou. Alfabeto final com 31 símbolos (`23456789ABCDEFGHJKMNPQRSTUVWXYZ`); research e data-model atualizados.
- **T028 — testes existentes ajustados** pela Fase 2 nos templates: `tests/api/routers/test_activity_type_extension.py` (tipos e versão 5), `tests/integration/journeys/conftest.py` (`process_tasks` indexado por `activity_key`, porque o proponente passa a ter várias tarefas) e `tests/integration/journeys/test_pre_validated_method_triage.py`, `tests/api/routers/test_timeline_router.py` (dois `ACTIVITY_UNBLOCKED` da Fase 2 após a aprovação).
- **T105**: nenhuma correção necessária; todas as rotas já passavam pelo guarda de edição.
- **Testes de desbloqueio (T017–T021)**: aprovam a triagem e designam pelo motor (`participant_service.create_assignment`), não pelo HTTP, para não depender dos payloads de submissão de cada template; a jornada T124 cobre o caminho HTTP completo.
- **T126**: suíte final com `--cov`: **1017 passaram, 1 pulado, 0 falhas**; `ruff check .` limpo. Cobertura total 92%; `sample_service.py` 96% e `routers/samples.py` 98%. Depois disso entraram 3 testes para ramos descobertos (processo sem a atividade, `PATCH` com campo obrigatório nulo, remoção com SDS). Fica sem cobertura só o `IntegrityError` de CAS duplicado, que é defensivo: a trava na atividade já serializa os cadastros.
- **Regressão intermitente corrigida**: `tests/api/routers/test_process_retirement.py::test_admin_deletes_others_process_and_cancels_pending_children` pegava "a primeira atividade" só por `order_index`, e com a Fase 2 há duas com índice 1; o teste agora filtra pela primeira fase.
- **T128**: não executada. Exigiria `alembic upgrade head` no banco local de desenvolvimento; o mesmo roteiro está coberto pela jornada automatizada T124.
- **T129**: pendente de confirmação do usuário (ação externa no GitHub).
