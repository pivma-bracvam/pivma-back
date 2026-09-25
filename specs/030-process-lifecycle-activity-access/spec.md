# Feature Specification: Ciclo de vida do processo e acesso por atividade

**Feature Branch**: `feat/030-process-lifecycle-activity-access`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Remover o status de fluxo do processo (`SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE`, `PLANNING`) e manter um campo explícito de ciclo de vida, o único exposto pela API. Triagem é uma atividade, não um status; Planning é uma etapa, não um status; na etapa seguinte haverá atividades em paralelo. A visibilidade deixa de depender do status do processo: cada usuário vê as atividades atribuídas a ele. Cada atividade concede 'pode ver' e 'pode editar' a cargos (nunca a usuários), de forma expansível para mais granularidade. Submissão: o cargo proponente vê e edita. Pré-avaliação por IA: o proponente continua vendo (lista de cargos permitidos) e a IA vê e edita. Triagem: BraCVAM vê e edita. Todas as atividades precisam desse mecanismo."

## Contexto

Hoje o processo guarda uma única coluna `status` com dois significados
misturados:

- **Posição no fluxo**: `SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE` e
  `PLANNING`. É uma cópia do estado das fases e atividades, que o motor mantém
  sincronizada à mão. Ela não representa atividades paralelas e o `PLANNING`
  nunca muda depois da triagem.
- **Ciclo de vida**: `CLOSED`, `CANCELLED` e `ARCHIVED`. Diz se o processo está
  vivo ou encerrado e bloqueia exclusão, arquivamento e mudança de
  participantes.

A posição no fluxo também decide quem vê o processo. Em `SUBMISSION` e
`AI_PRE_EVALUATION` só o proponente enxerga; nos demais estados, qualquer
participante enxerga tudo. Essa regra é global ao processo e não funciona
quando atividades diferentes têm públicos diferentes ao mesmo tempo.

Esta feature separa as duas coisas:

1. O processo passa a ter só o ciclo de vida (`OPEN`, `CLOSED`, `CANCELLED`,
   `ARCHIVED`).
2. A posição no fluxo passa a ser lida das fases e atividades, que já existem.
3. O acesso passa a ser declarado por atividade, como concessões de "ver" e
   "editar" a cargos.

O Plano de Trabalho da Fase II sustenta a direção: o RF030 pede "etapas
concluídas, em andamento, pendentes e futuras", uma visão por etapa e não por
um rótulo único do processo.

## Clarifications

### Session 2026-09-25

- Q: Participantes do processo sem concessão em nenhuma atividade veem o
  processo? → A: Veem o cabeçalho e o ciclo de vida, sem nenhuma atividade
  (FR-015).
- Q: Administrador e BraCVAM mantêm visão total? → A: Sim, como um cargo local
  atribuído automaticamente em todo processo, com ver habilitado em todas as
  atividades. Segue a mesma regra de concessão, sem exceção (FR-016).
- Q: O proponente vê a atividade de triagem? → A: Não. Uma nova atividade de
  revisão do retorno, comum aos retornos da IA e do BraCVAM, mostra todo o
  conteúdo ao proponente, que escolhe como seguir; conforme a escolha, o sistema
  reabre a submissão como rascunho, encaminha à triagem ou encerra o processo
  (User Story 4, FR-035 a FR-040).
- Q: Quais resultados da triagem abrem a revisão do retorno? → A: Só
  `NEEDS_REVISION`. Rejeição fecha o processo na hora; aprovação conclui a
  fase 1.
- Q: O `admin` edita a triagem? → A: Não. Só o `bracvam` edita; o `admin` vê
  (FR-026).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - O processo expõe só o ciclo de vida (Priority: P1)

Quem consulta ou lista processos vê se o processo está aberto, encerrado,
cancelado ou arquivado. Nenhuma resposta traz mais uma posição de fluxo como
"triagem" ou "planejamento".

