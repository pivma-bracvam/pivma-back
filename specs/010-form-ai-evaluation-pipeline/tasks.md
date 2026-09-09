# Tasks: Pipeline de IA para Formulários (Fase 1 - Estrutura Base e Mock)

**Branch**: `010-form-ai-evaluation-pipeline` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup (Shared Infrastructure & Dependencies)

**Purpose**: Inicialização das dependências e estrutura de diretórios do projeto

- [x] T001 Adicionar dependência `structlog` no pyproject.toml e atualizar o ambiente virtual
- [x] T002 [P] Criar diretórios de armazenamento de logs locais em logs/application/ e logs/ai/ com arquivo .gitignore
- [x] T003 [P] Criar estrutura básica das pastas de demonstração em demos/operational-index/ e demos/ai-pipeline/

---

## Phase 2: Foundational (Core Infrastructure & Logging Engine)

**Purpose**: Infraestrutura transversal de logging estruturado e extensão de esquema do formulário

**⚠️ CRITICAL**: Nenhuma user story de IA pode ser implementada antes da conclusão desta fase

- [x] T004 Implementar configuração central de logging estruturado com structlog e TimedRotatingFileHandler (retenção 7 dias) em src/pivma/core/logging.py
- [x] T005 [P] Estender modelo FormField com `ai_evaluation_enabled` (bool, default False), `ai_context_instructions` e `ai_validation_rules` em src/pivma/core/database/models.py e src/pivma/schemas.py
- [x] T006 Gerar e aplicar migração Alembic para adicionar os campos de IA na tabela form_fields em migrations/versions/
- [x] T007 [P] Implementar schemas e dataclasses de telemetria e veredito canônico (OperationalEventIndex, AIStepExecutionLog, AIEvaluationVerdict, PipelineExecutionGroup) em src/pivma/ai/contracts.py

**Checkpoint**: Base de dados e logging estruturado prontos — implementação das User Stories liberada.

---

## Phase 3: User Story 1 - Execução do Pipeline Simulado de IA para Campos Sinalizados (Priority: P1) 🎯 MVP

**Goal**: Filtrar campos do formulário com `ai_evaluation_enabled = True`, executar 3 etapas sequenciais simuladas (Extração, Avaliação Mock, Síntese) e retornar o veredito canônico negativo por padrão (`REPROVED` / `NEEDS_ADJUSTMENT`).

**Independent Test**: Submeter uma instância de formulário com campos marcados para IA via `POST /forms/instances/{instance_id}/evaluate-ai` e validar o retorno 200 com veredito negativo estruturado contendo score de confiança, inconformidades simuladas e recomendações.

### Tests for User Story 1 ⚠️

- [x] T008 [P] [US1] Criar testes unitários para o orquestrador e as 3 etapas simuladas do pipeline em tests/unit/test_ai_pipeline.py
- [x] T009 [P] [US1] Criar teste de integração para o endpoint de avaliação de formulários em tests/integration/test_form_ai_evaluation_api.py

### Implementation for User Story 1

- [x] T010 [P] [US1] Implementar Etapa 1 (ContextExtractionStep) para extrair e higienizar valores de campos com ai_evaluation_enabled=True em src/pivma/ai/steps/context_extraction.py
- [x] T011 [P] [US1] Implementar Etapa 2 (MockEvaluationStep) simulando verificação de conformidade, gerando latência e custo simulado em src/pivma/ai/steps/mock_evaluation.py
- [x] T012 [P] [US1] Implementar Etapa 3 (VerdictSynthesisStep) consolidando retorno canônico com veredito negativo padrão, issues e recomendações em src/pivma/ai/steps/verdict_synthesis.py
- [x] T013 [US1] Implementar orquestrador FormAIPipelineEngine com propagação de correlation_id e registro em logs/ai/ e logs/application/ em src/pivma/ai/pipeline.py
- [x] T014 [US1] Implementar endpoint de disparo de avaliação `POST /forms/instances/{instance_id}/evaluate-ai` em src/pivma/routers/forms.py

**Checkpoint**: User Story 1 (MVP) totalmente funcional e testável de forma independente.

---

## Phase 4: User Story 2 - Registro Estruturado e Streaming em Tempo Real para Administradores (Priority: P2)

**Goal**: Disponibilizar endpoints administrativos para leitura de histórico e streaming em tempo real (Server-Sent Events / SSE) de eventos operacionais e eventos de IA agrupados por pipeline.

**Independent Test**: Conectar com usuário Administrador aos endpoints `/admin/logs/operational/stream` e `/admin/logs/ai/stream`, disparar avaliações e constatar recebimento das mensagens SSE em tempo real agrupadas por correlation_id.

### Tests for User Story 2 ⚠️

- [x] T015 [P] [US2] Criar testes de integração para as rotas administrativas e streaming SSE em tests/integration/test_admin_logs_sse.py

### Implementation for User Story 2

- [x] T016 [US2] Implementar serviço de leitura e agregação de logs JSONL por correlation_id em src/pivma/core/log_service.py
- [x] T017 [US2] Implementar gerenciador de transmissão SSE em tempo real (EventBroadcaster) em src/pivma/core/sse_broadcaster.py
- [x] T018 [US2] Implementar roteador de logs administrativos (/admin/logs/operational, /admin/logs/operational/stream, /admin/logs/ai, /admin/logs/ai/stream) com verificação de Role.ADMIN em src/pivma/routers/admin_logs.py
- [x] T019 [US2] Registrar roteador admin_logs em src/pivma/__init__.py

