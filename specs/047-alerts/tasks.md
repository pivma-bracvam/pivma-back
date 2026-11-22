---

description: "Lista de tarefas da Spec 047"
---

# Tasks: Alerts na plataforma

**Input**: artefatos em `specs/047-alerts/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/alerts-api.md](contracts/alerts-api.md), [quickstart.md](quickstart.md)

**Tests**: obrigatórios (`AGENTS.md`, constituição V). Cada tarefa de teste cobre um comportamento. Em cada história, escreva os testes primeiro e confirme que falham pelo motivo esperado antes de implementar. Carregue `testing-methodology` antes das tarefas de teste e `karpathy-guidelines` antes das tarefas de código.

**Organization**: uma fase por história. A US2 (caixa) vem antes da US1 (tarefa nova) porque os testes da US1 leem os alerts por `GET /alerts`. A jornada da US2 fica no fim da fase da US1, porque precisa de alerts gerados por uma ação real.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo: arquivo diferente e sem dependência de tarefa incompleta
- **[Story]**: história da spec (US1 a US6)

## Convenções

- As jornadas descrevem na docstring do módulo o ator, o objetivo e a origem (Spec 047 e história), numeram os passos em comentários e usam só a API pública, a partir de `bootstrap_fresh_deploy`. A exceção é `pre_evaluation_service._execute` e `_mark_failed`, que não têm rota pública.
- Use os helpers de `tests/integration/journeys/conftest.py` (`sign_up`, `log_in`, `log_out`, `make_bracvam`, `process_tasks`, `journey_client`) e de `sample_steps.py` (`study_team`, `designate`, `complete_study_team`, `approve_structure`).
- Nos testes focados de API, verifique o `code` do erro, não a mensagem.
- Para conferir parâmetros, compare o conjunto de chaves de `params` com a lista de [data-model.md](data-model.md#parâmetros-por-tipo), e não só a presença de uma chave.
- Nenhuma tarefa altera a fila de e-mail (`notifications`) nem os e-mails existentes.

---

## Phase 1: Setup

- [X] T001 Confirmar a base: rodar `poetry run pytest tests/api/routers/test_tasks*.py tests/integration/journeys/etapa_1_submissao_triagem` em `develop` e anotar o resultado em `specs/047-alerts/tasks.md` (seção Notas), para comparar depois de mover a regra de `can_act`

- [X] T002 Obter da equipe a decisão sobre o alcance dos alerts do BraCVAM (research R13, `docs/observacoes-e-pendencias.md`, seção "Alerts na plataforma"), antes de T058. Sem decisão, T058 segue a regra de `can_act`, que é o comportamento confirmado

---

## Phase 2: Foundational (bloqueia todas as histórias)

**Objetivo**: tabela, modelo e a função que grava alerts na sessão.

### Testes da base

- [X] T003 [P] Teste de migração em `tests/integration/migrations/test_alerts_migration.py`: `upgrade` cria `alerts` com as colunas de [data-model.md](data-model.md), a FK para `users.id` e `process_instances.id`, a restrição "`target_type = 'process'` se, e somente se, `target_id` for nulo", `ix_alerts_user_created` em `(user_id, created_at DESC)` e `ix_alerts_user_unread` em `(user_id) WHERE read_at IS NULL`; `downgrade` remove tudo
- [X] T004 [P] Teste em `tests/integration/database/test_alert_service.py`: `add_alerts` com o mesmo usuário duas vezes na lista grava um só alert (FR-005)
- [X] T005 [P] Teste em `tests/integration/database/test_alert_service.py`: `add_alerts` não grava alert para o `actor_id` mesmo quando ele está na lista (FR-006)
- [X] T006 [P] Teste em `tests/integration/database/test_alert_service.py`: `add_alerts` não grava alert para usuário com `deleted_at` preenchido (FR-004, research R7)
- [X] T007 [P] Teste em `tests/integration/database/test_alert_service.py`: depois de `add_alerts` e `rollback` da sessão, nenhum alert fica gravado (FR-003, SC-004)
- [X] T008 [P] Teste em `tests/integration/database/test_alert_service.py`: `add_alerts` com `actor_id=None` grava `created_by` nulo; com autor, grava o autor (research R11)

### Implementação da base

- [X] T009 Modelo `Alert(AuditMixin)` em `src/pivma/core/database/models.py`, tabela `alerts`: `id` UUID; `user_id` FK `users.id` obrigatório; `kind` `String(64)`; `target_type` `String(32)` ("`process`, `task` ou `sample_receipt`"); `process_instance_id` FK `process_instances.id` obrigatório; `target_id` UUID nulo ("Nulo em `process`"); `params` JSONB "Nunca nulo; `{}` quando o tipo não tem parâmetro além do processo"; `read_at` nulo; os dois índices e a restrição de verificação de T003
- [X] T010 Migração `migrations/versions/<rev>_alerts.py` com `down_revision = 'c4e6a8b0d2f1'`, revisada à mão, com `upgrade` e `downgrade` (depende de T009)
- [X] T011 `src/pivma/core/alert_service.py` com as constantes dos dez tipos e dos três `target_type`, e `add_alerts(session, *, kind, user_ids, process_id, target_type, target_id, params, actor_id)`: junta os ids em `set`, tira `actor_id`, filtra contas ativas em uma consulta, cria um `Alert` por id com `set_creation_audit(actor_id)` e não comita (research R6, R7, R11)
- [X] T012 [P] Factory `tests/factories/alert_factory.py` que cria um `Alert` para um usuário e um processo, com `kind`, `target_type`, `target_id`, `params`, `read_at` e `created_at` opcionais

**Checkpoint**: T003 a T008 verdes.

---

## Phase 3: User Story 2 - Ler e limpar a caixa de alerts (Priority: P1) 🎯 MVP

**Goal**: o usuário lista os próprios alerts, vê o contador de não lidos e marca um ou todos como lidos.

**Independent Test**: criar três alerts por factory, listar, marcar um, marcar todos e conferir o contador em cada passo.

### Testes focados da US2 (contrato)

- [X] T013 [P] [US2] `tests/api/routers/test_alerts_router.py`: `GET /alerts` devolve só os alerts do usuário da sessão, do mais recente para o mais antigo, com `sort = {"by": "created_at", "order": "desc"}`
- [X] T014 [P] [US2] `tests/api/routers/test_alerts_router.py`: dois alerts com o mesmo `created_at` saem por `id` decrescente (research R8)
- [X] T015 [P] [US2] `tests/api/routers/test_alerts_router.py`: `unread=true` devolve só os não lidos e `filters_applied.unread = true`
- [X] T016 [P] [US2] `tests/api/routers/test_alerts_router.py`: `unread=false` devolve só os lidos
- [X] T017 [P] [US2] `tests/api/routers/test_alerts_router.py`: `unread_count` é o total de não lidos do usuário, igual com `unread=false`, `per_page=1` e `page=2` (FR-013, SC-003)
- [X] T018 [P] [US2] `tests/api/routers/test_alerts_router.py`: com 25 alerts e `per_page=10`, a página 3 traz 5 itens e `pagination` coerente (`total_items=25`, `total_pages=3`, `has_next=false`)
- [X] T019 [P] [US2] `tests/api/routers/test_alerts_router.py`: página além da última devolve `data = []` e o `unread_count` correto
- [X] T020 [P] [US2] `tests/api/routers/test_alerts_router.py`: usuário sem alerts recebe `data = []` e `unread_count = 0`
- [X] T021 [P] [US2] `tests/api/routers/test_alerts_router.py`: item com `target_type = 'process'` sai com `target.id = null`, e item `task` sai com `target.process_id` e `target.id` (contrato)
- [X] T022 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/{id}/read` preenche `read_at`, devolve o alert e o `unread_count` seguinte cai 1 (FR-014)
- [X] T023 [P] [US2] `tests/api/routers/test_alerts_router.py`: marcar de novo um alert lido responde `200` e mantém o `read_at` original (FR-014)
- [X] T024 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/{id}/read` com alert de outro usuário responde `404 not_found` e não muda o alert (FR-016)
- [X] T025 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/{id}/read` com id inexistente responde `404 not_found`
- [X] T026 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/{id}/read` com id que não é UUID responde `422 validation_error`
- [X] T027 [P] [US2] `tests/api/routers/test_alerts_router.py`: `GET /alerts` com `per_page=101` responde `422 validation_error`
- [X] T028 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/read-all` marca todos os não lidos do usuário, responde `{"updated": n}` e não mexe nos alerts de outro usuário (FR-015)
- [X] T029 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/read-all` sem não lidos responde `{"updated": 0}`
- [X] T030 [P] [US2] `tests/api/routers/test_alerts_router.py`: `GET /alerts` sem sessão responde `401 not_authenticated` (FR-017)
- [X] T031 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/{id}/read` e `POST /alerts/read-all` sem sessão respondem `401 not_authenticated` (FR-017)
- [X] T032 [P] [US2] `tests/api/routers/test_alerts_router.py`: `POST /alerts/{id}/read` e `POST /alerts/read-all` com cookie e origem fora de `AUTH_ALLOWED_ORIGINS` respondem `403 invalid_origin` (FR-017)
- [X] T033 [P] [US2] `tests/api/routers/test_alerts_router.py`: marcar como lido não grava `AuditEvent` e não muda a tarefa do destino (FR-019)
- [X] T034 [P] [US2] `tests/api/routers/test_alerts_concurrency.py`: duas chamadas simultâneas de `POST /alerts/read-all` terminam em `200`, a soma de `updated` é o total inicial de não lidos e o `unread_count` final é 0
- [X] T035 [P] [US2] `tests/api/routers/test_alerts_concurrency.py`: `POST /alerts/{id}/read` e `POST /alerts/read-all` simultâneos terminam em `200`, e o alert fica com um único `read_at`

