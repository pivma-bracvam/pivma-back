# Implementation Plan: Template de coleta de dados

**Branch**: `feat/041-collection-template` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/041-collection-template/spec.md`

## Summary

Cria o catálogo global de templates de coleta (issue #26):

- Duas tabelas novas com `AuditMixin`: o template e as suas colunas.
- CRUD sob a permissão nova `collection_templates.manage`, sem exclusão do
  template.
- Arquivo-modelo só com o cabeçalho, em CSV (UTF-8 com BOM, `;`) e em
  `.xlsx` (`openpyxl`).
- Vínculo opcional na criação do processo, restrito a quem tem a permissão.
- Travamento estrutural calculado por consulta: o template trava quando a
  definição das amostras de um processo vinculado conclui.

A concorrência entre a alteração estrutural e a conclusão das amostras se
resolve com uma trava na linha do template, tomada pelas duas operações
(research R4).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2,
Alembic; nova: `openpyxl (>=3.1.5,<4.0.0)` (research R8)

**Storage**: PostgreSQL 17. Duas tabelas novas e uma coluna em
`process_instances`. O arquivo-modelo é gerado em memória, sem disco.

**Testing**: pytest, pytest-asyncio, Testcontainers, factory-boy; `openpyxl`
também lê o `.xlsx` nos testes

**Target Platform**: servidor Linux (Docker)

**Project Type**: web-service (backend)

**Performance Goals**: catálogo com dezenas de templates e colunas; a
listagem faz uma consulta de travamento por página

**Constraints**: nenhuma alteração estrutural depois da conclusão das
amostras, mesmo com operações simultâneas (FR-019); erros no formato da
Spec 034; listagem no envelope das Specs 032/033

**Scale/Scope**: 8 rotas novas; 3 rotas existentes ganham um campo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
| --- | --- |
| I. Requisitos e evidência | PASS. Fontes: issue #26 e as decisões de 2026-10-09 em `docs/observacoes-e-pendencias.md`, copiadas em Clarifications. As três lacunas foram perguntadas ao usuário antes do plano. O protótipo não é usado. |
| II. Rastreabilidade e auditoria | PASS. As duas tabelas usam `AuditMixin`, e a exclusão de coluna é lógica. A criação do processo grava o vínculo no `PROCESS_CREATED`. O catálogo de coleta não é o institucional, então dispensa histórico próprio (research R12). |
| III. Segurança, autorização e sigilo | PASS. Toda rota checa a permissão no banco a cada requisição. As escritas do catálogo e as seis de `routers/processes.py` usam `CurrentUser` e `TrustedOrigin` (R11). Na criação do processo, a permissão é checada antes da existência do template (R10). Os erros não repetem valores. O catálogo não guarda nem expõe dado cego. |
| IV. IA como apoio | N/A. Sem IA. |
| V. Testes orientados a jornadas | PASS. Uma jornada por história no `tasks.md`, mais testes focados de validação, autorização, travamento, concorrência, paginação e migração. |
| VI. Mudanças simples e cirúrgicas | PASS. Um serviço e um router novos. As mudanças em código existente se limitam a: um parâmetro opcional em `instantiate_process`, um campo em dois esquemas, uma trava em `complete_sample_definition` e a permissão no bootstrap. Nada de tabela de histórico, flag de travamento ou reordenação. |
| VII. Documentação | PASS. Manual atualizado no mesmo PR (ver a estrutura abaixo). |

Re-check pós-design: PASS, sem exceções. Sem entradas em Complexity
Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/041-collection-template/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/http-api.md
├── checklists/requirements.md
└── tasks.md              # /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml, poetry.lock, uv.lock     # openpyxl
src/pivma/
├── core/
│   ├── authorization.py                 # COLLECTION_TEMPLATES_MANAGE
│   ├── database/models.py               # CollectionTemplate, CollectionTemplateColumn;
│   │                                    # ProcessInstance.collection_template_id
│   ├── collection_template_service.py   # novo: regras, travamento, arquivo-modelo
│   ├── process_engine.py                # instantiate_process(collection_template_id)
│   └── sample_service.py                # complete_sample_definition trava o template
├── routers/
│   ├── collection_templates.py          # novo
│   └── processes.py                     # campo novo, 403, resposta
├── schemas.py                           # esquemas novos; CreateProcessRequest,
│                                        # ProcessInstanceDetail
├── bootstrap_system.py                  # permissão no catálogo e na BraCVAM
└── __init__.py                          # registra o router
migrations/versions/<rev>_collection_templates.py

tests/
├── factories/collection_template_factory.py (novo)
├── unit/core/test_collection_template_file.py
├── api/routers/
│   ├── test_collection_templates_router.py       # US1, US5
│   ├── test_collection_template_validation.py    # US2
│   ├── test_collection_template_lock.py          # US3
│   ├── test_collection_template_concurrency.py   # FR-019, chave e posição
│   ├── test_collection_template_security.py      # US6
│   └── test_process_collection_template.py       # US4
├── integration/bootstrap/test_bootstrap_system.py  # permissão nova
├── integration/migrations/test_collection_template_migration.py
└── integration/journeys/etapa_2_planejamento_preparacao/
    └── test_collection_template_journey.py

manual/
├── referencia/{rotas,erros,eventos,perfis-permissoes-cargos}.md
├── explicacao/escopo.md
└── guias/montar-template-de-coleta.md (novo) e guias/index.md
mkdocs.yml                               # entrada do guia novo em nav
```

**Structure Decision**: backend único existente (`src/pivma`). O domínio novo
segue o par serviço e router de `sample_service`/`samples`. O router replica
o padrão do `institutional.py` para permissão, origem e listagem.

## Pontos de atenção para as tarefas

- `test_bracvam_rbac_migration` trava as composições explícitas da migração.
  A migração nova não compõe, então esse teste não muda. O teste do
  bootstrap que lista o catálogo canônico muda.
- Os três pontos que montam `ProcessInstanceDetail` em `routers/processes.py`
  (criar, listar, consultar) precisam do campo novo.
- A trava em `complete_sample_definition` entra antes do `commit` e só
  quando o processo tem vínculo. O teste de concorrência segura uma das
  transações aberta para provar as duas ordens (US3, cenário 8). Ele
  confere a espera pela trava em `pg_stat_activity`, sem depender de tempo.
- O banco de teste nasce com `create_all` e não tem a linha de
  `collection_templates.manage`. Os testes criam a permissão por um helper
  da fábrica, e não pela fixture `bracvam_user` sozinha.
- A US4 vem antes da US3 na execução, porque a jornada da US3 cria o
  processo com o vínculo.
- A pendência da #30, sobre processos sem vínculo, segue registrada em
  `docs/observacoes-e-pendencias.md`. Esta entrega não a resolve.

## Complexity Tracking

Sem violações.
