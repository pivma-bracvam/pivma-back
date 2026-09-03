# Feature Specification: Atualização Administrativa de Usuários

**Feature Branch**: `008-admin-user-update`

**Created**: 2026-09-03

**Status**: Approved for implementation

**Input**: User request to implement `PATCH /users/{user_id}` so an administrator can fill or change `full_name` for existing accounts, including mock accounts that still have `null`.

## Clarifications

### Session 2026-09-03

- **Decisão explícita da equipe**: a atualização administrativa será exposta em `PATCH /users/{user_id}`. O campo `full_name` será o único campo editável nesta entrega.
- **Decisão técnica registrada nesta feature**: a mutação exigirá a permissão separada `users.manage`; ela será concedida pelo perfil oficial Administrador e permanecerá fora de `ADMINISTRATIVE_PERMISSIONS`.
- Contas antigas ou mockadas não serão obrigadas a preencher `full_name`. Um administrador poderá preencher o campo posteriormente.
- Novos cadastros deverão informar `full_name`. A coluna continuará anulável para preservar contas antigas e mockadas.
- O campo omitido no PATCH não representa atualização. O corpo sem `full_name` e o valor `null` serão rejeitados; o valor atual nunca será apagado por esta operação.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preencher o nome de uma conta existente (Priority: P1)

Como pessoa administradora, quero atualizar o nome completo de uma conta para completar os dados de usuários antigos ou mockados.

**Why this priority**: Sem essa operação, a equipe precisa alterar diretamente o banco para completar dados de contas existentes.

**Independent Test**: Criar uma conta com `full_name = null`, autenticar uma pessoa com `users.manage`, executar o PATCH e confirmar o valor aparado na resposta e no banco.

**Acceptance Scenarios**:

1. **Given** uma conta existente e uma pessoa autenticada com `users.manage`, **When** a pessoa envia `PATCH /users/{user_id}` com um nome válido, **Then** o backend responde HTTP 200 com o nome aparado e persiste o novo valor.
2. **Given** uma conta cujo nome já foi preenchido, **When** a pessoa autorizada envia outro nome válido, **Then** o backend substitui o valor anterior e devolve o novo nome.

### User Story 2 - Impedir atualizações não autorizadas ou inválidas (Priority: P2)

Como responsável pela plataforma, quero que somente uma pessoa autorizada altere dados de usuários e que a API rejeite payloads inválidos.

**Why this priority**: O nome completo integra a identidade administrativa e não pode ser alterado por qualquer sessão ou por dados fora do contrato.

**Independent Test**: Repetir a atualização sem sessão, sem `users.manage`, com origem não confiável, com identificador inexistente e com valores inválidos, conferindo cada resposta.

**Acceptance Scenarios**:

1. **Given** uma requisição sem sessão, **When** ela tenta atualizar uma conta, **Then** o backend responde HTTP 401.
2. **Given** uma sessão sem `users.manage`, **When** ela tenta atualizar uma conta, **Then** o backend responde HTTP 403 sem alterar o registro.
3. **Given** uma sessão autorizada e uma origem não confiável, **When** ela tenta atualizar uma conta, **Then** o backend responde HTTP 403 sem alterar o registro.
4. **Given** uma sessão autorizada e um UUID sem conta correspondente, **When** ela tenta atualizar a conta, **Then** o backend responde HTTP 404.
5. **Given** uma sessão autorizada, **When** ela envia nome vazio, composto somente por espaços, maior que 255 caracteres ou `null`, **Then** o backend responde HTTP 422 sem alterar o registro.

### User Story 3 - Preservar identidade e rastreabilidade (Priority: P3)

Como equipe de desenvolvimento, quero manter contas antigas compatíveis e registrar quem atualizou o nome.

**Why this priority**: Os mocks existentes não terão preenchimento obrigatório e a alteração precisa continuar compatível com o padrão de auditoria do projeto.

**Independent Test**: Atualizar uma conta legada e verificar que `full_name`, `updated_at` e `updated_by` registram a alteração sem expor senha ou hash.

**Acceptance Scenarios**:

1. **Given** uma conta legada com `full_name = null`, **When** uma pessoa autorizada informa um nome válido, **Then** a conta passa a ter esse nome e mantém os identificadores e a credencial inalterados.
2. **Given** uma atualização concluída, **When** a conta é consultada pelos endpoints de usuário existentes, **Then** o novo `full_name` aparece nas respostas públicas correspondentes.

### Edge Cases