**Why this priority**: É a mudança de contrato que as demais dependem. Sem ela,
o rótulo de fluxo continua sendo a fonte de verdade e o paralelismo segue
impossível.

**Independent Test**: Criar um processo, levá-lo da submissão à triagem aprovada
e confirmar que detalhe, listagem e respostas de decisão mostram o ciclo de
vida `OPEN` em todos os passos, e `CLOSED` após uma triagem rejeitada.

**Acceptance Scenarios**:

1. **Given** um usuário que acabou de criar um processo, **When** ele consulta
   o detalhe, **Then** o ciclo de vida é `OPEN` e não há campo de posição de
   fluxo.
2. **Given** um processo com submissão enviada e aguardando triagem, **When**
   qualquer usuário autorizado consulta o detalhe, **Then** o ciclo de vida é
   `OPEN`.
3. **Given** um processo em triagem, **When** o BraCVAM aprova, **Then** a
   resposta da decisão informa o ciclo de vida `OPEN` e a fase 1 aparece como
   concluída.
4. **Given** um processo em triagem, **When** o BraCVAM rejeita, **Then** o
   ciclo de vida passa a `CLOSED`.
5. **Given** processos com ciclos de vida diferentes, **When** um usuário lista
   filtrando por ciclo de vida, **Then** só retornam os processos daquele ciclo.
6. **Given** um filtro com valor de posição de fluxo antigo (por exemplo,
   `TRIAGE`), **When** a listagem é chamada, **Then** a requisição é recusada
   como valor inválido.

---

### User Story 2 - Cada usuário vê e edita só as atividades concedidas ao seu cargo (Priority: P1)

Cada atividade declara quais cargos podem vê-la e quais podem editá-la. Um
usuário acessa uma atividade quando tem, no processo ou globalmente, um cargo
com a concessão correspondente. A concessão vale para o cargo, nunca para um
usuário específico.

Na fase 1:

| Momento | Proponente | IA | BraCVAM | Admin |
|---|---|---|---|---|
| Proponente preenchendo a submissão | vê e edita | — | vê | vê |
| Submissão enviada, aguardando pré-avaliação por IA | vê | vê e edita (a avaliação) | vê | vê |
| Aguardando triagem | vê a própria submissão | — | vê e edita a triagem | vê |
| Retorno ao proponente (User Story 4) | vê e edita | — | vê | vê |

Administrador e BraCVAM veem todas as atividades de todos os processos. Isso
não é uma exceção à regra: é uma concessão de ver que toda atividade dá aos
cargos globais `admin` e `bracvam` (FR-016).

**Why this priority**: É a regra de segurança que substitui a visibilidade
baseada no status. Sem ela, remover o status abre ou fecha o acesso de forma
errada.

**Independent Test**: Com dois usuários de cargos diferentes no mesmo processo,
verificar para cada atividade que quem não tem a concessão não a vê nem a
edita, e que quem tem a concessão a vê e a edita.

**Acceptance Scenarios**:

1. **Given** um processo recém-criado, **When** o proponente abre a atividade
   de submissão, **Then** ele vê e salva rascunho.
2. **Given** um processo recém-criado, **When** um participante sem o cargo
   proponente e sem cargo global tenta abrir a submissão, **Then** ele vê o
   cabeçalho do processo, mas a atividade não é encontrada para ele.
3. **Given** um segundo usuário que recebe o cargo proponente no mesmo processo,
   **When** ele abre a submissão, **Then** ele vê e edita, pois a concessão é do
   cargo.
4. **Given** um usuário cujo cargo proponente foi revogado, **When** ele tenta
   abrir a submissão, **Then** perde o acesso imediatamente.
5. **Given** uma submissão enviada e aguardando a pré-avaliação por IA, **When**
   o proponente abre a submissão, **Then** ele vê os valores enviados e não
   consegue editar.
6. **Given** uma submissão aguardando a pré-avaliação por IA, **When** a IA
   conclui, **Then** o resultado é gravado e a submissão segue para a triagem
   (positivo) ou volta ao proponente (negativo), como hoje.
