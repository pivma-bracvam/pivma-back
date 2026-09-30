---
description: "Tarefas da Spec 035 — validade da designação laboratorial"
---

# Tasks: Validade da designação laboratorial

**Input**: `specs/035-lab-designation-validity/` (spec.md, plan.md, research.md, data-model.md, contracts/http-api.md, quickstart.md)

**Tests**: obrigatórios (`AGENTS.md`), planejados com `fastapi-testing-methodology`.
Risco **crítico** (autorização e isolamento de laboratório): integração do
predicado, API, segurança e concorrência. Cada tarefa de teste cobre um
comportamento observável e vem antes da implementação da sua história.

**Organization**: por história da spec. US1, US2 e US3 são P1; US4 e US5 são P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: história da spec (US1 a US5)

## Arquivos de teste

- `tests/integration/database/test_lab_designation_effectiveness.py` — predicado único (R2)
- `tests/api/routers/test_lab_designation_validity.py` — acesso, consistência e eventos pela API
- `tests/api/routers/test_lab_designation_concurrency.py` — ações institucionais simultâneas (R4)

Fixtures compartilhadas ficam no próprio `test_lab_designation_validity.py`:
um template mínimo (via `sync_template_from_dict`, padrão de
`tests/factories/task_listing_factory.py`) com uma atividade `lab_bench` com
`access: {edit: [participating_laboratory], view: []}` e outra `stats_review`
com `access: {edit: [statistician], view: []}`; instituição, laboratório e
vínculo ativos via `tests/factories/institutional_factory.py`; designação via
`Assignment` com `laboratory_id`; o `bracvam_user` de `tests/conftest.py` como
ator das ações institucionais (tem todas as permissões, Spec 023), com
`Origin: https://testserver`.

---

## Phase 1: Setup

- [X] T001 Confirmar a linha de base: `poetry run pytest tests/api/routers/test_participant_router.py tests/api/routers/test_activity_access.py tests/api/routers/test_institutional_router.py -q` passa na branch antes de qualquer mudança

---

## Phase 2: Foundational — predicado único de efetividade (research R2)

**Purpose**: `effective_assignment_clause()` é usado por todas as histórias.

### Testes (antes da implementação)

- [X] T002 [P] Teste: designação `study_manager` ativa é efetiva sem vínculo nenhum, em `tests/integration/database/test_lab_designation_effectiveness.py`
- [X] T003 [P] Teste: designação `participating_laboratory` com vínculo, laboratório e instituição ativos é efetiva, em `tests/integration/database/test_lab_designation_effectiveness.py`
- [X] T004 [P] Teste: designação laboratorial com vínculo encerrado (`deleted_at` preenchido) não é efetiva, em `tests/integration/database/test_lab_designation_effectiveness.py`
- [X] T005 [P] Teste: designação laboratorial com laboratório inativo não é efetiva, em `tests/integration/database/test_lab_designation_effectiveness.py`
- [X] T006 [P] Teste: designação laboratorial com instituição do laboratório inativa não é efetiva, em `tests/integration/database/test_lab_designation_effectiveness.py`
- [X] T007 [P] Teste: vínculo ativo do mesmo usuário com outro laboratório não torna efetiva a designação pelo laboratório sem vínculo, em `tests/integration/database/test_lab_designation_effectiveness.py`
- [X] T008 [P] Teste: `lead_laboratory` segue a mesma regra de `participating_laboratory` (vínculo encerrado → não efetiva), em `tests/integration/database/test_lab_designation_effectiveness.py`

### Implementação

- [X] T009 Criar `effective_assignment_clause()` em `src/pivma/core/authorization.py`: para `role_key` fora de `LABORATORY_ROLE_KEYS`, verdadeiro; para cargo laboratorial, `EXISTS` de `UserInstitutionalAffiliation` com `user_id` e `laboratory_id` da designação, `deleted_at IS NULL`, junto a `Laboratory` e `Institution` (do laboratório) com `deleted_at IS NULL`; filtros explícitos, sem depender do filtro global de soft-delete

