# Implementation Plan: Migração das listagens para o padrão e referências resumidas

**Branch**: `feat/033-listing-migration-refs` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/033-listing-migration-refs/spec.md`

## Summary

As 19 listagens restantes passam ao envelope da Spec 032, na forma sem contagens `ListPage[Item, Filters]`: `data`, `pagination` por página, `filters_applied` e `sort`. `ListEnvelope` passa a estender `ListPage`, sem mudar o JSON de `GET /tasks`.

A paginação acontece no banco quando a listagem é uma consulta só, e em memória quando o filtro de acesso roda em Python (convites, linha do tempo, versões de submissão, afiliações próprias). Assim os totais continuam corretos para cada perfil (research R2). A ordem atual vira a padrão, com desempate por `id` (R4).

Identificadores soltos e campos achatados viram as referências `UserRef`, `ProfileRef`, `InstitutionRef`, `LaboratoryRef` e `TemplateRef`. `ProcessRef` vem da Spec 032. Pessoas e laboratórios são carregados em lote por um módulo novo, `core/references.py` (R6, R7). As duas consultas de logs administrativos saem do OpenAPI (R8).

Sem tabela nova, sem migração e sem dependência nova.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2

**Storage**: PostgreSQL 17; sem mudança de esquema

**Testing**: Pytest + pytest-asyncio, testcontainers, factory_boy, `TestClient`; metodologia em `.agents/skills/fastapi-testing-methodology/`

**Target Platform**: Linux server (API HTTP)

**Project Type**: web-service (backend)

**Performance Goals**: por página, uma consulta de itens, uma de total e no máximo uma por tipo de referência (sem N+1). Etiquetas geram QR só para os itens da página.

**Constraints**:
- Mesma visibilidade e os mesmos totais por perfil de antes (FR-006, SC-004).
- Nenhum e-mail em referência de pessoa (SC-003).
- Nenhum conteúdo das amostras além do atual nas etiquetas.
- Quebra de contrato aceita, registrada no changelog único.
- Logs administrativos fora da documentação e fora do changelog.

**Scale/Scope**:
- 7 roteadores alterados: `users`, `rbac`, `institutional`, `processes`, `process_participants`, `ai_evaluations` e `samples`. Mais `admin_logs` (só `include_in_schema`) e `invites` (aceite com referências).
- `schemas.py`: `ListPage`, `NoFilters`, 3 modelos de filtros, 5 referências, cerca de 19 especializações nomeadas; saem 11 schemas antigos.
- `core/listing.py` com dois helpers novos e `core/references.py` novo.
- Serviços tocados: `evaluation_service` (paginação e total), `sample_service` (etiquetas paginadas) e `invite_service` (referências).
- Cerca de 40 arquivos de teste ajustados, mais os testes novos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` ainda é o template sem preencher. Os gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Alinhamento de 2026-09-27 (padronização 032–034); decisões em Clarifications, incluindo linha do tempo, amostras e logs |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ Nenhum marcador aberto |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ Nenhuma regra de acesso muda. Onde o filtro de acesso roda em Python, a paginação vem depois dele (R2). Auditoria continua como identificador. Etiquetas mantêm o conteúdo cego |
| Mudança cirúrgica, sem abstração preventiva | ✅ `ListPage` e os helpers de paginação e de referências servem às 19 rotas desta spec. Os filtros de acesso em Python não são reescritos (R2) |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final do `tasks.md` |

**Re-check pós-design**: sem violações. Pontos de atenção:

- **Escopo largo:** 19 rotas e cerca de 40 arquivos de teste. O `tasks.md` deve agrupar por domínio (catálogo/RBAC, processos, participantes, IA, amostras) para dar pontos de verificação intermediários.
- **Linha do tempo e convites:** continuam carregando tudo antes de paginar, como hoje. Quando o volume justificar, a solução é levar esses filtros para SQL numa spec própria.
- **Ordem nova em templates:** hoje a lista não tem ordem definida e passa a ser por nome.
- **Alterações do RBAC e do catálogo:** o `422` de paginação inválida muda de corpo (`'Invalid pagination'` → erro de validação padrão). A Spec 034 padroniza isso de qualquer forma.

## Project Structure

### Documentation (this feature)

```text
specs/033-listing-migration-refs/
├── plan.md
├── research.md
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
│   ├── listing.py           # + PageQuery, PerPageQuery, paginate_query, paginate_items (R2, R3)
│   ├── references.py        # novo: user_refs, laboratory_refs em lote (R6)
│   ├── evaluation_service.py # list_definitions devolve total; desempate por id
│   ├── sample_service.py    # list_labels paginada; QR só na página
│   └── invite_service.py    # InvitePublic com referências
├── routers/
│   ├── users.py             # GET /users
│   ├── rbac.py              # permissões, perfis, alterações
│   ├── institutional.py     # instituições, laboratórios, afiliações, alterações
│   ├── processes.py         # templates, processos, versões, linha do tempo; ProcessInstanceDetail.template
│   ├── process_participants.py # participantes, histórico, convites
│   ├── invites.py           # aceite devolve InvitePublic com referências
│   ├── ai_evaluations.py    # avaliações e referências de IA
│   ├── samples.py           # etiquetas
│   └── admin_logs.py        # include_in_schema=False
└── schemas.py               # ListPage, NoFilters, filtros, referências, especializações; remoção dos antigos

tests/
├── unit/core/test_listing.py               # + paginate_items
├── integration/database/test_references.py # carregamento em lote, desativados, sem e-mail
├── api/routers/test_listing_contract.py    # envelope e paginação por listagem (parametrizado)
├── api/routers/test_references_openapi.py  # descrições das referências; logs fora do OpenAPI
└── (≈40 arquivos existentes ajustados)
```

**Structure Decision**: backend único. A paginação fica nos roteadores, como na Spec 032. Só o que é repetido em várias rotas vai para `core`: paginação e carregamento de referências.

## Complexity Tracking

Sem violações a justificar.
