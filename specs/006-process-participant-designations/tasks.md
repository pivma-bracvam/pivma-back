# Tasks: Designações e Conflito de Interesse

**Input**: Artefatos em `specs/006-process-participant-designations/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/process-participants.openapi.yaml` e `quickstart.md`

**Tests**: Obrigatórios. Cada tarefa de teste abaixo cobre um único comportamento observável da matriz de `quickstart.md`. Parametrização é usada somente quando varia a entrada sob o mesmo contrato.

**Organization**: As tarefas estão agrupadas pelas três histórias da spec. A implementação segue a menor extensão aprovada: uma coluna, uma tabela, uma permissão, um router e alterações pontuais nos módulos existentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode ser executada em paralelo porque usa arquivo distinto e não depende de tarefa incompleta.
- **[Story]**: associa a tarefa a `US1`, `US2` ou `US3`.
- Tarefas de setup e fundação não recebem rótulo de história.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar somente a superfície de módulo prevista no plano, sem implementar comportamento.

- [X] T001 Criar o router vazio com prefixo `/processes/{process_id}/participants` em `src/pivma/routers/process_participants.py`
- [X] T002 Registrar o router de participantes na aplicação em `src/pivma/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Criar a evolução persistente e os builders compartilhados que bloqueiam todas as histórias.

**CRITICAL**: Nenhuma história deve ser implementada antes da conclusão desta fase.

### Tests for Foundational Persistence

> Escrever cada teste primeiro e confirmar que falha pela ausência da evolução correspondente.

- [X] T003 Testar I-M01: o upgrade adiciona a coluna opcional `assignments.laboratory_id` em `tests/integration/migrations/test_participant_migration.py`
- [X] T004 Testar I-M02: o upgrade adiciona a FK de `assignments.laboratory_id` sem cascata em `tests/integration/migrations/test_participant_migration.py`
- [X] T005 Testar I-M03: o upgrade cria a tabela `conflict_interest_declarations` em `tests/integration/migrations/test_participant_migration.py`
- [X] T006 Testar I-M04: o upgrade cria o índice determinístico de última declaração em `tests/integration/migrations/test_participant_migration.py`
- [X] T007 Testar I-M05: o upgrade normaliza designações legadas `PROPONENT` para `proponent` em `tests/integration/migrations/test_participant_migration.py`
- [X] T008 Testar I-M06: o upgrade preserva cada registro preexistente, parametrizado por processo, tarefa, designação e evento sob a mesma regra, em `tests/integration/migrations/test_participant_migration.py`
- [X] T009 Testar I-M07: o upgrade não cria backfill implícito, parametrizado por laboratório, declaração e evento sob a mesma regra, em `tests/integration/migrations/test_participant_migration.py`
- [X] T010 Testar I-M08: o upgrade cria `process.participants.manage` e a concede somente ao perfil Administrador em `tests/integration/migrations/test_participant_migration.py`
- [X] T011 Testar I-M09: o downgrade remove somente as estruturas e o seed da feature 006 em `tests/integration/migrations/test_participant_migration.py`
- [X] T012 Testar I-M10: o downgrade restaura designações locais `proponent` para `PROPONENT` em `tests/integration/migrations/test_participant_migration.py`
- [X] T013 Testar I-M11: o downgrade preserva cada registro anterior, parametrizado por processo, tarefa, designação e evento sob a mesma regra, em `tests/integration/migrations/test_participant_migration.py`

### Implementation for Foundational Persistence

- [X] T014 Implementar upgrade e downgrade após `5e31a8c7d204`, incluindo coluna/FK, tabela/índice, normalização de papel e seed estável da permissão, em `migrations/versions/6f2c9a1d4e70_process_participant_designations.py`
- [X] T015 Evoluir `Assignment` com `laboratory_id` e relacionamento e criar `ConflictInterestDeclaration` com `AuditMixin`, FK sem cascata e índice determinístico em `src/pivma/core/database/models.py`
- [X] T016 Criar factories reutilizáveis de designação e declaração, compatíveis com a sessão assíncrona dos testes, em `tests/factories/participant_factory.py`
- [X] T017 Exportar as novas factories sem alterar as existentes em `tests/factories/__init__.py`

**Checkpoint**: Migração, modelos e factories compartilhados estão disponíveis; as histórias podem começar.

---

## Phase 3: User Story 1 - Designar e revogar participantes (Priority: P1) MVP

**Goal**: Permitir que Administrador ou `group_manager` efetivo designe, liste e revogue participantes, com validação de usuário, papel, laboratório e vínculo vigentes, sem ciclos ativos duplicados.

**Independent Test**: Um gestor autorizado designa um usuário ativo, consulta o ciclo vigente, revoga-o e cria um novo ciclo equivalente. Um participante laboratorial somente é aceito com laboratório e vínculo vigentes.

### Tests for User Story 1

> Escrever os testes e confirmar as falhas esperadas antes de implementar a história. Tarefas no mesmo arquivo devem ser executadas em sequência.

- [X] T018 [US1] Testar U-S01: aceitar os oito papéis locais aprovados, parametrizados, em `tests/unit/schemas/test_participant_schemas.py`
- [X] T019 [US1] Testar U-S02: rejeitar papel fora do catálogo em `tests/unit/schemas/test_participant_schemas.py`
- [X] T020 [US1] Testar U-S03: rejeitar os dois papéis laboratoriais sem `laboratory_id`, parametrizados, em `tests/unit/schemas/test_participant_schemas.py`
- [X] T021 [US1] Testar U-S04: rejeitar os seis papéis não laboratoriais com `laboratory_id`, parametrizados, em `tests/unit/schemas/test_participant_schemas.py`
- [X] T022 [US1] Testar I-A01 em PostgreSQL real: permissão global ativa autoriza gestão em qualquer processo em `tests/integration/database/test_participant_authorization.py`
- [X] T023 [US1] Testar I-A02 em PostgreSQL real: `group_manager` efetivo autoriza gestão somente no próprio processo em `tests/integration/database/test_participant_authorization.py`
- [X] T024 [US1] Testar I-A03 em PostgreSQL real: `group_manager` revogado não autoriza gestão em `tests/integration/database/test_participant_authorization.py`
- [X] T025 [US1] Testar I-A04 em PostgreSQL real: designação `group_manager` de usuário inativo não autoriza gestão em `tests/integration/database/test_participant_authorization.py`
- [X] T026 [US1] Testar I-D01 em PostgreSQL real: FK rejeita laboratório inexistente em `tests/integration/database/test_participant_constraints.py`
- [X] T027 [US1] Testar I-D02 em PostgreSQL real: índice parcial rejeita ciclo ativo duplicado por processo, usuário e papel quando as designações usam laboratórios diferentes em `tests/integration/database/test_participant_constraints.py`
- [X] T028 [US1] Testar I-D03 em PostgreSQL real: novo ciclo equivalente é aceito após revogação em `tests/integration/database/test_participant_constraints.py`
- [X] T029 [US1] Testar I-Q01 em PostgreSQL real: designação laboratorial com vínculo vigente é calculada como efetiva em `tests/integration/database/test_participant_constraints.py`
- [X] T030 [US1] Testar I-Q02 em PostgreSQL real: inativação de vínculo, laboratório ou usuário torna a designação inefetiva, parametrizada pela origem, em `tests/integration/database/test_participant_constraints.py`
- [X] T031 [US1] Testar A-D01 via TestClient: Administrador cria designação individual válida e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T032 [US1] Testar A-D02 via TestClient: `group_manager` cria designação no próprio processo e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T033 [US1] Testar A-D03 via TestClient: gestor cria designação laboratorial com vínculo vigente e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T034 [US1] Testar A-D04 via TestClient: usuário ou laboratório inexistente retorna 404, parametrizado pelo alvo, em `tests/api/routers/test_participant_router.py`
- [X] T035 [US1] Testar A-D05 via TestClient: usuário ou laboratório inativo retorna 409, parametrizado pelo alvo, em `tests/api/routers/test_participant_router.py`
- [X] T036 [US1] Testar A-D06 via TestClient: processo inexistente retorna 404 para gestor global autorizado em `tests/api/routers/test_participant_router.py`
- [X] T037 [US1] Testar A-D07 via TestClient: processo logicamente excluído retorna 409 para gestor global autorizado em `tests/api/routers/test_participant_router.py`
- [X] T038 [US1] Testar A-D08 via TestClient: ausência de vínculo laboratorial vigente retorna 409 em `tests/api/routers/test_participant_router.py`
- [X] T039 [US1] Testar A-D09 via TestClient: duplicidade ativa sequencial retorna 409 em `tests/api/routers/test_participant_router.py`
- [X] T040 [US1] Testar A-D10 via TestClient: `group_manager` efetivo do processo conclui revogação válida e recebe 204 em `tests/api/routers/test_participant_router.py`
- [X] T041 [US1] Testar A-D11 via TestClient: revogação repetida retorna 409 em `tests/api/routers/test_participant_router.py`
- [X] T042 [US1] Testar A-D12 via TestClient: nova designação equivalente após revogação cria outro ciclo e retorna 201 em `tests/api/routers/test_participant_router.py`
- [X] T043 [US1] Testar A-D13 via TestClient: listagem do gestor retorna todos os ciclos ativos do processo em `tests/api/routers/test_participant_router.py`
- [X] T044 [US1] Testar A-S04: `group_manager` de outro processo recebe 403 ao designar em `tests/api/routers/test_participant_security.py`
- [X] T045 [US1] Testar A-S07: `group_manager` de outro processo recebe 403 ao revogar em `tests/api/routers/test_participant_security.py`
- [X] T046 [US1] Testar A-S06: `rbac.assignments.manage` e `institutional.affiliations.manage` não concedem designação ou revogação, parametrizadas pela permissão e operação, em `tests/api/routers/test_participant_security.py`
- [X] T047 [P] [US1] Testar A-X01 em PostgreSQL real: duas designações equivalentes concorrentes resultam em 201 e 409 e somente um ciclo ativo em `tests/api/routers/test_participant_concurrency.py`
- [X] T128 [US1] Testar A-A05 via TestClient: criação de processo grava `PARTICIPANT_ASSIGNED` para o proponente com o contexto `process_creation` em `tests/api/routers/test_process_router.py`
- [X] T048 [P] [US1] Testar A-R01: criação de processo mantém uma única designação local `proponent` em `tests/api/routers/test_process_router.py`
- [X] T049 [P] [US1] Testar A-R02: listagem de tarefas preserva `assigned_role = 'PROPONENT'` em `tests/api/routers/test_tasks_router.py`
- [X] T129 [US1] Testar A-A06 via TestClient: designação rejeitada por alvo inexistente ou vínculo laboratorial ausente não grava `PARTICIPANT_ASSIGNED`, parametrizada pela causa, em `tests/api/routers/test_participant_router.py`

### Implementation for User Story 1

- [X] T050 [P] [US1] Implementar schemas estritos de criação e resposta da designação, incluindo catálogo de papéis e regra de `laboratory_id`, em `src/pivma/schemas.py`
- [X] T051 [P] [US1] Implementar predicates de gestão global/local e cálculo de efetividade atual, reavaliando usuário, laboratório e vínculo, em `src/pivma/core/authorization.py`
- [X] T052 [P] [US1] Normalizar novas designações automáticas para `proponent`, obter o ciclo criado e gravar `PARTICIPANT_ASSIGNED` com `source=process_creation` na mesma transação; preservar papéis de `Task`, em `src/pivma/core/process_engine.py`
- [X] T053 [US1] Implementar no router a resolução de processo, usuário, laboratório e vínculo, tratando processo com `deleted_at` como inativo sem reinterpretar `status` ou `closed_at`, em `src/pivma/routers/process_participants.py`
- [X] T054 [US1] Implementar `POST /processes/{process_id}/participants` com unicidade concorrente, transação atômica e `PARTICIPANT_ASSIGNED` em `src/pivma/routers/process_participants.py`
- [X] T055 [US1] Implementar `DELETE /processes/{process_id}/participants/{assignment_id}` com revogação atômica e `PARTICIPANT_REVOKED` em `src/pivma/routers/process_participants.py`
- [X] T056 [US1] Implementar a visão do gestor em `GET /processes/{process_id}/participants`, ordenada por `assigned_at DESC, id DESC`, em `src/pivma/routers/process_participants.py`

**Checkpoint**: US1 funciona como MVP e pode ser validada sem declaração de conflito ou consulta histórica.

---

## Phase 4: User Story 2 - Declarar conflito de interesse (Priority: P2)

**Goal**: Permitir declarações imutáveis do próprio titular e bloquear revisões ou decisões de triagem enquanto qualquer ciclo ativo do usuário mantiver conflito vigente.

**Independent Test**: Um participante declara conflito em ciclo ativo, recebe 201, não consegue revisar nem decidir na triagem e depois registra nova declaração sem conflito, preservando a anterior e restabelecendo a decisão.

### Tests for User Story 2

> Escrever os testes e confirmar as falhas esperadas antes de implementar a história. Cada teste de bloqueio deve verificar somente o efeito indicado.

- [X] T057 [US2] Testar U-S05: justificativa composta somente por espaços é rejeitada em `tests/unit/schemas/test_participant_schemas.py`
- [X] T058 [US2] Testar U-S06: schemas de designação e declaração rejeitam campo extra, parametrizados pelo contrato, em `tests/unit/schemas/test_participant_schemas.py`
- [X] T059 [US2] Testar I-C01 em PostgreSQL real: ausência de declaração não gera conflito em `tests/integration/database/test_participant_authorization.py`
- [X] T060 [US2] Testar I-C02 em PostgreSQL real: última declaração verdadeira de ciclo ativo gera conflito em `tests/integration/database/test_participant_authorization.py`
- [X] T061 [US2] Testar I-C03 em PostgreSQL real: declaração falsa posterior retira o conflito do mesmo ciclo em `tests/integration/database/test_participant_authorization.py`
- [X] T062 [US2] Testar I-C04 em PostgreSQL real: conflito verdadeiro em outro ciclo ativo prevalece sobre declaração falsa em `tests/integration/database/test_participant_authorization.py`
- [X] T063 [US2] Testar I-C05 em PostgreSQL real: conflito de ciclo revogado é ignorado no cálculo em `tests/integration/database/test_participant_authorization.py`
- [X] T064 [US2] Testar I-C06 em PostgreSQL real: empate de `declared_at` usa o maior identificador como registro mais recente em `tests/integration/database/test_participant_authorization.py`
- [X] T065 [US2] Testar I-D04 em PostgreSQL real: exclusão física de designação referenciada por declaração é rejeitada pela FK em `tests/integration/database/test_participant_constraints.py`
- [X] T066 [US2] Testar I-Q03 em PostgreSQL real: consulta da última declaração ordena por momento e identificador em `tests/integration/database/test_participant_constraints.py`
- [X] T067 [US2] Testar A-C01 via TestClient: titular declara conflito em designação ativa e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T068 [US2] Testar A-C02 via TestClient: titular declara ausência de conflito em nova linha, preserva a anterior e recebe 201 em `tests/api/routers/test_participant_router.py`
- [X] T069 [US2] Testar A-C03 via TestClient: outro usuário não declara pelo titular e recebe 403 em `tests/api/routers/test_participant_router.py`
- [X] T070 [US2] Testar A-C04 via TestClient: titular não declara em ciclo revogado e recebe 409 em `tests/api/routers/test_participant_router.py`
- [X] T071 [US2] Testar A-C11 via TestClient: designação alheia e identificador desconhecido produzem a mesma resposta 403, parametrizados, em `tests/api/routers/test_participant_router.py`
- [X] T072 [P] [US2] Testar A-S05: designar, revogar ou declarar sem origem confiável retorna 403, parametrizado pela mutação, em `tests/api/routers/test_participant_security.py`
- [X] T073 [US2] Testar A-B01 via TestClient: conflito vigente bloqueia gravação de revisão de triagem com 403 em `tests/api/routers/test_participant_task_blocking.py`
- [X] T074 [US2] Testar A-B02 via TestClient: conflito vigente bloqueia decisão de triagem com 403 em `tests/api/routers/test_participant_task_blocking.py`
- [X] T075 [US2] Testar A-B03 via TestClient: ausência de conflito preserva o caminho existente de revisão de triagem em `tests/api/routers/test_participant_task_blocking.py`
- [X] T076 [US2] Testar A-B04 via TestClient: declaração falsa posterior restabelece o caminho existente de decisão de triagem em `tests/api/routers/test_participant_task_blocking.py`
- [X] T077 [US2] Testar A-B05 via TestClient: revisão bloqueada não cria nem altera `FieldReview` ou evento de revisão em `tests/api/routers/test_participant_task_blocking.py`
- [X] T078 [US2] Testar A-B06 via TestClient: decisão bloqueada não cria `Decision` nem evento de decisão em `tests/api/routers/test_participant_task_blocking.py`
- [X] T079 [US2] Testar A-B07 via TestClient: conflito vigente em um papel bloqueia ação autorizada por outro papel ativo em `tests/api/routers/test_participant_task_blocking.py`
- [X] T080 [US2] Testar A-B08 via TestClient: revogação do ciclo conflitado restabelece a ação autorizada por outro ciclo ativo em `tests/api/routers/test_participant_task_blocking.py`

### Implementation for User Story 2

- [X] T081 [P] [US2] Implementar schemas estritos de entrada e resposta da declaração, normalizando e validando justificativa sem aceitar autoria ou `declared_at` do cliente, em `src/pivma/schemas.py`
- [X] T082 [P] [US2] Implementar consulta reutilizável do conflito vigente por usuário e processo com desempate por `declared_at` e `id` em `src/pivma/core/authorization.py`
- [X] T083 [US2] Implementar `POST /processes/{process_id}/participants/{assignment_id}/conflicts` para o titular ativo, com append-only, transação atômica e `CONFLICT_DECLARED`, em `src/pivma/routers/process_participants.py`
- [X] T084 [US2] Criar `AuthorizationError` em `src/pivma/core/process_engine.py` para o bloqueio por conflito, sem alterar `ConflictError` e seu contrato legado
- [X] T085 [US2] Aplicar a guarda de conflito antes de qualquer mutação em `save_field_reviews`, lançando `AuthorizationError`, em `src/pivma/core/process_engine.py`
- [X] T086 [US2] Aplicar a mesma guarda antes de qualquer mutação em `execute_triage_decision`, lançando `AuthorizationError`, em `src/pivma/core/process_engine.py`
- [X] T087 [US2] Mapear somente `AuthorizationError` para 403 nas duas rotas de triagem em `src/pivma/routers/triage.py`

**Checkpoint**: US2 registra declarações imutáveis e bloqueia somente os dois fluxos avaliativos/decisórios já existentes.

---

## Phase 5: User Story 3 - Consultar participantes e histórico (Priority: P3)

**Goal**: Expor estado atual, histórico, conflitos e eventos conforme o escopo: gestores veem o processo inteiro, participantes veem somente os próprios registros e pessoas externas não recebem conteúdo protegido.

**Independent Test**: Após criar, revogar e recriar uma designação e registrar duas declarações, o gestor consulta todos os ciclos e eventos; o titular consulta somente os seus; uma pessoa externa recebe 403 sem distinção entre processo conhecido e desconhecido.

### Tests for User Story 3

> Escrever os testes e confirmar as falhas esperadas antes de implementar a história. Paginação, auditoria, timeline e desempenho permanecem em testes separados.

- [X] T088 [US3] Testar I-A05 em PostgreSQL real: participante comum recebe escopo próprio de leitura sem gestão em `tests/integration/database/test_participant_authorization.py`
- [X] T089 [US3] Testar I-A06 em PostgreSQL real: pessoa externa recebe ausência de escopo de participantes em `tests/integration/database/test_participant_authorization.py`
- [X] T090 [US3] Testar A-D14 via TestClient: listagem do participante retorna somente os ciclos próprios em `tests/api/routers/test_participant_router.py`
- [X] T091 [US3] Testar A-D15 via TestClient: listagem retorna `has_conflict = null` quando não existe declaração em `tests/api/routers/test_participant_router.py`
- [X] T092 [US3] Testar A-D16 via TestClient: listagem retorna `effective = false` após perda de vínculo em `tests/api/routers/test_participant_router.py`
- [X] T093 [US3] Testar A-D17 via TestClient: listagem do gestor retorna `has_conflict = true` após declaração vigente com conflito em `tests/api/routers/test_participant_router.py`
- [X] T094 [US3] Testar A-C12 via TestClient: histórico do gestor expõe a justificativa da declaração em `tests/api/routers/test_participant_router.py`
- [X] T095 [US3] Testar A-C13 via TestClient: histórico do titular expõe a justificativa da própria declaração em `tests/api/routers/test_participant_router.py`
- [X] T096 [US3] Testar A-C05 via TestClient: histórico do gestor inclui ciclos ativos e revogados em `tests/api/routers/test_participant_router.py`
- [X] T097 [US3] Testar A-C06 via TestClient: histórico do participante inclui somente ciclos próprios em `tests/api/routers/test_participant_router.py`
- [X] T098 [US3] Testar A-C07 via TestClient: histórico ordena ciclos por atribuição e identificador em `tests/api/routers/test_participant_router.py`
- [X] T099 [US3] Testar A-C08 via TestClient: histórico ordena declarações por declaração e identificador em `tests/api/routers/test_participant_router.py`
- [X] T100 [US3] Testar A-C09 via TestClient: `limit` acima de 200 retorna 422 em `tests/api/routers/test_participant_router.py`
- [X] T101 [US3] Testar A-C10 via TestClient: `offset` e `limit` paginam ciclos sem repetição em `tests/api/routers/test_participant_router.py`
- [X] T102 [US3] Testar A-S01: as cinco operações retornam 401 sem autenticação, parametrizadas pela operação, em `tests/api/routers/test_participant_security.py`
- [X] T103 [US3] Testar A-S02: pessoa externa recebe 403 ao listar participantes de processo conhecido em `tests/api/routers/test_participant_security.py`
- [X] T104 [US3] Testar A-S03: pessoa externa recebe a mesma resposta 403 para processo desconhecido em `tests/api/routers/test_participant_security.py`
- [X] T105 [US3] Testar A-S08: pessoa externa recebe a mesma resposta 403 no histórico de processo conhecido e desconhecido em `tests/api/routers/test_participant_security.py`
- [X] T106 [US3] Testar A-A01: designação, revogação e declaração concluídas gravam o tipo e o contexto de evento exigidos, parametrizadas pela mutação, em `tests/api/routers/test_participant_router.py`
- [X] T107 [US3] Testar A-A02: designação duplicada rejeitada não grava `PARTICIPANT_ASSIGNED` em `tests/api/routers/test_participant_router.py`
- [X] T108 [US3] Testar A-A03: revogação repetida rejeitada não grava outro `PARTICIPANT_REVOKED` em `tests/api/routers/test_participant_router.py`
- [X] T109 [US3] Testar A-A04: declaração por terceiro rejeitada não grava `CONFLICT_DECLARED` em `tests/api/routers/test_participant_router.py`
- [X] T110 [US3] Testar A-T01 via TestClient: gestor vê todos os novos eventos na timeline em `tests/api/routers/test_participant_timeline.py`
- [X] T111 [US3] Testar A-T02 via TestClient: participante vê somente os próprios eventos de participante na timeline em `tests/api/routers/test_participant_timeline.py`
- [X] T112 [US3] Testar A-T03 via TestClient: pessoa externa não recebe os novos eventos na timeline em `tests/api/routers/test_participant_timeline.py`
- [X] T113 [US3] Testar A-T04 via TestClient: filtragem dos novos eventos preserva os eventos anteriores da timeline em `tests/api/routers/test_participant_timeline.py`
- [X] T114 [US3] Testar A-T05 via TestClient: timeline desempata eventos com o mesmo `occurred_at` pelo identificador crescente em `tests/api/routers/test_participant_timeline.py`
- [X] T115 [US3] Testar A-P01: após massa e aquecimento, pelo menos 19 de 20 listagens atuais medidas somente na requisição HTTP terminam em até 2 segundos em `tests/api/routers/test_participant_timed_acceptance.py`
- [X] T116 [US3] Testar A-P02: após massa e aquecimento, pelo menos 19 de 20 consultas históricas medidas somente na requisição HTTP terminam em até 2 segundos em `tests/api/routers/test_participant_timed_acceptance.py`

### Implementation for User Story 3

- [X] T117 [P] [US3] Completar schemas de estado atual, declaração histórica, ciclo histórico e paginação com justificativa restrita em `src/pivma/schemas.py`
- [X] T118 [P] [US3] Implementar o cálculo de escopo de leitura `manager`, `self` ou ausente no pedido atual em `src/pivma/core/authorization.py`
- [X] T119 [US3] Completar a listagem atual e implementar `GET /processes/{process_id}/participants/history` com escopo, estados derivados, ordenação determinística e `offset`/`limit` em `src/pivma/routers/process_participants.py`
- [X] T120 [US3] Filtrar somente `PARTICIPANT_ASSIGNED`, `PARTICIPANT_REVOKED` e `CONFLICT_DECLARED` na timeline conforme escopo, preservando eventos legados, em `src/pivma/routers/processes.py`

**Checkpoint**: As três histórias estão funcionais, auditáveis e testáveis de forma independente pelos critérios acima.

---

## Phase 6: Polish & Cross-Cutting Verification

**Purpose**: Documentar a superfície entregue e executar as verificações proporcionais sem ampliar o escopo.

- [X] T121 [P] Documentar a permissão, as cinco operações, os papéis locais e o bloqueio de conflito em `README.md`
- [X] T122 Conferir os caminhos, status, schemas e limites implementados contra `specs/006-process-participant-designations/contracts/process-participants.openapi.yaml`
- [X] T123 Executar os testes focados de unidade, persistência, migração, API, segurança, concorrência, bloqueio, timeline e desempenho listados em `specs/006-process-participant-designations/quickstart.md`
- [X] T124 Executar `poetry run pytest -q` e conferir diretamente a saída do Pytest para regressão das features 001 a 005 conforme `specs/006-process-participant-designations/quickstart.md`
- [X] T125 Executar `poetry run ruff check` e `poetry run alembic heads` conforme `specs/006-process-participant-designations/quickstart.md`
- [ ] T126 Executar o cenário manual cronometrado de designar, consultar e revogar em até 2 minutos conforme `specs/006-process-participant-designations/quickstart.md`
- [ ] T127 Executar separadamente o cenário manual funcional de declarar conflito e confirmar o bloqueio conforme `specs/006-process-participant-designations/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 — Setup**: inicia imediatamente.
- **Phase 2 — Foundational**: depende de T001–T002 e bloqueia todas as histórias.
- **Phase 3 — US1**: depende da fundação e entrega o MVP.
- **Phase 4 — US2**: depende da fundação; na sequência recomendada, reutiliza o router e a designação entregues pela US1.
- **Phase 5 — US3**: depende da fundação; a validação completa do histórico e dos eventos pressupõe as mutações de US1 e US2.
- **Phase 6 — Verification**: depende das histórias escolhidas para entrega; a regressão completa pressupõe as três.

