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
poetry run pytest tests/integration/database/test_per_laboratory_*.py tests/integration/database/test_laboratory_*.py
poetry run pytest tests/api/routers/test_laboratory_waivers.py tests/api/routers/test_laboratory_reopen.py
poetry run pytest tests/api/routers/test_tasks_laboratory.py tests/api/routers/test_laboratory_isolation.py
poetry run pytest tests/integration/migrations/test_per_laboratory_migration.py
poetry run pytest                     # suíte completa, sem regressão (SC-008)
poetry run ruff check . && poetry run ruff format --check .
```

## Cenário de aceite da issue (template de teste)

Nenhum template padrão declara atividade por laboratório nesta entrega. Os
testes usam o template de teste de `tests/factories/laboratory_run_factory.py`
(`LAB_RUN_TEMPLATE`), que estende o de `tests/factories/sample_factory.py` com
uma fase:

```text
sample_definition ─▶ receipt (per_laboratory) ─▶ upload (per_laboratory) ─▶ statistics (process) ─▶ lab_feedback (per_laboratory)
receipt ─┬─▶ material_return (per_laboratory, custody) ◀── upload
```

0. Antes de concluir `sample_definition`, `POST .../laboratory-waivers`
   como Grupo Gestor → **409** `sample_definition_not_frozen` (FR-017a).
1. Processo com Labs A, B e C designados; concluir `sample_definition`.
   → `receipt` com 3 execuções `IN_PROGRESS`; `upload` e `material_return`
   ativadas com 3 execuções `BLOCKED` cada, sem tarefa (SC-001, FR-004).
2. Concluir `receipt` do Lab A. → a execução do Lab A em `upload` passa a
   `IN_PROGRESS` com tarefa; B e C continuam `BLOCKED` (história 3).
3. Usuário do Lab A tenta concluir a execução do Lab B. → recusado; nada
   muda (SC-007). `GET /tasks` como Lab A → só tarefas do Lab A;
   `GET /tasks/{tarefa do Lab B}` → 404; a trilha não mostra eventos do
   Lab B (SC-009).
4. Concluir `receipt` e `upload` dos Labs A e B. → `statistics` continua
   `BLOCKED` (SC-003).
5. `POST .../phases/{fase}/laboratory-waivers` para o Lab C como Grupo
   Gestor. → `receipt` e `upload` do Lab C ficam `WAIVED`; `upload` conclui;
   `statistics` abre; `material_return` do Lab C passa a `IN_PROGRESS`
   (SC-004, SC-005).
6. `POST .../activities/upload/laboratories/{Lab B}/reopen`. → execução 1
   do Lab B `SUPERSEDED` com dados intactos, execução 2 `IN_PROGRESS`;
   `upload` volta a `IN_PROGRESS`; `statistics` volta a `BLOCKED`; a cadeia
   do Lab B em `material_return` é encerrada e trocada por uma execução
   `BLOCKED`; Labs A e C intactos (SC-002, SC-006).
7. `GET /tasks?activity_key=upload` como Grupo Gestor. → uma tarefa por
   laboratório na rodada vigente, com `laboratory` e `activity_run_status`
   (`COMPLETED`, `IN_PROGRESS`, `WAIVED`). A trilha do Grupo Gestor traz os
   eventos `LABORATORY_WAIVED`; a do Lab C (dispensado) não traz.
8. Excluir o processo (`DELETE /processes/{id}`). → execuções `WAIVED` e
   `SUPERSEDED` continuam como estavam; só as `IN_PROGRESS` e `BLOCKED` viram
   `CANCELLED` (SC-010). O arquivamento não mexe em execuções.

## Regressão dos templates padrão

`poetry run pytest tests/integration/bootstrap` → os cinco templates carregam
sem mudança; os processos existentes têm `execution_scope = 'process'`
após a migração.
