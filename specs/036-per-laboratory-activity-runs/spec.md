# Feature Specification: Execução de atividades por laboratório participante

**Feature Branch**: `feat/036-per-laboratory-activity-runs`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: issue #58, "[Feature]: Execução de atividades por
laboratório participante no motor de processos". Uma atividade declarada no
template como "por laboratório" abre uma execução e uma tarefa para cada
laboratório participante. A atividade só conclui quando todos os laboratórios
concluem ou são dispensados. O grupo gestor dispensa um laboratório ou reabre
a execução de um laboratório só, sem perder o histórico dos demais. Inclui os
dois comentários da issue (chave do laboratório e decisões de arquitetura) e
as decisões da sessão de 2026-10-02.

## Contexto

Na Etapa 3 (execução da validação), cada laboratório participante recebe as
amostras, executa o ensaio, envia os resultados e devolve ou descarta o
material por conta própria, no próprio ritmo (#28, #29, #30, #31).

- **CONFIRMADO, implementação atual**: o motor de processos mantém uma única
  execução aberta por atividade no processo inteiro. Concluir essa execução
  conclui a atividade e libera as atividades dependentes.
- **CONFIRMADO, implementação atual**: o template de processo não tem como
  declarar que uma atividade é executada por laboratório. A carga do template
  ignora chaves desconhecidas sem aviso.
- **CONFIRMADO, implementação atual**: a permissão de editar uma atividade
  depende só do cargo (Spec 030). Qualquer pessoa com o cargo
  `participating_laboratory` edita a atividade, sem distinção de laboratório.
- **CONFIRMADO, implementação atual**: a conclusão de `sample_definition`
  congela o conjunto de laboratórios participantes e gera um código cego por
  substância e laboratório (Spec 031, FR-013). Os cinco templates padrão têm
  essa atividade antes da Etapa 3.
- **CONFIRMADO, fonte oficial**: RF039 (registro do despacho), RF040 (check-in
  das amostras), RF044 (cada laboratório vê só os próprios dados) e RF046
  (monitoramento interlaboratorial de recebimento, execução, prazos e
  submissão).

Se as atividades da Etapa 3 forem declaradas hoje, o primeiro laboratório que
concluir encerra a atividade para todos, as atividades seguintes abrem antes
de todos os dados chegarem e não há como pedir a um laboratório só que refaça
o trabalho.

Esta issue bloqueia #28, #29, #30 e #31, e é a base de #59 (isolamento de
visão por laboratório).

## Clarifications

### Session 2026-10-02

- Q: Qual lista de laboratórios define as execuções: as designações ativas no
  momento da abertura ou o conjunto congelado em `sample_definition`? → A: O
  conjunto congelado. As designações decidem só quem age em cada execução. Um
  laboratório que perde a designação depois do congelamento continua com a
  execução pendente até concluir ou ser dispensado (FR-004, FR-005).
- Q: Quem dispensa um laboratório e quem reabre a execução de um laboratório?
  → A: Dispensa: `group_manager` com designação efetiva no processo, Admin e
  BraCVAM. Reabertura administrativa: os mesmos. A reabertura dentro do fluxo
  de uma atividade (ex.: recusa de dados na #30, por `statistician` ou
  `group_manager`) fica com a issue dessa atividade e usa o mesmo mecanismo
  (FR-017, FR-022).
- Q: O que acontece com as atividades seguintes quando uma execução é reaberta
  depois de elas já terem começado ou concluído? → A: Voltam a ficar
  bloqueadas, em cadeia (FR-025).
- Q: A dispensa vale para uma atividade ou para a fase? → A: Para o
  laboratório na fase inteira, exceto as atividades de custódia do material
  (ex.: devolução ou descarte), que continuam obrigatórias para quem recebeu
  amostras (FR-018, FR-019).
- Q: Um laboratório dispensado depois de receber as amostras consegue devolver
  o material se a devolução depende de atividades que esperam todos os
  laboratórios? → A: Sim. Entre duas atividades por laboratório, a dependência
  se resolve por laboratório: a etapa seguinte abre para o Lab X quando a
  anterior do Lab X conclui ou é dispensada. A espera por todos vale só quando
  uma atividade única do processo depende de uma atividade por laboratório
  (FR-010, FR-011). Isso substitui a regra da issue de liberar dependentes só
  após a conclusão da atividade agregadora.
