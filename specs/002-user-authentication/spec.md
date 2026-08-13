# Feature Specification: Autenticação de Usuários

**Feature Branch**: `feature/user-authentication`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "Implementar a autenticação de usuários prevista no RF001 para contas já cadastradas na plataforma. O sistema deve permitir que um usuário apresente suas credenciais, seja autenticado de forma segura e tenha sua identidade reconhecida em requisições posteriores. Por decisão técnica da equipe, a autenticação deve utilizar JWT transportado por cookies. Esta feature deve permanecer restrita à autenticação e não deve incluir gestão de perfis, permissões, vínculos institucionais ou laboratoriais, designação de participantes ou demais funcionalidades dos RF002–RF006."

## Clarifications

### Session 2026-08-13

- Q1: Qual identificador de conta é aceito no login? → A: Username ou e-mail.
- Q2: Qual ciclo de vida a sessão deve ter? → A: JWT único por 8 horas. O logout remove o cookie; a feature não inclui revogação no servidor antes da expiração.
- Q3: Qual proteção contra requisições forjadas entre sites deve ser adotada? → A: Cookie com `SameSite=Strict` e validação de origem para operações autenticadas que alterem estado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Iniciar sessão (Priority: P1)

Uma pessoa com conta ativa fornece suas credenciais e inicia uma sessão autenticada. Nas requisições seguintes, o backend reconhece a identidade da mesma conta.

**Why this priority**: Este fluxo atende à parte de autenticação do RF001 e permite que recursos futuros identifiquem quem fez uma requisição.

**Independent Test**: Autenticar uma conta existente com credenciais corretas e verificar que uma requisição posterior, feita com o cookie recebido, reconhece o mesmo usuário.

**Acceptance Scenarios**:

1. **Given** uma conta ativa e credenciais corretas, **When** a pessoa inicia sessão, **Then** o sistema cria uma sessão autenticada e entrega o JWT em cookie.
2. **Given** uma sessão autenticada válida, **When** a pessoa faz uma requisição posterior com o cookie da sessão, **Then** o backend reconhece a identidade da conta associada.
3. **Given** credenciais incorretas, uma conta inexistente ou uma conta excluída logicamente, **When** a pessoa tenta iniciar sessão, **Then** o sistema não cria sessão e responde com a mesma falha pública, sem revelar qual dado falhou.

---

### User Story 2 - Preservar a sessão com segurança (Priority: P2)

Uma pessoa autenticada mantém sua identidade somente enquanto a sessão for válida. O navegador não pode ler o material de autenticação entregue pelo sistema.

**Why this priority**: A sessão precisa proteger a credencial e deixar claro quando ela deixa de valer.

**Independent Test**: Examinar o cookie entregue após o login, tentar usar um token inválido ou expirado e confirmar que o backend não reconhece uma identidade nesses casos.

**Acceptance Scenarios**:

1. **Given** uma sessão criada com sucesso, **When** a resposta é examinada, **Then** o JWT é entregue somente em cookie com proteção contra leitura por scripts do navegador e transmissão por canal inseguro.
2. **Given** um JWT adulterado, expirado ou associado a uma conta excluída logicamente, **When** ele é apresentado em uma requisição posterior, **Then** o backend não reconhece uma identidade autenticada.
3. **Given** uma tentativa de autenticação, **When** a resposta, registros operacionais e mensagens de erro são examinados, **Then** eles não expõem senha, JWT ou detalhes que diferenciem conta inexistente de senha incorreta.

### Edge Cases

