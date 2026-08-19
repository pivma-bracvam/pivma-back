# Feature Specification: Autorização de Usuários e RBAC

**Feature Branch**: `feat/rbac-authorization`

**Created**: 2026-08-19

**Status**: Approved

**Input**: User description: "Criar a especificação da feature 003 - user authorization and RBAC do backend, pertencente ao Módulo de Gestão de Usuários da Fase II, com foco em RF002 Gestão de Perfis e RF004 Controle de Acesso, cobrindo a documentação do projeto sem ampliar a complexidade além do necessário."

## Clarifications

### Session 2026-08-19

- Q: Como os nove perfis oficiais devem coexistir com perfis criados pelos administradores? → A: Os nove perfis oficiais possuem nomes protegidos e permissões editáveis; administradores podem criar perfis adicionais.
- Q: Quantos perfis uma conta pode possuir ao mesmo tempo? → A: Uma conta pode possuir múltiplos perfis, e suas permissões formam uma união cumulativa.
- Q: Como as permissões administrativas de RBAC devem ser separadas? → A: O sistema separa consulta da configuração, gestão de perfis e gestão de atribuições.
- Q: Como a primeira conta com o perfil Administrador deve ser definida? → A: A implantação indica uma conta existente; a inicialização falha se a conta estiver ausente ou inativa.
- Q: Quais eventos de autorização devem gerar registro persistente nesta feature? → A: Somente mudanças de RBAC concluídas geram registro persistente; a recusa 403 após a verificação de permissão fica no registro operacional.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bloquear ações sem permissão (Priority: P1)

Uma pessoa autenticada acessa somente as ações protegidas concedidas por seus perfis ativos. O
backend nega qualquer tentativa sem permissão, inclusive quando a pessoa altera identificadores ou
contorna controles da interface.

**Why this priority**: O RF004 exige controle de acesso e a constituição determina que o backend
valide cada ação e dado protegido.

**Independent Test**: Preparar duas contas ativas, conceder a permissão exigida a apenas uma delas e
confirmar que somente essa conta conclui a mesma ação protegida.

**Acceptance Scenarios**:

1. **Given** uma conta autenticada com a permissão exigida por uma ação, **When** a pessoa solicita a ação, **Then** o backend permite que o fluxo prossiga.
2. **Given** uma conta autenticada sem a permissão exigida, **When** a pessoa solicita a mesma ação, **Then** o backend nega o acesso sem retornar o conteúdo protegido.
3. **Given** uma requisição sem identidade autenticada, **When** ela solicita uma ação protegida, **Then** o backend exige autenticação e não avalia perfis como substituto da identidade.
4. **Given** uma conta com mais de um perfil ativo, **When** a pessoa solicita uma ação, **Then** o backend considera a união das permissões concedidas por esses perfis.
5. **Given** uma conta sem acesso a um recurso protegido, **When** a pessoa troca no pedido o identificador por um recurso de outra pessoa, **Then** o backend mantém a negação e não revela se o recurso existe.

---

### User Story 2 - Administrar perfis e permissões (Priority: P2)

Um administrador autorizado consulta os perfis existentes, cria perfis adequados às atribuições
da plataforma e altera as permissões concedidas por cada perfil.

**Why this priority**: O RF002 exige criação e administração de perfis com permissões,
atribuições e responsabilidades distintas.

**Independent Test**: Criar um perfil, associar a ele uma permissão disponível, alterar sua
descrição, retirar a permissão e inativá-lo, conferindo o estado após cada operação.

**Acceptance Scenarios**:

1. **Given** um administrador com permissão para gerir perfis, **When** ele cria um perfil com nome e descrição válidos, **Then** o perfil fica disponível para receber permissões e atribuições.
2. **Given** um perfil ativo e uma permissão existente no catálogo, **When** o administrador concede ou retira essa permissão, **Then** o perfil passa a refletir a nova composição.
3. **Given** um perfil ativo que não seja o perfil protegido de Administrador, **When** o administrador o inativa, **Then** o perfil deixa de conceder permissões e não pode receber novas atribuições.
4. **Given** um nome de perfil usado por outro perfil ativo, sem distinção entre maiúsculas e minúsculas, **When** o administrador tenta criar ou renomear um perfil com esse nome, **Then** o sistema rejeita a operação sem alterar os registros existentes.
5. **Given** uma pessoa sem qualquer permissão administrativa de RBAC, **When** ela tenta consultar ou alterar a configuração de perfis, **Then** o backend nega a operação e não expõe a configuração protegida.
6. **Given** um dos nove perfis oficiais, **When** um administrador tenta renomeá-lo, **Then** o sistema rejeita a operação e preserva seu nome oficial.
7. **Given** uma conta que pode consultar a configuração de RBAC, mas não gerir perfis, **When** ela consulta e depois tenta alterar um perfil, **Then** o backend permite a consulta e nega a alteração.

