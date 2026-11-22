# Implementation Plan: Alerts na plataforma

**Branch**: `feat/047-alerts` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/047-alerts/spec.md`

## Summary

A entrega cria a tabela `alerts`, um serviço `core/alert_service.py` que grava os alerts na sessão da operação de negócio, e três rotas em `routers/alerts.py`: listar com contador de não lidos, marcar um como lido e marcar todos.

Cada gatilho chama o serviço logo depois do próprio `AuditEvent` ([research R4](research.md#r4-pontos-de-geração)). Quem recebe uma tarefa nova sai da mesma regra de `can_act` de `GET /tasks`, que muda de `routers/tasks.py` para `core/authorization.py` sem mudar o conteúdo ([R3](research.md#r3-quem-recebe-task_opened)). Os caminhos da IA passam autor nulo, para que o proponente receba a devolução e a ida para a triagem ([R5](research.md#r5-autor-nas-ações-da-ia)).

A fila de e-mail (`notifications`) não muda.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2, Alembic

**Storage**: PostgreSQL 17. Uma tabela nova (`alerts`) e uma migração

**Testing**: Pytest, Testcontainers, provedor de IA fake, factories de `tests/factories/`

**Target Platform**: serviço Linux em contêiner

**Project Type**: web service

**Performance Goals**: a listagem e o contador saem de duas consultas indexadas. A geração faz uma consulta por candidato em `task_opened` e uma consulta de destinatários nos demais tipos

**Constraints**: alert na mesma transação da operação; nenhuma dependência do canal de e-mail; parâmetros sem dado cego, de outro laboratório ou de autoria oculta; contratos existentes sem mudança

**Scale/Scope**: dezenas de candidatos por processo; cerca de onze alerts por pessoa do BraCVAM a cada processo ([R13](research.md#r13-ponto-a-validar-alcance-do-bracvam))

## Constitution Check

*GATE: avaliado antes da pesquisa e de novo depois do desenho.*

| Princípio | Antes | Depois do desenho |
|---|---|---|
| I. Requisitos e evidência | PASS. RF011 e RF033 como fonte, decisões do usuário em `docs/observacoes-e-pendencias.md`, fatos classificados na spec | PASS. O alcance do BraCVAM ficou como PONTO A VALIDAR (R13), e o plano segue o comportamento atual de `can_act` |
| II. Rastreabilidade e auditoria | PASS. `Alert` herda `AuditMixin`. Os gatilhos já gravam `AuditEvent` | PASS. Marcar como lido é estado pessoal e não grava `AuditEvent` (FR-019, R11). Não há exclusão |
| III. Segurança, autorização e sigilo | PASS. Rotas com `CurrentUser` e `TrustedOrigin`; alert de outro usuário responde `404` | PASS. Destinatários pela mesma cláusula de `can_act`, que já trata laboratório e conflito. Parâmetros com chaves fixas por tipo, sem dado cego (R12) |
| IV. IA como apoio | PASS. A feature não muda decisões da IA | PASS |
| V. Testes orientados a jornadas | PASS. Cada história tem teste de jornada; erros, isolamento, autoria, concorrência e paginação em testes focados | PASS |
| VI. Simples e cirúrgico | PASS. Sem push, sem preferências, sem e-mail novo | PASS. A única mudança fora do código novo é mover `_can_act_clause` e acrescentar `alert_actor_id` em duas funções do motor, ambas exigidas pela spec |
| VII. Documentação do estado atual | PASS. O manual ganha a página de alerts e as rotas | PASS |

Sem exceções. Complexity Tracking não se aplica.

## Project Structure

### Documentation (this feature)

```text
specs/047-alerts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── alerts-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── alert_service.py            # novo: geração, destinatários, leitura
│   ├── authorization.py            # recebe task_can_act_clause
│   ├── database/models.py          # modelo Alert
│   ├── process_engine.py           # gatilhos de tarefa, triagem, laboratório
│   ├── participant_service.py      # designação e efetividade
│   ├── pre_evaluation_service.py   # resultado positivo, autor nulo
│   ├── return_review_service.py    # desistência
│   ├── sample_receipt_service.py   # resolução e decisão de frasco
│   └── structure_approval_service.py
├── routers/
│   ├── alerts.py                   # novo
│   ├── process_participants.py     # revogação
│   └── tasks.py                    # importa task_can_act_clause
├── schemas.py                      # AlertItem, AlertListResponse, AlertReadAllResponse
└── __init__.py                     # include_router(alerts.router)

migrations/versions/<rev>_alerts.py  # nova, down_revision c4e6a8b0d2f1

tests/
├── factories/alert_factory.py
├── integration/database/test_alert_service.py   # deduplicação, autor, conta inativa, rollback
├── integration/migrations/test_alerts_migration.py
├── integration/journeys/
│   ├── etapa_1_submissao_triagem/
│   │   ├── test_alerts_task_journey.py           # US1
│   │   ├── test_alerts_inbox_journey.py          # US2
│   │   └── test_alerts_withdrawal_journey.py     # US6
│   ├── etapa_2_planejamento_preparacao/
│   │   ├── test_alerts_proponent_decisions_journey.py  # US3
│   │   └── test_alerts_assignments_journey.py    # US4
│   └── etapa_3_execucao_validacao/
│       └── test_alerts_laboratories_journey.py   # US5
└── api/routers/
    ├── test_alerts_router.py       # listagem, leitura, paginação, 401/403/404/422
    ├── test_alerts_concurrency.py  # marcações simultâneas
    ├── test_alerts_task_opened.py  # US1
    ├── test_alerts_decisions.py    # US3 e US6
    ├── test_alerts_assignments.py  # US4
    ├── test_alerts_laboratories.py # US5
    └── test_alerts_security.py     # isolamento, cegamento, autoria, conflito, e-mail desligado

manual/
├── explicacao/alertas.md           # novo
├── referencia/rotas.md
├── referencia/eventos.md           # tipos de alert por gatilho
└── explicacao/escopo.md            # RF011 e RF033
```

**Structure Decision**: o serviço segue o padrão `core/*_service.py`, e a rota o padrão `routers/*.py`. Os testes seguem as pastas de jornada por etapa e os testes de rota em `tests/api/routers/`.

## Ordem de implementação

1. Modelo, migração e `alert_service` com a leitura, a listagem e as rotas (história 2). Verificação: testes de rota verdes com alerts criados por factory.
2. `task_can_act_clause` em `authorization.py`, com `GET /tasks` sem mudança. Verificação: a suíte de `/tasks` continua verde.
3. `task_opened` nos seis pontos e `alert_actor_id` nos caminhos da IA (história 1). Verificação: jornada da triagem e testes de laboratório e conflito.
4. Demais tipos (histórias 3 a 6). Verificação: uma jornada por etapa e o teste de chaves proibidas por tipo.
5. Manual. Verificação: `poe docs-build`.

## Complexity Tracking

Não se aplica.
