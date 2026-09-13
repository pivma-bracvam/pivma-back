# Implementation Plan: Exclusão, Cancelamento e Arquivamento de Processos

**Branch**: `022-process-retirement` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-process-retirement/spec.md`

## Summary

Implementar contratos REST separados para `DELETE /processes/{id}`, `PATCH /processes/{id}/withdrawal`, `PATCH /processes/{id}/cancellation` e `PATCH /processes/{id}/archive`, sem justificativa no ciclo de vida. O serviço distinguirá rascunho inicial pela ausência do evento `SUBMISSION_SUBMITTED`, removerá fisicamente apenas seu agregado e anexos, permitirá desistência do proponente após `REVISION_REQUESTED`, cancelará processos submetidos e arquivará somente processos terminais. A autorização de cancelamento e arquivamento usa `triage.review`; a exclusão física é exclusiva do proponente efetivo.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy async 2, Alembic

**Storage**: PostgreSQL e diretório local de anexos

**Testing**: pytest, pytest-asyncio, factory_boy, testcontainers; Ruff para lint

**Target Platform**: Serviço web FastAPI em Linux; demonstrações estáticas servidas pelo projeto e conectadas à API local

**Project Type**: Serviço web monolítico, com páginas HTML/JavaScript desacopladas em `demos/`

**Performance Goals**: Uma ação de ciclo de vida atualiza somente o processo e as entidades subordinadas afetadas em uma transação. A exclusão de rascunho também remove seu diretório de anexos. Listagens operacionais mantêm a paginação atual e não consultam arquivados por padrão.

**Constraints**: Reutilizar RBAC e auditoria existentes; permitir exclusão física somente para rascunho nunca submetido; não introduzir restauração, novos perfis, endpoints de apoio à demo ou uma máquina de estados paralela. Toda mutação e conclusão assíncrona deve respeitar `CANCELLED` e `ARCHIVED`.

**Scale/Scope**: Uma instância de processo por comando; quatro operações de ciclo de vida; router de processos, motor de processo, pré-avaliação assíncrona, schemas, testes, seed e uma demo.

## Constitution Check

**Pré-design: APROVADO**

- Requisitos e decisão de domínio são classificados na spec: a exclusão física de rascunho, a desistência, o cancelamento e o arquivamento foram confirmados pelo responsável da demanda.
- Cancelamento, desistência e arquivamento preservam ator, estados e momento em `AuditEvent`; a exclusão física remove somente o agregado que nunca entrou no pipeline.
- A autorização permanece obrigatória no backend: proponente efetivo apenas para o próprio rascunho ou revisão devolvida; `triage.review` para cancelar e arquivar. `available_actions` é apenas uma projeção para a interface.
- A mudança fica restrita ao ciclo de vida de processo e às guardas necessárias para impedir mutações posteriores e conclusão tardia de IA.
- Testes de API, domínio e integração assíncrona, além de demo e seed contra a API real, fornecem evidência verificável.

**Pós-design: APROVADO**

O desenho usa status e colunas de auditoria já existentes para cancelamento, desistência e arquivamento, sem nova tabela ou permissão. A exclusão de rascunho remove o agregado e o diretório local de anexos. Os endpoints separados tornam a intenção inequívoca, e as guardas ficam no domínio e no worker, não somente na interface HTTP.

## Project Structure

### Documentation (this feature)

```text
specs/022-process-retirement/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── process-lifecycle.openapi.yaml
└── tasks.md                     # criado por $speckit-tasks
```

### Source Code

```text
src/pivma/
├── core/
│   ├── authorization.py          # autorização reutilizada
│   ├── database/models.py        # entidades persistidas existentes
│   ├── process_engine.py         # comando, remoção física e guardas de ciclo de vida
│   ├── attachment_service.py     # remoção do diretório de anexos do rascunho
│   └── pre_evaluation_service.py # proteção contra conclusão tardia
├── routers/
│   └── processes.py              # contrato HTTP e consulta histórica
└── schemas.py                    # request/response de ciclo de vida

tests/
├── api/routers/                  # contrato, autorização, listagem e fluxos
├── unit/core/                    # regras puras e de domínio
├── integration/ai/               # execução tardia de pré-avaliação
└── integration/database/         # exclusão física e concorrência

scripts/seeds/
└── seed_process_retirement.py

demos/
├── process-retirement/
│   └── index.html
└── index.html
```

**Structure Decision**: O backend existente concentra regras em `core/process_engine.py` e os contratos HTTP em `routers/` e `schemas.py`. A demonstração permanece descartável em `demos/` e usa somente os contratos públicos descritos nesta feature.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional requer justificativa.
