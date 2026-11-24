# Implementation Plan: Acompanhamento do Patrocinador

**Branch**: `feat/047-sponsor-tracking` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/048-sponsor-tracking/spec.md`

## Summary

Um router novo, `sponsor_tracking`, responde a duas rotas de leitura.
`GET /sponsor-tracking/processes` lista os processos em que o usuário tem
designação ativa de Patrocinador, com a data da designação, a fase atual e a
quantidade de atividades em andamento.
`GET /sponsor-tracking/processes/{process_id}` devolve o cabeçalho, as pessoas
de cada cargo (inclusive o proponente), a fase atual e as execuções
`IN_PROGRESS`, uma por laboratório na Fase 3. Quem não é Patrocinador do
processo recebe `404`, salvo Admin e BraCVAM. A lista e o detalhe calculam a
fase atual pela mesma função privada.

As consultas reaproveitam `process_cargos_scope` e `effective_assignment_clause`,
as mesmas regras da autorização. As rotas de atividade não mudam, e nenhum
schema novo referencia dados internos do estudo.

A entrega não cria tabela, migração nem permissão.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2

**Storage**: PostgreSQL 17, sem mudança de esquema

**Testing**: Pytest, Testcontainers, `TestClient` com `authenticate`, jornadas a partir de `bootstrap_fresh_deploy`

**Target Platform**: serviço Linux em contêiner

**Project Type**: web service

**Performance Goals**: lista com até três consultas por página (total, página com a data da designação, execuções em andamento dos processos `OPEN` da página), sem consulta por item; detalhe com até seis (processo, designação, perfil de plataforma quando não for Patrocinador, cargos, laboratórios, execuções)

**Constraints**: só leitura; contratos atuais intactos; resposta com `extra='forbid'`

**Scale/Scope**: poucos processos por Patrocinador; até dezenas de designações e execuções por processo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Antes | Depois do desenho |
|---|---|---|
| I. Requisitos e evidência | PASS: spec com CONFIRMADO e INFERÊNCIA; decisões em `docs/observacoes-e-pendencias.md`, seção "Acompanhamento do patrocinador", copiadas para Clarifications | PASS: cada escolha de [research](research.md) aponta o FR ou a decisão que atende |
| II. Rastreabilidade e auditoria | PASS: sem modelo novo; leitura não é ação de negócio (FR-010) | PASS: nenhuma rota grava evento ([R8](research.md#r8-auditoria)); as jornadas citam a história que provam |
| III. Segurança, autorização e sigilo | PASS: `404` a quem não é Patrocinador (FR-009); sem e-mail; dados internos fora (FR-007) | PASS: acesso calculado no banco a cada requisição ([R4](research.md#r4-quem-consulta-o-detalhe)); schemas sem campo de substância, código, formulário ou resultado ([R7](research.md#r7-o-que-fica-fora-da-resposta)); a execução de um laboratório aparece só como nome, fase e data, sem conteúdo nem acesso |
| IV. IA como apoio, decisão humana | PASS: não toca IA | PASS: não toca IA |
| V. Testes orientados a jornadas | PASS: uma jornada por história | PASS: [quickstart](quickstart.md) lista a jornada e os testes focados de autorização, isolamento, paginação, ordem e regressão das rotas de amostras |
| VI. Simples e cirúrgico | PASS: rotas novas aprovadas na spec; rotas atuais sem mudança | PASS: um router, seis schemas e a classe do envelope da lista. O router usa `process_cargos_scope`, `effective_assignment_clause` e `laboratory_refs`. A consulta paginada traz o processo e a data da designação juntos e usa `build_pagination` para montar o envelope ([R1](research.md#r1-rota-própria-ou-extensão-de-processes), [R3](research.md#r3-cartão-da-lista)) |
| VII. Documentação do estado atual | PASS: FR-011 pede o manual | PASS: guia novo e páginas de referência listados abaixo |

Sem exceções.

## Project Structure

### Documentation (this feature)

```text
specs/048-sponsor-tracking/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── sponsor-tracking.md
├── checklists/
│   └── requirements.md
└── tasks.md             # gerado por /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── __init__.py                       # include_router(sponsor_tracking.router)
├── schemas.py                        # SponsoredProcessSummary, SponsoredProcessListResponse,
│                                     # TrackingPerson, TrackingRole, TrackingPhase,
│                                     # TrackingActivity, SponsorTrackingDetail
└── routers/sponsor_tracking.py       # as duas rotas e as consultas

tests/
├── api/routers/test_sponsor_tracking.py           # lista, detalhe, fase, atividades, estados
├── api/routers/test_sponsor_tracking_security.py  # 404 por cargo, Admin/BraCVAM, sem dado interno, rotas de amostras inalteradas
└── integration/journeys/etapa_2_planejamento_preparacao/
    └── test_sponsor_tracking_journey.py           # US1, US2 e US3

manual/
├── guias/acompanhar-como-patrocinador.md   # novo; entra no nav do mkdocs.yml
├── referencia/perfis-permissoes-cargos.md  # observação do cargo sponsor
├── referencia/listagens-e-referencias.md   # a lista nova no envelope padrão
└── explicacao/escopo.md                    # o acompanhamento entregue
```

`manual/referencia/rotas.md` é gerado do OpenAPI no build e não precisa de
edição.

**Structure Decision**: serviço único, nas pastas atuais. O único módulo novo
é o router, porque as rotas têm prefixo próprio
([R1](research.md#r1-rota-própria-ou-extensão-de-processes)).