### User Story Dependencies

```text
Setup (T001–T002)
        |
Foundation (T003–T017)
        |
US1 / MVP (T018–T056, T128–T129)
        |
US2 (T057–T087)
        |
US3 (T088–T120)
        |
Verification (T121–T127)
```

A ordem sequencial é recomendada porque as três histórias alteram `schemas.py`, `authorization.py` e `process_participants.py`. T128 deve preceder T052, e T129 deve preceder T054; os dois IDs foram acrescentados após a numeração inicial, mas permanecem na fase e na ordem de execução de US1. Os testes de US2 podem preparar `Assignment` por factory, e os de US3 podem preparar ciclos e declarações diretamente por ORM, mas a entrega integrada deve seguir P1 → P2 → P3 para evitar conflitos de edição e regressões ocultas.

### Within Each User Story

- Escrever cada tarefa de teste antes da implementação associada e confirmar a falha pelo motivo esperado.
- Manter um teste por comportamento da matriz; não anexar auditoria, autorização, concorrência ou paginação ao teste de sucesso.
- Implementar schemas e predicates antes das rotas que os consomem.
- Gravar mudança e `AuditEvent` na mesma transação.
- Concluir e executar os testes focados da história antes de avançar.

### Parallel Opportunities

- Depois da fundação, os fluxos de testes em arquivos distintos podem avançar em paralelo; tarefas no mesmo arquivo permanecem sequenciais.
- Em US1, schemas T018–T021, autorização T022–T025, persistência T026–T030, API T031–T043 e segurança T044–T046 formam fluxos independentes; T047–T049 estão marcadas `[P]` por usarem arquivos exclusivos.
- Em US2, os fluxos de schema T057–T058, autorização T059–T064, persistência T065–T066, API T067–T071, segurança T072 e bloqueio T073–T080 podem ser distribuídos por arquivo.
- Em US3, autorização T088–T089, API T090–T101 e T106–T109, segurança T102–T105, timeline T110–T114 e desempenho T115–T116 podem ser distribuídos por arquivo.
- As implementações marcadas `[P]` usam arquivos distintos. As mutações do router e do engine permanecem ordenadas.