---

### User Story 3 - Atribuir perfis a contas (Priority: P3)

Um administrador autorizado atribui ou retira perfis de contas ativas e consulta as permissões
efetivas resultantes. A mudança passa a reger os pedidos seguintes da conta.

**Why this priority**: Perfis administráveis produzem valor quando controlam o que cada conta pode
fazer.

**Independent Test**: Atribuir um perfil a uma conta sem permissão, confirmar o novo acesso,
retirar o perfil e confirmar a negação no pedido seguinte.

**Acceptance Scenarios**:

1. **Given** uma conta ativa e um perfil ativo, **When** o administrador autorizado atribui o perfil à conta, **Then** as permissões do perfil valem para os pedidos seguintes dessa conta.
2. **Given** uma conta com um perfil atribuído, **When** o administrador autorizado retira o perfil, **Then** as permissões exclusivas desse perfil deixam de valer no pedido seguinte.
3. **Given** uma conta com dois perfis que concedem a mesma permissão, **When** o administrador retira um deles, **Then** a conta preserva a permissão concedida pelo outro perfil ativo.
4. **Given** uma conta excluída logicamente ou um perfil inativo, **When** o administrador tenta criar uma atribuição, **Then** o sistema rejeita a operação sem criar vínculo parcial.
5. **Given** a última conta com o perfil protegido de Administrador, **When** alguém tenta retirar esse perfil ou eliminar sua capacidade de administrar RBAC, **Then** o sistema rejeita a operação para preservar ao menos um administrador ativo.
6. **Given** uma conta que pode gerir perfis, mas não gerir atribuições, **When** ela tenta atribuir um perfil a outra conta, **Then** o backend nega a operação sem criar o vínculo.

---

### User Story 4 - Rastrear mudanças de acesso (Priority: P4)

Um responsável autorizado identifica quem criou, alterou ou inativou um perfil e quem concedeu ou
retirou um perfil de uma conta.

**Why this priority**: Mudanças de acesso afetam a segurança da plataforma e precisam manter a
rastreabilidade exigida pela constituição e pelo RF034.

**Independent Test**: Executar cada tipo de mudança de RBAC com uma conta administradora e conferir
que o sistema associa a operação ao responsável e ao momento correspondente.

**Acceptance Scenarios**:

1. **Given** uma mudança concluída em perfil, permissão ou atribuição, **When** um responsável autorizado consulta seus dados de rastreabilidade, **Then** o sistema informa o tipo de mudança, o responsável e o momento.
2. **Given** uma tentativa negada de administrar RBAC, **When** a operação termina, **Then** nenhum perfil, permissão ou atribuição sofre alteração.
3. **Given** uma conta autenticada sem a permissão exigida, **When** o backend devolve 403 após verificar a permissão, **Then** ele registra a recusa para acompanhamento operacional e não cria evento persistente na trilha de mudanças de RBAC.
4. **Given** que a implantação concluiu a primeira atribuição de Administrador, **When** um responsável autorizado consulta a trilha de mudanças, **Then** o sistema informa a inicialização, seu momento e a ausência de autor autenticado.

### Edge Cases

- Uma pessoa perde uma permissão durante uma sessão autenticada ainda válida. O backend usa o
  estado atual dos perfis no pedido seguinte e nega a ação.
- Dois administradores tentam criar perfis com nomes equivalentes ao mesmo tempo. O sistema mantém
  somente um perfil ativo com esse nome e rejeita a operação concorrente.
- Dois administradores alteram a mesma atribuição ao mesmo tempo. O sistema mantém uma relação
  única entre conta e perfil, sem vínculos duplicados ou parciais.
- Um administrador tenta conceder uma permissão inexistente. O sistema rejeita a operação.
- Um perfil inativado ainda possui contas vinculadas. O sistema preserva o histórico dos vínculos,
  mas o perfil deixa de conceder acesso.
