# Tasks: Estrutura Base de Processos e Fase 1: Submissão e Triagem

**Branch**: `feat/process-submission-triage` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialização da estrutura de diretórios e definições declarativas do pipeline

- [X] T001 Adicionar dependência `pyyaml` em `pyproject.toml` para leitura declarativa de templates
- [X] T002 [P] Criar diretório `src/pivma/templates_data/` para armazenar definições declarativas de templates e formulários
- [X] T003 [P] Criar arquivo de definição declarativa do pipeline de validação completa em `src/pivma/templates_data/full_validation_v1.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Modelagem de dados, persistência relacional, motor central de processos e infraestrutura de testes que bloqueiam todas as histórias

**⚠️ CRITICAL**: Nenhuma história de usuário pode ser iniciada antes da conclusão desta fase

- [X] T004 [P] Criar entidades ORM do motor de processos (`ProcessTemplate`, `ProcessTemplateVersion`, `ProcessInstance`, `Phase`, `ActivityInstance`, `ActivityRun`, `Task`, `FormTemplate`, `FormField`, `FormInstance`, `FormValue`, `FieldReview`, `Artifact`, `ActivityDependency`, `Assignment`, `Decision`, `AuditEvent`) em `src/pivma/core/database/models.py`
- [X] T005 Gerar migração Alembic para criação das tabelas do motor de processos e formulários em `migrations/versions/`
- [X] T006 [P] Implementar serviço/parser de templates declarativos YAML e sincronização de banco em `src/pivma/bootstrap_process_templates.py`
- [X] T007 [P] Implementar motor de processos (`process_engine.py`) com regras de transição de estado, avaliação determinística de dependências e gerência de `ActivityRun` em `src/pivma/core/process_engine.py`
- [X] T008 [P] Implementar factories Factory Boy para instâncias de processo, atividades, tarefas e formulários em `tests/factories/process_factory.py`
- [X] T009 [P] Escrever testes de integração para constraints de banco e migração do motor de processos em `tests/integration/database/test_process_constraints.py` e `tests/integration/migrations/test_process_migration.py`
- [X] T010 [P] Escrever testes unitários para o carregador de templates YAML em `tests/unit/core/test_template_loader.py`
- [X] T011 [P] Escrever testes unitários para as transições de estado e cálculo de bloqueios de dependência em `tests/unit/core/test_process_engine.py`

**Checkpoint**: Fundação pronta - banco migrado, modelos, engine e factories verificados.

---

## Phase 3: User Story 1 - Submissão de Proposta de Validação (Priority: P1) 🎯 MVP

**Goal**: Permitir ao proponente instanciar processos a partir do template de Validação Completa, preencher formulários com validação dinâmica, salvar rascunhos e submeter formalmente gerando dossiê.

- [X] T012 [P] [US1] Escrever testes de contrato de API e integração para instanciação e listagem de processos em `tests/api/routers/test_process_router.py`
- [X] T013 [P] [US1] Escrever testes de API para inspeção, salvamento de rascunho e submissão com validação dinâmica de formulários em `tests/api/routers/test_form_submission.py`
- [X] T014 [P] [US1] Definir schemas Pydantic de requisição/resposta para processos, templates, formulários e valores em `src/pivma/schemas.py`
- [X] T015 [US1] Implementar endpoints de processos (`GET /processes/templates`, `GET /processes/templates/{key}`, `POST /processes`, `GET /processes`, `GET /processes/{id}`, `GET /processes/{id}/timeline`) em `src/pivma/routers/processes.py`
- [X] T016 [US1] Implementar endpoints de formulários (`GET /processes/{id}/activities/{activity_key}/form`, `PUT /processes/{id}/activities/{activity_key}/form`, `POST /processes/{id}/activities/{activity_key}/form`) em `src/pivma/routers/forms.py`
- [X] T017 [US1] Registrar novos roteadores (`processes`, `forms`) na aplicação FastAPI em `src/pivma/__init__.py`

**Checkpoint**: User Story 1 completa e testável independentemente. MVP operacional.

---

## Phase 4: User Story 2 - Triagem e Decisão Inicial (Priority: P2)

**Goal**: Permitir ao avaliador/triador revisar campos individualmente, registrar pareceres de conformidade e formalizar decisão com transição para Planning, Rejeição ou Diligência (com reexecução da submissão mantendo histórico).

- [X] T018 [P] [US2] Escrever testes de API para revisão campo a campo de triagem em `tests/api/routers/test_triage_review.py`
- [X] T019 [P] [US2] Escrever testes de API para decisões de triagem (Aprovação, Rejeição, Diligência/Needs Revision) em `tests/api/routers/test_triage_decision.py`
- [X] T020 [US2] Implementar endpoint de revisão de campos (`POST /processes/{id}/triage/reviews`) em `src/pivma/routers/triage.py`
- [X] T021 [US2] Implementar endpoint de decisão de triagem (`POST /processes/{id}/triage/decision`) com aplicação de transições no motor em `src/pivma/routers/triage.py`
- [X] T022 [US2] Registrar router de triagem na aplicação FastAPI em `src/pivma/__init__.py`

**Checkpoint**: User Story 1 e 2 integradas, suportando ciclo de vida completo de submissão e triagem com reexecução imutável.

---

## Phase 5: User Story 3 - Painel Operacional de Tarefas e Linha do Tempo (Priority: P3)

**Goal**: Permitir aos usuários visualizar a caixa de entrada de tarefas com filtros por status e papel, e consultar a linha do tempo imutável do processo.

- [X] T023 [P] [US3] Escrever testes de API para listagem e filtragem de tarefas por papel e status em `tests/api/routers/test_tasks_router.py`
- [X] T024 [P] [US3] Escrever testes de API para consulta de linha do tempo e auditoria do processo em `tests/api/routers/test_timeline_router.py`
- [X] T025 [US3] Implementar endpoint de caixa de tarefas (`GET /tasks`, `GET /tasks/{id}`) com filtros por papel e status em `src/pivma/routers/tasks.py`
- [X] T026 [US3] Implementar consulta de linha do tempo do processo (`GET /processes/{id}/timeline`) em `src/pivma/routers/processes.py`
- [X] T027 [US3] Registrar router de tarefas na aplicação FastAPI em `src/pivma/__init__.py`

**Checkpoint**: Todas as histórias de usuário funcionais e testáveis.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificação ponta a ponta, cobertura de testes e documentação

- [X] T028 [P] Executar cenários do guia de validação rápida (`specs/004-process-submission-triage/quickstart.md`)
- [X] T029 [P] Executar suíte completa de testes (`poetry run pytest`) garantindo 100% de sucesso
- [X] T030 [P] Atualizar documentação operacional no `README.md` com instruções de carregamento de templates e endpoints da Fase 1

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências - inicia imediatamente.
- **Foundational (Phase 2)**: Depende do Setup (Phase 1) - BLOQUEIA todas as histórias de usuário.
- **User Story 1 (Phase 3)**: Depende da conclusão da Phase 2. Constitui o MVP.
- **User Story 2 (Phase 4)**: Depende da conclusão da Phase 3 (utiliza o processo criado e submetido).
- **User Story 3 (Phase 5)**: Depende da conclusão da Phase 2 e consome dados de US1/US2.
- **Polish (Phase 6)**: Depende da conclusão das histórias de usuário.

### Parallel Opportunities

- **Phase 1**: T002 e T003 podem ser criados em paralelo.
- **Phase 2**: T004 (Modelos), T006 (YAML Parser), T007 (Engine) e T008 (Factories) podem ser desenvolvidos de forma modular; T009, T010 e T011 rodam em paralelo.
- **User Stories**: Testes de API marcados com `[P]` devem ser escritos primeiro (TDD).

---

## Implementation Strategy

### MVP First (User Story 1)
1. Concluir Setup (Phase 1) e Foundational (Phase 2).
2. Implementar User Story 1 (Submissão de Proposta).
3. Validar de ponta a ponta que uma proposta pode ser submetida e avançar para `TRIAGE`.

### Incremental Delivery
1. Adicionar User Story 2 (Triagem, Pareceres e Diligência com `ActivityRun #2`).
2. Adicionar User Story 3 (Quadro de Tarefas Operacionais e Timeline).
3. Executar suíte de integração e validação rápida.
