# Implementation Plan: Remover o Kanban de Pendências (`GET /activities/kanban`)

**Branch**: `chore/029-remove-activities-kanban` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-remove-activities-kanban/spec.md`

## Summary

Remover o endpoint `GET /activities/kanban` e o código que só ele usa, sem
alterar o motor de processos nem o `/tasks`. A remoção vai de fora para
dentro: primeiro o registro do router, depois o router, os schemas, as
funções de domínio que ficaram órfãs e os testes exclusivos do Kanban. Um
teste de regressão novo garante que a rota e o contrato OpenAPI não voltam.
Não há mudança de banco.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy assíncrono, Pydantic

**Storage**: PostgreSQL (sem alteração nesta feature)

**Testing**: pytest + pytest-asyncio, PostgreSQL via Testcontainers (`uv run pytest`)

**Target Platform**: Serviço web Linux (container)

**Project Type**: web-service (backend de API)

**Performance Goals**: N/A (remoção)

**Constraints**: nenhuma mudança de comportamento fora do Kanban (FR-004);
nenhuma migration nova nem edição de migration existente.

**Scale/Scope**: 1 router, 4 schemas + 1 alias de tipo, 2 funções de domínio,
5 arquivos de teste removidos; 1 arquivo de teste novo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Nota**: `.specify/memory/constitution.md` contém só o template padrão (não
ratificado), e o `AGENTS.md` desta branch está vazio. O gate usa as regras do
`AGENTS.md` vigente na `develop` (`git show origin/develop:AGENTS.md`).

**Pré-design: APROVADO**

- **Precedência de fontes**: a remoção deixa o RF031 (Painel de
  monitoramento) do Plano de Trabalho sem implementação. O conflito está
  registrado na spec (Assumptions) e foi resolvido por instrução explícita do
  usuário, que tem precedência sobre o Plano.
- **Mudanças cirúrgicas (karpathy-guidelines)**: em conformidade. Só sai o
  que o Kanban usa sozinho. Os símbolos que ficam órfãos por causa desta
  remoção (research.md #2) também saem, e nada além deles.
- **Testes (fastapi-testing-methodology)**: em conformidade. Há um teste de
  regressão para o comportamento observável novo (404 e ausência no OpenAPI).
  A garantia de "nada mais muda" vem da suíte existente, que roda sem edição
  (SC-002).
- **README**: não cita o Kanban nem lista endpoints de atividades; nenhuma
  atualização necessária.

**Pós-design: APROVADO**

- `data-model.md` confirma que nenhuma entidade, tabela ou coluna muda.
- `contracts/removed-endpoints.md` documenta o único contrato removido; os
  demais contratos ficam iguais.
- Nenhum item em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/029-remove-activities-kanban/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── removed-endpoints.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py                  # remove import e include_router de activities
├── schemas.py                   # remove bloco "KANBAN DE PENDÊNCIAS", ActivityCargo
│                                #   e GLOBAL_ACTIVITY_CARGOS (camada de API)
├── routers/
│   └── activities.py            # REMOVIDO
└── core/
    ├── process_engine.py        # remove KANBAN_* e classify_kanban_column;
    │                            #   ajusta docstrings de _compute_activity_due_date
    │                            #   e _resolve_activity_cargo
    └── authorization.py         # remove resolve_activity_holders e
                                 #   _GLOBAL_CARGO_SYSTEM_KEYS; ajusta comentário
                                 #   que cita ActivityCargo

tests/
├── api/routers/
│   ├── test_activities_kanban.py          # REMOVIDO
│   ├── test_kanban_blocking_context.py    # REMOVIDO
│   ├── test_kanban_role_scoping.py        # REMOVIDO
│   └── test_activities_kanban_removed.py  # NOVO (regressão FR-007)
└── unit/core/
    ├── test_kanban_column_classification.py  # REMOVIDO
    └── test_resolve_activity_holders.py      # REMOVIDO
```

**Structure Decision**: projeto único existente (`src/pivma`, `tests/`). Nenhum
diretório novo além da pasta da spec.

## Complexity Tracking

Nenhuma violação.