- Uma conta possui perfil com nome semelhante a um papel oficial. O backend decide pelo vínculo e
  pelas permissões registradas, nunca pelo texto apresentado pelo cliente.
- A implantação indica como primeiro Administrador uma conta ausente ou inativa. A inicialização
  falha sem atribuir o perfil a outra conta.
- Uma permissão global coincide com uma futura ação que exige instituição, laboratório ou
  participação em processo. O sistema não concede acesso ao dado contextual até que uma feature
  aprovada defina e implemente essa regra adicional.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE exigir uma identidade autenticada para toda a administração de perfis, permissões e atribuições.
- **FR-002**: O backend DEVE verificar a permissão exigida por cada ação protegida antes de consultar, criar, alterar ou devolver dados protegidos.
- **FR-003**: O sistema DEVE negar uma ação protegida quando a conta não possuir a permissão exigida em nenhum perfil ativo.
- **FR-004**: A resposta de acesso negado NÃO DEVE expor o conteúdo protegido nem confirmar a existência de recurso que a conta não possa consultar.
- **FR-005**: O sistema DEVE manter um catálogo de permissões identificadas de forma estável, cada uma ligada a uma capacidade de negócio aprovada.
- **FR-006**: Esta feature DEVE separar no catálogo três capacidades administrativas: consultar a configuração de RBAC e sua rastreabilidade, gerir perfis e suas permissões, e gerir atribuições entre perfis e contas.
- **FR-007**: O administrador NÃO DEVE criar permissões livres durante a operação; features aprovadas ampliam o catálogo quando introduzem novas capacidades protegidas.
- **FR-008**: O sistema DEVE permitir que um administrador autorizado consulte, crie, altere e inative perfis.
- **FR-009**: Cada perfil DEVE possuir nome, descrição de atribuições e responsabilidades, estado ativo ou inativo e um conjunto de permissões do catálogo.
- **FR-010**: Nomes de perfis ativos DEVEM ser únicos sem distinção entre maiúsculas e minúsculas.
- **FR-011**: O sistema DEVE iniciar com os perfis citados no Plano de Trabalho: Proponente, Grupo Gestor, Gerente do Estudo, Laboratório Participante, Avaliador Ad Hoc, Revisor, Especialista, Analista Estatístico e Administrador. O sistema DEVE proteger esses nomes contra renomeação, permitir a edição de suas permissões e aceitar perfis adicionais criados por administradores autorizados.
- **FR-012**: O perfil Administrador DEVE receber as permissões de administração de RBAC definidas nesta feature; os demais perfis iniciais não recebem permissões de outros módulos antes que especificações aprovadas definam essas capacidades.
- **FR-013**: O sistema DEVE proteger o perfil Administrador contra renomeação e inativação e impedir mudanças que deixem a plataforma sem ao menos uma conta ativa capaz de administrar RBAC.
- **FR-014**: O sistema DEVE permitir que um administrador autorizado atribua um ou mais perfis ativos a uma conta ativa e retire essas atribuições.
- **FR-015**: O sistema DEVE manter no máximo uma atribuição ativa entre uma conta e um perfil, inclusive diante de pedidos concorrentes. Retiradas encerram a atribuição ativa e uma concessão posterior inicia novo ciclo rastreável.
- **FR-016**: O sistema DEVE calcular as permissões efetivas de uma conta pela união das permissões de seus perfis ativos, sem regra de negação explícita nesta feature.
- **FR-017**: Criação, alteração e inativação de perfis, mudanças de permissões e atribuições ou retiradas de perfis DEVEM produzir efeito nos pedidos posteriores sem exigir uma nova autenticação.
- **FR-018**: O sistema DEVE associar cada criação, alteração e inativação de perfil e cada concessão ou retirada administrativa de perfil ao responsável autenticado e ao momento da operação. A primeira atribuição do Administrador definida por FR-024 é a única exceção: ela registra o momento e a natureza da inicialização, com autoria nula por não existir responsável autenticado.
- **FR-019**: O sistema DEVE preservar registros inativos e atribuições encerradas para rastreabilidade; registros inativos NÃO DEVEM conceder acesso.
- **FR-020**: O backend NÃO DEVE confiar em nomes de perfil, permissões ou indicadores de acesso enviados pelo cliente para autorizar uma ação.
- **FR-021**: Esta feature DEVE preservar os contratos existentes de cadastro e autenticação das features 001 e 002.
- **FR-022**: Esta feature cobre a dimensão global de perfil do RF004. Ela NÃO DEVE conceder acesso baseado em instituição, laboratório ou participação em processo antes das especificações de RF003 e RF005.
- **FR-023**: Esta feature NÃO DEVE incluir administração de contas, vínculos institucionais ou laboratoriais, designação por processo, conflito de interesse, matriz de acesso de outros módulos, cegamento, renovação de sessão ou trilha geral de auditoria.
- **FR-024**: A implantação DEVE indicar uma conta existente e ativa para receber a primeira atribuição do perfil Administrador. A inicialização DEVE falhar quando a conta indicada estiver ausente ou inativa e NÃO DEVE promover outra conta de forma automática.
- **FR-025**: Somente mudanças de RBAC concluídas DEVEM compor a rastreabilidade persistente desta feature. O sistema DEVE registrar no acompanhamento operacional a recusa 403 emitida após a verificação de permissão, sem incluí-la nessa trilha. Requisições sem identidade, com origem inválida, payload inválido ou conflito de estado não integram esse acompanhamento RBAC.