- Corpo vazio ou sem `full_name` não representa uma atualização válida e retorna HTTP 422.
- Campos adicionais, como `username`, `email`, `password` ou `password_hash`, não fazem parte deste contrato e retornam HTTP 422.
- A atualização de `full_name` não altera username, e-mail, senha, perfis, vínculos, estado ativo ou permissões.
- Uma conta antiga pode continuar com `full_name = null` até que alguém a atualize; esta feature não executa preenchimento em massa.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE disponibilizar `PATCH /users/{user_id}` para atualização administrativa de uma conta existente.
- **FR-002**: O backend DEVE exigir sessão autenticada, origem confiável e a permissão específica `users.manage` antes de alterar qualquer conta.
- **FR-003**: A permissão `users.manage` DEVE ser separada de `users.read`, `rbac.read`, `rbac.profiles.manage` e `rbac.assignments.manage`; o perfil oficial Administrador DEVE recebê-la pelo cálculo normal de permissões efetivas.
- **FR-004**: O PATCH DEVE aceitar somente `full_name` nesta entrega; campos adicionais ou campos de credencial DEVEM ser rejeitados.
- **FR-005**: O PATCH DEVE exigir `full_name` no corpo; ausência do campo ou valor `null` DEVE retornar HTTP 422.
- **FR-006**: O sistema DEVE remover espaços externos e aceitar `full_name` com 1 a 255 caracteres após o trim.
- **FR-007**: O sistema DEVE retornar HTTP 422 para nome vazio, composto somente por espaços ou maior que 255 caracteres, sem persistir alteração parcial.
- **FR-008**: O sistema DEVE retornar HTTP 404 quando o UUID não identificar uma conta existente.
- **FR-009**: Uma atualização válida DEVE persistir o nome aparado, atualizar `updated_at` e `updated_by` com a identidade da pessoa administradora e retornar HTTP 200 com a projeção pública da conta.
- **FR-010**: O PATCH NÃO DEVE alterar username, e-mail, senha, hash de senha, perfis, vínculos institucionais, designações, estado ativo ou permissões.
- **FR-011**: O `POST /users` DEVE exigir `full_name` para novos cadastros, mantendo a coluna anulável e a leitura de `null` para contas antigas ou mockadas.
- **FR-012**: As respostas de `POST /users`, `GET /auth/me` e `GET /users` DEVEM continuar expondo o valor persistido de `full_name`, inclusive `null` para contas antigas.

### Key Entities

- **Conta de usuário**: Registro com identificadores, credencial protegida, nome completo opcional para legado e campos de auditoria de criação, atualização e exclusão lógica.
- **Permissão de gestão de usuários**: Capacidade administrativa separada da consulta de usuários, atribuída ao perfil oficial Administrador nesta entrega.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários autorizados, uma pessoa com `users.manage` consegue preencher ou substituir o `full_name` de uma conta e recebe HTTP 200.
- **SC-002**: Em 100% dos cenários sem sessão, sem permissão ou com origem não confiável, o backend impede a alteração com o código HTTP correspondente.
- **SC-003**: Em 100% dos cenários inválidos, o backend retorna HTTP 422 e preserva o valor anterior de `full_name`.
- **SC-004**: Em 100% das atualizações válidas, a conta registra a identidade da pessoa administradora e o momento da alteração nos campos de auditoria existentes.
- **SC-005**: 100% das contas antigas ou mockadas continuam podendo ser consultadas com `full_name = null` sem migração de dados obrigatória.
- **SC-006**: 100% das respostas públicas de usuário continuam sem senha, hash, token ou dados internos de autorização.

## Assumptions

- A atualização é administrativa; edição pelo próprio usuário fica fora desta entrega.
- `users.manage` será a capacidade mínima para a mutação e o perfil Administrador será a primeira composição semeada.
- O nome completo é um valor não único e não participa da autenticação, da busca ou da ordenação da listagem existente.
- O padrão `AuditMixin` é suficiente para registrar o ator e o instante desta alteração; uma trilha de eventos dedicada para mudanças de perfil fica fora desta entrega.

## Scope and Traceability

### In Scope

- `PATCH /users/{user_id}` para atualizar `full_name`.
- Permissão `users.manage` e composição no perfil Administrador.
- Validação, auditoria nos campos existentes e preservação das projeções públicas.
- Obrigatoriedade de `full_name` somente para novos cadastros.

### Out of Scope

- Alteração de username, e-mail, senha, perfis, vínculos ou estado ativo.
- Edição de dados pelo próprio usuário.
- Atualização em lote.
- Preenchimento obrigatório ou em massa de contas antigas/mockadas.
- `display_name` separado ou personalização de nome de exibição.

### Requirement Traceability

| Requirement | Source / Evidence |
|---|---|
| Operação administrativa de atualização | `docs/planejamento/gestao-de-usuarios.md`, seção Administração de usuários |
| Rota e campo do PATCH | Decisão explícita da equipe registrada na Session 2026-09-03 |
| Autorização no backend | Constituição, Princípio III, e dependências de autorização existentes |
| Auditoria de atualização | Constituição, Princípio II, e `AuditMixin` existente em `User` |
| Compatibilidade com contas mockadas | Decisão explícita da equipe registrada na Session 2026-09-03 |