**Checkpoint**: T002–T008 passam consultando `Assignment.id` com o predicado.

---

## Phase 3: User Story 1 — Quem deixa o laboratório perde o acesso do cargo (P1) 🎯 MVP

**Goal**: designação laboratorial não efetiva não concede acesso nenhum do cargo (FR-004 a FR-007).

**Independent Test**: designar, confirmar acesso a `lab_bench`, encerrar o vínculo, confirmar negação.

### Testes (antes da implementação)

- [X] T010 [P] [US1] Teste de regressão: após encerrar o vínculo, `require_activity_access(..., 'view')` sobre `lab_bench` levanta `NotFoundError`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T011 [P] [US1] Teste: com vínculo ativo, `require_activity_access(..., 'edit')` sobre `lab_bench` passa (controle positivo), em `tests/api/routers/test_lab_designation_validity.py`
- [X] T012 [P] [US1] Teste: após encerrar o vínculo, `GET /tasks` não lista a tarefa de `lab_bench` para a pessoa, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T013 [P] [US1] Teste: após encerrar o vínculo, `GET /tasks?actionable=true` não lista a tarefa de `lab_bench`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T014 [P] [US1] Teste: com o cargo laboratorial como única designação, após encerrar o vínculo, `GET /processes` não lista o processo, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T015 [P] [US1] Teste: no mesmo caso, `GET /processes/{id}` responde `404` com `code: not_found`, igual a quem nunca teve cargo (FR-005), em `tests/api/routers/test_lab_designation_validity.py`
- [X] T016 [P] [US1] Teste: no mesmo caso, `GET /processes/{id}/timeline` responde `404`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T017 [P] [US1] Teste: pessoa com `statistician` efetivo no mesmo processo continua acessando `stats_review` e vendo o processo após perder o cargo laboratorial (FR-007), em `tests/api/routers/test_lab_designation_validity.py`
- [X] T018 [P] [US1] Teste: após encerrar o vínculo, a designação continua com `revoked_at` nulo e a tarefa de `lab_bench` continua com o mesmo status (FR-006), em `tests/api/routers/test_lab_designation_validity.py`

### Implementação

- [X] T019 [US1] Aplicar `effective_assignment_clause()` em `process_cargos_scope` em `src/pivma/core/authorization.py` (cobre `user_cargos`, `activity_view_clause`, `_can_act_clause` e amostras)
- [X] T020 [US1] Aplicar `effective_assignment_clause()` em `active_participant_process_scope` em `src/pivma/core/authorization.py` (visibilidade de processo e linha do tempo)

**Checkpoint**: T010–T018 passam; a issue #60 está corrigida para fim de vínculo.

---

## Phase 4: User Story 2 — Laboratório ou instituição inativados retiram o acesso (P1)

**Goal**: inativar laboratório ou instituição tem o mesmo efeito da US1.

**Independent Test**: inativar pela API e confirmar a negação.

### Testes

- [X] T021 [P] [US2] Teste: após `DELETE /institutional/laboratories/{id}`, `require_activity_access(..., 'view')` sobre `lab_bench` levanta `NotFoundError`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T022 [P] [US2] Teste: após `DELETE /institutional/institutions/{id}` da instituição do laboratório, `require_activity_access(..., 'view')` sobre `lab_bench` levanta `NotFoundError`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T023 [P] [US2] Teste: inativar o Laboratório A não afeta a designação de outra pessoa pelo Laboratório B, em `tests/api/routers/test_lab_designation_validity.py`

### Implementação

- [X] T024 [US2] Confirmar que T021–T023 passam só com T009 e T019–T020; nenhum código novo esperado (confirmado: nenhum ajuste necessário)

---

## Phase 5: User Story 3 — Exibição e autorização dizem a mesma coisa (P1)

**Goal**: `/auth/me`, listagem de participantes, autorização e validação de nova designação usam a regra do FR-001 (FR-002, FR-003).

