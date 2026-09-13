# Guia de Validação: Simplificação de Cargos Globais (RBAC)

## Pré-requisitos

```bash
docker compose up -d db
PYTHONPATH=src poetry run alembic upgrade head
PYTHONPATH=src poetry run fastapi dev src/pivma/__init__.py
```

## Verificação automatizada

```bash
poetry run pytest -q tests/unit/core/test_rbac_global_roles.py
poetry run pytest -q tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_security.py
poetry run pytest -q tests/integration/migrations/test_deprecate_legacy_global_profiles.py
poetry run ruff check src tests migrations
```

Os testes devem cobrir: efetivo de permissões de Admin/BraCVAM incluindo toda `Permission` (inclusive uma criada depois, no próprio teste, para provar que não depende de composição); `GET /rbac/profiles` listando somente Administrador e BraCVAM como ativos; rejeição ao tentar atribuir um perfil descontinuado; preservação de `rbac_changes` histórico; `can_manage_process_templates` continuando a aceitar Administrador e BraCVAM.

## Validação ponta a ponta

1. Aplique a migration (`alembic upgrade head`) num banco com a massa de seed padrão (`seed_users`, `seed_all`).
2. Autentique como `admin` e consulte o efetivo de permissões — confirme que inclui toda permissão cadastrada, inclusive `institutional.catalogs.manage`, `process.participants.manage` etc., mesmo que o `admin` nunca tenha sido explicitamente composto com elas.
3. Consulte `GET /rbac/profiles` — confirme que só Administrador e BraCVAM aparecem como perfis ativos/atribuíveis.
4. Tente `POST /rbac/users/{id}/profiles/{profile_id}` usando o id de um dos 8 perfis descontinuados (obtido via consulta direta ao banco ou pelo histórico) — confirme rejeição.
5. Confirme que um usuário sem nenhum perfil global continua operando normalmente nos fluxos que dependem só de papel local por processo (ex.: proponente de um processo via `Assignment`), sem qualquer regressão.

## Resultado esperado

Administrador e BraCVAM operam sem barreira de permissão em qualquer funcionalidade, presente ou futura. Apenas três cargos globais existem na prática: Padrão (ausência de perfil), Administrador, BraCVAM. Nenhum histórico de RBAC é perdido.
