# Tasks: Processos de tipo aposentado na listagem e no detalhe

**Input**: Design documents from `specs/044-retired-template-processes/`

**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: a constituição exige regressão para defeito, e o usuário pediu o teste
antes da correção.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Foundational

- [X] T001 Criar o helper que registra um tipo fora dos YAMLs, simula o deploy que o aposenta e limpa a sessão em tests/factories/retired_template_factory.py

## Phase 2: User Story 1 - Ver os processos depois da aposentadoria de um tipo (Priority: P1)

**Goal**: lista e detalhe respondem com o tipo do processo, mesmo aposentado.

**Independent Test**: criar um processo, aposentar o tipo por deploy e consultar
lista e detalhe pela API.

### Tests for User Story 1

- [X] T002 [US1] Jornada: o proponente vê na lista o processo de tipo aposentado e o de tipo vigente, abre o aposentado e encontra chave, nome e versão, em tests/integration/journeys/etapa_1_submissao_triagem/test_retired_type_process.py
- [X] T003 [P] [US1] `GET /processes` devolve chave, nome e versão do tipo aposentado em tests/api/routers/test_retired_template_processes.py
- [X] T004 [P] [US1] `GET /processes/{id}` devolve chave, nome e versão do tipo aposentado em tests/api/routers/test_retired_template_processes.py
- [X] T005 [P] [US1] Outro proponente não vê o processo na lista e recebe 404 no detalhe em tests/api/routers/test_retired_template_processes.py
- [X] T006 [P] [US1] Processo excluído de tipo aposentado fica fora da lista e responde 404 no detalhe em tests/api/routers/test_retired_template_processes.py
- [X] T007 [P] [US1] O tipo aposentado fica fora de `GET /processes/templates` e `POST /processes` responde 404 em tests/api/routers/test_retired_template_processes.py
- [X] T008 [US1] Rodar T002 a T007 antes da correção e confirmar que T002, T003, T004 falham com `AttributeError`

### Implementation for User Story 1

- [X] T009 [US1] Criar `template_refs` em src/pivma/core/references.py
- [X] T010 [US1] Usar `template_refs` em `list_processes` e remover o `selectinload` em src/pivma/routers/processes.py
- [X] T011 [US1] Usar `template_refs` em `get_process` e remover o `selectinload` em src/pivma/routers/processes.py

## Phase 3: Polish

- [X] T012 [P] Descrever o tipo aposentado em manual/explicacao/modelo-de-processo.md
- [X] T013 [P] Registrar a divergência com a decisão 6 da Spec 043 em docs/observacoes-e-pendencias.md
- [X] T014 Rodar `poe lint`, `poe test` e `poe docs-build`

## Dependencies

T001 precede os testes. T008 precede T009. T009 precede T010 e T011.

## Parallel Example

T003 a T007 ficam no mesmo arquivo, mas cobrem cenários independentes. T012 e T013
não dependem um do outro.

## Implementation Strategy

Escrever os testes, ver a falha, corrigir e rodar a suíte completa.
