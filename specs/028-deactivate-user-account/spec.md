# Feature Specification: Desativação de Conta de Usuário

**Feature Branch**: `028-deactivate-user-account`

**Created**: 2026-09-21

**Status**: Draft

**Input**: Issue #42: disponibilizar `DELETE /users/{user_id}` para desativação lógica de contas, com autorização administrativa, auditoria e proteção contra autodesativação e remoção do último administrador ativo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Desativar uma conta (Priority: P1)

Como pessoa administradora autorizada, quero desativar uma conta que não deve mais acessar a plataforma, sem apagar seu registro e sua rastreabilidade.

**Why this priority**: Contas cadastradas permanecem ativas sem uma operação administrativa de desativação, o que impede a revogação do acesso pela gestão de usuários.

**Independent Test**: Autenticar uma pessoa com `users.manage`, desativar outra conta ativa e confirmar a resposta sem conteúdo, os dados de auditoria e a presença da conta somente na listagem de inativas.

**Acceptance Scenarios**:

1. **Given** uma conta ativa e uma pessoa autenticada com `users.manage` em origem confiável, **When** a pessoa solicita `DELETE /users/{user_id}`, **Then** o sistema desativa a conta, registra o responsável e o momento e responde HTTP 204 sem conteúdo.
2. **Given** uma conta desativada, **When** uma pessoa autorizada consulta a listagem padrão de usuários, **Then** a conta não aparece entre as contas ativas.
3. **Given** uma conta desativada, **When** uma pessoa autorizada consulta `GET /users?active=false`, **Then** a conta aparece como inativa.

---

### User Story 2 - Preservar o acesso administrativo (Priority: P2)

Como responsável pela plataforma, quero impedir desativações que removam o acesso administrativo necessário para gerir o sistema.

**Why this priority**: A operação não pode permitir que uma pessoa desative a própria conta nem que a plataforma fique sem ao menos uma conta administradora ativa.

**Independent Test**: Tentar desativar a conta autenticada e a última conta que satisfaz a invariante administrativa, confirmando HTTP 409 e a preservação das duas contas.

**Acceptance Scenarios**:

1. **Given** uma pessoa administradora autenticada, **When** ela tenta desativar a própria conta, **Then** o sistema responde HTTP 409 e mantém a conta ativa.
2. **Given** apenas uma conta ativa que satisfaz a invariante administrativa, **When** outra pessoa autorizada tenta desativá-la, **Then** o sistema responde HTTP 409 e mantém a conta ativa.
3. **Given** duas ou mais contas ativas que satisfazem a invariante administrativa, **When** uma pessoa autorizada desativa uma delas sem desativar a própria conta, **Then** o sistema conclui a operação e preserva ao menos uma conta administradora ativa.

---

### User Story 3 - Revogar o uso de sessões existentes (Priority: P3)

Como responsável pela segurança, quero que uma conta desativada perca acesso mesmo quando possui uma credencial de sessão emitida antes da desativação.

**Why this priority**: A desativação só revoga o acesso se também impedir o uso de credenciais já emitidas.

**Independent Test**: Emitir uma credencial para uma conta ativa, desativar a conta com outra sessão administrativa e repetir uma requisição protegida com a credencial anterior, esperando HTTP 401.

**Acceptance Scenarios**:

1. **Given** uma credencial válida emitida para uma conta que foi desativada, **When** essa credencial é usada em uma requisição protegida, **Then** o sistema responde HTTP 401.
2. **Given** uma conta desativada, **When** a pessoa tenta se autenticar com suas credenciais, **Then** o sistema responde HTTP 401.

### Edge Cases

- Uma requisição sem sessão válida recebe HTTP 401 e não altera a conta indicada.
- Uma sessão sem `users.manage` ou uma requisição de origem não confiável recebe HTTP 403 e não altera a conta indicada.
- Um identificador que não corresponde a uma conta ativa recebe HTTP 404 e não altera registros.
- Duas tentativas concorrentes não podem desativar todas as contas que satisfazem a invariante administrativa.
- Uma falha durante a desativação não pode deixar somente parte dos dados de auditoria registrada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE disponibilizar `DELETE /users/{user_id}` para desativar logicamente uma conta ativa.
- **FR-002**: O sistema DEVE exigir sessão autenticada, origem confiável e a permissão `users.manage` antes de desativar uma conta.
- **FR-003**: A desativação concluída DEVE preservar o registro da conta e preencher somente os campos existentes de auditoria de exclusão com o momento da operação e a identidade da pessoa responsável.
- **FR-004**: Uma desativação concluída DEVE responder HTTP 204 sem conteúdo.
- **FR-005**: O sistema NÃO DEVE permitir que uma pessoa desative a própria conta por esta operação; a tentativa DEVE responder HTTP 409 sem alterar a conta.
- **FR-006**: O sistema DEVE rejeitar com HTTP 409 qualquer desativação que deixe a plataforma sem ao menos uma conta ativa que satisfaça a invariante administrativa existente.
- **FR-007**: O sistema DEVE preservar a invariante administrativa mesmo diante de pedidos concorrentes de desativação.
- **FR-008**: Uma conta desativada NÃO DEVE conseguir iniciar nova sessão nem usar credenciais emitidas antes da desativação; essas tentativas DEVEM responder HTTP 401.
- **FR-009**: A listagem padrão de usuários DEVE continuar retornando somente contas ativas.
- **FR-010**: `GET /users?active=false` DEVE continuar retornando somente contas inativas e DEVE incluir contas desativadas por esta operação.
- **FR-011**: Requisições sem sessão válida DEVEM responder HTTP 401; requisições sem `users.manage` ou provenientes de origem não confiável DEVEM responder HTTP 403. Nenhum desses casos pode alterar a conta indicada.
- **FR-012**: O sistema DEVE responder HTTP 404 quando o identificador não corresponder a uma conta ativa, sem alterar qualquer registro.
- **FR-013**: Esta feature NÃO DEVE excluir fisicamente contas, reativar contas, alterar dados cadastrais, modificar perfis ou permissões, nem criar novos campos de conta ou de auditoria.

