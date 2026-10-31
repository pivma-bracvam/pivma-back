# Implementation Plan: Processos de tipo aposentado na listagem e no detalhe

**Branch**: `fix/044-retired-template-processes` | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/044-retired-template-processes/spec.md`

## Summary

`GET /processes` e `GET /processes/{id}` passam a montar a referência do tipo
com `template_refs`, nova função em lote de `core/references.py`, que ignora o
filtro global de soft delete. O formato da resposta não muda.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2.

**Storage**: PostgreSQL 17, sem migração.

**Testing**: pytest, pytest-asyncio e Testcontainers. Uma jornada a partir de
`bootstrap_fresh_deploy`, em
`tests/integration/journeys/etapa_1_submissao_triagem/`, e testes focados em
`tests/api/routers/`.

**Target Platform**: servidor Linux (Docker, `python:3.14-slim`)

**Project Type**: serviço web (backend)

**Performance Goals**: uma consulta de referências por página, como as demais
de `core/references.py`.

**Constraints**: resposta sem campo novo; filtros de visibilidade e de processo
excluído intactos.

**Scale/Scope**: duas rotas e uma função nova.

## Constitution Check

| Princípio | Resultado |
|---|---|
| I. Requisitos e evidência | PASS. O pedido do usuário e o banco do preview sustentam a spec. |
| II. Rastreabilidade e auditoria | PASS. Nenhuma escrita nova; os dados aposentados continuam guardados. |
| III. Segurança, autorização e sigilo | PASS. A leitura sem filtro só alcança nome, chave e versão do tipo do processo que a rota já autorizou. |
| IV. IA como apoio | PASS. A mudança não toca a IA. |
| V. Testes orientados a jornadas | PASS. Jornada e regressão escritas antes da correção. |
| VI. Mudanças simples | PASS. Reaproveita o padrão de `core/references.py`, sem mudar contrato. |
| VII. Documentação do estado atual | PASS. `manual/explicacao/modelo-de-processo.md` e `docs/observacoes-e-pendencias.md` entram no PR. |

Reavaliação após o desenho: sem mudanças.

## Project Structure

### Documentation (this feature)

```text
specs/044-retired-template-processes/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── tasks.md
└── checklists/requirements.md
```

`data-model.md` e `contracts/` ficam de fora: a feature não muda tabela nem
contrato.

### Source Code (repository root)

```text
src/pivma/core/references.py        # template_refs
src/pivma/routers/processes.py      # listagem e detalhe usam template_refs
tests/integration/journeys/etapa_1_submissao_triagem/test_retired_type_process.py
tests/api/routers/test_retired_template_processes.py
```

**Structure Decision**: a função entra em `core/references.py`, que já concentra
referências em lote que mostram registros desativados.

## Complexity Tracking

Sem exceções à constituição.
