# Validação rápida: Autorização de Usuários e RBAC

## Pré-requisitos

1. Configure as variáveis existentes de banco, JWT e origens confiáveis.
2. Inicie PostgreSQL/pgvector e aplique `poetry run alembic upgrade head`.
3. Use HTTPS no fluxo real do navegador, pois a autenticação usa cookie `Secure`.

## Validação automatizada

Execute os grupos focados:

```bash
poetry run pytest tests/unit/core/test_authorization.py -q
poetry run pytest tests/integration/database/test_rbac_constraints.py tests/integration/migrations/test_rbac_migration.py tests/integration/test_rbac_bootstrap.py -q
poetry run pytest tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_security.py tests/api/routers/test_rbac_concurrency.py -q
```

Depois execute regressão e lint:

```bash
poetry run pytest
poetry run ruff check
```

Confirme a saída direta de `poetry run pytest`. O task `poetry test` usa `ignore_fail = true` e não comprova sucesso sozinho.

## Evidência mínima por risco

| Risco | Evidência esperada |
|---|---|
| Autorização | 401 sem identidade; 403 uniforme sem permissão; consulta do alvo somente depois da permissão. |
| Revogação | O mesmo cookie reflete concessão, retirada e inativação no pedido seguinte. |
| Separação | `rbac.read`, `rbac.profiles.manage` e `rbac.assignments.manage` não concedem umas às outras. |
| Concorrência | Nomes e atribuições não duplicam; duas retiradas não eliminam o último administrador. |
| Rastreabilidade | Estado e mudança persistente confirmam juntos; recusas 403 após a verificação de permissão aparecem no log e não em `rbac_changes`. |
| Migração | Upgrade semeia 9 perfis, 3 permissões e 3 composições; downgrade preserva `users`. |

## Validação manual

1. Crie uma conta pelo contrato existente `POST /users/` e copie seu `id`.
2. Execute o [bootstrap](contracts/bootstrap.md) com esse UUID.
3. Autentique a conta em `POST /auth/login` e mantenha o cookie recebido.
4. Crie uma segunda conta ativa e registre seu `id` para receber o perfil.
5. Consulte `GET /rbac/permissions` e `GET /rbac/profiles`; confirme os três códigos e os nove nomes oficiais.
6. Inicie o cronômetro. Com o cookie e um `Origin` confiável, crie um perfil adicional, altere sua composição e conceda o perfil à conta preparada por `POST /rbac/users/{user_id}/profiles/{profile_id}`.
7. Consulte `GET /rbac/users/{user_id}/access`; confirme perfis ativos e união das permissões.
8. Retire o perfil, confirme a mudança no pedido seguinte e consulte `GET /rbac/changes`.

As respostas e os erros esperados estão no [contrato HTTP](contracts/rbac.openapi.yaml). O [modelo de dados](data-model.md) define constraints, histórico e transações.

Pare o cronômetro após a atribuição da etapa 6. O intervalo mede apenas a criação do perfil, a definição de permissões e a atribuição à conta preparada, em até 2 minutos. Registre o tempo e o resultado junto à execução de T037.

## Registro de validação

Em 2026-08-19, a equipe aceitou formalmente o SC-004 com base no teste HTTP
reproduzível `tests/api/routers/test_rbac_timed_acceptance.py`, executado com
conta-alvo preparada e cookie autenticado. A criação do perfil, a definição de
`rbac.read` e a atribuição levaram **0,048533 segundo** (aproximadamente 0,05
segundo), abaixo do limite de 2 minutos.