### Key Entities

- **Perfil de acesso**: Agrupa nome, atribuições, responsabilidades, estado e permissões. Uma
  conta pode possuir mais de um perfil.
- **Permissão**: Identifica uma capacidade de negócio protegida que o backend pode exigir antes de
  executar uma ação.
- **Atribuição de perfil**: Relaciona uma conta a um perfil e preserva autoria, início e
  encerramento da concessão.
- **Permissão efetiva**: Resultado da união das permissões concedidas pelos perfis ativos de uma
  conta no momento do pedido.
- **Conta de usuário**: Identidade cadastrada e autenticável definida pelas features 001 e 002.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários automatizados, contas sem a permissão exigida não concluem a ação nem recebem dados protegidos.
- **SC-002**: Em 100% dos cenários automatizados, contas com a permissão exigida por ao menos um perfil ativo conseguem prosseguir para a ação protegida.
- **SC-003**: Em 100% dos cenários de alteração, inativação ou retirada de acesso, o pedido seguinte da conta reflete a nova permissão sem exigir nova autenticação.
- **SC-004**: Durante a validação manual cronometrada, um administrador autorizado conclui, em até 2 minutos, o fluxo de criar um perfil, conceder uma permissão e atribuí-lo a uma conta.
- **SC-005**: O conjunto de validação cobre os nove perfis de referência, contas com zero, um e múltiplos perfis, perfil inativo e permissão compartilhada por mais de um perfil.
- **SC-006**: Em 100% dos cenários concorrentes de nome de perfil e atribuição, o sistema termina com um único registro válido e sem alteração parcial.
- **SC-007**: Em 100% das mudanças administrativas concluídas de RBAC no conjunto de validação, um responsável autorizado consegue identificar o autor, o tipo de mudança e o momento correspondente. Na primeira atribuição por bootstrap, a consulta identifica a inicialização e seu momento, com autoria nula.
- **SC-008**: Nenhum cenário de inativação ou retirada de perfil deixa a plataforma sem uma conta ativa capaz de administrar RBAC.
- **SC-009**: Todos os cenários existentes das features 001 e 002 continuam válidos após a introdução de RBAC.
- **SC-010**: Em 100% dos cenários de separação administrativa, possuir uma das três capacidades de RBAC não concede as outras duas.
- **SC-011**: Em todos os cenários de inicialização, somente a conta ativa indicada recebe a primeira atribuição de Administrador; uma indicação ausente ou inválida interrompe a inicialização sem promover outra conta.
- **SC-012**: Em 100% das recusas 403 emitidas após a verificação de permissão, o acompanhamento operacional recebe o resultado da tentativa e a trilha persistente de mudanças de RBAC permanece inalterada.

## Assumptions

- **CONFIRMADO, fonte oficial**: O Módulo de Gestão de Usuários pertence à Fase II e o RF002
  exige criação e administração de perfis com diferentes permissões, atribuições e
  responsabilidades, conforme `docs/plano-de-trabalho-fase-ii.md`, seção 3.1.
- **CONFIRMADO, fonte oficial**: O RF004 exige controle de acesso segundo perfil, instituição e
  participação no processo. RF034 exige logs e auditoria, e RF044 exige isolamento entre
  laboratórios durante etapas restritas.
- **DECISÃO TÉCNICA REGISTRADA**: O backend aplica RBAC e policies de autorização; controles de
  interface não substituem essa validação, conforme
  `docs/planejamento/gestao-de-usuarios.md`.
