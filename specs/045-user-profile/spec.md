# Feature Specification: Perfil do Usuário

**Feature Branch**: `feat/045-user-profile`

**Created**: 2026-11-04

**Status**: Implemented

**Input**: Pedido do usuário, com decisões da equipe em reunião e pedido indireto do BraCVAM: criar o perfil do usuário com os dados da conta (sem `username`), uma seção de cargos globais e uma de cargos locais junto ao processo de cada um. A própria pessoa vê o seu perfil completo. A arquitetura deve ser a mais simples possível, evitar respostas grandes para quem participa de muitos processos e permitir, no futuro, novos campos (como uma descrição) e uma visão do perfil de outras pessoas por membros comuns, sem dados sensíveis. O pedido inclui as lacunas apontadas pelo frontend: data de atribuição dos cargos globais, cargos locais por processo com datas, histórico de cargos locais revogados, `created_at` da conta e a ausência de `GET /users/{user_id}`.

## Contexto

**CONFIRMADO** (código em `develop`, commit `bf7f1e7`): `/users/{user_id}` só publica `PATCH` e `DELETE`. Não existe `GET /users/{user_id}`. O frontend localiza a pessoa pela listagem `GET /users`, que exige `users.read`.

**CONFIRMADO**: o banco já guarda tudo o que o perfil precisa. A conta tem `created_at`. A atribuição de cargo global (`user_access_profiles`) tem `created_at` e `deleted_at`. A designação em processo (`assignments`) tem `assigned_at`, `revoked_at` e o laboratório, quando o cargo é laboratorial. Nenhuma resposta da API expõe essas datas fora das rotas de escrita.

**CONFIRMADO**: `GET /auth/me` devolve a identidade, os cargos globais ativos e os escopos (processo e cargos efetivos) sem datas. `GET /processes/{id}/participants` e `.../participants/history` listam designações por processo, nunca por pessoa.

**CONFIRMADO**: `users.read` foi criada para a listagem administrativa. Os perfis Administrador e BraCVAM recebem todas as permissões do catálogo, `users.read` incluída. O catálogo RBAC permite conceder qualquer permissão a perfis novos.

**CONFIRMADO** (constituição, princípio III): nenhuma rota pode contornar o cegamento nem o isolamento por laboratório. Hoje, quem não gere os participantes de um processo vê nele só as próprias designações. Administrador e BraCVAM, os perfis que têm `users.read` hoje, já veem e gerem os participantes de qualquer processo.

**INFERÊNCIA**: o Plano de Trabalho não descreve uma página de perfil. A feature se apoia no RF001 (cadastro de usuários), no RF002 (perfis e atribuições) e no RF005 (designação de participantes por processo). A fonte da feature é a decisão da equipe registrada em Clarifications.

## Clarifications

### Session 2026-11-04 (decisões da equipe em reunião)

- O perfil mostra todos os dados da conta, exceto `username`, e as seções de cargos globais e de cargos locais.
- Cada cargo local aparece junto ao processo a que pertence. A resposta não pode crescer sem limite para quem participa de muitos processos.
- A própria pessoa vê o próprio perfil por inteiro.
- O perfil vai ganhar campos no futuro, como uma descrição.
- A equipe pode criar no futuro uma permissão para membros comuns verem o perfil de outras pessoas sem dados sensíveis, como e-mail e `username`. Esta spec não entrega essa visão; ela só não pode dificultar a inclusão.
- A arquitetura deve ser a mais simples que atenda aos pontos acima.
- Q: Quem tem `users.read` vê todos os cargos locais de outra pessoa ou só os dos processos em que gere participantes? → A: Vê todos. `users.read` é permissão administrativa e deve continuar só com perfis administrativos. Se a equipe precisar de uma consulta mais restrita, cria outra permissão no futuro, como mais um caso da regra de FR-015.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver o próprio perfil (Priority: P1)

Como pessoa autenticada, quero abrir meu perfil e ver meus dados de conta, desde quando a conta existe e quais cargos globais tenho, com a data de cada atribuição.