- Q: O que torna um template inconsistente? → A: O template passa a declarar
  o modo de execução da atividade. A carga recusa valor de modo desconhecido,
  atividade por laboratório que pode abrir antes do congelamento e atividade
  por laboratório que o cargo `participating_laboratory` não pode editar
  (FR-001 a FR-003).
- Q: A dispensa pode ser revertida? → A: Não (FR-020a).
- Q: A custódia é obrigatória para todo laboratório dispensado, inclusive o
  que não recebeu amostras? → A: Sim (FR-019).
- Q: É permitido dispensar todos os laboratórios? → A: Sim (Edge Cases).
- Q: Como o grupo gestor acompanha cada laboratório? → A: Pela lista de
  tarefas, com o laboratório em cada tarefa, sem painel novo (FR-028).
- Q: Esta entrega cria uma rota para o laboratório concluir a própria
  execução, ou adapta as rotas de formulário? → A: Nenhuma das duas. O motor
  oferece a conclusão e as issues #28 a #31 a usam nas próprias rotas. As
  rotas de formulário existentes não mudam para atividades de execução única
  e recusam atividade por laboratório até a issue consumidora estendê-las
  (FR-016, FR-034).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cada laboratório recebe a própria execução (Priority: P1)

Um processo tem três laboratórios participantes congelados na definição das
amostras. Quando uma atividade por laboratório abre, cada laboratório recebe a
própria execução e a própria tarefa. Cada um conclui a sua sem afetar a dos
outros, e a atividade só conclui quando os três terminam.

**Why this priority**: é o núcleo da issue. Sem isso nenhuma atividade da
Etapa 3 pode ser declarada.

**Independent Test**: com um template de teste que declara uma atividade por
laboratório depois de `sample_definition`, criar um processo com três
laboratórios, concluir a definição das amostras e verificar três execuções
abertas. Concluir duas e verificar que a atividade continua em andamento.
Concluir a terceira e verificar a conclusão da atividade.

**Acceptance Scenarios**:

1. **Given** um processo com N laboratórios no conjunto congelado, **When** a
   atividade por laboratório abre, **Then** existem exatamente N execuções
   abertas e N tarefas, cada uma ligada ao seu laboratório.
2. **Given** três execuções abertas, **When** o Lab A conclui a sua, **Then**
   as execuções dos labs B e C continuam abertas e a atividade continua em
   andamento.
3. **Given** dois laboratórios concluídos e um pendente, **When** alguém
   consulta a atividade, **Then** ela continua em andamento e uma atividade
   única do processo que depende dela continua bloqueada.
4. **Given** todos os laboratórios concluídos, **When** o último conclui,
   **Then** a atividade conclui e as atividades únicas do processo que
   dependiam dela abrem.
5. **Given** um processo cujo conjunto congelado não tem laboratório, **When**
   a conclusão de uma dependência tenta abrir a atividade por laboratório,
   **Then** essa conclusão é recusada com erro de domínio e nada dela fica
   gravado, nem execução parcial.

---

### User Story 2 - Só o próprio laboratório age na sua execução (Priority: P1)

Uma pessoa designada pelo Lab A conclui a execução do Lab A. Ela não consegue
agir na execução do Lab B, mesmo tendo o cargo que edita a atividade.

**Why this priority**: sem essa regra, um laboratório envia ou conclui dados
em nome de outro, o que invalida o ensaio interlaboratorial.

**Independent Test**: com dois laboratórios e uma pessoa designada por cada
um, tentar agir na execução do outro laboratório e verificar a recusa.

**Acceptance Scenarios**:

1. **Given** uma pessoa com designação efetiva pelo Lab A, **When** ela age na
   execução do Lab A, **Then** a ação é aceita.
2. **Given** a mesma pessoa, **When** ela tenta agir na execução do Lab B,
   **Then** a ação é recusada e a execução do Lab B não muda.
