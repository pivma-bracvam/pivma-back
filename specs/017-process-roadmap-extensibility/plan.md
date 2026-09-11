# Implementation Plan: Roteiro Dinâmico e Extensibilidade de Atividades para Fases Futuras

**Branch**: `017-process-roadmap-extensibility` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-process-roadmap-extensibility/spec.md`

## Summary

Adicionar uma classificação explícita (`activity_type`) a `ActivityInstance`, permitir
que atividades declaradas em YAML sem `form_template_key` sejam instanciadas e avancem
sem gerar `FormInstance`, e generalizar minimamente o avanço de dependências (hoje
hardcoded só para `triage_evaluation`) para desbloquear a próxima atividade quando sua
dependência é satisfeita. A validação de ponta a ponta é feita publicando a **versão 2**
de `validated_method_dossier` (template4, Spec 011) com uma Fase 2 de exemplo contendo uma
atividade não-formulário, exposta em uma página de demonstração dedicada que consome
apenas endpoints já existentes (`GET /processes/templates/{key}`, `POST /processes`,
`GET /processes/{id}`, `GET /tasks`, `POST /processes/{id}/triage/decision`), sem nenhum
endpoint novo.

## Technical Context

**Language/Version**: Python 3.14 (FastAPI, SQLAlchemy async)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x (asyncio), Alembic, PyYAML, psycopg3

**Storage**: PostgreSQL (via Alembic migration para a nova coluna `activity_type`)

**Testing**: pytest (Testcontainers `pgvector/pgvector:pg17`), estrutura em níveis
(`tests/unit`, `tests/api/routers`, `tests/integration/database`,
`tests/integration/migrations`), factories em `tests/factories/`

**Target Platform**: Linux server (API HTTP), demonstração em página HTML estática

**Project Type**: web-service (API) + demo HTML estático desacoplado em `demos/`

**Performance Goals**: N/A (sem novo requisito de performance; volume idêntico ao já
suportado pela Spec 004/011)

**Constraints**: retrocompatibilidade total com os 5 métodos oficiais e com todas as
instâncias já criadas (Spec 004 SC-002); nenhuma alteração de contrato para atividades
que permanecem do tipo formulário; nenhum endpoint criado só para viabilizar a demo
(Constituição, Princípio II)

**Scale/Scope**: uma coluna nova, ~3 funções pequenas no motor de processos, uma nova
versão de um template YAML já existente, uma página de demo e um seed dedicado

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Especificação Antes da Implementação**: ✅ `spec.md` escrito e revisado nesta
  sessão; este `plan.md` precede qualquer alteração em `src/`; `tasks.md` virá em seguida.
- **II. Domínio Puro na API, Demos Descartáveis**: ✅ nenhum endpoint novo é criado; a
  página de demo consome exclusivamente contratos já existentes; o seed vive em
  `scripts/seeds/` e a página em `demos/`, ambos descartáveis sem afetar `src/`.
- **III. Demonstração como Critério de Conclusão**: ✅ a spec só se considera concluída
  com a página de demo + seed funcionais, batendo na API real (User Story 3).
- **IV. Qualidade Verificável (NÃO NEGOCIÁVEL)**: ✅ `ruff format`, `ruff check` e
  `pytest` continuam obrigatórios; testes novos seguem a skill
  `fastapi-testing-methodology` e a estrutura em níveis já estabelecida.
- **V. Auditabilidade e Rastreabilidade**: ✅ `ActivityInstance` já herda `AuditMixin`; a
  nova coluna não quebra isso; o desbloqueio da atividade de exemplo continua gerando
  `AuditEvent`, consistente com a trilha já exigida pela Spec 004 (FR-011).
- **VI. Segurança por Padrão**: ✅ nenhuma rota de mutação nova; as rotas reaproveitadas já
  validam `CurrentUser`/`TrustedOrigin` e RBAC conforme especificado nas Specs 003/006/009/014.

**Desvio consciente registrado (não é violação, é decisão explícita da Spec 017)**: a
Fase 2 de exemplo é publicada em uma nova versão de um método **oficial ativo**
(`validated_method_dossier`), não em um template isolado. Isso foi avaliado e decidido
com o usuário (ver Spec 017, seção "Decisão registrada nesta revisão"); a mitigação é a
imutabilidade de versão da Spec 004 (FR-001/SC-002), não o isolamento do template.

Nenhum gate bloqueado. Prosseguindo para Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/017-process-roadmap-extensibility/
├── plan.md              # Este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/pivma/
├── core/
│   ├── database/
│   │   └── models.py                 # + ActivityInstance.activity_type
│   └── process_engine.py             # + suporte a atividade sem formulário
│                                      # + generalização mínima de desbloqueio
│                                      #   por dependência (além de triage_evaluation)
├── templates_data/
│   └── 04_validated_method_dossier.yaml  # + version: 2, + phase_2_planning_preview
└── schemas.py                        # + activity_type nos schemas que já expõem
                                       #   atividade (TaskSummary/TaskDetail)

migrations/versions/
└── <novo>_activity_instance_activity_type.py

tests/
├── unit/core/                        # activity_type default/serialização
├── api/routers/                      # instanciar + avançar atividade não-formulário
└── integration/database/             # constraint/coluna + retrocompatibilidade

demos/
└── roadmap/
    └── index.html                    # nova página de demo

scripts/seeds/
└── seed_roadmap_demo.py              # seed dedicado desta demo
```

**Structure Decision**: projeto único (API Python + demos HTML estáticos já
estabelecidos pelo repositório). Sem novo serviço, sem novo diretório de topo — a
extensão vive inteiramente dentro da estrutura já existente (`core/`, `templates_data/`,
`migrations/`, `demos/`, `scripts/seeds/`).

## Complexity Tracking

*Sem violações de constituição a justificar. Tabela omitida.*

## Post-Design Constitution Check

Reavaliado após `research.md`, `data-model.md`, `contracts/` e `quickstart.md`: nenhum
gate novo foi violado pelo desenho. Confirmações adicionais que o desenho tornou
explícitas:

- Nenhum endpoint HTTP novo foi desenhado (ver `contracts/roadmap-composition.md`) —
  reforça o Princípio II.
- A migração é aditiva e teoricamente reversível (`DROP COLUMN` no downgrade), atendendo
  ao padrão de `tests/integration/migrations/` (upgrade/downgrade) exigido pelo
  Princípio IV.
- A generalização do desbloqueio de dependência (`data-model.md`, seção 4) reutiliza
  `ActivityDependency` já modelado pela Spec 004 em vez de introduzir uma tabela nova —
  não há novo modelo relacional a decorar com `AuditMixin` (Princípio V já satisfeito,
  pois `ActivityInstance` já herda `AuditMixin`).

Gate final: **aprovado**, sem itens em `Complexity Tracking`.
