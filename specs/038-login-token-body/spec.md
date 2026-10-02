# Feature Specification: Token de Acesso no Corpo da Resposta de Login

**Feature Branch**: `feat/auth-credentials-management` (por decisão do usuário, a feature é desenvolvida na branch atual, sem branch própria)

**Created**: 2026-10-02

**Status**: Draft

**Input**: Issue #44 — "[Feature] Retornar access_token no corpo JSON de POST /auth/login para clientes de API". Pedido do usuário: manter o cookie HttpOnly e devolver o token no corpo, sem deixar débitos ou lacunas técnicas e sem criar complexidade.

## Contexto

**CONFIRMADO** (código atual): `POST /auth/login` entrega o token de acesso apenas no cookie `access_token` (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, validade de 8 horas) e responde HTTP 200 com corpo vazio. Credenciais inválidas, conta inexistente e conta desativada recebem a mesma resposta 401 `invalid_credentials`.

**CONFIRMADO** (código atual): a autenticação das rotas protegidas aceita o mesmo token no cabeçalho `Authorization: Bearer <token>` quando a requisição não traz o cookie. Hoje, um cliente fora do navegador não tem como obter esse token pela API, a não ser lendo o cabeçalho `Set-Cookie`.

**CONFIRMADO** (documentação OpenAPI atual): a resposta 200 do login não tem schema documentado, e o único esquema de segurança declarado é o cookie `access_token`. O botão "Authorize" de `/docs` não oferece Bearer.

**CONFIRMADO** (código atual): as mutações autenticadas exigem cabeçalho `Origin` presente na lista de origens confiáveis (proteção contra CSRF da sessão por cookie). Um cliente fora do navegador não envia `Origin`, então hoje só conseguiria fazer leituras com Bearer.

## Clarifications

### Session 2026-10-02

- Q: Mutações autenticadas só por Bearer devem passar pela checagem de origem? → A: Não. Requisição autenticada só por `Authorization: Bearer` (sem cookie `access_token`) dispensa a checagem de `Origin`. Requisição com cookie continua exigindo origem confiável, mesmo que também traga Bearer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Obter o token no corpo do login (Priority: P1)

Como integrador de API, script de automação ou cliente fora do navegador, quero receber o token de acesso no corpo da resposta de login para usá-lo nas chamadas seguintes.

**Why this priority**: É o objetivo da issue. Sem isso, esses clientes precisam extrair o token do cabeçalho `Set-Cookie`.

**Independent Test**: Fazer login com credenciais válidas e conferir que o corpo traz o token, o tipo `bearer` e a validade em segundos, e que esse token é o mesmo entregue no cookie.

**Acceptance Scenarios**:

1. **Given** uma conta ativa, **When** o cliente faz login com credenciais válidas, **Then** o sistema responde HTTP 200 com `access_token`, `token_type` igual a `bearer` e `expires_in` igual a 28800.
2. **Given** o login do item anterior, **When** o cliente compara o `access_token` do corpo com o valor do cookie `access_token`, **Then** os dois são idênticos.
3. **Given** credenciais inválidas, conta inexistente ou conta desativada, **When** o cliente tenta o login, **Then** a resposta 401 `invalid_credentials` continua igual à atual e não traz token.

---

### User Story 2 - Usar o token recebido como Bearer (Priority: P1)

Como cliente de API, quero enviar o token recebido no cabeçalho `Authorization: Bearer <token>` e ser autenticado nas rotas protegidas sem depender de cookie.

**Why this priority**: Receber o token só tem valor se ele autenticar as chamadas seguintes.

**Independent Test**: Fazer login, descartar os cookies do cliente e chamar `GET /auth/me` com o token do corpo no cabeçalho `Authorization`.

**Acceptance Scenarios**:

1. **Given** um token obtido no corpo do login, **When** o cliente chama uma rota protegida sem cookie e com `Authorization: Bearer <token>`, **Then** o sistema reconhece a conta dona do token.

---