3. **Given** que a designação dela pelo Lab A deixou de ser efetiva (Spec
   035), **When** ela tenta agir na execução do Lab A, **Then** a ação é
   recusada, e a execução continua pendente.
4. **Given** a lista de tarefas, **When** a pessoa do Lab A consulta, **Then**
   o indicador "posso agir" é verdadeiro só na tarefa do Lab A.

---

### User Story 3 - Cada laboratório avança na própria cadeia (Priority: P1)

Duas atividades por laboratório estão em sequência (ex.: recebimento e envio
de resultados). Quando o Lab A conclui o recebimento, o envio de resultados
abre para o Lab A, sem esperar os labs B e C.

**Why this priority**: sem isso, um laboratório atrasado no recebimento trava
a execução experimental de todos. É também o que permite ao laboratório
dispensado devolver o material (história 4).

**Independent Test**: com duas atividades por laboratório encadeadas e três
laboratórios, concluir a primeira só para o Lab A e verificar que a segunda
abriu só para o Lab A.

**Acceptance Scenarios**:

1. **Given** duas atividades por laboratório em sequência, **When** o Lab A
   conclui a primeira, **Then** a segunda abre para o Lab A e continua sem
   execução para os labs B e C.
2. **Given** a mesma situação, **When** o Lab A conclui a primeira, **Then** a
   segunda atividade passa a constar em andamento.
3. **Given** uma atividade por laboratório que depende de duas atividades por
   laboratório, **When** o Lab A conclui só uma delas, **Then** a execução do
   Lab A na atividade seguinte não abre.
4. **Given** uma atividade por laboratório que depende de uma atividade única
   do processo, **When** a atividade única conclui, **Then** a atividade por
   laboratório abre para todos os laboratórios do conjunto congelado.

---

### User Story 4 - Dispensar um laboratório (Priority: P1)

O Lab C quebrou um equipamento e não vai concluir o ensaio. O grupo gestor
registra a dispensa do Lab C na fase, com o motivo. As atividades
experimentais da fase passam a contar como resolvidas para o Lab C. Se o Lab C
já recebeu amostras, a devolução ou o descarte continua obrigatório para ele e
abre sem esperar os outros laboratórios.

**Why this priority**: sem a dispensa, um único laboratório inadimplente trava
o estudo indefinidamente.

**Independent Test**: com três laboratórios, concluir dois, dispensar o
terceiro e verificar que a atividade conclui e a etapa seguinte abre. Em outra
fase com uma atividade de custódia, verificar que ela abre para o laboratório
dispensado.

**Acceptance Scenarios**:

1. **Given** dois laboratórios concluídos e o Lab C pendente, **When** o grupo
   gestor dispensa o Lab C na fase, **Then** a execução pendente do Lab C fica
   como dispensada, a atividade conclui e as atividades únicas que dependiam
   dela abrem.
2. **Given** uma fase com atividades por laboratório ainda não abertas,
   **When** o Lab C é dispensado, **Then** essas atividades, ao abrirem, já
   criam a execução do Lab C como dispensada e a tarefa dele como cancelada,
   e contam o Lab C como resolvido.
3. **Given** uma atividade de custódia na fase e o Lab C dispensado, **When**
   as atividades de que ela depende ficam resolvidas para o Lab C, **Then** a
   custódia abre para o Lab C e conta para a conclusão da atividade como as
   demais.
4. **Given** uma execução já concluída pelo Lab C, **When** o Lab C é
   dispensado, **Then** a execução concluída continua concluída, com os dados
   intactos.
5. **Given** a dispensa, **When** alguém consulta a trilha do processo,
   **Then** encontra um evento com o laboratório, a fase, o motivo, o autor e o
   momento.
6. **Given** uma pessoa sem `group_manager` efetivo e sem perfil Admin ou
   BraCVAM, **When** ela tenta dispensar um laboratório, **Then** a ação é
   recusada e nada muda.
7. **Given** um laboratório já dispensado na fase, **When** alguém tenta
   dispensá-lo de novo, **Then** a ação é recusada como conflito.

---

### User Story 5 - Reabrir a execução de um laboratório (Priority: P2)

