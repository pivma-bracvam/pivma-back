# Implementation Plan: Semântica BraCVAM e autorização da triagem

**Branch**: `014-bracvam-triage-authorization` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/014-bracvam-triage-authorization/spec.md`

## Summary

Introduzir o perfil de acesso `bracvam` e a permissão `triage.review`, e amarrá-la
às quatro ações de triagem hoje sem RBAC ou presas ao papel errado
(`group_manager`): parecer de campo, decisão de triagem, consulta da pré-avaliação
e feedback por critério. Em paralelo, remover a esteira de avaliação legada da
Spec 010 (engine mock, endpoint `evaluate-ai`, formato de log próprio, campo
`ai_evaluation` na resposta de submissão) — a pré-avaliação da Spec 013 passa a ser
a única. Persistir um snapshot imutável do conteúdo avaliado por execução, com
degradação graciosa para execuções antigas. Fechar a lacuna de teste de
observabilidade do fluxo novo.

Abordagem técnica: uma migração de RBAC no padrão de `8b701d7bfeae` (perfil +
permissões + composições, com downgrade); uma migração para a coluna JSONB
`evaluation_runs.evaluated_content_snapshot`; troca de guardas em
`pre_evaluation.py`/`process_engine.py`; exclusão física dos módulos legados
(`ai/pipeline.py`, `ai/steps/`) e do que os referencia; ajustes de duas demos.

## Technical Context

**Language/Version**: Python >=3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2 / pydantic-settings, Alembic, PostgreSQL + pgvector, structlog. Sem novas dependências.

**Storage**: PostgreSQL. Duas migrações Alembic (RBAC; coluna de snapshot).

**Testing**: pytest + pytest-asyncio, Testcontainers (`pgvector/pgvector:pg17`), factory_boy, padrão AAA. Provider de IA `fake` nos testes.

**Target Platform**: servidor Linux (API) + páginas estáticas em `demos/`.

**Project Type**: web-service (API de domínio) + demos descartáveis.

**Performance Goals**: sem metas novas; a verificação de permissão adiciona 1 consulta RBAC por requisição de triagem (já é o padrão do projeto — `has_permission`).

**Constraints**: Ruff line-length 79, aspas simples, regras I/F/E/W/PL/PT; `migrations/` fora do Ruff. Migrações com teste de upgrade **e** downgrade. Nenhum endpoint novo para demos.

**Scale/Scope**: ~9 perfis de acesso, catálogo de permissões pequeno. Remoção legada toca ~10 arquivos de código + 2 de teste; a feature nova toca ~8 arquivos + ~5 arquivos de teste novos/alterados.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Situação | Observação |
|---|---|---|
| I. Especificação antes da implementação | PASS | `spec.md` aprovado; este `plan.md`; `/speckit-tasks` a seguir. |
| II. Domínio puro, demos descartáveis | PASS | Nenhum endpoint/parâmetro só-para-demo. As demos `submission/` e `ai-pipeline/` são **ajustadas** para não depender do que foi removido; continuam desacopláveis. |
| III. Demonstração como critério de conclusão | PASS | Demos de submissão, triagem e observabilidade validadas contra a API real + seed atualizado (SC-010). Catálogo `demos/index.html` inalterado (4 módulos). |
| IV. Qualidade verificável (NÃO NEGOCIÁVEL) | PASS | `ruff format`/`check`/`pytest` verdes. Testes nos 4 níveis: unit (schemas, `_group_pipeline`), api/routers (autorização de triagem, ausência do endpoint legado, snapshot no payload), integration/database (snapshot imutável), integration/migrations (upgrade+downgrade das 2 migrações). Skills `karpathy-guidelines` e `fastapi-testing-methodology` **não estão instaladas** neste ambiente (lacuna já registrada no CLAUDE.md); os princípios são aplicados manualmente. |
| V. Auditabilidade e rastreabilidade | PASS | Snapshot é append-only por execução (nunca atualizado). Artefatos/eventos legados preservados (FR-016). Migrações reversíveis sem apagar execuções (FR-023). |
| VI. Segurança por padrão | PASS | Permissão reavaliada no banco a cada requisição (FR-008, via `require_permission`/`has_permission`). Guarda de conflito de interesse mantém precedência (FR-007). Rotas de mutação já validam `CurrentUser` + `TrustedOrigin`. Erros não vazam detalhes. |

**Restrições tecnológicas**: migração de modelo (`evaluation_runs`) gera revisão Alembic com nome descritivo + teste up/down. Configuração via `Settings` (nada novo). Sem violação → **Complexity Tracking vazio**.

## Project Structure

### Documentation (this feature)

```text
specs/014-bracvam-triage-authorization/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — decisões D1..D8
├── data-model.md        # Fase 1 — perfil/permissão/composições + coluna snapshot
├── quickstart.md        # Fase 1 — roteiro de validação (cenários A..F)
├── contracts/
│   ├── triage-authorization.md      # rotas × permissão; matriz de acesso
│   ├── pre-evaluation-payload.md     # evaluated_content (snapshot vs derivado)
│   └── removed-endpoints.md          # o que sai da API (Spec 010)
├── checklists/
│   └── requirements.md  # (de /speckit-specify)
└── tasks.md             # /speckit-tasks (não criado aqui)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── authorization.py            # + TRIAGE_REVIEW = 'triage.review'
│   ├── process_engine.py           # save_field_reviews/execute_triage_decision: guarda de permissão;
│   │                               #   remover _run_legacy_field_ai_mock; simplificar o ramo "sem associações"
│   ├── pre_evaluation_service.py   # _ensure_can_read/record_feedback: group_manager+ai_evaluations.read -> triage.review;
│   │                               #   _execute: gravar run.evaluated_content_snapshot;
│   │                               #   get_pre_evaluation: snapshot com fallback para _evaluated_content
│   ├── log_service.py              # remover uso de AIEvaluationVerdict / verdict_synthesis
│   └── database/models.py          # EvaluationRun.evaluated_content_snapshot: Mapped[list | None] (JSONB)
├── routers/
│   ├── triage.py                   # require_permission(TRIAGE_REVIEW) em reviews e decision
│   ├── pre_evaluation.py           # _ensure_can_read/record_feedback: nova permissão
│   └── forms.py                    # remover direct_forms_router + endpoint evaluate-ai + ramo ai_evaluation
├── ai/
│   ├── contracts.py                # remover AIEvaluationVerdict, PipelineContext, StepResult; PipelineExecutionGroup sem `verdict`
│   ├── pipeline.py                 # REMOVER (FormAIPipelineEngine)
│   └── steps/                      # REMOVER (context_extraction, mock_evaluation, verdict_synthesis)
├── schemas.py                      # ActivityCompletionResponse/FormInstanceResponse: remover `ai_evaluation`
└── __init__.py                     # remover include_router(forms.direct_forms_router)

