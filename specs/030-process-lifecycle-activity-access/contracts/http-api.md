# Contrato HTTP: Ciclo de vida do processo e acesso por atividade

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudança **incompatível** com o frontend atual. Legenda: 🔴 remove ou troca
contrato, 🟡 muda regra de acesso sem mudar formato, 🟢 novo.

## Tipo compartilhado

```text
ProcessLifecycle = "OPEN" | "CLOSED" | "CANCELLED" | "ARCHIVED"
```

## Processos

| Endpoint | Mudança |
|---|---|
| 🔴 `POST /processes` | `status` passa a ser `ProcessLifecycle` (sempre `OPEN` na criação) |
| 🔴 `GET /processes` | itens com `status: ProcessLifecycle`; `?status=` aceita só `ProcessLifecycle` e responde **422** para `SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE`, `PLANNING`. Visibilidade: Admin/BraCVAM veem todos; demais, processos com atribuição ativa. Arquivados seguem ocultos por padrão e só para quem tem acesso de revisão |
| 🔴 `GET /processes/{id}` | `status: ProcessLifecycle`; 404 para quem não é Admin/BraCVAM nem tem atribuição ativa |
| 🔴 `DELETE /processes/{id}`, `PATCH /processes/{id}/archive` | `status`/`previous_status` em `ProcessLifecycle`; regras de transição de FR-003 |
| 🟡 `PUT`/`PATCH /processes/{id}` (edição da submissão) | exige editar em `proposal_submission` (403 se só vê) e execução aberta com formulário não enviado (409); deixa de depender de `status == SUBMISSION` |
| 🟡 `GET /processes/{id}/submission-versions[/{n}]` | exige ver em `proposal_submission` (404) |
| 🟡 `GET /processes/{id}/timeline` | eventos ligados a uma execução só aparecem para quem vê a atividade dela |

## Formulários de atividade

`/processes/{id}/activities/{activity_key}/form` e anexos
(`.../form/fields/{field_key}/attachment`).

| Operação | Regra |
|---|---|
| 🟡 `GET` form, `GET` anexo | ver na atividade; senão **404** |
| 🟡 `PUT` rascunho, `POST` envio, `POST`/`DELETE` anexo | editar na atividade; sem ver **404**, vê sem editar **403**; execução fechada, formulário enviado ou processo fora de `OPEN` **409** |

## Triagem

| Endpoint | Mudança |
|---|---|
| 🟡 `POST /processes/{id}/triage/reviews` | `triage.review` **e** editar em `triage_evaluation` (só `bracvam`). Admin recebe **403** |
| 🔴 `POST /processes/{id}/triage/decision` | mesma regra de acesso; 409 se `triage_evaluation` não tem execução `IN_PROGRESS`. Resposta abaixo |

```json
// 200 — TriageDecisionResponse
{
  "process_id": "uuid",
  "process_status": "OPEN | CLOSED",
  "decision_id": "uuid",
  "outcome": "APPROVED | REJECTED | NEEDS_REVISION",
  "return_review_run": 1          // número da execução aberta em NEEDS_REVISION; null nos demais
}
```

`new_process_status` e `next_activity_run` deixam de existir.

## Pré-avaliação por IA

| Endpoint | Mudança |
|---|---|
| 🟡 `GET /processes/{id}/pre-evaluation` | ver em `proposal_submission` (proponente, Admin, BraCVAM); **404** para os demais, no lugar do 403 atual |
| 🟡 `POST /processes/{id}/pre-evaluation/{run_id}/feedback` | sem mudança (`triage.review`) |
| 🔴 `POST /processes/{id}/submission/direct-review` | **removido**. Substituído pela escolha `CONTEST_AI` da revisão do retorno |
| 🟡 `POST /admin/pre-evaluations/{run_id}/retry` | também cancela a revisão do retorno aberta (R9) |

## Revisão do retorno 🟢

### `GET /processes/{id}/return-review`

Ver em `submission_return_review`; senão **404**. **404** também quando não há
execução aberta.

```json
// 200
{
  "run_number": 1,
  "source": "AI_PRE_EVALUATION | TRIAGE",
  "opened_at": "datetime",
  "due_date": "datetime | null",
  "available_choices": ["REVISE", "CONTEST_AI", "WITHDRAW"],   // CONTEST_AI só com source = AI_PRE_EVALUATION
  "ai_pre_evaluation": { /* PreEvaluationResponse atual */ },   // só com source = AI_PRE_EVALUATION
  "triage_decision": {                                          // só com source = TRIAGE
    "outcome": "NEEDS_REVISION",
    "justification": "string",
    "decided_at": "datetime"
  }
}
```

### `POST /processes/{id}/return-review`

Exige `Origin` confiável e editar em `submission_return_review`.

```json
// request
{ "choice": "REVISE | CONTEST_AI | WITHDRAW", "justification": "string | null" }

// 200
{
  "choice": "REVISE",
  "process_status": "OPEN | CLOSED",
  "submission_run": 2              // em REVISE: número da nova execução da submissão; null nos demais
}
```

| Situação | Status |
|---|---|
| sem ver | 404 |
| vê sem editar (Admin, BraCVAM) | 403 |
| sem execução aberta ou escolha já registrada | 409 `invalid_transition` |
| `CONTEST_AI` com `source = TRIAGE` | 422 |
| processo fora de `OPEN` | 409 |

## Tarefas

| Endpoint | Mudança |
|---|---|
| 🟡 `GET /tasks` | só tarefas de atividades que o usuário vê; filtros `status`, `role`, `process_id` mantidos |
| 🟡 `GET /tasks/{id}` | **404** sem ver na atividade |

## Sem mudança

`/auth/*`, `/users/*`, `/rbac/*`, `/institutional/*`, participantes e convites
(exceto a leitura de `status` em ciclo de vida), `/ai-evaluations/*`,
`/form-templates/*`, `/admin/logs`.