O estatístico recusou os dados do Lab B. O grupo gestor reabre a execução do
Lab B com um motivo. O Lab B recebe uma nova execução. A execução anterior do
Lab B e as execuções dos labs A e C ficam como estavam.

**Why this priority**: é critério de aceite da issue e sustenta a integridade
dos dados (BPL), mas só é usada depois que há execuções concluídas.

**Independent Test**: com três laboratórios concluídos, reabrir o Lab B e
verificar a nova execução do Lab B, a execução anterior preservada, os labs A
e C intactos e a atividade de volta para em andamento.

**Acceptance Scenarios**:

1. **Given** a execução do Lab B concluída, **When** o grupo gestor reabre a
   execução do Lab B com motivo, **Then** a execução anterior fica marcada como
   substituída e uma nova execução do Lab B abre com o número seguinte.
2. **Given** a reabertura, **When** alguém consulta a execução anterior do
   Lab B, **Then** os valores, anexos e eventos dela continuam íntegros e
   legíveis.
3. **Given** a reabertura do Lab B, **When** alguém consulta os labs A e C,
   **Then** as execuções deles não mudaram.
4. **Given** uma atividade concluída, **When** a execução do Lab B é reaberta,
   **Then** a atividade volta para em andamento.
5. **Given** atividades seguintes que dependiam da conclusão de todos e já
   tinham aberto ou concluído, **When** a execução do Lab B é reaberta,
   **Then** elas voltam a ficar bloqueadas, em cadeia, e as execuções abertas
   delas são encerradas como canceladas, com os dados preservados.
6. **Given** atividades seguintes por laboratório, **When** a execução do Lab B
   é reaberta, **Then** só a cadeia do Lab B volta a ficar bloqueada; as
   cadeias dos labs A e C seguem.
7. **Given** a reabertura, **When** alguém consulta a trilha, **Then**
   encontra um evento com o laboratório, a atividade, o número da execução
   anterior e da nova, o motivo e o autor.
8. **Given** uma pessoa sem `group_manager` efetivo e sem perfil Admin ou
   BraCVAM, **When** ela tenta a reabertura administrativa, **Then** a ação é
   recusada e nada muda.
9. **Given** um laboratório dispensado na fase, **When** alguém tenta reabrir
   uma execução dele que não seja de custódia, **Then** a ação é recusada.

---

### User Story 6 - O template declara a execução por laboratório (Priority: P2)

Quem mantém os templates declara numa atividade que ela é executada por
laboratório e, na fase, quais atividades são de custódia. A carga dos
templates recusa uma declaração que levaria o processo a travar.

**Why this priority**: as histórias anteriores dependem dessa declaração, mas
a validação em si só protege contra erro de configuração.

**Independent Test**: carregar templates com cada declaração inválida e
verificar a recusa com mensagem que identifica template e atividade; carregar
os cinco templates padrão e verificar que nada muda.

**Acceptance Scenarios**:

1. **Given** uma atividade sem declaração de modo de execução, **When** o
   template é carregado, **Then** ela funciona como hoje, com uma execução
   única.
2. **Given** uma atividade com modo de execução desconhecido, **When** o
   template é carregado, **Then** a carga é recusada.
3. **Given** uma atividade por laboratório que não depende, direta ou
   indiretamente, de `sample_definition`, **When** o template é carregado,
   **Then** a carga é recusada.
4. **Given** uma atividade por laboratório sem `participating_laboratory` entre
   os cargos que editam, **When** o template é carregado, **Then** a carga é
   recusada.
5. **Given** uma marcação de custódia numa atividade que não é por
   laboratório, **When** o template é carregado, **Then** a carga é recusada.

---

### User Story 7 - Acompanhar cada laboratório (Priority: P2)

O grupo gestor acompanha, para cada atividade por laboratório, quem já
concluiu, quem está pendente, quem foi dispensado e quem teve a execução
reaberta (RF046).

**Why this priority**: é critério de aceite da issue. Depende das histórias 1,
4 e 5 para ter o que mostrar.

**Independent Test**: com três laboratórios em estados diferentes, consultar a
lista de tarefas filtrada pela atividade e a trilha do processo e verificar o
laboratório e o estado de cada um.

