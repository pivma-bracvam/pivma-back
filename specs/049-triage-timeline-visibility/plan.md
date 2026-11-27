# Implementation Plan: Visibilidade da triagem e cegamento na linha do tempo

**Branch**: `fix/049-triage-timeline-visibility` | **Date**: 2026-11-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/049-triage-timeline-visibility/spec.md`

## Summary

O proponente passa a ver a triagem (issue #81): os cinco templates concedem `view` de `triage_evaluation` a `proponent`, com versão nova, e uma migração de dados estende a concessão às instâncias existentes. A linha do tempo esconde o autor dos eventos de decisão da triagem e omite `FIELD_REVIEWED` para quem não tem `triage.review`. `GET .../form` filtra os pareceres em rascunho (pendência da Spec 046). A linha do tempo trata os convites como eventos de participante e esconde do cargo de revisão cega a identidade do proponente e dos outros avaliadores (issue #84). Nenhuma tabela, coluna ou rota nova; o desenho estende os filtros que já existem em `routers/processes.py` e `routers/forms.py` ([research](research.md)).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy assíncrono, Alembic, Pydantic

**Storage**: PostgreSQL (coluna `activity_instances.view_roles`, `text[]`)

**Testing**: Pytest com testes de API (`tests/api/routers/`), jornadas (`tests/integration/journeys/`) e migração (`tests/integration/migrations/`)

**Target Platform**: serviço web em Linux (Docker)

**Project Type**: web-service (backend)

**Performance Goals**: sem meta nova. A linha do tempo ganha no máximo três consultas por requisição: o acesso de plataforma do usuário, as designações dele no processo e as designações cegas do processo. As duas últimas só rodam para quem não tem acesso de plataforma. `has_process_review_access` já é consultado hoje e passa a ser calculado uma vez só

**Constraints**: o filtro roda antes da paginação (Spec 033, R2); o contrato de resposta não muda de forma, só de conteúdo

**Scale/Scope**: 5 templates, 1 migração de dados, 2 rotas alteradas (`GET /processes/{id}/timeline`, `GET /processes/{id}/activities/{key}/form`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Antes | Depois do desenho |
|---|---|---|
| I. Requisitos e evidência | PASS: spec com CONFIRMADO e INFERÊNCIA; decisões na seção "Visibilidade da triagem e cegamento na linha do tempo (Spec 049)" de `docs/observacoes-e-pendencias.md`, copiadas para Clarifications | PASS: cada escolha de [research](research.md) aponta o FR ou a decisão que atende |
| II. Rastreabilidade e auditoria | PASS: sem modelo novo; leitura não grava evento | PASS: o autor continua gravado em todo evento; só a resposta o omite ([R3](research.md#r3-autor-dos-eventos-da-triagem), [R7](research.md#r7-cegamento-do-autor)). A migração não apaga dado e tem downgrade ([R2](research.md#r2-migração-dos-processos-existentes)) |
| III. Segurança, autorização e sigilo | PASS: a spec fecha dois vazamentos de cegamento e isolamento (FR-007, FR-008) e mantém a escrita da triagem restrita (FR-010) | PASS: as checagens leem o banco a cada requisição (`has_process_review_access`, `can_manage_participants`, `viewer_assignments`); a visão nova não abre rota de escrita nem formulário ([R1](research.md#r1-visão-do-proponente-na-triagem)) |
| IV. IA como apoio, decisão humana | PASS: não toca IA | PASS: não toca IA |
| V. Testes orientados a jornadas | PASS: uma jornada por história | PASS: [quickstart](quickstart.md) lista as jornadas e os testes focados de autorização, isolamento, paginação, cegamento e migração |
| VI. Simples e cirúrgico | PASS: sem rota, tabela ou coluna nova | PASS: dois conjuntos de tipos de evento, uma função de autores ocultos e um filtro de pareceres; reaproveita `ProgressView` e o critério de `submission_run_reviews` ([R5](research.md#r5-pareceres-em-get-form), [R7](research.md#r7-cegamento-do-autor)) |
| VII. Documentação do estado atual | PASS: FR-011 pede o manual | PASS: páginas listadas abaixo |

Sem exceções.

## Project Structure

### Documentation (this feature)

```text
specs/049-triage-timeline-visibility/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── timeline-and-form.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── templates_data/
│   ├── 01_pre_validated_method.yaml      # view de triage_evaluation; version 7
│   ├── 02_scope_extension.yaml           # idem; version 7
│   ├── 03_me_too_validation.yaml         # idem; version 7
│   ├── 04_validated_method_dossier.yaml  # idem; version 9
│   └── 05_test_short_form.yaml           # idem; version 3
├── routers/
│   ├── processes.py   # INVITE_EVENT_TYPES, TRIAGE_AUTHOR_EVENTS, _visible_events, _blind_hidden_authors, get_process_timeline
│   └── forms.py       # get_activity_form: filtro de reviews
migrations/versions/
└── <nova>_triage_evaluation_proponent_view.py

tests/
├── api/routers/
│   ├── test_triage_proponent_view.py     # US1: autor da triagem, FIELD_REVIEWED, 403, paginação (novo)
│   ├── test_timeline_router.py           # US1: regressão da Spec 030 com assign_sponsor
│   ├── test_alerts_task_opened.py        # US1: proponente sem alerta da triagem
│   ├── test_participant_timeline.py      # US3: convites, isolamento por laboratório, paginação
│   ├── test_timeline_blind_review.py     # US4: cegamento do autor (novo)
│   └── test_activity_form_reviews.py     # US2: reviews em rascunho x decididos (novo)
├── integration/
│   ├── database/test_activity_access_columns.py   # asserção da matriz da Fase 1
│   ├── journeys/etapa_1_submissao_triagem/
│   │   ├── test_proponent_triage_view.py           # jornada da US1 (novo)
│   │   ├── test_proponent_reads_decided_reviews.py # jornada da US2 (novo)
│   │   └── test_return_review_via_ai.py            # ajuste: pendências com actionable=true
│   ├── journeys/etapa_2_planejamento_preparacao/
│   │   ├── test_invite_timeline_privacy.py         # jornada da US3 (novo)
│   │   └── test_blind_reviewer_timeline.py         # jornada da US4 (novo)
│   └── migrations/test_triage_proponent_view_migration.py   # migração (novo)

manual/
├── explicacao/autorizacao.md          # visibilidade da linha do tempo por cargo
├── referencia/eventos.md              # quem vê cada grupo de eventos e o autor
├── referencia/perfis-permissoes-cargos.md   # proponente vê a triagem
├── guias/responder-ao-retorno.md      # pareceres só depois da decisão
└── guias/conduzir-a-triagem.md        # o proponente acompanha a triagem sem ver o autor
```

**Entrega**: a PR aponta para `develop`, que recebeu a PR #83 em `9f06d31`.

**Structure Decision**: projeto único em `src/pivma/`. A mudança fica nos routers que já filtram a linha do tempo e o formulário, sem módulo novo no core. As páginas do manual serão confirmadas no `/speckit-tasks` com uma busca pelos trechos afetados.

## Complexity Tracking

Sem violações.
