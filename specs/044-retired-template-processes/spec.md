# Feature Specification: Processos de tipo aposentado na listagem e no detalhe

**Feature Branch**: `fix/044-retired-template-processes`

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "Correção de defeito: GET /processes e
GET /processes/{id} respondem 500 quando o processo pertence a um template de
processo aposentado pelo bootstrap (soft delete). Causa confirmada: 3 processos
OPEN de proof_of_concept no preview. Listagem e detalhe devem continuar
funcionando e mostrar o tipo do processo."

## Contexto

- **CONFIRMADO, banco do preview** (consulta do usuário em 2026-10-31): 3
  processos `OPEN` usam o template `proof_of_concept`, com soft delete em
  2026-10-26. Nenhum outro template aposentado tem processo ativo.
- **CONFIRMADO, log do preview**: `GET /processes?page=1&per_page=100` responde
  500 com `AttributeError` em `_template_ref`.
- **CONFIRMADO, reprodução local**: um processo criado antes de o bootstrap
  aposentar seu tipo derruba `GET /processes` e `GET /processes/{id}`.
- **CONFIRMADO, implementação atual**: o bootstrap aplica soft delete no
  template cujo YAML sumiu e mantém as versões. O filtro global de soft delete
  esconde o template do processo, que chega nulo à resposta.
- **CONFIRMADO, Spec 043**: a decisão 6 dispensou o tratamento dos processos
  abertos da Prova de Conceito, sem prever a queda da listagem.

## Clarifications

### Session 2026-10-31

- Q: Corrigir o código ou limpar os dados do preview? → A: corrigir o código,
  com teste de regressão escrito antes da correção (usuário, 2026-10-31).
- Q: O contrato da resposta muda? → A: não. `template` mantém `key`, `name` e
  `version`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver os processos depois da aposentadoria de um tipo (Priority: P1)

Você criou uma submissão de um tipo que o BraCVAM retirou depois. Ao abrir a
lista de processos, você vê todos os seus processos, inclusive esse, com o nome
do tipo em que ele foi criado. Ao abrir o processo, você vê o mesmo tipo.

**Why this priority**: hoje um único processo nesse estado impede quem o
enxerga de ver qualquer processo da lista.

**Independent Test**: criar um processo de um tipo, aposentar o tipo por um novo
deploy e consultar lista e detalhe pela API.

**Acceptance Scenarios**:

1. **Given** um processo de tipo aposentado e um processo de tipo vigente,
   **When** o proponente consulta a lista, **Then** recebe os dois processos,
   cada um com a chave, o nome e a versão do seu tipo.
2. **Given** um processo de tipo aposentado, **When** o proponente consulta o
   detalhe, **Then** recebe o processo com a chave, o nome e a versão do tipo.

### Edge Cases

- Um processo excluído continua fora da lista e responde 404 no detalhe, mesmo
  quando o tipo está aposentado.
- O processo de tipo aposentado segue as regras de visibilidade: outro
  proponente não o vê na lista e recebe 404 no detalhe.
- O tipo aposentado continua fora de `GET /processes/templates` e não aceita
  novos processos.
- A página pode misturar processos de tipos vigentes e aposentados.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A listagem de processos DEVE incluir processos de tipo aposentado,
  com chave, nome e versão do tipo.
- **FR-002**: O detalhe do processo DEVE responder com chave, nome e versão do
  tipo aposentado.
- **FR-003**: A visibilidade e o tratamento de processos excluídos DEVEM
  continuar iguais.
- **FR-004**: O tipo aposentado DEVE continuar indisponível para novas
  submissões e fora da lista de tipos.
- **FR-005**: O formato da resposta DEVE continuar igual.

### Key Entities

- **Tipo de processo**: template com versões. Sai de uso por soft delete e
  continua identificando os processos criados com ele.
- **Processo**: guarda a versão do tipo usada na criação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Com processos de tipo aposentado na base, 100% das consultas de
  lista e detalhe feitas por quem tem acesso respondem com sucesso.
- **SC-002**: O usuário identifica o tipo de 100% dos processos listados.
- **SC-003**: Nenhuma pessoa passa a ver processo que não via antes da correção.

## Assumptions

- Decidir o destino dos 3 processos do preview fica fora de escopo, assim como
  continuar o fluxo de um processo cujo formulário foi aposentado.
- A correção não restaura o tipo aposentado nem altera o bootstrap.
