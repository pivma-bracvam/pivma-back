# Feature Specification: Recuperação de Senha por Token Temporário

**Feature Branch**: `feat/auth-credentials-management` (branch única das issues #43, #44 e #45)

**Created**: 2026-10-02

**Status**: Draft

**Input**: Issue #45 — "[Feature] Implementar fluxo de recuperação e redefinição de senha com token temporário". Pedido do usuário: implementar a issue com boas práticas, sem complexidade nem abstrações desnecessárias.

## Clarifications

### Session 2026-10-02

- Q: Em desenvolvimento local, o link de redefinição deve aparecer no log do servidor ou só no backend de e-mail falso? → A: Nunca em log; em desenvolvimento, o link é lido no backend de e-mail falso.

## Contexto

**CONFIRMADO** (código atual, commit `c25f31a`): não há fluxo para quem esqueceu a senha. A troca de senha só existe com sessão ativa (`PATCH /auth/me`, Spec 037) ou por uma pessoa administradora com `users.manage` (`PATCH /users/{user_id}`, Spec 008).

**CONFIRMADO**: a Spec 036 entregou uma base de notificações com envio de e-mail fora da requisição, novas tentativas e provedor trocável por configuração, incluindo uma implementação falsa para testes e desenvolvimento. A própria Spec 036 lista a recuperação de senha (#45) como próximo uso dessa base.

**CONFIRMADO**: o convite de designação (Spec 028) já guarda no banco só o hash do token, nunca o valor bruto, e monta o link a partir de um modelo de endereço configurável na implantação.

**CONFIRMADO** (Plano de Trabalho, RF001): o Módulo de Gestão de Usuários abrange "cadastro e autenticação dos usuários da plataforma". **INFERÊNCIA**: a recuperação de acesso faz parte desse requisito; o Plano de Trabalho não detalha o fluxo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pedir a recuperação de senha (Priority: P1)

Como pessoa usuária que esqueceu a senha, quero informar meu e-mail e receber um link de redefinição, sem depender de uma pessoa administradora.

**Why this priority**: É a entrada do fluxo. Sem ela, nenhum token é emitido.

**Independent Test**: Enviar o e-mail de uma conta ativa e conferir que a resposta é a mensagem neutra e que uma mensagem com o link e o prazo é registrada para esse endereço.

**Acceptance Scenarios**:

1. **Given** uma conta ativa, **When** alguém pede a recuperação com o e-mail dessa conta, **Then** o sistema responde HTTP 200 com a mensagem neutra, emite um token válido por 30 minutos e registra o envio de um e-mail para o endereço da conta com o link de redefinição e o prazo.
2. **Given** uma conta ativa, **When** o pedido usa o e-mail com letras maiúsculas e minúsculas diferentes do cadastro, **Then** o sistema trata o pedido como o do item anterior.
3. **Given** uma conta ativa com um token ainda não usado, **When** a pessoa pede a recuperação de novo, **Then** um novo token é emitido e o token anterior deixa de funcionar.
4. **Given** um token emitido, **When** se inspeciona o banco de dados, **Then** só existe o hash do token, nunca o valor bruto.

---

### User Story 2 - Não revelar quais e-mails têm conta (Priority: P1)

Como responsável pela plataforma, quero que o pedido de recuperação não permita descobrir se um e-mail está cadastrado.

**Why this priority**: A rota é pública. Sem essa proteção, ela vira uma ferramenta de enumeração de contas.

**Independent Test**: Comparar as respostas a um e-mail cadastrado, um e-mail inexistente e o e-mail de uma conta excluída.

**Acceptance Scenarios**:

1. **Given** um e-mail sem conta, **When** alguém pede a recuperação, **Then** o sistema responde HTTP 200 com a mesma mensagem neutra da conta existente, sem emitir token nem registrar envio.
2. **Given** uma conta excluída logicamente, **When** alguém pede a recuperação com o e-mail dela, **Then** o sistema responde igual ao item anterior.
3. **Given** um e-mail com formato inválido ou corpo fora do contrato, **When** alguém pede a recuperação, **Then** o sistema responde HTTP 422, como em qualquer validação de entrada, sem consultar contas.

---

### User Story 3 - Redefinir a senha com o token (Priority: P1)

Como pessoa usuária que recebeu o link, quero definir uma nova senha e entrar na plataforma logo em seguida.

**Why this priority**: Conclui o fluxo e devolve o acesso à pessoa.

**Independent Test**: Usar o token recebido com uma nova senha válida, fazer login com a nova senha e conferir que a senha antiga e o mesmo token não funcionam mais.

**Acceptance Scenarios**:

1. **Given** um token válido, **When** a pessoa envia o token e uma nova senha válida, **Then** o sistema responde HTTP 204, a senha da conta é trocada e o token é marcado como usado.
2. **Given** a redefinição do item anterior, **When** a pessoa faz login com a nova senha, **Then** o login é aceito; com a senha antiga, é recusado.
3. **Given** um token já usado, **When** alguém tenta usá-lo de novo, **Then** o sistema responde HTTP 400 e a senha não muda.
4. **Given** um token emitido há mais de 30 minutos, **When** alguém tenta usá-lo, **Then** o sistema responde HTTP 400 e a senha não muda.
5. **Given** um valor que não corresponde a nenhum token emitido, **When** alguém tenta usá-lo, **Then** o sistema responde HTTP 400.
6. **Given** um token substituído por um pedido mais recente, **When** alguém tenta usá-lo, **Then** o sistema responde HTTP 400.
7. **Given** um token válido, **When** a nova senha viola a política de senhas do cadastro, **Then** o sistema responde HTTP 422, a senha não muda e o token continua utilizável.

---

### Edge Cases

- Token inválido, expirado, já usado ou substituído recebem a mesma resposta HTTP 400, com o mesmo código e a mesma mensagem, para não revelar qual dos casos ocorreu.
- Uma conta excluída depois da emissão do token não pode ser redefinida: o token passa a responder HTTP 400.
- Duas redefinições simultâneas com o mesmo token: só uma é aceita; a outra recebe HTTP 400.
- Com o canal de e-mail não configurado na implantação, o pedido responde a mesma mensagem neutra e não emite token, porque o link não teria como chegar à pessoa. O log registra que o envio não foi possível, sem o token nem o e-mail.
- Uma falha de entrega posterior ao pedido não muda a resposta já dada; a base de notificações faz as novas tentativas.
- O token bruto não aparece em respostas, logs nem mensagens de erro. Ele só existe no link enviado por e-mail.
- Uma pessoa com sessão ativa também pode usar o fluxo; a sessão não interfere.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer `POST /auth/forgot-password`, pública, que recebe apenas `email`. Campos fora do contrato ou e-mail com formato inválido DEVEM retornar HTTP 422.
- **FR-002**: Para toda entrada válida, a rota DEVE responder HTTP 200 com a mesma mensagem neutra ("Se o e-mail estiver cadastrado, as instruções foram enviadas."), exista ou não uma conta ativa com esse e-mail.
- **FR-003**: Quando o e-mail corresponder, sem diferenciar maiúsculas de minúsculas, a uma conta não excluída, o sistema DEVE emitir um token aleatório de uso único, imprevisível, válido por 30 minutos a partir da emissão.
- **FR-004**: O sistema DEVE persistir só o hash do token, vinculado à conta, com o instante de expiração e o instante de uso (vazio até o consumo). O valor bruto NÃO DEVE ser persistido, registrado em log nem devolvido em resposta, em nenhum ambiente, inclusive o de desenvolvimento local.
- **FR-005**: Ao emitir um token, o sistema DEVE invalidar os tokens anteriores da mesma conta que ainda não foram usados.
- **FR-006**: Ao emitir um token, o sistema DEVE registrar pela base de notificações (Spec 036) um e-mail para o endereço da conta com o link de redefinição e o prazo de validade. O pedido de envio DEVE ser gravado junto com o token, na mesma transação.
- **FR-007**: O link DEVE ser montado a partir de um modelo de endereço configurável na implantação, com um marcador para o token, como no convite (Spec 036).
- **FR-008**: Sem canal de e-mail ou sem modelo de link configurados, o pedido DEVE responder a mensagem neutra sem emitir token.
- **FR-009**: O sistema DEVE oferecer `POST /auth/reset-password`, pública, que recebe apenas `token` e `new_password`. Campos ausentes ou fora do contrato DEVEM retornar HTTP 422.
- **FR-010**: `new_password` DEVE seguir a política de senhas do cadastro: 8 a 128 caracteres e nenhum caractere de espaço.
- **FR-011**: O sistema DEVE aceitar o token apenas se o hash corresponder a um token emitido, não expirado, não usado, não invalidado e vinculado a uma conta não excluída.
- **FR-012**: Um token recusado pela regra de FR-011 DEVE retornar HTTP 400 com um único código de erro estável e mensagem em português, no formato único de erros do projeto (Spec 034), sem distinguir o motivo.
- **FR-013**: Uma redefinição aceita DEVE, na mesma transação, gravar a nova senha na forma protegida já usada no cadastro e marcar o token como usado. Se algo falhar, nada é alterado.
- **FR-014**: Um token DEVE ser consumido no máximo uma vez, inclusive sob requisições simultâneas.
- **FR-015**: Uma redefinição aceita DEVE responder HTTP 204 e registrar a própria pessoa como autora da última atualização da conta, nos campos de auditoria existentes.
- **FR-016**: A senha nova DEVE valer no login seguinte; a senha anterior DEVE ser recusada.
- **FR-017**: As duas rotas NÃO DEVEM exigir sessão nem alterar `username`, `email`, perfis, permissões, vínculos ou estado da conta.
- **FR-018**: Os contratos existentes de `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me`, `POST /auth/logout` e `PATCH /users/{user_id}` DEVEM permanecer inalterados.

### Key Entities

- **Token de redefinição de senha**: registro novo, vinculado a uma conta, com o hash do token, o instante de expiração, o instante de uso (vazio até o consumo) e os campos de auditoria padrão do projeto. O token só é válido enquanto não expirou, não foi usado e não foi substituído.
- **Conta de usuário**: registro existente. Esta feature só troca a credencial protegida e atualiza os campos de auditoria de atualização.
- **Notificação**: registro existente da Spec 036. Esta feature acrescenta um novo tipo de mensagem, o e-mail de redefinição de senha.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma pessoa que esqueceu a senha recupera o acesso sem intervenção administrativa, com um pedido e uma redefinição.
- **SC-002**: Em 100% dos pedidos válidos, a resposta é idêntica em status e corpo, exista ou não a conta.
- **SC-003**: Em 100% das tentativas com token inválido, expirado, usado ou substituído, a senha da conta permanece inalterada.
- **SC-004**: Em 100% das redefinições aceitas, o login seguinte aceita a nova senha e recusa a anterior.
- **SC-005**: Nenhum token permanece utilizável mais de 30 minutos após a emissão nem depois de um uso.
- **SC-006**: Nenhuma resposta, log ou registro do banco contém o token bruto ou a senha.
- **SC-007**: A suíte de testes existente de autenticação, usuários e notificações continua passando sem alteração de asserções.

## Assumptions

- **DECISÃO DESTA SPEC**: validade fixa de 30 minutos, o limite superior da faixa da issue (15 a 30 minutos). Dá tempo para a entrega do e-mail com novas tentativas sem estender a janela de ataque. Não vira configuração enquanto ninguém pedir.
- **DECISÃO CONFIRMADA PELO USUÁRIO (2026-10-02) — CONFLITO COM A ISSUE**: a issue admite "imprimir o token em logs em ambiente local/desenvolvimento". Esta spec não faz isso: a Spec 036 proíbe o link bruto em logs, e o backend de e-mail falso da Spec 036 já atende desenvolvimento e testes sem esse risco. A divergência está registrada em `docs/observacoes-e-pendencias.md`, como pede a constituição.
- **DECISÃO DESTA SPEC**: o pedido aceita só e-mail, como diz a issue, e não nome de usuário. A mensagem precisa ir para um e-mail, e aceitar os dois identificadores amplia a superfície sem ganho.
- **DECISÃO DESTA SPEC**: a redefinição aceita responde HTTP 204, sem corpo, como `POST /auth/logout`. Ela não abre sessão; a pessoa faz login em seguida.
- **DECISÃO DESTA SPEC**: um novo pedido invalida os tokens anteriores ainda não usados, para que só o link mais recente funcione.
- Conta ativa significa conta não excluída logicamente, o mesmo critério do login.
- Sessões abertas antes da redefinição continuam válidas até expirar. O projeto ainda não tem revogação de sessões (mesma limitação registrada na Spec 037).
- Não há limite de tentativas nem de pedidos por e-mail ou por origem nesta entrega. O login também não tem esse controle; um limite comum deve ser especificado à parte.
- O envio ocorre fora da requisição (Spec 036), então o tempo de resposta não depende da entrega do e-mail. Igualar o tempo de resposta entre conta existente e inexistente além disso fica fora do escopo.
- Tokens usados ou expirados permanecem no banco. Limpeza periódica fica fora desta entrega.

## Scope and Traceability

### In Scope

- `POST /auth/forgot-password` e `POST /auth/reset-password`.
- Novo registro de token de redefinição, com migração de banco.
- Novo tipo de e-mail na base de notificações e o modelo configurável do link.
- Testes de API e de unidade cobrindo token válido, expirado, reutilizado, substituído, inválido e a resposta neutra.

### Out of Scope

- Limite de tentativas, bloqueio de conta e CAPTCHA.
- Revogação de sessões após a redefinição.
- Recuperação por nome de usuário ou por outros canais (WhatsApp, Telegram).
- Página de redefinição no frontend.
- Limpeza de tokens antigos.

### Requirement Traceability

| Requirement | Source / Evidence |
|---|---|
| Pedido e redefinição (FR-001, FR-003, FR-009 a FR-016) | Issue #45, Escopo e Critérios de Aceite |
| Resposta neutra (FR-002) | Issue #45, proteção contra enumeração |
| Só o hash persistido (FR-004) | Issue #45; padrão do convite (Spec 028, research R1) |
| Envio por e-mail e link configurável (FR-006 a FR-008) | Spec 036 (base de notificações, link configurável, recuperação de senha citada como uso futuro) |
| Invalidação de tokens anteriores (FR-005) | Decisão desta spec registrada em Assumptions |
| Formato de erro (FR-012) | Spec 034 |
| Política de senha (FR-010) | Spec 001, Spec 008 e Spec 037 |
| Auditoria (FR-015) | Constituição, Princípio II; padrão da Spec 037 |
| Cadastro e autenticação de usuários | Plano de Trabalho, RF001 (INFERÊNCIA quanto à recuperação) |
