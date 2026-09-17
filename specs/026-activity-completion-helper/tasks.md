---

description: "Task list for Helper Único de Conclusão de Atividade (Issue #22)"
---

# Tasks: Helper Único de Conclusão de Atividade (Issue #22)

**Input**: Design documents from `/specs/026-activity-completion-helper/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (contracts/ vazio deliberadamente — sem mudança de contrato)

**Tests**: Incluídos e obrigatórios nesta feature (spec.md FR-008/FR-009 exigem
suíte verde + teste unitário isolado do helper). Antes de qualquer tarefa de
teste abaixo, chame `Skill({skill: "fastapi-testing-methodology"})` — exigido
pelo `AGENTS.md`/`CLAUDE.md` deste projeto para criar ou alterar testes.

**Organization**: Fase 2 concentra o refactor em si (é um único mecanismo
compartilhado pelas três user stories, não divisível em fatias
independentes de código); as fases 3-5 contêm os testes/validações que
provam cada user story, mais as tarefas de teste de regressão específicas de
cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa incompleta)
- **[Story]**: US1, US2 ou US3 (spec.md)

## Path Conventions

Projeto único (backend FastAPI): `src/pivma/`, `tests/` na raiz do repositório.

---

## Phase 1: Setup

Nenhuma tarefa de setup necessária — branch (`chore/026-activity-completion-helper`)
e ambiente já existentes; nenhuma dependência nova, nenhuma migração.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: O refactor em si — um único helper de conclusão e a absorção do
caminho bespoke da triagem pelo motor genérico de dependências. É pré-requisito
bloqueante para todas as user stories: nenhuma delas é observável sem esta
fase completa.

**⚠️ CRITICAL**: Nenhuma tarefa das fases 3-5 pode começar antes desta fase.

- [X] T001 Criar o helper `_complete_activity_run(session, run, act, user_id)`
  em `src/pivma/core/process_engine.py` (próximo a `_activate_activity`,
  antes de `submit_proposal_form`), encapsulando exatamente o bloco hoje
  duplicado: `run.status = 'COMPLETED'`, `run.completed_at = utc_now()`,
  `run.set_update_audit(user_id)`; `act.status = 'COMPLETED'`,
  `act.set_update_audit(user_id)`; e, para cada `Task` não deletada dessa
  `run` (`Task.activity_run_id == run.id`, `Task.deleted_at.is_(None)`),
  `status = 'COMPLETED'`, `completed_at = utc_now()`,
  `set_update_audit(user_id)`.
- [X] T002 Adicionar o parâmetro opcional `task_title: str | None = None` a
  `_activate_activity` em `src/pivma/core/process_engine.py` (~linha 1732):
  ao criar a `Task`, usar `title=task_title or act.name` em vez do
  `title=act.name` fixo atual — comportamento padrão (`None`) idêntico ao de
  hoje para todo chamador que não passar o parâmetro. **Achado durante a
  implementação, fora do escopo original desta tarefa**: `_activate_activity`
  também tinha `run_number=1` hardcoded — inofensivo enquanto só era chamada
  uma vez por atividade, mas quebraria o incremento de rodada da triagem
  (FR-004) se não corrigido. Corrigido na mesma tarefa: `run_number` agora é
  `max(run_numbers já existentes para a atividade) + 1`.
- [X] T003 Estender `_advance_dependent_activities` em
  `src/pivma/core/process_engine.py` (~linha 1796) para aceitar um parâmetro
  opcional `task_titles: dict[str, str] | None = None`, repassando
  `task_titles.get(dependent_act.key)` como `task_title` na chamada a
  `_activate_activity` (T002) — `None`/ausente preserva o comportamento
  padrão (`act.name`) para toda atividade que não estiver no dicionário.
- [X] T004 Substituir o bloco duplicado de conclusão em `submit_proposal_form`
  (`src/pivma/core/process_engine.py`, ~linhas 1918-1931 — `current_run.status
  = 'COMPLETED'` até o loop de `Task`) por uma chamada a
  `_complete_activity_run(session, current_run, act, user_id)` (T001).
- [X] T005 Substituir o bloco duplicado de conclusão em
  `execute_triage_decision` (`src/pivma/core/process_engine.py`, ~linhas
  2292-2302) por uma chamada a `_complete_activity_run(session, triage_run,
  triage_act, user_id)` (T001). **Achado durante a implementação**: o
  bloco comum não marcava `triage_act.status`; isso ficava a cargo de cada
  handler de resultado (`_handle_approved_decision`/`_handle_rejected_decision`
  redundantemente ajustavam para `'COMPLETED'`; `_handle_needs_revision`
  sobrescrevia para `'BLOCKED'` depois). `_complete_activity_run` já marca
  `act.status = 'COMPLETED'`; removida a atribuição redundante dos dois
  primeiros handlers (mesmo resultado final, sem duplicar a atribuição) —
  `_handle_needs_revision` continua sobrescrevendo por último, sem mudança de
  comportamento.
- [X] T006 Na branch "sem avaliação por IA associada" de `submit_proposal_form`
  (`src/pivma/core/process_engine.py`, ~linhas 2002-2007), substituir `await
  _unblock_triage_activity(session, process_id, user_id)` por `await
  _advance_dependent_activities(session, process, act, user_id,
  task_titles={'triage_evaluation': TRIAGE_TASK_TITLE})` (depende de T003;
  `process` e `act`/submission `ActivityInstance` já estão no escopo da
  função; `TRIAGE_TASK_TITLE` é uma constante nova do módulo, para não
  repetir o literal em 3 lugares).
- [X] T007 Em `src/pivma/core/pre_evaluation_service.py`, na branch
  `consolidation.result == 'positive'` de `_execute` (~linhas 205-209),
  substituir `await _unblock_triage_activity(session, run.process_instance_id,
  run.created_by)` por: obter a `ActivityInstance` da submissão (novo helper
  `_submission_activity`, mesmo padrão de `_triage_activity` já existente
  neste arquivo) e chamar `_advance_dependent_activities(session, process,
  submission_act, run.created_by, task_titles={'triage_evaluation':
  TRIAGE_TASK_TITLE})` (depende de T003; `process` já está no escopo local).
- [X] T008 Em `src/pivma/core/pre_evaluation_service.py`, em
  `request_direct_review` (~linha 316), aplicar a mesma substituição de T007
  — precisou também carregar `process` via `session.get(ProcessInstance,
  process_id)` (não estava no escopo local desta função, diferente de
  `_execute`). **Achado durante a implementação, só detectado pelo teste de
  regressão (T020) falhando**: neste caminho especificamente, a submissão
  está `IN_PROGRESS` (rodada reaberta por `_return_to_proponent` após
  resultado negativo/falho da IA), não `COMPLETED` — o motor genérico
  (`_dependency_satisfied`) recusava destravar a triagem porque a dependência
  declarada exige `proposal_submission` `COMPLETED`. A revisão direta é
  precisamente um bypass intencional dessa regra (o proponente pula a IA e
  força a triagem humana). Corrigido em `_close_open_submission_run`: ao
  cancelar a rodada aberta, agora também marca a `ActivityInstance` da
  submissão como `COMPLETED`, satisfazendo a dependência genuinamente em vez
  de rotear ao redor dela.
- [X] T009 Remover `_unblock_triage_activity` de
  `src/pivma/core/process_engine.py` (~linhas 1666-1715) e seu import em
  `src/pivma/core/pre_evaluation_service.py` (linha 51) — depende de T004,
  T006, T007, T008 (todos os chamadores já migrados). **Achado durante a
  implementação, fora do escopo original**: a função definia
  `triage_act.status = 'READY'` na ativação; `_activate_activity` (motor
  genérico) usa `'IN_PROGRESS'` — o valor já usado por toda outra atividade
  do sistema quando ativada (`proposal_submission`, `planning_preview`), sem
  nenhum consumidor de API que distinga os dois valores (só `'BLOCKED'` e
  `'COMPLETED'` são tratados de forma especial em `classify_kanban_column` e
  no Kanban/tasks). Decisão: alinhar a triagem à convenção já usada em todo o
  resto do motor (`'IN_PROGRESS'`) em vez de preservar `'READY'` como um
  terceiro caso especial — mantém o objetivo da issue (parar de tratar a
  triagem como exceção). Sem efeito de API observável; 4 testes que
  asseguravam o literal `'READY'` precisam de ajuste (ver T014b).
- [X] T010 Atualizar o docstring de `_template_activity_data` em
  `src/pivma/core/process_engine.py` (~linhas 486-491), que hoje cita
  `_unblock_triage_activity` e `_open_new_submission_run` como "caminhos
  legados" — `_unblock_triage_activity` não existe mais depois de T009;
  ajustar o texto para citar só `_open_new_submission_run` como caminho
  restante que resolve atividade por chave (fora do escopo desta feature).
  Também atualizado um comentário desatualizado em
  `demos/kanban/index.html` (~linhas 188-196) que citava a função removida
  ao explicar por que a demo casa tarefas por título.

**Checkpoint**: Com T001-T010 concluídas, o motor de processos tem um único
caminho para "concluir e destravar dependentes"; as fases seguintes só
adicionam prova (testes) e validação manual — não há mais lógica nova a
escrever depois deste ponto.

---

## Phase 3: User Story 1 - Pendência da nova rodada de triagem (Priority: P1) 🎯 MVP

**Goal**: Depois de uma diligência de triagem e reenvio do proponente, a
pessoa responsável pela triagem vê uma tarefa `READY` própria dessa rodada,
com prazo recalculado a partir do início dela.

**Independent Test**: Rodar submissão → diligência (`NEEDS_REVISION`) →
reenvio e confirmar via `GET /tasks?status=READY` que existe uma tarefa de
triagem para a nova rodada, distinta da tarefa (já concluída) da primeira.

### Tests for User Story 1 ⚠️

> Chame `Skill({skill: "fastapi-testing-methodology"})` antes desta subfase.
> Escreva/ajuste os testes e confirme que falham contra o código pré-T001-T010
> antes de prosseguir (o helper ainda não existe nesse ponto se a
> implementação for feita em TDD estrito; se a Fase 2 já estiver
> implementada, confirme que os testes antigos falhavam com o comportamento
> anterior, via `git stash`/checkout do estado pré-mudança, ou documente que
> a ordem foi invertida).

- [X] T011 [P] [US1] Em
  `tests/api/routers/test_triage_decision.py::test_triage_decision_needs_revision_and_resubmission`,
  adicionar asserts após o reenvio (~linha 113, após `resubmit_resp`):
  consultar a `ActivityRun` de `triage_evaluation` mais recente e confirmar
  `run_number == 2` (era travado em `1`), e que existe uma `Task` distinta
  (por `id`) da tarefa da rodada 1, com `status == 'READY'`.
- [X] T012 [P] [US1] No mesmo teste (ou um novo, no mesmo arquivo), autenticar
  como `triador` e chamar `GET /tasks?process_id={process_id}&status=READY`;
  confirmar que a resposta contém a tarefa da rodada 2 da triagem (hoje a
  lista vem vazia para essa combinação depois do reenvio — bug a corrigir).
- [X] T013 [P] [US1] Em `tests/api/routers/test_activities_kanban.py` (ou
  arquivo equivalente de teste do Kanban), adicionar um teste (ou estender um
  existente) cobrindo o mesmo cenário de diligência+reenvio: confirmar que o
  card de `triage_evaluation` no `GET /activities/kanban` reporta
  `run_started_at` igual ao início da rodada 2, não da rodada 1.
- [X] T014 [US1] Atualizar
  `tests/unit/core/test_activity_due_date.py::test_triage_evaluation_gets_own_due_date_via_legacy_unblock`
  (linhas 98-129): renomear o teste (remover "via_legacy_unblock", já que o
  caminho deixa de ser bespoke) e ajustar o docstring (linhas 102-106) para
  não citar `_unblock_triage_activity`, que não existe mais depois de T009 —
  as asserções existentes (linhas 125-129) já continuam válidas sem mudança.
- [X] T014b [P] [US1] Ajustar os 4 testes que hoje esperam
  `triage_act.status == 'READY'` para `== 'IN_PROGRESS'` (achado T009):
  `tests/integration/ai/test_run_pre_evaluation.py:110`,
  `tests/integration/ai/test_pre_evaluation_skips_attachments.py:123`,
  `tests/unit/core/test_triage_decoupled_form.py:67`,
  `tests/unit/core/test_process_engine.py:102`.

### Implementation for User Story 1

Nenhuma implementação adicional — entregue integralmente pela Fase 2
(T001-T010). Esta subfase é intencionalmente só validação.

- [~] T015 [US1] Rodar manualmente os passos 1-6 de `quickstart.md` contra a
  API local (`poe serve` + `demos/triage/index.html`) e confirmar o
  resultado esperado de cada passo antes de prosseguir. **Não executado
  manualmente nesta sessão** (sem navegador disponível no ambiente) — os
  mesmos passos foram exercitados e confirmados via teste de API automatizado
  equivalente (T011/T012, que reproduzem exatamente o fluxo submissão →
  diligência → reenvio → checagem de `GET /tasks`). Recomendo uma passada
  manual pela demo antes do merge, como evidência end-to-end contra a API
  real (AGENTS.md, Regra 3).

**Checkpoint**: User Story 1 completa e testável de ponta a ponta — já é um
incremento entregável (MVP) por si só.

---

## Phase 4: User Story 2 - Único ponto de manutenção no motor (Priority: P2)

**Goal**: Os quatro pontos de conclusão de atividade usam a mesma
implementação, verificável por inspeção e coberta por teste unitário
isolado do helper.

**Independent Test**: Inspecionar os quatro pontos de chamada e confirmar
ausência de bloco duplicado; rodar o teste unitário do helper isoladamente.

### Tests for User Story 2 ⚠️

> Chame `Skill({skill: "fastapi-testing-methodology"})` antes desta subfase,
> se ainda não foi chamada nesta sessão de implementação.

- [X] T016 [P] [US2] Criar teste unitário isolado em
  `tests/unit/core/test_process_engine.py` para `_complete_activity_run`
  (FR-009): fabricar (ou usar factories já existentes) uma `ActivityRun` em
  `IN_PROGRESS`, sua `ActivityInstance` e uma ou mais `Task` `READY`
  associadas; chamar o helper diretamente; confirmar que todas passam a
  `COMPLETED` com `completed_at` preenchido — sem depender de
  `submit_proposal_form` nem `execute_triage_decision`.

### Implementation for User Story 2

Nenhuma implementação adicional — entregue integralmente pela Fase 2.

- [X] T017 [US2] Documentar no PR (não é código) a verificação por inspeção
  (SC-003): os quatro pontos — `submit_proposal_form`,
  `execute_triage_decision`, `pre_evaluation_service._execute`,
  `pre_evaluation_service.request_direct_review` — usam exclusivamente
  `_complete_activity_run` e/ou `_advance_dependent_activities`, sem bloco de
  conclusão duplicado remanescente em nenhum dos dois módulos. **Confirmado
  por grep**: `run.status = 'COMPLETED'`/`act.status = 'COMPLETED'`/
  `t.status = 'COMPLETED'` só aparecem juntos dentro da definição de
  `_complete_activity_run`; os dois pontos que concluíam run/atividade/tasks
  inline agora só chamam essa função. As duas ocorrências avulsas restantes
  (`phase.status`, em `_handle_approved_decision`; `submission_act.status`,
  no fix de T008) são de entidades diferentes, não duplicatas do mesmo bloco.

**Checkpoint**: User Stories 1 e 2 completas e testáveis independentemente.

---

## Phase 5: User Story 3 - Auditoria consistente do desbloqueio da triagem (Priority: P3)

**Goal**: A linha do tempo do processo registra o desbloqueio da triagem
(evento `ACTIVITY_UNBLOCKED`) pelos três caminhos que a destravam, assim como
já registra para qualquer outra atividade dependente.

**Independent Test**: Destravar a triagem por cada um dos três caminhos e
confirmar o evento na timeline.

### Tests for User Story 3 ⚠️

- [X] T018b Achado só pela suíte completa (T022), fora da lista original:
  `tests/api/routers/test_timeline_router.py::test_process_timeline_events_recorded_and_ordered`
  trava a ordem exata dos `event_type` da timeline e passou a falhar —
  `ACTIVITY_UNBLOCKED` aparecia entre `FORM_DRAFT_SAVED` e
  `SUBMISSION_SUBMITTED` (efeito antes da causa na narrativa), porque em
  `submit_proposal_form` o evento `SUBMISSION_SUBMITTED` só era adicionado ao
  final da função, depois da chamada a `_advance_dependent_activities` no
  ramo sem IA. Corrigido movendo o `AuditEvent` de `SUBMISSION_SUBMITTED` para
  antes do `if has_assignments`/`else` (mesma convenção já usada em
  `_handle_approved_decision`: evento-causa antes de destravar dependentes) —
  teste atualizado para incluir `ACTIVITY_UNBLOCKED` na posição correta.
- [X] T018 [P] [US3] Em `tests/api/routers/test_triage_decision.py`, no
  cenário de reenvio pós-diligência (mesmo teste de T011), adicionar assert
  confirmando um `AuditEvent` do tipo `ACTIVITY_UNBLOCKED` com
  `context_data['activity_key'] == 'triage_evaluation'` gerado após o
  reenvio — ausente hoje.
- [X] T019 [P] [US3] Em `tests/integration/ai/test_run_pre_evaluation.py` (ou
  arquivo equivalente que já cubra `consolidated_result == 'positive'`),
  adicionar o mesmo assert de `ACTIVITY_UNBLOCKED` para o caminho da
  pré-avaliação por IA.
- [X] T020 [P] [US3] Em `tests/api/routers/test_direct_review.py`, adicionar
  o mesmo assert de `ACTIVITY_UNBLOCKED` para o caminho de revisão direta.

### Implementation for User Story 3

Nenhuma implementação adicional — o evento é emitido automaticamente por
`_advance_dependent_activities` (já existente), consequência de T006-T008.

- [~] T021 [US3] Rodar manualmente o passo 7 de `quickstart.md` (`GET
  /processes/{id}/timeline`) e confirmar visualmente o evento novo. **Não
  executado manualmente** (mesmo motivo de T015) — coberto por teste
  automatizado equivalente em T018/T019/T020, que consultam `AuditEvent`
  diretamente pelos três caminhos de desbloqueio.

**Checkpoint**: Todas as user stories completas e testáveis
independentemente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Fechamento da entrega — suíte completa, changelog e preparação
do PR.

- [X] T022 Rodar a suíte completa (`pytest`, via `poe test` ou equivalente do
  `pyproject.toml`) e confirmar 100% de sucesso (SC-004), incluindo os testes
  atualizados nas fases 3-5. **697 passed, 1 skipped** na rodada final. A
  primeira tentativa deu 697 erros uniformes (até em testes sem banco) por
  contenção de conexão/lock com um `fastapi dev` já rodando contra o mesmo
  Postgres do `.env` — confirmado pela ausência do problema ao rodar cada
  arquivo isoladamente. Parado com autorização do usuário antes de repetir a
  suíte completa; não é um problema introduzido por esta feature.
- [X] T023 Rodar `ruff check` e `ruff format --check` (ou `poe lint`) sobre
  `src/pivma/core/process_engine.py`, `src/pivma/core/pre_evaluation_service.py`
  e os arquivos de teste alterados. `ruff check` limpo (2 achados corrigidos:
  `_activate_activity` passou de 5 para 6 argumentos, precisou de
  `# noqa: PLR0913, PLR0917`, mesmo padrão já usado em outras funções do
  arquivo; uma linha longa em `test_run_pre_evaluation.py`). `ruff format
  --check` aponta 1 arquivo (`tests/unit/core/test_activity_due_date.py`)
  com formatação pré-existente fora do padrão do `ruff format` — confirmado
  via `git stash` que já estava assim antes desta feature, em linhas que não
  editei; fora de escopo, não corrigido.