### User Story 3 - Navegador continua com sessão por cookie (Priority: P1)

Como pessoa usuária no frontend web, quero que o login continue criando a sessão por cookie seguro, sem mudança no meu fluxo.

**Why this priority**: É a proteção existente contra roubo de sessão por script no navegador e não pode regredir.

**Independent Test**: Fazer login e conferir os atributos do cookie e o acesso a `GET /auth/me` usando só o cookie.

**Acceptance Scenarios**:

1. **Given** uma conta ativa, **When** a pessoa faz login, **Then** o cookie `access_token` continua com `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/` e validade de 28800 segundos.
2. **Given** o login do item anterior, **When** a pessoa chama `GET /auth/me` só com o cookie, **Then** é autenticada como antes.

---

### User Story 4 - Executar mutações com Bearer (Priority: P1)

Como cliente de API, quero executar operações de escrita autenticado por Bearer, sem precisar forjar um cabeçalho `Origin`.

**Why this priority**: Sem isso, o token no corpo só serve para leituras, e integrações, scripts e clientes mobile/CLI continuam bloqueados nas escritas.

**Independent Test**: Fazer login, descartar os cookies e enviar uma mutação autenticada (por exemplo, `PATCH /auth/me`) com `Authorization: Bearer <token>` e sem `Origin`.

**Acceptance Scenarios**:

1. **Given** um token obtido no login e nenhum cookie, **When** o cliente envia uma mutação com `Authorization: Bearer <token>` e sem `Origin`, **Then** o sistema aplica as regras normais de autenticação e permissão, sem rejeitar por origem.
2. **Given** uma sessão por cookie, **When** o navegador envia uma mutação sem `Origin` confiável, **Then** o sistema continua respondendo 403 `invalid_origin`.
3. **Given** uma requisição com cookie `access_token` e também `Authorization: Bearer`, **When** ela chega sem `Origin` confiável, **Then** o sistema responde 403 `invalid_origin`.

---

### User Story 5 - Contrato do login documentado (Priority: P2)

Como integrador, quero que a documentação interativa da API mostre o formato da resposta de login.

**Why this priority**: Facilita testes manuais em `/docs` e a geração de clientes, mas não bloqueia o uso do token.

**Independent Test**: Consultar o documento OpenAPI e conferir que a resposta 200 do login referencia um schema com os três campos e que o esquema Bearer está declarado.

**Acceptance Scenarios**:

1. **Given** o documento OpenAPI publicado, **When** o integrador consulta a resposta 200 de `POST /auth/login`, **Then** encontra um schema com `access_token` (texto), `token_type` (sempre `bearer`) e `expires_in` (inteiro, em segundos), os três obrigatórios.
2. **Given** o documento OpenAPI publicado, **When** o integrador consulta os esquemas de segurança, **Then** encontra o cookie `access_token` e o esquema HTTP Bearer, e as rotas protegidas aceitam qualquer um dos dois.

---

### Edge Cases

