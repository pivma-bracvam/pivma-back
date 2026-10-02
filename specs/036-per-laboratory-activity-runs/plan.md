# Implementation Plan: Execução de atividades por laboratório participante

**Branch**: `feat/036-per-laboratory-activity-runs` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/036-per-laboratory-activity-runs/spec.md`

## Summary

O template ganha `execution_scope: "per_laboratory"` e `custody` por
atividade, validados na carga. Uma atividade por laboratório abre uma
execução e uma tarefa para cada laboratório do conjunto congelado pelos
códigos cegos da Spec 031.

Na ativação, a atividade cria uma execução para cada laboratório congelado;
a de quem ainda tem dependência por laboratório pendente nasce bloqueada.
Entre atividades por laboratório, cada laboratório avança na própria cadeia.
Uma atividade única que depende de uma atividade por laboratório espera a
conclusão de todos os laboratórios congelados.

O motor ganha `complete_laboratory_run` e `reopen_laboratory_run`, que as
issues #28 a #31 vão chamar. Duas rotas novas fazem a dispensa por fase e a
reabertura administrativa; a dispensa exige as amostras congeladas.
`GET /tasks` mostra o laboratório e o status da execução, e cada
laboratório só vê as próprias tarefas e eventos; os gestores veem todos. O
cancelamento do processo deixa de alterar execuções terminais.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Alembic,
Pydantic v2. Nenhuma dependência nova.

**Storage**: PostgreSQL 17. Uma migração: duas colunas em
`activity_instances`, uma em `activity_runs`, índice único de
`activity_runs` refeito com `NULLS NOT DISTINCT` e a tabela nova
`laboratory_waivers`.

**Testing**: Pytest + pytest-asyncio, testcontainers, factory_boy,
`TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`.

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: `GET /tasks` sem N+1 (laboratórios em lote via
`references.laboratory_refs`). Escala: dezenas de laboratórios e poucas
atividades por laboratório por processo.

**Constraints**:
- Nenhuma mudança de comportamento em atividades de execução única (FR-016).
- Execuções substituídas mantêm dados intactos (FR-024).
- Migração com upgrade e downgrade testados.
- Transições serializadas por processo (R12).
- Nenhuma resposta a pessoa de laboratório revela outro laboratório
  (FR-035 a FR-038).

**Scale/Scope**:
- 1 migração.
- 3 modelos alterados ou novos.
- Motor: cerca de 10 funções novas e 5 alteradas em `process_engine.py`
  (inclui `_cancel_pending_children`).
- 1 predicado novo em `authorization.py`; `_visible_events` alterado.
- 1 validação nova no bootstrap.
- 2 rotas novas.
- `tasks.py`: 3 pontos alterados.
- 2 schemas alterados e 3 novos.
- Cerca de 6 arquivos de teste novos e o template de teste da Spec 031
  estendido.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` é o template sem preencher, como nas
specs 031 a 035. Os gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Issue #58 e os 2 comentários; RF039, RF040, RF044, RF046; Spec 031 FR-013; Spec 035 FR-001 |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ 17 decisões em Clarifications (duas sessões, a segunda vinda do `/speckit-analyze`); a mudança do item 3 da issue (dependência por laboratório) foi aprovada pelo usuário |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ Só o próprio laboratório age (R8) e vê as próprias tarefas e eventos (R13); dispensa só visível a gestores. Dispensa e reabertura só para gestores. Execuções terminais imutáveis, inclusive no cancelamento (R14). Códigos cegos só lidos. O isolamento do conteúdo das atividades fica com a #59 (FR-032) |
| Mudança cirúrgica, sem abstração preventiva | ✅ Sem rota genérica de conclusão (R7); estado da tarefa inalterado (R5); sem filtro novo em `/tasks` (R11) |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final do `tasks.md` |