- [X] T024 Revisar `specs/026-activity-completion-helper/CHANGELOG.md` contra
  o comportamento efetivamente implementado e validado nas fases 3-5; remover
  a nota de rascunho do topo do arquivo quando confirmado. Todos os 4 itens
  batem com o que os testes automatizados confirmaram; nota de rascunho
  removida.
- [ ] T025 Preparar o commit/PR: `git status` e `git add` seletivo, incluindo
  **só** os arquivos desta feature (`src/pivma/core/process_engine.py`,
  `src/pivma/core/pre_evaluation_service.py`, os arquivos de teste alterados
  e `specs/026-activity-completion-helper/`) — a branch foi criada a partir
  de `develop` com um WIP não commitado e não relacionado (specs/025,
  migrations, `docs/`, `mkdocs.yml`, etc.) que não deve entrar neste PR.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: Sem dependência de Setup (Fase 1 vazia) —
  BLOQUEIA as fases 3-5 por completo (T001-T010 formam uma cadeia de
  dependência interna: T002→T003→T006/T007/T008→T009→T010; T001 é
  independente até ser consumida por T004/T005).
- **User Stories (Fases 3-5)**: Todas dependem só da Fase 2 completa; entre
  si, são independentes (nenhuma altera código usada por outra) e podem ser
  feitas em qualquer ordem ou em paralelo por pessoas diferentes.
