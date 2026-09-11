# Feature Specification: Kanban de Pendências e Revisão de Cargos

**Feature Branch**: `018-kanban-activities-roles`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Quero desenvolver um kanban para as atividades, pense que sou o BraCVAM tenho 300 métodos associados, preciso abrir o kanban e entender o que esta associado a mim nas colunas: `Não Iniciado`, `Em Andamento`, `Em Atraso`, `Concluído` sem ter que abrir método por método. O desenvolvimento do Kanban também exige revisão em como funciona os cargos hoje em dia, garanta que o comportamento é o seguinte: Estados globais: Padrão, Admin, BraCVAM. Admin e Bracvam podem ver todos os processos, e gerenciam a plataforma como um todo. Os demais cargos são atribuidos durante o percurso de uma validação, e são validos no contexto daquela validação, posso ser Proponente em um e Gestor em outro. Ao final quero conseguir listar tudo que existe de pendêcias de uma forma que me dê o contexto do que preciso fazer agora o que vem antes e o que já esta pronto."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver todas as minhas pendências em um só lugar (Priority: P1)

Como integrante da equipe BraCVAM responsável por dezenas ou centenas de métodos em
andamento ao mesmo tempo, quero abrir um único quadro Kanban que já mostre todas as
atividades relevantes para mim em todos os métodos associados, organizadas em
`Não Iniciado`, `Em Andamento`, `Em Atraso` e `Concluído`, para entender minha carga de
trabalho de uma só vez, sem precisar abrir método por método.

**Why this priority**: é o pedido direto e explícito desta feature; sozinho já entrega
valor completo (MVP) mesmo antes de qualquer refinamento de contexto adicional.

**Independent Test**: Com um usuário de cargo global BraCVAM (ou Admin) associado a
centenas de métodos em estágios variados, abrir o Kanban mostra todas as atividades
relevantes já distribuídas nas quatro colunas, sem nenhuma navegação prévia para dentro
de um método individual.

**Acceptance Scenarios**:

1. **Given** um usuário BraCVAM com 300 métodos associados em estágios variados,
   **When** ele abre o Kanban, **Then** toda atividade sob sua responsabilidade (ou, para
   Admin/BraCVAM, toda atividade da plataforma) aparece em exatamente uma das quatro
   colunas, identificada com o método/processo a que pertence.
2. **Given** uma atividade que ainda não começou (bloqueada por uma etapa anterior não
   concluída), **When** o Kanban é exibido, **Then** ela aparece em `Não Iniciado`.
3. **Given** uma atividade aguardando ação de alguém, **When** o Kanban é exibido,
   **Then** ela aparece em `Em Andamento`.
4. **Given** uma atividade finalizada, **When** o Kanban é exibido, **Then** ela aparece
   em `Concluído`, claramente distinta do trabalho ativo.
5. **Given** um usuário sem nenhuma atividade associada, **When** ele abre o Kanban,
   **Then** cada coluna mostra um estado vazio, nunca um erro.

---

### User Story 2 - Cargos globais e cargos por processo funcionam como esperado (Priority: P1)

Como qualquer usuário da plataforma, quero que meu cargo global (`Padrão`, `Admin` ou
`BraCVAM`) determine se vejo a plataforma inteira ou não, e que os demais cargos
(Proponente, Gestor, etc.) só valham dentro do processo específico em que fui designado
— podendo ser, por exemplo, Proponente em um método e Gestor em outro ao mesmo tempo —
para que o Kanban (e qualquer outra tela) sempre reflita exatamente o que devo ver e
fazer.

**Why this priority**: é um pré-requisito estrutural explicitamente exigido junto com o
Kanban; sem essa correção, o Kanban tanto pode vazar dados (usuário comum vendo métodos
alheios) quanto esconder dados (Admin/BraCVAM não vendo tudo). P1 porque a correção do
Kanban depende diretamente disso.

**Independent Test**: Criar um usuário com cargo global `Padrão`, atribuído como
Proponente apenas no Método A e como Gestor apenas no Método B; confirmar que ele só
enxerga/atua nesses dois métodos, cada um com as permissões do cargo correspondente, e
não enxerga o Método C. Separadamente, confirmar que um usuário `Admin` ou `BraCVAM`
enxerga e gerencia todos os métodos, incluindo A, B e C.

**Acceptance Scenarios**:

1. **Given** um usuário `Padrão` com atribuição ativa apenas como Proponente no Método A,
   **When** ele consulta suas pendências/Kanban, **Then** somente atividades do Método A
   aparecem, dentro dos limites que o cargo de Proponente permite.
