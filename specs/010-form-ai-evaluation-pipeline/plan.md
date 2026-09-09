# Implementation Plan: Pipeline de IA para Formulários (Fase 1 - Estrutura Base e Mock)

**Branch**: `010-form-ai-evaluation-pipeline` | **Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-form-ai-evaluation-pipeline/spec.md`

## Summary

Implementar a arquitetura inicial para avaliação automatizada de campos de formulários via IA operando em 3 etapas sequenciais simuladas (*mock*), com resposta canônica de produção e resultado negativo por padrão (`REPROVED` / `NEEDS_ADJUSTMENT`). Adicionar infraestrutura de logging estruturado em duas camadas (`logs/application/` para o Índice Operacional de Eventos e `logs/ai/` para o Log Granular de Etapas de IA) serializado em JSONL via `logging` nativo + `structlog` com retenção automática de 7 dias. Disponibilizar endpoints administrativos para streaming em tempo real (Server-Sent Events / SSE) com os registros de IA agrupados pela pipeline de origem, além de dois módulos de demonstração interativa em `demos/` e carga via `scripts/seeds/` conforme o [AGENTS.md](../../AGENTS.md).

## Technical Context

**Language/Version**: Python 3.13 (compatível com `pyproject.toml` `>=3.14,<4.0` / runtime 3.13+)  
**Primary Dependencies**: FastAPI (>=0.141), Pydantic v2, SQLAlchemy 2.0 (asyncio), `structlog` (adição como dependência para serialização JSONL), `pyyaml`  
**Storage**: PostgreSQL 16 (para `FormField.ai_evaluation_enabled` e dados da aplicação) e Arquivos locais em JSONL em `logs/application/` e `logs/ai/` (com rotação diária de 7 dias)  
**Testing**: pytest 9.1+, pytest-asyncio, testcontainers, factory-boy (seguindo `fastapi-testing-methodology`)  
**Target Platform**: Linux / Docker Container (backend FastAPI assíncrono)  
**Project Type**: Web service RESTful com streaming SSE e páginas estáticas de demonstração (`demos/`)  
**Performance Goals**: Execução do pipeline simulado em < 250ms por campo; latência de transmissão SSE < 100ms; resposta da API de observabilidade < 200ms  
**Constraints**: 
- 100% simulado (*mock*) na Fase 1, sem chamadas a modelos externos de LLM ou chaves de API pagas.
- Retenção máxima de 7 dias de logs locais com exclusão automática.
- Isolamento estrito entre `demos/` e `src/` (conforme `AGENTS.md`).
- Acesso a logs e streams restrito a usuários com perfil de Administrador (`Role.ADMIN`).  
**Scale/Scope**: Validação em formulários com múltiplos campos; suporte a múltiplos assinantes SSE em simultâneo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I - Modularidade e Desacoplamento**: PASS. O pipeline de IA (`src/pivma/ai/pipeline.py`) é desacoplado em 3 classes de etapa (`ContextExtractionStep`, `MockEvaluationStep`, `VerdictSynthesisStep`). O código das demonstrações (`demos/`) é totalmente desacoplado do backend (`src/`).
- **Princípio II - Test-First**: PASS. Casos de teste de unidade e integração para o pipeline, rotação de logs e rotas SSE planejados com base nos contratos.
- **Princípio III - Observabilidade e Simplicidade**: PASS. Sistema em duas camadas (Índice Geral e Detalhamento de IA) em formato JSONL leve, evitando coletores pesados (OpenTelemetry/Grafana) antes da necessidade real.
- **Princípio IV - Governança Normativa (AGENTS.md)**: PASS. Inclusão de dois módulos de demonstração interativa em `demos/`, catálogo unificado `demos/index.html` e script de seed em `scripts/seeds/seed_form_ai_demo.py`.

## Project Structure

### Documentation (this feature)

```text
specs/010-form-ai-evaluation-pipeline/
├── plan.md              # Este arquivo (plano de implementação técnica)
├── research.md          # Decisões arquiteturais e trade-offs
├── data-model.md        # Esquemas e modelos de dados (FormField, JSONL, Veredito)
├── quickstart.md        # Guia de validação ponta a ponta e testes
├── checklists/
│   └── requirements.md  # Checklist de validação de qualidade dos requisitos
└── contracts/
    └── admin_logs.openapi.yaml  # Contrato OpenAPI dos endpoints administrativos e de IA
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── database/
│   │   ├── models.py                   # Adição de ai_evaluation_enabled e ai_context no FormField
│   │   └── migrations/                 # Migração Alembic para os novos campos
│   └── logging.py                      # Configuração centralizada de logging + structlog + TimedRotatingFileHandler
├── ai/
│   ├── __init__.py
│   ├── contracts.py                    # Dataclasses/Pydantic schemas do pipeline e veredito
│   ├── pipeline.py                     # Orquestrador do pipeline de avaliação de formulários
│   └── steps/
│       ├── __init__.py
│       ├── context_extraction.py       # Etapa 1: extração e sanitização
│       ├── mock_evaluation.py          # Etapa 2: validação de conformidade simulada
│       └── verdict_synthesis.py        # Etapa 3: síntese canônica negativa
├── routers/
│   ├── admin_logs.py                   # Endpoints de consulta e streaming SSE (/admin/logs/*)
│   └── forms.py                        # Endpoint de disparo de avaliação por IA (/forms/instances/{id}/evaluate-ai)
└── schemas.py                          # Esquemas Pydantic atualizados para FormField e AI

logs/                                   # Diretório fora de src/
├── application/                        # Índice Operacional (events_YYYY-MM-DD.jsonl)
└── ai/                                 # Log Granular de Etapas de IA (ai_steps_YYYY-MM-DD.jsonl)

demos/                                  # Diretório de demonstração (desacoplado de src/)
├── index.html                          # Catálogo central das demonstrações
├── operational-index/
│   ├── index.html                      # Módulo 1: Visualização Geral (Tempo Real)
│   └── app.js                          # Consumo do stream SSE do Índice Operacional
└── ai-pipeline/
    ├── index.html                      # Módulo 2: Visualização da IA (Tempo Real agrupada por pipeline)
    └── app.js                          # Consumo do stream SSE agrupado e disparo de simulação

scripts/
└── seeds/
    └── seed_form_ai_demo.py            # Carga de teste mínima com campos de IA e usuário admin

tests/
├── unit/
│   ├── test_ai_pipeline.py             # Testes de unidade do pipeline e das 3 etapas
│   └── test_structured_logging.py      # Testes de unidade da rotação e formatação JSONL
└── integration/
    ├── test_form_ai_evaluation_api.py  # Teste de integração do disparo de avaliação
    └── test_admin_logs_sse.py          # Teste de integração das rotas administrativas de streaming
```

**Structure Decision**: Adotou-se o modelo de projeto único FastAPI modularizado (`src/pivma`), com separação dos submódulos `ai/` para o motor do pipeline, `logs/` fora de `src/` para persistência em JSONL, `demos/` para as interfaces interativas exigidas pelo `AGENTS.md` e `scripts/seeds/` para os scripts de carga.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Adição de dependência `structlog` | Serialização padronizada de dicionários complexos em JSONL com enriquecimento de contexto e performance | Serialização manual com `json.dumps` é propensa a falhas com tipos especiais (UUID, datetime) e poluente no código de negócio |
| Endpoints de streaming SSE | Transmissão de eventos em tempo real para atender ao requisito explícito de visualização em tempo real para administradores | Polling contínuo via HTTP degrada performance e aumenta latência de observabilidade |