**Acceptance Scenarios**:

1. **Given** uma atividade por laboratório, **When** alguém lista as tarefas,
   **Then** cada tarefa dessa atividade traz o laboratório e o status da
   execução (em andamento, concluída, dispensada, substituída ou cancelada);
   tarefas de atividades únicas não trazem laboratório.
2. **Given** a lista de tarefas na rodada vigente, **When** um laboratório teve
   a execução reaberta, **Then** a rodada vigente é a mais recente de cada
   laboratório, e não a mais recente da atividade.
3. **Given** a trilha do processo, **When** um laboratório conclui, é
   dispensado ou tem a execução reaberta, **Then** o evento correspondente traz
   o laboratório.

---

### Edge Cases

- **Laboratório que perde a designação depois do congelamento**: a execução
  dele continua pendente e a atividade não conclui. Ninguém consegue agir por
  ele até nova designação; o grupo gestor resolve designando outra pessoa do
  laboratório ou dispensando o laboratório.
- **Laboratório designado depois do congelamento**: não recebe execução nas
  atividades por laboratório daquele estudo.
- **Laboratório com duas pessoas designadas**: uma execução por laboratório;
  qualquer uma das duas com designação efetiva age nela.
- **Atividade única que depende de atividade por laboratório já concluída por
  todos, depois uma reabertura**: a atividade única volta a ficar bloqueada
  (FR-025).
- **Dispensa com todos os outros laboratórios já concluídos**: a dispensa é o
  que conclui a atividade e libera as seguintes, na mesma operação.
- **Dispensa de todos os laboratórios**: permitida; as atividades
  experimentais concluem sem dados de laboratório. As atividades de custódia
  continuam obrigatórias para quem recebeu amostras.
- **Reabertura de execução ainda aberta**: recusada; não há o que reabrir.
- **Reabertura de execução cancelada ou já substituída**: recusada; só a
  execução vigente do laboratório pode ser reaberta.
- **Duas conclusões simultâneas dos últimos laboratórios**: a atividade
  conclui uma vez e as atividades seguintes abrem uma vez.
- **Processo encerrado, cancelado ou arquivado**: dispensa e reabertura são
  recusadas, como as demais mudanças (Spec 030).
- **Cancelamento do processo**: as execuções por laboratório abertas são
  canceladas como as demais (Spec 022/030).
- **Laboratório desativado depois do congelamento**: a execução continua; o
  acesso das pessoas segue a Spec 035.

## Requirements *(mandatory)*

### Functional Requirements

**Declaração no template**

- **FR-001**: O template MUST permitir declarar o modo de execução de cada
  atividade: execução única no processo (padrão, quando omitido) ou execução
  por laboratório.
- **FR-002**: O template MUST permitir marcar uma atividade por laboratório
  como de custódia, isto é, não dispensável para laboratório que recebeu
  amostras.
- **FR-003**: A carga do template MUST recusar, com mensagem que identifica o
  template e a atividade: modo de execução desconhecido; atividade por
  laboratório que não dependa, direta ou indiretamente, de `sample_definition`;
  atividade por laboratório sem `participating_laboratory` entre os cargos que
  editam; marcação de custódia em atividade que não é por laboratório.

**Abertura**

- **FR-004**: Ao abrir uma atividade por laboratório, o sistema MUST criar uma
  execução e uma tarefa para cada laboratório do conjunto congelado na
  conclusão de `sample_definition` do processo, ligadas ao laboratório.
- **FR-005**: As designações ativas no momento da abertura MUST NOT alterar o
  conjunto de execuções: um laboratório designado depois do congelamento não
  recebe execução, e um laboratório que perdeu a designação recebe.
- **FR-006**: Se o conjunto congelado não tiver laboratório, a abertura MUST
  ser recusada com erro de domínio, sem gravar nenhuma execução.
- **FR-007**: Para laboratório dispensado na fase, a abertura de atividade que
  não seja de custódia MUST criar a execução dele já dispensada e a tarefa já
  cancelada, para que o acompanhamento mostre o laboratório (FR-028). Em
  atividade de custódia, a execução abre normalmente (FR-019).

**Execução e autorização**

