---

description: "Tarefas executáveis para exclusão, cancelamento e arquivamento de processos"
---

# Tasks: Exclusão, Cancelamento e Arquivamento de Processos

**Input**: Artefatos de design em `specs/022-process-retirement/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/process-lifecycle.openapi.yaml` e `quickstart.md`

**Classificação**: **CONFIRMADO**: decisão do responsável da demanda determina exclusão física em cascata para rascunho nunca submetido. **PROPOSTA**: o comando único, os códigos de ação e a projeção para o front-end mantêm a superfície pequena. **INFERÊNCIA**: o diretório local `ATTACHMENTS_DIR/{process_id}/` reúne os binários de anexo do processo.

**Tests**: Obrigatórios. A feature altera exclusão física, transações, autorização e execução assíncrona, classificados como risco alto. Escreva cada teste antes da tarefa de implementação que ele cobre e confirme sua falha inicial.

**Sem migração**: `ProcessInstance.status` e os status dos filhos são strings livres; a feature reutiliza colunas e auditoria existentes para cancelamento e arquivamento. Não criar migration, tabela, perfil RBAC ou estado `DELETED`.

## Formato

Cada linha de tarefa usa `- [ ] T### [P?] [US?] descrição com caminho`. `[P]` indica arquivos distintos e ausência de dependência entre as tarefas.

## Phase 1: Preparação

**Purpose**: Criar massa de teste reutilizável para processos em cada condição de ciclo de vida.

- [X] T001 Criar helpers de rascunho com registros e anexo, processo submetido, encerrado e com pré-avaliação pendente em `tests/factories/process_retirement_factory.py`
- [X] T002 Registrar os helpers de retirement usados por testes de API e integração em `tests/conftest.py`

---

## Phase 2: Fundamentos compartilhados

**Purpose**: Criar as regras reutilizadas por todas as ações, sem alterar a estrutura persistida.

- [X] T003 Criar teste unitário para rascunho retornado a `SUBMISSION` continuar submetido em `tests/unit/core/test_process_retirement.py`
- [X] T004 Criar teste unitário para justificativa vazia ser inválida em `tests/unit/core/test_process_retirement.py`
- [X] T005 Criar teste unitário para justificativa acima de 2.000 caracteres ser inválida em `tests/unit/core/test_process_retirement.py`
- [X] T006 Implementar constantes de ações, status terminais e limite de justificativa em `src/pivma/core/process_engine.py`
- [X] T007 Implementar a detecção de submissão formal por `AuditEvent.SUBMISSION_SUBMITTED` em `src/pivma/core/process_engine.py`
- [X] T008 Implementar a guarda de processo mutável para `CANCELLED` e `ARCHIVED` em `src/pivma/core/process_engine.py`
- [X] T009 Implementar schema de requisição de ação de ciclo de vida em `src/pivma/schemas.py`
- [X] T010 Implementar schemas de resposta de ação, incluindo `deleted=true` para exclusão física, e de `available_actions` em `src/pivma/schemas.py`

**Checkpoint**: O domínio identifica rascunho inicial sem ambiguidade e os schemas rejeitam justificativa inválida.

---

## Phase 3: User Story 1 - Excluir permanentemente um rascunho não submetido (Priority: P1) 🎯 MVP

**Goal**: Permitir ao proponente efetivo ou ator de plataforma remover fisicamente o agregado de um rascunho que nunca entrou no pipeline.

**Independent Test**: Criar um rascunho inicial com dados e anexo, removê-lo com justificativa válida e confirmar que não restam registros vinculados nem diretório de anexos.

### Tests for User Story 1

