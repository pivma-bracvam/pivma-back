# Implementation Plan: Prazo Real (due_date) das Atividades

**Branch**: `024-activity-description-due-date` (implementação direta em `develop`, sem branch de feature dedicado — decisão registrada em `spec.md` > Clarifications/Assumptions) | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-activity-description-due-date/spec.md`

## Summary

`Task.due_date` existe no modelo hoje mas nunca é preenchido — todo consumidor
de prazo depende do cálculo ao vivo em `classify_kanban_column` (formato
`run_started_at + sla_hours`), que só alimenta a classificação do kanban, não
nenhum outro endpoint. A abordagem técnica: reaproveitar exatamente essa mesma
fórmula, calculada uma vez no momento em que uma `Task` é criada para uma
atividade — nos **quatro** pontos do motor de processos que criam `Task` hoje:
`_init_first_activity`, `_activate_activity` (motor genérico) e, achado
durante a validação manual contra a API real, dois caminhos legados
anteriores à Spec 017 que resolvem uma atividade pela chave em vez do motor
genérico — `_unblock_triage_activity` (desbloqueia `triage_evaluation`, usado
por praticamente todo processo real) e `_open_new_submission_run` (reabre
`proposal_submission` para retrabalho). Persistir o resultado em
`Task.due_date`. `TaskSummary` já declara `due_date` — só passa a vir
preenchido. `TaskDetail` ainda não declara o campo (só `TaskSummary` tem
hoje) e precisa ganhá-lo, junto com `get_task_detail`, para que o endpoint de
detalhe também exponha o prazo — extensão de um endpoint já existente, não um
endpoint novo (AGENTS.md, Regra 4). Sem backfill (spec, Clarifications).

## Technical Context

**Language/Version**: Python 3.14 (`pyproject.toml`, `requires-python = ">=3.14,<4.0"`)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x (async) + psycopg3, Alembic (migração de schema não é necessária aqui — `due_date` já existe na tabela `tasks`, só passa a ser escrito)

**Storage**: PostgreSQL (tabela `tasks`, coluna `due_date` já existente, hoje sempre `NULL`)

**Testing**: pytest + pytest-asyncio, seguindo a metodologia já usada no projeto (`tests/unit/core`, `tests/api/routers`) — a fetch da skill `fastapi-testing-methodology` acontece na fase de tasks/implementação, antes de escrever os testes

**Target Platform**: Linux server (mesmo backend containerizado já existente, `compose.yaml`/`Dockerfile`)

**Project Type**: Serviço web único (backend FastAPI) — sem frontend próprio; `demos/` é a única camada de interface, explicitamente desacoplada de `src/` (AGENTS.md)

**Performance Goals**: Nenhuma meta nova — o cálculo é o mesmo já feito hoje em `classify_kanban_column`, só passa a rodar uma vez na ativação da atividade em vez de a cada leitura do kanban; custo desprezível e não recorrente por consulta

**Constraints**: Nenhum endpoint novo (AGENTS.md, Regra 4 — "Proibição de Endpoints Facilitadores"); mudança deve caber nos dois pontos já existentes de criação de `Task` no motor de processos, sem caminho paralelo

**Scale/Scope**: Escopo intencionalmente básico (spec, Assumptions) — só a persistência de `due_date` para atividades ativadas a partir desta mudança; sem backfill, sem descrição de atividade (fora de escopo, ver spec)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` ainda é o template não preenchido deste
projeto (placeholders `[PRINCIPLE_1_NAME]` etc.) — não há princípios
ratificados para checar aqui. A governança normativa real deste repositório é
o `AGENTS.md` (referenciado por `CLAUDE.md`). Gates aplicáveis:

| Gate (AGENTS.md) | Avaliação |
|---|---|
| Módulo ≠ Spec; módulo novo precisa de demo | Esta spec **não** cria um módulo novo — estende o módulo de Atividades/Kanban já demonstrado em `demos/kanban`. Gate cumprido reutilizando essa demo (Fase 1, `quickstart.md`), sem criar uma pasta nova em `demos/`. |
| Demonstração como critério de conclusão, com a API real | `demos/kanban` já consome a API real; será estendida para exibir `due_date` a partir de `GET /tasks`. O seed (`scripts/seeds/seed_kanban.py`) não precisa mudar — os templates oficiais já declaram `sla_hours` e o seed já instancia processos que passam por essas atividades. |
| Proibição de endpoints facilitadores | `TaskSummary`/`TaskDetail` já expõem `due_date` — nenhum endpoint novo é criado só para a demo ou para esta capacidade. |
| Total desacoplamento de `demos/` | Mudança em `demos/kanban` continua HTML/JS estático consumindo a API pública; nenhum acoplamento novo com `src/`. |

**Resultado**: PASS, sem violações a justificar. `Complexity Tracking` fica vazio.

## Project Structure

### Documentation (this feature)

```text
specs/024-activity-description-due-date/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── tasks-due-date.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── process_engine.py     # _compute_activity_due_date + _template_activity_data (novos); wired em
│   │                          # _init_first_activity, _activate_activity, _unblock_triage_activity,
│   │                          # _open_new_submission_run — os 4 pontos que criam Task
│   └── database/models.py    # Task.due_date já existe — nenhuma migração nova
├── routers/
│   └── tasks.py               # get_task_detail passa a preencher due_date na resposta
└── schemas.py                  # TaskDetail ganha due_date (TaskSummary já tinha)

tests/
├── unit/core/                  # cálculo de due_date na ativação (primeira atividade e desbloqueio por dependência)
└── api/routers/                # GET /tasks e /tasks/{id} passam a retornar due_date não nulo quando há sla_hours

demos/kanban/                   # estendida para exibir due_date por card/task (via GET /tasks)
# scripts/seeds/seed_kanban.py não muda — massa com sla_hours já existe
```

**Structure Decision**: Opção 1 (projeto único) — é um ajuste pontual dentro
do backend Python já existente (`src/pivma`), sem novo serviço, sem novo
diretório de topo. A única superfície de UI tocada é a demo já existente de
kanban, mantida desacoplada em `demos/kanban` por convenção do projeto.

## Complexity Tracking

*Sem violações do Constitution Check — tabela vazia intencionalmente.*

## Constitution Check (pós-design, Fase 1)

Revisado após `research.md`/`data-model.md`/`contracts/`/`quickstart.md`: o
único ajuste de contrato é um campo novo (`due_date`) em `TaskDetail`,
resposta de um endpoint já existente (`GET /tasks/{id}`) — não conflita com
a Regra 4 do `AGENTS.md` (só proíbe endpoint novo criado para facilitar a
demo, não a extensão de um campo em endpoint já existente e já usado pelo
domínio). `demos/kanban` e `scripts/seeds/seed_kanban.py` seguem
desacoplados de `src/`. **Resultado**: PASS, sem mudança em relação à
checagem inicial.
