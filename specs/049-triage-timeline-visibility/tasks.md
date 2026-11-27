---
description: "Tarefas da Spec 049, visibilidade da triagem e cegamento na linha do tempo"
---

# Tasks: Visibilidade da triagem e cegamento na linha do tempo

**Input**: documentos de `specs/049-triage-timeline-visibility/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/timeline-and-form.md](contracts/timeline-and-form.md), [quickstart.md](quickstart.md)

**Tests**: obrigatórios (AGENTS.md, constituição V, skill `testing-methodology`). A feature é de risco **crítico** (autorização, cegamento, isolamento por laboratório), então cada história tem jornada, um teste de contrato por perfil negado e por resultado distinto, regressão do comportamento que precisa continuar, e teste da migração. Os testes de cada história vêm antes da implementação dela e devem falhar antes dela. Nas asserções de "não identifica", verifique que o `id` da pessoa não aparece em `response.text`, como em `test_timeline_does_not_identify_reviewer_to_proponent` (`tests/api/routers/test_return_review.py`), além de `user_id is None` no evento.

**Organization**: US1, US3 e US4 são P1 e mexem em `_visible_events` e `get_process_timeline` (`src/pivma/routers/processes.py`), então a implementação delas é sequencial. US2 (P2) mexe só em `src/pivma/routers/forms.py` e pode correr em paralelo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: história de origem (US1 a US4)

## Path Conventions

- Código: `src/pivma/`; migrações: `migrations/versions/`; testes: `tests/` (camadas em `.agents/skills/testing-methodology/references/06-projeto-pivma.md`).

---

## Phase 1: Setup

**Purpose**: registrar a linha de base antes de mudar o contrato.

- [X] T001 Rodar `poetry run pytest tests/api/routers/test_timeline_router.py tests/api/routers/test_participant_timeline.py tests/api/routers/test_return_review.py tests/integration/journeys/etapa_1_submissao_triagem tests/integration/database/test_activity_access_columns.py` e anotar no PR o resultado (todos verdes esperados em `feat/047-sponsor-tracking`, commit `abe9eed`).

---

## Phase 2: Foundational

Sem tarefa bloqueante: nenhuma tabela, coluna ou helper compartilhado novo. Cada história traz o que precisa.

---

## Phase 3: User Story 1 - O proponente acompanha a triagem (Priority: P1) 🎯 MVP

**Goal**: o proponente vê a tarefa de triagem e as decisões com justificativa, sem saber quem avaliou (FR-001 a FR-005, FR-010).

**Independent Test**: enviar uma submissão, decidir a triagem como BraCVAM e conferir, como proponente, `GET /tasks` e `GET /processes/{id}/timeline`.

### Tests for User Story 1

- [X] T002 [US1] Jornada em `tests/integration/journeys/etapa_1_submissao_triagem/test_proponent_triage_view.py` (docstring "Spec 049, US1"; helpers de `tests/integration/journeys/conftest.py`: `bootstrap_fresh_deploy`, `sign_up`, `log_in`, `log_out`, `make_bracvam`, `process_tasks`). Passos: (1) o proponente cria o processo `pre_validated_method` e envia a submissão; (2) o proponente vê a tarefa `triage_evaluation` em `READY` com `can_act == false` e não a vê com `actionable=true`; (3) o triador salva um parecer por campo (`POST /processes/{id}/triage/reviews`) e aprova; (4) o proponente vê a tarefa em `COMPLETED`, recebe `TRIAGE_APPROVED` com `context_data['justification']` e `user_id is None`, não recebe `FIELD_REVIEWED`, e o `id` do triador não aparece em `response.text` da linha do tempo.
- [X] T003 [P] [US1] Contrato em `tests/api/routers/test_triage_proponent_view.py`: depois de `REJECTED`, o proponente recebe `TRIAGE_REJECTED` com a justificativa, `user_id is None`, e o `id` do triador fora de `response.text`.
- [X] T004 [P] [US1] Contrato em `tests/api/routers/test_triage_proponent_view.py`: depois de `NEEDS_REVISION`, o proponente recebe `REVISION_REQUESTED` com a justificativa e `user_id is None`, e `RETURN_REVIEW_OPENED` continua com `user_id is None`.
- [X] T005 [P] [US1] Contrato em `tests/api/routers/test_triage_proponent_view.py`: com pareceres salvos, a linha do tempo do proponente não tem `FIELD_REVIEWED`, e `pagination.total_items` é igual ao número de eventos devolvidos com `per_page=100` (FR-009).
- [X] T006 [P] [US1] Contrato em `tests/api/routers/test_triage_proponent_view.py`: o proponente recebe `403` em `POST /processes/{id}/triage/reviews`, verificando o `code` do erro.
- [X] T007 [P] [US1] Contrato em `tests/api/routers/test_triage_proponent_view.py`: o proponente recebe `403` em `POST /processes/{id}/triage/decision`, e o processo continua sem decisão de triagem.
- [X] T008 [P] [US1] Regressão em `tests/api/routers/test_triage_proponent_view.py`: o BraCVAM recebe `TRIAGE_APPROVED`, `TRIAGE_REJECTED` e `REVISION_REQUESTED` com `user_id` igual ao do triador e recebe `FIELD_REVIEWED` (SC-005). Um teste por tipo de decisão.
- [X] T009 [P] [US1] Contrato em `tests/api/routers/test_triage_proponent_view.py`: proponente que também tem `triage.review` (perfil BraCVAM concedido) recebe o `user_id` do triador em `TRIAGE_APPROVED` (edge case).
- [X] T010 [P] [US1] Regressão em `tests/api/routers/test_alerts_task_opened.py`: o proponente não recebe alerta `TASK_OPENED` da tarefa `triage_evaluation` (o alerta segue `edit_roles`, Spec 047).
- [X] T011 [P] [US1] Atualizar `tests/integration/database/test_activity_access_columns.py::test_phase1_access_matrix_on_instantiation`: trocar `assert 'proponent' not in activities['triage_evaluation'].view_roles` por `assert 'proponent' in activities['triage_evaluation'].view_roles`, mantendo `edit_roles == ['bracvam']`.
- [X] T012 [P] [US1] Reescrever `tests/api/routers/test_timeline_router.py::test_timeline_hides_events_of_activities_without_view` para manter a cobertura da Spec 030 (FR-021) com uma atividade que o proponente continua sem ver: aprovar a triagem, concluir a designação `assign_sponsor` como BraCVAM e verificar que o proponente não recebe eventos cujo `activity_run_id` é da execução de `assign_sponsor` (ex.: `ROLE_ASSIGNMENT_COMPLETED`). Renomear para `test_timeline_hides_events_of_activities_without_view_after_triage`.
- [X] T013 [P] [US1] Teste de migração em `tests/integration/migrations/test_triage_proponent_view_migration.py`, no formato de `test_process_lifecycle_migration.py` (`run_migration`, `run_downgrade`): (a) upgrade acrescenta `proponent` a `view_roles` de `triage_evaluation` e mantém `edit_roles`; (b) instância que já tinha `proponent` termina com uma ocorrência só; (c) upgrade, downgrade e upgrade de novo terminam com uma ocorrência só (o Alembic não reaplica uma revisão já aplicada, então a repetição passa pelo downgrade); (d) instâncias de outras atividades não mudam; (e) downgrade retira `proponent`; (f) num processo semeado com `view_roles` sem `proponent` na triagem e uma `Assignment` ativa de `proponent`, depois do upgrade a instância `triage_evaluation` passa no `activity_view_clause(session, proponente_id)` de `pivma.core.process_engine`, o mesmo filtro de `GET /tasks`; antes do upgrade, não passa (US1, cenário 8). O teste de migração semeia com SQL e não tem `client`, por isso usa o filtro e não a rota. Um teste por item.

### Implementation for User Story 1

- [X] T014 [US1] Nos cinco YAML de `src/pivma/templates_data/`, em `triage_evaluation`, trocar `view: []` por `view: ["proponent"]` (manter `edit: ["bracvam"]`) e subir `process_template.version`: `01_pre_validated_method.yaml` 6→7, `02_scope_extension.yaml` 6→7, `03_me_too_validation.yaml` 6→7, `04_validated_method_dossier.yaml` 8→9, `05_test_short_form.yaml` 2→3 (research R1).
- [X] T015 [US1] Criar `migrations/versions/<rev>_triage_evaluation_proponent_view.py` com `down_revision = 'b7d3e9a1c5f2'`. `upgrade`: `UPDATE activity_instances SET view_roles = array_append(view_roles, 'proponent') WHERE key = 'triage_evaluation' AND NOT ('proponent' = ANY(view_roles))`. `downgrade`: `UPDATE activity_instances SET view_roles = array_remove(view_roles, 'proponent') WHERE key = 'triage_evaluation'` (research R2). Conferir com `poetry run alembic heads` que fica um head só.
- [X] T016 [US1] Em `src/pivma/routers/processes.py`, criar `TRIAGE_AUTHOR_EVENTS = frozenset({'TRIAGE_APPROVED', 'TRIAGE_REJECTED', 'REVISION_REQUESTED', 'RETURN_REVIEW_OPENED'})` e, em `get_process_timeline`, trocar `e.event_type != 'RETURN_REVIEW_OPENED'` por `e.event_type not in TRIAGE_AUTHOR_EVENTS` (research R3).
- [X] T017 [US1] Em `src/pivma/routers/processes.py`, `_visible_events` descarta `FIELD_REVIEWED` para quem não tem `has_process_review_access`, antes da paginação (research R4). Calcular `has_process_review_access` uma vez por requisição e reaproveitar em `get_process_timeline`.
- [X] T018 [US1] Ajustar as jornadas que contam tarefas `READY` do proponente como "pendências" para usar `actionable=true`: `_pending` em `tests/integration/journeys/etapa_1_submissao_triagem/test_return_review_via_ai.py` (passo 5, depois da contestação, a triagem fica `READY` e visível ao proponente) e qualquer outra apontada pela suíte. Não trocar asserção que mede visibilidade de propósito.
- [X] T019 [US1] Rodar T002 a T013 e a suíte de `tests/integration/journeys/etapa_1_submissao_triagem` e `tests/api/routers`; todos verdes.

**Checkpoint**: US1 entregue sozinha resolve a issue #81.

---

## Phase 4: User Story 3 - Convites ficam com quem gerencia participantes (Priority: P1)

**Goal**: só quem gerencia participantes lê os convites; os demais veem só o próprio aceite (FR-007, FR-009).

**Independent Test**: convidar um avaliador ad hoc e membros de dois laboratórios, aceitar e comparar a linha do tempo do gestor, do proponente e de cada laboratório.

### Tests for User Story 3

- [X] T020 [US3] Jornada em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_invite_timeline_privacy.py` (docstring "Spec 049, US3"; partir de `bootstrap_fresh_deploy` e trocar de ator com `sign_up`, `log_in`, `log_out` e `make_bracvam` de `tests/integration/journeys/conftest.py`): (1) o proponente envia e o BraCVAM aprova a triagem; (2) o BraCVAM convida por e-mail um avaliador ad hoc e um membro do Laboratório A (`POST /processes/{id}/participants/invites`); (3) o convidado do laboratório aceita (token obtido como em `tests/api/routers/test_invite_acceptance.py`) e vê o próprio `INVITE_ACCEPTED`; (4) o proponente lê a linha do tempo e não recebe nenhum `INVITE_*` nem o e-mail dos convidados em `response.text`; (5) o BraCVAM vê `INVITE_CREATED` e `INVITE_ACCEPTED` com e-mail e autor.
- [X] T021 [P] [US3] Contrato em `tests/api/routers/test_participant_timeline.py`: quem gerencia participantes recebe `INVITE_CREATED`, `INVITE_RESENT`, `INVITE_REVOKED` e `INVITE_ACCEPTED`, com `context_data['email']` em `INVITE_CREATED` e `user_id` preenchido.
- [X] T022 [P] [US3] Contrato em `tests/api/routers/test_participant_timeline.py`: o proponente não recebe `INVITE_CREATED`, `INVITE_RESENT` nem `INVITE_REVOKED` de convite para outra pessoa, e o e-mail convidado não aparece em `response.text`.
- [X] T023 [P] [US3] Contrato em `tests/api/routers/test_participant_timeline.py`: o proponente não recebe o `INVITE_ACCEPTED` de outra pessoa.
- [X] T024 [P] [US3] Isolamento em `tests/api/routers/test_participant_timeline.py`: com convites aceitos por membros dos laboratórios A e B, o membro de A recebe o próprio `INVITE_ACCEPTED` e nenhum `INVITE_*` do convite de B (constituição III, RF044).
- [X] T025 [P] [US3] Paginação em `tests/api/routers/test_participant_timeline.py`: com convites ocultos ao proponente, `pagination.total_items` é igual ao total de eventos visíveis, e a segunda página (`per_page=1`) não pula evento visível.