### Testes

- [X] T025 [P] [US3] Teste: com a instituição do laboratório inativa, `GET /processes/{id}/participants` mostra `effective: false`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T026 [P] [US3] Teste: com a instituição do laboratório inativa, `GET /auth/me` não inclui o escopo daquela designação em `access.scopes`, em `tests/api/routers/test_lab_designation_validity.py`
- [X] T027 [P] [US3] Teste parametrizado: para vínculo ativo, vínculo encerrado, laboratório inativo e instituição inativa, o `effective` da listagem de participantes coincide com o resultado de `require_activity_access` sobre `lab_bench` (SC-002), em `tests/api/routers/test_lab_designation_validity.py`
- [X] T028 [P] [US3] Teste: `has_active_laboratory_affiliation` retorna `False` quando o vínculo está ativo mas o laboratório está inativo, em `tests/integration/database/test_lab_designation_effectiveness.py`

### Implementação

- [X] T029 [US3] Reescrever `compute_effectiveness_map` em `src/pivma/core/authorization.py` para consultar os ids efetivos com `effective_assignment_clause()` (mais não revogada, não excluída, usuário ativo), mantendo a assinatura e o retorno `dict[UUID, bool]`
- [X] T030 [US3] Fazer `has_active_laboratory_affiliation` em `src/pivma/core/authorization.py` usar a mesma subconsulta de vínculo ativo do predicado (vínculo, usuário, laboratório e instituição ativos)

---

## Phase 6: User Story 4 — A perda da validade fica na trilha (P2)

**Goal**: um evento `PARTICIPANT_EFFECTIVENESS_LOST` por designação que deixou de valer, só em processos em andamento (FR-008 a FR-011, FR-008a).

### Testes

- [ ] T031 [P] [US4] Teste: `DELETE /institutional/users/{id}/affiliations/{id}` com designações efetivas em dois processos em andamento grava um `PARTICIPANT_EFFECTIVENESS_LOST` em cada processo, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T032 [P] [US4] Teste: o evento traz `user_id` do ator e `context_data` com `assignment_id`, `participant_user_id`, `role_key`, `laboratory_id`, `result: success`, `source: institutional` e `reason: affiliation_ended`, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T033 [P] [US4] Teste: `DELETE /institutional/laboratories/{id}` grava o evento com `reason: laboratory_deactivated`, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T034 [P] [US4] Teste: `DELETE /institutional/institutions/{id}` grava o evento com `reason: institution_deactivated` para designações de todos os laboratórios da instituição, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T035 [P] [US4] Teste: inativar o laboratório de uma designação que já não valia (vínculo encerrado antes) não grava evento novo (FR-010), em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T036 [P] [US4] Teste: designação revogada não gera evento ao encerrar o vínculo (FR-010), em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T037 [P] [US4] Teste: processo com status `CLOSED` não recebe evento, e a pessoa perde o acesso a ele mesmo assim (FR-008a), em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T038 [P] [US4] Teste: processo excluído logicamente não recebe evento (FR-008a), em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T039 [P] [US4] Teste: encerrar vínculo sem laboratório ou sem designação afetada não grava evento de processo, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T040 [P] [US4] Teste: na linha do tempo, quem gere participantes vê o evento e outro participante sem gestão não o vê (visibilidade de `PARTICIPANT_EVENT_TYPES`), em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T041 [P] [US4] Teste: `DELETE` concorrente do vínculo e do laboratório sobre a mesma designação resulta em exatamente um `PARTICIPANT_EFFECTIVENESS_LOST`, em `tests/api/routers/test_lab_designation_concurrency.py` (padrão de `tests/api/routers/test_participant_concurrency.py`: sessões independentes, `Barrier`, limpeza explícita)

### Implementação

