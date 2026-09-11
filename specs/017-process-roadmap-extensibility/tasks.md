---

description: "Task list for 017-process-roadmap-extensibility"
---

# Tasks: Roteiro Dinâmico e Extensibilidade de Atividades para Fases Futuras

**Input**: Design documents from `/specs/017-process-roadmap-extensibility/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/,
quickstart.md

**Tests**: incluídos — a Constituição do projeto (Princípio IV, NÃO NEGOCIÁVEL) exige
`ruff format`/`ruff check`/`pytest` antes de qualquer entrega, com testes seguindo a
skill `fastapi-testing-methodology` e a estrutura em níveis já estabelecida.

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

**Purpose**: extensão de schema e do motor de processos da qual as três histórias
dependem. Nenhuma história pode ser validada antes desta fase.

**⚠️ CRITICAL**: bloqueia todas as user stories.

- [x] T001 Gerar e escrever a migração Alembic que adiciona
  `activity_type VARCHAR(32) NOT NULL DEFAULT 'form'` à tabela `activity_instances`, com
  `downgrade` removendo a coluna, em `migrations/versions/<hash>_activity_instance_activity_type.py`
  (data-model.md §1).
- [x] T002 [P] Adicionar o campo `activity_type: Mapped[str] = mapped_column(String(32), default='form')`
  à classe `ActivityInstance` em `src/pivma/core/database/models.py` (data-model.md §1).
- [x] T003 Popular `activity_type` a partir de `a_data.get('activity_type', 'form')` ao
  criar cada `ActivityInstance` em `_create_phases_and_activities`, em
  `src/pivma/core/process_engine.py` (data-model.md §2).
- [x] T004 Implementar `_advance_dependent_activities(session, process, completed_act, user_id)`
  em `src/pivma/core/process_engine.py`: para cada `ActivityDependency` cujo
  `required_activity_id` seja `completed_act.id`, verificar se **todas** as dependências
  da atividade dependente estão satisfeitas (`required_activity.status == required_status`)
  e, em caso positivo, ativá-la — status `IN_PROGRESS`, `blocked_reason=None`, fase
  associada promovida de `NOT_STARTED` para `IN_PROGRESS`, `ActivityRun #1`
  (`status='IN_PROGRESS'`) criado, `Task` (`status='READY'`, `assigned_role` lido da
  definição YAML da atividade) criada, e `FormInstance` criada **somente se**
  `form_template_key` estiver presente na definição da atividade (data-model.md §4).
- [x] T005 Chamar `_advance_dependent_activities` a partir de `_handle_approved_decision`
  em `src/pivma/core/process_engine.py`, logo após marcar `ctx.triage_act` e sua fase
  como `COMPLETED`, passando `ctx.triage_act` como atividade concluída.
- [x] T006 [P] Registrar um `AuditEvent` (`event_type='ACTIVITY_UNBLOCKED'`,
  `context_data={'activity_key', 'activity_type'}`) para cada atividade ativada por
  `_advance_dependent_activities`, em `src/pivma/core/process_engine.py` (Spec 004 FR-011).
- [x] T007 [P] Teste unitário: instanciar `ActivityInstance` sem informar `activity_type`
  e confirmar o default `'form'`, em `tests/unit/core/test_activity_type_default.py`
  (usar factory de `tests/factories/`, não SQL manual).
- [x] T008 [P] Teste de migração (upgrade e downgrade) confirmando a criação/remoção da
  coluna `activity_type` com o valor default aplicado a linhas pré-existentes, em
  `tests/integration/migrations/test_activity_instance_activity_type_migration.py`.

**Checkpoint**: schema e motor prontos — as três user stories podem ser validadas.

---

## Phase 3: User Story 1 - Consultar o roteiro completo de uma instância (Priority: P1) 🎯 MVP

**Goal**: comprovar que a estrutura completa (fases/atividades declaradas, inclusive as
que ainda não começaram) já é observável via API real, sem endpoint novo.

