# Quickstart: validar a Spec 036

Guia de verificação ponta a ponta. Contrato em
[contracts/http-api.md](contracts/http-api.md); entidades em
[data-model.md](data-model.md).

## Pré-requisitos

- Docker (os testes sobem PostgreSQL com pgvector via testcontainers).
- Dependências instaladas: `poetry install`.

## Testes automatizados

Os arquivos exatos saem do `tasks.md`. A suíte de aceite cobre:

```bash
poetry run pytest tests/unit/core/test_execution_scope_validation.py
poetry run pytest tests/integration/database/test_per_laboratory_engine.py
poetry run pytest tests/api/routers/test_laboratory_waivers.py tests/api/routers/test_laboratory_reopen.py
poetry run pytest tests/api/routers/test_tasks_laboratory.py
poetry run pytest tests/integration/migrations/test_per_laboratory_migration.py
poetry run pytest                     # suíte completa, sem regressão (SC-008)
poetry run ruff check . && poetry run ruff format --check .
```

## Cenário de aceite da issue (template de teste)

Nenhum template padrão declara atividade por laboratório nesta entrega. Os
testes usam o template de teste de `tests/factories/sample_factory.py`,
estendido com uma fase:

```text
sample_definition ─▶ receipt (per_laboratory) ─▶ upload (per_laboratory) ─▶ statistics (process)
                                              └─▶ return (per_laboratory, custody) ◀─ upload
```

1. Processo com Labs A, B e C designados; concluir `sample_definition`.
   → `receipt` com 3 execuções `IN_PROGRESS`, uma por laboratório (SC-001).
2. Concluir `receipt` do Lab A. → `upload` abre só para o Lab A; B e C
   continuam em `receipt` (história 3).
3. Usuário do Lab A tenta concluir a execução do Lab B. → recusado; nada
   muda (SC-007).
4. Concluir `receipt` e `upload` dos Labs A e B. → `statistics` continua
   `BLOCKED` (SC-003).
5. `POST .../phases/{fase}/laboratory-waivers` para o Lab C como Grupo
   Gestor. → `receipt` e `upload` do Lab C ficam `WAIVED`; `upload` conclui;
   `statistics` abre; `return` abre para o Lab C (SC-004, SC-005).
6. `POST .../activities/upload/laboratories/{Lab B}/reopen`. → execução 1
   do Lab B `SUPERSEDED` com dados intactos, execução 2 `IN_PROGRESS`;
   `upload` volta a `IN_PROGRESS`; `statistics` volta a `BLOCKED`; a cadeia
   do Lab B em `return` é cancelada; Labs A e C intactos (SC-002, SC-006).
7. `GET /tasks?activity_key=upload` como Grupo Gestor. → uma tarefa por
   laboratório na rodada vigente, com `laboratory` e `activity_run_status`
   (`COMPLETED`, `IN_PROGRESS`, `WAIVED`).

## Regressão dos templates padrão

`poetry run pytest tests/integration/bootstrap` → os cinco templates carregam
sem mudança; os processos existentes têm `execution_scope = 'process'`
após a migração.
