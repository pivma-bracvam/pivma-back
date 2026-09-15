# Phase 1 Data Model: Prazo Real (due_date) das Atividades

Nenhuma entidade nova e nenhuma migração de schema. Esta spec muda apenas a
**semântica de preenchimento** de um campo já existente.

## `Task.due_date` (já existente, `models.py:757`)

| Aspecto | Antes desta spec | Depois desta spec |
|---|---|---|
| Coluna | `due_date: datetime \| None`, sempre `NULL` | mesma coluna, mesmo tipo |
| Quando é escrita | Nunca (dead field) | No momento da criação da `Task`, se a atividade correspondente declarar `sla_hours` |
| Fórmula | N/A | `run_started_at (ActivityRun) + timedelta(hours=sla_hours)` — mesma fórmula de `classify_kanban_column` |
| Quando fica `NULL` | Sempre | Atividade sem `sla_hours` declarado no template (continua "sem prazo", nunca um valor inferido — FR-002) |
| Atualização em retrabalho | N/A | Cada novo `ActivityRun` (novo ciclo de execução) tem sua própria `Task`, com seu próprio `due_date` calculado a partir do `run_started_at` desse ciclo — nenhum valor é herdado do ciclo anterior |
| Atividades já em andamento antes desta spec | `NULL` | Continuam `NULL` até serem concluídas e reabertas num novo ciclo — sem backfill (spec, Clarifications) |

### Insumos usados no cálculo (entidades existentes, sem alteração de schema)

- **`ActivityRun.started_at`** — já existente, é o `run_started_at` usado tanto
  por `classify_kanban_column` quanto pelo novo cálculo de `due_date`.
- **`sla_hours`** — já existente na definição declarativa da atividade
  (`process_template_versions.definition_payload`, campo opcional por
  atividade dentro de `phases[].activities[]`). Não é uma coluna própria de
  `ActivityInstance`; é lido do payload do template no momento da ativação,
  do mesmo jeito que já é lido hoje para alimentar `KanbanCardItem.sla_hours`.

### Regra de derivação (única fonte de verdade)

```
due_date = None                                   se sla_hours is None
due_date = run_started_at + timedelta(hours=sla_hours)   caso contrário
```

Esta é a mesma expressão já usada, hoje, dentro de `classify_kanban_column`
para decidir a coluna `EM_ATRASO` — reaproveitada, não duplicada com uma
regra divergente (garante FR-003).

## Sem novas relações

`Task` já se relaciona 1:N a partir de `ActivityRun` (`activity_run_id`); essa
relação não muda. Nenhuma nova tabela, índice ou chave estrangeira é
introduzida por esta spec.
