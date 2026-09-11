# Implementation Plan: Kanban de Pendências e Revisão de Cargos

**Branch**: `018-kanban-activities-roles` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-kanban-activities-roles/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Consolidar, para o usuário autenticado, todas as atividades pendentes/em
andamento/atrasadas/concluídas de todos os métodos a que ele tem acesso em uma única
visão Kanban — sem abrir método por método — e, como pré-requisito estrutural, corrigir
a autorização hoje existente para que os cargos globais (`Padrão`, `Admin`, `BraCVAM`)
controlem visibilidade em toda a plataforma e os cargos contextuais (Proponente, Gestor
etc.) valham apenas dentro do método em que foram atribuídos, sempre vinculados a um
cargo — nunca a uma pessoa específica.

A abordagem técnica reaproveita, quase integralmente, o modelo de autorização já
existente (`Assignment`/`role_key` por processo, `AccessProfile`/`UserAccessProfile`
para o nível global, `GET /auth/me` que já computa `access.profiles` +
`access.scopes` agrupados por processo). Nenhuma tabela nova é necessária: a correção é,
sobretudo, aplicar consistentemente uma regra de visibilidade que hoje só existe pela
metade, normalizar o vocabulário de "cargo" usado por atividades/tarefas (hoje três
vocabulários distintos e parcialmente inconsistentes) e declarar o novo conceito de
prazo (SLA) por etapa dentro da mesma definição declarativa (YAML) que já descreve
fases, atividades, dependências e formulários. A visão Kanban em si é servida por um
novo endpoint de leitura, construído sobre `ActivityInstance` (não `Task`, porque
atividades ainda não iniciadas não têm `Task`/`ActivityRun` algum) com a mesma regra de
visibilidade.

## Technical Context

**Language/Version**: Python >=3.14 (padrão do projeto)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic,
PostgreSQL (`pgvector`), `structlog` — stack já estabelecida, sem dependência nova.

**Storage**: PostgreSQL. Nenhuma tabela nova; um SLA opcional passa a viver dentro do
JSONB `ProcessTemplateVersion.definition_payload` (mesmo lugar que já guarda fases,
atividades, dependências e formulários) e uma migração de dados normaliza valores já
armazenados em `tasks.assigned_role`.

**Testing**: `pytest` com Testcontainers (`pgvector/pgvector:pg17`), factories de
`tests/factories/`, estrutura em níveis (`unit/`, `api/routers/`,
`integration/database/`, `integration/migrations/`) — conforme Constituição Princípio IV.

**Target Platform**: Linux server (API); a demonstração é uma página estática em
`demos/` consumindo a API real.

**Project Type**: web-service de projeto único (`src/pivma/`), com `demos/` desacoplado
— não há frontend/mobile próprios neste repositório.

**Performance Goals**: Um usuário Admin/BraCVAM com ~300 métodos associados (dado do
enunciado) precisa montar o Kanban completo em uma única consulta paginável, sem uma
requisição por método (FR-012); nenhum outro alvo numérico foi definido pelo usuário —
usar as práticas já adotadas pelo projeto para listagens (paginação `page`/`size`, como
em `GET /processes`).

**Constraints**: nenhum endpoint exclusivo para viabilizar a demo (Constituição
Princípio II); toda rota de mutação valida `CurrentUser` + `TrustedOrigin`; autorização
RBAC reavaliada no banco a cada requisição, sem cache de permissão no token
(Constituição Princípio VI); todo novo modelo relacional herda `AuditMixin` — não
aplicável aqui, pois nenhuma tabela nova é criada.

