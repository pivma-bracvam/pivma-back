# Implementation Plan: Regra de Consolidação: Todos os Campos Conformes para Avançar à Triagem

**Branch**: `026-all-fields-compliant-routing` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-all-fields-compliant-routing/spec.md`

## Summary

Substitui a regra de consolidação da pré-avaliação por IA (Spec 013, FR-030) por
uma regra mais estrita: a submissão só avança automaticamente para a triagem do
BraCVAM quando **todos** os critérios avaliados concluírem como **conforme**;
qualquer critério **não conforme**, **parcialmente conforme** ou **indeterminado**
(ex.: documento/OCR/imagem mockados, por decisão explícita da Clarification
Session 2026-09-18) devolve a submissão ao proponente, independentemente da
severidade. A abordagem técnica é a menor mudança possível: reescrever o
predicado de bloqueio dentro da função pura `consolidate()` de
`src/pivma/ai/consolidation.py`. Nenhum endpoint, schema, migração ou fluxo de
roteamento/triagem muda de forma — apenas a condição que decide `positive` vs
`negative`.

## Technical Context

**Language/Version**: Python >=3.14 (`pyproject.toml`)

**Primary Dependencies**: FastAPI, SQLAlchemy (async) + Alembic, pydantic-settings,
LangChain/langchain-openai (via provedor de modelos já existente, não tocado por
esta feature)

**Storage**: PostgreSQL (via SQLAlchemy async + psycopg); **nenhuma migração
necessária** nesta feature — não há alteração de schema.

**Testing**: pytest + pytest-asyncio, Testcontainers (Postgres real em
integração/API), Factory Boy, provedor de IA fake/stub nas camadas `unit`/`api`/CI
(sem chamadas externas), seguindo a skill `fastapi-testing-methodology` do projeto.

**Target Platform**: Servidor Linux (mesmo runtime do restante do backend).

**Project Type**: Web service (backend único, `src/pivma/`); sem frontend/mobile
nesta feature.

**Performance Goals**: N/A além do já garantido pela Spec 013 (submissão confirma
em <2s; processamento de pré-avaliação em background) — esta feature não muda
custo computacional, apenas a condição de ramificação após o processamento já
existente.

**Constraints**: Nenhuma execução de pré-avaliação histórica pode ser
reprocessada ou ter seu resultado recalculado retroativamente (FR-007).

**Scale/Scope**: Uma função pura (`consolidate`), seus testes unitários, e os
testes de integração/API que hoje fixam o comportamento antigo baseado em
severidade.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` neste repositório é o template não preenchido
(placeholders `[PRINCIPLE_N_NAME]`), sem princípios ratificados a verificar. Não há
gate constitucional formal a aplicar. Nenhuma violação a justificar em
Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/026-all-fields-compliant-routing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── consolidation-rule.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Projeto único (backend FastAPI), sem separação frontend/backend. Estrutura real já
existente — esta feature só toca os arquivos marcados com `*`:

```text
src/pivma/
├── ai/
│   └── consolidation.py *   # Predicado de bloqueio (Decisão 2 do research.md)
├── core/
│   ├── pre_evaluation_service.py   # Consumidor de consolidate(); sem mudança de lógica
│   ├── process_engine.py           # Roteamento/transições; sem mudança
│   └── database/models.py          # EvaluationRunItem.is_alert; sem mudança de schema
└── routers/
    └── pre_evaluation.py           # GET /processes/{id}/pre-evaluation; sem mudança de shape

tests/
├── unit/ai/
│   └── test_consolidation.py *     # Reescrever casos que fixam a regra antiga
├── integration/ai/
│   └── test_run_pre_evaluation.py *  # Adicionar caso severidade baixa + não conforme → negativo
└── api/routers/
    └── test_pre_evaluation_get.py   # Revisar se fixa contagem/alerts da regra antiga
```

**Structure Decision**: Nenhuma estrutura nova. A mudança é cirúrgica dentro do
projeto único já existente (`src/pivma/ai/consolidation.py` + testes
correspondentes); não há necessidade de novos módulos, routers, tabelas ou
diretórios.

## Complexity Tracking

*Sem violações do Constitution Check a justificar — seção não aplicável.*
