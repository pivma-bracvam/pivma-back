# Contrato HTTP: convite por e-mail

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Mudanças **compatíveis** nas rotas de convite da Spec 028. Nenhuma rota nova.

## `POST /processes/{process_id}/participants/invites`

Corpo: igual ao atual; `channel` passa a aceitar `"email"`.

```json
{ "email": "ana@exemplo.org", "role_key": "statistician", "channel": "email" }
```

`201`: `InviteCreatedResponse` como hoje, com `token`, mais o campo `delivery`.

```json
{
  "id": "…",
  "channel": "email",
  "status": "pending",
  "token": "…",
  "delivery": {
    "status": "pending",
    "attempts": 0,
    "last_attempt_at": null,
    "sent_at": null,
    "error_code": null
  }
}
```

Erros novos:

| Status | `code` | Quando |
|---|---|---|
| `409` | `channel_unavailable` | `channel = "email"` e o canal de e-mail ou `INVITE_URL_TEMPLATE` não estão configurados (FR-019) |

`channel = "link"` continua igual e devolve `delivery: null`.

## `POST /processes/{process_id}/participants/invites/{invite_id}/resend`

Sem corpo, como hoje. Para convite `email`: cancela o envio pendente e registra
um novo com o novo link. A resposta traz `delivery` do novo envio (`pending`).
Se o canal deixou de estar configurado desde a criação, responde
`409 channel_unavailable` e não altera o convite.

## `POST /processes/{process_id}/participants/invites/{invite_id}/revoke`

Sem mudança de contrato. Cancela o envio pendente; a resposta mostra
`delivery.status = "cancelled"`.

## `GET /processes/{process_id}/participants/invites`

Cada item ganha `delivery` (situação do envio mais recente do convite, ou
`null` para canal `link`).

## `POST /invites/{token}/accept`

Sem mudança de contrato. Cancela envio pendente do convite aceito.

## Esquema `InviteDeliveryPublic`

| Campo | Tipo |
|---|---|
| `status` | `"pending" \| "sent" \| "failed" \| "cancelled"` |
| `attempts` | inteiro |
| `last_attempt_at` | data-hora ou `null` |
| `sent_at` | data-hora ou `null` |
| `error_code` | texto ou `null` (valores em [data-model.md](../data-model.md)) |