**Why this priority**: Toda conta ativa usa o perfil, sem depender de permissão administrativa. É o menor recorte que entrega valor.

**Independent Test**: Provisionar o ambiente, criar uma conta comum com um cargo global, autenticar com ela e consultar o próprio perfil pelo identificador devolvido em `GET /auth/me`.

**Acceptance Scenarios**:

1. **Given** uma conta comum autenticada com um cargo global ativo, **When** ela consulta o próprio perfil, **Then** a resposta traz identificador, nome completo, e-mail, estado ativo, data de criação e o cargo global com a data de atribuição, sem `username`.
2. **Given** a mesma conta sem `users.read`, **When** ela consulta o próprio perfil, **Then** o sistema responde com sucesso.
3. **Given** um cargo global revogado da conta, **When** ela consulta o próprio perfil, **Then** o cargo revogado não aparece na seção de cargos globais.

---

### User Story 2 - Ver os próprios cargos locais por processo (Priority: P1)

Como pessoa designada em processos, quero ver os processos em que atuo, com os cargos que tenho em cada um e a data de cada designação, e consultar à parte os cargos que já perdi.

**Why this priority**: O frontend pediu essa informação, e ela não existe hoje em nenhuma rota por pessoa.

**Independent Test**: Designar a mesma conta em dois processos, com dois cargos em um deles, revogar um cargo e consultar os cargos locais ativos e os revogados.

**Acceptance Scenarios**:

1. **Given** uma conta com cargos ativos em dois processos, **When** ela consulta os próprios cargos locais ativos, **Then** recebe um item por processo, cada um com código, título e estado do processo e a lista de cargos com data de designação.
2. **Given** um processo em que a conta tem dois cargos ativos, **When** ela consulta os cargos ativos, **Then** o processo aparece uma vez, com os dois cargos.
3. **Given** um cargo revogado, **When** a conta consulta os cargos revogados, **Then** o cargo aparece com as datas de designação e de revogação, e não aparece entre os ativos.
4. **Given** um cargo laboratorial, **When** a conta consulta os cargos locais, **Then** o cargo traz o laboratório da designação.
5. **Given** uma conta designada em mais processos do que cabem numa página, **When** ela consulta os cargos locais, **Then** a resposta vem paginada por processo, no envelope de listagem do projeto.

---

### User Story 3 - Administração consulta o perfil de outra pessoa (Priority: P2)

Como pessoa com `users.read`, quero abrir o perfil de uma conta encontrada na listagem de usuários e ver os mesmos dados e cargos que a dona da conta vê, incluindo todos os cargos locais.

**Why this priority**: Corrige a falta de `GET /users/{user_id}` apontada pelo frontend. Depende das histórias 1 e 2.

**Independent Test**: Autenticar como Administrador, consultar o perfil e os cargos locais de outra conta e repetir a consulta com uma conta comum, que deve ser recusada.

**Acceptance Scenarios**:

1. **Given** uma conta com `users.read`, **When** ela consulta o perfil de outra conta ativa, **Then** recebe os mesmos campos da história 1.
2. **Given** uma conta com `users.read`, **When** ela consulta o perfil de uma conta desativada, **Then** recebe o perfil com o estado inativo.
3. **Given** uma conta com `users.read`, **When** ela consulta um identificador que não existe, **Then** o sistema responde HTTP 404.
4. **Given** uma conta sem `users.read`, **When** ela consulta o perfil ou os cargos locais de outra conta, existente ou não, **Then** o sistema responde HTTP 403 sem dados da conta.
5. **Given** uma conta com `users.read`, **When** ela consulta os cargos locais de outra conta, **Then** recebe todos os processos e cargos dessa conta que atendem ao filtro, como a dona da conta receberia.

### Edge Cases