7. **Given** uma submissão aguardando triagem, **When** o BraCVAM abre a
   triagem, **Then** ele vê a submissão e registra avaliações e decisão.
8. **Given** uma submissão aguardando triagem, **When** o proponente tenta
   registrar uma decisão de triagem, **Then** a ação é recusada por falta de
   concessão de edição.
9. **Given** um usuário, **When** ele lista suas tarefas, **Then** só aparecem
   tarefas de atividades que o seu cargo pode ver.
10. **Given** um processo com a submissão em rascunho, **When** um usuário
    BraCVAM ou Admin abre a submissão, **Then** ele vê o rascunho e não consegue
    editá-lo.

---

### User Story 3 - Toda atividade de todo template declara as concessões (Priority: P1)

Cada atividade dos cinco templates canônicos (18 atividades hoje) declara as
concessões de ver e editar. Um template sem concessão em alguma atividade não é
aceito na carga dos templates.

**Why this priority**: O usuário exigiu que todas as atividades tenham o
mecanismo. Uma atividade sem concessão ficaria inacessível ou, pior, aberta.

**Independent Test**: Carregar os templates canônicos e confirmar que toda
atividade tem ao menos um cargo com concessão de edição; carregar um template
com uma atividade sem concessões e confirmar a recusa.

**Acceptance Scenarios**:

1. **Given** os cinco templates canônicos, **When** a carga de templates roda,
   **Then** toda atividade termina com as concessões declaradas.
2. **Given** um template com uma atividade sem nenhum cargo de edição, **When**
   a carga roda, **Then** ela falha indicando o template e a atividade.
3. **Given** um template que concede a um cargo fora do vocabulário de cargos,
   **When** a carga roda, **Then** ela falha indicando o cargo inválido.
4. **Given** uma atividade que declara só o cargo responsável, **When** a carga
   roda, **Then** esse cargo recebe ver e editar.

---

### User Story 4 - O proponente revisa o retorno da IA ou do BraCVAM (Priority: P2)

Quando a pré-avaliação por IA ou a triagem devolvem a submissão, o proponente
recebe uma atividade de **revisão do retorno**. Nela ele lê todo o conteúdo do
retorno (resultado da IA ou decisão e justificativa do BraCVAM) e escolhe como
seguir. Conforme a escolha, o sistema reabre a submissão como rascunho ainda
não enviado, encaminha para a triagem humana ou encerra o processo.

Essa atividade substitui a volta do processo ao status `SUBMISSION`. O retorno
passa a ser uma etapa visível do fluxo, com dono (cargo `proponent`) e decisão
registrada.

**Why this priority**: Dá ao proponente acesso ao resultado sem conceder a ele
a atividade de triagem (FR-029). Também remove a última transição que hoje
"volta" o status do processo.

**Independent Test**: Levar a submissão a um retorno negativo da IA e a um
pedido de revisão da triagem. Em cada caso, confirmar que surge a atividade de
revisão do retorno para o proponente, que ele vê o conteúdo do retorno e que
cada escolha produz o efeito esperado.

**Acceptance Scenarios**:

1. **Given** uma pré-avaliação por IA negativa ou com falha, **When** ela
   conclui, **Then** surge a atividade de revisão do retorno para o proponente,
   com o resultado da IA, e a submissão continua travada.
2. **Given** uma triagem com pedido de revisão, **When** o BraCVAM decide,
   **Then** surge a atividade de revisão do retorno para o proponente, com a
   decisão e a justificativa.
3. **Given** a revisão do retorno aberta, **When** o proponente escolhe revisar
   a submissão, **Then** a revisão do retorno é concluída e uma nova execução da
   submissão abre como rascunho, preenchida com os valores anteriores.
4. **Given** a revisão do retorno aberta após a IA, **When** o proponente
   contesta o resultado, **Then** a submissão segue para a triagem humana, como
   a revisão direta faz hoje.
