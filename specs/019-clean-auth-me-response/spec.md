# Feature Specification: Limpeza e Padronização do Contrato de Sessão Atual

**Feature Branch**: `019-clean-auth-me-response`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Vamos manter só a versão mais recente, quebre a retrocompatibilidade, testes que utilizam a estrutura anterior podem ser removidos completamente"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consumo Estruturado da Identidade e Acesso da Sessão (Priority: P1)

Como um operador ou sistema cliente autenticado na plataforma, desejo consultar os dados da minha sessão ativa em uma estrutura limpa e não redundante, para que a identidade cadastral e os privilégios de acesso fiquem claramente separados e fáceis de consumir sem duplicidade de campos.

**Why this priority**: É o cerne da especificação. Elimina a redundância do contrato de sessão, consolidando a separação semântica entre identidade do usuário e contexto de autorização.

**Independent Test**: Autenticar uma conta ativa, solicitar os dados da sessão atual e verificar que a resposta contém exclusivamente dois blocos de primeiro nível: as informações cadastrais encapsuladas em `user` e as credenciais/escopos em `access`, sem replicação dos atributos de usuário no nível raiz.

**Acceptance Scenarios**:

1. **Given** que um usuário está autenticado com uma sessão ativa válida, **When** ele solicita os dados da sessão atual, **Then** a resposta deve conter os objetos `user` (com identificador, nome de usuário, e-mail e nome completo) e `access` (com perfis, permissões e escopos), sem campos de identificação soltos no nível raiz.
2. **Given** um usuário que possui nome completo preenchido e perfis atribuídos, **When** ele consulta a sua sessão atual, **Then** o nome completo e perfis refletem fidedignamente seu cadastro dentro de `user` e `access` respectivamente.

---

### User Story 2 - Atualização Consistente de Consumidores e Telas de Demonstração (Priority: P2)

Como usuário ou avaliador que interage com os módulos e interfaces visuais do sistema, desejo que todas as páginas e ferramentas operacionais continuem exibindo corretamente as informações da minha conta logada após a modernização do contrato da sessão.

**Why this priority**: Garante que a quebra de retrocompatibilidade do contrato seja acompanhada pela atualização de todos os pontos de integração internos do sistema, mantendo a integridade operacional e visual.

**Independent Test**: Acessar as interfaces de demonstração e fluxos operacionais autenticados e confirmar que o nome e papel do usuário logado são apresentados de forma íntegra a partir do nó `user`.

**Acceptance Scenarios**:

1. **Given** um usuário logado navegando em uma tela do sistema que exibe o usuário atual no cabeçalho ou nas ações, **When** a interface consulta a sessão ativa, **Then** a interface processa com sucesso o nó `user` e renderiza os dados do usuário sem erros de referência indefinida.

---

### Edge Cases

- Como o sistema se comporta quando a conta autenticada não possui nome completo cadastrado (ex.: contas legadas)? O atributo `full_name` dentro de `user` deve retornar `null` de forma explícita e válida, sem falhas de serialização.
- Como o sistema lida com requisições não autenticadas? A resposta de não autorizado deve continuar sendo rejeitada com o status de sessão inválida/ausente, independentemente da reestruturação do payload de sucesso.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE retornar os dados da sessão autenticada estruturados exclusivamente em dois blocos principais: `user` (dados cadastrais do usuário) e `access` (direitos de acesso e escopos).
- **FR-002**: O sistema NÃO DEVE expor atributos de identidade do usuário (tais como identificador, nome de usuário, e-mail ou nome completo) diretamente na raiz do objeto de resposta da sessão.
- **FR-003**: O bloco `user` DEVE conter os atributos de identificação da conta autenticada: identificador único, nome de usuário, endereço de e-mail e nome completo (admitindo nulo para contas legadas).
- **FR-004**: O bloco `access` DEVE manter a listagem de perfis ativos, permissões globais efetivas e escopos atribuídos ao usuário autenticado na sessão.
- **FR-005**: O sistema DEVE descontinuar formalmente o formato de resposta plano herdado de versões anteriores, tratando a quebra de compatibilidade como definitiva.
- **FR-006**: Todos os módulos consumidores internos, telas de demonstração e suítes de teste DEVEM ser atualizados para referenciar exclusivamente a estrutura encapsulada `user.*`.

### Key Entities

- **Identidade do Usuário (User Identity)**: Representa o conjunto de atributos de cadastro da pessoa na plataforma (identificador, username, e-mail e nome completo).
- **Contexto de Acesso (Access Context)**: Representa os direitos operacionais da sessão ativa, incluindo perfis atribuídos, lista de códigos de permissão efetivos e escopos de participação em processos.
- **Resposta da Sessão do Usuário (Current User Session)**: Contrato unificado que reúne a Identidade do Usuário (`user`) e seu Contexto de Acesso (`access`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das respostas de consulta à sessão autenticada devolvem o modelo estritamente encapsulado em `user` e `access`, com 0 campos de usuário redundantes na raiz.
- **SC-002**: 100% das páginas de demonstração que exibem dados da sessão logada continuam funcionando perfeitamente, lendo as propriedades da entidade `user`.
- **SC-003**: 100% dos testes automatizados de contrato da sessão passam validando unicamente a nova estrutura não redundante, com remoção total de asserções que dependiam da compatibilidade legada na raiz.

## Assumptions

- A quebra de retrocompatibilidade do endpoint de sessão foi aprovada pelo mantenedor, priorizando clareza arquitetural e limpeza de dívida técnica sobre suporte a clientes obsoletos.
- Clientes externos que ainda dependiam da raiz plana deverão migrar para acessar as propriedades através do atributo `user`.
- Mecanismos de autenticação, tempos de expiração e segurança de cookies permanecem inalterados.