**Checkpoint**: Endpoints administrativos e streaming SSE funcionais e testados.

---

## Phase 5: User Story 3 - Demonstração: Módulo de Visualização Geral (Índice Operacional em Tempo Real) (Priority: P3)

**Goal**: Criar interface interativa de demonstração em `demos/operational-index/` consumindo SSE da API real para exibir o fluxo cronológico de eventos operacionais da plataforma.

**Independent Test**: Acessar `demos/operational-index/index.html`, informar token de administrador, disparar requisições e verificar a exibição em tempo real de eventos operacionais com status, duração total e correlation_id.

### Implementation for User Story 3

- [x] T020 [P] [US3] Implementar página e scripts da interface de Visualização Geral com consumo de SSE e filtros em demos/operational-index/index.html e demos/operational-index/app.js
- [x] T021 [US3] Criar catálogo central unificado de demonstrações em demos/index.html listando os módulos da plataforma conforme AGENTS.md

**Checkpoint**: Módulo 1 de demonstração operacional acessível e validado com a API real.

---

## Phase 6: User Story 4 - Demonstração: Módulo de Visualização da IA (Pipelines Agrupados em Tempo Real) (Priority: P4)

**Goal**: Criar interface interativa de demonstração em `demos/ai-pipeline/` consumindo SSE da API real para exibir pipelines de IA agrupados pela execução com inspeção de etapas, latência, custos e payloads.

**Independent Test**: Acessar `demos/ai-pipeline/index.html`, acionar avaliação de formulário pelo painel e verificar os cards de pipeline sendo criados e atualizados em tempo real com as 3 etapas e payloads expansíveis.

### Implementation for User Story 4

- [x] T022 [P] [US4] Implementar interface interativa de Visualização de IA com cards agrupados por pipeline, timeline das 3 etapas e visualizador de payloads em demos/ai-pipeline/index.html e demos/ai-pipeline/app.js
- [x] T023 [US4] Registrar Módulo de IA no catálogo central em demos/index.html
- [x] T024 [US4] Implementar script de carga de seed em scripts/seeds/seed_form_ai_demo.py provisionando template com campos de IA e usuário admin

**Checkpoint**: Módulo 2 de demonstração de IA operacional e validado de ponta a ponta.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ajustes finais, testes de rotação, linting e validação do quickstart

- [x] T025 [P] Criar testes unitários para a rotação e retenção de 7 dias de logs em tests/unit/test_structured_logging.py
- [x] T026 Atualizar template declarativo com flag de IA no campo de justificativa em src/pivma/templates_data/full_validation_v1.yaml
- [x] T027 Executar formatação e verificação de lint com ruff check e ruff format no projeto
- [x] T028 Executar validação ponta a ponta dos cenários de teste descritos em specs/010-form-ai-evaluation-pipeline/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências externas — execução imediata.
- **Foundational (Phase 2)**: Depende do Setup — **BLOQUEIA** todas as User Stories.
- **User Story 1 (Phase 3)**: Depende da conclusão da Phase 2 (Foundational).
- **User Story 2 (Phase 4)**: Depende da conclusão da Phase 3 (US1 gera os eventos que o streaming transmite).
- **User Story 3 (Phase 5)**: Depende da Phase 4 (consome os endpoints de streaming operacional).
- **User Story 4 (Phase 6)**: Depende da Phase 4 (consome os endpoints de streaming de IA agrupado).
- **Polish (Phase 7)**: Depende da conclusão de todas as User Stories anteriores.

---

## Parallel Opportunities

- **Phase 1**: T002 e T003 podem ser executados em paralelo com T001.
- **Phase 2**: T005 e T007 podem ser executados em paralelo com T004.
- **Phase 3**: T008 (testes unitários) e T009 (testes de integração) podem ser escritos em paralelo; T010, T011 e T012 (as 3 etapas do pipeline) podem ser desenvolvidas em paralelo antes da orquestração T013.
- **Phase 4**: T015 (testes de integração) pode ser implementado antes/em paralelo com T016 e T017.
- **Phase 5 e Phase 6**: As interfaces de demonstração em `demos/operational-index/` (T020) e `demos/ai-pipeline/` (T022) podem ser implementadas em paralelo por diferentes desenvolvedores após a entrega da Phase 4.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Executar Phase 1 (Setup) e Phase 2 (Foundational).
2. Implementar Phase 3 (User Story 1: Pipeline em 3 etapas simuladas + endpoint de avaliação).
3. **VALIDAR MVP**: Executar testes unitários e de integração (`pytest tests/unit/test_ai_pipeline.py tests/integration/test_form_ai_evaluation_api.py`).

### Entrega Incremental

1. **Incremento 1 (MVP)**: Avaliação de campos de formulário via pipeline simulado com retorno negativo padronizado.
2. **Incremento 2 (US2)**: Endpoints administrativos de consulta e streaming SSE em tempo real com retenção de 7 dias.
3. **Incremento 3 (US3)**: Demonstração interativa do Índice Operacional em `demos/operational-index/`.
4. **Incremento 4 (US4)**: Demonstração interativa do Pipeline de IA agrupado por execução em `demos/ai-pipeline/` + carga via seed `seed_form_ai_demo.py`.
5. **Incremento 5 (Polish)**: Validação integrada do `quickstart.md`, lint e suíte de testes completa.