- **CONFIRMADO, constituição 1.0.0**: Toda ação e dado protegido exige autenticação e
  autorização no backend. Features futuras devem definir isolamento e cegamento antes da
  implementação desses controles.
- **CONFIRMADO, artefatos e implementação existentes**: As features 001 e 002 fornecem contas cadastradas e uma
  identidade autenticada sem perfil ou permissão. Esta feature depende desses contratos.
- **CONFIRMADO, implementação atual**: A conta ativa usa exclusão lógica, e a sessão identifica a
  conta a cada pedido. O código atual ainda não possui perfis ou permissões.
- **CONFIRMADO NO MATERIAL COMPLEMENTAR**: O protótipo mostra tarefas e visões diferentes para
  perfis simulados, além de uma área de configuração para Administrador. O protótipo não comprova
  autorização no backend.
- **DECISÃO da Session 2026-08-19**: Uma conta pode acumular perfis e recebe a união cumulativa
  de suas permissões. O modelo não inclui negação explícita, hierarquia ou herança entre perfis.
- **DECISÃO da Session 2026-08-19**: A implantação indica uma conta existente e ativa para receber
  o primeiro perfil Administrador. A inicialização falha se a conta estiver ausente ou inativa e
  não promove outra conta. O plano técnico definirá o mecanismo sem criar cadastro administrativo
  público.
- **DECISÃO da Session 2026-08-19**: Somente mudanças de RBAC concluídas integram a rastreabilidade
  persistente desta feature. A recusa 403 após a verificação de permissão fica em registro
  operacional; uma feature posterior definirá a trilha geral de auditoria, sua retenção e sua consulta.
- **DECISÃO da Session 2026-08-19**: Os nove papéis do Plano formam o catálogo inicial de perfis,
  possuem nomes protegidos e aceitam mudanças de permissão. Administradores podem criar perfis
  adicionais. Somente Administrador recebe permissões de RBAC nesta etapa; features posteriores
  definem permissões de domínio para os outros perfis.
- **INFERÊNCIA delimitadora**: Termos adicionais do protótipo, como BraCVAM, Grupo de Seleção de
  Amostras, Laboratório Líder e Especialistas Temáticos do Comitê ADHOC, podem representar perfis
  ou atribuições contextuais. Esta feature não os transforma em perfis canônicos sem validação da
  equipe.

## Scope and Traceability

| Fonte | Natureza | Cobertura nesta feature |
|---|---|---|
| RF002 | Requisito oficial | Cobertura integral da gestão de perfis, composição de permissões e atribuição de perfis a contas. |
| RF004 | Requisito oficial | Cobertura da autorização global por perfil. Instituição e participação ficam bloqueadas até as features de RF003 e RF005. |
| RF034 | Requisito oficial transversal | Registro do responsável e do momento das mudanças de RBAC; a trilha geral de auditoria fica fora do escopo. |
| RF044 | Requisito oficial transversal | Impede que o perfil global contorne o futuro isolamento laboratorial; a matriz e o cegamento pertencem às features do processo. |
| Feature 001 | Especificação existente | Preserva cadastro, exclusão lógica e contratos públicos. |
| Feature 002 | Especificação existente | Reutiliza a identidade autenticada e preserva login, sessão e logout. |
| Protótipo | Fonte complementar | Usa somente os papéis e diferenças de visão confirmados como referência; não presume segurança demonstrada. |
| Pendências documentadas | Controle de lacunas | Mantém fora do escopo a equivalência entre papéis, a matriz contextual, o cegamento e a revelação de identidades. |

## Out of Scope

- Administração dos dados ou do estado de contas de usuário.
- Vínculos entre contas, instituições e laboratórios do RF003.
- Designações por processo do RF005 e conflitos de interesse do RF006.
- Permissões funcionais dos módulos de submissão, IA, aprovação, ensaios ou avaliação.
- Regras de isolamento por laboratório, cegamento, revelação de identidade e acesso por fase do processo.
- Hierarquia de perfis, negações explícitas, permissões por campo ou linguagem genérica de regras.
- Trilhas imutáveis, retenção e consulta geral de eventos de auditoria.
- Persistência de recusas de autorização na trilha de mudanças de RBAC.
- Mudanças no ciclo de vida da sessão, recuperação de conta, confirmação de e-mail, 2FA ou mensageria.