2. **Given** o mesmo usuário também tem atribuição ativa como Gestor no Método B,
   **When** ele visualiza o Kanban, **Then** atividades do Método A (como Proponente) e
   do Método B (como Gestor) aparecem juntas, cada uma identificada com o cargo aplicável
   naquele método.
3. **Given** um usuário com cargo global `Admin` ou `BraCVAM`, **When** ele consulta
   qualquer método ou o Kanban, **Then** todos os métodos da plataforma estão visíveis e
   gerenciáveis, independente de ter ou não atribuição específica naquele método.
4. **Given** um usuário `Padrão` sem atribuição ativa no Método C, **When** ele tenta
   consultar o Método C ou suas atividades, **Then** o acesso é negado.
5. **Given** uma atribuição de um usuário em um método é encerrada/revogada, **When** ele
   consulta o Kanban novamente, **Then** as atividades daquele método deixam de aparecer
   para ele, a menos que outra atribuição ativa ainda se aplique.
6. **Given** um método com duas pessoas atribuídas simultaneamente ao cargo de
   Proponente, **When** qualquer uma das duas consulta o Kanban, **Then** a pendência
   daquele cargo aparece para ambas — a atividade pertence ao cargo, não a uma pessoa
   específica dentre as que o exercem.

---

### User Story 3 - Lista de pendências com contexto de ordem (Priority: P2)

Como usuário responsável por atividades em andamento, quero, a partir do Kanban,
entender rapidamente para cada pendência o que preciso fazer agora, o que precisa
acontecer antes (e por quem) e o que já foi concluído, para priorizar meu trabalho sem
precisar reconstruir mentalmente a ordem das etapas de cada método.

**Why this priority**: aprofunda o valor entregue pela User Story 1 com o contexto de
ordem/dependência pedido explicitamente ao final da solicitação; o Kanban básico (US1)
já é utilizável sem isso, por isso fica em P2.

**Independent Test**: Abrir uma atividade bloqueada e verificar que o sistema mostra qual
atividade/decisão anterior precisa acontecer primeiro e quem é responsável por ela, sem
precisar reconstruir o histórico do método inteiro. Abrir uma atividade acionável agora e
verificar que ela está claramente marcada como "sua vez".

**Acceptance Scenarios**:

1. **Given** uma atividade em `Não Iniciado` por depender de uma etapa anterior não
   concluída, **When** o usuário a inspeciona, **Then** o sistema mostra qual
   atividade/decisão precisa acontecer primeiro e seu responsável/status atual.
2. **Given** uma atividade em `Em Andamento` sob responsabilidade do usuário, **When** ele
   a visualiza, **Then** ela está claramente marcada como acionável agora (distinta de
   uma atividade em andamento sob responsabilidade de outra pessoa).
3. **Given** uma atividade em `Concluído`, **When** o usuário a visualiza, **Then** ele
   consegue ver que está finalizada e, ao menos aproximadamente, quando.

---

### Edge Cases

- O que acontece quando um método não tem nenhuma pendência atribuível a uma pessoa no
  momento (ex.: aguardando uma etapa automática, como a pré-avaliação assíncrona por
  IA)? → A atividade aparece em `Não Iniciado`/bloqueada com o motivo textual da espera,
  nunca é omitida do Kanban.
- O que acontece quando a única atribuição de um usuário em um método é revogada
  enquanto ele ainda tem um cartão aberto na tela? → Na próxima atualização/consulta, o
  item some do Kanban dele (User Story 2, cenário 5).
- Como o Kanban permanece utilizável quando um único usuário (Admin/BraCVAM) acumula
  atividades de centenas de métodos (ex.: 300) simultaneamente, incluindo um volume
  potencialmente grande em `Concluído`?
- O que acontece com uma atividade cujo método não declara prazo (SLA) para aquela
  etapa? → Ela nunca é classificada como `Em Atraso`, independente de há quanto tempo
  está em andamento — esse é o comportamento padrão de qualquer atividade sem prazo
  declarado.
- O que acontece hoje quando uma atividade é criada sem que exista, no momento, ninguém
  atribuído ao cargo responsável por ela? → A revisão desta spec (User Story 2) exige que
  isso deixe de ser possível: toda atividade nasce associada a um cargo válido para
  aquele método (declarado no template), nunca "solta"; se ninguém ocupa esse cargo
  ainda, a atividade permanece visível para quem tiver permissão de gerenciar
  atribuições naquele método, sinalizando a lacuna, em vez de ficar sem responsável
  algum.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST oferecer, para o usuário autenticado, uma visão Kanban
  consolidada das atividades pendentes/em andamento/concluídas em todos os métodos
  associados a ele, sem exigir a abertura individual de cada método.