5. **Given** a revisão do retorno aberta, **When** o proponente escolhe
   desistir, **Then** o processo passa ao ciclo de vida `CLOSED`, com o motivo
   registrado.
6. **Given** a revisão do retorno aberta, **When** outro cargo que não o
   proponente tenta registrar a escolha, **Then** a ação é recusada.
7. **Given** o fluxo de retorno por IA, **When** a atividade de revisão do
   retorno é aberta, **Then** o BraCVAM e o Admin a veem, mas não a editam.
8. **Given** uma triagem rejeitada ou aprovada, **When** o BraCVAM decide,
   **Then** nenhuma revisão do retorno é aberta: a rejeição encerra o processo
   (`CLOSED`) na hora e a aprovação conclui a fase 1, como hoje.

---

### User Story 5 - Fases e atividades guardam onde o processo está (Priority: P2)

Os estados de fase e atividade (não iniciada, bloqueada, em andamento,
concluída, cancelada) passam a ser a única fonte da posição no fluxo e ficam
corretos com atividades em paralelo. Pela API, o usuário acompanha essa posição
pelas tarefas que pode ver; o processo expõe só o ciclo de vida (decisão do
usuário). Uma visualização de fases pela API (RF030) fica para uma feature
futura.

**Why this priority**: Substitui a informação que o rótulo de fluxo dava. Pode
vir depois do contrato e da regra de acesso, porque as fases e atividades já
existem.

**Independent Test**: Aprovar a triagem e verificar, no banco, que a fase 1 está
concluída e que nenhuma atividade da fase seguinte está em andamento sem ter
sido liberada; com duas atividades liberadas em paralelo, verificar em
`/tasks` que cada usuário recebe só as tarefas das atividades que vê.

**Acceptance Scenarios**:

1. **Given** uma triagem aprovada, **When** o estado do processo é verificado,
   **Then** a fase 1 está concluída e o ciclo de vida é `OPEN`.
2. **Given** um processo com duas atividades liberadas em paralelo, **When** um
   usuário com concessão nas duas lista suas tarefas, **Then** recebe as tarefas
   das duas, e as duas atividades estão em andamento.
3. **Given** um processo com duas atividades em andamento, **When** um usuário
   com concessão em só uma delas lista suas tarefas, **Then** recebe apenas a
   tarefa da atividade concedida.

---

### User Story 6 - Processos existentes migram sem perder o ciclo de vida (Priority: P2)

Processos criados antes desta feature mantêm o comportamento. Os que estavam em
posição de fluxo passam a `OPEN`; os encerrados, cancelados e arquivados
continuam como estavam.

**Why this priority**: Sem migração, processos reais ficam com valores que a
nova regra não reconhece.

**Independent Test**: Criar processos em cada um dos sete valores antigos,
aplicar a migração e conferir o ciclo de vida resultante e o acesso de cada
cargo.

**Acceptance Scenarios**:

1. **Given** processos em `SUBMISSION`, `AI_PRE_EVALUATION`, `TRIAGE` e
   `PLANNING`, **When** a migração roda, **Then** todos ficam `OPEN`.
2. **Given** processos em `CLOSED`, `CANCELLED` e `ARCHIVED`, **When** a
   migração roda, **Then** mantêm o mesmo ciclo de vida.
3. **Given** a migração aplicada, **When** ela é revertida, **Then** cada
   processo volta a uma posição de fluxo coerente com o estado das suas
   atividades.
4. **Given** um processo existente aguardando triagem, **When** a migração roda,
   **Then** o BraCVAM continua conseguindo decidir a triagem.

### Edge Cases

- A IA termina a pré-avaliação depois de o processo ser cancelado: o resultado
  é descartado e nada avança, como hoje.