### Implementação da US2

- [X] T036 [US2] Schemas em `src/pivma/schemas.py`: `AlertTarget` (`type`, `process_id`, `id` nulo), `AlertItem` (`id`, `kind`, `target`, `params`, `read_at`, `created_at`), `AlertFilters` (`unread: bool | None`), `AlertListResponse(ListPage[AlertItem, AlertFilters])` com `unread_count: int`, `AlertReadAllResponse` (`updated: int`)
- [X] T037 [US2] Leitura em `src/pivma/core/alert_service.py`: `list_alerts` com `paginate_query` e ordem `created_at DESC, id DESC`; `unread_count`; `mark_read` e `mark_all_read` com `UPDATE ... WHERE user_id = :me AND read_at IS NULL`, preenchendo `updated_by` (research R9)
- [X] T038 [US2] Rotas em `src/pivma/routers/alerts.py`: `GET /alerts` (`CurrentUser`, `PageQuery`, `PerPageQuery`, `unread`), `POST /alerts/read-all` declarada antes de `POST /alerts/{alert_id}/read`, ambas com `TrustedOrigin`; `404 not_found` pelo `http_error` do projeto
- [X] T039 [US2] Registrar `alerts.router` em `src/pivma/__init__.py`

**Checkpoint**: T013 a T035 verdes.

