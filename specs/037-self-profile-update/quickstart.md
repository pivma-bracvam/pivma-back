# Quickstart: Autogestão de Nome e Senha da Própria Conta

## Pré-requisitos

1. Instale as dependências com Poetry.
2. Inicie o PostgreSQL/pgvector com `docker compose up db -d`. Os testes usam Testcontainers e só precisam do Docker ativo.
3. Não há migração nova nesta feature.
4. Use uma conta comum, sem `users.manage`, autenticada por `POST /auth/login`.
5. Envie `Origin: https://testserver` nas mutações locais, como na configuração de testes.

## Cenários de validação

| Cenário | Resultado esperado |
|---|---|
| `{"full_name": "  Maria Silva  "}` | HTTP 200 com `full_name: "Maria Silva"`; `GET /auth/me` mostra o novo nome; `updated_by` = id da própria conta. |
| `{"current_password": <atual>, "new_password": <nova>}` | HTTP 200; login com a nova senha funciona e com a antiga retorna 401. |
| Os três campos juntos, com a senha atual correta | HTTP 200; nome e senha alterados. |
| Senha atual incorreta (com ou sem `full_name`) | HTTP 400 `invalid_current_password`; nome, hash e auditoria inalterados. |
| `new_password` sem `current_password` | HTTP 422; conta inalterada. |
| `current_password` sem `new_password` | HTTP 422; conta inalterada. |
| `new_password` curta, longa ou com espaço | HTTP 422 com "Senha inválida.", sem a regra; conta inalterada. |
| Corpo `{}`, valor `null` em qualquer campo, nome vazio ou só espaços | HTTP 422; conta inalterada. |
| `username`, `email`, `password_hash` ou outro campo extra | HTTP 422; conta inalterada. |
| Sem cookie de sessão | HTTP 401. |
| Origem ausente ou não confiável | HTTP 403; conta inalterada. |
| Conta desativada depois do login | HTTP 401. |
| Outra conta existente | Permanece inalterada após qualquer cenário acima. |

O contrato está em [contracts/auth-me.openapi.yaml](contracts/auth-me.openapi.yaml), e as combinações do corpo em [data-model.md](data-model.md).

## Testes automatizados

```bash
poetry run pytest tests/api/routers/test_auth_router.py tests/unit/schemas/test_user_schemas.py tests/unit/core/test_errors.py -q
poetry run pytest tests/api/routers/test_user_update.py tests/api/routers/test_error_contract.py -q
poetry run pytest
poetry run ruff check src tests
poetry run ruff format --check src tests
```

Só registre resultados depois de executar os comandos e conferir a saída.