- Dois eventos concorrentes disputam a mesma submissão (IA concluindo, pedido de
  revisão direta, reprocessamento): só um avança; o outro recebe conflito. A
  trava hoje feita no status do processo passa a ser feita na pré-avaliação ou
  na atividade.
- A triagem pede revisão: abre a revisão do retorno para o proponente e a
  submissão só reabre quando ele escolher revisar. O BraCVAM mantém a visão da
  triagem já decidida.
- O proponente deixa a revisão do retorno aberta sem escolher: ela segue o
  prazo da atividade, como as demais tarefas; nada avança sozinho.
- Um usuário tem dois cargos no processo, com concessões diferentes na mesma
  atividade: vale a união (ver + editar).
- Um usuário tem concessão de ver mas não de editar e tenta salvar: recusa por
  falta de permissão, não por "atividade não encontrada".
- Um participante do processo sem concessão em nenhuma atividade (por
  exemplo, um `sponsor` na fase 1) vê o cabeçalho e o ciclo de vida do
  processo, e nenhuma atividade (FR-015).
- Um usuário sem nenhuma atribuição no processo e sem cargo global tenta abri-lo:
  "não encontrado".
- Tentativa de editar uma atividade concluída ou bloqueada, mesmo com concessão
  de edição: recusa por transição inválida, como hoje.
- Processo com ciclo de vida `CLOSED`, `CANCELLED` ou `ARCHIVED`: nenhuma
  concessão de edição vale; as de ver continuam valendo.
- Usuário com conflito de interesse vigente no processo: continua bloqueado
  independentemente das concessões, como hoje.

## Requirements *(mandatory)*

### Functional Requirements

**Ciclo de vida**

- **FR-001**: O processo MUST ter um único campo de ciclo de vida, com os
  valores `OPEN`, `CLOSED`, `CANCELLED` e `ARCHIVED`, e mais nenhum.
- **FR-002**: Todo processo MUST nascer `OPEN`.
- **FR-003**: As transições de ciclo de vida MUST ser apenas: `OPEN → CLOSED`
  (triagem rejeitada ou desistência na revisão do retorno), `OPEN → CANCELLED`
  (exclusão), `CLOSED → ARCHIVED` e
  `CANCELLED → ARCHIVED` (arquivamento). Qualquer outra MUST ser recusada.
- **FR-004**: O sistema MUST recusar, na própria gravação, qualquer valor de
  ciclo de vida fora dos quatro permitidos.
- **FR-005**: As regras que hoje dependem de estado terminal (exclusão,
  arquivamento, ações disponíveis, mudanças de participantes, avanço da
  pré-avaliação) MUST continuar com o mesmo comportamento, lendo o ciclo de
  vida.
- **FR-006**: Detalhe, listagem, criação, exclusão, arquivamento e resposta da
  decisão de triagem MUST expor o ciclo de vida e MUST NOT expor posição de
  fluxo. A resposta da revisão direta da pré-avaliação MUST NOT informar
  posição de fluxo.
- **FR-007**: O filtro de listagem por status MUST aceitar só valores de ciclo
  de vida e recusar valores antigos de fluxo. A regra atual de arquivados
  (ocultos por padrão e visíveis só a quem tem acesso de revisão) MUST ser
  mantida.
- **FR-008**: O sistema MUST NOT gravar posição de fluxo no processo. A posição
  MUST ser lida das fases e atividades.

**Acesso por atividade**

- **FR-009**: Cada atividade de template MUST declarar concessões de **ver** e
  de **editar**, cada uma como uma lista de cargos. Editar MUST implicar ver.
- **FR-010**: As concessões MUST ser dadas a cargos do vocabulário existente
  (cargos de processo e os cargos globais `admin` e `bracvam`), nunca a
  usuários.
- **FR-011**: Um usuário MUST ter concessão numa atividade quando possuir, de
  forma efetiva, um cargo listado: por atribuição ativa no processo (cargos de
  processo) ou por perfil global (cargos globais). A resolução MUST reaproveitar
  a regra de cargo efetivo já usada para tarefas.