---

## Phase 4: User Story 1 - Saber que há uma tarefa nova para mim (Priority: P1)

**Goal**: cada usuário que pode agir em uma tarefa nova recebe um alert `task_opened` com destino na tarefa.

**Independent Test**: enviar uma proposta, rodar a pré-avaliação positiva e conferir o alert de triagem de cada pessoa do BraCVAM, sem alert para o proponente.

### Jornada da US1

- [X] T040 [US1] Jornada em `tests/integration/journeys/etapa_1_submissao_triagem/test_alerts_task_journey.py`: (1) o proponente cria e envia a proposta e não tem alert; (2) a IA aprova e cada uma de duas pessoas do BraCVAM vê um `task_opened` não lido de `triage_evaluation`, com `target.type = "task"`; (3) a primeira abre a tarefa pelo `target`, marca o alert como lido e pede revisão; (4) ela não recebe alert novo, e o proponente vê um `task_opened` de `submission_return_review`, sem justificativa, parecer nem nome do triador; (5) a segunda pessoa do BraCVAM continua com o alert de triagem, lido ou não como estava (FR-020)

### Testes focados da US1

- [X] T041 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: a tarefa de triagem gera um alert por pessoa do BraCVAM, com `params` exatamente `process_code`, `process_title`, `activity_key`, `activity_name`, `run_number`, `due_date` (FR-010)
- [X] T042 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: o proponente que cria o processo não recebe alert de `proposal_submission` (FR-006)
- [X] T043 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: a pessoa do BraCVAM que conclui uma designação e libera a seguinte não recebe alert, e a colega recebe (US1, cenário 5)
- [X] T044 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: na devolução pela IA com resultado negativo, o proponente recebe `task_opened` de `submission_return_review` com `created_by` nulo (research R5)
- [X] T045 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: na devolução pela falha da IA, o proponente recebe o mesmo alert, com as mesmas chaves de `params` do T044 (Edge Cases)
- [X] T046 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: um proponente que também tem o perfil BraCVAM recebe o alert da triagem aberta pela IA (research R5)
- [X] T047 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: um usuário com dois cargos que podem agir na tarefa recebe um só alert (FR-005)
- [X] T048 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: usuário com conta desativada não recebe alert da tarefa (FR-004)
- [X] T049 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: atividade reaberta gera novo alert com `run_number = 2` para quem pode agir (Edge Cases)
- [X] T050 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: a tarefa criada já cancelada na dispensa de laboratório não gera `task_opened` (research R4)
- [X] T051 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: concluir a tarefa não muda `read_at` nem a quantidade de alerts dela (FR-020)
- [X] T052 [P] [US1] `tests/api/routers/test_alerts_task_opened.py`: o problema no recebimento abre a resolução e os designados do Grupo de Seleção de Amostras recebem `task_opened`, com destino na tarefa e sem segundo alert para o mesmo acontecimento (FR-011)
- [X] T053 [P] [US1] `tests/api/routers/test_alerts_security.py`: em atividade por laboratório com A e B, os designados por A recebem só o alert da execução de A, com `laboratory_name` de A, e os de B só o de B (SC-002)
- [X] T054 [P] [US1] `tests/api/routers/test_alerts_security.py`: usuário com conflito de interesse vigente no processo não recebe alert da tarefa que o cargo dele executaria (US1, cenário 4)
- [X] T055 [P] [US1] `tests/api/routers/test_alerts_security.py`: o destinatário de cada `task_opened` em uma jornada até a homologação é exatamente quem vê a tarefa com `can_act = true` em `GET /tasks` (SC-001)
- [X] T056 [P] [US1] `tests/api/routers/test_alerts_security.py`: depois de revogada a designação, o alert continua na lista e `GET /tasks/{target.id}` responde `404 not_found` (FR-018, Edge Cases)

