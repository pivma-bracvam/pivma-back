# Contract: `due_date` em endpoints de Tarefa

Nenhum endpoint novo. Dois endpoints já existentes mudam de comportamento
e/ou de forma de resposta:

## `GET /tasks` (lista) — `TaskSummary`

Sem mudança de schema. O campo já existe:

```jsonc
{
  "id": "uuid",
  "process_id": "uuid",
  "process_code": "string",
  "title": "string",
  "assigned_role": "string | null",
  "status": "string",
  "due_date": "datetime | null"   // já existia — passa a vir preenchido quando sla_hours está declarado
}
```

**Antes**: `due_date` sempre `null`.
**Depois**: `due_date` = `run_started_at + sla_hours` quando a atividade
declara `sla_hours`; continua `null` quando não declara.

## `GET /tasks/{id}` (detalhe) — `TaskDetail`

**Mudança de schema**: acrescenta o campo `due_date`.

```jsonc
{
  "id": "uuid",
  "process_id": "uuid",
  "activity_key": "string",
  "activity_run_number": "integer",
  "title": "string",
  "status": "string",
  "is_blocked": "boolean",
  "blocked_reason": "string | null",
  "due_date": "datetime | null"   // NOVO
}
```

Mesma regra de preenchimento do item anterior.

## Fora deste contrato (sem mudança)

- `GET /processes/{id}/roadmap` (ou endpoint equivalente da Spec 017) e o
  endpoint de kanban continuam expondo `sla_hours` + `run_started_at` (ou
  `run_started_at`/coluna já classificada), sem passar a incluir `due_date` —
  a consistência entre os dois é garantida pela mesma fórmula (ver
  `research.md`), não por um campo compartilhado.
- Nenhum endpoint de escrita muda de contrato — `due_date` é sempre derivado
  pelo motor de processos no momento da ativação da atividade, nunca
  recebido em um payload de request.
