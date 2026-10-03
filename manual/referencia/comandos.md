# Comandos

## Tarefas (`poe`)

Definidas em `[tool.poe.tasks]` do `pyproject.toml`. Rode com
`poetry run poe <tarefa>` ou `uv run poe <tarefa>`.

| Tarefa | Faz |
|---|---|
| `serve` | `fastapi dev src/pivma/__init__.py` (recarrega ao salvar) |
| `lint` | `ruff check` |
| `format` | `ruff check`, `ruff check --fix`, `ruff format` |
| `test` | `pytest -s -x -vv` e relatório de cobertura em `htmlcov/`. Argumentos extras vão para o pytest |
| `docs-serve` | Este site em `http://localhost:8008` |
| `docs-build` | Gera o site em `site/` (modo estrito) |

As tarefas `docs-*` exigem o grupo `docs`: `poetry install --with docs` ou
`uv sync --group docs`.

## Scripts

| Comando | Faz |
|---|---|
| `alembic upgrade head` | Aplica as migrações |
| `alembic revision --autogenerate -m "<descrição>"` | Gera uma migração a partir dos modelos |
| `python -m pivma.bootstrap_system` | Provisiona perfis, permissões, templates e o administrador inicial. Idempotente |
| `python -m pivma.bootstrap_process_templates` | Só os templates |
| `python -m pivma.bootstrap_rbac --user-id <UUID>` | Torna uma conta existente a administradora inicial |
| `python -m pivma.notifications.worker` | Worker de envio de notificações |

Prefixe com `poetry run` ou `uv run`.

## Dependências

| Ação | Comando |
|---|---|
| Instalar | `poetry install` ou `uv sync` |
| Mudar uma dependência | Edite `pyproject.toml` e rode `poetry lock && uv lock` |

Os dois lockfiles são versionados, e o CI falha se um deles estiver
desatualizado.
