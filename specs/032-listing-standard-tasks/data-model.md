# Data Model: Padrão de listagens e lista de tarefas

**Feature**: [spec.md](spec.md) · **Research**: [research.md](research.md)

Sem tabela nova e sem migração. Todos os dados já existem: `Task`, `ActivityRun`, `ActivityInstance`, `Phase`, `ProcessInstance`, `Assignment`, `ConflictInterestDeclaration` e `EvaluationRun`. Este documento descreve os modelos de resposta e as regras de derivação.

## Modelos genéricos (reutilizados pela Spec 033)

### Pagination

| Campo | Tipo | Regra |
|---|---|---|
| `page` | int ≥ 1 | página pedida |
| `per_page` | int, 1–100 | tamanho pedido (padrão 20) |
| `total_items` | int ≥ 0 | itens do conjunto filtrado |
| `total_pages` | int ≥ 0 | `ceil(total_items / per_page)`; 0 sem itens |
| `has_next` | bool | `page < total_pages` |
| `has_prev` | bool | `page > 1 and total_pages > 0` |

### SortApplied

| Campo | Tipo |
|---|---|
| `by` | texto (campo de ordenação aplicado) |
| `order` | `asc` \| `desc` |

### ListEnvelope[Item, Filters, Facets, Summary]

| Campo | Tipo | Presença |
|---|---|---|
| `data` | lista de `Item` | sempre |
| `pagination` | `Pagination` | sempre |
| `filters_applied` | `Filters` | sempre, com os padrões preenchidos |
| `sort` | `SortApplied` | sempre |
| `facets` | `Facets` | só com `include=facets` |
| `summary` | `Summary` | só com `include=summary` |

## Referências

Todo campo com descrição na documentação da API. Uma referência não contém listas.

### ProcessRef

| Campo | Tipo | Origem |
|---|---|---|
| `id` | UUID | `ProcessInstance.id` |
| `code` | texto | `ProcessInstance.code` |
| `title` | texto | `ProcessInstance.title` |

### PhaseRef

| Campo | Tipo | Origem |
|---|---|---|
| `key` | texto | `Phase.key` |
| `order` | int | `Phase.order_index` |

## Lista de tarefas

### TaskSummary (item; muda)

| Campo | Tipo | Origem | Situação |
|---|---|---|---|
| `id` | UUID | `Task.id` | mantido |
| `process` | `ProcessRef` | processo da atividade | **novo**, substitui `process_id`, `process_code`, `process_title` |
| `activity_key` | texto | `ActivityInstance.key` | mantido |
| `activity_run_number` | int | `ActivityRun.run_number` | mantido |
| `phase` | `PhaseRef` | fase da atividade | **novo**, substitui `phase_key`, `phase_order` |
| `title` | texto | `Task.title` | mantido |
| `assigned_role` | texto \| null | `Task.assigned_role` | mantido |
| `status` | `READY` \| `COMPLETED` \| `CANCELLED` | `Task.status` | mantido; agora enum na documentação |
| `due_date` | datetime \| null | `Task.due_date` | mantido |
| `can_act` | bool | research R1 | **novo** |

### TaskFiltersApplied

| Campo | Tipo | Padrão |
|---|---|---|
| `status` | lista de status | `[]` (todos) |
| `activity_key` | lista de texto | `[]` (todas) |
| `phase_order` | int \| null | null |
| `process_id` | UUID \| null | null |
| `role` | texto \| null | null |
| `actionable` | bool | `false` |
| `current_run` | bool | **`true`** |
| `overdue` | bool | `false` |

### TaskFacets

| Campo | Tipo |
|---|---|
| `activity_key` | mapa `activity_key → quantidade` |
| `status` | mapa `status → quantidade` |

Os valores sem itens não aparecem no mapa. As contagens usam o conjunto com todos os filtros aplicados (research R5).

### TaskListSummary

| Campo | Tipo | Regra |
|---|---|---|
| `ai_pre_evaluation_in_progress` | int ≥ 0 | processos distintos visíveis com execução de pré-avaliação `in_progress` (research R6) |

## Regras de derivação

- **Visibilidade** (sem mudança): `process_visibility_clause` e `activity_view_clause`.
- **Rodada vigente**: research R3.
- **Pode agir**: research R1 e R2.
- **Atrasada**: `status = READY` e `due_date < agora (UTC naive)`. Tarefa sem prazo nunca está atrasada.
- **Ordem**: research R7.
