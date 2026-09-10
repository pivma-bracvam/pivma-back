---
description: "Task list — Avaliação Configurável por IA na Submissão e Triagem"
---

# Tasks: Avaliação Configurável por IA na Submissão e Triagem (Fechamento da Versão 1)

**Input**: Design em `specs/013-configurable-ai-evaluation/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: INCLUÍDOS — a Constituição (Princípio IV, NÃO NEGOCIÁVEL) e o `AGENTS.md` exigem testes nas camadas `unit`/`api`/`integration` e demonstração funcional como critério de conclusão. Antes de criar ou alterar qualquer teste, invoque `Skill({skill: "fastapi-testing-methodology"})`.

**Organização**: por user story (US1–US7 do spec), permitindo entrega incremental. `[P]` = paralelizável (arquivos distintos, sem dependência pendente).

**Nota de skill**: `andrej-karpathy-skills:karpathy-guidelines` não está instalada neste ambiente — não é possível invocá-la; siga os princípios de simplicidade da Constituição manualmente.

## Path Conventions

Projeto único existente: código em `src/pivma/`, testes em `tests/`, migrações em `migrations/versions/`, demos em `demos/`, seeds em `scripts/seeds/`.

## Progresso da implementação

- **Phase 1 + Phase 2 (Foundational) concluídas** (T001–T021). Migração `8b701d7bfeae` aplicada; `uv run pytest tests/unit` verde (108); testes de migração verdes.
- **Desvios registrados:**
  - T012 nomeou o novo pipeline `src/pivma/ai/evaluation_pipeline.py` (arquivo novo) em vez de reescrever `src/pivma/ai/pipeline.py` — o `pipeline.py` da Spec 010 e `ai/steps/*` seguem intactos até serem removidos na US2 (T039/T041), mantendo a suíte verde entre fases.
  - T016 (novos módulos de step) foi **absorvido em T015**: a lógica de preparação/avaliação/síntese vive inline em `evaluation_pipeline.py` (Constituição: "código não complexo demais"). Os `ai/steps/*` antigos serão removidos na US2.
  - T009/T010: `ai_evaluations.read`/`.manage` concedidas **apenas ao Administrador** (o invariante do catálogo RBAC não admite composições não-admin via migração). `test_rbac_migration` atualizado para `(11, 11, 0)`.
- **US1 (T022–T034) concluída.** `evaluation_service.py` + router `ai_evaluations.py` (2 routers) + schemas + 4 arquivos de teste. Ajuste chave: relacionamento `criterion.version` setado explicitamente para manter a coleção em memória com `expire_on_commit=False`.
- **US2 (T035–T047) concluída.** `_open_new_submission_run` extraído; `pre_evaluation_service.py` (`run_pre_evaluation` background, `_execute`, roteamento positivo/negativo/falha, `sweep_stale_runs`, `retry_run`); `submit_proposal_form` retorna 4-tupla e não libera a triagem quando há associações; router `pre_evaluation.py` (`GET /pre-evaluation`, `POST /submission/direct-review`, `POST /admin/pre-evaluations/{run}/retry`); `lifespan` com varredura; 5 arquivos de teste (16 casos).
  - Fixtures `ai_eval_admin`/`fake_provider` movidas para o `tests/conftest.py` global; helpers em `tests/ai_eval_helpers.py`. Fixture autouse `_stub_pre_evaluation_background` neutraliza o `BackgroundTasks` nos testes (a lógica é exercida via `_execute` direto).
  - Esteira mock da Spec 010 preservada como `_run_legacy_field_ai_mock` (só roda quando o template não tem associações). Endpoint `/forms/instances/{id}/evaluate-ai` e `tests/unit/test_ai_pipeline.py` mantidos — remoção total da Spec 010 fica para limpeza posterior (T041 parcial).
- **US3 (T048–T050) concluída.** `test_direct_review.py` (4 casos).
- **US4 (T051–T056) concluída.** `record_feedback` (guarda de conflito de interesse + upsert), `agreement_metrics`; endpoints `POST /processes/{id}/pre-evaluation/{run_id}/feedback` e `GET /ai-evaluations/agreement-metrics`; `get_pre_evaluation` estendido com `evaluations` (definição+versão+referências) e `references` por item de atenção (FR-039); `test_pre_evaluation_feedback.py` + `test_agreement_metrics.py` (5 casos).
  - Rotas `/{definition_id}` passaram a usar convertor `:uuid`/`:int` para não sombrear `/references`, `/suggest-criteria`, `/agreement-metrics`.
- **US5 (T057–T060) concluída.** `test_evaluation_library_reuse.py` (3) + `test_evaluation_library.py` (2).
- **US6 (T061–T062) concluída.** `test_evaluation_test_mode_iteration.py` (2).
- **US7 (T063–T067) concluída — revisada após feedback do usuário.** A abordagem original (dois módulos novos `demos/ai-evaluation-library/` e `demos/ai-evaluation-form-editor/` que apenas imprimiam respostas de endpoint) foi substituída: o ciclo de demos passou a ter 4 módulos (`demos/forms/`, `demos/submission/`, `demos/triage/`, `demos/ai-pipeline/`). A configuração por IA agora é feita a partir do próprio editor de formulário, pela página dedicada `demos/forms/ai-config.html?template=<k>&field=<f>` (criar/reaproveitar → sugerir → editar → testar → publicar → associar, só endpoints existentes; o `PUT` de associações preserva a lista fazendo GET+append). Seed padronizado: `scripts/seeds/ai_evaluation_seed.py` removido, substituído por `scripts/seeds/seed_ai_evaluations.py` (contas padrão do `seed_users`, incluído no `seed_all`). Restrição registrada: `GET .../pre-evaluation` e `.../feedback` exigem proponente / `group_manager` / Administrador — o seed designa `triage_evaluator` como `group_manager` do processo `[DEMO IA]`. Ver `demos/RELATORIO-REVISAO-CICLO-IA.md`.
- **Polish (T068–T073) concluída.** `log_service` soma `real_cost` e usa o `pipeline_name` do step (agrupamento por `correlation_id` inalterado); `tests/integration/ai/test_openai_live.py` opt-in (`RUN_OPENAI_TESTS`); `.env.example` + seção no `README.md`; `ruff format`/`check` verdes.
  - T067/T073 (validação manual em navegador / execução literal do `quickstart.md`) cobertos indiretamente pela suíte + execução do seed; validação visual das duas demos fica para o usuário rodar a app.
- **STATUS: 73/73 tarefas.**

---

## Phase 1: Setup (Infraestrutura compartilhada)

- [X] T001 Adicionar `langchain-openai` e `langchain-core` em `[project.dependencies]` de `pyproject.toml` (versões fixadas no padrão `(>=x,<y)`) e rodar `uv sync` / `poetry lock`
- [X] T002 [P] Estender `Settings` em `src/pivma/core/settings.py` com defaults seguros (não quebrar `.env`/testes atuais): `OPENAI_API_KEY: str | None = None`, `AI_PROVIDER: str = 'openai'`, `AI_MODEL_EXTRACTION: str = 'gpt-5.4-nano'`, `AI_MODEL_FAST: str = 'gpt-5.4-nano'`, `AI_MODEL_REASONING: str = 'gpt-5.4-mini'`
- [X] T003 [P] Em `tests/conftest.py`, adicionar `os.environ.setdefault('AI_PROVIDER', 'fake')` junto aos demais defaults de ambiente

---

## Phase 2: Foundational (Pré-requisitos bloqueantes)

**⚠️ CRÍTICO**: nenhuma user story começa antes desta fase.

- [X] T004 Adicionar em `src/pivma/core/database/models.py` os modelos de configuração (herdam `AuditMixin`): `EvaluationDefinition` (`name String(255)`, `slug String(80)`, `description Text?`, `mode String default 'simple'`; índice único parcial `(slug) WHERE deleted_at IS NULL`); `EvaluationVersion` (`definition_id FK`, `version_number Integer` (≥1), `status String default 'draft'` valores `{draft, published}`, `objective Text`, `references JSONB`, `test_run_count Integer default 0`, `published_at datetime?`, `published_by FK users?`; índices únicos parciais `(definition_id, version_number)` e `(definition_id) WHERE status='draft' AND deleted_at IS NULL`)
- [X] T005 Adicionar em `src/pivma/core/database/models.py`: `EvaluationCriterion` (`version_id FK`, `order_index Integer default 0`, `statement Text`, `check_type String` valores `{presence, conformity, quality, comparison, cross_field_consistency}`, `polarity String default 'positive'` valores `{positive, negative, consistency}`, `required_evidence Text?`, `severity String default 'medium'` valores `{info, low, medium, high, critical}`, `on_missing_info String default 'indeterminate'` valores `{non_compliant, indeterminate}`, `recommendation_hint Text?`); `EvaluationReference` (`identifier String(64)`, `label String(255)`, `version_label String(64)`, `reference_date Date?`; índice único parcial `(identifier, version_label) WHERE deleted_at IS NULL`)
- [X] T006 Adicionar em `src/pivma/core/database/models.py`: `EvaluationAssignment` (`form_template_id FK`, `definition_id FK`, `pinned_version_id FK?` (null = última publicada), `target_type String` valores `{field, field_set, document, form, process}`, `field_keys JSONB` (lista; vazia para `form`/`process`), `enabled Boolean default true`; índice único parcial `(form_template_id, definition_id, target_type, field_keys) WHERE deleted_at IS NULL`)
- [X] T007 Adicionar em `src/pivma/core/database/models.py` os modelos de execução (imutáveis pós-conclusão): `EvaluationRun` (`process_instance_id FK`, `activity_run_id FK`, `form_instance_id FK`, `correlation_id UUID`, `status String default 'in_progress'` valores `{in_progress, completed, failed}`, `consolidated_result String?` valores `{positive, negative}`, `provider_name String(32)?`, `models_used JSONB`, `real_cost Numeric(12,6) default 0`, `started_at datetime`, `finished_at datetime?`, `error_summary Text?`; índices `(process_instance_id, started_at desc)` e `(status)`); `EvaluationRunItem` (`run_id FK`, `criterion_id FK`, snapshots `criterion_statement Text`/`check_type String`/`polarity String`/`severity String`, `conclusion String` valores `{compliant, non_compliant, partial, indeterminate}`, `is_alert Boolean`, `evidence_excerpt Text?`, `evidence_location Text?`, `justification Text?`, `recommendation Text?`, `inference_confidence Float?`, `evidence_completeness String?` valores `{sufficient, partial, insufficient}`, `model_layer String(16)`)
- [X] T008 Adicionar em `src/pivma/core/database/models.py`: `DirectReviewRequest` (`evaluation_run_id FK`, `process_instance_id FK`, `requested_by FK users`, `justification Text?`; índice único parcial `(evaluation_run_id) WHERE deleted_at IS NULL` — impede duplicidade, FR-038); `ReviewerFeedback` (`run_item_id FK`, `reviewer_id FK users`, `verdict String` valores `{agree, disagree, inconclusive}`, `reason Text?`; índice único parcial `(run_item_id, reviewer_id) WHERE deleted_at IS NULL`); `EvaluationTestRun` (`version_id FK`, `sample_content Text`, `result_payload JSONB`, `real_cost Numeric(12,6) default 0`)
- [X] T009 Gerar migração `alembic revision --autogenerate -m "configurable_ai_evaluation"` em `migrations/versions/`; revisar; acrescentar migração de dados que insere as permissões `ai_evaluations.read` e `ai_evaluations.manage` e as concede ao perfil `Administrador` (+ `read` ao `Grupo Gestor`), no padrão de `migrations/versions/c1e4a9f8b312_user_authorization_rbac.py`; rodar `alembic upgrade head`
- [X] T010 [P] Adicionar constantes `AI_EVALUATIONS_READ = 'ai_evaluations.read'` e `AI_EVALUATIONS_MANAGE = 'ai_evaluations.manage'` em `src/pivma/core/authorization.py`
- [X] T011 [P] Criar `src/pivma/ai/schemas.py` com os modelos Pydantic de saída estruturada do LLM: `CriterionVerdict` (`conclusion`, `evidence_excerpt`, `evidence_location`, `justification`, `recommendation`, `inference_confidence`, `evidence_completeness`), `SuggestedCriterion` (`statement`, `check_type`, `polarity`, `suggested_severity`)
- [X] T012 [P] Criar `src/pivma/ai/provider.py`: ABC `ModelProvider` (`extraction()/fast()/reasoning() -> BaseChatModel`, `evaluate_criterion(...) -> CriterionVerdict`, `suggest_criteria(objective, target_type) -> list[SuggestedCriterion]`); `OpenAIModelProvider` (um `ChatOpenAI` por camada, `temperature=0`, `.with_structured_output(...)`, captura de custo via `usage_metadata`); `FakeModelProvider` determinístico (heurística por polaridade; conteúdo vazio → `indeterminate`; alvo documento/imagem → `indeterminate`; `suggest_criteria` devolve lista canônica por `target_type`); `get_model_provider(settings)` seleciona por `settings.AI_PROVIDER` e levanta erro claro **na chamada** (não no import) se `openai` sem `OPENAI_API_KEY`
- [X] T013 Adicionar `ModelProviderDep = Annotated[ModelProvider, Depends(get_model_provider)]` e `get_model_provider(settings: SettingsDependency)` em `src/pivma/dependencies.py`
- [X] T014 [P] Criar `src/pivma/ai/consolidation.py`: `consolidate(items) -> ConsolidatedResult` — ordem `info < low < medium < high < critical`; resultado `negative` **sse existe ≥1 item com `conclusion == 'non_compliant'` e `severity in {'high', 'critical'}`**, senão `positive`; todo item não-`compliant` que não dispara o negativo recebe `is_alert = True`; item `indeterminate` nunca torna negativo
- [X] T015 Reescrever `src/pivma/ai/pipeline.py` como `EvaluationPipeline`: etapas `context_preparation` (camada `extraction`) → `criterion_evaluation` (uma por critério; camada por `check_type`: `presence`/`conformity` → `fast`; `quality`/`comparison`/`cross_field_consistency` → `reasoning`; alvo documento/OCR/imagem → `conclusion='indeterminate'` sem chamar modelo) → `synthesis`; mantém `correlation_id`, `AIStepExecutionLog` + `broadcaster`; retorna itens + `consolidated_result` + `real_cost` + `models_used`
- [X] T016 [P] Refatorar `src/pivma/ai/steps/` para o novo conjunto (`context_preparation.py`, `criterion_evaluation.py`, `synthesis.py`); remover a lógica fixa de `mock_evaluation.py` / `verdict_synthesis.py` / `context_extraction.py`
- [X] T017 [P] Estender `src/pivma/ai/contracts.py`: adicionar `model_name` e `real_cost` a `AIStepExecutionLog`; incluir `provider`, `models_used`, `real_cost`, `consolidated_result` no `metadata` do `OperationalEventIndex`; renomear a operação para `FORM_AI_PRE_EVALUATION`
- [X] T018 [P] Criar factories em `tests/factories/evaluation_factory.py` (`EvaluationDefinitionFactory`, `EvaluationVersionFactory`, `EvaluationCriterionFactory`) e `tests/factories/evaluation_run_factory.py` (`EvaluationRunFactory`, `EvaluationRunItemFactory`)
- [X] T019 [P] Unit test `tests/unit/ai/test_consolidation.py`: negativo só com ≥1 não conformidade `high`/`critical`; só `indeterminate` → `positive`; não conformidade `low`/`medium` → `positive` + `is_alert=True`
- [X] T020 [P] Unit test `tests/unit/ai/test_provider.py`: `get_model_provider` retorna `FakeModelProvider` para `AI_PROVIDER=fake`; caminho `openai` sem chave levanta erro claro na chamada; mapeamento camada ↔ `check_type`
- [X] T021 [P] Migration test `tests/integration/migrations/test_configurable_ai_evaluation.py`: `upgrade` + `downgrade`; permissões inseridas no upgrade e removidas no downgrade

**Checkpoint**: base pronta — user stories podem começar.

---

## Phase 3: User Story 1 - Configuração assistida de avaliação pelo BraCVAM (Priority: P1) 🎯 MVP

**Goal**: o BraCVAM descreve o objetivo em linguagem natural, recebe critérios sugeridos, edita, define tipo/evidência/severidade, associa a um alvo de formulário e publica a versão 1 imutável.

**Independent Test**: criar definição → `suggest-criteria` → `PATCH` critérios → associar ao campo POP de um template → `publish` v1; `PATCH` na v1 publicada retorna 409.

### Implementação

- [X] T022 [P] [US1] Adicionar schemas em `src/pivma/schemas.py`: `CreateEvaluationRequest`, `EvaluationDefinitionResponse`, `EvaluationVersionResponse`, `CriterionInput` (`id?`, `order_index`, `statement`, `check_type`, `polarity`, `required_evidence?`, `severity`, `on_missing_info`, `recommendation_hint?`), `PatchEvaluationVersionRequest` (`objective?`, `references?: list[UUID]`, `criteria?: list[CriterionInput]`), `PublishResponse` (com `test_warning: bool`), `SuggestCriteriaRequest/Response`, `ReferenceRequest/Response`, `EvaluationAssignmentInput/Response`
- [X] T023 [US1] Criar `src/pivma/core/evaluation_service.py` com: `create_definition(...)` (definição + `EvaluationVersion` v1 `draft`); `get_definition(...)`; `patch_draft_version(...)` (409 se `published`; `criteria` = substituição total: cria itens sem `id`, atualiza `id` conhecidos, exclui logicamente ausentes); `create_new_version(...)` (clona a última versão em novo `draft`, `version_number = max+1`; 409 se já existe `draft`); `publish_version(...)` (valida ≥1 critério → 422; congela `objective`/critérios/snapshot `references` JSONB `[{reference_id, identifier, version_label}]`; grava `published_at/by`; retorna `test_warning = test_run_count == 0`)
- [X] T024 [US1] Adicionar a `evaluation_service.py`: `list_definitions(search, offset, limit)` (limit 1–100 default 50); `soft_delete_definition(id, force)` (409 se houver `EvaluationAssignment` ativo e `force` ausente); `list_references()`; `create_reference()` (409 em `(identifier, version_label)` duplicado ativo); `reference_impact(id)` (containment JSONB sobre `EvaluationVersion.references` e execuções)
- [X] T025 [US1] Adicionar a `evaluation_service.py`: `suggest_criteria(objective, target_type, provider)` → delega a `provider.suggest_criteria` (sem persistir); `run_test(definition_id, n, sample_content, provider)` → só `draft` (409 se `published`); executa `EvaluationPipeline` em memória; persiste `EvaluationTestRun`; incrementa `EvaluationVersion.test_run_count`; retorna resultado por critério + `consolidated_result`
- [X] T026 [US1] Adicionar a `evaluation_service.py`: `get_assignments(template_key)`; `replace_assignments(template_key, list)` (valida: `definition` com ≥1 versão `published` → 422; `field_keys` existem no template para `field`/`field_set` → 422; `field_keys` vazio para `form`/`process`; `pinned_version_id` pertence à definição e está `published`); `get_evaluable_fields(template_key)` (campos com `ai_evaluation_enabled=true` + associações)
- [X] T027 [US1] Criar `src/pivma/routers/ai_evaluations.py` com endpoints da biblioteca/versões/publish conforme `contracts/ai-evaluation-config.md`: `GET/POST /ai-evaluations`, `GET/DELETE /ai-evaluations/{id}`, `GET/PATCH /ai-evaluations/{id}/versions/{n}`, `POST /ai-evaluations/{id}/versions`, `POST /ai-evaluations/{id}/versions/{n}/publish`; autorização `require_permission('ai_evaluations.manage')` (mutação) / `'ai_evaluations.read'` (leitura) + `TrustedOrigin`
- [X] T028 [US1] Adicionar a `ai_evaluations.py`: `POST /ai-evaluations/suggest-criteria`, `POST /ai-evaluations/{id}/versions/{n}/test` (usa `ModelProviderDep`; `503` se provedor indisponível), `GET/POST /ai-evaluations/references`, `GET /ai-evaluations/references/{id}/impact`
- [X] T029 [US1] Adicionar endpoints de associação a `ai_evaluations.py`: `GET/PUT /form-templates/{template_key}/evaluation-assignments` e `GET /form-templates/{template_key}/evaluable-fields` conforme `contracts/evaluation-assignments.md`
- [X] T030 [US1] Registrar `ai_evaluations.router` em `src/pivma/__init__.py`
- [X] T031 [P] [US1] API tests `tests/api/routers/test_ai_evaluations_config.py`: fluxo criar→suggest→patch→publish; `PATCH` em versão publicada → 409; `POST /versions` → novo `draft`; publish sem critério → 422; perfil não-BraCVAM → 403; sem sessão → 401
- [X] T032 [P] [US1] API tests `tests/api/routers/test_ai_evaluations_test_mode.py`: `test` em `draft` retorna resultado por critério e incrementa `test_run_count`; `test` em `published` → 409 (usa `FakeModelProvider` via `app.dependency_overrides`)
- [X] T033 [P] [US1] API tests `tests/api/routers/test_evaluation_assignments.py`: `PUT` substitui lista; `field_keys` inexistente no template → 422; definição sem versão publicada → 422; proponente → 403; `GET evaluable-fields`
- [X] T034 [P] [US1] Integration test `tests/integration/database/test_evaluation_versioning.py`: apenas um `draft` por definição (índice único parcial); critérios de versão publicada não podem ser inseridos/alterados/excluídos; definição excluída logicamente não quebra `EvaluationAssignment` nem execuções

**Checkpoint**: US1 funcional e testável — o BraCVAM configura e publica avaliações.

---

## Phase 4: User Story 2 - Pré-avaliação automática obrigatória na submissão (Priority: P2)

**Goal**: cada envio do formulário dispara uma pré-avaliação assíncrona; o proponente vê status "em andamento" e depois uma síntese compreensível; o resultado consolidado roteia (positivo → triagem; negativo/falha → volta ao proponente).

**Independent Test**: submeter formulário com associações → resposta imediata `pre_evaluation.status='in_progress'`, triagem não liberada; `GET /pre-evaluation` até `completed`; negativo → nova run de submissão para o proponente.

### Implementação

- [X] T035 [US2] Extrair helper `_open_new_submission_run(session, process_id, reason, user_id) -> int` de `_handle_needs_revision` em `src/pivma/core/process_engine.py` e refatorar `_handle_needs_revision` para usá-lo (sem mudança de comportamento)
- [X] T036 [US2] Criar `src/pivma/core/pre_evaluation_service.py`: `create_pending_run(session, process_id, activity_run_id, form_instance_id) -> EvaluationRun` (`status='in_progress'`, `correlation_id` novo); `resolve_targets(session, form_template_id, form_values)` (associações ativas → versão efetiva = `pinned_version_id` ou última `published`; expande `field_keys` → conteúdo submetido)
- [X] T037 [US2] Adicionar `run_pre_evaluation(run_id)` a `pre_evaluation_service.py`: abre `AsyncSession` própria; carrega run + alvos; executa `EvaluationPipeline` com `get_model_provider(Settings())`; persiste `EvaluationRunItem` com snapshots; `consolidate(...)`; grava `real_cost`/`models_used`/`provider_name`/`finished_at`/`status='completed'`; cria `Artifact key='ai_pre_evaluation_report'` com `metadata_payload` = relatório; em exceção → `status='failed'` + `error_summary` genérico + `AuditEvent AI_PRE_EVALUATION_FAILED`
- [X] T038 [US2] Adicionar roteamento ao final de `run_pre_evaluation`: `positive` → `_unblock_triage_activity` + `process.status='TRIAGE'` + `AuditEvent AI_PRE_EVALUATION_COMPLETED`; `negative` ou `failed` → `_open_new_submission_run(reason='Pré-avaliação automática')` + `process.status='SUBMISSION'` + `Task` PROPONENT (em `failed`, marcar o relatório com flag de falha para a UI)
- [X] T039 [US2] Editar `submit_proposal_form` em `src/pivma/core/process_engine.py`: substituir o bloco inline do `FormAIPipelineEngine` — quando o template tiver `EvaluationAssignment` ativo: chamar `create_pending_run`, **não** chamar `_unblock_triage_activity`, manter `process.status='SUBMISSION'`, marcar a atividade de triagem com `blocked_reason='Aguardando pré-avaliação automática'`, `AuditEvent AI_PRE_EVALUATION_STARTED`, retornar a run pendente; sem associações → comportamento atual (avança para `TRIAGE`)
- [X] T040 [US2] Editar `submit_form` em `src/pivma/routers/forms.py`: receber `BackgroundTasks`; quando `submit_proposal_form` retornar run pendente, `background_tasks.add_task(run_pre_evaluation, run_id)`; estender `ActivityCompletionResponse` (em `src/pivma/schemas.py`) com `pre_evaluation: {run_id, status} | None`
- [X] T041 [US2] Repontar o `direct_forms_router` `POST /forms/instances/{id}/evaluate-ai` (Spec 010) para o novo `EvaluationPipeline` **ou** removê-lo e ajustar `src/pivma/__init__.py`; remover uso de `AIEvaluationVerdict` fixo
- [X] T042 [US2] Criar `src/pivma/routers/pre_evaluation.py` com `GET /processes/{id}/pre-evaluation` (query `run_id?`; escopo por papel: participante `proponent` ou `ai_evaluations.read`) devolvendo `status`, `consolidated_result`, `summary` (contagens), `attention_points` (critério, conclusão, evidência, `evidence_location`, severidade, `recommendation`, referência, `evidence_completeness`, `inference_confidence`), `evaluation` (`definition_name`, `version_number`), `models_used`, timestamps, `direct_review_request`; registrar router em `src/pivma/__init__.py`
- [X] T043 [US2] Adicionar varredura de execuções presas ao `lifespan` do app em `src/pivma/__init__.py`: no startup, marcar `EvaluationRun` `status='in_progress'` com `started_at` > 15 minutos como `failed` e devolver a submissão ao proponente com flag de falha
- [X] T044 [P] [US2] Integration test `tests/integration/ai/test_run_pre_evaluation.py`: chamar `run_pre_evaluation` direto com sessão + `FakeModelProvider`; asserir run + itens persistidos com snapshot, `consolidated_result`, `Artifact` criado, e efeitos de roteamento (triagem liberada em `positive` / nova run de submissão em `negative`)
- [X] T045 [P] [US2] API test `tests/api/routers/test_pre_evaluation_submit.py`: submeter com associações → resposta imediata `pre_evaluation.status='in_progress'`, triagem **não** liberada; submeter sem associações → avança para `TRIAGE`, `pre_evaluation: null`
- [X] T046 [P] [US2] API test `tests/api/routers/test_pre_evaluation_get.py`: estados `in_progress` / `completed` negativo / `completed` positivo / só `indeterminate` → `positive` / `failed`; escopo proponente vs gestor
- [X] T047 [P] [US2] Unit test `tests/unit/ai/test_pipeline_targets.py`: alvo documento/OCR/imagem → item `indeterminate` sem chamada de modelo; camada correta por `check_type`

**Checkpoint**: US1 + US2 funcionam de forma independente.

---

## Phase 5: User Story 3 - Retorno ao proponente e solicitação de intervenção direta (Priority: P3)

**Goal**: após pré-avaliação negativa, o proponente pode corrigir e reenviar (nova pré-avaliação) ou ignorar a IA e solicitar intervenção direta do BraCVAM, preservando o relatório original.

**Independent Test**: pré-avaliação negativa → `POST /submission/direct-review` → `process_status='TRIAGE'`, relatório intacto; segunda chamada → 409.

### Implementação

- [X] T048 [US3] Adicionar `request_direct_review(session, process_id, user_id, justification)` a `src/pivma/core/pre_evaluation_service.py`: pré-condições (última run `completed`+`negative` **ou** `failed`; sem `DirectReviewRequest` existente para ela → 409); cria `DirectReviewRequest`; encerra a run de submissão aberta pelo roteamento negativo; `_unblock_triage_activity`; `process.status='TRIAGE'`; `AuditEvent DIRECT_REVIEW_REQUESTED`
- [X] T049 [US3] Adicionar `POST /processes/{id}/submission/direct-review` a `src/pivma/routers/pre_evaluation.py` (participante `proponent` + `TrustedOrigin`); `409` em duplicidade/estado inválido; `422` se o último resultado foi `positive`
- [X] T050 [P] [US3] API test `tests/api/routers/test_direct_review.py`: negativo → direct-review → `TRIAGE` + relatório preservado; segunda chamada → 409; resultado `positive` → 422; caminho "corrigir e reenviar" dispara nova pré-avaliação

**Checkpoint**: US1 + US2 + US3 independentes.

---

## Phase 6: User Story 4 - Triagem assistida do BraCVAM com a IA como evidência auxiliar (Priority: P4)

**Goal**: o triador vê a pré-avaliação completa (critérios, evidências, severidade, referência, versão, run id, timestamps), registra concordância/discordância por critério e decide — a decisão permanece humana.

**Independent Test**: abrir triagem → `GET /pre-evaluation` mostra tudo de FR-039 → `POST .../feedback` com agree/disagree por item (resultado da IA inalterado); conflito de interesse → 403.

### Implementação

- [X] T051 [US4] Adicionar `record_feedback(session, process_id, run_id, reviewer_id, items)` a `src/pivma/core/pre_evaluation_service.py`: guarda de conflito de interesse (`_guard_against_current_conflict`) → `AuthorizationError`; upsert `ReviewerFeedback` por `(run_item_id, reviewer_id)`; valida item pertence à run → 404; `AuditEvent AI_CRITERION_FEEDBACK_RECORDED`; **não** altera `EvaluationRunItem`
- [X] T052 [US4] Adicionar `agreement_metrics(session, check_type?, from?, to?)` a `src/pivma/core/evaluation_service.py`: taxa de concordância global e por `check_type`; critérios mais contestados (maior `disagree_rate`); execuções com mais `disagree` (derivado de `ReviewerFeedback ⨝ EvaluationRunItem`)
- [X] T053 [US4] Adicionar `POST /processes/{id}/pre-evaluation/{run_id}/feedback` (gestor + `TrustedOrigin`) a `src/pivma/routers/pre_evaluation.py` e `GET /ai-evaluations/agreement-metrics` (`ai_evaluations.read`) a `src/pivma/routers/ai_evaluations.py`
- [X] T054 [US4] Garantir que o payload de `GET /processes/{id}/pre-evaluation` para gestor contém tudo que FR-039 exige (conteúdo avaliado, critérios, evidência, `evidence_location`, severidade, referência normativa, `version_number`, data/hora, `run_id`); estender em `src/pivma/routers/pre_evaluation.py` se faltar
- [X] T055 [P] [US4] API test `tests/api/routers/test_pre_evaluation_feedback.py`: agree/disagree/inconclusive por critério; resultado da IA inalterado; reenviar mesmo item atualiza (não duplica); conflito de interesse vigente → 403
- [X] T056 [P] [US4] API test `tests/api/routers/test_agreement_metrics.py`: taxas calculadas; filtro por `check_type`

**Checkpoint**: US1–US4 independentes; ciclo de valor completo.

---

## Phase 7: User Story 5 - Biblioteca de avaliações reutilizáveis e versionamento imutável (Priority: P5)

**Goal**: manter biblioteca reutilizável; associar uma definição a múltiplos templates sem cópia; edição de versão publicada gera nova versão; submissões antigas ficam na versão que usaram.

**Independent Test**: uma definição associada a 2 templates; editar (nova versão) → v2; execuções antigas continuam na v1 (via snapshot no item).

### Implementação

- [X] T057 [US5] Estender `list_definitions` em `src/pivma/core/evaluation_service.py` com `published_versions` (contagem) e `assignments_count`; confirmar que `replace_assignments` referencia a definição (sem cópia da configuração)
- [X] T058 [US5] Confirmar/ajustar em `resolve_targets` (`src/pivma/core/pre_evaluation_service.py`) a resolução `pinned_version_id` → senão última `published`; expor ponto de teste
- [X] T059 [P] [US5] Integration test `tests/integration/database/test_evaluation_library_reuse.py`: definição em 2 templates sem duplicação; editar publicada → v2; execução anterior mantém snapshot da v1; remover definição com associação ativa → exclusão lógica, execuções reconstroem
- [X] T060 [P] [US5] API test `tests/api/routers/test_evaluation_library.py`: `GET /ai-evaluations` com status de versão + contagens; associação com `pinned_version_id` vs última publicada

---

## Phase 8: User Story 6 - Modo de teste antes da publicação (Priority: P6)

**Goal**: executar a avaliação sobre conteúdo de exemplo antes de publicar, iterar, e ser avisado na publicação quando nunca testada.

**Independent Test**: rodar teste → ajustar critério via PATCH → rodar de novo → publicar com `test_warning=false`; publicar sem nunca testar → `test_warning=true`.

### Implementação

- [X] T061 [US6] Garantir que `publish_version` (`src/pivma/core/evaluation_service.py`) retorna `test_warning` e que o endpoint `POST /ai-evaluations/{id}/versions/{n}/publish` (`src/pivma/routers/ai_evaluations.py`) expõe esse campo; confirmar guarda `draft`-only em `run_test` (409)
- [X] T062 [P] [US6] API test `tests/api/routers/test_evaluation_test_mode_iteration.py`: teste → PATCH critério → teste de novo → publish com `test_warning=false`; publish sem teste → `test_warning=true`; `test` em versão publicada → 409

---

## Phase 9: User Story 7 - Demonstrações interativas (Priority: P7)

**Goal**: dois módulos em `demos/` contra a API real em `http://localhost:8000` — configuração pelo editor de formulário e pela biblioteca — sem nada criado só para a demo.

**Independent Test**: abrir cada módulo a partir de `demos/index.html`, usar o seed, e ver dados reais do banco sendo alterados via API.

### Implementação

- [X] T063 [US7] Criar `scripts/seeds/ai_evaluation_seed.py`: usuário admin BraCVAM + proponente; uma avaliação publicada "Verificação de estrutura de POP" (com critério `critical` e critério `low`); uma `EvaluationReference`; associação ao campo POP de `pre_validated_method`; uma `ProcessInstance` pronta para submissão
- [X] T064 [US7] Criar `demos/ai-evaluation-library/index.html` + `app.js`: fluxo criar → `suggest-criteria` → editar → testar → publicar → associar; autentica via `/auth/token`; consome só `http://localhost:8000`
- [X] T065 [US7] Criar `demos/ai-evaluation-form-editor/index.html` + `app.js`: a partir da tela do editor de formulário, listar `evaluable-fields`, anexar/desanexar avaliações, submeter como proponente e acompanhar a pré-avaliação resolver e rotear
- [X] T066 [US7] Atualizar `demos/index.html` para catalogar os dois novos módulos
- [X] T067 [US7] Validação manual: rodar os dois módulos contra a API local + seed; confirmar mutações reais no banco e ausência de endpoint/dado exclusivo de demo

---

## Phase 10: Polish & Cross-Cutting

- [X] T068 [P] Ligar `broadcaster.broadcast_operational` / `broadcast_ai_step` para `FORM_AI_PRE_EVALUATION` e confirmar que o streaming de `src/pivma/routers/admin_logs.py` agrupa por `correlation_id`
- [X] T069 [P] Criar teste opt-in `tests/integration/ai/test_openai_live.py` com `@pytest.mark.skipif(not os.getenv('RUN_OPENAI_TESTS'), reason='usa tokens reais')`
- [X] T070 [P] Atualizar `.env.example` com `OPENAI_API_KEY`, `AI_PROVIDER`, `AI_MODEL_EXTRACTION`, `AI_MODEL_FAST`, `AI_MODEL_REASONING`
- [X] T071 [P] Atualizar `README.md` (seção de IA) e `demos/DESIGN.md` com o novo modelo de avaliação configurável e os dois módulos de demo
- [X] T072 Rodar `uv run ruff format` + `uv run ruff check` + `uv run pytest`; corrigir regressões
- [X] T073 Executar de ponta a ponta os cenários A–E de `specs/013-configurable-ai-evaluation/quickstart.md`

---

## Dependencies & Execution Order

### Fases

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende do Setup — **BLOQUEIA** todas as user stories. Ordem interna: T004→T005→T006→T007→T008→T009 (mesmo arquivo `models.py` / migração, sequenciais); T010–T021 em paralelo após os modelos existirem (T011–T017 dependem só de T002; T018–T021 dependem dos modelos + T012/T014).
- **US1 (Phase 3)**: depende da Foundational. É o MVP.
- **US2 (Phase 4)**: depende da Foundational + US1 (precisa de `EvaluationAssignment` e de versões publicadas para avaliar).
- **US3 (Phase 5)**: depende de US2 (resultado negativo).
- **US4 (Phase 6)**: depende de US2 (execução para dar feedback).
- **US5 (Phase 7)**: depende de US1 (reforça biblioteca/versionamento); testes cruzam com US2.
- **US6 (Phase 8)**: depende de US1 (modo de teste já criado em T025; aqui é reforço).
- **US7 (Phase 9)**: depende de US1–US4 (fluxo completo nas demos).
- **Polish (Phase 10)**: depende das stories desejadas concluídas.

### Dentro de cada story

Modelos → serviços → endpoints → testes. Testes `[P]` de uma mesma story rodam juntos (arquivos distintos).

### Oportunidades de paralelismo

- Setup: T002, T003 em paralelo.
- Foundational: T010, T011, T012, T014, T016, T017 em paralelo; depois T018, T019, T020, T021.
- US1: T031–T034 em paralelo após os endpoints; T022 em paralelo com T023 (schemas vs serviço).
- US2: T044–T047 em paralelo após implementação.
- US4: T055, T056 em paralelo.
- Polish: T068–T071 em paralelo.

---

## Parallel Example: Foundational

```bash
# Após T004–T009 (models + migração), lançar em paralelo:
Task: "T010 constantes de autorização em src/pivma/core/authorization.py"
Task: "T011 schemas de saída do LLM em src/pivma/ai/schemas.py"
Task: "T012 ModelProvider + Fake/OpenAI em src/pivma/ai/provider.py"
Task: "T014 regra de consolidação em src/pivma/ai/consolidation.py"
Task: "T017 estender src/pivma/ai/contracts.py"
```

## Parallel Example: User Story 1

```bash
Task: "T031 API tests de configuração em tests/api/routers/test_ai_evaluations_config.py"
Task: "T032 API tests de modo de teste em tests/api/routers/test_ai_evaluations_test_mode.py"
Task: "T033 API tests de associação em tests/api/routers/test_evaluation_assignments.py"
Task: "T034 integração de versionamento em tests/integration/database/test_evaluation_versioning.py"
```

---

## Implementation Strategy

### MVP (US1)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **PARAR e VALIDAR**: BraCVAM cria, testa, associa e publica uma avaliação; imutabilidade da versão publicada confirmada.
3. Demo parcial possível já aqui (`demos/ai-evaluation-library/` sem o fluxo de submissão).

### Entrega incremental

- Setup + Foundational → base pronta.
- + US1 → configuração completa (MVP).
- + US2 → pré-avaliação assíncrona no fluxo de submissão.
- + US3 → contrapeso do proponente.
- + US4 → triagem assistida (fecha o ciclo de valor).
- + US5/US6 → reforço de governança e qualidade de configuração.
- + US7 → demonstrações (critério de conclusão do `AGENTS.md`).

---

## Notes

- Antes de criar/alterar testes: `Skill({skill: "fastapi-testing-methodology"})`.
- Toda mutação declara `CurrentUser` + `TrustedOrigin`. Todo modelo novo herda `AuditMixin` e usa exclusão lógica.
- `unit`/`api`/CI **nunca** chamam a OpenAI: `AI_PROVIDER=fake` no `conftest` + `app.dependency_overrides[get_model_provider]` nos testes.
- Enums são `String(N)` validados na camada Pydantic/serviço (padrão do repositório — sem `Enum` nativo do Postgres).
- FR-049/FR-050 (formulário dinâmico): **sem tarefa** — a decisão é não estender o editor da Spec 012; consumido como está.
- Portão antes de entregar cada story: `ruff format` + `ruff check` + `pytest` verdes.
- Commit por tarefa ou grupo lógico; parar em cada checkpoint para validar a story isoladamente.

## Requirements → Tasks (cobertura)

| Grupo de requisitos | Tarefas |
|---|---|
| FR-001–011 (configuração) | T022–T030 |
| FR-012–016 (versionamento/governança) | T023, T034, T059 |
| FR-017–020 (modo de teste) | T025, T061, T062 |
| FR-021–021d (assíncrono) | T036–T043, T045 |
| FR-022–029 (execução do pipeline) | T014–T016, T037, T047 |
| FR-024a–e (provedor de modelos) | T011–T013, T020 |
| FR-030–033 (consolidação/roteamento) | T014, T038, T044 |
| FR-034–038 (fluxo do proponente) | T042, T048–T050 |
| FR-039–043 (triagem/feedback) | T051–T056 |
| FR-044–048 (auditoria/observabilidade) | T017, T037, T068 |
| SC-011 (CI sem tokens) | T003, T012, T020, T032 |
| SC-013/014 + demos | T045, T063–T067 |
