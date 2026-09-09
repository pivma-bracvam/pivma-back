# Implementation Tasks: 011 - Processos Padrão do Sistema (5 Pipelines Oficiais e Fase 1: Submissão, Avaliação por IA e Deliberação BraCVAM)

**Feature**: `011-standard-process-templates`
**Date**: 2026-09-09
**Spec**: [specs/011-standard-process-templates/spec.md](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/specs/011-standard-process-templates/spec.md)
**Plan**: [specs/011-standard-process-templates/plan.md](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/specs/011-standard-process-templates/plan.md)

---

## Phase 1: Setup (Infraestrutura e Limpeza de Templates)

**Purpose**: Remover o template mock legado e estruturar o diretório para os novos templates oficiais.

- [x] T001 Excluir arquivo de template demonstrativo legado em `src/pivma/templates_data/full_validation_v1.yaml`
- [x] T002 [P] Atualizar carregador assíncrono em `src/pivma/bootstrap_process_templates.py` para desativar templates não mais presentes no diretório `templates_data`
- [x] T003 [P] Criar esquema base de validação e parser para os 5 novos templates declarativos em `src/pivma/bootstrap_process_templates.py`

---

## Phase 2: Foundational (Pré-Requisitos e Integração do Motor de IA)

**Purpose**: Ajustar o motor de processos para suportar os 5 templates e disparar o pipeline de IA na submissão.

- [x] T004 Adaptar `submit_proposal_form` em `src/pivma/core/process_engine.py` para invocar o `FormAIPipelineEngine` da Spec 010 para os campos sinalizados com `ai_evaluation_enabled`
- [x] T005 [P] Criar geração e persistência do artefato `ai_evaluation_report` vinculado à `ActivityRun` da submissão em `src/pivma/core/process_engine.py`
- [x] T006 [P] Garantir que o desbloqueio da triagem em `_unblock_triage_activity` em `src/pivma/core/process_engine.py` disponibilize o parecer de IA e mantenha compatibilidade com os 5 processos

**Checkpoint**: Motor de processos e bootstrap prontos para receber as definições dos 5 processos oficiais.

---

## Phase 3: User Story 1 - Seleção e Instanciação dos Processos Oficiais do BraCVAM (Priority: P1) 🎯 MVP

**Goal**: Disponibilizar os 5 processos oficiais do BraCVAM via carga declarativa e permitir sua instanciação pelos proponentes, extinguindo o template anterior.

**Independent Test**: Executar o bootstrap e consultar `GET /processes/templates`. O retorno deve conter exatamente os 5 novos processos oficiais ativos e nenhuma referência a `full_validation`. Instanciar um processo com `POST /processes` para cada uma das 5 chaves com sucesso.

### Tests for User Story 1 ⚠️

- [x] T007 [P] [US1] Atualizar testes de unidade do carregador declarativo em `tests/unit/core/test_template_loader.py` para validar a carga dos 5 novos templates e a ausência de `full_validation`
- [x] T008 [P] [US1] Atualizar testes de listagem e instanciação de templates em `tests/api/routers/test_process_router.py` cobrindo as 5 chaves semânticas

### Implementation for User Story 1

- [x] T009 [P] [US1] Criar arquivo declarativo do Processo 1 em `src/pivma/templates_data/01_pre_validated_method.yaml` (key: `pre_validated_method`, name: "Método Pré-Validado")
- [x] T010 [P] [US1] Criar arquivo declarativo do Processo 2 em `src/pivma/templates_data/02_scope_extension.yaml` (key: `scope_extension`, name: "Extensão de Escopo de Aplicação")
- [x] T011 [P] [US1] Criar arquivo declarativo do Processo 3 em `src/pivma/templates_data/03_me_too_validation.yaml` (key: `me_too_validation`, name: "Validação Me-Too")
- [x] T012 [P] [US1] Criar arquivo declarativo do Processo 4 em `src/pivma/templates_data/04_validated_method_dossier.yaml` (key: `validated_method_dossier`, name: "Método Validado – Dossiê Submetido")
- [x] T013 [P] [US1] Criar arquivo declarativo do Processo 5 em `src/pivma/templates_data/05_proof_of_concept.yaml` (key: `proof_of_concept`, name: "Prova de Conceito (PoC)")
- [x] T014 [US1] Ajustar inicialização e instanciação em `src/pivma/routers/processes.py` para validar e mapear os 5 templates oficiais

**Checkpoint**: User Story 1 completa e testável como MVP independente (5 templates oficiais ativos e instanciáveis).