- **FR-008**: Só pessoas com designação efetiva (Spec 035) de
  `participating_laboratory` pelo laboratório da execução MUST poder agir nela,
  além das concessões globais vigentes de Admin e BraCVAM. A recusa MUST
  deixar a execução inalterada.
- **FR-009**: O indicador "posso agir" da lista de tarefas MUST seguir o
  FR-008.

**Conclusão e dependências**

- **FR-010**: Concluir a execução de um laboratório MUST concluir só essa
  execução e a tarefa dela.
- **FR-011**: Quando uma atividade por laboratório depende de outra atividade
  por laboratório, a execução do Lab X na dependente MUST abrir quando todas
  as dependências estiverem resolvidas para o Lab X (concluídas ou
  dispensadas), independentemente dos outros laboratórios.
- **FR-012**: Uma atividade por laboratório MUST constar em andamento a partir
  da abertura da primeira execução de laboratório.
- **FR-013**: Uma atividade por laboratório MUST concluir quando todas as
  execuções vigentes do conjunto congelado estiverem concluídas ou
  dispensadas.
- **FR-014**: Uma atividade única do processo que depende de uma atividade por
  laboratório MUST abrir só quando esta concluir (FR-013).
- **FR-015**: A conclusão da atividade e a abertura das seguintes MUST ocorrer
  uma única vez, mesmo com conclusões simultâneas de laboratórios.
- **FR-016**: Atividades com execução única MUST manter o comportamento atual.

**Dispensa**

- **FR-017**: `group_manager` com designação efetiva no processo, Admin e
  BraCVAM MUST poder dispensar um laboratório do conjunto congelado numa fase,
  com motivo obrigatório. Os demais MUST receber recusa.
- **FR-018**: A dispensa MUST marcar como dispensadas as execuções não
  concluídas do laboratório nas atividades por laboratório da fase que não
  sejam de custódia, e as tarefas abertas delas como canceladas. Execuções já
  concluídas MUST continuar concluídas.
- **FR-019**: Atividades de custódia MUST continuar exigindo a execução de
  todo laboratório dispensado, tenha ou não recebido amostras, e MUST abrir para ele quando as dependências dele
  estiverem resolvidas (FR-011).
- **FR-020**: Dispensar um laboratório já dispensado na mesma fase MUST ser
  recusado como conflito.
- **FR-020a**: A dispensa MUST NOT ser revertida; o sistema MUST NOT
  oferecer ação para desfazê-la.
- **FR-021**: A dispensa MUST registrar na trilha do processo um evento com o
  laboratório, a fase, o motivo, o autor e o momento, na mesma transação.

**Reabertura**

- **FR-022**: O sistema MUST oferecer a reabertura da execução vigente de um
  laboratório numa atividade por laboratório, com motivo obrigatório, como
  ação administrativa para `group_manager` com designação efetiva, Admin e
  BraCVAM, e como mecanismo reutilizável pelas atividades que recusam dados.
- **FR-023**: A reabertura MUST marcar a execução vigente como substituída e
  criar uma nova execução e uma nova tarefa para o mesmo laboratório, com o
  número de execução seguinte daquele laboratório.
- **FR-024**: A reabertura MUST NOT alterar valores, anexos, decisões ou
  eventos da execução substituída, nem as execuções dos outros laboratórios.
- **FR-025**: A reabertura MUST devolver a atividade para em andamento quando
  ela estava concluída e MUST voltar a bloquear, em cadeia: as atividades
  únicas que dependiam da conclusão dela; e, nas atividades por laboratório
  seguintes, só a cadeia do laboratório reaberto. Execuções abertas dessas
  atividades MUST ser encerradas como canceladas, com os dados preservados;
  ao serem liberadas de novo, abrem nova execução.
- **FR-026**: A reabertura MUST ser recusada para execução aberta, substituída
  ou cancelada, e para execução não de custódia de laboratório dispensado na
  fase.
- **FR-027**: A reabertura MUST registrar na trilha um evento com o
  laboratório, a atividade, o número da execução substituída e da nova, o
  motivo e o autor, na mesma transação.

**Exposição**