- **FR-002**: O sistema MUST classificar cada atividade relevante para o usuário em
  exatamente uma das quatro colunas: `Não Iniciado`, `Em Andamento`, `Em Atraso` ou
  `Concluído`.
- **FR-003**: Para um usuário com cargo global `Admin` ou `BraCVAM`, o Kanban MUST
  incluir atividades de todos os métodos da plataforma, independente de atribuição
  específica em cada um.
- **FR-004**: Para um usuário com cargo global `Padrão`, o Kanban MUST incluir somente
  atividades de métodos em que ele possua, no momento, ao menos uma atribuição ativa e
  não revogada (em qualquer cargo contextual).
- **FR-005**: O sistema MUST suportar um mesmo usuário mantendo cargos contextuais
  diferentes em métodos diferentes simultaneamente (ex.: Proponente no Método A, Gestor
  no Método B), refletindo em cada atividade o cargo aplicável naquele método específico.
- **FR-006**: O sistema MUST impedir que um usuário de cargo global `Padrão` visualize
  ou atue sobre um método (ou suas atividades) no qual não possua atribuição ativa,
  independente do status desse método.
- **FR-007**: O sistema MUST tratar atividades em `Concluído` como registro histórico
  somente leitura, visualmente distinto do trabalho ativo.
- **FR-008**: O sistema MUST classificar uma atividade como `Em Atraso` quando o método
  declara, na definição do template daquela etapa, um prazo máximo (SLA) e a atividade
  está em andamento há mais tempo do que esse prazo desde que foi liberada. Uma etapa
  cujo template não declara prazo MUST default para nunca ser classificada como
  `Em Atraso`, independente de há quanto tempo está em andamento.
- **FR-008a**: A definição do prazo (SLA) de cada etapa MUST ser parte da definição
  declarativa do template do método (a mesma fonte que já declara fases, atividades,
  dependências e formulários), e não um valor configurável por atividade individual via
  API/tela em tempo de execução.
- **FR-009**: Para uma atividade em `Não Iniciado` por dependência, o sistema MUST
  apresentar o motivo do bloqueio, incluindo qual atividade/decisão anterior precisa
  acontecer primeiro.
- **FR-010**: Para uma atividade em `Em Andamento` que exige ação do usuário atual, o
  sistema MUST distingui-la claramente de uma atividade em andamento sob
  responsabilidade de outra pessoa/cargo.
- **FR-011**: O sistema MUST refletir, na consulta seguinte, qualquer mudança em uma
  atribuição por processo (concessão ou revogação) ou no status de uma atividade,
  sem depender de dado desatualizado em cache.
- **FR-012**: O sistema MUST permanecer utilizável (legível e navegável) para um usuário
  com atividades espalhadas por centenas de métodos (ex.: 300) sem exigir paginação
  método por método para montar a visão.
- **FR-013**: O sistema MUST permitir que, a partir de um cartão do Kanban, o usuário
  identifique a qual método/processo ele pertence e navegue até o detalhe completo
  daquele método.
- **FR-014**: O sistema MUST aplicar a mesma regra de visibilidade (FR-003/FR-004) em
  toda consulta/listagem de processos já existente na plataforma, não somente no Kanban
  — corrigindo a lacuna hoje existente em que um usuário autenticado sem nenhuma
  atribuição em um método ainda consegue consultá-lo fora dos estágios exclusivos do
  proponente.
- **FR-015**: O sistema MUST apresentar um estado vazio (não um erro) quando o usuário
  não tiver nenhuma atividade associada em uma determinada coluna.
- **FR-016**: O sistema MUST associar toda atividade/pendência a um cargo (global, no
  caso de Admin/BraCVAM, ou contextual, no caso dos demais), nunca diretamente a uma
  pessoa específica; uma pendência MUST ser resolvível por qualquer pessoa que ocupe,
  no momento, o cargo responsável naquele método, mesmo quando mais de uma pessoa ocupa
  o mesmo cargo simultaneamente.
- **FR-017**: O sistema MUST revalidar, como parte desta entrega, se alguma atividade
  hoje é criada vinculada diretamente a uma pessoa específica (em vez de somente ao
  cargo) e corrigir esse comportamento onde encontrado, preservando a compatibilidade
  com processos já em andamento.

### Key Entities *(include if feature involves data)*

- **Atividade do Processo (Pendência)**: unidade de trabalho representada como um
  cartão do Kanban; pertence a um único método/processo, tem um status e um cargo
  responsável — nunca uma pessoa específica — e, quando o template declara um prazo
  para a etapa, um critério de atraso.
