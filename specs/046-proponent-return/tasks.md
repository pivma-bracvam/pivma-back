---

description: "Lista de tarefas da Spec 046"
---

# Tasks: Retorno ao Proponente

**Input**: artefatos em `specs/046-proponent-return/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: obrigatórios (`AGENTS.md`, constituição V). Cada tarefa de teste cobre um comportamento. Em cada história, escreva os testes primeiro e confirme que falham pelo motivo esperado antes de implementar. Carregue `testing-methodology` antes das tarefas de teste e `karpathy-guidelines` antes das tarefas de código.

**Organization**: uma fase por história, na ordem de prioridade da spec.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo: arquivo diferente e sem dependência de tarefa incompleta
- **[Story]**: história da spec (US1, US2, US3)

## Convenções

- As jornadas descrevem na docstring do módulo o ator, o objetivo e a origem (Spec 046 e história), numeram os passos em comentários e usam só a API pública, a partir de `bootstrap_fresh_deploy`. A exceção é chamar `pre_evaluation_service._execute`, `_mark_failed` e o worker, que não têm rota pública.
- Nos testes focados de API, verifique o `code` do erro, não a mensagem.
- Em `tests/api/routers/test_return_review.py`, reaproveite `_triage_return`, `_ai_return`, `_choose` e `_created_process`.
- Pareceres são gravados por `POST /processes/{id}/triage/reviews`, com `{"reviews": [{"field_key", "status", "comments"}]}`.

---

## Phase 1: Setup

**Purpose**: registrar a linha de base. Nenhuma dependência nova.

- [X] T001 Rodar `poetry run pytest tests/api/routers/test_return_review.py tests/integration/notifications tests/integration/journeys/etapa_1_submissao_triagem` e registrar o resultado, para separar falhas prévias das causadas por esta entrega

**Fase Foundational**: não se aplica. Nenhuma peça é pré-requisito de mais de uma história.

---

## Phase 2: User Story 1 - Corrigir a proposta com os pareceres à mão (Priority: P1) 🎯 MVP

**Goal**: o proponente lê os pareceres da rodada anterior depois de `REVISE`, e cada versão devolvida mostra os da própria rodada.

**Independent Test**: devolver uma submissão com pareceres, escolher `REVISE`, abrir o formulário em uma nova sessão e consultar a versão devolvida.

### Jornadas da US1

- [X] T002 [US1] Criar `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_feedback.py` com a jornada `test_proponente_corrige_com_pareceres_e_consulta_cada_rodada`: o proponente envia; o triador grava pareceres em dois campos e decide `NEEDS_REVISION`; o proponente sai, entra de novo, escolhe `REVISE` e vê `previous_reviews` com status, comentário e data, e `reviews` vazio; salva rascunho, reenvia e relê a versão 1 igual; o triador devolve a rodada 2 com outro parecer; as versões 1 e 2 mostram só os próprios pareceres (cenários 1 a 4)
- [X] T003 [US1] Adicionar a `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_feedback.py` a jornada `test_proponente_revisa_retorno_da_ia_sem_pareceres`, no fluxo de `test_return_review_via_ai.py`: a IA devolve, o proponente escolhe `REVISE`, `previous_reviews` vem vazio e `GET .../pre-evaluation` segue com o resultado (cenário 5)

### Testes focados da US1

- [X] T004 [US1] Testar `test_form_previous_reviews_empty_on_first_run` em `tests/api/routers/test_return_review.py`: a primeira rodada devolve `previous_reviews == {}` (FR-002)
- [X] T005 [US1] Testar `test_form_previous_reviews_empty_when_previous_run_has_no_reviews` em `tests/api/routers/test_return_review.py`: devolução pela triagem sem pareceres seguida de `REVISE` devolve `{}` (FR-002)
- [X] T006 [US1] Testar `test_form_previous_reviews_empty_for_other_activities` em `tests/api/routers/test_return_review.py`: `GET .../activities/statistical_plan/form`, com o processo montado por `tests/factories/structure_approval_factory.py`, devolve `{}` mesmo com pareceres na submissão (FR-002)
- [X] T007 [US1] Testar `test_form_previous_reviews_follows_requested_run_number` em `tests/api/routers/test_return_review.py`: em processo na rodada 3, `?run_number=2` traz os pareceres da rodada 1 em `previous_reviews` e os da rodada 2 em `reviews`, sem misturar, e `?run_number=1` traz `previous_reviews == {}` (contrato, cenário 1)
- [X] T008 [US1] Testar `test_form_previous_reviews_keeps_removed_field` em `tests/api/routers/test_return_review.py`: o administrador remove o campo avaliado por `PUT /processes/templates/{key}/forms/{form_key}`, e a chave segue em `previous_reviews`, fora de `fields` (FR-004)
- [X] T009 [US1] Testar `test_version_reviews_keeps_removed_field` em `tests/api/routers/test_return_review.py`: mesma remoção, com a chave presente em `GET .../submission-versions/1` (FR-004)
- [X] T010 [US1] Testar `test_form_previous_reviews_only_immediately_previous_run` em `tests/api/routers/test_return_review.py`: rodada 1 devolvida pela triagem com pareceres, rodada 2 devolvida pela IA e `REVISE`; o formulário da rodada 3 traz `{}` e a versão 1 mantém os pareceres (edge case)
- [X] T011 [US1] Testar `test_version_reviews_empty_when_returned_by_ai` em `tests/api/routers/test_return_review.py`: versão devolvida pela IA responde `reviews == {}` (contrato)
- [X] T012 [US1] Testar `test_triage_cannot_change_reviews_of_returned_run` em `tests/api/routers/test_return_review.py`: depois de `NEEDS_REVISION`, `POST .../triage/reviews` responde `409` e a versão devolvida não muda (FR-005)
- [X] T013 [US1] Testar `test_reviews_responses_do_not_identify_reviewer` em `tests/api/routers/test_return_review.py`: cada parecer do formulário e da versão tem exatamente as chaves `status`, `comments` e `reviewed_at`, e nome, e-mail e ID do triador não aparecem no corpo (FR-006, SC-005)
- [X] T014 [US1] Testar `test_stranger_gets_404_on_form_with_previous_reviews` em `tests/api/routers/test_return_review.py`: usuário sem acesso recebe `404` no formulário, sem nenhum parecer no corpo (FR-007)
- [X] T015 [US1] Testar `test_stranger_gets_404_on_version_with_reviews` em `tests/api/routers/test_return_review.py`: usuário sem acesso recebe `404` na versão devolvida (FR-007)
- [X] T016 [US1] Testar `test_versions_listing_has_no_reviews` em `tests/api/routers/test_return_review.py`: os itens de `GET .../submission-versions` não têm a chave `reviews` (FR-003)
- [X] T017 [US1] Testar `test_return_review_404_after_decision_with_reviews` em `tests/api/routers/test_return_review.py`: depois de `REVISE` numa devolução com pareceres, `GET .../return-review` responde `404` (FR-008)
- [X] T018 [US1] Testar `test_soft_deleted_review_is_hidden` em `tests/api/routers/test_return_review.py`: um `FieldReview` com `set_deletion_audit` some de `previous_reviews` e da versão. O parecer é alterado direto no banco, porque não existe rota de exclusão (integração da consulta)

### Implementação da US1

- [X] T019 [US1] Adicionar `previous_reviews: dict[str, FieldReviewSummary]` a `FormInstanceResponse` e `reviews: dict[str, FieldReviewSummary]` a `SubmissionVersionResponse`, sem tocar em `SubmissionVersionSummary`, em `src/pivma/schemas.py`
- [X] T020 [US1] Criar `submission_run_reviews(session, process_id, run_number) -> dict[str, dict[str, Any]]` em `src/pivma/core/process_engine.py`, conforme research R1: uma consulta com `skip_soft_delete_filter=True`, `deleted_at` nulo em `FieldReview`, `FormInstance`, `ActivityRun` e `ActivityInstance`, sem filtrar `FormField`, ordenada por `FieldReview.reviewed_at`
- [X] T021 [US1] Em `get_returned_submission_version`, em `src/pivma/core/process_engine.py`, preencher `reviews` com `submission_run_reviews`, sem alterar `_load_submission_version_rows`
- [X] T022 [US1] Em `get_activity_form`, em `src/pivma/routers/forms.py`, usar a execução hoje descartada de `get_current_form_instance` e passar `previous_reviews` com `submission_run_reviews(session, id, run.run_number - 1)` só em `proposal_submission`, sem alterar a montagem de `reviews`
- [X] T023 [US1] Rodar T002 a T018 e os testes de `tests/api/routers/test_process_submission_update.py`, e confirmar que passam

**Checkpoint**: a issue #73 está entregue e testável sozinha.

---

## Phase 3: User Story 2 - Saber da devolução por e-mail (Priority: P2)

**Goal**: toda devolução avisa cada proponente ativo por e-mail, sem revelar conteúdo nem avaliador, e sem depender do canal.

**Independent Test**: devolver uma submissão pela triagem e pela IA e conferir o e-mail entregue pelo canal falso.

### Infraestrutura de teste da US2

- [X] T024 [US2] Criar em `tests/conftest.py`, ao lado de `email_settings`, a fixture `return_email_settings(monkeypatch)`: guarda uma instância de `email_settings()`, aplica `monkeypatch.setattr('pivma.core.process_engine.Settings', lambda: settings)` e a devolve, para o worker usar a mesma chave. Definir também `no_email_channel(monkeypatch)`, com `NOTIFICATION_EMAIL_BACKEND=None`, para o teste não depender do `.env` local

### Jornada da US2

- [X] T025 [US2] Criar `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_email.py` com a jornada `test_proponente_recebe_aviso_da_devolucao_pela_triagem_e_pela_ia`: a triagem devolve e o worker (`process_next` com `FakeEmailChannel`) entrega um e-mail com código, título, origem `Triagem`, prazo e orientação; o proponente revisa e reenvia; a IA devolve em outro processo do template 4 e o e-mail traz a origem `Pré-avaliação por IA` (cenários 1 e 2)
- [X] T026 [US2] Adicionar a `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_email.py` a jornada `test_reprocessamento_cancela_aviso_pendente_e_nova_devolucao_avisa`: a IA falha, o envio fica `pending`, o administrador reprocessa, o envio vira `cancelled`, o worker não entrega nada, e a nova devolução gera e entrega outro e-mail (cenário 5)

### Testes focados da US2

Renderizador em `tests/unit/notifications/test_submission_returned_email_renderer.py`, no modelo de `test_sample_decision_email_renderer.py`.

- [X] T027 [P] [US2] Testar `test_subject_names_return_and_process` em `tests/unit/notifications/test_submission_returned_email_renderer.py`: assunto `Submissão devolvida — VAL-2026-0001`
- [X] T028 [P] [US2] Testar `test_body_has_process_origin_deadline_and_guidance` em `tests/unit/notifications/test_submission_returned_email_renderer.py`, parametrizado por corpo (texto e HTML) e por origem: `TRIAGE` vira `Triagem`, `AI_PRE_EVALUATION` vira `Pré-avaliação por IA` (FR-010)
- [X] T029 [P] [US2] Testar `test_body_omits_deadline_line_without_due_date` em `tests/unit/notifications/test_submission_returned_email_renderer.py`: com `due_date` nulo, a linha `Prazo` não aparece
- [X] T030 [P] [US2] Testar `test_html_escapes_process_title` em `tests/unit/notifications/test_submission_returned_email_renderer.py`: título com `<script>` sai escapado no HTML

Integração em `tests/integration/notifications/test_submission_returned_email.py`, no modelo de `test_sample_decision_email.py`, reaproveitando `_triage_return` e `_ai_return`.

- [X] T031 [P] [US2] Testar `test_triage_return_enqueues_one_email_with_subject_and_process` em `tests/integration/notifications/test_submission_returned_email.py`: envio `pending`, `kind` `submission_returned_email`, destinatário do proponente, `subject_type` `submission_return_review`, `subject_id` da execução do retorno e `process_instance_id` preenchido (FR-009, FR-014)
- [X] T032 [P] [US2] Testar `test_negative_ai_return_enqueues_email` em `tests/integration/notifications/test_submission_returned_email.py` (FR-009, SC-003)
- [X] T033 [P] [US2] Testar `test_failed_ai_return_enqueues_email_with_same_origin` em `tests/integration/notifications/test_submission_returned_email.py`: o payload da falha é igual em origem ao da reprovação (FR-009, FR-011)
- [X] T034 [P] [US2] Testar `test_each_active_proponent_gets_own_email` em `tests/integration/notifications/test_submission_returned_email.py`: dois proponentes ativos, adicionados com `grant_cargo`, geram dois envios (edge case)
- [X] T035 [P] [US2] Testar `test_revoked_proponent_gets_no_email` em `tests/integration/notifications/test_submission_returned_email.py`: designação com `revoked_at` não recebe, e a devolução conclui (FR-009)
- [X] T036 [P] [US2] Testar `test_deleted_account_gets_no_email` em `tests/integration/notifications/test_submission_returned_email.py`: conta com exclusão lógica não recebe (edge case)
- [X] T037 [P] [US2] Testar `test_other_roles_get_no_email` em `tests/integration/notifications/test_submission_returned_email.py`: patrocinador designado no processo não recebe (FR-009)
- [X] T038 [P] [US2] Testar `test_delivered_email_hides_justification_reviews_and_reviewer` em `tests/integration/notifications/test_submission_returned_email.py`: em devolução pela triagem com justificativa e parecer marcados, assunto, texto e HTML entregues não contêm esses textos nem o nome do triador (FR-011, SC-005)
- [X] T039 [P] [US2] Testar `test_delivered_email_hides_ai_result` em `tests/integration/notifications/test_submission_returned_email.py`: em devolução pela IA, o e-mail não contém o enunciado do critério nem a palavra `falha` (FR-011)
- [X] T040 [P] [US2] Testar `test_return_completes_without_email_channel` em `tests/integration/notifications/test_submission_returned_email.py`, com `no_email_channel`: `200`, tarefa `READY`, nenhum `Notification` (FR-012, SC-004)
- [X] T041 [P] [US2] Testar `test_rollback_of_return_discards_email` em `tests/integration/notifications/test_submission_returned_email.py`: chamar `open_return_review` e fazer `rollback` não deixa envio, provando a mesma transação (FR-009)
- [X] T042 [P] [US2] Testar `test_permanent_delivery_failure_keeps_return_open` em `tests/integration/notifications/test_submission_returned_email.py`: com falha permanente em `FakeEmailChannel.failures`, o envio vira `failed` e o retorno segue aberto (SC-004)
- [X] T043 [P] [US2] Testar `test_retry_cancels_pending_email_and_records_event` em `tests/integration/notifications/test_submission_returned_email.py`: envio `cancelled`, `error_code` `return_review_cancelled`, payload apagado e evento `NOTIFICATION_CANCELLED` com `user_id` do administrador, não de quem criou a execução (FR-013, FR-013a)
- [X] T044 [P] [US2] Testar `test_retry_keeps_already_sent_email` em `tests/integration/notifications/test_submission_returned_email.py`: envio `sent` não muda no reprocessamento (FR-013)
- [X] T045 [P] [US2] Testar `test_decision_keeps_pending_email` em `tests/integration/notifications/test_submission_returned_email.py`: `REVISE` não cancela o envio pendente (research R7)
- [X] T046 [P] [US2] Testar `test_sent_email_records_audit_event_with_subject` em `tests/integration/notifications/test_submission_returned_email.py`: depois do worker, `NOTIFICATION_SENT` traz `kind` e assunto, sem destinatário (FR-014)
- [X] T047 [P] [US2] Testar `test_retry_records_cancellation_with_admin_as_author` em `tests/integration/notifications/test_submission_returned_email.py`, com `no_email_channel`: mesmo sem envio, a linha do tempo tem um `RETURN_REVIEW_CANCELLED` com `user_id` do administrador, `source` e `run_number` (FR-013a)
- [X] T048 [P] [US2] Testar `test_retry_new_run_keeps_original_creator` em `tests/integration/notifications/test_submission_returned_email.py`: a nova `EvaluationRun` mantém o `created_by` da anterior (FR-013a)
- [X] T049 [P] [US2] Testar `test_process_deletion_cancels_pending_email` em `tests/integration/notifications/test_submission_returned_email.py`: depois de `DELETE /processes/{id}`, o envio fica `cancelled`, grava `NOTIFICATION_CANCELLED` e o worker não entrega nada (FR-013)

### Implementação da US2

- [X] T050 [US2] Adicionar `SUBMISSION_RETURNED_EMAIL = 'submission_returned_email'`, o mapa de origens e `render_submission_returned_email` a `src/pivma/notifications/renderers.py`, usando `_format_deadline`, `escape` e o contrato [submission-returned-email.md](contracts/submission-returned-email.md), e registrar em `RENDERERS`
- [X] T051 [US2] Criar `_active_proponent_emails(session, process_id)` em `src/pivma/core/process_engine.py`, no modelo de `_selection_group_emails`, com `PROPONENT_ROLE_KEY`
- [X] T052 [US2] Em `open_return_review`, em `src/pivma/core/process_engine.py`, depois do evento `RETURN_REVIEW_OPENED`: importar `Settings` no módulo, chamar `Settings()`, sair sem envio se `email_channel_available` for falso e pedir um envio por e-mail com `subject=(RETURN_REVIEW_KEY, run.id)`, `process_instance_id` e payload `process_code`, `process_title`, `source` e `due_date` em ISO ou nulo (research R3 e R4)
- [X] T053 [US2] Em `cancel_open_return_review`, em `src/pivma/core/process_engine.py`, chamar `cancel_pending_notifications(session, subject=(RETURN_REVIEW_KEY, run.id), reason='return_review_cancelled', actor_id=user_id)` e gravar `AuditEvent` `RETURN_REVIEW_CANCELLED`, com `activity_run_id`, `user_id` e `context_data` `source` e `run_number`, para cada execução cancelada
- [X] T054 [US2] Em `retry_run`, em `src/pivma/core/pre_evaluation_service.py`, renomear o parâmetro para `actor_id`, repassá-lo a `cancel_open_return_review` e usar `new_run.set_creation_audit(old.created_by)`. Em `retry_pre_evaluation`, em `src/pivma/routers/pre_evaluation.py`, passar `actor.id` e deixar `del origin`
- [X] T055 [US2] Em `delete_process`, em `src/pivma/core/process_engine.py`, chamar `cancel_pending_notifications` com `subject=(RETURN_REVIEW_KEY, run.id)` e `reason='return_review_cancelled'` para cada execução de `submission_return_review` do processo, inclusive retorno já decidido (cenário 6 da US2). A desistência não passa por aí
- [X] T056 [US2] Rodar T025 a T049 e os testes de `tests/unit/notifications`, e confirmar que passam

**Checkpoint**: o RF011 está entregue e testável sozinho.

---

## Phase 4: User Story 3 - Decisões simultâneas sobre o mesmo retorno (Priority: P3)

**Goal**: operações disputando o mesmo retorno ou a mesma execução da IA terminam com um vencedor e um efeito.

**Independent Test**: disparar as operações em conexões independentes contra o banco real e conferir vencedor e efeitos.

### Jornada da US3

- [X] T057 [US3] Criar `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_conflicts.py` com a jornada `test_escolha_vale_uma_vez_e_reprocessamento_nao_atropela_contestacao`: a IA falha; o proponente contesta e vê a triagem assumir; o administrador tenta reprocessar e recebe `409`; a segunda escolha do proponente recebe `409`; o triador continua com uma única tarefa `READY`, e não surge nova pré-avaliação

### Regressão sequencial do reprocessamento

Em `tests/api/routers/test_return_review.py`. Estes testes reproduzem de forma determinística o defeito da research R5 e devem falhar antes da correção (FR-016a). O teste de `in_progress` não existe hoje como contrato; os demais são regressões.

- [X] T058 [US3] Testar `test_retry_in_progress_run_is_conflict` em `tests/api/routers/test_return_review.py`: `409`, sem nova `EvaluationRun`
- [X] T059 [US3] Testar `test_retry_older_failed_run_is_conflict` em `tests/api/routers/test_return_review.py`: depois de reprocessar, reprocessar de novo o ID antigo responde `409`
- [X] T060 [US3] Testar `test_retry_after_revise_is_conflict` em `tests/api/routers/test_return_review.py`: `409`, sem nova execução e com a nova rodada da submissão intacta
- [X] T061 [US3] Testar `test_retry_after_contest_is_conflict` em `tests/api/routers/test_return_review.py`: `409`, sem nova execução, com a triagem aberta e o `DirectReviewRequest` mantido
- [X] T062 [US3] Testar `test_retry_after_contest_and_triage_return_is_conflict` em `tests/api/routers/test_return_review.py`: a IA falha, o proponente contesta e a triagem decide `NEEDS_REVISION`; o reprocessamento da execução responde `409`, sem nova execução, e o retorno da triagem, a tarefa e o envio pendente seguem abertos
- [X] T063 [US3] Testar `test_retry_completed_run_is_conflict` em `tests/api/routers/test_return_review.py`, caso ainda não exista: execução `completed` responde `409`
- [X] T064 [US3] Testar `test_rejected_retry_leaves_no_partial_effect` em `tests/api/routers/test_return_review.py`: num caso de conflito com retorno aberto (execução mais antiga), o retorno, a tarefa e o envio pendente seguem abertos

### Infraestrutura de concorrência

- [X] T065 [US3] Criar `tests/factories/return_review_factory.py` com o context manager `committed_return_review(engine, state)`, para `state` em `'triage_return'`, `'ai_failed'` e `'ai_in_progress'`, no modelo de `committed_lab_process` e do `_purge` de `test_per_laboratory_concurrency.py`. Usar um template de sonda próprio, com `proposal_submission`, `triage_evaluation`, `submission_return_review` e a dependência da triagem sobre a submissão, para não commitar os templates oficiais. `ai_failed` chama `_mark_failed` sobre uma `EvaluationRun` `in_progress`. `ai_in_progress` deixa essa execução aberta, com uma avaliação publicada associada ao template e um critério `critical` cujo enunciado não aparece no conteúdo, para `_execute` dar negativo com o provedor fake (ver `_submitted_run` em `tests/integration/ai/test_run_pre_evaluation.py`). O `finally` apaga, nessa ordem de dependência, tudo o que o caso cria, incluindo `notifications`, `direct_review_requests`, `evaluation_runs` e as tabelas da avaliação, e o teste confere que nenhuma linha do processo sobrou

### Testes de concorrência

Cada teste abre uma `AsyncSession(engine, expire_on_commit=False)` por concorrente e usa `asyncio.gather(..., return_exceptions=True)`. Depois confere os efeitos em sessão nova.

Em `tests/integration/database/test_return_review_concurrency.py` (FR-015):

- [X] T066 [P] [US3] Testar `test_revise_and_withdraw_race_has_one_winner` em `tests/integration/database/test_return_review_concurrency.py`, com `triage_return`: um sucesso, um `ConflictError`, um `RETURN_REVIEW_DECIDED`, e estado coerente com o vencedor: nova rodada aberta e processo `OPEN`, ou nenhuma rodada nova e processo `CLOSED`
- [X] T067 [P] [US3] Testar `test_double_revise_opens_one_submission_run` em `tests/integration/database/test_return_review_concurrency.py`, com `triage_return`: um `ConflictError` e exatamente uma execução nova da submissão
- [X] T068 [P] [US3] Testar `test_revise_and_contest_race_has_one_winner` em `tests/integration/database/test_return_review_concurrency.py`, com `ai_failed`, porque `CONTEST_AI` não se aplica a retorno da triagem: um `RETURN_REVIEW_DECIDED`, e nunca nova rodada junto com `DirectReviewRequest`

Em `tests/integration/database/test_pre_evaluation_concurrency.py` (FR-016, FR-016a):

- [X] T069 [P] [US3] Testar `test_double_retry_creates_one_run` em `tests/integration/database/test_pre_evaluation_concurrency.py`, com `ai_failed` e `return_email_settings`: um `ConflictError`, uma nova `EvaluationRun` e um `NOTIFICATION_CANCELLED`
- [X] T070 [P] [US3] Testar `test_retry_and_contest_race_has_one_winner` em `tests/integration/database/test_pre_evaluation_concurrency.py`, com `ai_failed`: um `ConflictError`, e nunca nova `EvaluationRun` junto com `DirectReviewRequest`
- [X] T071 [P] [US3] Testar `test_execute_and_retry_race_keeps_one_result` em `tests/integration/database/test_pre_evaluation_concurrency.py`, com `ai_in_progress`: `retry_run` recebe `ConflictError`, sem nova `EvaluationRun`, e existe um `ai_pre_evaluation_report`
- [X] T072 [P] [US3] Testar `test_execute_and_contest_race_keeps_one_result` em `tests/integration/database/test_pre_evaluation_concurrency.py`, com `ai_in_progress` e resultado negativo: um relatório e no máximo um `DirectReviewRequest`. A contestação pode ter sucesso se chegar depois do resultado, então o teste confere os efeitos, não o vencedor

### Implementação da US3

- [X] T073 [US3] Confirmar que T058 a T062, T069 e T070 falham pelo motivo da research R5, e registrar a saída. Se algum passar, revisar o achado antes de alterar o código
- [X] T074 [US3] Em `cancel_open_return_review`, em `src/pivma/core/process_engine.py`, trocar a leitura de `act.runs` por um `select` das execuções `IN_PROGRESS` com `execution_reason == RETURN_SOURCE_AI`, `with_for_update()`, `populate_existing` e `selectinload(ActivityRun.tasks)`. Alterar a atividade só se cancelou alguma execução, e devolver `True` nesse caso (research R5)
- [X] T075 [US3] Em `retry_run`, em `src/pivma/core/pre_evaluation_service.py`, depois de `ensure_process_mutable`, usar o retorno do cancelamento feito com `actor_id`, travar a `EvaluationRun` com `status == 'failed'` e conferir `_latest_run`. Em qualquer falha, chamar `session.rollback()` e lançar `ConflictError` (FR-016a)
- [X] T076 [US3] Remover o `TODO(spec-030)` de `src/pivma/core/pre_evaluation_service.py`, mantendo a nota da Spec 030 sobre a trava da `EvaluationRun`
- [X] T077 [US3] Remover o `TODO(spec-030)` de `src/pivma/core/return_review_service.py`
- [X] T078 [US3] Rodar T057 a T072 e confirmar que passam. Se um teste revelar outra corrida, corrigi-la nesta entrega, com o teste como regressão (FR-017)
- [X] T079 [US3] Repetir 20 vezes `poetry run pytest tests/integration/database/test_return_review_concurrency.py tests/integration/database/test_pre_evaluation_concurrency.py` e confirmar que não há falha intermitente nem deadlock

**Checkpoint**: nenhuma corrida testada produz efeito duplicado.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: manual e verificação final (FR-018). Carregue `stop-slop` antes de editar as páginas.

- [X] T080 [P] Documentar `previous_reviews`, inclusive `?run_number`, e `reviews` da versão em `manual/guias/enviar-uma-proposta.md`
- [X] T081 [P] Documentar em `manual/guias/responder-ao-retorno.md` onde ler os pareceres depois de `REVISE`, o e-mail de devolução e as condições do reprocessamento
- [X] T082 [P] Ajustar a referência a `reviews` em `manual/guias/conduzir-a-triagem.md`, e citar os pareceres em `manual/tutorial/triagem-pede-ajustes.md` se o tutorial mostrar a revisão pelo proponente
- [X] T083 [P] Adicionar `submission_returned_email`, o motivo de cancelamento, a exclusão do processo e o comportamento sem canal a `manual/explicacao/notificacoes.md`, inclusive a abertura da página, o diagrama de estados e a seção Rastro
- [X] T084 [P] Ajustar a linha do reprocessamento, inclusive o retorno da triagem, e o texto do `409` em `manual/explicacao/pre-avaliacao-ia.md`
- [X] T085 [P] Atualizar RF011 e RF033 em `manual/explicacao/escopo.md`
- [X] T086 [P] Adicionar `RETURN_REVIEW_CANCELLED` e seu contexto a `manual/referencia/eventos.md`, conferir `manual/referencia/rotas.md` e `erros.md`, e atualizar só o que mudou
- [X] T087 Conferir que `grep -rn "TODO(spec-030)" src` não lista nada
- [X] T088 Rodar `poetry run poe lint`
- [X] T089 Rodar `poetry run poe test` e informar o resultado lido na saída do pytest, porque a tarefa usa `-x` e `ignore_fail` e sai com código 0 mesmo com falha
- [X] T090 Rodar `poetry run poe docs-build`
- [X] T091 Percorrer os critérios de parada de `testing-methodology` e o [quickstart](quickstart.md), e registrar no PR cada FR com o teste que o prova

---

## Dependencies & Execution Order

- **Setup** vem antes de tudo.
- **US1** não depende das outras histórias e entrega o MVP.
- **US2** não depende da US1.
- **US3** depende da US2: T053 e T074 alteram a mesma função, T075 parte de T054, e T069 usa a fixture de T024.
- **Polish** vem depois das histórias entregues.
- Dentro de cada história: testes, confirmação de falha, implementação e verificação.
- T019 a T022 e T051 a T055 alteram arquivos em comum: execute em sequência.
- T065 precede T066 a T072.

## Parallel Opportunities

```text
# US2: renderizador e integração, em arquivos separados
T027, T028, T029, T030   tests/unit/notifications/test_submission_returned_email_renderer.py
T031 a T049              tests/integration/notifications/test_submission_returned_email.py

