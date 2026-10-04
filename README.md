# pi\*VMA — API

Backend da pi\*VMA. Python 3.14, FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2,
Alembic, PostgreSQL 17 com pgvector, Argon2id.

| Onde | O quê |
|---|---|
| [`manual/`](manual/index.md) (site MkDocs) | O que o sistema faz hoje: tutorial, guias, referência da API e explicações |
| `http://localhost:8000/docs` | Swagger: corpos e respostas de cada rota |
| [`docs/`](docs/README.md) | Fontes de requisito: plano de trabalho e guia do protótipo |
| [`brand/`](brand/README.md) | Pacote de marca: cores, fontes, logotipos e guia de design |
| [`specs/`](specs/) | Histórico de cada mudança (Spec Kit) |
| [`AGENTS.md`](AGENTS.md) | Regras para agentes de código |

## Início rápido

Requer Python 3.14, Docker e Poetry ou uv.

```bash
cp .env.example .env
docker compose up db -d
```

| Passo | Poetry | uv |
|---|---|---|
| Instalar | `poetry install` | `uv sync` |
| Migrar | `poetry run alembic upgrade head` | `uv run alembic upgrade head` |
| Provisionar perfis, permissões e templates | `poetry run python -m pivma.bootstrap_system` | `uv run python -m pivma.bootstrap_system` |
| Subir a API | `poetry run poe serve` | `uv run poe serve` |

Variáveis obrigatórias: `DATABASE_URL`, `JWT_SECRET_KEY` (32 bytes ou mais) e
`AUTH_ALLOWED_ORIGINS`. Para criar o primeiro administrador no
provisionamento, defina `INITIAL_ADMIN_EMAIL` e `INITIAL_ADMIN_PASSWORD`.
Todas as variáveis: [Variáveis de ambiente](manual/referencia/ambiente.md).

Para levar um processo do cadastro à triagem: [tutorial](manual/tutorial/primeiro-processo.md).

## Documentação

```bash
poetry install --with docs
```

```bash
poetry run poe docs-serve
```

Com uv: `uv sync --group docs` e `uv run poe docs-serve`. O site abre em
`http://localhost:8008`; `poe docs-build` gera em `site/`. A lista de rotas é
gerada do OpenAPI no build.

## Tarefas

Definidas em `[tool.poe.tasks]`. Rode com `poetry run poe <tarefa>` ou
`uv run poe <tarefa>`. Com o plugin do Poe no Poetry, `poetry <tarefa>`
também funciona.

| Tarefa | Faz |
|---|---|
| `serve` | `fastapi dev src/pivma/__init__.py` |
| `lint` | `ruff check` |
| `format` | `ruff check`, `ruff check --fix`, `ruff format` |
| `test` | `pytest -s -x -vv` e relatório HTML de cobertura em `htmlcov/` |
| `docs-serve`, `docs-build` | Site da documentação |

Argumentos extras vão para o pytest: `poe test tests/integration/journeys`.
Demais scripts: [Comandos](manual/referencia/comandos.md).

## Dependências

- Fonte única: `pyproject.toml` (`[project]` e `[dependency-groups]`).
- Os dois lockfiles são versionados: `poetry.lock` e `uv.lock`.
- Ao mudar uma dependência, atualize os dois: `poetry lock && uv lock`.
- O CI falha se algum estiver desatualizado (`poetry check --lock`, `uv lock --check`).
- A imagem Docker instala a partir do `uv.lock`, sem o grupo `dev`.

## Docker

```bash
docker compose up --build -d
```

| Serviço | Função | Porta |
|---|---|---|
| `db` | PostgreSQL 17 + pgvector | `5432` |
| `api` | API; o `entrypoint.sh` roda `alembic upgrade head` e `bootstrap_system` antes do Uvicorn | `8000` |
| `worker` | Envio de notificações (`python -m pivma.notifications.worker`), mesma imagem | — |
| `mailpit` | SMTP falso de desenvolvimento; caixa em `http://localhost:8025` | `1025`, `8025` |

Produção: [Operar em produção](manual/guias/operar-em-producao.md).

## Testes

PostgreSQL com pgvector via Testcontainers (Docker precisa estar rodando). Schema criado uma vez por sessão; cada teste em transação com rollback. A metodologia está na skill [`testing-methodology`](.agents/skills/testing-methodology/SKILL.md): jornada do usuário primeiro, testes focados por risco depois.

| Diretório | Conteúdo |
|---|---|
| `tests/integration/journeys/etapa_<n>_*/` | Jornadas pela API pública, a partir de um deploy novo. Helpers em `journeys/conftest.py` |
| `tests/api/routers/` | Contrato HTTP: status, erros, autorização, formato |
| `tests/integration/database/` | Consultas e restrições no PostgreSQL |
| `tests/integration/migrations/` | Upgrade e downgrade do Alembic |
| `tests/integration/bootstrap/` | Provisionamento de perfis, permissões e administrador |
| `tests/integration/ai/` | Pré-avaliação com provedor fake |
| `tests/integration/notifications/` | Worker e envio de notificações |
| `tests/unit/` | Regras isoladas, schemas, segurança |
| `tests/factories/` | Factory Boy |

## Contribuição

- Antes do PR: `poe lint`, `poe format`, `poe test`.
- Mudou um modelo em `src/pivma/core/database/models.py`: gere a migração com `alembic revision --autogenerate -m "<descrição>"` e revise.
- Modelos novos herdam `AuditMixin`.
- Rotas de escrita usam `CurrentUser` e `TrustedOrigin`.
- Mudou uma dependência: `poetry lock && uv lock`.
- Mudou um comportamento: atualize o [`manual/`](manual/index.md) e rode `poe docs-build`.
