# Validação rápida: Listagem Administrativa de Usuários

## Pré-requisitos

1. Configure `DATABASE_URL`, `JWT_SECRET_KEY` e `AUTH_ALLOWED_ORIGINS` conforme o README.
2. Inicie PostgreSQL/pgvector.
3. Depois da implementação, aplique `poetry run alembic upgrade head`.
4. Prepare uma conta ativa com perfil que conceda `users.read`; a migração acrescenta essa permissão ao perfil oficial Administrador.

## Validação automatizada

Execute primeiro os testes focados:

```bash
poetry run pytest tests/integration/migrations/test_admin_user_listing_migration.py tests/unit/core/test_authorization.py -q
poetry run pytest tests/api/routers/test_user_listing.py tests/api/routers/test_user_listing_security.py -q
```

Execute a regressão dos contratos preservados:

```bash
poetry run pytest tests/api/routers/test_user_router.py tests/api/routers/test_auth_router.py tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_security.py tests/integration/test_rbac_bootstrap.py -q
```

Finalize com as verificações do repositório:

```bash
poetry run pytest
poetry run ruff check
poetry run alembic check
```

Confira a saída direta de `poetry run pytest`. O task `poetry test` ignora o código de falha do Pytest e não comprova sucesso sozinho.

## Evidência mínima por risco

| Risco | Evidência esperada |
|---|---|
| Autenticação e autorização | 401 sem sessão; 403 sem `users.read`; permissões RBAC não concedem a leitura; `users.read` permite a consulta. |
| Não vazamento | Topo restrito a `offset`, `limit`, `items`; cada item restrito a `id`, `full_name`, `username`, `email`, `active`, `profiles`; cada perfil restrito a `id`, `name`, `active`; respostas 401/403 sem coleção. |
| Busca | Username e e-mail por substring; caixa equivalente; espaços externos removidos; busca vazia omitida; `%` e `_` literais. |
| Estado | Padrão e `active=true` retornam contas ativas; `active=false` retorna inativas. |
| Perfil | Somente perfil e atribuição ativos; UUID desconhecido retorna página vazia; nenhuma conta duplicada. |
| Paginação | Defaults 0/100, máximo 100, ordem `lower(username), id`, filtros antes da página e offset além do fim com lista vazia. |
| Migração | `users.read` semeada no Administrador, efeito em atribuição existente, nenhuma mudança em `ADMINISTRATIVE_PERMISSIONS` e downgrade restrito à nova permissão. |
| Auditoria | Leitura bem-sucedida não cria `RbacChange`; 403 produz o log operacional existente. |
| Nome completo | `POST /users` exige `full_name`, remove espaços externos e devolve o valor em `POST /users`, `GET /auth/me` e `GET /users`; contas antigas podem devolver `null` até o PATCH administrativo. |

## Validação manual do contrato

Com uma sessão autorizada, execute as consultas abaixo e compare as respostas com [o contrato OpenAPI](contracts/users.openapi.yaml):

```http
GET /users?offset=0&limit=20
GET /users?search=Joao&offset=0&limit=20
GET /users?active=false&offset=0&limit=20
GET /users?profile_id=<UUID>&offset=0&limit=20
GET /users?search=joao&active=true&profile_id=<UUID>&offset=0&limit=20
```

Confirme estes resultados:

1. `joao`, `Joao` e `JOAO` devolvem os mesmos UUIDs na mesma ordem.
2. Uma busca por parte do username e outra por parte do e-mail localizam a conta esperada.
3. `%` e `_` não ampliam o conjunto como curingas.
4. A concatenação das páginas de um conjunto sem mudanças mantém a ordem e não repete UUIDs.
5. O UUID retornado funciona em uma operação RBAC existente que aceite `user_id`.
6. `full_name` aparece com o valor persistido ou `null`; nenhuma resposta contém `password_hash`, token, sessão, permissões ou auditoria; os perfis aparecem somente com `id`, `name` e `active`.

O [modelo de dados](data-model.md) registra os predicados de estado e perfil. `research.md` registra a escolha de `EXISTS`, escape literal e os limites de `FilterPage`.

## Evidência da validação manual

Em 31/08/2026, a validação foi executada contra um PostgreSQL/pgvector
isolado com a migration aplicada e a aplicação iniciada localmente. A sessão
do Administrador localizou `helena.souza` por `search=helena` e por
`search=HELENA`, sempre retornando o UUID
`e164b83d-414d-4a42-9363-3e37b967bb96`. A consulta por e-mail também localizou
a conta; `%` foi tratado literalmente e as páginas `limit=2` em `offset=0` e
`offset=2` não repetiram UUIDs. A resposta `active=false` foi vazia porque a
base manual não continha contas inativas.

O UUID copiado foi aceito por `GET /rbac/users/{user_id}/access`, que retornou
HTTP 200 e o mesmo `user_id`. O tempo medido pelo `curl` foi de `0.006521 s`
para a localização e `0.019519 s` para a confirmação no RBAC (`0.026040 s`
de tempo de rede somado; todas as consultas manuais retornaram em no máximo
`0.034767 s`).