## Parallel Examples

### User Story 1

```text
Fluxo A: T018 → T019 → T020 → T021  (schemas)
Fluxo B: T022 → T023 → T024 → T025  (autorização em PostgreSQL)
Fluxo C: T026 → T027 → T028 → T029 → T030  (constraints e consultas)
Fluxo D: T031 → ... → T043  (contratos HTTP)
Fluxo E: T044 → T045 → T046  (segurança)
T047, T048 e T049 podem avançar em paralelo com esses fluxos.
```

### User Story 2

```text
Fluxo A: T057 → T058  (schemas)
Fluxo B: T059 → ... → T064  (cálculo de conflito em PostgreSQL)
Fluxo C: T065 → T066  (constraints e ordenação)
Fluxo D: T067 → ... → T071  (declaração HTTP)
Fluxo E: T073 → ... → T080  (bloqueio e ausência de efeitos parciais)
```

### User Story 3

```text
Fluxo A: T088 → T089  (escopo de leitura em PostgreSQL)
Fluxo B: T090 → ... → T101 → T106 → ... → T109  (estado, histórico e auditoria)
Fluxo C: T102 → ... → T105  (fronteiras HTTP)
Fluxo D: T110 → ... → T114  (timeline)
Fluxo E: T115 → T116  (desempenho)
```

