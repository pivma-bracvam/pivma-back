# Feature Specification: Remover o Kanban de Pendências (`GET /activities/kanban`)

**Feature Branch**: `chore/029-remove-activities-kanban`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Remover o endpoint GET /activities/kanban (Kanban de pendências, Spec 018) do backend. O frontend não o utiliza e a forma de expor atividades será remodelada futuramente. O motor de processos (process_engine), o endpoint /tasks, Task.due_date/sla_hours, assigned_role/ACTIVITY_CARGOS e process_visibility_clause permanecem inalterados. Remover: router activities (única rota), include_router, schemas Kanban*, classify_kanban_column e constantes KANBAN_*, resolve_activity_holders (sem chamadas em produção) e os testes exclusivos do kanban."

## Contexto

A Spec 018 criou uma visão consolidada das atividades de todos os processos
visíveis ao usuário, organizada em quatro colunas (`NAO_INICIADO`,
`EM_ANDAMENTO`, `EM_ATRASO`, `CONCLUIDO`). O frontend não consome essa visão e
o responsável pelo produto decidiu remodelar a forma de expor atividades. Até
lá, o endpoint deixa de existir.

O motor de processos (instanciação, ativação e dependências de atividades,
criação de tarefas, prazo derivado de `sla_hours`, cargos das atividades) não
muda. A Spec 018 também revisou cargos globais e contextuais; essa parte segue
em vigor e é usada pelo fluxo de tarefas, participantes e convites.

A branch sai de `028-role-assignment-invites`, que já remove a seed, as demos
e a documentação do Kanban. Sobram código de aplicação e testes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A API deixa de oferecer o Kanban (Priority: P1)

Como mantenedor do backend, quero que a visão consolidada de atividades em
colunas deixe de existir, para que a remodelagem futura parta de uma base sem
um contrato que ninguém consome.

**Why this priority**: É o objetivo da mudança.

**Independent Test**: Uma requisição autenticada a `GET /activities/kanban`
não encontra a rota, e o contrato OpenAPI publicado não lista mais o caminho
nem os schemas do Kanban.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado com qualquer perfil, **When** ele requisita
   `GET /activities/kanban`, **Then** a API responde 404.
2. **Given** a aplicação em execução, **When** o contrato OpenAPI é consultado,
   **Then** ele não contém o caminho `/activities/kanban`, a tag `Activities`
   nem schemas `Kanban*`.

---

### User Story 2 - O fluxo de atividades e tarefas continua igual (Priority: P1)

Como usuário que participa de um processo, quero continuar recebendo e vendo
minhas tarefas, com cargo, status, bloqueio e prazo, exatamente como hoje.

**Why this priority**: A remoção não pode quebrar o motor nem o `/tasks`, que
continuam em uso.

**Independent Test**: A suíte existente de motor, tarefas, triagem,
formulários, participantes e convites passa sem alteração nos testes. A
rejeição de `assigned_role` inválido (cenário 3) não tinha teste; ganha um
teste de guarda novo, que passa antes e depois da remoção.

**Acceptance Scenarios**:

1. **Given** um processo instanciado, **When** uma atividade é ativada,
   **Then** a tarefa é criada com o mesmo cargo e o mesmo prazo de antes.
2. **Given** um usuário com visibilidade sobre um processo, **When** ele
   consulta `GET /tasks` e `GET /tasks/{id}`, **Then** as respostas mantêm os
   mesmos campos e as mesmas regras de visibilidade.
3. **Given** um template com `assigned_role` fora do vocabulário de cargos,
   **When** ele é instanciado, **Then** o erro de validação continua sendo
   levantado.

### Edge Cases

- Um cliente externo que ainda chame `/activities/kanban` passa a receber 404.
  Não há redirecionamento nem resposta de depreciação: o frontend não usa o
  endpoint.
- Não existe tabela, coluna nem migration exclusiva do Kanban. Nenhuma
  alteração de banco é necessária, e migrations antigas não são editadas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST deixar de expor `GET /activities/kanban`. Como é
  a única rota do grupo `/activities`, o grupo inteiro deixa de ser registrado.
- **FR-002**: O contrato da API MUST deixar de publicar os schemas do Kanban
  (`KanbanColumn`, `KanbanCardProcess`, `KanbanCardItem`, `KanbanPage`).
- **FR-003**: O sistema MUST remover a lógica usada só pelo Kanban: a
  classificação de atividades em colunas (`classify_kanban_column` e as
  constantes `KANBAN_*`) e a resolução de ocupantes de cargo
  (`resolve_activity_holders`), que não tem chamada fora do Kanban. Também
  saem os símbolos que ficam sem uso por causa desta remoção: o tipo de API
  `ActivityCargo` e a cópia de `GLOBAL_ACTIVITY_CARGOS` em `schemas.py`, e o
  mapa `_GLOBAL_CARGO_SYSTEM_KEYS` em `authorization.py`. O vocabulário de
  cargos do domínio (`ACTIVITY_CARGOS` e `GLOBAL_ACTIVITY_CARGOS` em
  `authorization.py`) permanece.
- **FR-004**: O sistema MUST manter sem mudança de comportamento o motor de
  processos, `GET /tasks`, `GET /tasks/{id}`, o cálculo de `Task.due_date` a
  partir de `sla_hours`, a validação de `assigned_role` contra o vocabulário
  de cargos e a regra de visibilidade de processos.
- **FR-005**: Os testes que cobrem só o Kanban MUST ser removidos:
  `tests/api/routers/test_activities_kanban.py`,
  `tests/api/routers/test_kanban_blocking_context.py`,
  `tests/api/routers/test_kanban_role_scoping.py`,
  `tests/unit/core/test_kanban_column_classification.py` e
  `tests/unit/core/test_resolve_activity_holders.py`.
- **FR-006**: Comentários e docstrings que citam o Kanban como referência
  (por exemplo, o de `_compute_activity_due_date` e o de
  `_resolve_activity_cargo`) MUST ser ajustados para não apontar para código
  removido.
- **FR-007**: Um teste de regressão MUST garantir que `GET /activities/kanban`
  responde 404 e que o OpenAPI não expõe o caminho.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nenhuma referência a `kanban` ou `resolve_activity_holders`
  permanece em `src/` e `tests/`, fora do teste de regressão do FR-007.
- **SC-002**: A suíte de testes completa passa, e nenhum teste fora da lista
  do FR-005 precisa ser alterado para passar.
- **SC-003**: `GET /activities/kanban` responde 404 para qualquer usuário.

## Assumptions

- O frontend não consome `GET /activities/kanban`, segundo o responsável pelo
  produto. Nenhum outro cliente conhecido o consome.
- A pasta `specs/018-kanban-activities-roles/` fica como registro histórico e
  não é editada.
- O RF031 (Painel de monitoramento) do Plano de Trabalho da Fase II fica sem
  implementação no backend até a remodelagem. A remoção é decisão explícita do
  responsável pelo produto, que está acima do Plano de Trabalho na ordem de
  precedência das fontes.
- A branch depende da `028-role-assignment-invites`. O PR aponta para ela ou
  espera o merge dela na `develop`.