- **FR-028**: A lista e o detalhe de tarefas MUST trazer o laboratório nas
  tarefas de atividades por laboratório e nenhum laboratório nas demais, e
  MUST trazer o status da execução da tarefa, que distingue concluída,
  dispensada, substituída e cancelada.
- **FR-029**: O filtro de rodada vigente da lista de tarefas MUST considerar a
  execução mais recente de cada laboratório nas atividades por laboratório.
- **FR-030**: Os eventos de conclusão, dispensa e reabertura de execução de
  laboratório MUST trazer o laboratório na trilha do processo.

**Preservação**

- **FR-031**: Dispensa e reabertura MUST ser recusadas em processo encerrado,
  cancelado ou arquivado (Spec 030).
- **FR-032**: Esta feature MUST NOT alterar a visibilidade das atividades por
  laboratório entre laboratórios; o isolamento de visão fica com a #59.
- **FR-033**: Esta feature MUST NOT alterar os códigos cegos nem o conjunto
  congelado da Spec 031.
- **FR-034**: As rotas de formulário existentes MUST manter o comportamento
  atual em atividades de execução única e MUST recusar, como transição
  inválida, o uso em atividade por laboratório, sem alterar nenhuma execução.

### Key Entities

- **Atividade** *(existente)*: passa a ter um modo de execução (única ou por
  laboratório) e, quando por laboratório, pode ser de custódia. O status
  agrega as execuções dos laboratórios.
- **Execução** *(existente)*: passa a poder pertencer a um laboratório. O
  número da execução conta por laboratório dentro da atividade. Ganha os
  estados dispensada e substituída.
- **Tarefa** *(existente)*: herda o laboratório da execução.
- **Dispensa de laboratório** *(novo)*: laboratório, fase do processo, motivo,
  autor e momento. No máximo uma vigente por laboratório e fase.
- **Conjunto congelado de laboratórios** *(existente, Spec 031)*: laboratórios
  com código cego ativo após a conclusão de `sample_definition`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em processo com N laboratórios congelados, 100% das aberturas de
  atividade por laboratório criam exatamente N execuções e N tarefas, uma por
  laboratório.
- **SC-002**: Em 100% dos casos testados, a conclusão, dispensa ou reabertura
  de um laboratório não altera nenhuma execução de outro laboratório.
- **SC-003**: Nenhuma atividade única que depende de atividade por laboratório
  abre enquanto houver laboratório pendente.
- **SC-004**: Um estudo com um laboratório inadimplente avança para a etapa
  seguinte com uma única ação de dispensa do grupo gestor.
- **SC-005**: Um laboratório dispensado depois de receber amostras consegue
  registrar a devolução ou o descarte sem esperar os outros laboratórios.
- **SC-006**: 100% das execuções substituídas mantêm valores, anexos e eventos
  idênticos aos de antes da reabertura.
- **SC-007**: 100% das tentativas de agir na execução de outro laboratório são
  recusadas.
- **SC-008**: Os cinco templates padrão carregam sem mudança de comportamento e
  os testes existentes de motor, tarefas, amostras e templates continuam
  passando.

## Assumptions

- Nenhum template padrão declara atividade por laboratório nesta entrega. As
  atividades reais chegam com #28 a #31; aqui o comportamento é verificado com
  templates de teste.
- "Fase" na dispensa é a fase do template em que a atividade está declarada.
- Um laboratório dispensado por engano volta a participar por decisão formal
  fora do sistema, em estudo ou fase posterior (FR-020a).
- A recusa de dados dentro de uma atividade (ex.: parecer do estatístico na
  #30) e a autorização dela ficam com a issue dessa atividade, que reutiliza a
  reabertura desta spec.
- O acompanhamento por laboratório usa a lista de tarefas; a trilha do
  processo complementa com os eventos de cada laboratório. Não há painel novo.
- Admin e BraCVAM mantêm o acesso global atual às atividades (Spec 030).
- Isolamento de visão entre laboratórios (#59), notificações e prazos por
  laboratório ficam fora do escopo.
- O ajuste da unicidade de CAS e de códigos cegos por fase (comentário da
  issue, item 5) fica para issue posterior da Spec 031.
