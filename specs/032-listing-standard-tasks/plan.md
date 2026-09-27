# Implementation Plan: Padrão de listagens e lista de tarefas para o quadro de atividades

**Branch**: `feat/032-listing-standard-tasks` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/032-listing-standard-tasks/spec.md`

## Summary

`GET /tasks` passa a responder no envelope padrão de listagem: `data`, `pagination` por página, `filters_applied`, `sort` e, sob demanda, `facets` e `summary`. O envelope é um modelo genérico que a Spec 033 reutiliza nas outras 20 listagens.

Cada tarefa traz o processo e a etapa como referências resumidas (`ProcessRef`, `PhaseRef`) e o campo `can_act`. `can_act` usa a mesma regra de `require_activity_access(..., 'edit')`: concessão de editar e nenhum conflito de interesse vigente. A regra vira uma expressão SQL que serve ao campo e ao filtro `actionable` (research R1, R2).

A lista considera só a rodada vigente por padrão (R3) e ganha os filtros `phase_order`, `activity_key` e `status` múltiplos e `overdue`, além de ordenação estável (R7). As contagens por atividade e status saem do mesmo conjunto filtrado (R5). O resumo conta os processos em pré-avaliação por IA (R6).

Sem tabela nova, sem migração e sem dependência nova.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2 (modelos genéricos e `model_serializer`)

**Storage**: PostgreSQL 17; sem mudança de esquema. Usa o índice único existente `uq_activity_runs_number_active` para a rodada vigente

**Testing**: Pytest + pytest-asyncio, testcontainers, factory_boy, `TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: número fixo de consultas por pedido (página, total, até 2 contagens, resumo), independente do número de tarefas; sem N+1

**Constraints**:
- Visibilidade idêntica à atual em `data`, `facets` e `summary`.
- `can_act` coerente com a autorização das ações.
- Nenhum conteúdo das amostras cegas na lista.
- Quebra de contrato aceita, mas registrada no changelog único do frontend.

**Scale/Scope**:
- 1 roteador alterado (`tasks.py`).
- Schemas novos em `schemas.py`: envelope genérico, `Pagination`, `SortApplied`, `ProcessRef`, `PhaseRef` e os filtros, contagens e resumo da lista de tarefas.
- 1 módulo pequeno em `core/listing.py` (cálculo da paginação).
- 1 função em `authorization.py` (conflito em SQL).
- 14 arquivos de teste existentes ajustados e testes novos para a lista.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` ainda é o template sem preencher. Os gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Pedido do usuário em 2026-09-27; Spec 029 ("forma de expor atividades será remodelada"); decisões em Clarifications |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ Nenhum marcador aberto; as suposições (conflito tira `can_act`, contagens com o filtro da própria dimensão) estão registradas e são revisáveis por `/speckit-clarify` |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ Visibilidade reaproveita `process_visibility_clause` e `activity_view_clause` sem alteração; `can_act` espelha `require_activity_access`; a lista não expõe conteúdo das amostras |
| Mudança cirúrgica, sem abstração preventiva | ✅ O envelope genérico e o helper de paginação são pedidos pela spec (FR-001 a FR-008) e já têm uso definido na Spec 033; nada além disso é generalizado |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final do `tasks.md` (seção de tarefas e convenção de listagem) |

**Re-check pós-design**: sem violações. Pontos de atenção:

- Quebra de contrato em `GET /tasks`. O frontend usa deploy direto da `develop` e a quebra temporária foi aceita. O changelog único das Specs 032–034 deve listar a mudança.
- O genérico `ListEnvelope` com `model_serializer(mode='wrap')` precisa aparecer corretamente no OpenAPI (um schema por especialização). Verificar na implementação.
- `can_act` não considera permissões RBAC específicas de cada ação (ex.: `triage.review`), só a concessão por atividade e o conflito (R1). Hoje os perfis com concessão de editar a triagem têm essa permissão.

## Project Structure

### Documentation (this feature)

```text
specs/032-listing-standard-tasks/
├── plan.md              # este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── http-api.md      # Phase 1
├── checklists/
│   └── requirements.md  # /speckit-specify
└── tasks.md             # /speckit-tasks (ainda não criado)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── authorization.py     # + current_conflict_clause(user_id)      (R2)
│   └── listing.py           # novo: build_pagination(page, per_page, total)  (R4)
├── routers/
│   └── tasks.py             # GET /tasks no envelope; filtros, ordem, can_act, facets, summary
└── schemas.py               # Pagination, SortApplied, ListEnvelope[...]; ProcessRef, PhaseRef;
                             # TaskSummary (process, phase, can_act); TaskFiltersApplied,
                             # TaskFacets, TaskListSummary

tests/
├── api/routers/
│   ├── test_tasks_listing.py          # novo: envelope, paginação, ordem, filtros, facets, summary
│   ├── test_tasks_actionable.py       # novo: can_act/actionable por perfil, Admin, conflito
│   ├── test_tasks_router.py           # ajuste de formato
│   ├── test_tasks_visibility.py       # ajuste de formato; visibilidade em facets/summary
│   ├── test_tasks_summary_fields.py   # ajuste: process/phase como referências
│   └── (outros 9 arquivos que leem /tasks)  # ajuste de formato
├── unit/core/test_listing.py          # novo: cálculo da paginação (limites)
└── integration/journeys/conftest.py   # process_tasks lê ['data']
```

**Structure Decision**: backend único. A lógica da lista fica no roteador `tasks.py`, como hoje, porque nenhum outro ponto a usa. Só a regra de conflito (usada também pela autorização) vai para `authorization.py`, e só o cálculo da paginação (usado pela Spec 033) vai para `core/listing.py`.

## Complexity Tracking

Sem violações a justificar.