- [ ] T042 [US4] Em `src/pivma/core/participant_service.py`, criar a captura de efetividade: selecionar e travar (`FOR UPDATE` em `Assignment`) as designações ativas de cargo laboratorial dos laboratórios informados (e do usuário, quando informado) em processos não excluídos com status fora de `IMMUTABLE_PROCESS_STATUSES`, e devolver os ids efetivos entre elas pelo predicado
- [ ] T043 [US4] Em `src/pivma/core/participant_service.py`, criar o registro das transições: recalcular os ids efetivos após `flush` e gravar `AuditEvent` com `event_type` `PARTICIPANT_EFFECTIVENESS_LOST` ou `PARTICIPANT_EFFECTIVENESS_RESTORED` ("cabem em `String(64)`"), `user_id` do ator, `context_data` de `_assignment_event_context(result='success', source='institutional')` mais `reason`
- [ ] T044 [US4] Chamar a captura e o registro em `deactivate_affiliation`, `deactivate_laboratory` e `deactivate_institution` em `src/pivma/routers/institutional.py`, antes do `commit` (reasons `affiliation_ended`, `laboratory_deactivated`, `institution_deactivated`; na instituição, os laboratórios dela)
- [ ] T045 [US4] Incluir os dois tipos novos em `PARTICIPANT_EVENT_TYPES` em `src/pivma/routers/processes.py`

---

## Phase 7: User Story 5 — Vínculo restabelecido (P2)

**Goal**: novo vínculo devolve a efetividade e grava `PARTICIPANT_EFFECTIVENESS_RESTORED` (FR-012, FR-012a).

### Testes

- [ ] T046 [P] [US5] Teste: após encerrar e recriar o vínculo com o mesmo laboratório (`POST /institutional/users/{id}/affiliations`), `require_activity_access(..., 'edit')` sobre `lab_bench` volta a passar, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T047 [P] [US5] Teste: a recriação grava um `PARTICIPANT_EFFECTIVENESS_RESTORED` com `reason: affiliation_created` por processo em andamento, em `tests/api/routers/test_lab_designation_validity.py`
- [ ] T048 [P] [US5] Teste: criar vínculo para quem já tinha a designação efetiva (outro laboratório, ou vínculo sem laboratório) não grava evento, em `tests/api/routers/test_lab_designation_validity.py`

### Implementação

- [ ] T049 [US5] Chamar a captura e o registro de T042–T043 em `create_affiliation` em `src/pivma/routers/institutional.py`, depois do `flush` do vínculo e antes do `commit`, com `reason` `affiliation_created`, só quando `laboratory_id` for informado

---

## Phase 8: Polish

- [ ] T050 Atualizar `README.md` (seção "Participantes e Conflito de Interesses"): regra de designação efetiva, perda de acesso sem revogação e os dois eventos novos
- [ ] T051 Rodar `poetry run ruff check .` e `poetry run ruff format --check .` sem erros
- [ ] T052 Rodar a suíte completa `poetry run pytest -q`; ajustar só testes que dependiam do defeito corrigido, registrando cada ajuste (SC-005)
- [ ] T053 Marcar as tarefas concluídas neste arquivo e registrar no PR os resultados reais de T051–T052

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T009)** → histórias.
- **US1 (T010–T020)** depende do predicado. É o MVP e corrige a #60.
- **US2 (T021–T024)** depende de US1 (mesmas funções); sem código novo.
- **US3 (T025–T030)** depende só do predicado; pode correr em paralelo a US1.
- **US4 (T031–T045)** depende do predicado; T041 depende de T042–T044.
- **US5 (T046–T049)** depende de T042–T043.
- **Polish** por último.

## Parallel Example

```text
# Testes do predicado (mesmo arquivo, independentes entre si)
T002..T008

# US1: testes independentes, depois T019 e T020 em sequência (mesmo arquivo)
T010..T018 → T019 → T020
```

## Implementation Strategy

1. T001–T009, depois US1 (T010–T020): valida a correção da #60 com o menor diff.
2. US2 e US3 fecham a regra única.
3. US4 e US5 acrescentam a trilha.
4. Polish e PR para a `develop`.