- [X] T011 [US1] Criar teste de API para `DELETE_DRAFT` do proponente efetivo retornar 200 em `tests/api/routers/test_process_retirement.py`
- [X] T012 [US1] Criar teste de integração para `DELETE_DRAFT` remover processo e registros vinculados do banco em `tests/integration/database/test_process_retirement_deletion.py`
- [X] T013 [US1] Criar teste de API para rascunho removido não aparecer em `GET /processes` em `tests/api/routers/test_process_retirement.py`
- [X] T014 [US1] Criar teste de integração para `DELETE_DRAFT` remover arquivo e diretório do processo e falhar sem apagar linhas se a remoção do arquivo falhar em `tests/integration/database/test_process_retirement_deletion.py`
- [X] T015 [US1] Criar teste de API para ator de plataforma excluir rascunho alheio em `tests/api/routers/test_process_retirement.py`
- [X] T016 [US1] Criar teste de segurança para proponente sem vínculo receber `forbidden` em `tests/api/routers/test_process_retirement.py`
- [X] T017 [US1] Criar teste de API para processo com `SUBMISSION_SUBMITTED` rejeitar `DELETE_DRAFT` com `invalid_transition` em `tests/api/routers/test_process_retirement.py`
- [X] T018 [US1] Criar teste de API para ação em processo fisicamente removido retornar `not_found` em `tests/api/routers/test_process_retirement.py`

### Implementation for User Story 1

- [X] T019 [US1] Implementar ramo `DELETE_DRAFT` com bloqueio, autorização e remoção física ordenada do agregado em `src/pivma/core/process_engine.py`
- [X] T020 [US1] Implementar remoção do diretório `ATTACHMENTS_DIR/{process_id}/` e de seus arquivos em `src/pivma/core/attachment_service.py`
- [X] T021 [US1] Expor `POST /processes/{id}/lifecycle` para `DELETE_DRAFT` com resposta `deleted=true` em `src/pivma/routers/processes.py`
- [X] T022 [US1] Mapear processo fisicamente removido para categoria HTTP `not_found` em `src/pivma/routers/processes.py`

**Checkpoint**: A exclusão física de rascunho é utilizável pelo proponente e remove o agregado e seus anexos.

---

## Phase 4: User Story 2 - Cancelar um processo em validação (Priority: P1)

**Goal**: Permitir que Administrador ou BraCVAM cancele um processo submetido, interrompa trabalho pendente e preserve o histórico.

**Independent Test**: Submeter um processo com trabalho humano e execução de IA pendentes, cancelá-lo como administrador e verificar status, cascata seletiva, bloqueio de escrita e auditoria.

### Tests for User Story 2

- [X] T023 [US2] Criar teste de API para `CANCEL` autorizado retornar `CANCELLED` em `tests/api/routers/test_process_retirement.py`
- [X] T024 [US2] Criar teste de API para `CANCEL` preencher `closed_at` em `tests/api/routers/test_process_retirement.py`
- [X] T025 [US2] Criar teste de API para `CANCEL` preservar a justificativa em `closure_reason` em `tests/api/routers/test_process_retirement.py`
- [X] T026 [US2] Criar teste de API para `CANCEL` cancelar tarefa pendente em `tests/api/routers/test_process_retirement.py`
- [X] T027 [US2] Criar teste de API para `CANCEL` cancelar execução de atividade pendente em `tests/api/routers/test_process_retirement.py`
- [X] T028 [US2] Criar teste de API para `CANCEL` cancelar atividade pendente em `tests/api/routers/test_process_retirement.py`
- [X] T029 [US2] Criar teste de API para `CANCEL` cancelar fase pendente em `tests/api/routers/test_process_retirement.py`
- [X] T030 [US2] Criar teste de API para `CANCEL` cancelar `EvaluationRun` em progresso em `tests/api/routers/test_process_retirement.py`
- [X] T031 [US2] Criar teste de API para `CANCEL` preservar tarefa concluída em `tests/api/routers/test_process_retirement.py`
- [X] T032 [US2] Criar teste de API para `CANCEL` preservar formulário pendente sem submetê-lo em `tests/api/routers/test_process_retirement.py`
- [X] T033 [US2] Criar teste de API para `CANCEL` criar evento `PROCESS_CANCELLED` com contagens em `tests/api/routers/test_process_retirement.py`
- [X] T034 [US2] Criar teste de segurança para usuário comum receber `forbidden` ao cancelar em `tests/api/routers/test_process_retirement.py`
- [X] T035 [US2] Criar teste de API para cancelar processo `CLOSED` retornar `invalid_transition` em `tests/api/routers/test_process_retirement.py`
- [X] T036 [US2] Criar teste de API para cancelar processo `CANCELLED` retornar `invalid_transition` em `tests/api/routers/test_process_retirement.py`
- [X] T037 [US2] Criar teste de API para salvar formulário de processo cancelado retornar erro de transição em `tests/api/routers/test_process_retirement.py`
- [X] T038 [US2] Criar teste de API para submeter formulário de processo cancelado retornar erro de transição em `tests/api/routers/test_process_retirement.py`
- [X] T039 [US2] Criar teste de API para decisão de triagem em processo cancelado retornar erro de transição em `tests/api/routers/test_process_retirement.py`
- [X] T040 [US2] Criar teste de integração para conclusão tardia de pré-avaliação não alterar processo cancelado em `tests/integration/ai/test_process_retirement_pre_evaluation.py`
- [X] T041 [US2] Criar teste de integração para retry de pré-avaliação em processo cancelado retornar erro de transição em `tests/integration/ai/test_process_retirement_pre_evaluation.py`
- [X] T042 [P] [US2] Criar teste de integração para segunda ação concorrente não criar auditoria de sucesso em `tests/integration/database/test_process_retirement_concurrency.py`

