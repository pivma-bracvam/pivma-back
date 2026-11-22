# Contrato: API de alerts

Todas as rotas exigem sessão (`CurrentUser`) e mostram só os alerts do usuário da sessão. As de escrita exigem origem confiável (`TrustedOrigin`). Os erros seguem `{"detail": {"code", "message"}}`.

## `GET /alerts`

Lista os alerts do usuário, do mais recente para o mais antigo.

| Parâmetro | Tipo | Padrão | Regra |
|---|---|---|---|
| `page` | inteiro ≥ 1 | 1 | |
| `per_page` | inteiro de 1 a 100 | 20 | |
| `unread` | booleano | ausente | `true`: só não lidos. `false`: só lidos. Ausente: todos |

Resposta `200`:

```json
{
  "data": [
    {
      "id": "6f1c…",
      "kind": "task_opened",
      "target": {
        "type": "task",
        "process_id": "a3b2…",
        "id": "9d0e…"
      },
      "params": {
        "process_code": "CR-2026-0012",
        "process_title": "Ensaio de irritação ocular in vitro",
        "activity_key": "triage_evaluation",
        "activity_name": "Triagem e Decisão BraCVAM",
        "run_number": 1,
        "due_date": "2026-11-24T14:00:00"
      },
      "read_at": null,
      "created_at": "2026-11-21T14:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_items": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  },
  "filters_applied": { "unread": null },
  "sort": { "by": "created_at", "order": "desc" },
  "unread_count": 1
}
```

- `target.id` vem nulo quando `target.type` é `process`.
- `unread_count` conta todos os não lidos do usuário, sem considerar `unread`, `page` nem `per_page`.
- Os parâmetros de cada tipo estão em [data-model.md](../data-model.md#parâmetros-por-tipo).

| Status | `code` | Quando |
|---|---|---|
| 401 | `not_authenticated` | Sem sessão |
| 422 | `validation_error` | `page`, `per_page` ou `unread` inválidos |

## `POST /alerts/{alert_id}/read`

Marca um alert como lido. Marcar de novo responde `200` e mantém o `read_at` original.

Resposta `200`: o alert, no formato de um item de `data`.

| Status | `code` | Quando |
|---|---|---|
| 401 | `not_authenticated` | Sem sessão |
| 403 | `invalid_origin` | Origem fora de `AUTH_ALLOWED_ORIGINS` |
| 404 | `not_found` | Alert inexistente ou de outro usuário |
| 422 | `validation_error` | `alert_id` não é UUID |

## `POST /alerts/read-all`

Marca como lidos todos os alerts não lidos do usuário.

Resposta `200`:

```json
{ "updated": 3 }
```

| Status | `code` | Quando |
|---|---|---|
| 401 | `not_authenticated` | Sem sessão |
| 403 | `invalid_origin` | Origem fora de `AUTH_ALLOWED_ORIGINS` |

## Rota do destino no front

O backend não devolve URL. O front monta a rota a partir de `target`:

| `target.type` | Identificadores | Tela |
|---|---|---|
| `process` | `process_id` | Processo |
| `task` | `process_id`, `id` | Tarefa do processo |
| `sample_receipt` | `process_id`, `id` | Frasco no recebimento de amostras |

A rota do destino confere a permissão como hoje. Se o usuário perdeu o acesso, a leitura responde `404` (por exemplo, `GET /tasks/{id}`), e o front mostra que o item não está mais disponível. Tentar agir sem permissão responde `403`.
