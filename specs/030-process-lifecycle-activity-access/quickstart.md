# Quickstart: validar ciclo de vida e acesso por atividade

**Feature**: [spec.md](spec.md) · **Contrato**: [contracts/http-api.md](contracts/http-api.md)

## Pré-requisitos

- Docker disponível (a suíte sobe `pgvector/pgvector:pg17` via testcontainers).
- `poetry install` executado.

## 1. Suíte da feature

```bash
# jornadas de ponta a ponta (bootstrap real, login por cookie, troca de usuário)
poetry run pytest tests/integration/journeys -q --no-cov

# matriz de acesso por atividade, triagem, revisão do retorno e tarefas
poetry run pytest tests/api/routers -q --no-cov -k "access or triage or return_review or tasks or process"

# migração (upgrade e downgrade)
poetry run pytest tests/integration/migrations -q --no-cov -k lifecycle

# carga dos templates (FR-013, FR-014)
poetry run pytest tests/unit/core -q --no-cov -k "template or access"
```

**Esperado**: tudo verde.

## 2. Suíte completa e lint

```bash
poetry run pytest -q
poetry run ruff check . && poetry run ruff format --check .
```

**Esperado**: suíte verde. Os testes de concorrência novos da pré-avaliação e da
revisão do retorno foram adiados (TODOs `TODO(spec-030)` no código).

## 3. Cenários de aceitação

| # | Cenário | Onde é provado | Resultado esperado |
|---|---|---|---|
| 1 | Processo 1: cadastro → criar → enviar → BraCVAM aprova | `tests/integration/journeys/test_pre_validated_method_triage.py` | `status == "OPEN"` em todos os passos; fase 1 `COMPLETED`; tarefas `COMPLETED` (SC-004) |
| 2 | Triagem rejeita | testes de triagem | `process_status == "CLOSED"`, sem revisão do retorno |
| 3 | Triagem pede revisão → proponente escolhe `REVISE` | jornada de retorno pela triagem | revisão do retorno aberta; após a escolha, submissão run 2 em rascunho com valores copiados |
| 4 | IA negativa → proponente escolhe `CONTEST_AI` | jornada de retorno pela IA (provedor fake) | triagem liberada para o BraCVAM |
| 5 | Qualquer retorno → `WITHDRAW` | testes de revisão do retorno | `CLOSED` com `closure_reason`; tarefas pendentes canceladas |
| 6 | Matriz da fase 1 (US2) | testes de acesso por atividade | proponente/BraCVAM/Admin/`sponsor`: ver, editar ou 404/403 conforme [data-model.md](data-model.md#matriz-da-fase-1-todos-os-templates) (SC-003) |
| 7 | Admin tenta decidir a triagem | testes de triagem | 403 |
| 8 | `sponsor` com atribuição abre o processo em submissão | testes de visibilidade | cabeçalho 200; formulário da submissão 404 |
| 9 | `GET /processes?status=TRIAGE` | testes de listagem | 422 |
| 10 | Duas escolhas concorrentes na mesma revisão do retorno | **adiado** (`TODO(spec-030)` em `return_review_service.py`) | — |
| 11 | Migração com processos nos 7 valores antigos | teste de migração | 4 de fluxo → `OPEN`; terminais preservados; triagem pendente continua decidível (SC-006) |
| 12 | Nenhuma resposta traz valores de fluxo | varredura nos testes de contrato | ausência de `SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE`, `PLANNING` como estado de processo (SC-001) |

## 4. Checagem manual no app (opcional)

```bash
poetry run alembic upgrade head
poetry run python -m pivma.bootstrap_system
poetry run poe serve
```

Em `/docs`: criar um processo com um usuário comum, enviar a submissão,
entrar como BraCVAM e decidir `NEEDS_REVISION`; voltar ao proponente e
consultar `GET /processes/{id}/return-review`.