migrations/versions/
├── <rev>_bracvam_profile_triage_permission.py   # perfil + permissão + composições (bracvam, administrator)
└── <rev>_evaluation_run_content_snapshot.py     # coluna JSONB

scripts/seeds/
├── seed_users.py                   # triage_evaluator: perfil 'BraCVAM' em vez de 'Revisor'
└── seed_ai_evaluations.py          # remover _grant_group_manager (contorno)

tests/
├── unit/
│   ├── ai/test_log_grouping.py         # NOVO — _build_pipeline_group sem verdict
│   └── test_ai_pipeline.py             # REMOVER (Spec 010)
├── api/routers/
│   ├── test_triage_authorization.py    # NOVO — matriz de acesso das 4 ações
│   ├── test_triage_decision.py         # ajustar (autenticar com perfil BraCVAM)
│   ├── test_pre_evaluation_*.py        # ajustar guardas
│   └── test_form_submission.py         # ajustar (sem `ai_evaluation` na resposta)
├── integration/
│   ├── database/test_evaluation_run_snapshot.py   # NOVO — snapshot imutável
│   ├── ai/test_run_pre_evaluation.py              # + assert de observabilidade (M4)
│   ├── migrations/test_bracvam_rbac_migration.py  # NOVO — up/down
│   ├── migrations/test_evaluation_run_snapshot_migration.py  # NOVO — up/down
│   └── test_form_ai_evaluation_api.py             # REMOVER (Spec 010)
demos/
├── submission/index.html           # remover ramo `data.ai_evaluation` de renderTransition + renderAiReportBox
└── ai-pipeline/app.js              # remover disparo via evaluate-ai; observar pré-avaliações da demo de submissão
```

**Structure Decision**: projeto single (API em `src/pivma/`, testes em `tests/`, demos em `demos/`, migrações em `migrations/versions/`). Nenhuma pasta nova; a feature adiciona 2 migrações e alguns arquivos de teste, e **remove** o subsistema `ai/pipeline.py` + `ai/steps/`.

## Ordem de execução recomendada

1. **US1 (P1)** — permissão + perfil + migração RBAC + guardas + seeds + testes de autorização. Entregável e testável isolado.
2. **US2 (P2)** — remoção da Spec 010 (código, endpoint, schema, testes legados, demos). Depende só de US1 estar decidida (não bloqueia).
3. **US3 (P3)** — coluna de snapshot + migração + captura no `_execute` + leitura com fallback + testes de imutabilidade.
4. **US4 (P4)** — teste de regressão de observabilidade (encaixa após US2, que remove o formato legado).
5. **Polish** — atualizar Spec 013 (FR-022/L1), `demos/DESIGN.md`, relatório, `README`.

## Post-Design Constitution Re-check

Após Fase 1 (research + data-model + contracts + quickstart): **sem novas
violações**. Os artefatos não introduzem endpoint/parâmetro só-para-demo (II), a
migração de snapshot é reversível sem apagar linhas (V), a autorização é
verificada por requisição e o conflito de interesse mantém precedência (VI), e a
cobertura de teste está mapeada nos 4 níveis (IV). Nenhuma tecnologia nova.
Nenhum `NEEDS CLARIFICATION` restante no Technical Context.

## Complexity Tracking

> Sem violações constitucionais. Seção vazia.