**Independent Test**: consultar `GET /processes/templates/validated_method_dossier`
depois da publicação da versão 2 e confirmar que as duas fases e os três `activity_type`
aparecem na resposta, mesmo sem nenhuma instância ter avançado até a Fase 2.

### Tests for User Story 1

- [x] T009 [P] [US1] Teste de API: `GET /processes/templates/validated_method_dossier`
  retorna `definition.phases` com `phase_2_planning_preview` e sua atividade com
  `activity_type == "placeholder"` — implementado em
  `tests/api/routers/test_activity_type_extension.py` (arquivo dedicado, em vez de
  crescer `test_process_router.py`, pela regra de nomes de domínio da metodologia de
  testes do projeto).

### Implementation for User Story 1

*Nenhuma implementação adicional — esta história é satisfeita inteiramente pelas tarefas
da Fase 2 (Foundational) somadas à Fase 4 (US2, que introduz a Fase 2 de exemplo no YAML).
A tarefa acima apenas comprova o contrato já coberto por design (contracts/roadmap-composition.md §1).*

**Checkpoint**: US1 validável de forma independente assim que T001-T003 e T010 (US2)
estiverem prontos.

---

## Phase 4: User Story 2 - Declarar atividades que não são formulário (Priority: P2)

**Goal**: uma atividade sem formulário pode ser declarada, instanciada e avançar quando
sua dependência é satisfeita, sem gerar `FormInstance`.

**Independent Test**: aprovar a triagem de uma instância criada a partir da versão 2 de
`validated_method_dossier` e confirmar que `planning_preview` é ativada com
`activity_type == "placeholder"`, sem `FormInstance` associada.

### Tests for User Story 2

- [x] T010 [US2] Teste de API: instanciar processo a partir de
  `validated_method_dossier` (versão 2), completar `proposal_submission`, aprovar via
  `POST /processes/{id}/triage/decision {"outcome": "APPROVED"}`, e então confirmar via
  `GET /tasks?process_id={id}` que existe uma `Task` para `planning_preview` com
  `status == "READY"` — implementado em `test_placeholder_activity_unlocks_on_triage_approval`,
  em `tests/api/routers/test_activity_type_extension.py`.
- [x] T011 [P] [US2] Confirmar que nenhuma linha de `form_instances` é criada para a
  `ActivityRun` de `planning_preview` — dobrado sobre o mesmo teste de T010 (mesma
  transação/sessão já monta o cenário; arquivo de integração separado seria puramente
  redundante), com consulta direta via `session` ao final de
  `test_placeholder_activity_unlocks_on_triage_approval`.
- [x] T012 [P] [US2] Teste de não regressão: repetir os cenários já cobertos por
  `tests/api/routers/test_process_router.py`, `test_form_submission.py` e
  `test_triage_review.py` para os 5 métodos oficiais, confirmando que nenhum se altera
  (SC-003 da spec) — adicionar/():ajustar apenas se a suíte existente já não cobrir a
  execução completa de `validated_method_dossier` versão 1→2.

### Implementation for User Story 2

- [x] T013 [US2] Editar `src/pivma/templates_data/04_validated_method_dossier.yaml`:
  incrementar `process_template.version` para `2` e adicionar
  `phase_2_planning_preview` (order_index 2) com a atividade `planning_preview`
  (`activity_type: "placeholder"`, `assigned_role: "BRACVAM_ADMIN"`, sem
  `form_template_key`, `dependencies: [{required_activity_key: "triage_evaluation",
  required_status: "COMPLETED", condition_type: "ACTIVITY_COMPLETED"}]`) — mantendo a
  Fase 1 exatamente como está hoje (data-model.md §3).

**Checkpoint**: US1 e US2 funcionam de ponta a ponta via API real.

---

## Phase 5: User Story 3 - Validar a extensão em um método oficial já ativo (Priority: P3)