---

## Phase 4: User Story 2 - Elaboração e Envio da Submissão pelo Proponente (Priority: P2)

**Goal**: Permitir que o proponente elabore rascunhos e envie a submissão com os formulários dedicados de cada uma das 5 modalidades de método.

**Independent Test**: Criar instâncias dos 5 tipos de processo, consultar o formulário específico de cada um em `GET /processes/{id}/activities/proposal_submission/form`, salvar rascunhos parciais e submeter com sucesso.

### Tests for User Story 2 ⚠️

- [x] T015 [P] [US2] Atualizar testes de formulários e submissão em `tests/api/routers/test_form_submission.py` para utilizar `pre_validated_method` e `submission_pre_validated_v1`
- [x] T016 [P] [US2] Adicionar testes cobrindo a validação de campos dedicados dos 5 formulários em `tests/api/routers/test_form_submission.py`

### Implementation for User Story 2

- [x] T017 [P] [US2] Definir campos do formulário `submission_pre_validated_v1` em `src/pivma/templates_data/01_pre_validated_method.yaml`
- [x] T018 [P] [US2] Definir campos do formulário `submission_scope_extension_v1` em `src/pivma/templates_data/02_scope_extension.yaml`
- [x] T019 [P] [US2] Definir campos do formulário `submission_me_too_v1` em `src/pivma/templates_data/03_me_too_validation.yaml`
- [x] T020 [P] [US2] Definir campos do formulário `submission_validated_dossier_v1` em `src/pivma/templates_data/04_validated_method_dossier.yaml`
- [x] T021 [P] [US2] Definir campos do formulário `submission_proof_of_concept_v1` em `src/pivma/templates_data/05_proof_of_concept.yaml`
- [x] T022 [US2] Implementar suporte no validador de formulário em `src/pivma/core/process_engine.py` para as regras dos campos dedicados dos 5 novos formulários

**Checkpoint**: User Stories 1 e 2 totalmente operacionais de forma independente.

---

## Phase 5: User Story 3 - Avaliação Automatizada por IA e Pré-Análise Técnica (Priority: P3)

**Goal**: Disparar automaticamente o pipeline de IA da Spec 010 no momento do envio da proposta pelo proponente, gerando resultado mock negativo padrão (`NEEDS_ADJUSTMENT`) e gravando logs operacionais.

**Independent Test**: Submeter um formulário com campos marcados com `ai_evaluation_enabled: true`. Constatar que o veredito foi emitido com resultado negativo simulado, inconsistências e recomendações, com eventos registrados nos logs JSONL e broadcast SSE.

### Tests for User Story 3 ⚠️

- [x] T023 [P] [US3] Atualizar testes de integração da avaliação de IA em `tests/integration/test_form_ai_evaluation_api.py` para validar o trigger automático no envio da proposta
- [x] T024 [P] [US3] Adicionar teste unitário validando que campos não marcados com `ai_evaluation_enabled` são ignorados e campos marcados geram veredito padrão negativo em `tests/unit/core/test_process_engine.py`

### Implementation for User Story 3

- [x] T025 [P] [US3] Configurar instruções contextuais (`ai_context_instructions`) e flags `ai_evaluation_enabled: true` nos campos analíticos dos 5 arquivos YAML em `src/pivma/templates_data/`
- [x] T026 [US3] Integrar retorno da avaliação simulada de IA no payload de resposta do endpoint `POST /processes/{process_id}/activities/proposal_submission/submit` em `src/pivma/routers/forms.py`
- [x] T027 [US3] Persistir o relatório de veredito da IA no artefato do processo para recuperação na triagem em `src/pivma/core/process_engine.py`

**Checkpoint**: User Stories 1, 2 e 3 integradas com o pipeline de IA simulado.

---

## Phase 6: User Story 4 - Validação e Deliberação Final pelo BraCVAM (Priority: P4)

