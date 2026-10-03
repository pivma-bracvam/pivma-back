# Feature Specification: Autogestão de Nome e Senha da Própria Conta

**Feature Branch**: `feat/037-self-profile-update`

**Created**: 2026-10-02

**Status**: Implemented

**Input**: Issue #43 — "[Feature] Implementar endpoint PATCH /auth/me para auto-gestão de dados cadastrais e alteração de senha". Pedido do usuário: especificar a issue sem criar complexidade ou débito técnico desnecessários, respeitando as instruções do repositório.

## Contexto

**CONFIRMADO** (código em `origin/develop`, commit `8560237`): a única rota que altera dados de uma conta é `PATCH /users/{user_id}` (Spec 008). Ela exige a permissão administrativa `users.manage`. Uma pessoa autenticada sem essa permissão não consegue corrigir o próprio nome nem trocar a própria senha.

**CONFIRMADO**: `GET /auth/me` já devolve a identidade da pessoa autenticada (`id`, `username`, `email`, `full_name`) e as permissões efetivas. Rotas de mutação autenticadas por cookie já exigem origem confiável (por exemplo, `POST /auth/logout` e `PATCH /users/{user_id}`).

**CONFIRMADO** (Plano de Trabalho, RF001): o Módulo de Gestão de Usuários abrange "cadastro e autenticação dos usuários da plataforma". **INFERÊNCIA**: a manutenção dos próprios dados de acesso faz parte desse requisito; o Plano de Trabalho não detalha o fluxo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Atualizar o próprio nome completo (Priority: P1)

Como pessoa usuária autenticada, quero corrigir ou preencher meu nome completo sem depender de uma pessoa administradora.

**Why this priority**: É a mudança de menor risco e resolve o caso mais comum, inclusive o de contas antigas com nome vazio.

**Independent Test**: Autenticar uma conta sem permissões administrativas, enviar um novo nome pela rota de autogestão e confirmar o novo valor na resposta e em `GET /auth/me`.

**Acceptance Scenarios**:

1. **Given** uma pessoa autenticada sem `users.manage`, **When** ela envia um nome completo válido para a própria conta, **Then** o sistema responde HTTP 200 com o nome sem espaços externos e persiste o novo valor.
2. **Given** a atualização do item anterior, **When** a pessoa consulta `GET /auth/me`, **Then** a resposta mostra o nome atualizado.
3. **Given** uma pessoa autenticada, **When** ela atualiza o próprio nome, **Then** a conta registra a própria pessoa como autora da última atualização e o instante da alteração.

---

### User Story 2 - Trocar a própria senha mediante confirmação da senha atual (Priority: P1)

Como pessoa usuária autenticada, quero trocar minha senha informando a senha atual, para manter minha credencial sob meu controle.

**Why this priority**: Sem essa operação, a troca de senha depende de uma pessoa administradora, que passaria a conhecer a nova credencial.

**Independent Test**: Autenticar uma conta, enviar a senha atual correta e uma nova senha válida, e confirmar que o login passa a aceitar apenas a nova senha.

**Acceptance Scenarios**:

1. **Given** uma pessoa autenticada, **When** ela envia a senha atual correta e uma nova senha válida, **Then** o sistema responde HTTP 200 e o login seguinte aceita a nova senha e rejeita a antiga.
2. **Given** uma pessoa autenticada, **When** ela envia uma senha atual incorreta e uma nova senha válida, **Then** o sistema responde HTTP 400 e a conta permanece inalterada.
3. **Given** uma pessoa autenticada, **When** ela envia uma nova senha sem a senha atual, **Then** o sistema responde HTTP 422 e a conta permanece inalterada.
4. **Given** uma pessoa autenticada, **When** ela envia uma nova senha que viola a política de senhas do cadastro, **Then** o sistema responde HTTP 422 e a conta permanece inalterada.
5. **Given** uma pessoa autenticada, **When** ela envia nome e senha juntos com a senha atual incorreta, **Then** o sistema responde HTTP 400 e nenhum dos dois campos é alterado.

---

### User Story 3 - Impedir alterações indevidas (Priority: P2)

Como responsável pela plataforma, quero que a rota de autogestão altere apenas a conta da sessão e apenas os campos previstos.

