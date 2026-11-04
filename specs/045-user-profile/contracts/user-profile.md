# Contrato: Perfil do Usuário

As duas rotas exigem sessão (cookie `access_token` ou `Authorization: Bearer`).
Os erros seguem o formato único `{"detail": {"code", "message"}}`.

## Acesso (as duas rotas)

| Quem consulta | Conta consultada | Resposta |
|---|---|---|
| sem sessão, ou com sessão de conta desativada | qualquer | 401 |
| a própria pessoa | a própria | 200 |
| outra conta, sem `users.read` | existente ou não | 403 `forbidden`, sem dados da conta |
| outra conta, com `users.read` | ativa ou desativada | 200 |
| outra conta, com `users.read` | inexistente | 404 `not_found` |
| qualquer | `user_id` sem formato UUID | 422 `validation_error` |

## GET /users/{user_id}

`operationId`: `getUserProfile`

```json
{
  "id": "6c1f...",
  "full_name": "Ana Souza",
  "email": "ana@example.com",
  "active": true,
  "created_at": "2026-10-02T13:20:00Z",
  "global_profiles": [
    {"id": "0000...000a", "name": "BraCVAM", "assigned_at": "2026-10-03T09:00:00Z"}
  ]
}
```

- `username` e `password_hash` não aparecem.
- `global_profiles` traz só as atribuições vigentes, em ordem de `assigned_at`
  crescente e depois de `id`. Sem atribuições, vem `[]`.

## GET /users/{user_id}/process-roles

`operationId`: `listUserProcessRoles`

| Parâmetro | Valores | Padrão |
|---|---|---|
| `active` | `true` (não revogados), `false` (revogados) | `true` |
| `page` | ≥ 1 | 1 |
| `per_page` | 1 a 100 | 20 |

```json
{
  "data": [
    {
      "process": {"id": "9a2e...", "code": "VAL-2026-0007", "title": "Método X", "status": "OPEN"},
      "roles": [
        {
          "id": "51d0...",
          "role_key": "lead_laboratory",
          "laboratory": {
            "id": "3b7c...",
            "name": "Lab A",
            "active": true,
            "institution": {"id": "8e11...", "name": "Instituto B", "active": true}
          },
          "assigned_at": "2026-10-20T10:00:00Z",
          "revoked_at": null
        },
        {
          "id": "4f02...",
          "role_key": "proponent",
          "laboratory": null,
          "assigned_at": "2026-10-10T08:00:00Z",
          "revoked_at": null
        }
      ]
    }
  ],
  "pagination": {"page": 1, "per_page": 20, "total_items": 1, "total_pages": 1, "has_next": false, "has_prev": false},
  "filters_applied": {"active": true},
  "sort": {"by": "last_assigned_at", "order": "desc"}
}
```

- Cada item é um processo. `pagination` conta processos, não cargos.
- Os processos seguem a designação mais recente entre os cargos do item, da
  mais nova para a mais antiga, e depois o `id` do processo. Os cargos seguem
  `assigned_at` decrescente e depois `id`.
- Um processo com um cargo ativo e outro revogado aparece nas duas consultas,
  cada vez só com o cargo que atende ao filtro.
- Designações excluídas e processos excluídos não aparecem. Processos
  encerrados, cancelados e arquivados aparecem.
- Página além da última: `data` vazio, com os totais.

## Contratos que não mudam

`GET /auth/me`, `GET /users`, `POST /users`, `PATCH /users/{user_id}`,
`DELETE /users/{user_id}`, as rotas de `/rbac` e as de participantes.
