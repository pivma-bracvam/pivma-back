# Implementation Plan: Terminologia dos tipos e código da submissão

**Branch**: `feat/043-submission-types-and-code` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/043-submission-types-and-code/spec.md`

## Summary

Atende às seções 1 e 2.1 (item 3) do documento do BraCVAM:

- Os quatro tipos mantidos ganham nome, descrição e ordem de exibição novos
  nos YAMLs. O nome do formulário de submissão de cada tipo acompanha o
  nome novo (research R7). As chaves não mudam.
- `process_templates` ganha `display_order`. A listagem ordena por ele e o
  bootstrap recusa YAML sem ordem (R1, R2).
- O YAML da Prova de Conceito sai. O bootstrap já desativa o template e o
  formulário ausentes; testes e manual deixam de citá-la (R6).
- `generate_process_code` passa a gerar `VAL-<ano>-<n:04d>` com uma
  sequência anual em tabela própria, incrementada por upsert na transação da
  criação, com o ano no horário de Brasília (R3, R4, R5).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2,
Alembic. Dependência nova: `tzdata` (R4).

**Storage**: PostgreSQL 17. Uma migração: coluna
`process_templates.display_order` e tabela `process_code_sequences`.

**Testing**: pytest, pytest-asyncio, Testcontainers, factory-boy. Uma
jornada por história, a partir de `bootstrap_fresh_deploy`, em
`tests/integration/journeys/etapa_1_submissao_triagem/`. Testes focados para
ordem, recusa do YAML sem ordem, remoção da Prova de Conceito, sequência,
concorrência, rollback, virada de ano, fuso e número acima de 9999. Relógio
controlado por `monkeypatch` em `pivma.core.process_engine.utc_now`.

**Target Platform**: servidor Linux (Docker, `python:3.14-slim`)

**Project Type**: web-service (backend)

**Performance Goals**: uma linha travada por ano durante a criação de um
processo; volume esperado de dezenas de submissões por ano

**Constraints**: chaves de tipos e formulários inalteradas; contrato de
`GET /processes/templates` muda só na ordem, no total e em `sort.by`; sem
migração de dados (preview descartável, produção vazia)

**Scale/Scope**: 4 YAML alterados, 1 YAML removido, 1 migração, 2 funções
alteradas no bootstrap, 1 rota com ordenação nova, 1 função de código

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
| --- | --- |
| I. Requisitos e evidência | PASS. Fonte: documento do BraCVAM (seções 1 e 2.1, item 3), decisões do usuário em `docs/observacoes-e-pendencias.md` e na seção Clarifications, Plano de Trabalho 3.2 (crCode único). O nome dos formulários (R7) segue a mesma decisão de terminologia. |
| II. Rastreabilidade e auditoria | PASS. `process_code_sequences` herda `AuditMixin`. `PROCESS_CREATED` continua gravando o código. A Prova de Conceito sai por soft delete, feito pelo bootstrap. |
| III. Segurança, autorização e sigilo | PASS. Nenhuma permissão muda. A listagem continua exigindo sessão; a criação continua com `CurrentUser` e `TrustedOrigin`. |
| IV. IA como apoio | N/A. Sem IA. |
| V. Testes orientados a jornadas | PASS. Uma jornada por história e testes focados por risco, incluindo concorrência e ordenação. |
| VI. Mudanças simples e cirúrgicas | PASS. Uma coluna, uma tabela de contador e o mecanismo de soft delete existente. Contrato alterado (ordem e `sort.by` da listagem) aprovado na spec (FR-003). Arquivos YAML não são renomeados (R9). |
| VII. Documentação do estado atual | PASS. Manual e `templates_data/README.md` no mesmo PR, com `poe docs-build`. |

Reavaliação após o desenho (Phase 1): PASS. O desenho não acrescentou rota,
permissão nem abstração.

## Project Structure

### Documentation (this feature)

```text
specs/043-submission-types-and-code/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── process-templates.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── templates_data/01_pre_validated_method.yaml      # nome, descrição, display_order 1, nome do formulário
├── templates_data/04_validated_method_dossier.yaml  # display_order 2
├── templates_data/02_scope_extension.yaml           # display_order 3
├── templates_data/03_me_too_validation.yaml         # display_order 4
├── templates_data/05_proof_of_concept.yaml          # removido
├── templates_data/README.md                         # display_order; sem exemplo da Prova de Conceito
├── bootstrap_process_templates.py                   # valida e grava display_order
├── core/process_engine.py                           # generate_process_code sequencial
├── core/database/models.py                          # ProcessTemplate.display_order; ProcessCodeSequence
└── routers/processes.py                             # ordenação de GET /processes/templates

migrations/versions/<rev>_submission_types_and_code.py

pyproject.toml, poetry.lock, uv.lock                 # tzdata

tests/
├── integration/journeys/etapa_1_submissao_triagem/test_submission_types_and_code.py  # novo
├── integration/database/test_process_code_generation.py     # sequência, concorrência, rollback, ano
├── integration/bootstrap/                                   # display_order obrigatório
├── integration/migrations/test_submission_types_and_code_migration.py  # novo
├── api/routers/test_process_router.py                       # ordem, total, sort, 404 da Prova de Conceito
└── 9 arquivos com proof_of_concept                          # research R6

manual/
├── referencia/templates.md               # tabela dos tipos e ordem
├── guias/enviar-uma-proposta.md          # exemplo com outro tipo; formato do código
└── explicacao/escopo.md                  # tipos de submissão e formato do código
```

**Structure Decision**: o contador fica em `process_engine.py`, onde já está
`generate_process_code`; o modelo vai para `core/database/models.py` ao lado
de `ProcessInstance`.

## Complexity Tracking

Nenhuma violação da constituição a justificar.
