# Implementation Plan: Andamento do processo por cargo

**Branch**: `feat/047-sponsor-tracking` | **Date**: 2026-11-23, redesenho em 2026-11-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/048-process-progress/spec.md`

## Summary

`GET /processes` ganha o filtro `role` e, em cada item, a fase atual, a
quantidade de execuções em andamento que o usuário vê e as designações dele
no processo. `GET /processes/{id}/progress` é nova e devolve as fases com a
situação, a fase atual, as pessoas por cargo e as execuções em andamento,
filtradas pelo recorte do cargo. Quem não vê o processo recebe `404`.

`pivma.core.process_progress` guarda a regra de recorte (`ProgressView`) e
as consultas usadas pela lista e pelo andamento, para os dois mostrarem a
mesma fase e a mesma contagem. As consultas reaproveitam
`process_cargos_scope` e `effective_assignment_clause`, as regras da
autorização. As rotas de atividade e `GET /tasks` não mudam.

A entrega não cria tabela, migração nem permissão.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2

**Storage**: PostgreSQL 17, sem mudança de esquema

**Testing**: Pytest, Testcontainers, `TestClient` com `authenticate`, jornadas a partir de `bootstrap_fresh_deploy`

**Target Platform**: serviço Linux em contêiner

**Project Type**: web service

**Performance Goals**: a lista faz três consultas a mais por página (designações do usuário, execuções em andamento dos processos `OPEN`, laboratórios), sem consulta por item; o andamento faz até seis (processo, designações do usuário, fases, pessoas, execuções, laboratórios)

**Constraints**: só leitura; mudanças aditivas em `GET /processes`; respostas do andamento com `extra='forbid'`

**Scale/Scope**: até dezenas de designações e execuções por processo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Antes | Depois do desenho |
|---|---|---|
| I. Requisitos e evidência | PASS: spec com CONFIRMADO e INFERÊNCIA; decisões em `docs/observacoes-e-pendencias.md`, seção "Andamento do processo", copiadas para Clarifications | PASS: cada escolha de [research](research.md) aponta o FR ou a decisão que atende |
| II. Rastreabilidade e auditoria | PASS: sem modelo novo; leitura não é ação de negócio (FR-010) | PASS: nenhuma rota grava evento ([R8](research.md#r8-auditoria)); as jornadas citam a história que provam |
| III. Segurança, autorização e sigilo | PASS: `404` a quem não vê o processo (FR-009); recorte por cargo (FR-012); sem e-mail; dados internos fora (FR-007) | PASS: acesso e recorte calculados no banco a cada requisição ([R4](research.md#r4-quem-consulta-o-andamento), [R9](research.md#r9-recorte-por-cargo)); isolamento por laboratório pela mesma base de `/tasks`; revisão cega preservada; schemas sem campo de substância, código, formulário ou resultado ([R7](research.md#r7-o-que-fica-fora-da-resposta)); a execução de um laboratório aparece só como nome, fase e data, sem conteúdo nem acesso |
| IV. IA como apoio, decisão humana | PASS: não toca IA | PASS: não toca IA |
| V. Testes orientados a jornadas | PASS: uma jornada por história | PASS: [quickstart](quickstart.md) lista a jornada e os testes focados de autorização, isolamento, paginação, ordem e regressão das rotas de amostras |
| VI. Simples e cirúrgico | PASS: uma rota nova para todos os cargos; `GET /processes` só ganha campos e um filtro | PASS: um módulo no core, oito schemas pequenos e uma cláusula (`role_process_clause`) que `proponent_process_clause` reaproveita. A lista volta a usar `paginate_query` ([R1](research.md#r1-onde-mora-o-acompanhamento), [R3](research.md#r3-campos-do-item-da-lista)) |
| VII. Documentação do estado atual | PASS: FR-011 pede o manual | PASS: guia novo e páginas de referência listados abaixo |

Sem exceções.

## Project Structure

### Documentation (this feature)

```text
specs/048-process-progress/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── process-progress.md
├── checklists/
│   └── requirements.md
└── tasks.md             # gerado por /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── core/process_progress.py          # ProgressView, viewer_assignments, open_runs,
│                                     # current_phase, build_progress
├── core/process_engine.py            # role_process_clause
├── routers/processes.py              # filtro role, campos do item, GET /{id}/progress
└── schemas.py                        # ProgressPhase, ProgressPhaseStatus, ViewerRole,
                                      # ProcessListItem, ProgressPerson, ProgressRole,
                                      # ProgressActivity, ProgressRun, ProcessProgress

tests/
├── api/routers/test_process_progress.py             # lista, filtro, andamento, fases, estados
├── api/routers/test_process_progress_visibility.py  # recorte de cada cargo
├── api/routers/test_process_progress_security.py    # 404, sem dado interno, rotas de amostras inalteradas
└── integration/journeys/etapa_2_planejamento_preparacao/
    └── test_process_progress_journey.py             # US1 a US4

manual/
├── guias/acompanhar-andamento.md           # guia; no nav do mkdocs.yml
├── referencia/perfis-permissoes-cargos.md  # observação do cargo sponsor
├── referencia/listagens-e-referencias.md   # filtro role e campos novos
└── explicacao/escopo.md                    # RF030
```

`manual/referencia/rotas.md` é gerado do OpenAPI no build e não precisa de
edição.

**Structure Decision**: serviço único, nas pastas atuais. O único módulo novo
é `core/process_progress.py`, porque a lista e o andamento compartilham a
regra de recorte ([R1](research.md#r1-onde-mora-o-acompanhamento)).