- **FR-012**: Na ausência de declaração explícita, o cargo responsável da
  atividade MUST receber ver e editar. Declarações explícitas MUST poder
  acrescentar cargos só com ver.
- **FR-013**: A carga de templates MUST recusar atividades sem cargo de edição
  e concessões a cargos inexistentes, indicando template, atividade e cargo.
- **FR-014**: Todas as atividades dos cinco templates canônicos (as 18 atuais e
  a revisão do retorno de cada template) MUST ter concessões declaradas ou
  derivadas (FR-012) após a carga.
- **FR-015**: Um usuário MUST ver o cabeçalho de um processo (identificação,
  título, template e ciclo de vida) quando tiver atribuição ativa nele ou
  concessão de ver em ao menos uma de suas atividades. O conteúdo de cada
  atividade MUST seguir só as concessões. Quem não atende a nenhuma das duas
  condições MUST receber "não encontrado".
- **FR-016**: Toda atividade MUST conceder ver aos cargos globais `admin` e
  `bracvam`, além das concessões que declarar. Com isso, Administrador e BraCVAM
  veem todos os processos e todas as atividades, incluindo o rascunho do
  proponente, pela mesma regra de concessão que vale para os demais cargos. Essa
  concessão MUST ser aplicada pelo sistema e MUST NOT poder ser removida por um
  template. Editar continua exigindo concessão explícita.
- **FR-017**: Ler uma atividade, seu formulário, suas versões de submissão,
  seus anexos e suas tarefas MUST exigir concessão de ver. Quem não tem MUST
  receber "não encontrado", sem revelar a existência da atividade.
- **FR-018**: Salvar rascunho, enviar formulário, anexar, remover anexo,
  registrar avaliação de campo, decidir triagem e registrar a escolha na revisão
  do retorno MUST exigir concessão de editar
  na atividade correspondente. Quem vê mas não edita MUST receber "proibido".
- **FR-019**: Editar MUST valer só enquanto a atividade tiver uma execução
  aberta e o processo estiver `OPEN`. Fora disso, a recusa MUST ser por
  transição inválida, como hoje.
- **FR-020**: A listagem de tarefas MUST retornar só tarefas de atividades que o
  usuário pode ver.
- **FR-021**: A linha do tempo do processo MUST mostrar só eventos de atividades
  que o usuário pode ver, preservando o cegamento já aplicado hoje.
- **FR-022**: Conflito de interesse vigente MUST continuar bloqueando o usuário
  no processo, acima de qualquer concessão.

**Fase 1 (submissão, pré-avaliação e triagem)**

- **FR-023**: A atividade de submissão MUST conceder ver e editar ao cargo
  `proponent`.
- **FR-024**: Enquanto a pré-avaliação por IA estiver pendente, a submissão MUST
  ficar travada para edição e visível ao proponente.
- **FR-025**: A pré-avaliação por IA MUST agir como ator do sistema: ler a
  submissão e gravar o resultado da avaliação, sem depender de um cargo humano.
  Resultado positivo MUST seguir para a triagem, como hoje. Resultado negativo
  ou falha MUST abrir a revisão do retorno (FR-035), em vez de reabrir a
  submissão diretamente.
- **FR-026**: A atividade de triagem MUST conceder ver e editar ao cargo
  `bracvam`, e só a ele. O cargo `admin` MUST apenas ver a triagem: o
  Administrador deixa de conseguir decidi-la, mesmo tendo `triage.review`.
- **FR-027**: A decisão de triagem MUST exigir execução aberta da atividade de
  triagem, em vez de um status de processo.
- **FR-028**: A edição da submissão MUST exigir execução aberta da atividade de
  submissão, em vez de um status de processo.
- **FR-029**: O proponente MUST NOT ter concessão na atividade de triagem. Ele
  MUST receber o conteúdo do retorno pela revisão do retorno (FR-035 a FR-040).