### Implementation for User Story 2

- [X] T043 [US2] Implementar ramo `CANCEL` atômico com autorização de plataforma e bloqueio de linha em `src/pivma/core/process_engine.py`
- [X] T044 [US2] Cancelar filhos não terminais e preservar filhos terminais no ramo `CANCEL` de `src/pivma/core/process_engine.py`
- [X] T045 [US2] Registrar `PROCESS_CANCELLED` com estados, justificativa e contagens de filhos em `src/pivma/core/process_engine.py`
- [X] T046 [US2] Aplicar guarda de processo mutável aos caminhos de edição e submissão em `src/pivma/core/process_engine.py`
- [X] T047 [US2] Aplicar guarda de processo mutável aos caminhos de revisão e decisão de triagem em `src/pivma/core/process_engine.py`
- [X] T048 [US2] Impedir `_execute` de rotear pré-avaliação após cancelamento em `src/pivma/core/pre_evaluation_service.py`
- [X] T049 [US2] Impedir `_mark_failed` e `_sweep_stale_runs` de alterar processo cancelado em `src/pivma/core/pre_evaluation_service.py`
- [X] T050 [US2] Impedir `retry_run` de criar pré-avaliação para processo cancelado em `src/pivma/core/pre_evaluation_service.py`
- [X] T051 [US2] Mapear recusa de cancelamento para categoria HTTP `invalid_transition` em `src/pivma/routers/processes.py`

**Checkpoint**: Cancelamento interrompe trabalho pendente em uma transação, preserva histórico e bloqueia fluxos síncronos ou assíncronos posteriores.

---

## Phase 5: User Story 3 - Arquivar um processo terminal (Priority: P2)

**Goal**: Permitir que Administrador ou BraCVAM arquive processos encerrados sem alterar seu histórico.

**Independent Test**: Arquivar um processo `CLOSED` e outro `CANCELLED`; confirmar que ambos saem da listagem padrão e entram na consulta histórica autorizada.

### Tests for User Story 3