- As credenciais incluem uma senha que não corresponde à credencial protegida da conta.
- A conta foi excluída logicamente entre a criação da sessão e uma requisição posterior.
- O navegador apresenta um cookie ausente, corrompido, adulterado ou vencido.
- A requisição que altera estado usa um cookie de autenticação sem a proteção contra requisições forjadas definida para esta feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir que uma conta ativa se autentique com username ou e-mail e senha.
- **FR-002**: O sistema DEVE verificar a senha apresentada contra a credencial protegida já cadastrada, sem armazenar, retornar ou registrar a senha em formato recuperável.
- **FR-003**: Após autenticação bem-sucedida, o sistema DEVE entregar um JWT exclusivamente por cookie e associá-lo à identidade da conta autenticada.
- **FR-004**: O backend DEVE reconhecer, em requisições posteriores, apenas uma identidade cujo JWT seja íntegro, válido e ligado a uma conta ativa.
- **FR-005**: O sistema DEVE rejeitar com a mesma resposta pública qualquer tentativa com identificador inexistente, senha incorreta ou conta excluída logicamente, sem criar uma sessão.
- **FR-006**: O cookie de autenticação DEVE impedir leitura por scripts do navegador e transmissão por conexão insegura.
- **FR-007**: O sistema DEVE criar uma sessão com validade máxima de 8 horas, sem token de renovação. O logout DEVE remover o cookie de autenticação; a feature não inclui revogação no servidor antes da expiração.
- **FR-008**: Para operações autenticadas que alterem estado, o sistema DEVE usar cookie com `SameSite=Strict` e validar a origem da requisição antes de aceitá-la.
- **FR-009**: A feature DEVE tornar a identidade autenticada disponível ao processamento de requisições no backend, sem conceder perfis, permissões ou acesso a recursos de domínio.
- **FR-010**: A feature NÃO DEVE incluir gestão de perfis ou permissões, vínculos institucionais ou laboratoriais, designação de participantes, declaração de conflito de interesse, recuperação ou troca de senha, cadastro de contas ou funcionalidades dos RF002 a RF006.
- **FR-011**: A feature DEVE preservar o contrato atual de criação de usuários e a regra de que identificadores de contas excluídas logicamente podem ser reutilizados.

### Key Entities

- **Conta de usuário**: Registro cadastrado que possui identificadores, uma credencial protegida e estado ativo ou excluído logicamente.
- **Sessão autenticada**: Período no qual uma conta ativa tem sua identidade reconhecida mediante um JWT válido transportado por cookie.
- **JWT de autenticação**: Credencial assinada que vincula uma sessão à identidade de uma conta, com validade limitada conforme decisão da equipe.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Todos os casos automatizados com credenciais corretas de contas ativas iniciam sessão e reconhecem a identidade correta em requisição posterior com o cookie correspondente.
- **SC-002**: Todos os casos automatizados com senha incorreta, identificador inexistente ou conta excluída logicamente não criam sessão e retornam a mesma resposta pública.
- **SC-003**: Todos os casos automatizados com JWT ausente, adulterado ou expirado não reconhecem uma identidade autenticada.
- **SC-004**: Todos os casos automatizados de autenticação bem-sucedida entregam o JWT somente em cookie protegido contra leitura por scripts e transmissão insegura.
- **SC-005**: Todos os casos automatizados de operações autenticadas que alteram estado rejeitam origem inválida, e todos os cookies de autenticação usam `SameSite=Strict`.
- **SC-006**: Todos os casos automatizados de expiração e logout deixam de reconhecer a identidade após oito horas ou após a remoção do cookie.

## Assumptions

- **CONFIRMADO, fonte oficial**: RF001 exige cadastro e autenticação de usuários da plataforma, conforme `docs/plano-de-trabalho-fase-ii.md`, seção 3.1.
- **CONFIRMADO, decisão técnica da equipe na solicitação atual**: a autenticação usa JWT transportado por cookies.
- **CONFIRMADO, implementação atual**: as contas existentes armazenam a senha como hash Argon2id e usam `deleted_at` para exclusão lógica, conforme `src/pivma/core/security.py` e `src/pivma/core/database/models.py`.
- **CONFIRMADO, contrato existente**: username e e-mail são únicos entre contas ativas, sem distinção de caixa, e ficam disponíveis após exclusão lógica, conforme `specs/001-secure-user-registration/spec.md` e `tests/routers/test_user.py`.
- **PROPOSTA desta feature**: a autenticação não atribui perfil, permissão, vínculo institucional ou laboratorial. Esses comportamentos dependem dos RF002 a RF006 e de especificações próprias.
- **DECISÃO da Session 2026-08-13**: a conta pode iniciar sessão com username ou e-mail. As comparações respeitam a regra existente de unicidade sem distinção de caixa.
- **DECISÃO da Session 2026-08-13**: a sessão usa somente um JWT de até 8 horas. A remoção do cookie encerra a sessão no navegador; não há token de renovação nem revogação antecipada no servidor nesta feature.
- **DECISÃO da Session 2026-08-13**: operações autenticadas que alterem estado usam `SameSite=Strict` e validação de origem. A lista exata de origens autorizadas pertence ao plano técnico.
- A rota pública que recebe as credenciais e a forma de expor uma identidade reconhecida serão definidas no plano técnico após a aprovação desta especificação.
