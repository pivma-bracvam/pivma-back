# Implementation Plan: Helper Único de Conclusão de Atividade (Issue #22)

**Branch**: `chore/026-activity-completion-helper` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/026-activity-completion-helper/spec.md`

## Summary

Unificar os quatro pontos do motor de processos que hoje reimplementam,
isoladamente, a sequência "concluir a execução atual de uma atividade e
destravar as dependentes": `submit_proposal_form` e `execute_triage_decision`
(bloco literal de conclusão de execução/atividade/tarefas, duplicado) em
`core/process_engine.py`, e as duas chamadas a `_unblock_triage_activity` em
`core/pre_evaluation_service.py` (`_execute` e `request_direct_review`), que
hoje resolvem a triagem por chave fixa em vez de usar o motor genérico de
dependências (`_advance_dependent_activities`/`_activate_activity`,
dirigido pela tabela `ActivityDependency`).

A unificação corrige, deliberadamente, uma divergência de comportamento já
existente: `_unblock_triage_activity` reaproveita a mesma `ActivityRun`/`Task`
da triagem entre rodadas de diligência, em vez de criar uma nova a cada
rodada (como a submissão já faz via `_open_new_submission_run`). Essa
divergência foi tratada como bug (decisão do responsável do produto, riscos
aceitos — ver `spec.md` > Clarifications), não como comportamento a
preservar. Nenhum endpoint, schema de request/response ou contrato de API
muda de forma.

Além da implementação, esta entrega inclui um **CHANGELOG voltado a quem já
opera o sistema hoje** (triadores, gestores de processo, suporte), descrevendo
em linguagem não-técnica os efeitos observáveis da mudança — não um changelog
de código interno.

## Technical Context

**Language/Version**: Python 3.14 (`pyproject.toml`, `requires-python = ">=3.14,<4.0"`)

**Primary Dependencies**: FastAPI 0.141, SQLAlchemy 2.0 (async) + psycopg, Pydantic v2 — nenhuma dependência nova

**Storage**: PostgreSQL; tabelas existentes `activity_instances`, `activity_runs`, `tasks`, `activity_dependencies`, `audit_events` — sem migração de schema, só efeito de dado (mais linhas de `ActivityRun`/`Task`/`AuditEvent` por processo com diligência de triagem)

**Testing**: pytest + pytest-asyncio, seguindo a metodologia já usada no projeto (`tests/unit/core`, `tests/api/routers`); a skill `fastapi-testing-methodology` é carregada explicitamente na fase de tasks/implementação, antes de escrever ou alterar qualquer teste

**Target Platform**: Linux server (backend FastAPI já containerizado)

**Project Type**: Serviço web único (backend); `demos/` é a única camada de interface, desacoplada de `src/` (AGENTS.md)

**Performance Goals**: Nenhuma meta nova. O helper único faz o mesmo número de operações de banco que os quatro caminhos já fazem hoje somados às operações que `_unblock_triage_activity` hoje pula (criação de run/task) — custo desprezível, não recorrente por requisição.

**Constraints**: Nenhum endpoint novo nem mudança de schema de resposta (AGENTS.md, Regra 4 — "Proibição de Endpoints Facilitadores"); os quatro pontos de chamada devem passar a usar exclusivamente o helper único; comportamento observável dos três pontos que já usam o motor genérico não muda; o quarto ponto (triagem) muda de forma documentada e intencional (spec, FR-003 a FR-006).

**Scale/Scope**: Dois módulos centrais (`core/process_engine.py`, `core/pre_evaluation_service.py`), um helper novo, testes unitários e de integração, sem seed/demo novos (reaproveita `demos/triage/` e `scripts/seeds/seed_triage.py` existentes), um CHANGELOG orientado a usuário.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Nota**: `.specify/memory/constitution.md` contém só o template padrão (não
ratificado). Como em specs anteriores (ex. 020, 022), o gate usa os
princípios registrados em `AGENTS.md` como critério — lido a partir de
`git show HEAD:AGENTS.md`, já que a cópia no working tree está vazia por uma
edição não commitada, sem relação com esta feature (sinalizado ao usuário).

**Pré-design: APROVADO**

- **Regra 1 (demo por novo módulo)**: não se aplica — esta feature não cria
  um módulo novo, é um refactor/correção de um mecanismo interno já
  existente (conclusão de atividade e desbloqueio de dependentes).
- **Regra 3 (demonstração como critério de conclusão)**: em conformidade —
  a demo já existente (`demos/triage/`) já expõe a ação "Solicitar
  Diligência" (`NEEDS_REVISION`) contra a API real; a validação desta
  feature reaproveita esse fluxo (submissão → diligência → reenvio →
  decisão) sem precisar de uma página nova. Ver `quickstart.md`.
- **Regra 4 (proibição de endpoints facilitadores)**: em conformidade —
  nenhum endpoint novo é criado; os efeitos observáveis (FR-003 a FR-006 da
  spec) aparecem nos endpoints e schemas já existentes (`GET /tasks`,
  Kanban, timeline).
- **Menor implementação completa**: em conformidade — reaproveita o motor
  genérico de dependências já existente (`_advance_dependent_activities`/
  `_activate_activity`) em vez de criar um terceiro mecanismo.

**Pós-design: APROVADO**

- `data-model.md` confirma: nenhuma tabela, coluna ou migração nova; a
  mudança é só de cardinalidade de uso (`ActivityRun`/`Task` por rodada da
  triagem) e de um evento de auditoria já padronizado.
- `research.md` #3 registra e mitiga o único risco de escopo encontrado
  durante o design (o texto da tarefa de triagem mudar para *toda* primeira
  rodada, não só para diligências) — resolvido preservando o texto atual via
  parâmetro explícito, sem reabrir discussão de contrato.
- `contracts/` permanece vazio deliberadamente — nenhum contrato muda de
  forma (FR-007).
- Nenhum item pendente em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/026-activity-completion-helper/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — decisões de design do helper único
├── data-model.md        # Fase 1 — efeito sobre ActivityRun/Task/AuditEvent
├── quickstart.md        # Fase 1 — validação manual via demo de triagem
├── CHANGELOG.md          # Rascunho do changelog orientado a usuário (ver Deliverables)
├── contracts/            # Vazio deliberadamente — ver "Contracts" abaixo
└── tasks.md              # Saída do /speckit-tasks (não criado por este comando)
```