- [X] T052 [US3] Criar teste de API para arquivar processo `CLOSED` retornar `ARCHIVED` em `tests/api/routers/test_process_retirement.py`
- [X] T053 [US3] Criar teste de API para arquivar processo `CANCELLED` retornar `ARCHIVED` em `tests/api/routers/test_process_retirement.py`
- [X] T054 [US3] Criar teste de API para arquivamento registrar `PROCESS_ARCHIVED` com status terminal anterior em `tests/api/routers/test_process_retirement.py`
- [X] T055 [US3] Criar teste de API para arquivar processo ativo retornar `invalid_transition` em `tests/api/routers/test_process_retirement.py`
- [X] T056 [US3] Criar teste de API para arquivar rascunho retornar `invalid_transition` em `tests/api/routers/test_process_retirement.py`
- [X] T057 [US3] Criar teste de segurança para usuário comum receber `forbidden` ao arquivar em `tests/api/routers/test_process_retirement.py`
- [X] T058 [US3] Criar teste de API para `GET /processes` omitir processos arquivados em `tests/api/routers/test_process_retirement.py`
- [X] T059 [US3] Criar teste de API para `GET /processes?status=ARCHIVED` retornar arquivo para ator de plataforma em `tests/api/routers/test_process_retirement.py`
- [X] T060 [US3] Criar teste de segurança para consulta `status=ARCHIVED` sem acesso de plataforma retornar `forbidden` em `tests/api/routers/test_process_retirement.py`
- [X] T061 [US3] Criar teste de API para edição de formulário de processo arquivado retornar erro de transição em `tests/api/routers/test_process_retirement.py`
- [X] T062 [US3] Criar teste de API para linha do tempo de processo arquivado expor o evento de arquivamento em `tests/api/routers/test_process_retirement.py`

### Implementation for User Story 3

- [X] T063 [US3] Implementar ramo `ARCHIVE` com autorização de plataforma em `src/pivma/core/process_engine.py`
- [X] T064 [US3] Registrar `PROCESS_ARCHIVED` com status anterior e justificativa em `src/pivma/core/process_engine.py`
- [X] T065 [US3] Omitir `ARCHIVED` quando `GET /processes` não recebe filtro de status em `src/pivma/routers/processes.py`
- [X] T066 [US3] Autorizar a consulta explícita `status=ARCHIVED` somente para acesso de plataforma em `src/pivma/routers/processes.py`

**Checkpoint**: Arquivamento separa histórico de operação sem excluir dados ou permitir novas mutações.

---

## Phase 6: User Story 4 - Front-end conhece as ações permitidas (Priority: P3)

**Goal**: Entregar códigos de ação e falha estáveis para a interface sem transferir a autorização ao cliente.

**Independent Test**: Consultar os mesmos processos como proponente e como administrador e comparar `available_actions` com o resultado da ação enviada ao backend.

### Tests for User Story 4

- [X] T067 [US4] Criar teste de API para rascunho próprio expor `DELETE_DRAFT` em `available_actions` em `tests/api/routers/test_process_retirement.py`
- [X] T068 [US4] Criar teste de API para rascunho alheio não expor `DELETE_DRAFT` ao proponente em `tests/api/routers/test_process_retirement.py`
- [X] T069 [US4] Criar teste de API para processo ativo expor `CANCEL` ao ator de plataforma em `tests/api/routers/test_process_retirement.py`
- [X] T070 [US4] Criar teste de API para processo `CLOSED` expor `ARCHIVE` ao ator de plataforma em `tests/api/routers/test_process_retirement.py`
- [X] T071 [US4] Criar teste de API para processo arquivado expor lista vazia de ações em `tests/api/routers/test_process_retirement.py`
- [X] T072 [US4] Criar teste de API para justificativa em branco retornar código `invalid_justification` em `tests/api/routers/test_process_retirement.py`
- [X] T073 [US4] Criar teste de API para processo invisível retornar código `not_found` em `tests/api/routers/test_process_retirement.py`
- [X] T074 [US4] Criar teste de API para ação enviada fora de `available_actions` retornar código `invalid_transition` em `tests/api/routers/test_process_retirement.py`

### Implementation for User Story 4

- [X] T075 [US4] Implementar cálculo de `available_actions` com estado, evento de submissão e autorização em `src/pivma/core/process_engine.py`
- [X] T076 [US4] Incluir `available_actions` nas projeções de detalhe e listagem em `src/pivma/routers/processes.py`
- [X] T077 [US4] Padronizar códigos `not_found`, `forbidden`, `invalid_justification` e `invalid_transition` em `src/pivma/routers/processes.py`

