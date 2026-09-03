# Quickstart: Atualização Administrativa de Usuários

## Pré-requisitos

1. Instale as dependências com Poetry.
2. Inicie o PostgreSQL/pgvector com `docker compose up db -d`.
3. Aplique as migrações com `PYTHONPATH=src poetry run alembic upgrade head`.
4. Prepare uma sessão de uma conta com o perfil oficial Administrador ou com `users.manage`.
5. Use `Origin: https://testserver` nos requests de mutação locais, conforme a configuração de testes.

## Cenários de validação

| Cenário | Resultado esperado |
|---|---|
| Administrador atualiza conta legada com `{"full_name":"  Maria Silva  "}` | HTTP 200, resposta com `Maria Silva`, valor persistido e auditoria atualizada. |
| Administrador substitui um nome existente | HTTP 200 e novo valor aparado. |
| Conta sem sessão | HTTP 401. |
| Sessão sem `users.manage` | HTTP 403 e nome inalterado. |
| Origem não confiável | HTTP 403 e nome inalterado. |
| UUID desconhecido | HTTP 404. |
| Nome vazio, espaços, `null`, maior que 255 ou campo extra | HTTP 422 e nome inalterado. |
| Novo cadastro sem `full_name` | HTTP 422. |
| Conta antiga sem nome consultada pelos endpoints existentes | Continua válida e retorna `full_name: null`. |

## Testes automatizados

```bash
poetry run pytest tests/unit/schemas/test_user_schemas.py tests/api/routers/test_user_router.py tests/api/routers/test_user_update.py tests/integration/migrations/test_user_management_permission_migration.py -q
poetry run pytest
```

O contrato do PATCH está em [contracts/users.openapi.yaml](contracts/users.openapi.yaml). O modelo e a transição de estado estão em [data-model.md](data-model.md).
