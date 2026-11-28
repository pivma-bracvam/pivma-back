# Contrato: linha do tempo, formulário e tarefas da triagem

Nenhuma rota nova e nenhum campo novo. Os schemas de resposta (`TimelineListResponse`, `FormInstanceResponse`, `TaskDetail`) não mudam de forma; muda o conteúdo para cada leitor.

## `GET /processes/{id}/timeline`

Erros sem mudança: `404` para quem não vê o processo.

| Leitor | Eventos de convite | `FIELD_REVIEWED` | `user_id` em `TRIAGE_APPROVED`, `TRIAGE_REJECTED`, `REVISION_REQUESTED`, `RETURN_REVIEW_OPENED` | `user_id` do proponente e de avaliadores cegos |
|---|---|---|---|---|
| Admin, BraCVAM (com `triage.review`) | todos | sim | preenchido | preenchido |
| Quem gerencia participantes, sem `triage.review` | todos | não | nulo | preenchido |
| Proponente | só o próprio `INVITE_ACCEPTED` | não | nulo | preenchido |
| Laboratório participante | só o próprio `INVITE_ACCEPTED` | não | nulo | preenchido |
| Só `adhoc_evaluator` e/ou `peer_reviewer` | só o próprio `INVITE_ACCEPTED` | não | nulo | nulo, exceto o próprio |
| Cargo cego + outro cargo | pela união | pela união | pela união | preenchido |

`pagination.total_items` conta só os eventos devolvidos ao leitor.

Exemplo (proponente, triagem aprovada):

```json
{
  "id": "…",
  "event_type": "TRIAGE_APPROVED",
  "user_id": null,
  "activity_run_id": "…",
  "occurred_at": "2026-11-27T12:00:00Z",
  "context_data": {"justification": "Proposta completa."}
}
```

## `GET /processes/{id}/activities/{activity_key}/form`

| Leitor | `reviews` |
|---|---|
| Com `triage.review` | pareceres do formulário, inclusive em edição |
| Demais | só pareceres de triagem `COMPLETED`; `{}` enquanto a triagem não decide |

`previous_reviews` sem mudança.

## `GET /tasks`, `GET /tasks/{id}`

O proponente passa a receber a tarefa `triage_evaluation` do próprio processo, com `status`, `due_date` e `activity_run_number`. Ele não pode agir: as rotas `POST /processes/{id}/triage/reviews` e `POST /processes/{id}/triage/decision` continuam respondendo `403` sem `triage.review`.