- **FR-030**: A aprovação da triagem MUST concluir a fase 1 e liberar as
  atividades dependentes, sem gravar posição de fluxo no processo.

**Revisão do retorno**

- **FR-035**: A fase 1 de cada template MUST ter uma atividade de revisão do
  retorno, com cargo responsável `proponent` e concessão de ver e editar a ele.
- **FR-036**: A revisão do retorno MUST ser aberta quando a pré-avaliação por IA
  terminar negativa ou com falha, e quando a triagem terminar com pedido de
  revisão (`NEEDS_REVISION`). Rejeição e aprovação MUST NOT abri-la. Cada abertura MUST ser uma nova execução
  da atividade.
- **FR-037**: A revisão do retorno MUST mostrar ao proponente todo o conteúdo do
  retorno: o resultado da IA (itens e consolidação, como hoje) ou a decisão e a
  justificativa do BraCVAM. Avaliações por campo da triagem MUST seguir o
  cegamento já aplicado hoje.
- **FR-038**: Enquanto a revisão do retorno estiver aberta, a submissão MUST
  ficar travada para edição.
- **FR-039**: O proponente MUST registrar uma escolha, e o sistema MUST aplicar o
  efeito correspondente:
  - **Revisar a submissão**: abre uma nova execução da submissão como rascunho
    não enviado, preenchida com os valores da execução anterior.
  - **Contestar o resultado da IA** (só em retorno da IA): encaminha à triagem
    humana, com o mesmo efeito da revisão direta atual.
  - **Desistir**: passa o processo a `CLOSED`, com o motivo registrado.
- **FR-040**: A escolha MUST concluir a execução da revisão do retorno, gerar
  evento de auditoria com a escolha e a justificativa (se houver) e MUST ser
  aceita uma única vez por execução. Uma segunda escolha concorrente MUST receber
  conflito.

**Concorrência, auditoria e migração**

- **FR-031**: IA concluindo, revisão direta e reprocessamento da mesma submissão
  MUST continuar mutuamente exclusivos. Só um avança e os demais recebem
  conflito ou são descartados, como hoje.
- **FR-032**: Eventos de auditoria que hoje registram status anterior e
  resultante MUST registrar o ciclo de vida.
- **FR-033**: A migração MUST converter `SUBMISSION`, `AI_PRE_EVALUATION`,
  `TRIAGE` e `PLANNING` em `OPEN` e preservar `CLOSED`, `CANCELLED` e
  `ARCHIVED`.
- **FR-034**: A reversão da migração MUST reconstruir uma posição de fluxo
  coerente a partir das atividades.

### Key Entities *(include if feature involves data)*

- **Processo**: instância de um template. Passa a ter só o ciclo de vida
  (`OPEN`, `CLOSED`, `CANCELLED`, `ARCHIVED`), a data e o motivo de
  encerramento.
- **Fase**: agrupa atividades e tem estado próprio (não iniciada, em andamento,
  concluída, cancelada). Substitui o antigo `PLANNING` como indicação de etapa.
- **Atividade**: unidade de trabalho com cargo responsável e estado. Passa a
  carregar concessões de ver e editar por cargo.
- **Concessão de atividade**: par (cargo, nível), com nível ver ou editar,
  declarado no template e copiado para cada atividade instanciada. Pode ganhar
  mais granularidade depois (por exemplo, por campo) sem mudar o princípio de
  concessão a cargo.
- **Cargo**: papel de processo (atribuição ativa) ou global (perfil). É a única
  coisa que recebe concessão.
- **Revisão do retorno**: atividade do proponente na fase 1, aberta a cada
  retorno da IA ou do BraCVAM. Registra a escolha do proponente (revisar,
  contestar a IA, desistir) e dispara o efeito correspondente.
- **Pré-avaliação por IA**: execução automática sobre a submissão. Age como
  ator do sistema e é o ponto de trava da concorrência que hoje usa o status do
  processo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nenhuma resposta da API contém os valores `SUBMISSION`,
  `AI_PRE_EVALUATION`, `TRIAGE` ou `PLANNING` como estado de processo.