### Implementation for User Story 3

- [X] T026 [US3] Em `src/pivma/routers/processes.py`, criar `INVITE_EVENT_TYPES = frozenset({'INVITE_CREATED', 'INVITE_RESENT', 'INVITE_REVOKED', 'INVITE_ACCEPTED'})` e, em `_visible_events`, depois do retorno antecipado de quem gerencia participantes, manter só `INVITE_ACCEPTED` com `event.user_id == current_user.id` (research R6). Depende de T017 (mesma função).
- [X] T027 [US3] Rodar T020 a T025 e `tests/api/routers/test_participant_timeline.py` inteiro; todos verdes.

**Checkpoint**: US1 + US3 fecham a exposição de convites da issue #84.

---

## Phase 5: User Story 4 - O avaliador cego não identifica o proponente (Priority: P1)

**Goal**: quem só tem cargos de revisão cega não recebe o `user_id` do proponente nem de outro avaliador (FR-008).

**Independent Test**: designar dois avaliadores ad hoc e conferir, como um deles, a ausência dos `id` do proponente e do outro avaliador na linha do tempo.

### Tests for User Story 4

- [X] T028 [US4] Jornada em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_blind_reviewer_timeline.py` (docstring "Spec 049, US4"; partir de `bootstrap_fresh_deploy` e trocar de ator com `sign_up`, `log_in`, `log_out` e `make_bracvam` de `tests/integration/journeys/conftest.py`): (1) o proponente cria e envia; (2) o BraCVAM aprova a triagem, designa o `group_manager` e depois os dois avaliadores ad hoc com `POST /processes/{id}/participants` (`role_key = 'adhoc_evaluator'`; o cargo só desbloqueia depois do `group_manager`, pela Sequência de Preenchimento, como em `test_invites_router.py::test_accept_and_revoke_pending_sibling_closes_activity`). Usar a designação direta e não o convite, para a jornada provar o autor dos eventos sem depender dos `INVITE_*`, que a US3 já cobre; (3) o avaliador 1 lê a linha do tempo: `PROCESS_CREATED` vem com `user_id is None`, os `id` do proponente e do avaliador 2 não aparecem em `response.text`, e eventos de autoria dele mesmo trazem o próprio `id`; (4) o BraCVAM lê a mesma linha do tempo com todos os autores.
- [X] T029 [P] [US4] Contrato em `tests/api/routers/test_timeline_blind_review.py`: para o `adhoc_evaluator`, todo evento que ele recebe e que tem o proponente como autor (`PROCESS_CREATED` e os demais visíveis a ele) vem com `user_id is None`, e o `id` do proponente não aparece em `response.text`.
- [X] T030 [P] [US4] Contrato em `tests/api/routers/test_timeline_blind_review.py`: a mesma regra vale para `peer_reviewer` (cargo concedido com `grant_cargo`).
- [X] T031 [P] [US4] Contrato em `tests/api/routers/test_timeline_blind_review.py`: com dois `adhoc_evaluator`, um não recebe o `id` do outro em `response.text`.
- [X] T032 [P] [US4] Contrato em `tests/api/routers/test_timeline_blind_review.py`: autor com designação de `proponent` ou de cargo cego já revogada continua oculto ao avaliador (research R7).
- [X] T033 [P] [US4] Contrato em `tests/api/routers/test_timeline_blind_review.py`: avaliador ad hoc que também é `group_manager` no processo recebe o `user_id` do proponente (união de cargos).
- [X] T034 [P] [US4] Contrato em `tests/api/routers/test_timeline_blind_review.py`: evento de autoria do BraCVAM chega ao avaliador ad hoc com `user_id` preenchido.
- [X] T035 [P] [US4] Regressão em `tests/api/routers/test_timeline_blind_review.py`: `sponsor` e `participating_laboratory` continuam recebendo o `user_id` do proponente em `PROCESS_CREATED` (o cegamento não vaza para cargos sem revisão cega).

### Implementation for User Story 4

- [X] T036 [US4] Em `src/pivma/routers/processes.py`, criar `_blind_hidden_authors(session, current_user, process_id) -> set[UUID]`: usa `has_platform_wide_access`, `viewer_assignments` e `progress_view` de `pivma.core.process_progress`; se `not view.full and view.roles and view.roles <= BLIND_REVIEW_ROLES`, devolve os `user_id` de todas as `Assignment` do processo (ativas ou revogadas) com `role_key` igual a `proponent` ou em `BLIND_REVIEW_ROLES`, menos `current_user.id`; senão, `set()` (research R7).
- [X] T037 [US4] Em `get_process_timeline`, devolver `user_id = None` quando `e.user_id` estiver em `_blind_hidden_authors(...)`, somado à regra de T016. Depende de T016.
- [X] T038 [US4] Rodar T028 a T035 e `tests/api/routers/test_timeline_router.py`; todos verdes.

**Checkpoint**: issue #84 resolvida.

---

## Phase 6: User Story 2 - O proponente lê só pareceres decididos (Priority: P2)

**Goal**: `reviews` em `GET .../form` só traz pareceres de triagem concluída para quem não tem `triage.review` (FR-006).

**Independent Test**: salvar pareceres sem decidir e comparar o formulário como proponente e como triador; decidir e comparar de novo.

### Tests for User Story 2

- [X] T039 [P] [US2] Jornada em `tests/integration/journeys/etapa_1_submissao_triagem/test_proponent_reads_decided_reviews.py` (docstring "Spec 049, US2"; partir de `bootstrap_fresh_deploy` e trocar de ator com `sign_up`, `log_in`, `log_out` e `make_bracvam` de `tests/integration/journeys/conftest.py`): (1) o proponente envia; (2) o triador salva pareceres e vê os próprios em `reviews`; (3) o proponente abre `GET /processes/{id}/activities/proposal_submission/form` e recebe `reviews == {}`; (4) o triador pede revisão; (5) o proponente abre o formulário com `run_number=1` e recebe os pareceres, sem o `id` do triador em `response.text`.
- [X] T040 [P] [US2] Contrato em `tests/api/routers/test_activity_form_reviews.py`: com pareceres e triagem sem decisão, o proponente recebe `reviews == {}`.
- [X] T041 [P] [US2] Regressão em `tests/api/routers/test_activity_form_reviews.py`: na mesma situação, o triador recebe os pareceres em edição em `reviews`.
- [X] T042 [P] [US2] Contrato em `tests/api/routers/test_activity_form_reviews.py`: depois da decisão, o proponente recebe os pareceres com `status` e `comments`, e o `id` do triador não aparece em `response.text`.
- [X] T043 [P] [US2] Contrato em `tests/api/routers/test_activity_form_reviews.py`: com a triagem aberta por contestação da IA (`_ai_return` e depois `_choose(client, pid, 'CONTEST_AI', ...)`, como em `tests/api/routers/test_return_review.py::test_contest_ai_moves_to_triage`, com as fixtures `ai_eval_admin` e `fake_provider`), pareceres novos da execução de triagem em andamento não aparecem para o proponente.
- [X] T044 [P] [US2] Regressão em `tests/api/routers/test_activity_form_reviews.py`: `previous_reviews` continua igual ao de antes para o proponente depois de uma revisão (Spec 046).

### Implementation for User Story 2

- [X] T045 [US2] Em `src/pivma/routers/forms.py::get_activity_form`, se o usuário não tem `has_process_review_access`, buscar o `status` das `ActivityRun` em `{fr.activity_run_id for fr in form_inst.reviews}` e só pôr em `reviews_dict` os pareceres cuja execução está `'COMPLETED'` (research R5; mesmo critério de `submission_run_reviews`).
- [X] T046 [US2] Rodar T039 a T044 e `tests/api/routers/test_return_review.py`; todos verdes.

**Checkpoint**: pendência da Spec 046 fechada.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T047 [P] Atualizar `manual/explicacao/autorizacao.md`: o proponente vê a triagem sem o autor; visibilidade dos eventos de convite; cegamento do autor para `adhoc_evaluator` e `peer_reviewer`. Usar a skill `stop-slop`.
- [X] T048 [P] Atualizar `manual/referencia/eventos.md`: quem recebe `FIELD_REVIEWED` e os `INVITE_*`, e quando `user_id` vem nulo.
- [X] T049 [P] Atualizar `manual/referencia/perfis-permissoes-cargos.md` (matriz da Fase 1: `triage_evaluation` com visão do proponente), `manual/guias/conduzir-a-triagem.md` (o proponente acompanha sem ver o autor) e `manual/guias/responder-ao-retorno.md` (pareceres só depois da decisão). Antes, `grep -rn "triage_evaluation\|reviews\|linha do tempo" manual/` para achar outros trechos que ficaram falsos.
- [X] T050 Rodar `poe docs-build`; sem link ou âncora quebrados.
- [X] T051 Rodar `poe lint` e `poe test` completos e registrar o resultado real no PR, inclusive falhas.
- [X] T052 Conferir os critérios de parada de `.agents/skills/testing-methodology/references/03-criterios-de-parada.md` e a matriz FR → teste abaixo; marcar no PR o que não se aplica e por quê.

## Phase 8: Revisão da PR (Codex, 2026-11-27)

- [X] T053 [P] [US1] Contrato em `tests/api/routers/test_pre_evaluation_feedback.py`: o proponente recebe `AI_CRITERION_FEEDBACK_RECORDED` com `user_id is None` e sem o id do triador em `response.text`; quem tem `triage.review` recebe o autor.
- [X] T054 [P] [US3] Contrato em `tests/api/routers/test_participant_timeline.py`: com o convite por e-mail aceito antes do envio, o proponente não recebe `NOTIFICATION_*` nem o id de quem aceitou; quem gerencia participantes recebe `NOTIFICATION_CANCELLED` com o autor.
- [X] T055 [P] [US4] Em `tests/api/routers/test_timeline_blind_review.py`, trocar o teste da união de cargos (issue #85) pelo de leitor sem cargo efetivo, que recebe o cegamento.
- [X] T056 [US1] Jornadas em `tests/integration/journeys/etapa_1_submissao_triagem/test_proponent_triage_view.py`: reprovação depois da pré-avaliação positiva e pedido de revisão, com prazo e rodada da tarefa.
- [X] T057 Em `src/pivma/routers/processes.py`: `AI_CRITERION_FEEDBACK_RECORDED` em `TRIAGE_AUTHOR_EVENTS`; `NOTIFICATION_*` de convite só para quem gerencia participantes; `_blind_hidden_authors` falha fechada sem cargo.
- [X] T058 Atualizar `manual/referencia/eventos.md`, `manual/explicacao/autorizacao.md`, `manual/guias/conduzir-a-triagem.md`, `manual/explicacao/escopo.md` (RF050) e o docstring da migração.

---

**Resultado (2026-11-27)**: `poe lint` sem erro; `poe test` com 2496 testes verdes, 1 pulado, cobertura de 95% (2506 verdes depois da Phase 8, sobre o commit `92470fc` da PR #83); `poe docs-build` sem link quebrado. A linha de base de T001 deu 84 verdes. Além das tarefas, quatro testes antigos fixavam o comportamento ou as versões que a spec muda e foram ajustados: `test_tasks_visibility.py` (o negado passa a ser o patrocinador, porque o proponente vê a triagem), `test_template_phase_2.py::NEW_VERSIONS` e as versões em `test_activity_type_extension.py` e `test_process_references.py`. Critérios de parada: atendidos. T032 tem um teste por caso: `test_revoked_evaluator_stays_hidden` e `test_revoked_proponent_stays_hidden`, que revoga a designação do proponente direto no banco porque a API não a revoga.

## Rastreabilidade FR → testes

| Requisito | Testes |
|---|---|
| FR-001 | T002, T011 |
| FR-002 | T013 |
| FR-003 | T002, T013(f) |
| FR-004 | T002, T003, T004, T008, T009, T053, T056 |
| FR-005 | T002, T005, T008 |
| FR-006 | T039 a T044 |
| FR-007 | T020 a T024, T054 |
| FR-008 | T028 a T035, T055 |
| FR-009 | T005, T025 |
| FR-010 | T006, T007 |
| FR-011 | T047 a T050 |
| Spec 030 FR-021 (regressão) | T012 |
| Spec 047 alertas (regressão) | T010 |

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (T001) antes de tudo.
- US1 (Phase 3) é o MVP. US3 e US4 dependem de US1 só porque editam as mesmas funções de `processes.py` (T016 → T017 → T026 → T036 → T037).
- US2 (Phase 6) é independente e pode correr em paralelo a US1, US3 e US4.
- Polish depois de todas as histórias.

### Within Each User Story

- Testes primeiro, falhando; depois a implementação; depois a tarefa de rodar a suíte da história.
- T014 e T015 (templates e migração) antes de T018 (ajuste das jornadas existentes).

### Parallel Opportunities

- US1: T003 a T013 em paralelo (arquivos diferentes ou testes independentes no mesmo arquivo novo).
- US3: T021 a T025 em paralelo, depois de T020.
- US4: T029 a T035 em paralelo, depois de T028.
- US2: T039 a T044 em paralelo; a história inteira em paralelo às outras.
- Polish: T047 a T049 em paralelo.

---

## Parallel Example: User Story 1

```bash
# Testes focados da US1, depois da jornada T002:
poetry run pytest tests/api/routers/test_triage_proponent_view.py
poetry run pytest tests/integration/migrations/test_triage_proponent_view_migration.py
poetry run pytest tests/integration/database/test_activity_access_columns.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001.
2. US1 (T002 a T019): resolve a issue #81.
3. Parar e validar: o proponente distingue "com a BraCVAM" de "triagem aprovada".

### Incremental Delivery

1. US1 → #81.
2. US3 → convites fora do alcance de quem não gerencia participantes.
3. US4 → cegamento completo; com US3, fecha a #84.
4. US2 → pendência da Spec 046.
5. Polish → manual e suíte completa.

---

## Notes

- Aplicar `karpathy-guidelines` a cada tarefa de código: mudança cirúrgica, sem refatorar o que está fora do escopo.
- O autor continua gravado em todo `AuditEvent`; nenhuma tarefa muda a gravação.
- A PR desta spec aponta para `develop`, que recebeu a PR #83 em `9f06d31`. Rebasear sobre a `develop` do dia antes de abrir a PR.
