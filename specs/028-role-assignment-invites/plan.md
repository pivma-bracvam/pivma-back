# Implementation Plan: Atribuição de Cargo por Convite com Link Compartilhável

**Branch**: `028-role-assignment-invites` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/028-role-assignment-invites/spec.md`

## Summary

Preencher os 8 papéis contextuais obrigatórios da Etapa 2 (Patrocinador, Grupo Gestor,
Grupo de Seleção de Amostras, Laboratório Líder, Laboratórios Participantes, Estatístico,
Colaboradores/Observadores, Especialistas ADHOC) como etapas próprias do roteiro do
processo, preenchíveis por designação direta (reaproveitando o mecanismo de `Assignment`
da Spec 006 sem alteração de regra) ou por um convite que gera um link único, sempre
associado a um e-mail, com expiração de 1h parametrizada por ambiente. A abordagem técnica
é deliberadamente aditiva: um novo `activity_type` ("role_assignment") no roteiro (Spec
017), uma tabela nova para o convite, uma função de autorização por papel que envolve as
três já existentes (`can_manage_participants`, `is_effective_group_manager`,
`is_active_effective_proponent`), e o fechamento automático da etapa reaproveitando o
helper único de conclusão já extraído pela Spec 026 — sem endpoint “concluir atividade”
dedicado e sem tocar no fluxo de cadastro/login (Spec 001/002).

## Technical Context

**Language/Version**: Python 3.14 (`pyproject.toml: requires-python = ">=3.14,<4.0"`)

**Primary Dependencies**: FastAPI 0.141 (`fastapi[standard]`), SQLAlchemy 2.0 async +
`psycopg[binary]` (Postgres), Alembic 1.19 (migrações DDL), Pydantic v2 / `pydantic-settings`
(schemas e `Settings`), `PyJWT` (sessão), `argon2-cffi` (hash de senha — não usado por esta
feature; o token de convite usa `hashlib.sha256`, ver `research.md`), `pyyaml` (templates
declarativos).

**Storage**: PostgreSQL via SQLAlchemy async. Uma tabela nova (`role_assignment_invites`);
nenhuma alteração de schema em `assignments`, `activity_instances` ou `tasks` — o novo tipo
de etapa reaproveita a coluna `activity_type` já existente (Spec 017) e um campo novo
opcional no YAML do template (`target_role_key`), sem migração.

**Testing**: `pytest` + `pytest-asyncio` + `factory-boy` + `httpx2`, seguindo a metodologia
já documentada na skill `fastapi-testing-methodology` e o padrão de
`tests/api/routers/test_participant_router.py` (Spec 006) como referência mais próxima.

**Target Platform**: Linux server, container Docker (backend-only; o frontend é um
repositório separado — esta feature só expõe contrato de API).

**Project Type**: Web service (API REST assíncrona) — projeto único (`src/pivma/`), sem
split frontend/backend neste repositório.

**Performance Goals**: Sem meta numérica nova além das já existentes na plataforma; os
critérios de sucesso da spec (SC-002/SC-006) são de UX (< 1 min para gerar convite, < 30s
para reenviar), não de throughput.

**Constraints**: Preservar os contratos e o comportamento já aprovados das Specs
001/002/006/017/018/023/026 (SC-008 da spec); migrações Alembic estritamente DDL, sem dados
de catálogo (pilar "Separação Rígida entre DDL e Catálogo", `docs/index.md`); nenhum envio
automatizado de e-mail nesta entrega (FR-006).

**Scale/Scope**: Mesma escala do restante da plataforma — dezenas de processos simultâneos,
até poucas dezenas de convites por processo; sem caracterização de escala nova.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` neste repositório é o template não preenchido do Spec
Kit (placeholders `[PRINCIPLE_1_NAME]` etc.) — não há uma constituição ratificada para
carregar. Na ausência dela, o gate desta feature usa os princípios que **já governam** o
código real do projeto, confirmados por leitura direta e reforçados por specs anteriores
(006/017/018/025/026):

