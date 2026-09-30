# Implementation Plan: Validade da designação laboratorial

**Branch**: `feat/035-lab-designation-validity` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/035-lab-designation-validity/spec.md`

## Summary

A designação laboratorial continua concedendo acesso depois do fim do vínculo
ou da inativação do laboratório (issue #60), contrariando a Spec 006 (FR-008).
O sistema já calcula a efetividade, mas só para exibir. A correção cria um
predicado SQL único de efetividade em `core/authorization.py` e o aplica nos
dois pontos por onde passa toda autorização por cargo de processo
(`process_cargos_scope` e `active_participant_process_scope`), no cálculo
exibido em `/auth/me` e na listagem de participantes, e na validação de nova
designação. As quatro ações institucionais que mudam a efetividade passam a
gravar eventos de perda ou volta da validade na trilha dos processos em
andamento, comparando o antes e o depois na mesma transação.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic 2

**Storage**: PostgreSQL 17 (pgvector); sem migração nesta feature

**Testing**: pytest com testcontainers (`pgvector/pgvector:pg17`), factory_boy; metodologia `fastapi-testing-methodology`

**Target Platform**: servidor Linux (container Docker)

**Project Type**: web-service (API backend)

**Performance Goals**: sem regressão perceptível nas rotas de processo e tarefa; a checagem nova é um `EXISTS` coberto por índice único parcial (research R3)

**Constraints**: negação idêntica à de quem nunca teve o cargo (Spec 034); eventos na mesma transação da ação institucional; nenhuma revogação automática

**Scale/Scope**: 4 módulos alterados (`core/authorization.py`, `core/participant_service.py`, `routers/institutional.py`, `routers/processes.py`), 1 arquivo de teste novo, ajustes em testes existentes e no `README.md`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` é o template sem preencher, como nas specs
anteriores (ex.: Spec 034). Os gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Issue #60; Spec 006 FR-008 e research decisão 6; RF004 e RF044 |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ Três respostas na Session 2026-09-30 da spec; nenhum marcador aberto |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ Restringe acesso, nunca amplia. Negação idêntica à de quem não tem o cargo. Eventos usam a trilha e a visibilidade existentes. Geração de códigos cegos inalterada (FR-014) |
| Mudança cirúrgica, sem abstração preventiva | ✅ Um predicado e um helper de eventos; nenhum módulo, tabela ou migração novos |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final (seção "Participantes e Conflito de Interesses") |

**Re-check pós-design**: sem violações. Pontos de atenção:

- **Filtro global de soft-delete (Spec 022)**: o predicado mantém os filtros
  `deleted_at` explícitos; o teste precisa cobrir laboratório e instituição
  inativos, não só o vínculo.
- **`compute_effectiveness_map`**: a reescrita via SQL muda o resultado quando
  a instituição está inativa. Testes existentes que assumiam o contrário, se
  houver, são ajustados como correção do defeito (SC-005).
- **Concorrência**: a trava `FOR UPDATE` nas designações candidatas evita
  eventos duplicados entre ações institucionais simultâneas (research R4).

## Project Structure

### Documentation (this feature)

```text
specs/035-lab-designation-validity/
├── spec.md
├── plan.md              # este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── http-api.md      # Phase 1
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── authorization.py        # effective_assignment_clause(); process_cargos_scope,
│   │                           # active_participant_process_scope, compute_effectiveness_map,
│   │                           # has_active_laboratory_affiliation passam a usá-lo
│   └── participant_service.py  # snapshot/registro de eventos de validade (R4)
└── routers/
    ├── institutional.py        # 4 endpoints chamam o serviço antes do commit
    └── processes.py            # PARTICIPANT_EVENT_TYPES ganha os 2 tipos novos

tests/api/routers/
├── test_lab_designation_validity.py   # novo: matriz de acesso, consistência, eventos
├── test_participant_router.py         # ajustes, se necessários
└── test_institutional_concurrency.py  # caso de concorrência dos eventos

README.md                              # regra de efetividade e eventos novos
```

**Structure Decision**: backend único existente (`src/pivma/`, `tests/`). A
feature altera módulos já existentes; nenhum módulo ou pacote novo.

## Complexity Tracking

Sem violações a justificar.