**Goal**: uma página de demonstração dedicada, batendo na API real, prova visualmente o
fluxo completo das duas fases — critério de conclusão da Constituição (Princípio III).

**Independent Test**: seguir os 6 passos de `quickstart.md` a partir da página publicada
e confirmar que a Fase 2 aparece bloqueada e depois `READY`, com `activity_type`
visível.

### Implementation for User Story 3

- [x] T014 [P] [US3] Criar `demos/roadmap/index.html`: página estática (mesmo padrão
  visual de `demos/submission/index.html`) com quatro ações — "Consultar roteiro
  declarado" (`GET /processes/templates/validated_method_dossier`), "Iniciar submissão
  de exemplo" (`POST /processes`), "Preencher e enviar submissão" (fluxo já existente de
  `demos/submission/`), e "Ver roteiro da instância" (`GET /processes/{id}` +
  `GET /tasks?process_id={id}`, decorando cada atividade com o `activity_type` obtido da
  definição do template) — sem nenhum endpoint novo (contracts/roadmap-composition.md).
- [x] T015 [US3] Registrar a nova demo em `demos/index.html` (catálogo central, AGENTS.md
  regra de módulo).
- [x] T016 ~~Criar `scripts/seeds/seed_roadmap_demo.py`~~ — **revisado durante a
  implementação**: nenhum seed novo é estritamente necessário (AGENTS.md exige "a massa
  de dados estritamente necessária"). Publicar a versão 2 do template já é automático:
  `seed_forms.py` chama `bootstrap_all_templates`, que cria uma nova
  `ProcessTemplateVersion` sempre que o `version` do YAML muda — sem código novo. Os
  usuários `proponent_user`/`triage_evaluator` já são semeados por `seed_users.py`. A
  instância de exemplo é criada ao vivo pela própria página de demo (Passo 2), não
  precisa vir pré-semeada. Criar um script que só chamaria algo já chamado violaria a
  regra de "estritamente necessária" em vez de cumpri-la.
- [x] T017 Adicionado um item ao "Ciclo principal" já impresso por
  `scripts/seeds/seed_all.py` apontando `http://localhost:8000/demos/roadmap/`
  (reaproveitando a impressão existente — nenhum passo de seed novo).

**Checkpoint**: as três user stories completas; `poe test` verde; `quickstart.md`
executado manualmente com sucesso.

---

## Final Phase: Polish & Cross-Cutting

- [x] T018 [P] `ruff check .` / `ruff format .` (equivalente a `poe lint`/`poe format` —
  `poe` não está disponível neste ambiente) rodados; nenhuma alteração fora do escopo
  desta feature permaneceu (uma reformatação acidental de migrações antigas e de um
  bloco de código Markdown em `specs/012-.../data-model.md`, causada por passar
  `migrations/`/`.` explicitamente a um comando que ignora `extend-exclude` para
  caminhos explícitos, foi revertida).
- [x] T019 Executado manualmente contra o servidor real de desenvolvimento (banco do
  `.env`, `fastapi dev` já em execução) via `curl`, reproduzindo a sequência da demo:
  1. `alembic upgrade head` aplicado; `seed_all` idempotente re-rodado.
  2. `ProcessTemplateVersion` confirmada: v1 intacta (só Fase 1), v2 publicada com
     `phase_2_planning_preview`.
  3. Processo real criado (`validated_method_dossier`, v2), submissão enviada (o form ao
     vivo tinha um campo extra `titulo_do_metodo` de uma customização anterior via editor
     da Spec 012 — drift pré-existente, fora do escopo desta spec), status foi a `TRIAGE`.
  4. Antes da aprovação: só 2 tasks (`PROPONENT`, `TRIAGE_LEAD`).
  5. Triagem aprovada (`triage_evaluator`) → `new_process_status = "PLANNING"`.
  6. Depois da aprovação: 3ª task apareceu (`BRACVAM_ADMIN`, "Prévia do Planejamento",
     `READY`); timeline registrou `ACTIVITY_UNBLOCKED` com `activity_type: "placeholder"`;
     confirmado via consulta direta ao banco: `activity_type='placeholder'`,
     `status='IN_PROGRESS'`, **zero** `FormInstance` associada.
  7. Não regressão confirmada no banco real: a instância `[DEMO 4]` pré-existente
     (aprovada antes desta mudança) permanece na versão 1, só com a Fase 1.
  8. `/demos/roadmap/`, `/demos/`, `/demos/submission/`, `/demos/triage/` respondem 200.
  A instância de teste criada (`[VALIDACAO SPEC017] Roteiro em Duas Fases`) não foi
  removida manualmente — o próprio `seed_triage.py` a desativa (soft-delete) no próximo
  `seed_all`, por não estar na lista de títulos oficiais.
- [x] T021 **Bug encontrado durante a integração com o `pivma-front` e corrigido**:
  `GET /processes/templates/{key}` retornava o `definition_payload` cru — para os 4
  métodos não tocados por esta spec (nenhum declara `activity_type` no YAML), cada
  atividade vinha **sem** o campo `activity_type`, violando FR-006/FR-003 no contrato
  de leitura (o default só era aplicado na instanciação, não na leitura). Corrigido com
  `_normalize_definition_payload` em `src/pivma/routers/processes.py` (preenche
  `activity_type: "form"` por atividade, sem mutar o payload persistido). Teste de
  regressão:
  `test_template_detail_defaults_activity_type_for_legacy_templates` em
  `tests/api/routers/test_activity_type_extension.py`. Suíte completa: 575 passed,
  1 skipped.
- [x] T020 `uv run pytest` (equivalente a `poe test` — `poe` indisponível neste ambiente)
  verde: **574 passed, 1 skipped**, cobrindo os testes novos desta feature e toda a
  suíte pré-existente das Specs 004/009/011/013/014/016.

---

## Dependencies & Execution Order

- **Foundational (Phase 2)**: bloqueia tudo; deve ser concluída primeiro (T001 → T002 →
  T003 → T004 → T005 → T006; T007/T008 em paralelo assim que T001/T002 existirem).
- **US1 (Phase 3)**: depende apenas da Fase 2 e do YAML de US2 (T013) para ter conteúdo
  de Fase 2 a observar — T009 pode ser escrito antes, mas só passa depois de T013.
- **US2 (Phase 4)**: depende da Fase 2 (Foundational). T013 (YAML) é pré-requisito de
  T009 (US1) e T010/T011 (US2).
- **US3 (Phase 5)**: depende de US1 e US2 estarem funcionais — a demo consome o
  comportamento real que elas comprovam.
- **Polish**: depende de todas as histórias desejadas estarem completas.

### Parallel Opportunities

- T002, T007, T008 em paralelo entre si (arquivos diferentes) assim que T001 existir.
- T006 em paralelo com T007/T008.
- T011 e T012 em paralelo entre si.
- T014, T015 em paralelo com T016 (arquivos diferentes); T017 depende de T016 existir.

---

## Implementation Strategy

### MVP First

1. Fase 2 (Foundational) completa.
2. Fase 4 (US2) completa — é o que efetivamente prova "mais do que formulário" na Fase 2.
3. Fase 3 (US1) confirmada como consequência (T009).
4. **PARE e VALIDE** manualmente via `GET /processes/templates/validated_method_dossier`
   e `GET /tasks?process_id=`.

### Entrega incremental

1. Foundational → schema e motor prontos.
2. US2 → Fase 2 de exemplo existe e avança de verdade.
3. US1 → confirmado que o roteiro completo já é observável (sem código adicional).
4. US3 → demo publicada, seed dedicado, critério de conclusão da Constituição atendido.
5. Polish → `ruff`/`pytest` verdes, quickstart executado, evidência registrada.
