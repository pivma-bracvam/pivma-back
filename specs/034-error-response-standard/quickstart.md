# Quickstart: Formato único das respostas de erro

Contrato em [contracts/http-api.md](contracts/http-api.md); códigos em [data-model.md](data-model.md).

## Testes automatizados

```bash
poetry run pytest tests/unit/core/test_errors.py          # tradução e montagem dos campos
poetry run pytest tests/api/test_error_contract.py         # formato por status (400–503)
poetry run pytest                                          # suíte completa, sem regressão
poetry run ruff check . && poetry run ruff format --check .
```

Os nomes finais saem do `tasks.md`.

## Verificação manual

1. `GET /tasks` sem cookie → `401`, `detail.code == "not_authenticated"`.
2. `GET /rota-inexistente` → `404`, `detail.code == "not_found"`.
3. `POST /users` com e-mail inválido e sem `full_name` → `422`, dois itens em `detail.fields`, mensagens em português, sem o e-mail enviado.
4. `POST /users` com senha curta → `422`, item `password` com `code: invalid` e sem a regra.
5. `GET /tasks?per_page=101` → `422`, item `location: query`, `field: per_page`.
6. Swagger (`/docs`): o `422` de qualquer rota aponta para `ErrorResponse`.