- **Polish (Fase 6)**: Depende de todas as fases anteriores.

### Parallel Opportunities

- Dentro da Fase 2: nenhuma tarefa é `[P]` — todas tocam
  `process_engine.py`/`pre_evaluation_service.py` em sequência de
  dependência.
- Fases 3, 4 e 5 podem ser trabalhadas em paralelo por pessoas diferentes
  depois do checkpoint da Fase 2.
- Dentro de cada fase de user story, as tarefas de teste marcadas `[P]`
  (T011-T013, T016, T018-T020) tocam arquivos de teste diferentes entre si e
  podem rodar em paralelo.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Completar Fase 2 (Foundational) — é o refactor inteiro.
2. Completar Fase 3 (User Story 1) — validação do bug corrigido.
3. **Parar e validar**: rodar `quickstart.md` passos 1-6 e a suíte de testes.
4. A essa altura já há um incremento entregável (o bug da issue está
   corrigido e coberto por teste).

### Incremental Delivery

1. Fase 2 → Fase 3 (US1, MVP) → Fase 4 (US2) → Fase 5 (US3) → Fase 6
   (Polish/PR). Como as fases 3-5 são só teste/validação sobre o mesmo
   código já escrito na Fase 2, a entrega real é atômica — a divisão em
   fases serve para checkpoints de revisão, não para deploys parciais.

## Notes

- `[P]` = arquivos de teste diferentes, sem dependência entre si.
- `[Story]` mapeia a tarefa à user story correspondente da spec.
- Nenhuma tarefa de implementação fica fora da Fase 2 — as fases 3-5 são
  deliberadamente só teste e validação, refletindo que esta é uma correção
  atômica, não um conjunto de fatias de produto independentes.
- Antes de tocar em qualquer arquivo de teste, chamar
  `Skill({skill: "fastapi-testing-methodology"})` (exigido pelo `AGENTS.md`
  via `CLAUDE.md` deste projeto).
- Ao final (T025), lembrar que a branch tem WIP não commitado e alheio a esta
  feature na working tree — só adicionar ao commit os arquivos listados.
