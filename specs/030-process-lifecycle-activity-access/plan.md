# Implementation Plan: Ciclo de vida do processo e acesso por atividade

**Branch**: `feat/030-process-lifecycle-activity-access` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/030-process-lifecycle-activity-access/spec.md`

## Summary

O processo deixa de guardar a posição no fluxo (`SUBMISSION`,
`AI_PRE_EVALUATION`, `TRIAGE`, `PLANNING`) e passa a ter só o ciclo de vida
(`OPEN`, `CLOSED`, `CANCELLED`, `ARCHIVED`), validado no banco. A posição passa
a ser lida das fases e atividades, que já existem.

O acesso passa a ser por atividade: cada `ActivityInstance` recebe
`view_roles` e `edit_roles`, copiados do template na instanciação. Um usuário vê
ou edita quando algum dos seus cargos efetivos no processo (atribuições ativas
mais os cargos globais `admin`/`bracvam` do perfil) está na lista. Admin e
BraCVAM veem tudo por uma concessão que o sistema acrescenta a toda atividade;
só o `bracvam` edita a triagem.

Uma atividade nova, **revisão do retorno**, recebe o retorno negativo da IA e o
pedido de revisão da triagem. O proponente escolhe revisar, contestar a IA ou
desistir, reaproveitando os efeitos que já existem. O endpoint de revisão direta
é substituído por essa escolha.

A trava de concorrência da pré-avaliação sai do processo e vai para a
`EvaluationRun`.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Alembic, Pydantic v2

**Storage**: PostgreSQL 17 com pgvector; colunas `ARRAY(String)` novas em
`activity_instances`; `CHECK` novo em `process_instances.status`

**Testing**: Pytest + pytest-asyncio, testcontainers, factory_boy,
`TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: listagens de processos e tarefas sem consulta extra por
linha: o filtro de concessão entra na mesma query (`view_roles && cargos`)

**Constraints**: mudança de contrato incompatível com o frontend; migração com
upgrade e downgrade testados; sem regressão nos testes de concorrência da
pré-avaliação

**Scale/Scope**: 5 templates, 23 atividades após a feature, cerca de 32 arquivos
de teste com cerca de 71 asserções de status a revisar

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` ainda é o template sem preencher: não há
princípios ratificados para avaliar. Os gates usados são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável (Plano de Trabalho → spec) | ✅ RF030 citado; decisões do usuário registradas em Clarifications |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ 5 perguntas respondidas; nenhum marcador aberto |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ R5–R8, R12; cegamento das avaliações por campo mantido (FR-037); conflito de interesse acima das concessões (FR-022) |
| Mudança cirúrgica, sem abstração preventiva | ✅ colunas na própria atividade em vez de tabela de concessões (R2); cargos globais derivados em vez de atribuições gravadas (R3); efeitos da revisão do retorno reaproveitados (R9) |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ tarefa final do `tasks.md` |

**Re-check pós-design**: sem violações. Um ponto de atenção, não violação: a
remoção de `POST /submission/direct-review` é incompatível, justificada em R9
(dois caminhos para a mesma transição).

## Project Structure

### Documentation (this feature)

```text
specs/030-process-lifecycle-activity-access/
├── spec.md
├── plan.md              # este arquivo
├── research.md          # R1–R12
├── data-model.md
├── quickstart.md
├── contracts/
│   └── http-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── authorization.py          # user_cargos, require_activity_view/edit, process_visibility_clause (R4–R6)
│   ├── process_engine.py         # constantes de ciclo de vida, guardas por execução, triagem, revisão do retorno (R7, R9)
│   ├── pre_evaluation_service.py # trava na EvaluationRun, retorno → revisão do retorno, retry (R8, R9)
│   └── database/models.py        # CHECK de status, view_roles/edit_roles
├── routers/
│   ├── processes.py              # filtro Literal, respostas, timeline (R11, R12)
│   ├── forms.py                  # acesso view/edit
│   ├── triage.py                 # concessão + triage.review, nova resposta
│   ├── pre_evaluation.py         # remove direct-review; leitura por concessão
│   ├── return_review.py          # novo: GET/POST /processes/{id}/return-review
│   └── tasks.py                  # filtro por view_roles
├── schemas.py                    # ProcessLifecycle, TriageDecisionResponse, ReturnReview*
├── bootstrap_process_templates.py# validação de access na carga (FR-013)
└── templates_data/0[1-5]_*.yaml  # access em toda atividade; submission_return_review na fase 1

migrations/versions/<rev>_process_lifecycle_activity_access.py   # R10

tests/
├── unit/core/                    # validação de access, user_cargos, lifecycle_available_actions
├── api/routers/                  # matriz de acesso, triagem, revisão do retorno, tarefas, listagem
├── integration/journeys/         # jornada do processo 1 atualizada + jornadas de retorno
├── integration/migrations/       # upgrade/downgrade da revisão nova
└── integration/ai/               # retorno da IA abrindo a revisão do retorno; concorrência
```

**Structure Decision**: Estrutura existente de projeto único. A única peça nova
de roteamento é `routers/return_review.py`, registrada em `src/pivma/__init__.py`
como os demais roteadores.

## Ordem de implementação sugerida

1. **Ciclo de vida** (US1): `CHECK`, constantes, escritas de fluxo removidas,
   guardas por execução (R7), schemas e filtro (R11). Jornada existente
   atualizada.
2. **Concessões** (US2, US3): colunas, validação na carga, cópia na
   instanciação, `user_cargos`, `require_activity_*`, visibilidade de processo,
   formulários, triagem, tarefas, timeline.
3. **Trava da IA** (R8), antes de mexer no retorno.
4. **Revisão do retorno** (US4): YAMLs, motor pulando `return_review`, abertura
   nos dois retornos, rotas, remoção de `direct-review`, retry.
5. **Posição por fases** (US5): asserções de fase concluída e atividades
   paralelas visíveis por concessão.
6. **Migração** (US6) e README.

## Complexity Tracking

Sem violações a justificar.