**Scale/Scope**: até ~300 processos associados a um único usuário; hoje 2 atividades
declaradas por método nos 5 templates oficiais (Fase 1), crescendo com fases futuras
(Spec 017) — o desenho da visibilidade e do Kanban não pode depender de um número fixo
de atividades por processo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
|---|---|
| I. Spec Kit | `spec.md` aprovado (checklist verde, 2 rodadas de clarificação resolvidas) antes deste `plan.md`. PASS. |
| II. Domínio puro / demos descartáveis | O novo endpoint de Kanban e a correção de visibilidade atendem ao domínio (qualquer cliente precisa disso), não só à demo; `demos/kanban/` consome exclusivamente API real. PASS — confirmado na implementação (`tasks.md` T017-T038). |
| III. Demo como critério de conclusão | Página em `demos/kanban/` + seed `scripts/seeds/seed_kanban.py` simulando um BraCVAM com ~300 métodos e dois usuários `Padrão` com cargos cruzados — implementado e validado end-to-end contra um Postgres real (upgrade de migração incluído). PASS. |
| IV. Qualidade verificável | `poe format`/`poe lint`/`poe test` continuam obrigatórios; testes nos 4 níveis, factories, Arrange-Act-Assert. **Exceção registrada**: as skills `andrej-karpathy-skills:karpathy-guidelines` e `fastapi-testing-methodology`, listadas pelo `CLAUDE.md` como disponíveis por equivalência neste ambiente Claude Code, **não estão instaladas** (`Skill({skill: "andrej-karpathy-skills:karpathy-guidelines"})` falha com "Unknown skill"; `fastapi-testing-methodology` não está symlinkada em `.claude/skills/`, só existe em `.agents/skills/`). Isso já havia sido antecipado para `stop-slop` no próprio `CLAUDE.md`; a mesma lacuna se aplica agora a estas duas. Os princípios das skills (simplicidade, reaproveitamento, metodologia de teste em níveis) são seguidos manualmente neste plano e devem sê-lo na implementação; a divergência fica registrada aqui conforme a cláusula de Conformidade da Constituição, em vez de presumir cumprimento automático. |
| V. Auditabilidade | Nenhuma tabela nova; nenhum dado de domínio é apagado fisicamente. A migração de dados que normaliza `tasks.assigned_role` preserva todas as linhas (`UPDATE`, não `DELETE`). PASS. |
| VI. Segurança por padrão | A correção de visibilidade (FR-006/FR-014) é reavaliada no banco a cada requisição (via `Assignment`/`AccessProfile`), sem cache — alinhado ao princípio, não uma exceção a ele. PASS. |

Nenhuma violação bloqueante identificada; a única divergência (skills ausentes) está
registrada como exceção justificada, não como item de `Complexity Tracking` (não é
complexidade de código, é lacuna de ambiente).

### Re-checagem pós-design (após Phase 1)

Confirmado em `research.md`/`data-model.md`/`contracts/`: nenhuma tabela nova, uma única
migração e de dados (não estrutural), nenhum endpoint criado só para a demo (o endpoint
novo, `GET /activities/kanban`, atende a User Story 1 independentemente de qualquer
demonstração), toda visibilidade reavaliada no banco a cada requisição (nenhum cache de
permissão introduzido). Constitution Check permanece PASS; nenhuma entrada nova em
`Complexity Tracking`.

## Project Structure

### Documentation (this feature)

```text
specs/018-kanban-activities-roles/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── authorization.py        # + has_platform_wide_access, active_participant_process_scope,
│   │                            #   resolve_activity_holders (novas funções puras de escopo/cargo)
│   ├── process_engine.py       # fix: _init_first_activity deixa de gravar Task.assigned_user_id;
│   │                            #   leitura de sla declarado no payload do template
│   └── database/models.py      # sem tabela nova; nenhuma mudança de schema estrutural
├── routers/
│   ├── processes.py             # GET /processes, GET /processes/{id}: aplica a visibilidade corrigida
│   ├── tasks.py                  # GET /tasks: aplica a visibilidade corrigida
│   └── activities.py             # NOVO: GET /activities/kanban (visão consolidada)
├── schemas.py                    # + schemas do Kanban; normalização do vocabulário de cargo (Literal)
└── templates_data/*.yaml         # + campo opcional `sla_hours` por atividade; `assigned_role`
                                    #   normalizado para o vocabulário de cargo compartilhado

migrations/versions/
└── <hash>_normalize_task_assigned_role.py   # migração de dados (UPDATE), não estrutural

demos/kanban/
└── index.html                    # consome só a API real (Constituição Princípio II);
                                    #   nome curto, seguindo o padrão já usado por
                                    #   demos/roadmap, demos/triage etc. (não o nome da spec)

scripts/seeds/
└── seed_kanban.py                # ~300 processos variados p/ 1 usuário BraCVAM + Padrão
                                    #   com cargos mistos; nome seguindo o padrão
                                    #   seed_<topico>.py já usado pelos demais seeds

tests/
├── unit/core/                    # resolução de cargo, classificação de coluna/SLA
├── api/routers/                  # contrato HTTP dos 3 endpoints (visibilidade, Kanban)
├── integration/database/         # nenhuma nova constraint estrutural a testar
└── integration/migrations/       # upgrade/downgrade da migração de normalização de dados
```

**Structure Decision**: projeto único já estabelecido (`src/pivma/` + `tests/` +
`migrations/` + `demos/` + `scripts/seeds/`); nenhuma reestruturação de diretórios é
necessária. A única adição de módulo é `src/pivma/routers/activities.py` para o novo
endpoint de Kanban; o restante são alterações em arquivos já existentes.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

Nenhuma violação de complexidade a justificar — o desenho deliberadamente evita tabelas
novas, reaproveitando `Assignment`/`AccessProfile`/`GET /auth/me` já existentes.