**Checkpoint**: A interface recebe apenas ações aplicáveis e respostas de falha previsíveis; o backend revalida cada comando.

---

## Phase 7: Demonstração, seed e validação transversal

**Purpose**: Evidenciar o comportamento completo pela API real e fechar a qualidade da entrega.

- [X] T078 [P] Criar seed idempotente de rascunho com anexo, processo ativo, processo `CLOSED` e caso inválido em `scripts/seeds/seed_process_retirement.py`
- [X] T079 Atualizar o agregador de seeds para executar retirement em `scripts/seeds/seed_all.py`
- [X] T080 [P] Criar página de demonstração desacoplada que usa autenticação e contratos reais em `demos/process-retirement/index.html`
- [X] T081 Registrar a demonstração de retirement e seu comando de seed em `demos/index.html`
- [X] T082 Executar os cenários de `quickstart.md` contra a API local e registrar ajustes necessários em `specs/022-process-retirement/quickstart.md`
- [X] T083 Executar Ruff nos arquivos alterados e corrigir problemas em `src/`, `tests/`, `scripts/seeds/` e `demos/`
- [X] T084 Executar a suíte direcionada de API em `tests/api/routers/test_process_retirement.py`
- [X] T085 Executar a suíte direcionada de integração assíncrona em `tests/integration/ai/test_process_retirement_pre_evaluation.py`
- [X] T086 Executar a suíte direcionada de concorrência em `tests/integration/database/test_process_retirement_concurrency.py`
- [X] T087 Executar a suíte direcionada de exclusão física em `tests/integration/database/test_process_retirement_deletion.py`

---

## Dependencies & Execution Order

```text
Preparação → Fundamentos → US1 (MVP) → US2 → US3 → US4 → Demonstração e validação
                                    └─────────────────────→ Demo e seed podem começar após US3
```

- A Phase 2 bloqueia todas as histórias porque define o critério de rascunho, a guarda e os schemas.
- US1 entrega o endpoint e a exclusão física em cascata do rascunho.
- US2 reutiliza o endpoint para cancelamento e adiciona as guardas de escrita e IA.
- US3 acrescenta arquivamento e a consulta histórica após a base de cancelamento.
- US4 projeta ações permitidas e padroniza os códigos depois que as transições existem.
- T078 e T080 podem ocorrer em paralelo após US3; T079 e T081 dependem dos arquivos criados por elas.

## Parallel Opportunities

```text
Após T002:
  T003, T006 e T008 podem começar em arquivos distintos.

Após US3:
  T078 (seed) e T080 (demo) podem ocorrer em paralelo.

Após T077:
  T083, T084, T085, T086 e T087 podem executar em paralelo.
```

## Parallel Examples by User Story

### US1

As tarefas de US1 alteram router, motor e dois arquivos de teste. Execute T011 até T022 em sequência para manter testes e implementação alinhados.

### US2

```text
Após T002, a equipe pode criar em paralelo:
  T042 em tests/integration/database/test_process_retirement_concurrency.py
  T023 em tests/api/routers/test_process_retirement.py
```

### US3

As tarefas de US3 compartilham `tests/api/routers/test_process_retirement.py` e `src/pivma/routers/processes.py`. Execute T052 até T066 em sequência.

### US4

As tarefas de US4 dependem das transições concluídas e compartilham as projeções de processo. Execute T067 até T077 em sequência.

## Implementation Strategy

### MVP

1. Execute T001 até T022.
2. Rode T011 até T018 antes de T019 até T022.
3. Valide exclusão física, ausência de registros órfãos e remoção do diretório de anexos antes de iniciar o cancelamento.

### Incremental delivery

1. US1 entrega descarte físico seguro de rascunho.
2. US2 entrega interrupção segura do pipeline, incluindo a regressão da execução tardia.
3. US3 separa o histórico das listagens operacionais.
4. US4 entrega a projeção leve para o front-end.
5. A fase final adiciona a demo e executa as validações descritas no quickstart.