**Re-check pós-design**: sem violações. O `/speckit-analyze` apontou um
vazamento de identidade entre laboratórios (C1), a perda de estados
terminais no cancelamento (C2), a regra de conclusão divergente no
data-model (C3) e a dispensa antes do congelamento (C4); os quatro foram
resolvidos com o usuário (Clarifications, R5, R9, R13, R14). Pontos de
atenção:

- **Rotas de formulário em atividade por laboratório** passam a responder
  409 (R7). Hoje não há atividade assim em template, mas a primeira issue
  consumidora que usar formulário precisa estender essas rotas.
- **`_advance_dependent_activities`** muda de comportamento só quando o
  dependente é `per_laboratory`. A suíte atual do motor (triagem, retorno,
  Etapa 2, amostras) é a regressão de FR-016.
- **Índice com `NULLS NOT DISTINCT`**: o downgrade recria o índice antigo.
  Ele só é possível sem execuções por laboratório com mesmo `run_number`, e
  o teste de migração cobre o caso vazio.
- **Trava por processo** (R12): serializa conclusão, dispensa e reabertura do
  mesmo processo. Contenção aceitável para ações humanas.

## Project Structure

### Documentation (this feature)

```text
specs/036-per-laboratory-activity-runs/
├── plan.md              # este arquivo
├── research.md          # R1–R12
├── data-model.md        # colunas, tabela, estados, eventos
├── quickstart.md        # roteiro de validação
├── contracts/
│   └── http-api.md      # rotas novas, campos novos em /tasks
├── checklists/
│   └── requirements.md  # checklist da spec
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── database/models.py         # ActivityInstance (+execution_scope, +is_custody), ActivityRun (+laboratory_id, índice), LaboratoryWaiver (novo)
│   ├── process_engine.py          # validate_execution_scopes, _frozen_laboratory_ids, _activate_laboratory_activity, _unblock_laboratory,
│   │                              # complete_laboratory_run, waive_laboratory, reopen_laboratory_run, _reblock_dependents,
│   │                              # require_laboratory_run_access; alterados: _create_phases_and_activities,
│   │                              # _advance_dependent_activities, _cancel_pending_children (R14), get_current_form_instance, get_current_activity_run
│   ├── authorization.py           # laboratory_run_visibility_clause (R13)
│   └── references.py              # sem mudança (laboratory_refs reaproveitado)
├── bootstrap_process_templates.py # chama validate_execution_scopes
├── routers/
│   ├── laboratory_runs.py         # novo: dispensa e reabertura (prefixo /processes)
│   ├── tasks.py                   # _current_run_clause, _can_act_clause, visibilidade por laboratório, _task_summary/detalhe
│   ├── processes.py               # _visible_events: eventos de laboratório e dispensa (R13)
│   └── forms.py, pre_evaluation.py# mapear ConflictError da atividade por laboratório para 409
├── schemas.py                     # TaskSummary/TaskDetail (+laboratory, +activity_run_status); LaboratoryWaiverCreate/Public, LaboratoryRunReopen*
└── __init__.py                    # registrar o roteador novo (include_router)

migrations/versions/
└── <rev>_per_laboratory_activity_runs.py

tests/
├── factories/sample_factory.py                      # template de teste estendido com a fase de execução
├── unit/core/test_execution_scope_validation.py     # R2
├── integration/database/test_per_laboratory_engine.py   # abertura, cadeia, barreira, dispensa, reabertura, concorrência
├── integration/migrations/test_per_laboratory_migration.py
├── api/routers/test_laboratory_waivers.py
├── api/routers/test_laboratory_reopen.py
├── api/routers/test_tasks_laboratory.py
└── api/routers/test_laboratory_isolation.py         # /tasks, /tasks/{id} e trilha entre laboratórios (R13)
```

**Structure Decision**: backend único, mesma organização das specs 030 e
031. A lógica fica no motor (`process_engine.py`), porque as transições por
laboratório reaproveitam `_activate_activity`, `_complete_activity_run` e
`_advance_dependent_activities`. As rotas novas ficam num roteador próprio,
como `samples.py` e `return_review.py`.

## Complexity Tracking

Sem violações dos gates.
