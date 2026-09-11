---

description: "Task list for 018-kanban-activities-roles"
---

# Tasks: Kanban de Pendências e Revisão de Cargos

**Input**: Design documents from `/specs/018-kanban-activities-roles/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/,
quickstart.md

**Tests**: incluídos — a Constituição do projeto (Princípio IV, NÃO NEGOCIÁVEL) exige
`ruff format`/`ruff check`/`pytest` antes de qualquer entrega, com testes seguindo a
estrutura em níveis já estabelecida (`tests/unit/`, `tests/api/routers/`,
`tests/integration/database/`, `tests/integration/migrations/`) e as factories de
`tests/factories/`.

**Organization**: tarefas agrupadas por user story (spec.md), precedidas pelas tarefas
fundacionais que bloqueiam todas as histórias.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1, US2 ou US3 (spec.md)

## Phase 1: Setup

Nenhuma inicialização de projeto é necessária — a feature vive inteiramente dentro da
estrutura já existente do repositório (API Python, Alembic, `demos/`,
`scripts/seeds/`). Fase omitida.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: normalizar o vocabulário de cargo compartilhado, corrigir a regra de
visibilidade e remover o vínculo de pendência-a-pessoa dos quais as três user stories
dependem.

**⚠️ CRITICAL**: bloqueia todas as user stories.

- [X] T001 Adicionar o `Literal` `ActivityCargo` em `src/pivma/schemas.py`, com os
  valores `'proponent'`, `'group_manager'`, `'study_manager'`, `'statistician'`,
  `'adhoc_evaluator'`, `'peer_reviewer'`, `'lead_laboratory'`,
  `'participating_laboratory'` (mesmo vocabulário contextual do `Literal`
  `ParticipantRole` já existente), mais os dois valores reservados de cargo global
  `'admin'` e `'bracvam'` (data-model.md §1).
- [X] T002 [P] Implementar `has_platform_wide_access(session, user_id) -> bool` em
  `src/pivma/core/authorization.py`: `true` quando o usuário tem `UserAccessProfile`
  ativa para `AccessProfile.system_key IN ('administrator', 'bracvam')` (research.md D1,
  data-model.md §1).
- [X] T003 [P] Implementar `active_participant_process_scope(user_id) -> Select` em
  `src/pivma/core/authorization.py`, irmã de `active_proponent_process_scope` já
  existente, mas sem filtrar por `role_key` — qualquer `Assignment` ativa
  (`revoked_at IS NULL`, `deleted_at IS NULL`) conta (research.md D2).
- [X] T004 [P] Implementar `resolve_activity_holders(session, process_id, cargo) ->
  list[User]` em `src/pivma/core/authorization.py`: para `cargo IN ('admin',
  'bracvam')`, consulta `UserAccessProfile`/`AccessProfile.system_key`; para os demais
  valores de `ActivityCargo`, consulta `Assignment` ativa naquele `process_id` com
  `role_key == cargo` (research.md D6).
- [X] T005 Corrigir `_init_first_activity` em `src/pivma/core/process_engine.py`: a
  `Task` de `proposal_submission` passa a ser criada só com `assigned_role`, sem
  `assigned_user_id=creator_id` — igual ao restante do motor (`_activate_activity`,
  `_unblock_triage_activity`, `_open_new_submission_run`) já faz (research.md D4, spec
  FR-016/FR-017).
- [X] T006 Normalizar o campo `assigned_role` nos 5 templates
  (`src/pivma/templates_data/*.yaml`): `"PROPONENT"` → `"proponent"`, `"TRIAGE_LEAD"` →
  `"bracvam"`, `"BRACVAM_ADMIN"` → `"bracvam"` (research.md D5).
- [X] T007 Gerar migração Alembic de dados
  `migrations/versions/<hash>_normalize_task_assigned_role.py`: `upgrade()` executa
  `UPDATE tasks SET assigned_role = 'proponent' WHERE assigned_role = 'PROPONENT'`,
  `UPDATE tasks SET assigned_role = 'bracvam' WHERE assigned_role = 'TRIAGE_LEAD'` e
  `UPDATE tasks SET assigned_role = 'bracvam' WHERE assigned_role = 'BRACVAM_ADMIN'`;
  `downgrade()` reverte simetricamente os três `UPDATE` (data-model.md §3). Nenhum
  `ALTER TABLE` — migração puramente de dados.
- [X] T008 [P] Validar que `assigned_role` pertence a `ActivityCargo` (T001) em dois
  pontos: quando `bootstrap_process_templates.py` sincroniza a definição de uma
  atividade, e quando `process_engine.py` cria uma `Task` a partir dela — rejeitando
  valor desconhecido em vez de aceitar string livre (data-model.md §1).
- [X] T009 [P] Aplicar `has_platform_wide_access` OR `process_id IN
  active_participant_process_scope(user)` ao `WHERE` de `GET /processes` e
  `GET /processes/{id}` em `src/pivma/routers/processes.py`
  (contracts/visibility-fixes.md §1-2; corrige o achado A1 do research.md).
- [X] T010 [P] Aplicar a mesma regra de visibilidade (T009) a `GET /tasks` em
  `src/pivma/routers/tasks.py`, que hoje não filtra por participação alguma
  (contracts/visibility-fixes.md §3; research.md achado A1).
- [X] T011 [P] Teste unitário: `has_platform_wide_access` retorna `true` para perfis
  `administrator`/`bracvam` e `false` para usuário sem nenhum desses perfis, em
  `tests/unit/core/test_authorization_platform_access.py` (usar factories de
  `tests/factories/`, não SQL manual).
- [X] T012 [P] Teste unitário: `active_participant_process_scope` inclui um processo
  onde o usuário tem `Assignment` ativa em qualquer `role_key` e exclui um processo com
  atribuição revogada ou inexistente, em
  `tests/unit/core/test_authorization_participant_scope.py`.
- [X] T013 [P] Teste unitário: `resolve_activity_holders` resolve cargo global
  (`'admin'`/`'bracvam'`) via `AccessProfile` e cargo contextual via `Assignment` ativa,
  retornando lista vazia quando ninguém ocupa o cargo, em
  `tests/unit/core/test_resolve_activity_holders.py`.
- [X] T014 [P] Teste de migração (upgrade e downgrade) da normalização de
  `tasks.assigned_role` (T007), confirmando os três `UPDATE` e a reversão simétrica, em
  `tests/integration/migrations/test_task_assigned_role_normalization_migration.py`.
- [X] T015 [P] Teste de API: `GET /processes` e `GET /processes/{id}` negam acesso
  (lista vazia / `404`) a um usuário `Padrão` sem atribuição no processo consultado, e
  permitem acesso total a `Admin`/`BraCVAM` mesmo sem atribuição, em
  `tests/api/routers/test_process_visibility.py`.
- [X] T016 [P] Teste de API: `GET /tasks` aplica a mesma restrição de visibilidade de
  T015, em `tests/api/routers/test_tasks_visibility.py`.

**Checkpoint**: vocabulário de cargo unificado, visibilidade corrigida em toda a
plataforma, pendência nunca mais vinculada a pessoa — as três user stories podem ser
implementadas.

---

## Phase 3: User Story 1 - Ver todas as minhas pendências em um só lugar (Priority: P1) 🎯 MVP

**Goal**: um único endpoint consolida, para o usuário autenticado, todas as atividades
de todos os métodos visíveis a ele, já classificadas em `Não Iniciado`/`Em
Andamento`/`Em Atraso`/`Concluído`.

**Independent Test**: com um usuário `BraCVAM` associado a ~300 processos em estágios
variados (via seed), `GET /activities/kanban` retorna todas as atividades relevantes já
distribuídas nas quatro colunas, sem nenhuma chamada por processo individual.

### Tests for User Story 1

- [X] T017 [P] [US1] Teste unitário: função de classificação de coluna — `BLOCKED` (sem
  run) → `NAO_INICIADO`; `READY`/`IN_PROGRESS` sem `sla_hours` ou dentro do prazo →
  `EM_ANDAMENTO`; `READY`/`IN_PROGRESS` com `sla_hours` excedido (`now - started_at >
  timedelta(hours=sla_hours)`) → `EM_ATRASO`; `COMPLETED` → `CONCLUIDO`, em
  `tests/unit/core/test_kanban_column_classification.py` (data-model.md, tabela de
  classificação).
- [X] T018 [P] [US1] Teste de API: `GET /activities/kanban` inclui atividades `BLOCKED`
  sem nenhuma `Task`/`ActivityRun` (ex.: fase 2 ainda não alcançada) classificadas como
  `NAO_INICIADO`, respeita `page`/`size`, preenche `counts_by_column` sobre o total
  visível (não só a página) e retorna `items: []`/`total: 0` para usuário sem nenhuma
  atividade associada, em `tests/api/routers/test_activities_kanban.py`
  (contracts/kanban-endpoint.md).

### Implementation for User Story 1

- [X] T019 [US1] Adicionar o campo opcional `sla_hours: int | null` a cada atividade nos
  5 templates (`src/pivma/templates_data/*.yaml`); ausente/`null` = sem prazo, nunca
  `EM_ATRASO` (data-model.md §1; depende de T006 já ter normalizado `assigned_role`
  nesses mesmos arquivos).
- [X] T020 [US1] Implementar a função pura de classificação de coluna testada em T017
  (ex.: `classify_kanban_column`) em `src/pivma/core/process_engine.py`, lendo
  `sla_hours` da definição da atividade dentro do `definition_payload` congelado da
  `ProcessTemplateVersion` da instância (nunca a versão mais recente do template).
- [X] T021 [P] [US1] Adicionar os schemas Pydantic do Kanban em `src/pivma/schemas.py`:
  enum `KanbanColumn` (`NAO_INICIADO`, `EM_ANDAMENTO`, `EM_ATRASO`, `CONCLUIDO`),
  `KanbanCardProcess`, `KanbanCardItem`, `KanbanPage` (campos e exemplo em
  contracts/kanban-endpoint.md).
- [X] T022 [US1] Implementar `GET /activities/kanban` em novo
  `src/pivma/routers/activities.py`: consulta `ActivityInstance` (não `Task`) com join
  até `ProcessInstance` e a `ActivityRun`/`Task` mais recente; aplica a visibilidade de
  T009/T010; decora cada item com `column` (T020), `cargo`
  (`Task.assigned_role`/definição da atividade), `blocked_reason`,
  `blocking_activity_key` (via `ActivityDependency`); suporta `column`, `process_id`,
  `page` (default `1`), `size` (default `50`, máx. `200`); calcula `counts_by_column`
  sobre o total visível antes da paginação (contracts/kanban-endpoint.md).
- [X] T023 [US1] Registrar `activities.router` em `src/pivma/__init__.py`, junto aos
  demais roteadores já incluídos.
- [X] T024 [US1] Criar `scripts/seeds/seed_kanban.py` com `run_seed_kanban()`: semear um
  usuário de perfil `bracvam` e ~300 `ProcessInstance` distribuídos pelos 5 templates
  oficiais, em estágios variados, incluindo casos propositalmente além do `sla_hours`
  declarado (T019), reaproveitando os helpers de `scripts/seeds/common.py` (Constituição
  Princípio III).
- [X] T025 [US1] Criar `demos/kanban/index.html`: quadro Kanban real com as quatro
  colunas, autenticando via `POST /auth/login` e consumindo `GET /activities/kanban`
  contra a API real, sem nenhum endpoint exclusivo para a demo e totalmente desacoplado
  de `src/` (Constituição Princípio II).
- [X] T026 [US1] Registrar a nova demonstração (card + link) em `demos/index.html`,
  seguindo o mesmo padrão das entradas existentes (ex.: `roadmap`).

**Checkpoint**: User Story 1 funcional e demonstrável de ponta a ponta (MVP).

---

## Phase 4: User Story 2 - Cargos globais e cargos por processo funcionam como esperado (Priority: P1)

**Goal**: comprovar, com evidência de API real, que `Admin`/`BraCVAM` veem tudo, que
cargos contextuais valem só no processo em que foram atribuídos (podendo ser diferentes
por processo para o mesmo usuário), e que uma pendência sem ninguém no cargo fica
sinalizada em vez de invisível.

**Independent Test**: usuário `Padrão` atribuído como Proponente só no Método A e Gestor
só no Método B enxerga exatamente esses dois no Kanban/consultas, com o cargo correto
por método, e não enxerga o Método C; `Admin`/`BraCVAM` enxergam os três.

### Tests for User Story 2

- [X] T027 [P] [US2] Teste de API: usuário `Padrão` com `Assignment` ativa como
  Proponente no Método A e Gestor no Método B vê ambos em `GET /activities/kanban`, cada
  atividade identificada com o cargo aplicável naquele método, e não vê nenhuma
  atividade do Método C, em `tests/api/routers/test_kanban_role_scoping.py`.
- [X] T028 [P] [US2] Teste de API: revogar (`revoked_at`) a única atribuição de um
  usuário em um método remove as atividades daquele método do Kanban na consulta
  seguinte, mesmo arquivo de T027.
- [X] T029 [P] [US2] Teste de API: duas pessoas com `Assignment` ativa no mesmo
  `role_key` no mesmo processo veem, ambas, a mesma pendência daquele cargo no Kanban
  (spec, User Story 2, cenário 6), mesmo arquivo de T027.
- [X] T030 [P] [US2] Teste unitário: `resolve_activity_holders` (T004) retornando lista
  vazia para um cargo contextual sem nenhuma `Assignment` ativa, extensão de
  `tests/unit/core/test_resolve_activity_holders.py` (T013).

### Implementation for User Story 2

- [X] T031 [US2] Adicionar o campo `cargo_unassigned: bool` ao item de
  `GET /activities/kanban` (`src/pivma/schemas.py` + `src/pivma/routers/activities.py`):
  `true` quando `resolve_activity_holders` (T004) retorna lista vazia para o cargo da
  atividade; visível apenas para quem tem `can_manage_participants` naquele processo
  (Edge Case da spec — cargo sem ocupante nunca deixa a pendência "solta").
- [X] T032 [US2] Estender `scripts/seeds/seed_kanban.py` (T024) com os 2 usuários
  `Padrão` exigidos por `quickstart.md` Cenário 2: um Proponente no Método A / Gestor no
  Método B; outro sem nenhuma atribuição em processo algum.
- [X] T033 [US2] Estender `demos/kanban/index.html` (T025) com um seletor entre o
  usuário `BraCVAM` e os dois usuários `Padrão` semeados, evidenciando lado a lado o
  recorte de visibilidade de cada um.

**Checkpoint**: User Stories 1 e 2 funcionais e demonstráveis juntas.

---

## Phase 5: User Story 3 - Lista de pendências com contexto de ordem (Priority: P2)

**Goal**: cada pendência bloqueada expõe o que precisa acontecer antes (e por quem), e
cada pendência em andamento distingue se é a vez do usuário atual ou de outra pessoa/cargo.

**Independent Test**: um cartão `NAO_INICIADO` mostra a atividade predecessora com seu
status/cargo atual sem sair do Kanban; um cartão `EM_ANDAMENTO` sob o cargo do usuário
atual aparece marcado como acionável agora, distinto de um sob outro cargo.

### Tests for User Story 3

- [X] T034 [P] [US3] Teste de API: item `NAO_INICIADO` por dependência expõe
  `blocking_activity_status` e `blocking_activity_cargo` da atividade predecessora
  (resolvida via `ActivityDependency`), em `tests/api/routers/test_kanban_blocking_context.py`.
- [X] T035 [P] [US3] Teste de API: item `EM_ANDAMENTO` cujo `cargo` é resolvido (T004)
  para o usuário autenticado vem com `actionable_now: true`; um item `EM_ANDAMENTO` sob
  cargo de outra pessoa vem com `actionable_now: false`, mesmo arquivo de T034.

### Implementation for User Story 3

- [X] T036 [US3] Estender `blocking_activity_key` em `GET /activities/kanban`
  (`src/pivma/routers/activities.py` + `src/pivma/schemas.py`) para incluir também
  `blocking_activity_status` e `blocking_activity_cargo`, resolvendo a atividade
  predecessora inteira via `ActivityDependency`, não só sua chave.
- [X] T037 [US3] Adicionar `actionable_now: bool` a cada item do Kanban: `true` quando
  `resolve_activity_holders(process_id, cargo)` (T004) inclui o usuário autenticado,
  em `src/pivma/routers/activities.py`.
- [X] T038 [US3] Atualizar `demos/kanban/index.html` (T025/T033) para destacar
  visualmente cartões `actionable_now` e exibir o contexto do predecessor ao expandir um
  cartão `NAO_INICIADO` (spec FR-009/FR-010, SC-003).

**Checkpoint**: as três user stories funcionais de ponta a ponta.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: fechar os portões de qualidade da Constituição antes de considerar a spec
concluída.

- [X] T039 [P] Rodar `poe format` + `poe lint` + `poe test` (ou equivalentes `uv`) e
  corrigir qualquer violação remanescente (Constituição Princípio IV).
- [X] T040 [P] Executar manualmente os 4 cenários de `quickstart.md` contra a API real
  (Cenários 1-4), confirmando os resultados esperados descritos em cada um.
- [X] T041 [P] Adicionar `run_seed_kanban()` (T024/T032) ao fluxo de
  `scripts/seeds/seed_all.py`, mantendo o padrão numerado (`[N/N] Semeando...`) já usado
  pelos demais seeds.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: sem dependências externas — bloqueia todas as user
  stories (vocabulário de cargo, visibilidade e remoção do vínculo pessoa-atividade são
  pré-requisitos estruturais de US1, US2 e US3).
- **User Story 1 (Phase 3)**: depende só de Foundational. Entrega o MVP.
- **User Story 2 (Phase 4)**: depende de Foundational **e** de US1 (T022/T024/T025 —
  estende o mesmo endpoint, seed e demo do Kanban em vez de criar os seus).
- **User Story 3 (Phase 5)**: depende de Foundational **e** de US1 (mesma razão de US2);
  independente de US2.
- **Polish (Phase 6)**: depende de todas as user stories desejadas estarem completas.

### User Story Dependencies

- **US1 (P1)**: nenhuma dependência de outra user story.
- **US2 (P1)**: reaproveita o endpoint/seed/demo de US1 para se tornar demonstrável;
  sua parte de autorização (T001-T010) já está pronta ao fim de Foundational.
- **US3 (P2)**: mesma relação de reaproveitamento com US1; nenhuma dependência de US2.

### Within Each User Story

- Testes antes da implementação correspondente.
- Schemas/funções puras antes do endpoint que as usa.
- Endpoint antes de seed/demo que o consomem.

### Parallel Opportunities

- Dentro de Foundational: T002, T003, T004 (funções puras em arquivos/trechos
  independentes) e T009, T010 (rotas diferentes) em paralelo; T011-T016 (todos os testes)
  em paralelo entre si, após as implementações correspondentes.
- Dentro de US1: T017, T018 (testes) em paralelo; T021 (schemas) em paralelo com T019
  (YAML) e T020 (função pura).
- US2 e US3 podem ser implementadas em paralelo por pessoas diferentes depois que US1
  estiver completa (ambas só estendem o mesmo endpoint em pontos distintos do payload).

---

## Parallel Example: Foundational

```bash
# Funções puras de autorização, em paralelo (mesmo arquivo, trechos independentes
# só depois de resolvido o conflito de merge; times pequenos preferem sequencial aqui):
Task: "Implementar has_platform_wide_access em src/pivma/core/authorization.py"
Task: "Implementar active_participant_process_scope em src/pivma/core/authorization.py"
Task: "Implementar resolve_activity_holders em src/pivma/core/authorization.py"

# Correção de visibilidade, arquivos diferentes, sempre em paralelo:
Task: "Aplicar visibilidade corrigida em src/pivma/routers/processes.py"
Task: "Aplicar visibilidade corrigida em src/pivma/routers/tasks.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 2: Foundational (crítico — bloqueia tudo).
2. Completar Phase 3: User Story 1.
3. **PARAR e VALIDAR**: rodar o Cenário 1 de `quickstart.md` isoladamente.
4. Demonstrar via `demos/kanban/`.

### Incremental Delivery

1. Foundational → base pronta.
2. US1 → Kanban consolidado utilizável sozinho (MVP).
3. US2 → mesma base, evidencia o recorte de cargos lado a lado.
4. US3 → mesma base, adiciona o contexto de ordem/predecessor.
5. Cada história soma valor sem quebrar a anterior — todas convergem no mesmo endpoint
   e na mesma demo, sem caminho paralelo (Constituição, proibição de modelo duplicado).