- Conta sem cargos globais: a seção vem vazia.
- Conta sem designações, ou sem revogações: a listagem vem vazia, com a paginação zerada.
- Processo excluído logicamente: suas designações não aparecem, ativas ou revogadas.
- Processo encerrado, cancelado ou arquivado: as designações aparecem, porque fazem parte do histórico da pessoa.
- Designação excluída logicamente: não aparece.
- Processo com um cargo ativo e outro revogado: aparece na consulta de ativos só com o ativo e na de revogados só com o revogado.
- Conta desativada consultada pela administração: os cargos locais aparecem com o estado registrado na designação. Desativar a conta não revoga designações.
- Perfil global atribuído, revogado e atribuído de novo: a seção mostra só a atribuição vigente, com a data dela.
- Sem sessão, ou com sessão de conta desativada: HTTP 401.
- Identificador com formato inválido: erro de validação no formato único do projeto.

## Requirements *(mandatory)*

### Functional Requirements

**Perfil**

- **FR-001**: O sistema DEVE oferecer `GET /users/{user_id}` com o perfil da conta: identificador, nome completo, e-mail, estado ativo, data de criação e cargos globais ativos.
- **FR-002**: O perfil NÃO DEVE conter `username`, hash de senha nem campos de auditoria além da data de criação da conta.
- **FR-003**: Cada cargo global do perfil DEVE trazer identificador, nome e data da atribuição vigente, em ordem crescente de data de atribuição e, no empate, de identificador.
- **FR-004**: Cargos globais revogados e cargos globais desativados NÃO DEVEM aparecer no perfil.

**Cargos locais**

- **FR-005**: O sistema DEVE oferecer `GET /users/{user_id}/process-roles`, uma listagem paginada com um item por processo.
- **FR-006**: Cada item DEVE trazer o processo (identificador, código, título e estado) e a lista de cargos daquela conta nele. Cada cargo traz a chave do cargo, o laboratório (quando houver), a data de designação e a data de revogação (nula quando ativo).
- **FR-007**: A listagem DEVE aceitar o filtro `active`, com padrão `true`. Com `true`, traz só cargos não revogados; com `false`, só cargos revogados. Processos sem cargo que atenda ao filtro ficam fora da página.
- **FR-008**: A listagem DEVE ordenar os processos pela designação mais recente entre os cargos do item, da mais nova para a mais antiga, e, no empate, pelo identificador do processo, em ordem crescente. Os cargos de cada item seguem a data de designação, da mais nova para a mais antiga, e, no empate, o identificador da designação, em ordem crescente.
- **FR-009**: A listagem DEVE usar o envelope paginado do projeto, com `page`, `per_page` e os limites já vigentes, e informar o filtro e a ordenação aplicados.
- **FR-010**: A listagem DEVE excluir designações excluídas logicamente e designações de processos excluídos logicamente.

**Acesso**

- **FR-011**: A própria pessoa DEVE ver o próprio perfil e todos os próprios cargos locais. Quem tem `users.read` DEVE ver o perfil e todos os cargos locais de qualquer conta, com os mesmos campos e filtros.
- **FR-012**: Sem `users.read`, a consulta a outra conta DEVE responder HTTP 403 antes de qualquer busca, para não revelar se a conta existe.
- **FR-013**: Com `users.read`, um identificador inexistente DEVE responder HTTP 404. Uma conta desativada DEVE responder com o perfil e o estado inativo.
- **FR-014**: As duas rotas DEVEM exigir sessão válida e responder HTTP 401 sem ela.
- **FR-015**: O sistema DEVE decidir num único ponto o que cada visão do perfil mostra, a partir de quem consulta e de quem é consultado, para que uma visão futura sem dados sensíveis seja um caso a mais nesse ponto, sem rota nova.

**Contratos existentes**

- **FR-016**: `GET /auth/me`, `GET /users`, `PATCH /users/{user_id}`, `DELETE /users/{user_id}` e as rotas de participantes DEVEM manter seus contratos.
- **FR-017**: A feature NÃO DEVE criar tabela, coluna nem permissão.

### Key Entities