### Implementação da US1

- [X] T057 [US1] Mover `_can_act_clause` de `src/pivma/routers/tasks.py` para `src/pivma/core/authorization.py` como `task_can_act_clause`, sem mudar o conteúdo, e importar em `routers/tasks.py`; rodar de novo os testes de T001 e comparar (research R3)
- [X] T058 [US1] Em `src/pivma/core/alert_service.py`, `alert_task_opened(session, task, actor_id)`: candidatos pelas designações ativas do processo e pelos perfis globais cujo cargo esteja em `edit_roles`; uma consulta por candidato com `task_can_act_clause` contra a tarefa; `params` de [data-model.md](data-model.md#parâmetros-por-tipo), com `laboratory_name` só em execução por laboratório; chama `add_alerts` (research R3)
- [X] T059 [US1] Chamar `alert_task_opened` depois do `flush` de cada tarefa `READY` em `src/pivma/core/process_engine.py`: `_init_first_activity`, `_activate_activity`, `_start_laboratory_run`, `_open_new_submission_run` e `open_return_review` (este sempre com `actor_id=None`) (research R4, R5)
- [X] T060 [US1] Chamar `alert_task_opened` em `_open_resolution_run` de `src/pivma/core/sample_receipt_service.py` (research R4)
- [X] T061 [US1] Argumento nomeado `alert_actor_id` em `_advance_dependent_activities` e `_activate_activity` de `src/pivma/core/process_engine.py`, repassado a `alert_task_opened`, com padrão igual a `user_id` para que os oito chamadores humanos não mudem; só as duas chamadas de `src/pivma/core/pre_evaluation_service.py` (resultado positivo e reprocessamento) passam `alert_actor_id=None` (research R5)

### Jornada da US2 (depende da geração da US1)

- [X] T062 [US2] Jornada em `tests/integration/journeys/etapa_1_submissao_triagem/test_alerts_inbox_journey.py`, contando só alerts `task_opened` das pessoas do BraCVAM, para não mudar quando a US3 entrar: (1) a IA aprova duas propostas, e cada uma de duas pessoas do BraCVAM, A e B, vê dois `task_opened` de triagem e `unread_count = 2`; (2) A pede revisão na primeira proposta e não ganha alert novo, e o contador dela segue 2; (3) A filtra os não lidos e recebe os dois; (4) A marca um como lido e o contador vai a 1; (5) A marca todos, recebe `{"updated": 1}` e o contador vai a 0; (6) B continua com `unread_count = 2`; (7) B tenta marcar um alert de A e recebe `404`

**Checkpoint**: MVP pronto. US1 e US2 verdes e os testes de T001 iguais ao resultado inicial.

---

## Phase 5: User Story 3 - Acompanhar a decisão sobre a minha submissão (Priority: P2)

**Goal**: o proponente recebe `submission_status_changed` na aprovação da IA e na decisão da triagem, e `structure_approved` na homologação, junto dos participantes.

**Independent Test**: levar uma proposta até a homologação e conferir os alerts do proponente em cada decisão.

### Jornada da US3

- [X] T063 [US3] Jornada em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_alerts_proponent_decisions_journey.py`: (1) a IA aprova e o proponente vê `submission_status_changed` com `status = "in_triage"`; (2) a triagem aprova e ele vê `status = "approved"`; (3) a equipe se forma, o BraCVAM homologa a estrutura e o proponente e o estatístico veem `structure_approved` com destino no processo

### Testes focados da US3

- [X] T064 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: a triagem rejeita e o proponente recebe `status = "rejected"`, com `params` exatamente `process_code`, `process_title`, `status` (FR-009)
- [X] T065 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: a triagem pede revisão e o proponente recebe só o `task_opened` do retorno, sem `submission_status_changed` (FR-011)
- [X] T066 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: proponente com conta desativada não recebe alert da decisão (US3, cenário 4)
- [X] T067 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: `submission_status_changed` da IA sai com `created_by` nulo e chega ao proponente (research R5)
- [X] T068 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: `structure_approved` não chega a designação revogada nem a designação sem efetividade
- [X] T069 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: a rejeição da estrutura não gera `structure_approved`, e as atividades reabertas chegam como `task_opened` (FR-011)
- [X] T070 [P] [US3] `tests/api/routers/test_alerts_decisions.py`: a pessoa do BraCVAM que homologa não recebe `structure_approved` (FR-006)

### Implementação da US3

- [X] T071 [US3] Em `src/pivma/core/alert_service.py`, `participant_user_ids(session, process_id, *, role_keys=None, exclude_role_keys=(), laboratory_id=None, effective=True)` com designações ativas, `effective_assignment_clause()` quando `effective` e conta ativa (data-model, Destinatários)
- [X] T072 [US3] `submission_status_changed` no ramo positivo de `src/pivma/core/pre_evaluation_service.py` (`in_triage`, `actor_id=None`) e nas decisões `TRIAGE_APPROVED` e `TRIAGE_REJECTED` de `src/pivma/core/process_engine.py`
- [X] T073 [US3] `structure_approved` no ramo `APPROVED` de `src/pivma/core/structure_approval_service.py`, para proponentes e demais designações ativas e efetivas

---

## Phase 6: User Story 4 - Saber das minhas designações (Priority: P2)

**Goal**: o designado recebe alert quando é designado diretamente, revogado ou quando a designação perde ou recupera a efetividade.

**Independent Test**: designar um usuário, revogar e conferir os dois alerts dele.

### Jornada da US4

- [X] T074 [US4] Jornada em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_alerts_assignments_journey.py`: (1) o BraCVAM designa um estatístico e ele vê `assignment_created` com `role_key = "statistician"`; (2) o BraCVAM revoga e ele vê `assignment_revoked`; (3) o BraCVAM não recebe alert das próprias ações

### Testes focados da US4

- [X] T075 [P] [US4] `tests/api/routers/test_alerts_assignments.py`: o usuário que aceita convite de designação não recebe `assignment_created` (US4, cenário 2)
- [X] T076 [P] [US4] `tests/api/routers/test_alerts_assignments.py`: designação por laboratório traz `laboratory_name`, e designação sem laboratório traz `laboratory_name = null`
- [X] T077 [P] [US4] `tests/api/routers/test_alerts_assignments.py`: o fim do vínculo com o laboratório gera `assignment_effectiveness_changed` com `effective = false` para o designado
- [X] T078 [P] [US4] `tests/api/routers/test_alerts_assignments.py`: a volta do vínculo gera `assignment_effectiveness_changed` com `effective = true`

### Implementação da US4

- [X] T079 [US4] `assignment_created` em `create_assignment` de `src/pivma/core/participant_service.py`, para `user_id` da designação, com `actor_id` da chamada
- [X] T080 [US4] `assignment_revoked` junto do evento `PARTICIPANT_REVOKED` em `src/pivma/routers/process_participants.py`
- [X] T081 [US4] `assignment_effectiveness_changed` em `record_laboratory_validity_changes` de `src/pivma/core/participant_service.py`, um alert por designação que mudou

---

## Phase 7: User Story 5 - Acompanhar a execução nos laboratórios (Priority: P3)

**Goal**: Grupo Gestor e Gerente do Estudo sabem da conclusão; o laboratório sabe da dispensa e da decisão sobre o frasco.

**Independent Test**: concluir a execução de A, dispensar a de B e decidir um problema de A, conferindo os alerts de cada parte.

### Jornada da US5

- [X] T082 [US5] Jornada em `tests/integration/journeys/etapa_3_execucao_validacao/test_alerts_laboratories_journey.py`: (1) o laboratório A relata problema em um frasco; (2) o Grupo decide e os designados por A veem `sample_nonconformity_decided` com destino no frasco; (3) A conclui a execução e o Grupo Gestor vê `laboratory_run_completed`; (4) o Grupo Gestor dispensa B e os designados por B veem `laboratory_run_waived`; (5) nenhum alert de A fala de B, e nenhum de B fala de A

### Testes focados da US5

- [X] T083 [P] [US5] `tests/api/routers/test_alerts_security.py`: `sample_nonconformity_decided` tem `params` exatamente `process_code`, `process_title`, `laboratory_name`, `blind_code`, `vial_status`, sem orientação, justificativa, código do frasco novo, nome químico, CAS ou SDS (SC-002)
- [X] T084 [P] [US5] `tests/api/routers/test_alerts_laboratories.py`: decisão de dois frascos gera um alert por frasco para cada designado do laboratório
- [X] T085 [P] [US5] `tests/api/routers/test_alerts_laboratories.py`: `laboratory_run_completed` chega a `group_manager` e `study_manager` com designação efetiva, e não chega aos laboratórios
- [X] T086 [P] [US5] `tests/api/routers/test_alerts_laboratories.py`: `laboratory_run_waived` chega só aos designados do laboratório dispensado

### Implementação da US5

- [X] T087 [US5] `laboratory_run_completed` e `laboratory_run_waived` junto dos eventos `LABORATORY_RUN_COMPLETED` e `LABORATORY_WAIVED` em `src/pivma/core/process_engine.py`
- [X] T088 [US5] `sample_nonconformity_decided` em `decide_nonconformity` de `src/pivma/core/sample_receipt_service.py`, um por frasco decidido, com `target_type = 'sample_receipt'` e `target_id` do frasco. A chamada fica fora de `_notify_laboratory`, que retorna cedo quando `email_channel_available` é falso (FR-007; prova em T093)

---

## Phase 8: User Story 6 - Saber da desistência do proponente (Priority: P3)

**Goal**: BraCVAM e participantes sabem quando o proponente desiste.

**Independent Test**: devolver uma submissão, desistir como proponente e conferir os alerts do BraCVAM.

### Jornada da US6

- [X] T089 [US6] Jornada em `tests/integration/journeys/etapa_1_submissao_triagem/test_alerts_withdrawal_journey.py`: (1) a triagem devolve a submissão; (2) o proponente desiste; (3) cada pessoa do BraCVAM vê `process_withdrawn` com destino no processo; (4) o proponente não recebe

### Testes focados da US6

- [X] T090 [P] [US6] `tests/api/routers/test_alerts_decisions.py`: participante com designação ativa no processo recebe `process_withdrawn`, e designação revogada não recebe

### Implementação da US6

- [X] T091 [US6] `process_withdrawn` junto do evento `PROCESS_WITHDRAWN` em `src/pivma/core/return_review_service.py`, para o perfil `bracvam` ativo e as designações ativas fora `proponent`

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T092 [P] Teste em `tests/api/routers/test_alerts_security.py`: nenhum alert gerado nas jornadas tem chave fora da lista do seu tipo em [data-model.md](data-model.md#parâmetros-por-tipo) (SC-002, research R12)
- [ ] T093 [P] Teste em `tests/api/routers/test_alerts_security.py`: sem `NOTIFICATION_EMAIL_BACKEND`, a devolução gera `task_opened` e a decisão sobre o frasco gera `sample_nonconformity_decided`, sem criar linhas em `notifications` (FR-007)
- [ ] T094 [P] Página `manual/explicacao/alertas.md` (com `stop-slop`): diferença para o e-mail, tipos, destinatários, destino e o que os parâmetros nunca trazem; incluir no `nav` de `mkdocs.yml`
- [ ] T095 [P] Rotas em `manual/referencia/rotas.md` e erros novos, se houver, em `manual/referencia/erros.md`
- [ ] T096 [P] Tipos de alert por gatilho em `manual/referencia/eventos.md`
- [ ] T097 [P] RF011 e RF033 em `manual/explicacao/escopo.md`, e link para a página de alerts em `manual/explicacao/notificacoes.md` e `manual/guias/acompanhar-tarefas.md`
- [ ] T098 Rodar o [quickstart.md](quickstart.md) e corrigir o que divergir
- [ ] T099 `poe lint`, `poe test` e `poe docs-build` verdes; informar só o que rodou
- [ ] T100 Conferir que a decisão sobre o alcance do BraCVAM (T002) está aplicada em `alert_service.py` e registrada em `docs/observacoes-e-pendencias.md`

---

## Dependencies & Execution Order

- **Setup (T001, T002)** antes de tudo. T002 precisa estar resolvida antes de T058.
- **Foundational (T003 a T012)** bloqueia todas as histórias. T010 depende de T009.
- **US2 (T013 a T039)** depende da base. Os testes usam a factory.
- **US1 (T040 a T061)** depende da base e das rotas da US2. T057 vem antes de T058; T058 antes de T059 a T061.
- **Jornada da US2 (T062)** depende de T059 e T061.
- **US3 a US6** dependem de US1 e US2. T071 serve a US3, US5 e US6, então vem antes delas. Entre si, US3 a US6 são independentes.
- **Polish** depois das histórias que quiser entregar.

## Parallel Opportunities

- T003 a T008 e T012 em paralelo, depois de T009 para os testes de serviço.
- Todos os testes focados de uma história marcados [P] em paralelo, antes da implementação.
- Depois de T071, as fases de US3, US4, US5 e US6 podem seguir em paralelo, por tocarem arquivos de serviço diferentes, com cuidado em `process_engine.py` (US3 e US5).
- T094 a T097 em paralelo.

## Implementation Strategy

1. **MVP**: base, US2 e US1 (até T062). O front já mostra a caixa, o contador e a tarefa nova.
2. **Incremento 2**: US3 e US4, avisos de decisão e designação.
3. **Incremento 3**: US5 e US6.
4. Polish e manual no mesmo PR de cada incremento entregue (constituição VII).

## Matriz de rastreabilidade

| Requisito | Testes | Implementação |
|---|---|---|
| FR-001, FR-010 | T041, T063, T064, T074, T082, T089 | T058, T072, T073, T079 a T081, T087, T088, T091 |
| FR-002, FR-008 | T003, T021 | T009, T010, T036 |
| FR-003 | T007 | T011 |
| FR-004 | T006, T048, T066 | T011 |
| FR-005 | T004, T047 | T011 |
| FR-006 | T005, T042, T043, T070, T075 | T011, T061 |
| FR-007 | T093 | T088 |
| FR-009 | T040, T064, T083, T092 | T058, T088 |
| FR-011 | T052, T065, T069 | T059, T060 |
| FR-012 | T013 a T016, T018, T019 | T037, T038 |
| FR-013 | T017 | T037 |
| FR-014 | T022, T023, T035 | T037 |
| FR-015 | T028, T029, T034 | T037 |
| FR-016 | T024 | T037 |
| FR-017 | T030 a T032 | T038 |
| FR-018 | T056 | — |
| FR-019 | T033 | T037 |
| FR-020 | T040, T051 | — |
| SC-001 | T055 | T057, T058 |
| SC-002 | T053, T083, T092 | T058, T088 |
| SC-003 | T017, T062 | T037 |
| SC-004 | T007 | T011 |
| SC-005 | T018 | T037 |

## Notas

- T001: em `develop` + spec, `pytest tests/api/routers/test_tasks*.py tests/integration/journeys/etapa_1_submissao_triagem` deu 92 passed. Depois de mover a regra (T057), o mesmo comando deu 92 passed.
- T002: sem decisão da equipe até a implementação do MVP. `alert_task_opened` segue a regra de `can_act` (research R13).
- T061: o argumento ficou `automatic: bool = False` em `_activate_activity` e `_advance_dependent_activities`, em vez de `alert_actor_id`. O efeito é o mesmo (autor nulo só na liberação feita pela IA) e os oito chamadores humanos não mudam. Só a chamada do resultado positivo em `pre_evaluation_service` passa `automatic=True`; `request_direct_review` é ação do proponente e mantém o autor.
- T040 e T062: sem avaliação por IA associada, a proposta enviada vai direto para a triagem, então as jornadas não rodam a IA. A abertura da triagem pela IA está em T046.
- T043: a aprovação da triagem pela pessoa do BraCVAM é a ação que libera as designações da Fase 2, então serve de exemplo do cenário 5.
- T050: a dispensa também abre a devolução do material do laboratório dispensado, que gera `task_opened`, e cancela o recebimento já aberto, cujo alert continua (FR-020). O teste confere só as tarefas que já nascem canceladas.
- Suíte completa: a FK `alerts.process_instance_id` impedia as rotinas de limpeza dos testes de concorrência de apagar os processos que elas commitam, e os processos que sobravam colidiam no código único com os testes seguintes (63 falhas só na suíte inteira). As sete rotinas passaram a apagar `alerts` antes do processo, como já faziam com `notifications`. Em `develop`, a suíte completa deu 2291 passed.
- T087: a dispensa vale para o laboratório na fase inteira e pode cobrir várias atividades de uma vez. O alert sai um por dispensa, com `phase_name` no lugar de `activity_name`; spec (FR-010) e data-model foram ajustados.
- T082: o descarte do frasco dispensa o laboratório sozinho, então a jornada usa o aceite com ressalva antes da dispensa manual. Com o aceite, o lote de A também fecha, e o Grupo Gestor recebe uma conclusão por laboratório.
- T084: uma decisão vale para todos os frascos do lote com problema; o teste decide uma vez e confere um alert por frasco.
- T068: a homologação exige a equipe completa, então o teste usa pessoas extras para a designação revogada e para a sem efetividade.
