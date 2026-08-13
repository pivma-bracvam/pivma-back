# Validação rápida: Autenticação de Usuários

## Pré-requisitos

1. Configure `DATABASE_URL`, uma chave JWT aleatória de pelo menos 32 bytes e uma origem confiável para o ambiente de validação.
2. Inicie o PostgreSQL e aplique as migrações, conforme o [README](../../README.md).
3. Use HTTPS ao testar o fluxo real no navegador, pois o cookie de autenticação usa `Secure`.

## Validação automatizada

Execute:

```bash
poetry run pytest tests/core/test_security.py tests/routers/test_auth.py tests/routers/test_user.py
poetry run ruff check
```

Os testes devem cobrir login por username e e-mail, falha pública uniforme, atributos do cookie, `GET /auth/me`, token adulterado ou vencido, conta excluída, logout, validação de origem e regressão do cadastro.

## Validação manual

1. Crie uma conta pelo contrato existente de `POST /users/`.
2. Faça `POST /auth/login` com username ou e-mail e senha. A resposta deve criar `access_token` somente por `Set-Cookie`.
3. Faça `GET /auth/me` enviando o cookie. A resposta deve conter somente `id`, `username` e `email` da mesma conta.
4. Faça `POST /auth/logout` com o cookie e uma origem configurada. A resposta deve retornar 204 e remover o cookie.
5. Repita `GET /auth/me`; a resposta deve retornar 401.

Consulte [contrato HTTP](contracts/auth.openapi.yaml) e [modelo de dados](data-model.md) para detalhes dos campos e resultados.