**Goal**: Permitir que os avaliadores do BraCVAM revisem os dados da submissão e os apontamentos da IA, emitindo decisão de Aprovação, Diligência (com reexecução Run #2) ou Rejeição.

**Independent Test**: Acessar tarefa de triagem, inspecionar parecer da IA e emitir `APPROVED` (avança processo para `PLANNING`), `NEEDS_REVISION` (cria Run #2 de submissão preservando dados anteriores) e `REJECTED` (encerra processo como `CLOSED`).

### Tests for User Story 4 ⚠️

- [x] T028 [P] [US4] Atualizar testes de decisão de triagem em `tests/api/routers/test_triage_decision.py` para validar transições com os novos templates oficiais
- [x] T029 [P] [US4] Atualizar testes de revisão campo a campo em `tests/api/routers/test_triage_review.py` para validar compatibilidade com os campos dos novos formulários

### Implementation for User Story 4

- [x] T030 [P] [US4] Garantir compatibilidade do fluxo de diligência (`_handle_needs_revision`) em `src/pivma/core/process_engine.py` com os formulários específicos dos 5 templates
- [x] T031 [US4] Disponibilizar acesso às análises da IA na consulta de tarefa de triagem em `src/pivma/routers/tasks.py` e `src/pivma/routers/triage.py`

**Checkpoint**: Ciclo completo da Fase 1 (Submissão → IA → BraCVAM) funcional para os 5 processos.

---

## Phase 7: Polish, Sementes & Demonstrações (AGENTS.md)

**Purpose**: Atualizar as suítes de testes residuais, os scripts de carga de dados e o catálogo de demonstrações.

- [x] T032 [P] Atualizar testes remanescentes que referenciavam `full_validation` em `tests/api/routers/test_tasks_router.py`, `tests/api/routers/test_timeline_router.py`, `tests/api/routers/test_participant_timeline.py` e `tests/api/routers/test_participant_task_blocking.py`
- [x] T033 [P] Atualizar script de seed geral em `scripts/seeds/seed_all.py` para popular instâncias dos 5 processos oficiais
- [x] T034 [P] Atualizar scripts de seed especializados em `scripts/seeds/seed_forms.py`, `scripts/seeds/seed_triage.py` e `scripts/seeds/seed_form_ai_demo.py` para utilizar as novas chaves
- [x] T035 [P] Atualizar catálogo de demonstração central em `demos/index.html` para listar e permitir selecionar os 5 processos oficiais
- [x] T036 [P] Atualizar interfaces de demonstração em `demos/submission/`, `demos/forms/` e `demos/triage/` para operar com os novos formulários declarativos
- [x] T037 Executar validação de ponta a ponta dos cenários descritos em `specs/011-standard-process-templates/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências - pode iniciar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup (Phase 1) - BLOQUEIA as histórias de usuário.
- **User Story 1 (Phase 3 - P1 🎯 MVP)**: Depende da Phase 2. Entrega os 5 processos no catálogo.
- **User Story 2 (Phase 4 - P2)**: Depende da Phase 3 (templates criados). Entrega os 5 formulários e submissão.
- **User Story 3 (Phase 5 - P3)**: Depende da Phase 4 (submissão ativa). Conecta o pipeline de IA simulado.
- **User Story 4 (Phase 6 - P4)**: Depende da Phase 5. Conecta a deliberação do BraCVAM com o parecer da IA.
- **Polish & Demos (Phase 7)**: Depende de todas as histórias anteriores concluídas.

### Parallel Opportunities

- **Phase 1**: T002 e T003 podem ser implementadas em paralelo após T001.
- **Phase 2**: T005 e T006 podem ser implementadas em paralelo.
- **Phase 3**: T007 e T008 (testes) em paralelo; T009 a T013 (os 5 arquivos YAML) podem ser criados em paralelo.
- **Phase 4**: T015 e T016 (testes) em paralelo; T017 a T021 (definição de campos dos formulários nos YAMLs) em paralelo.
- **Phase 5**: T023 e T024 (testes) em paralelo; T025 pode ser executada em paralelo com os testes.
- **Phase 6**: T028 e T029 (testes) em paralelo.
- **Phase 7**: T032 a T036 podem ser executadas em paralelo.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Concluir Setup (Phase 1) e Foundational (Phase 2).
2. Concluir User Story 1 (Phase 3): criar os 5 YAMLs oficiais e validar no catálogo `GET /processes/templates`.
3. Validar de forma independente: o sistema agora lista os 5 novos processos e rejeita `full_validation`.

### Entrega Incremental
1. **Incremento 1 (MVP)**: Catálogo dos 5 novos processos (`pre_validated_method`, `scope_extension`, `me_too_validation`, `validated_method_dossier`, `proof_of_concept`).
2. **Incremento 2**: Formulários dedicados e submissão com rascunhos.
3. **Incremento 3**: Avaliação simulada de IA disparada na submissão com logs estruturados.
4. **Incremento 4**: Triagem e parecer do BraCVAM deliberando sobre a proposta e análise da IA.
5. **Incremento 5 (AGENTS.md)**: Sementes atualizadas e demonstrações interativas operando de ponta a ponta.