### Source Code (repository root)

```text
src/pivma/core/
├── process_engine.py        # _complete_activity_run() (novo helper único);
│                             # submit_proposal_form() e execute_triage_decision()
│                             # passam a chamá-lo em vez do bloco duplicado;
│                             # _unblock_triage_activity() removido, substituído
│                             # pela chamada genérica a _advance_dependent_activities()
└── pre_evaluation_service.py # _execute() e request_direct_review() passam a
                              # chamar o motor genérico em vez de
                              # _unblock_triage_activity()

tests/unit/core/
└── test_process_engine.py   # teste unitário isolado do helper único (FR-009)

tests/api/routers/
├── test_triage_decision.py        # ajustado: nova rodada de triagem passa a
│                                    # ter run_number/Task próprios
└── (outros testes de submissão/pré-avaliação com asserts sobre a triagem,
    conforme mapeados na Fase 0/1)
```

**Structure Decision**: Mudança confinada a dois módulos já existentes em
`core/` e aos testes que exercitam os quatro pontos de chamada — nenhum
diretório novo em `src/`, nenhuma migração, nenhum demo/seed novo.

## Contracts

Este projeto expõe uma API REST, mas esta feature não adiciona, remove nem
muda a forma de nenhum endpoint, request ou response schema (spec, FR-007).
Por isso `contracts/` fica deliberadamente vazio — os contratos afetados
(`GET /tasks`, `GET /activities/kanban`, `GET /processes/{id}/timeline`,
`POST /processes/{id}/triage/decision`) já estão documentados no código-fonte
(`src/pivma/schemas.py`) e não sofrem alteração de schema. O efeito é só de
dado, documentado em `data-model.md` e no CHANGELOG orientado a usuário.

## Deliverables (entregáveis)

Além da implementação (dois módulos + testes), esta feature entrega:

- **`CHANGELOG.md`** (nesta pasta, promovido para o local de changelog do
  projeto se um existir — a confirmar na Fase de tasks): documento em
  linguagem não-técnica para quem **já usa o sistema hoje** (equipe BraCVAM/
  triadores, gestores de processo, suporte) e vai precisar revisar o que
  mudou depois do deploy. Cobre especificamente comportamento observável, não
  implementação:
  - `run_number` da atividade de triagem passa a incrementar a cada rodada de
    diligência, em vez de ficar fixo em 1.
  - Uma tarefa pendente nova aparece para quem faz a triagem a cada rodada de
    diligência (hoje, a segunda rodada em diante não gera pendência visível).
  - O prazo/SLA da triagem passa a ser recalculado a partir do início de cada
    rodada, não mais da primeira rodada do processo.
  - Um novo evento aparece no histórico do processo (linha do tempo) quando a
    triagem é destravada, consistente com o já emitido para outras etapas.
  - Nenhuma ação do usuário muda: os mesmos botões/fluxos de hoje continuam
    funcionando; a diferença é só o que aparece na lista de pendências, no
    Kanban e na linha do tempo depois de uma diligência.
  - Um rascunho inicial deste documento é produzido nesta fase de plano (ver
    `CHANGELOG.md`); ele deve ser revisado e confirmado como parte da
    implementação, antes de abrir o PR, para garantir que reflete o
    comportamento realmente entregue.

## Complexity Tracking

> Nenhuma violação do Constitution Check a justificar — a mudança reaproveita
> mecanismos já existentes e não introduz endpoints, tabelas ou permissões
> novas.
