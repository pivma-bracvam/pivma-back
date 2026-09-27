# Contrato HTTP: Padrão de listagens e `GET /tasks`

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudança **incompatível** em `GET /tasks`: o formato da resposta, os campos do processo e da etapa e o padrão de rodada. `GET /tasks/{id}` não muda. Legenda: 🟢 novo, 🔴 quebra, 🟡 muda comportamento.

## Padrão de listagem (vale para as Specs 033 em diante)

```json
{
  "data": [ ... ],
  "pagination": {
    "page": 1, "per_page": 20, "total_items": 45,
    "total_pages": 3, "has_next": true, "has_prev": false
  },
  "filters_applied": { ... },
  "sort": { "by": "due_date", "order": "asc" },
  "facets": { ... },
  "summary": { ... }
}
```

- `facets` e `summary` só aparecem quando pedidos em `include`.
- Página além da última: `200` com `data: []` e os totais corretos.
- Sem bloco `meta`.

## `GET /tasks` 🔴

### Parâmetros

| Parâmetro | Tipo | Padrão | Situação |
|---|---|---|---|
| `page` | int ≥ 1 | 1 | 🟢 |
| `per_page` | int 1–100 | 20 | 🟢 |
| `status` | repetível: `READY`, `COMPLETED`, `CANCELLED` | todos | 🟡 aceita vários; valor desconhecido → `422` (antes, lista vazia) |
| `activity_key` | repetível, texto | todas | 🟢 |
| `phase_order` | int ≥ 1 | — | 🟢 |
| `process_id` | UUID | — | mantido |
| `role` | texto (cargo da tarefa) | — | mantido |
| `actionable` | bool | `false` | 🟢 só tarefas em que o usuário pode agir |
| `current_run` | bool | **`true`** | 🟢🟡 só a rodada vigente de cada atividade; `false` inclui o histórico |
| `overdue` | bool | `false` | 🟢 abertas com prazo vencido |
| `sort_by` | `due_date`, `created_at` | `due_date` | 🟢 |
| `sort_order` | `asc`, `desc` | `asc` | 🟢 tarefas sem prazo sempre por último |
| `include` | repetível: `facets`, `summary` | — | 🟢 |

### Resposta `200`

```json
{
  "data": [
    {
      "id": "0b6d…",
      "process": { "id": "9f1c…", "code": "PIVMA-2026-0001", "title": "Método X" },
      "activity_key": "triage_evaluation",
      "activity_run_number": 2,
      "phase": { "key": "phase_1_submission_triage", "order": 1 },
      "title": "Realizar Triagem da Proposta",
      "assigned_role": "bracvam",
      "status": "READY",
      "due_date": "2026-10-02T12:00:00",
      "can_act": true
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total_items": 6, "total_pages": 1, "has_next": false, "has_prev": false },
  "filters_applied": {
    "status": ["READY"], "activity_key": [], "phase_order": 1,
    "process_id": null, "role": null,
    "actionable": false, "current_run": true, "overdue": false
  },
  "sort": { "by": "due_date", "order": "asc" },
  "facets": {
    "activity_key": { "proposal_submission": 2, "triage_evaluation": 3, "submission_return_review": 1 },
    "status": { "READY": 6 }
  },
  "summary": { "ai_pre_evaluation_in_progress": 4 }
}
```

### Campos removidos do item 🔴

| Antes | Agora |
|---|---|
| `process_id`, `process_code`, `process_title` | `process.id`, `process.code`, `process.title` |
| `phase_key`, `phase_order` | `phase.key`, `phase.order` |

### Erros

| Situação | Resposta |
|---|---|
| Sem login | `401` |
| `page < 1`, `per_page` fora de 1–100, `status`/`sort_by`/`sort_order`/`include` desconhecido | `422` (formato atual; a Spec 034 padroniza) |

### Regras

- **Visibilidade** igual à atual: processos visíveis e atividades com concessão de ver. Vale para `data`, `facets` e `summary`.
- **`can_act`**: o usuário tem cargo com concessão de editar a atividade (atribuição ativa no processo, ou `admin`/`bracvam` pelo perfil) e não tem conflito de interesse vigente no processo.
- **`facets`**: calculadas sobre todo o conjunto filtrado, sem paginação.
- **`summary.ai_pre_evaluation_in_progress`**: processos visíveis com pré-avaliação por IA em andamento. Respeita `process_id` e ignora os demais filtros de tarefa.