**Why this priority**: A rota fica disponível a qualquer conta autenticada, então seus limites precisam ser verificados no backend.

**Independent Test**: Repetir a requisição sem sessão, com origem não confiável, com campos fora do contrato e com corpo vazio, conferindo o status e a ausência de alteração.

**Acceptance Scenarios**:

1. **Given** uma requisição sem sessão válida, **When** ela tenta usar a rota de autogestão, **Then** o sistema responde HTTP 401.
2. **Given** uma sessão válida e uma origem ausente ou não confiável, **When** ela tenta usar a rota, **Then** o sistema responde HTTP 403 e a conta permanece inalterada.
3. **Given** uma sessão válida, **When** ela envia `username`, `email`, `password_hash` ou outro campo fora do contrato, **Then** o sistema responde HTTP 422 e a conta permanece inalterada.
4. **Given** uma sessão válida, **When** ela envia corpo vazio, valor `null` ou nome vazio após remover espaços, **Then** o sistema responde HTTP 422 e a conta permanece inalterada.
5. **Given** duas contas, **When** a primeira usa a rota, **Then** a segunda conta permanece inalterada.

---

### Edge Cases

- Uma senha atual enviada sem nova senha é rejeitada com HTTP 422, porque não representa nenhuma alteração válida.
- Uma conta desativada depois do login não consegue usar a rota: a sessão é recusada com HTTP 401, como já ocorre em `GET /auth/me`.
- A senha atual incorreta retorna HTTP 400, não HTTP 401. Um 401 indicaria sessão inválida e poderia levar o cliente a encerrar a sessão; aqui a sessão continua válida.
- Nova senha igual à senha atual é aceita; esta feature não cria regra de histórico ou reutilização de senhas.
- A resposta e as mensagens de erro não expõem senha, hash ou token.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer `PATCH /auth/me` para que a pessoa autenticada altere a própria conta, sem exigir `users.manage` ou outra permissão administrativa.
- **FR-002**: A rota DEVE alterar somente a conta identificada pela sessão; o corpo NÃO DEVE aceitar identificador de outra conta.
- **FR-003**: A rota DEVE exigir sessão válida (HTTP 401 sem ela) e origem confiável (HTTP 403 com origem ausente ou não confiável), seguindo as demais mutações autenticadas por cookie.
- **FR-004**: O corpo DEVE aceitar apenas `full_name`, `current_password` e `new_password`. Qualquer outro campo DEVE retornar HTTP 422.
- **FR-005**: O corpo DEVE conter `full_name`, `new_password` ou ambos. Corpo vazio, corpo só com `current_password` ou valor `null` em campo enviado DEVE retornar HTTP 422.
- **FR-006**: `full_name` DEVE seguir as regras do cadastro: espaços externos removidos e 1 a 255 caracteres após a remoção.
- **FR-007**: `new_password` DEVE seguir a política de senhas do cadastro: 8 a 128 caracteres e nenhum caractere de espaço.
- **FR-008**: Quando `new_password` for enviada, `current_password` DEVE ser obrigatória (HTTP 422 se ausente) e DEVE ser conferida com a credencial armazenada da conta.
- **FR-009**: Uma `current_password` incorreta DEVE retornar HTTP 400 com código de erro estável e mensagem em português, no formato único de erros do projeto (Spec 034).
- **FR-010**: A nova senha DEVE ser armazenada apenas na forma protegida já usada no cadastro; a senha em texto nunca é persistida nem devolvida.
- **FR-011**: A operação DEVE ser atômica: se qualquer validação falhar, nenhum campo é alterado.
- **FR-012**: Uma atualização válida DEVE registrar a própria pessoa como autora da última atualização e o instante da alteração, nos campos de auditoria existentes da conta.
- **FR-013**: Uma atualização válida DEVE retornar HTTP 200 com a projeção pública da conta (`id`, `username`, `email`, `full_name`), a mesma de `PATCH /users/{user_id}`.
- **FR-014**: `GET /auth/me` DEVE refletir o novo `full_name` na chamada seguinte à atualização.
- **FR-015**: A rota NÃO DEVE alterar `username`, `email`, perfis, permissões, vínculos institucionais, designações ou estado ativo da conta.
- **FR-016**: Os contratos existentes de `GET /auth/me`, `POST /auth/login`, `POST /auth/logout` e `PATCH /users/{user_id}` DEVEM permanecer inalterados.