- **Perfil do usuário**: projeção de leitura da conta, sem `username`, com os cargos globais vigentes. Não é persistido; nasce da conta e das atribuições.
- **Cargo global no perfil**: perfil de acesso atribuído à conta, com a data da atribuição vigente.
- **Processo com cargos locais**: um processo e os cargos da conta nele que atendem ao filtro, cada um com laboratório, designação e revogação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma conta comum abre o próprio perfil e os próprios cargos locais em duas requisições, sem permissão administrativa.
- **SC-002**: Em 100% das respostas de perfil, `username` e hash de senha estão ausentes.
- **SC-003**: Uma conta designada em mais processos do que cabem numa página recebe os cargos locais em páginas do tamanho pedido. Cada página traz no máximo `per_page` processos, e o total conta processos, não cargos.
- **SC-004**: Em 100% dos cenários, uma conta sem `users.read` recebe a mesma resposta HTTP 403 para outra conta existente e para um identificador inexistente.
- **SC-005**: Em 100% dos cenários, uma conta com `users.read` e a dona da conta recebem a mesma resposta para o perfil e para os cargos locais da conta.
- **SC-006**: A suíte existente de usuários, autenticação e participantes continua passando sem alteração de asserções.

## Assumptions

- **DECISÃO DESTA SPEC**: a própria pessoa usa as mesmas rotas, com o próprio identificador. `GET /auth/me` não muda. Ele carrega a sessão do frontend a cada página, e pôr nele o perfil e o histórico deixaria a resposta grande para quem participa de muitos processos. Campos futuros, como a descrição, entram no perfil.
- **DECISÃO DESTA SPEC**: os cargos locais ficam numa rota própria, paginada por processo, e o perfil não os embute. O perfil continua pequeno, e o frontend busca cada página quando precisar. Ativos e revogados usam a mesma rota com o filtro `active`, como `GET /users`.
- **DECISÃO DESTA SPEC**: os cargos de um processo vêm todos no mesmo item, sem paginação interna. Cada pessoa tem poucos cargos por processo.
- **DECISÃO DESTA SPEC**: a seção de cargos globais mostra só os vigentes. Concessões e revogações de cargos globais já aparecem no histórico de RBAC (`GET /rbac/changes`), e o frontend não pediu esse histórico.
- **DECISÃO DESTA SPEC**: o perfil não mostra se o cargo local está efetivo (por exemplo, cargo laboratorial sem vínculo ativo com o laboratório). Essa informação já existe em `GET /auth/me` e na listagem de participantes.
- **DECISÃO DESTA SPEC**: convites de designação pendentes não entram nos cargos locais. Eles ainda não são cargos.
- O e-mail é dado sensível na visão futura para membros comuns. Esta spec não entrega essa visão.
- `users.read` continua restrita a perfis administrativos. Dar essa permissão a um perfil não administrativo revelaria em quais processos cada pessoa atua; essa responsabilidade fica com quem administra o RBAC.
- As chaves de cargo seguem as já usadas pelas rotas de participantes. O frontend traduz cada chave para o nome exibido.

## Scope and Traceability

### In Scope

- `GET /users/{user_id}`: perfil da conta, com cargos globais vigentes e datas.
- `GET /users/{user_id}/process-roles`: cargos locais por processo, ativos ou revogados, paginados.
- Regra de acesso: a própria pessoa ou quem tem `users.read`.
- Testes de API das duas rotas e atualização do `manual/`.

### Out of Scope

- Visão do perfil de outras pessoas por membros comuns e a permissão correspondente.
- Campo de descrição ou qualquer campo novo no perfil.
- Edição do perfil. A própria pessoa já altera nome e senha em `PATCH /auth/me` (Spec 037).
- Histórico de cargos globais revogados no perfil.
- Mudanças em `GET /auth/me`, `GET /users` ou nas rotas de participantes.

### Requirement Traceability

| Fonte | Requisitos |
|-------|------------|
| Decisão da equipe (Clarifications) | FR-001 a FR-015 |
| Pedido do frontend: `GET /users/{user_id}` e `created_at` | FR-001, FR-013 |
| Pedido do frontend: data de atribuição dos cargos globais | FR-003 |
| Pedido do frontend: cargos locais por processo, com datas e histórico | FR-005 a FR-010 |
| RF001, RF002, RF005 | FR-001, FR-003, FR-005 |
| Constituição, princípio III | FR-011, FR-012 |
| Constituição, princípio VI | FR-016, FR-017 |