- **Processo (Método)**: instância de um método de validação em andamento, com um
  código/título identificador; agrupa as atividades exibidas no Kanban por contexto.
- **Cargo Global**: `Padrão`, `Admin` ou `BraCVAM` — determina o alcance de visibilidade
  e gestão do usuário em toda a plataforma, independente de qualquer método específico.
- **Atribuição por Processo (Cargo Contextual)**: papel (ex.: Proponente, Gestor) que um
  usuário exerce dentro de um método específico, válido apenas enquanto ativo naquele
  método; um mesmo usuário pode ter atribuições diferentes, simultaneamente, em métodos
  diferentes.
- **Critério de Atraso (SLA de Etapa)**: prazo máximo, declarado na definição do
  template do método para uma etapa específica, usado para determinar quando uma
  atividade em andamento passa a ser considerada `Em Atraso`; uma etapa sem prazo
  declarado nunca entra em atraso.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um usuário BraCVAM/Admin com 300 métodos associados consegue ver, em uma
  única tela, todas as atividades atualmente relevantes organizadas por status, sem abrir
  nenhum método individualmente.
- **SC-002**: Um usuário com cargos contextuais diferentes em métodos diferentes vê, em
  um só lugar, 100% das atividades relevantes a esses cargos e 0% das atividades de
  métodos em que não possui nenhuma atribuição (exceto Admin/BraCVAM).
- **SC-003**: Para qualquer atividade em `Não Iniciado`, o usuário identifica o que
  precisa acontecer antes sem sair da visão do Kanban, em no máximo uma interação
  adicional (ex.: expandir o cartão).
- **SC-004**: 100% dos métodos hoje visíveis para usuários `Padrão` sem nenhuma
  atribuição neles deixam de ser visíveis a esses usuários em qualquer tela/consulta da
  plataforma, não somente no Kanban.
- **SC-005**: Usuários conseguem, sem ambiguidade, distinguir uma atividade `Em Atraso`
  de uma atividade normalmente `Em Andamento`, com base no prazo declarado no template
  do método (quando existente).
- **SC-006**: 0% das atividades/pendências do sistema ficam vinculadas diretamente a uma
  pessoa específica sem passar por um cargo — toda pendência é resolvível por qualquer
  pessoa que ocupe o cargo responsável naquele método.

## Assumptions

- Cada cartão do Kanban representa uma atividade (pendência) dentro de um método, não o
  método inteiro; o cartão mostra contexto suficiente do método (código/título) para que
  o usuário não precise abri-lo só para se orientar.
- "Associado a mim" significa, para `Admin`/`BraCVAM`, literalmente todo método da
  plataforma; para os demais cargos, todo método em que o usuário tenha ao menos uma
  atribuição ativa e não revogada, em qualquer cargo contextual.
- As colunas `Não Iniciado`, `Em Andamento` e `Concluído` derivam dos estados de
  atividade já rastreados hoje pelo sistema (bloqueada/ainda não alcançada → `Não
  Iniciado`; liberada ou em andamento aguardando alguém → `Em Andamento`; finalizada →
  `Concluído`); `Em Atraso` é o único conceito novo, calculado a partir do prazo (SLA)
  declarado por etapa no template do método, quando existente.
- Um método antigo, cujo template ainda não declara prazo algum para nenhuma etapa,
  simplesmente nunca produz atividades `Em Atraso` — não é necessário migrar templates
  existentes para que o Kanban funcione.
- Revogar uma atribuição em um método remove a visibilidade daquele método para o
  usuário imediatamente na consulta seguinte (não é necessário aviso ativo/push).
- A demonstração desta feature, conforme o padrão do projeto, usa uma massa de dados de
  seed suficiente para simular um usuário BraCVAM com centenas de métodos associados em
  estágios variados, sem nenhum endpoint criado exclusivamente para viabilizar a
  demonstração.
- A revalidação de cargos (FR-016/FR-017) é uma revisão do comportamento atual, não uma
  reformulação do modelo de atribuições por processo já existente (Proponente, Gestor
  etc.) — o objetivo é garantir que nenhuma pendência fique vinculada a uma pessoa em
  vez de a um cargo, mantendo o mecanismo de atribuição por processo como está.
- A revisão de cargos aqui descrita corrige uma lacuna hoje existente: a consulta geral
  de métodos não restringe, atualmente, a visibilidade de processos fora dos estados
  exclusivos do proponente a quem participa deles — o comportamento-alvo é Admin/BraCVAM
  vendo tudo e os demais cargos vendo apenas onde têm atribuição ativa.