### Key Entities

- **Conta de usuário**: registro já existente com identificadores, nome completo, credencial protegida e campos de auditoria de criação, atualização e exclusão lógica. Esta feature não adiciona atributos.
- **Pedido de autogestão**: dados enviados pela pessoa autenticada com nome completo, senha atual e nova senha, todos opcionais, combinados conforme FR-005 e FR-008. Não é persistido.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários válidos, uma conta sem permissões administrativas altera o próprio nome ou a própria senha em uma única requisição.
- **SC-002**: Em 100% das trocas de senha bem-sucedidas, o login seguinte aceita a nova senha e rejeita a anterior.
- **SC-003**: Em 100% dos cenários com senha atual incorreta, ausente ou inválida, o nome, a credencial e os campos de auditoria da conta permanecem inalterados.
- **SC-004**: Em 100% dos cenários sem sessão ou com origem não confiável, nenhuma conta é alterada.
- **SC-005**: Em 100% das atualizações válidas, a auditoria da conta identifica a própria pessoa como autora.
- **SC-006**: Nenhuma resposta da rota contém senha, hash ou token.
- **SC-007**: A suíte de testes existente de autenticação e de atualização administrativa continua passando sem alteração de asserções.

## Assumptions

- **DECISÃO DESTA SPEC**: senha atual incorreta retorna HTTP 400. A issue aceitava 400 ou 401; 401 já significa "sessão ausente ou expirada" neste projeto.
- **DECISÃO DESTA SPEC**: a resposta usa a projeção pública da conta, já usada por `PATCH /users/{user_id}`, sem criar um novo formato de resposta. Quem precisar de permissões e escopos atualizados consulta `GET /auth/me`.
- A sessão usada na troca de senha continua válida até expirar. O projeto ainda não tem revogação de sessões nem `refresh_token`; invalidar outras sessões após a troca depende dessa infraestrutura e fica fora desta entrega.
- Não há limite de tentativas da senha atual nesta entrega. O login também não tem esse controle hoje; um limite comum aos dois fluxos deve ser especificado à parte.
- Alteração de `username` e `email` pela própria pessoa fica fora desta entrega: envolve unicidade, possível confirmação de e-mail e impacto no identificador de login.
- O padrão de auditoria existente na conta (autor e instante da última atualização) basta para esta feature. Uma trilha de eventos dedicada a trocas de senha fica fora do escopo.
- Recuperação de senha esquecida (sem sessão) é outro fluxo e fica fora desta entrega.

## Scope and Traceability

### In Scope

- `PATCH /auth/me` para alterar `full_name` e/ou a senha da própria conta.
- Confirmação da senha atual para trocar a senha.
- Validações reaproveitadas do cadastro, auditoria nos campos existentes e testes de API em `tests/api/routers/test_auth_router.py`, conforme a issue.

### Out of Scope

- Alteração de `username`, `email`, perfis, permissões ou estado ativo pela própria pessoa.
- Revogação de sessões após a troca de senha.
- Limite de tentativas, bloqueio de conta ou histórico de senhas.
- Recuperação de senha esquecida.
- Mudanças no schema do banco ou migrações.

### Requirement Traceability

| Requirement | Source / Evidence |
|---|---|
| Autogestão de nome e senha (FR-001, FR-004 a FR-008, FR-014) | Issue #43, Escopo e Critérios de Aceite |
| Status 400 para senha atual incorreta (FR-009) | Issue #43 (400 ou 401) e decisão desta spec registrada em Assumptions |
| Cadastro e autenticação de usuários | Plano de Trabalho, RF001 (INFERÊNCIA quanto à autogestão) |
| Sessão e origem confiável (FR-003) | Constituição, Princípio III; padrão de `POST /auth/logout` e `PATCH /users/{user_id}` |
| Auditoria (FR-012) | Issue #43; Constituição, Princípio II; Plano de Trabalho, RF034 |
| Formato de erro (FR-009) | Spec 034 (formato único das respostas de erro) |
| Regras de nome e senha (FR-006, FR-007) | Spec 001 e Spec 008, regras do cadastro |
| Projeção pública (FR-013) | Spec 008, resposta de `PATCH /users/{user_id}` |
