# Quickstart: validar a remoção do Kanban

## Pré-requisitos

- Branch `chore/029-remove-activities-kanban`.
- Docker disponível (os testes sobem PostgreSQL via Testcontainers).
- Dependências instaladas (`uv sync` ou `poetry install`).

## 1. Nenhuma referência residual (SC-001)

```bash
grep -rniE "kanban|resolve_activity_holders|ActivityCargo" src tests
```

Esperado: só aparecem ocorrências em
`tests/api/routers/test_activities_kanban_removed.py`.

## 2. Teste de regressão (FR-007, SC-003)

```bash
uv run pytest tests/api/routers/test_activities_kanban_removed.py -v
```

Esperado: os dois testes passam. `GET /activities/kanban` responde 404, e o
`/openapi.json` não tem o caminho, a tag `Activities` nem schemas `Kanban*`.

## 3. Suíte completa e lint (SC-002)

```bash
uv run ruff check
uv run pytest
```

Esperado: lint sem erros (sem imports órfãos) e suíte verde. Pelo
`git diff --stat`, nenhum arquivo de teste fora da lista do FR-005 foi
alterado.

## 4. Verificação manual opcional

Com a API rodando, `curl -i http://localhost:8000/activities/kanban` retorna
`404`, e a página `/docs` não mostra o grupo `Activities`.

Ver [contracts/removed-endpoints.md](contracts/removed-endpoints.md).