# US3: dois módulos de concorrência, depois de T065
T066 a T068              tests/integration/database/test_return_review_concurrency.py
T069 a T072              tests/integration/database/test_pre_evaluation_concurrency.py

# Polish: uma página por tarefa
T080 a T086
```

O `[P]` de tarefas no mesmo arquivo indica independência lógica. Quem editar em paralelo precisa combinar as mudanças nesse arquivo.

## Implementation Strategy

1. **MVP**: Setup e US1. Fecha a issue #73, o único bug de prioridade alta.
2. **Incremento**: US2 fecha o RF011.
3. **Incremento**: US3 corrige o reprocessamento e paga a dívida da Spec 030.
4. **Fechamento**: manual e suíte completa, no mesmo PR.

## Matriz de rastreabilidade

| Requisito | Testes |
|---|---|
| FR-001 | T002 |
| FR-002 | T004, T005, T006, T003 |
| FR-003 | T002, T016 |
| FR-004 | T008, T009 |
| FR-005 | T002, T012 |
| FR-006 | T013 |
| FR-007 | T014, T015 |
| FR-008 | T017 |
| FR-009 | T031, T032, T033, T035, T037, T041 |
| FR-010 | T025, T028 |
| FR-011 | T033, T038, T039 |
| FR-012 | T040 |
| FR-013 | T026, T043, T044, T049 |
| FR-013a | T043, T047, T048 |
| FR-014 | T031, T046 |
| FR-015 | T066, T067, T068 |
| FR-016 | T069, T070, T071, T072 |
| FR-016a | T058 a T064 |
| FR-017 | T076, T077, T087 |
| FR-018 | T080 a T086, T090 |

---

## Phase 6: Convergence

- [X] T092 Testar `test_malformed_notification_key_is_rejected` em `tests/unit/core/test_settings.py`: `NOTIFICATION_ENCRYPTION_KEY` que não é chave Fernet impede criar `Settings`, com erro que cita a variável e não repete o valor per SC-004 (partial)
- [X] T093 Testar `test_absent_notification_key_leaves_channel_unavailable` em `tests/unit/core/test_settings.py`: chave ausente ou vazia continua aceita em `Settings`, e `email_channel_available` responde falso per FR-012 (partial)
- [X] T094 Validar `NOTIFICATION_ENCRYPTION_KEY` com `field_validator` em `src/pivma/core/settings.py`, para a chave malformada barrar a inicialização em vez de lançar `ValueError` em `encrypt_payload` dentro de `open_return_review`, o que hoje responde `500` na triagem e deixa a `EvaluationRun` presa em `in_progress`, sem retorno, porque `_mark_failed` lança o mesmo erro per SC-004 (partial)
- [X] T095 Documentar em `manual/referencia/ambiente.md` e `manual/guias/operar-em-producao.md` que uma chave malformada impede a inicialização per FR-018 (partial)
- [X] T096 Trocar em `manual/explicacao/escopo.md` o estado `Atendido` do RF011, fora da legenda `Sim`, `Parcial` e `Não`, por `Parcial`, com o limite de que aprovação, rejeição e resultado positivo da IA não geram aviso, como diz a spec em Assumptions per FR-018 (contradicts)
- [X] T097 Trocar os atrasos fixos de `test_retry_and_contest_race_has_one_winner`, em `tests/integration/database/test_pre_evaluation_concurrency.py`, por um `asyncio.Event` acionado com a trava já obtida, para o reprocessamento começar sempre depois dela; hoje o teste falha se a contestação levar mais de 0,1 s até a trava, e continuar falhando sem o `FOR UPDATE` per FR-016 (partial)
- [X] T098 Repetir sobre o código final as 20 rodadas de T079, depois `poetry run poe lint`, `poetry run poe test` lendo o resultado do pytest e `poetry run poe docs-build`; T079 se sobrepôs à edição da fábrica, e T089 rodou `pytest` direto, sem a tarefa `poe test` per plan: Constitution Check (partial)
- [X] T099 Montar a tabela de cada FR com o teste que o prova para a descrição do PR, incluindo o que a matriz não lista: `test_timeline_does_not_identify_reviewer_to_proponent`, `test_timeline_keeps_return_author_for_bracvam` e `test_process_deletion_cancels_email_of_decided_return`; T091 está marcada como feita, mas não há PR nem tabela per Constitution II (partial)

---

## Phase 7: Pareceres em edição

Decisão do usuário em 2026-11-06, depois da convergência.

- [X] T100 Testar `test_version_hides_reviews_until_triage_decides` em `tests/api/routers/test_return_review.py`: depois de uma contestação, o parecer em edição não aparece na versão devolvida e aparece quando a triagem decide per SC-002 (partial)
- [X] T101 Em `submission_run_reviews`, em `src/pivma/core/process_engine.py`, ler só pareceres de execução da triagem concluída per FR-003 (partial)
- [X] T102 Registrar a decisão em `spec.md`, `research.md`, `contracts/submission-reviews.md`, `docs/observacoes-e-pendencias.md` e `manual/guias/enviar-uma-proposta.md` per FR-018 (partial)

---

## Rastreabilidade para o PR (T099)

| Requisito | Testes |
|---|---|
| FR-001 | `test_proponente_corrige_com_pareceres_e_consulta_cada_rodada` |
| FR-002 | `test_form_previous_reviews_empty_on_first_run`, `test_form_previous_reviews_empty_when_previous_run_has_no_reviews`, `test_form_previous_reviews_empty_for_other_activities`, `test_proponente_revisa_retorno_da_ia_sem_pareceres` |
| FR-003 | `test_proponente_corrige_com_pareceres_e_consulta_cada_rodada`, `test_versions_listing_has_no_reviews`, `test_version_hides_reviews_until_triage_decides` |
| FR-004 | `test_form_previous_reviews_keeps_removed_field`, `test_version_reviews_keeps_removed_field` |
| FR-005 | `test_proponente_corrige_com_pareceres_e_consulta_cada_rodada`, `test_triage_cannot_change_reviews_of_returned_run` |
| FR-006 | `test_reviews_responses_do_not_identify_reviewer`, `test_timeline_does_not_identify_reviewer_to_proponent`, `test_timeline_keeps_return_author_for_bracvam` |
| FR-007 | `test_stranger_gets_404_on_form_with_previous_reviews`, `test_stranger_gets_404_on_version_with_reviews` |
| FR-008 | `test_return_review_404_after_decision_with_reviews` |
| FR-009 | `test_triage_return_enqueues_one_email_with_subject_and_process`, `test_negative_ai_return_enqueues_email`, `test_failed_ai_return_enqueues_email_with_same_origin`, `test_revoked_proponent_gets_no_email`, `test_other_roles_get_no_email`, `test_rollback_of_return_discards_email` |
| FR-010 | `test_proponente_recebe_aviso_da_devolucao_pela_triagem_e_pela_ia`, `test_body_has_process_origin_deadline_and_guidance` |
| FR-011 | `test_failed_ai_return_enqueues_email_with_same_origin`, `test_delivered_email_hides_justification_reviews_and_reviewer`, `test_delivered_email_hides_ai_result` |
| FR-012 | `test_return_completes_without_email_channel`, `test_absent_notification_key_leaves_channel_unavailable` |
| FR-013 | `test_reprocessamento_cancela_aviso_pendente_e_nova_devolucao_avisa`, `test_retry_cancels_pending_email_and_records_event`, `test_retry_keeps_already_sent_email`, `test_process_deletion_cancels_pending_email`, `test_process_deletion_cancels_email_of_decided_return` |
| FR-013a | `test_retry_cancels_pending_email_and_records_event`, `test_retry_records_cancellation_with_admin_as_author`, `test_retry_new_run_keeps_original_creator` |
| FR-014 | `test_triage_return_enqueues_one_email_with_subject_and_process`, `test_sent_email_records_audit_event_with_subject` |
| FR-015 | `test_revise_and_withdraw_race_has_one_winner`, `test_double_revise_opens_one_submission_run`, `test_revise_and_contest_race_has_one_winner` |
| FR-016 | `test_double_retry_creates_one_run`, `test_retry_and_contest_race_has_one_winner`, `test_execute_and_retry_race_keeps_one_result`, `test_execute_and_contest_race_keeps_one_result` |
| FR-016a | `test_retry_in_progress_run_is_conflict`, `test_retry_older_failed_run_is_conflict`, `test_retry_after_revise_is_conflict`, `test_retry_after_contest_is_conflict`, `test_retry_after_contest_and_triage_return_is_conflict`, `test_retry_completed_run_is_conflict`, `test_rejected_retry_leaves_no_partial_effect` |
| FR-017 | `grep -rn "TODO(spec-030)" src` sem resultado |
| FR-018 | `poe docs-build` |
| SC-004 | `test_malformed_notification_key_is_rejected`, `test_return_completes_without_email_channel`, `test_permanent_delivery_failure_keeps_return_open` |