- **SC-002**: 100% das atividades dos templates canônicos (18 atuais e 5 de
  revisão do retorno) terminam a carga com ao menos um cargo com edição e com
  ver para `admin` e `bracvam`.
- **SC-003**: Para cada atividade da fase 1 e cada cargo da matriz da User
  Story 2, um teste confirma o acesso esperado (ver, editar ou nenhum) e o
  código de resposta correspondente.
- **SC-004**: A jornada "usuário novo cria o processo 1, envia, BraCVAM aprova a
  triagem" passa de ponta a ponta verificando o ciclo de vida `OPEN` em todos os
  passos e a fase 1 concluída ao final.
- **SC-005**: Um processo com duas atividades em andamento é representado sem
  ambiguidade: as duas ficam em andamento e cada usuário recebe exatamente as
  tarefas das atividades concedidas ao seu cargo.
- **SC-006**: Após a migração, 100% dos processos existentes têm um ciclo de vida
  válido, e os que aguardavam triagem continuam decidíveis pelo BraCVAM.
- **SC-007**: As disputas da pré-avaliação (IA concluindo, retry e contestação)
  e as escolhas na revisão do retorno ficam serializadas por trava no banco, e
  o código marca com `TODO(spec-030)` os dois testes de concorrência adiados.
  Os testes existentes da pré-avaliação continuam passando.
- **SC-008**: Nos dois tipos de retorno (IA e triagem), cada escolha do
  proponente produz o efeito definido em FR-039, verificado de ponta a ponta.

## Assumptions

- O vocabulário de cargos e a regra de cargo efetivo das tarefas (Spec 018) são
  reaproveitados, sem cargos novos. A IA não vira cargo; é tratada como ator do
  sistema (FR-025).
- As concessões são declaradas na definição dos templates e copiadas para as
  atividades na instanciação, como já acontece com o cargo responsável. Mudar
  um template não altera as concessões de processos já instanciados.
- Granularidade além de atividade (por campo, por fase) fica fora do escopo. O
  modelo de concessão a cargo deve permitir essa evolução sem quebrar os
  contratos desta feature.
- Os estados de fase e atividade existentes bastam para indicar a posição no
  fluxo. Esta feature não cria endpoint novo de visualização do fluxo (RF030);
  só garante que os dados estejam corretos e filtrados por concessão.
- As permissões globais atuais (`triage.review` e demais) continuam existindo.
  Decidir a triagem passa a exigir as duas coisas: a permissão global e a
  concessão de edição do cargo `bracvam` na atividade.
- A mudança de contrato é incompatível com o frontend atual, que precisa trocar
  o uso de status de fluxo por ciclo de vida e estados de atividade. A
  coordenação com o frontend fica fora deste repositório.
- O comportamento de cegamento e o conflito de interesse existentes não mudam.
- Por decisão do usuário, os testes de concorrência novos (FR-031 e a parte
  concorrente de FR-040) ficam fora desta feature. A trava é implementada; a
  prova com sessões concorrentes fica registrada como `TODO(spec-030)` no
  código. A escolha repetida em sequência continua testada.
- A concessão de ver para `admin` e `bracvam` (FR-016) atende à proposta do
  usuário de tratá-los como um cargo local atribuído automaticamente em todo
  processo. O plano escolhe entre gravar uma atribuição por processo ou derivar
  o cargo do perfil global, como a regra de cargo efetivo já faz. O
  comportamento observável é o mesmo.
- A revisão direta atual (proponente contesta a IA) passa a ser uma das escolhas
  da revisão do retorno. O plano decide se o endpoint atual é mantido como
  atalho ou substituído.
- Processos existentes que estavam com a submissão reaberta por retorno não
  ganham uma revisão do retorno retroativa; seguem com a submissão aberta.
