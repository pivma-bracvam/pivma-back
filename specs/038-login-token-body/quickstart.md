# Quickstart: Token de Acesso no Corpo da Resposta de Login

Guia de validação da Spec 038. Contrato em [contracts/auth-login.openapi.yaml](contracts/auth-login.openapi.yaml); regras de credencial em [data-model.md](data-model.md).

## Pré-requisitos

- Dependências instaladas (`poetry install`) e banco de testes disponível, como nas demais suítes.
- Para validação manual: API rodando localmente e uma conta ativa (por exemplo, criada pelo comando de administrador inicial do README).

## Validação automatizada

```bash
poetry run pytest tests/api/routers/test_auth_router.py -q
poetry run pytest -q
poetry run ruff check src tests
poetry run ruff format --check src tests
```

Esperado: todos os testes verdes, incluindo os novos de corpo do login, `Cache-Control`, Bearer, dispensa de origem e OpenAPI, e nenhum aviso do Ruff.

## Validação manual

Use a URL local da API em `API`, por exemplo `API=http://localhost:8000`.

1. **Token no corpo** (US1, US3):

   ```bash
   curl -si -X POST "$API/auth/login" -H 'Content-Type: application/json' \
     -d '{"identifier": "<usuario>", "password": "<senha>"}'
   ```

   Esperado: `200`, `Cache-Control: no-store`, `Set-Cookie: access_token=...; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=28800`, e corpo `{"access_token": "<mesmo valor do cookie>", "token_type": "bearer", "expires_in": 28800}`.

2. **Leitura com Bearer** (US2): `curl -s "$API/auth/me" -H "Authorization: Bearer <token>"` → `200` com a identidade da conta.

3. **Mutação com Bearer, sem Origin** (US4): `curl -s -X PATCH "$API/auth/me" -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' -d '{"full_name": "Nome Teste"}'` → `200`.

4. **Cookie continua protegido** (US4): repita o passo 3 trocando o Bearer por `-H "Cookie: access_token=<token>"` → `403 invalid_origin`.

5. **Credencial inválida** (edge case): login com senha errada → `401 invalid_credentials`, sem `Set-Cookie` e sem token no corpo.

6. **Swagger** (US5): abra `$API/docs`, confira o schema `LoginResponse` na resposta 200 do login, use "Authorize" → `HTTPBearer` com o token e execute `GET /auth/me` → `200`.

   Observação: se o login tiver sido feito pelo próprio `/docs`, o navegador guarda o cookie e passa a enviá-lo. Com cookie, as mutações voltam a exigir `Origin` confiável, e a origem da API normalmente não está em `AUTH_ALLOWED_ORIGINS`. Para testar mutações no `/docs` só com Bearer, obtenha o token por fora (passo 1) ou apague o cookie.
