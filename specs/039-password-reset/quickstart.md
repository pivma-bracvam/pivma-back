# Quickstart: Recuperação de Senha por Token Temporário

Roteiro para conferir a feature de ponta a ponta. Contrato em [contracts/password-reset.openapi.yaml](contracts/password-reset.openapi.yaml); campos e estados em [data-model.md](data-model.md).

## Testes automatizados

```bash
uv run alembic upgrade head
uv run pytest tests/api/routers/test_password_reset.py -v
uv run pytest tests/unit/notifications/test_password_reset_email_renderer.py tests/unit/core/test_settings.py -v
uv run pytest tests/integration/migrations/test_password_reset_migration.py -v
uv run pytest            # suíte completa (SC-007)
uv run ruff check src tests && uv run ruff format --check src tests
```

Resultado esperado: tudo verde, sem alterar asserções de testes existentes.

## Validação manual com o compose

Pré-requisitos no `.env`:

```text
NOTIFICATION_EMAIL_BACKEND="smtp"
SMTP_HOST="mailpit"
SMTP_PORT=1025
SMTP_SECURITY="none"
NOTIFICATION_FROM_ADDRESS="nao-responda@pivma.local"
NOTIFICATION_ENCRYPTION_KEY="<chave Fernet>"
PASSWORD_RESET_URL_TEMPLATE="http://localhost:3000/redefinir-senha/{token}"
```

Suba `api`, `worker` e `mailpit` com `docker compose up`.

| # | Passo | Resultado esperado |
|---|---|---|
| 1 | `POST /auth/forgot-password` com o e-mail de uma conta ativa | 200 com a mensagem neutra; em `http://localhost:8025` chega um e-mail com o link e o prazo |
| 2 | Repetir o passo 1 com um e-mail sem conta | 200 com o mesmo corpo; nenhum e-mail novo |
| 3 | `POST /auth/reset-password` com o token do link e uma senha válida | 204 |
| 4 | `POST /auth/login` com a senha nova e depois com a antiga | 200 e 401 |
| 5 | Repetir o passo 3 com o mesmo token | 400 `invalid_reset_token` |
| 6 | Pedir duas vezes e usar o token do primeiro e-mail | 400 `invalid_reset_token`; o do segundo funciona |
| 7 | Conferir `docker compose logs api worker` | Nenhuma linha contém o token ou o link |
| 8 | Remover `PASSWORD_RESET_URL_TEMPLATE`, reiniciar e repetir o passo 1 | 200 com a mensagem neutra; log `password_reset_unavailable`; nenhum token emitido |
