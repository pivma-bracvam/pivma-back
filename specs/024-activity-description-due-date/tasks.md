---

description: "Task list for Feature 024 - Prazo Real (due_date) das Atividades"
---

# Tasks: Prazo Real (due_date) das Atividades

**Input**: Design documents from `/specs/024-activity-description-due-date/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/tasks-due-date.md, quickstart.md

**Tests**: Incluídas — não foram pedidas explicitamente na spec, mas seguem a
convenção já usada no projeto (ex.: Spec 017 cobriu o comportamento default de
`activity_type` com um teste unitário dedicado).

**Skills obrigatórias (CLAUDE.md)**: antes de tocar em código, chame
`Skill({skill: "andrej-karpathy-skills:karpathy-guidelines"})`. Antes de
escrever ou alterar qualquer teste (T005, T006), chame
`Skill({skill: "fastapi-testing-methodology"})`. Isso vale para quem for
executar estas tasks, não foi feito neste comando.

**Organization**: Uma única User Story (US1, P1) — esta spec tem escopo
deliberadamente básico (spec.md, Assumptions).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: US1 = única user story desta spec
- Caminhos de arquivo exatos em cada descrição

## Path Conventions

Projeto único (`src/pivma`, `tests/`, `demos/`, `scripts/seeds/`) — sem
frontend/mobile separado (plan.md, Structure Decision).

---

## Phase 1: Setup

**Purpose**: Confirmar baseline antes de qualquer mudança — não há
dependência nova nem migração de schema para esta feature (plan.md,
Technical Context: `Task.due_date` já existe na tabela `tasks`).

- [X] T001 Rodar `poe test` para registrar a suíte completa passando antes de
      qualquer alteração. **Nota**: o Docker só ficou disponível nesta
      sandbox depois que T002–T009 já estavam implementadas (a primeira
      tentativa, antes disso, falhou por `docker.errors.DockerException` —
      sem Docker acessível). Não existe, portanto, uma execução literal
      "antes de qualquer mudança"; o que confirma a ausência de regressão é
      a suíte completa em T011 (`poe`/`poethepoet` não está instalado no
      venv — rodado via `pytest -q` direto).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Motor de processos passa a calcular e persistir `due_date` — é
o que a única user story desta spec depende para existir.

**⚠️ CRITICAL**: Nenhuma task da Fase 3 pode começar antes desta fase estar
completa.

- [X] T002 Em `src/pivma/core/process_engine.py`, criar uma função auxiliar
      pequena e pura que recebe `run_started_at: datetime | None` e
      `sla_hours: int | None` e devolve o `due_date` calculado
      (`run_started_at + timedelta(hours=sla_hours)`) ou `None` quando
      `sla_hours` for `None` — reaproveitando literalmente a mesma fórmula já
      usada por `classify_kanban_column` (data-model.md § "Regra de
      derivação"; research.md § 2), para não divergir dela (FR-003).
- [X] T003 Em `_init_first_activity` (`src/pivma/core/process_engine.py`),
      usar a função de T002 para definir `Task.due_date` no momento da
      criação da primeira tarefa do processo, a partir de
      `run.started_at`/`a_data.get('sla_hours')` (FR-001, FR-002).
- [X] T004 Em `_activate_activity` (`src/pivma/core/process_engine.py`),
      usar a mesma função de T002 para definir `Task.due_date` no momento da
      criação da tarefa de qualquer atividade desbloqueada por dependência, a
      partir do `run.started_at` desse novo ciclo — nunca reaproveitando o
      `due_date` de um ciclo (`ActivityRun`) anterior (FR-001; Edge Case:
      retrabalho/novo ciclo de execução). **Insuficiente sozinha** — ver T013
      e T014, achadas durante a validação manual (T010): existem mais dois
      pontos que criam `Task` e não passam por `_activate_activity`.
- [X] T005 Criar `tests/unit/core/test_activity_due_date.py`. **Revisado**:
      a primeira versão usava um template sintético (como
      `test_activity_type_default.py`) e passava, mas escondia uma lacuna
      real — reescrito para usar o template oficial
      `validated_method_dossier` (`bootstrap_all_templates`) e cobrir os
      4 pontos que criam `Task` (achado em T010, ver `research.md`): (a)
      primeira atividade (`_init_first_activity`); (b) `triage_evaluation`
      desbloqueada por `_unblock_triage_activity` (caminho legado, usado por
      praticamente todo processo real — é onde a lacuna estava); (c)
      `planning_preview` (sem `sla_hours`) desbloqueada por
      `_activate_activity` via aprovação de triagem; (d) reabertura de
      `proposal_submission` por `_open_new_submission_run` após
      `NEEDS_REVISION` — ganha `due_date` próprio, não herdado do ciclo
      anterior. 4 testes, todos verdes.

**Checkpoint**: motor de processos persiste `due_date` corretamente — US1
pode começar.

---

## Phase 3: User Story 1 - Consultar o prazo real de uma tarefa em andamento (Priority: P1) 🎯 MVP

**Goal**: Quem é responsável por uma tarefa, ou gerencia o processo, vê uma
data-limite concreta ao consultar `GET /tasks` ou `GET /tasks/{id}`, sem
precisar calculá-la a partir do início da execução e do SLA (spec.md, US1).

**Independent Test**: `quickstart.md` passos 1–6 — ativar uma atividade com
`sla_hours`, confirmar `due_date` preenchido em `GET /tasks` e
`GET /tasks/{id}`, e que é consistente com a classificação "em atraso" já
existente no kanban.

### Tests for User Story 1 ⚠️

> Escrever esta task ANTES da implementação (T007–T009) e confirmar que
> falha, por causa do campo ausente em `TaskDetail`/valor sempre nulo.

- [X] T006 [US1] Em `tests/api/routers/test_tasks_router.py`, adicionar
      casos cobrindo o contrato de `contracts/tasks-due-date.md`: (a)
      `GET /tasks` retorna `due_date` preenchido para uma tarefa cuja
      atividade declara `sla_hours`, e `null` para uma que não declara
      (comportamento; `TaskSummary` já tem o campo, só o valor muda); (b)
      `GET /tasks/{id}` também retorna `due_date` (campo novo em
      `TaskDetail`) com a mesma regra.

### Implementation for User Story 1

- [X] T007 [US1] Em `src/pivma/schemas.py`, acrescentar
      `due_date: datetime | None = None` a `TaskDetail` (contracts/tasks-due-date.md
      — `TaskSummary` já declara o campo, `TaskDetail` ainda não).
- [X] T008 [US1] Em `get_task_detail` (`src/pivma/routers/tasks.py`), passar
      `due_date=t.due_date` na construção do `TaskDetail` de resposta
      (depende de T007).
- [X] T009 [US1] Estender `demos/kanban/index.html` para, ao exibir um card,
      buscar `GET /tasks?process_id={id}` e mostrar a data-limite ao lado da
      linha já existente de `sla_hours`/`run_started_at` (research.md § 5;
      `scripts/seeds/seed_kanban.py` não precisa mudar — os templates
      oficiais já declaram `sla_hours`). **Corrigido após T010**: o
      casamento entre o card e a `Task` é por título (`GET /tasks` não tem
      `activity_key`), e o motor gera esse título de 5 formas diferentes
      conforme o caminho de ativação — a primeira versão só cobria 2 e
      deixava de mostrar o prazo justamente no card mais comum
      (`triage_evaluation`, criado por `_unblock_triage_activity` com um
      título fixo que não usa o nome da atividade). Lista exaustiva dos 5
      títulos agora embutida no JS, conferida contra `process_engine.py`.
- [X] T010 [US1] Executar manualmente os passos 1–6 de `quickstart.md` contra
      a API real (Docker disponibilizado pelo usuário) e confirmar que o
      `due_date` observado em `GET /tasks`/`GET /tasks/{id}` bate com a
      classificação de coluna do kanban para a mesma atividade (AGENTS.md,
      demonstração como critério de conclusão; FR-003). **Executado via
      `docker compose up -d db` + `alembic upgrade head` +
      `fastapi run` local + `scripts.seeds.seed_kanban` + chamadas reais à
      API (login, `POST /processes`, submissão de formulário, `GET /tasks`,
      `GET /tasks/{id}`)**: confirmado devido a
      2026-09-22T11:15:40Z = início (2026-09-15T11:15:40Z) + 168h para
      `proposal_submission`, e devido a 2026-09-18T11:15:54Z = início
      (2026-09-15T11:15:54Z) + 72h para `triage_evaluation` — os dois
      batendo entre `GET /tasks` e `GET /tasks/{id}`. **Essa validação foi o
      que revelou a lacuna de T013/T014** (o primeiro processo inspecionado,
      semeado por uma execução anterior do seed, mostrou `triage_evaluation`
      em `EM_ATRASO` no kanban mas `due_date: null` em `GET /tasks` — só
      depois de criar um processo novo e corrigir `_unblock_triage_activity`
      o valor passou a bater).

**Checkpoint**: US1 completa e testável de ponta a ponta — esta spec não tem
mais nenhuma user story além desta.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Confirmar ausência de regressão antes de considerar a spec
concluída.

- [X] T011 [P] Rodar `poe test` novamente e comparar com o baseline de T001 —
      nenhuma regressão esperada em
      `tests/unit/core/test_kanban_column_classification.py` nem nos demais
      testes de `test_tasks_router.py`/`test_process_engine.py` (SC-002: a
      classificação "em atraso" permanece idêntica à observada antes desta
      mudança). **Executado** (`pytest -q`, `poe` indisponível no venv):
      **700 passed, 1 skipped**, zero falhas — inclui os 4 testes novos de
      `test_activity_due_date.py`, o teste novo de `test_tasks_router.py`, e
      toda a suíte pré-existente sem regressão. `ruff check .` limpo.
- [X] T012 Confirmar, por inspeção do código alterado em T003/T004, que
      `sla_hours` continua sendo lido de
      `template_version.definition_payload` (o payload imutável associado à
      versão do template usada na instanciação) — sem task de código nova,
      só a garantia de que FR-004 (imutabilidade de versão) já vale por
      construção, sem regressão. Confirmado: `_init_first_activity` recebe
      `a_data` vindo de `_create_phases_and_activities`, que itera
      `payload.get('phases', [])` com `payload = template_version.definition_payload`
      (`instantiate_process`); `_activate_activity` recebe `a_data` de
      `_advance_dependent_activities`, que busca
      `session.get(ProcessTemplateVersion, process.template_version_id)` — a
      versão específica gravada na instância, nunca "a mais recente". Sem
      regressão.

---

## Fase 5: Achado durante a validação manual (T010)

**Contexto**: T010 revelou que a suposição de T002/plan.md/research.md —
"só dois pontos criam `Task`" — estava errada. Existem mais dois caminhos,
anteriores à Spec 017, que resolvem uma atividade pela chave (`'proposal_submission'`/
`'triage_evaluation'`) em vez de passar pelo motor genérico de dependências.
Sem estas duas tasks, `triage_evaluation` — a atividade mais comum de todo
processo real — nunca teria `due_date`.

- [X] T013 Em `_unblock_triage_activity` (`src/pivma/core/process_engine.py`),
      usar o novo helper `_template_activity_data` (busca `sla_hours` de
      `triage_evaluation` na versão do template da instância) e
      `_compute_activity_due_date` para preencher `due_date` na `Task`
      "Realizar Triagem da Proposta" — caminho hardcoded acionado por
      `submit_proposal_form` (sem avaliação por IA pendente) e por
      `pre_evaluation_service` (após pré-avaliação concluída), usado por
      todo processo instanciado dos 5 templates oficiais.
- [X] T014 Em `_open_new_submission_run` (`src/pivma/core/process_engine.py`),
      mesmo par de chamadas para `sla_hours` de `proposal_submission` e
      preencher `due_date` na `Task` do novo ciclo reaberto — caminho usado
      pela diligência de triagem (`NEEDS_REVISION`) e pelo retorno
      automático da pré-avaliação por IA (Edge Case de retrabalho, já
      previsto em `spec.md`, agora coberto de fato neste caminho também).

`tests/unit/core/test_activity_due_date.py` (T005, reescrito) e a validação
manual (T010) cobrem as duas.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — T001 pode rodar imediatamente.
- **Foundational (Phase 2)**: depende de T001 (baseline) só para referência
  de comparação futura, não bloqueia o início de T002. T002 → T003, T004 (na
  ordem, mesmo arquivo) → T005.
- **User Story 1 (Phase 3)**: depende da Fase 2 completa (o motor precisa
  estar persistindo `due_date` antes de expor/demonstrar o dado).
- **Polish (Phase 4)**: depende da Fase 3 completa.

### Within Phase 2 (Foundational)

- T002 antes de T003 e T004 (as duas usam a função criada em T002).
- T003 e T004 alteram o mesmo arquivo (`process_engine.py`) — não rodar em
  paralelo, mas a ordem entre elas é livre.
- T005 depende de T002–T004 já implementadas para poder passar.

### Within Phase 3 (User Story 1)

- T006 (teste) antes de T007–T009 (implementação), e deve falhar antes delas.
- T007 antes de T008 (T008 usa o campo criado em T007).
- T009 é independente de T007/T008 (arquivo e camada diferentes — front-end
  estático da demo), mas só faz sentido demonstrar depois que T003/T004
  (Fase 2) já persistem `due_date`.
- T010 depende de T006–T009 completas.

### Parallel Opportunities

- Nenhuma task de código desta spec é seguramente paralela entre si além de
  T009 (demo) em relação a T007/T008 (schema/router) — arquivos e camadas
  diferentes, sem dependência direta entre elas.
- T011 pode rodar em paralelo a T012 (T012 é só inspeção/confirmação, não
  edição de código).

---

## Parallel Example: User Story 1

```bash
# T007/T008 (schema + router) e T009 (demo) podem ser feitas por pessoas
# diferentes assim que a Fase 2 estiver completa, desde que T006 já exista
# (mesmo que ainda falhando) para orientar o contrato esperado:
Task: "Adicionar due_date a TaskDetail em src/pivma/schemas.py e preenchê-lo em get_task_detail (src/pivma/routers/tasks.py)"
Task: "Estender demos/kanban/index.html para exibir due_date via GET /tasks"
```

---

## Implementation Strategy

### MVP = a spec inteira

Como há uma única user story, o MVP desta spec é a spec completa:

1. Completar Fase 1 (Setup).
2. Completar Fase 2 (Foundational) — sem isso não há `due_date` para expor.
3. Completar Fase 3 (US1) — schema, router, demo, validação manual.
4. Completar Fase 4 (Polish) — confirmar zero regressão.
5. Usar o resultado (código + `quickstart.md` + este `tasks.md`) como
   referência concreta ao redigir a issue mencionada na conversa que originou
   esta spec — inclusive citando a lacuna de descrição por atividade
   (spec.md, Assumptions) como contexto para quem for desenvolvê-la depois.

---

## Notes

- [P] = arquivos diferentes, sem dependência direta.
- [US1] identifica a única user story desta spec, para rastreabilidade.
- Sem backfill, sem descrição de atividade, sem endpoint novo — por decisão
  já registrada em `spec.md` (Clarifications) e reforçada em `plan.md`
  (Constitution Check).
- Commitar após cada task ou grupo lógico (ex.: T002–T005 juntas, depois
  T006–T010 juntas).