- **Falha de autenticação**: nenhuma resposta de erro do login traz token, nem no corpo nem no cookie.
- **Validade coerente**: `expires_in`, a validade do cookie e a expiração gravada no token usam a mesma duração. Se a duração mudar no sistema, os três mudam juntos.
- **Cache intermediário**: a resposta de login carrega uma credencial no corpo e não pode ser guardada em cache por navegador nem proxy.
- **Cookie e Bearer na mesma requisição**: o cookie tem precedência na autenticação, como hoje, e a checagem de origem continua valendo.
- **Bearer inválido ou expirado**: a resposta é 401 `not_authenticated`, a mesma de uma sessão por cookie inválida.
- **Mutação cross-site com Bearer**: um site terceiro só consegue anexar `Authorization` a uma requisição do navegador após o preflight de CORS, que só aceita as origens configuradas. Por isso a dispensa de `Origin` não abre CSRF.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Em login bem-sucedido, o sistema DEVE responder HTTP 200 com corpo contendo `access_token`, `token_type` e `expires_in`.
- **FR-002**: `access_token` DEVE ser o mesmo token gravado no cookie `access_token` da mesma resposta.
- **FR-003**: `token_type` DEVE ser sempre `bearer`.
- **FR-004**: `expires_in` DEVE ser a validade do token em segundos, derivada da mesma duração usada no cookie e na expiração do token (hoje, 28800).
- **FR-005**: O sistema DEVE manter o cookie `access_token` com os atributos atuais (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, validade igual a `expires_in`).
- **FR-006**: As respostas de erro do login DEVEM permanecer inalteradas e não DEVEM conter token.
- **FR-007**: O token recebido no corpo DEVE autenticar rotas protegidas quando enviado como `Authorization: Bearer <token>`, sem cookie.
- **FR-008**: A resposta de login bem-sucedido DEVE indicar que não pode ser armazenada em cache (`Cache-Control: no-store`), como exige a prática de emissão de tokens do OAuth 2.0 (RFC 6749, seção 5.1).
- **FR-009**: O documento OpenAPI DEVE descrever o schema da resposta 200 de `POST /auth/login` com os três campos obrigatórios.
- **FR-010**: O documento OpenAPI DEVE declarar o esquema HTTP Bearer ao lado do cookie nas rotas protegidas, para que `/docs` permita autorizar com o token recebido.
- **FR-011**: Requisições sem cookie `access_token` e com `Authorization: Bearer` DEVEM dispensar a checagem de origem confiável. Requisições com cookie DEVEM manter a checagem atual.
- **FR-012**: O README DEVE documentar que o login também devolve o token no corpo para clientes fora do navegador, que mutações com Bearer dispensam `Origin` e que o frontend web continua usando o cookie.

### Key Entities

- **Resposta de login**: credencial emitida após autenticação. Atributos: token de acesso, tipo do token (`bearer`) e validade em segundos. Não é persistida; o token continua sendo o mesmo já emitido hoje.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um cliente fora do navegador autentica uma rota protegida em 2 chamadas (login e chamada protegida), sem ler cabeçalhos de cookie.
- **SC-002**: 100% dos logins bem-sucedidos devolvem o mesmo token no corpo e no cookie, com validade de 8 horas declarada nos dois.
- **SC-003**: 0 respostas de erro do login contêm token.
- **SC-004**: Os testes atuais de sessão por cookie (atributos do cookie, `GET /auth/me`, logout) continuam passando sem alteração de comportamento.
- **SC-005**: A documentação interativa mostra o formato da resposta de login, e uma pessoa consegue testar uma rota protegida em `/docs` colando o token recebido.
- **SC-006**: Um cliente fora do navegador executa uma mutação permitida com Bearer sem enviar `Origin`, e 100% das mutações com cookie sem origem confiável continuam rejeitadas.

## Assumptions

- O frontend web continua usando só o cookie e não deve guardar o token do corpo em armazenamento acessível por script. Expor o token no corpo é uma escolha explícita da issue para clientes de API; a proteção do cookie `HttpOnly` vale para quem continua usando o cookie.
- Não há refresh token, revogação de token nem lista de tokens emitidos. O logout continua removendo só o cookie; um token Bearer segue válido até expirar, como já acontece hoje com qualquer token emitido.
- A duração do token continua sendo de 8 horas. Esta feature não a torna configurável.
- O formato do corpo segue o padrão de resposta de token do OAuth 2.0 (`access_token`, `token_type`, `expires_in`), mas o login continua recebendo `identifier` e `password` em JSON. Adotar o fluxo de senha do OAuth 2.0 (formulário com `username`/`password`) está fora do escopo.
- O README hoje descreve o cookie com `SameSite=Lax`, mas o código usa `SameSite=Strict`. A atualização do README desta feature corrige essa divergência.
- A autenticação também aceita o token no parâmetro de consulta `token`, comportamento anterior a esta feature. Ele não é alterado aqui; a eventual remoção merece uma issue própria, porque pode haver cliente dependendo dele.
