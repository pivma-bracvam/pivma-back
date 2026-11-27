# Contrato: Andamento do processo

Duas leituras no router `processes`, tag `Processes`. Exigem sessão
(`CurrentUser`). Não gravam evento. Schemas em [data-model.md](../data-model.md).

## `GET /processes` (mudança aditiva)

Mesma rota, filtros, envelope e ordem de antes. Muda o seguinte (FR-001,
FR-002):

**Query nova**: `role` (um valor de `ParticipantRole`). Só processos em que o
usuário tem esse cargo efetivo. Valor fora do catálogo responde `422`.

**Item**: `ProcessListItem`, que é `ProcessInstanceDetail` mais três campos:

```json
{
  "id": "0b9c…",
  "code": "VAL-2026-0067",
  "title": "[TESTE] Formulário Curto",
  "status": "OPEN",
  "template": {"…": "…"},
  "started_at": "2026-11-20T13:02:11Z",
  "closed_at": null,
  "closure_reason": null,
  "collection_template_id": null,
  "available_actions": [],
  "current_phase": {"key": "phase_2_role_assignment", "name": "Fase 2: Composição da Governança", "order": 2},
  "open_activity_count": 3,
  "my_roles": [
    {"role_key": "sponsor", "laboratory": null, "assigned_at": "2026-11-21T10:15:00Z"}
  ]
}
```

`filters_applied` passa a trazer `role`.

| Situação | Resposta |
|---|---|
| Sem designação no cargo pedido | `200` com `data: []` |
| Designação revogada, convite pendente, processo excluído | o processo não aparece no filtro |
| Processo arquivado | só com `status=ARCHIVED`, como antes |
| Processo fora de `OPEN` ou sem execução aberta | `current_phase: null`, `open_activity_count: 0` |

## `GET /processes/{id}/progress`

Andamento do processo com o recorte do usuário (FR-003 a FR-006, FR-012,
FR-013).

**200** `ProcessProgress`:

```json
{
  "process_id": "0b9c…",
  "my_roles": [{"role_key": "sponsor", "laboratory": null, "assigned_at": "2026-11-21T10:15:00Z"}],
  "current_phase": {"key": "phase_3_validation_execution", "name": "Fase 3", "order": 3},
  "phases": [
    {"key": "phase_1_submission", "name": "Fase 1", "order": 1, "status": "COMPLETED", "activities": [
      {"key": "proposal_submission", "name": "Submissão da proposta", "status": "COMPLETED", "conditional": false, "open_runs": []},
      {"key": "submission_return_review", "name": "Revisão do Retorno", "status": "BLOCKED", "conditional": true, "open_runs": []}
    ]},
    {"key": "phase_3_validation_execution", "name": "Fase 3", "order": 3, "status": "IN_PROGRESS", "activities": [
      {"key": "sample_receipt", "name": "Recebimento das amostras", "status": "IN_PROGRESS", "conditional": false, "open_runs": [
        {"started_at": "2026-11-24T09:00:00Z", "laboratory": {"id": "…", "name": "Lab A", "…": "…"}}
      ]}
    ]}
  ],
  "roles": [
    {"role_key": "group_manager", "occupied": true, "people": [{"user": {"id": "…", "username": "gestor", "full_name": "Ana"}, "laboratory": null}]},
    {"role_key": "proponent", "occupied": true, "people": [{"user": {"id": "…", "username": "pedro", "full_name": "Pedro"}, "laboratory": null}]},
    {"role_key": "study_manager", "occupied": false, "people": []}
  ]
}
```

A lista de atividades e a situação são iguais para todos os cargos;
`open_runs` e `people` seguem o recorte. `occupied` vale mesmo quando
`people` vem vazia pelo recorte.

| Situação | Resposta |
|---|---|
| Quem vê o processo em `GET /processes/{id}` | `200`, com o recorte de [R9](../research.md#r9-recorte-por-cargo) |
| Admin e BraCVAM | `200` em qualquer processo; `my_roles: []` sem cargo |
| Sem designação efetiva, designação revogada, processo inexistente ou excluído | `404` `not_found`, "Processo não encontrado." |
| `id` que não é UUID | `422` `validation_error` |
| Sem sessão | `401` |

## Removido

`GET /sponsor-tracking/processes` e `GET /sponsor-tracking/processes/{id}`,
da versão de 2026-11-23, que só o deploy de dev chegou a usar.
