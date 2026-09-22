# Quickstart: Validar Desativação de Conta de Usuário

O contrato do endpoint está em [contracts/users-deactivation.openapi.yaml](./contracts/users-deactivation.openapi.yaml) e as regras de dados em [data-model.md](./data-model.md).

## Pré-requisitos

- Ambiente de testes configurado com PostgreSQL conforme o repositório.
- Dependências instaladas pelo Poetry.

## Executar a validação focada

```bash
poetry run pytest -q tests/api/routers/test_user_router.py
```

## Cenários esperados

1. Autentique uma conta com `users.manage` e envie `DELETE /users/{user_id}` para outra conta ativa com uma origem permitida. Espere 204 sem corpo. Consulte a conta no banco ignorando o filtro global e confirme `deleted_at` preenchido e `deleted_by` igual à autora.
2. Consulte `GET /users` e confirme que a conta não aparece. Consulte `GET /users?active=false` e confirme que ela aparece com `active: false`.
3. Use uma credencial criada antes da desativação em `/auth/me` e tente novo login com a conta desativada. Espere 401 nos dois casos.
4. Tente sem sessão, sem `users.manage` e com origem não permitida. Espere, respectivamente, 401, 403 e 403; a conta deve permanecer ativa.
5. Tente desativar a conta autora e a última conta que satisfaz a invariante administrativa. Espere 409 e nenhuma alteração na conta alvo.
6. Envie duas desativações simultâneas para contas administrativas diferentes. Espere um resultado 204 e um 409 e confirme que ao menos uma conta administrativa permanece ativa.
7. Tente UUID inexistente e conta já inativa. Espere 404 e nenhuma alteração adicional.

## Verificação complementar

```bash
poetry run ruff check src/pivma/routers/users.py tests/api/routers/test_user_router.py
```

O fluxo completo da suíte permanece disponível com `poetry run pytest -q` após a implementação.