### Key Entities

- **Conta de usuário**: Identidade cadastrada cujo estado ativo ou inativo decorre dos campos existentes de exclusão lógica. A conta preserva seus demais dados após a desativação.
- **Pessoa administradora responsável**: Conta autenticada com `users.manage` que solicita a desativação e fica registrada como autora da operação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das desativações autorizadas e sem conflito administrativo, a conta passa a constar como inativa, registra responsável e momento e a operação termina com HTTP 204.
- **SC-002**: Em 100% das tentativas de autodesativação ou de desativação da última conta que satisfaz a invariante administrativa, o sistema mantém a conta ativa e responde HTTP 409.
- **SC-003**: Em 100% dos testes com credenciais de contas desativadas, novas autenticações e requisições protegidas são rejeitadas com HTTP 401.
- **SC-004**: Em 100% dos testes de listagem, contas desativadas ficam ausentes da consulta padrão e aparecem na consulta de contas inativas.
- **SC-005**: Uma pessoa administradora autorizada consegue revogar o acesso de outra conta em uma única solicitação, sem intervenção direta nos dados persistidos.
- **SC-006**: Em testes concorrentes, 100% dos resultados preservam ao menos uma conta ativa que satisfaz a invariante administrativa.

## Assumptions

- HTTP 409 representa os conflitos de autodesativação e de preservação do último administrador, escolhendo uma das respostas permitidas pela issue #42.
- Uma conta inexistente ou já inativa não sofre nova alteração e recebe o mesmo tratamento de recurso ativo não encontrado, com HTTP 404.
- Os controles atuais de autenticação já consultam o estado vigente da conta em cada requisição protegida; esta feature não cria uma lista separada de revogação de credenciais.
- A desativação da conta não encerra nem remove seus vínculos, perfis, designações ou registros históricos. Esses dados deixam de conceder acesso enquanto a conta permanecer inativa.

## Scope and Traceability

### In Scope

- Desativação lógica de uma conta ativa por `DELETE /users/{user_id}`.
- Autorização por sessão, origem confiável e `users.manage`.
- Auditoria com os campos de exclusão existentes.
- Proteção contra autodesativação e contra remoção da última conta administradora ativa.
- Rejeição de credenciais de contas desativadas e preservação do comportamento atual das listagens.

### Out of Scope

- Exclusão física ou anonimização da conta.
- Reativação de conta.
- Alteração ou encerramento dos perfis, vínculos, designações e dados históricos da conta.
- Desativação em lote ou agendada.
- Novos campos, novos tipos de auditoria ou novos mecanismos de sessão.

### Requirement Traceability

| Requirement | Classification | Source / Evidence |
|---|---|---|
| Desativação lógica por operação administrativa | CONFIRMADO | Issue #42, contexto, escopo e critérios de aceite |
| Sessão, origem confiável e `users.manage` | CONFIRMADO | Issue #42; Spec 008, requisitos FR-002 e FR-003 |
| Auditoria da exclusão lógica | CONFIRMADO | Issue #42; Constituição, Princípio II; RF034 |
| Bloqueio de autodesativação | CONFIRMADO | Issue #42, regras de validação e segurança |
| Preservação de uma conta administradora ativa | CONFIRMADO | Issue #42; Spec 003, requisito FR-013 |
| Rejeição de credenciais da conta desativada | CONFIRMADO | Issue #42; comportamento vigente da autenticação |
| Listagem ativa e inativa | CONFIRMADO | Issue #42; contrato vigente de `GET /users` |
| HTTP 409 para os conflitos administrativos | PROPOSTA | Escolha entre HTTP 400/409 permitida pela issue #42 |
| HTTP 404 para conta inexistente ou já inativa | INFERÊNCIA | Contrato vigente de recurso não encontrado e filtro de exclusão lógica |