| Gate | Critério | Avaliação |
|---|---|---|
| **G1 — Reaproveitar, não paralelizar** | Nenhuma feature cria um segundo mecanismo para um efeito que já existe. | PASS: convite aceito grava `Assignment` pelo mesmo caminho de designação direta (Spec 006); fechamento de etapa reaproveita `_complete_activity_run`/`_advance_dependent_activities` (Spec 026), sem endpoint "concluir atividade" novo. |
| **G2 — DDL puro vs. catálogo** (`docs/index.md`, pilar 2) | Migrações Alembic só alteram estrutura; conteúdo de catálogo (templates, papéis por atividade) é provisionado fora da migração. | PASS: única migração desta feature cria a tabela `role_assignment_invites` (DDL puro); as 8 atividades entram via YAML em `templates_data/`, carregado no boot, como toda atividade de template já é (Spec 011/017). |
| **G3 — Vocabulário único de cargo** (Spec 018, decisão D5) | Não introduzir um segundo enum de papel paralelo a `ParticipantRole`/`ACTIVITY_CARGOS`. | PASS: os 8 papéis já são (ou passam a ser, via Issue #41) valores de `ParticipantRole`; a autorização por atividade usa o `ActivityCargo` já existente (`proponent`/`group_manager`/`admin`/`bracvam`) sem novo valor. |
| **G4 — Autorização decidida no backend** (`docs/index.md`, pilar 3) | Toda regra de quem pode agir vive em `core/authorization.py`; roteadores só chamam. | PASS: a matriz de autorização por papel (FR-001/002/003) é uma função pura nova composta a partir de três já existentes; nenhuma decisão de autorização acontece no roteador. |
| **G5 — Auditoria imutável para toda ação concluída** (Spec 006 FR-024, RF034) | Toda ação de estado (criar/revogar/aceitar) grava `AuditEvent`. | PASS: convite reaproveita `AuditEvent` com `event_type` novo por ação (ver `data-model.md`); nenhuma tabela de log paralela. |

Nenhuma violação a justificar — **Complexity Tracking** fica vazia.

**Re-check pós-design (depois de `research.md`/`data-model.md`/`contracts/`)**: todos os 5
gates continuam PASS sem ajuste. Nenhum artefato de Fase 0/1 introduziu um mecanismo
paralelo (R4 confirma reaproveito do helper único de conclusão), uma migração de dados
(a única tabela nova é DDL puro; as 8 atividades entram por YAML, não por migração), um
segundo vocabulário de papel (o contrato usa o mesmo `ParticipantRole`), uma decisão de
autorização fora de `core/authorization.py` (R3), ou uma ação sem `AuditEvent`
correspondente (seção 3 do `data-model.md` cobre as 4 ações que produzem estado).

## Project Structure

### Documentation (this feature)

```text
specs/028-role-assignment-invites/
├── plan.md              # Este arquivo
├── research.md           # Fase 0
├── data-model.md          # Fase 1
├── quickstart.md          # Fase 1
├── contracts/
│   └── invites.openapi.yaml
└── tasks.md              # Fase 2 (/speckit-tasks — não criado aqui)
```

### Source Code (repository root)

Projeto único (`src/pivma/`), padrão já estabelecido pelas 27 specs anteriores — nenhuma
estrutura nova, só arquivos/módulos novos dentro da árvore existente:

```text
src/pivma/
├── core/
│   ├── database/models.py         # + RoleAssignmentInvite (nova classe mapeada)
│   ├── authorization.py           # + can_manage_role_assignment(), + PROPONENT_MANAGEABLE_ROLE_KEYS
│   ├── process_engine.py          # + _maybe_close_role_assignment_activity() (usa helpers já existentes da Spec 026)
│   ├── invite_service.py          # NOVO: criar/reenviar/revogar/aceitar convite (token, expiração, e-mail match)
│   └── settings.py                # + INVITE_EXPIRATION_HOURS
├── routers/
│   ├── process_participants.py    # + rotas de convite sob /processes/{id}/participants/invites
│   │                               #   (create_participant existente ganha a chamada ao helper de fechamento de etapa)
│   └── invites.py                 # NOVO: GET /invites/{token}, POST /invites/{token}/accept (fora do prefixo /processes)
├── schemas.py                      # + InviteCreate/InvitePublic/InviteAcceptResponse, + 'role_assignment' em ActivityType
└── templates_data/
    └── 04_validated_method_dossier.yaml   # Fase 2 ganha as 8 atividades role_assignment
                                            # (ou template próprio da Etapa 2 — decisão de conteúdo, ver data-model.md)

migrations/versions/
└── <hash>_role_assignment_invites.py      # DDL puro: cria a tabela nova

tests/
├── unit/core/                     # can_manage_role_assignment, fechamento de etapa, expiração
├── integration/database/          # constraint única de convite pendente por (processo, papel, e-mail)
└── api/routers/
    ├── test_participant_router.py # regressão Spec 006 (SC-008) + designação direta fechando etapa
    └── test_invites_router.py     # NOVO: ciclo completo de convite

scripts/seeds/                      # seed a estender (citado na Issue #23) com processo em Planejamento
```

**Structure Decision**: projeto único (Option 1 do template, adaptado aos diretórios reais
acima) — não há frontend neste repositório e a feature não introduz um segundo serviço;
todo o trabalho é módulo novo ou extensão de módulo existente dentro de `src/pivma/`.

## Complexity Tracking

*Vazio — nenhuma violação do Constitution Check acima a justificar.*