## Implementation Strategy

### MVP First

1. Concluir Setup T001–T002.
2. Concluir Foundation T003–T017.
3. Concluir US1 T018–T056, T128 e T129.
4. Executar os testes focados de US1 e validar designação, listagem, revogação, vínculo laboratorial e concorrência.
5. Parar para revisão antes de acrescentar conflito e histórico.

### Incremental Delivery

1. **US1**: entrega RF005 com auditoria das mutações e preservação dos contratos legados.
2. **US2**: acrescenta RF006 e o bloqueio nos dois fluxos avaliativos/decisórios existentes.
3. **US3**: completa visibilidade, histórico, timeline, paginação e metas de consulta.
4. **Verification**: confirma contrato, regressão, lint, cadeia Alembic e cenário manual.

## Test Granularity and Definition of Done

- A matriz produz **98 tarefas de teste**: 11 fundacionais, 34 de US1, 24 de US2 e 29 de US3.
- Cada requisito FR-001 a FR-032 mantém ao menos uma evidência identificada em `quickstart.md`.
- Caminhos de sucesso HTTP, branches de autorização e conflito, erros relevantes, constraints PostgreSQL, migração, concorrência, privacidade, paginação e regressão têm evidências separadas.
- Factories e fixtures reutilizáveis preparam estados comuns por ORM. SQL direto fica restrito aos testes de migração ou constraint que exigirem o schema real.
- A história só termina quando seus testes focados passam sem ocultar falhas; `poetry test` não substitui a saída direta do Pytest.

## Notes

- `[P]` indica arquivos distintos e ausência de dependência incompleta; não autoriza edição paralela do mesmo arquivo.
- Não criar repository, service genérico, mensageria, notificações, novos papéis, novos tipos de tarefa ou endpoints além do contrato.
- Não alterar `Task.assigned_role`; somente `Assignment.role_key` usa as oito chaves minúsculas aprovadas.
- Não expor justificativas ou eventos de terceiros fora do escopo de gestão.
- Não fazer commit, push ou PR como parte destas tarefas sem solicitação explícita.
