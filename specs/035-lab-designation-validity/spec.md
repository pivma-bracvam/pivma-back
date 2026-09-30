# Feature Specification: Validade da designação laboratorial

**Feature Branch**: `feat/035-lab-designation-validity`

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: issue #60, "[Bug]: Designação laboratorial
continua valendo após o fim do vínculo institucional". Designações de cargos
laboratoriais (`lead_laboratory`, `participating_laboratory`) só concedem
acesso enquanto o vínculo institucional do usuário com o laboratório e o
próprio laboratório estiverem ativos. `/auth/me`, a listagem de participantes e
a autorização apresentam o mesmo resultado para a mesma designação. A perda de
validade fica na trilha de auditoria. A spec define as regras para tarefas em
andamento e para vínculo restabelecido.

## Contexto

Um cargo laboratorial num processo é sempre ocupado por uma pessoa em nome de
um laboratório. A Spec 006 exige, ao designar, que a pessoa tenha vínculo
institucional ativo com esse laboratório (FR-003) e já determinava que a perda
desse vínculo, ou a inativação do laboratório, retirasse no pedido seguinte o
acesso que dependia da designação, sem revogá-la nem apagar o histórico
(FR-008; research, decisão 6). A designação continua ativa, mas deixa de ser
**efetiva**.

- **CONFIRMADO, implementação atual**: o sistema calcula se cada designação é
  efetiva e mostra o resultado em `/auth/me` e na listagem de participantes do
  processo.
- **CONFIRMADO, implementação atual**: a autorização das atividades (Spec 018
  e Spec 030), a lista de tarefas e a visibilidade do processo consideram
  somente se a designação está ativa (não revogada, não excluída, usuário
  ativo). Não conferem vínculo nem laboratório. Uma pessoa que deixou o
  laboratório continua vendo e editando as atividades do cargo.
- **CONFIRMADO, implementação atual**: as regras de "vínculo ativo" divergem
  entre pontos do sistema. A validação da designação confere a instituição, mas
  não o laboratório; o cálculo de efetividade confere o laboratório, mas não a
  instituição. A consulta dos próprios vínculos (Spec 005) confere os quatro:
  vínculo, usuário, instituição e laboratório.
- **CONFIRMADO, fonte oficial**: RF004 exige controle de acesso segundo perfil,
  instituição e participação no processo. RF044 exige que cada laboratório veja
  apenas os próprios dados nas etapas restritas do ensaio.

A issue #60 bloqueia #28 e #30 (Etapa 3), que dão ao laboratório acesso a
recebimentos e resultados.

## Clarifications

### Session 2026-09-30

*(a preencher em `/speckit-clarify`)*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quem deixa o laboratório perde o acesso do cargo (Priority: P1)

Uma pessoa foi designada como laboratório participante num processo, em nome do
Laboratório A. O gestor de vínculos encerra o vínculo dela com o Laboratório A.
No pedido seguinte, ela não vê nem edita mais as atividades que dependiam desse
cargo, não recebe as tarefas desse cargo como suas e não enxerga o processo se
esse era o único cargo que a ligava a ele.

**Why this priority**: é o defeito da issue. Sem isso, alguém sem vínculo age
em nome de um laboratório, e a rastreabilidade e a validade do ensaio ficam
comprometidas.

**Independent Test**: designar um usuário como `participating_laboratory`,
confirmar o acesso a uma atividade concedida a esse cargo, encerrar o vínculo
e repetir o acesso: ele deve ser negado.

**Acceptance Scenarios**:

1. **Given** uma designação laboratorial efetiva e uma atividade que concede
   ver e editar a esse cargo, **When** o vínculo da pessoa com o laboratório é
   encerrado, **Then** o pedido seguinte dela para ver ou editar a atividade é
   negado, com a mesma resposta de quem nunca teve o cargo.
2. **Given** a mesma situação, **When** a pessoa lista as próprias tarefas,
   **Then** as tarefas do cargo laboratorial não aparecem para ela, nem como
   visíveis nem como "posso agir".
3. **Given** que o cargo laboratorial era a única designação da pessoa no
   processo, **When** ela lista ou consulta processos, **Then** o processo não
   aparece para ela.
4. **Given** que a pessoa também tem outro cargo efetivo no mesmo processo (ex.:
   `statistician`), **When** o vínculo laboratorial é encerrado, **Then** ela
   perde só o que dependia do cargo laboratorial e mantém o acesso do outro
   cargo.
5. **Given** a perda de validade, **When** o gestor consulta a designação,
   **Then** ela continua ativa (não revogada), com o histórico intacto, e
   aparece como não efetiva.

---

### User Story 2 - Laboratório ou instituição inativados retiram o acesso (Priority: P1)

O gestor de catálogos inativa o Laboratório A, ou a instituição à qual ele
pertence. Toda designação laboratorial em nome do Laboratório A deixa de ser
efetiva em todos os processos, pelas mesmas regras da história 1.

**Why this priority**: é o segundo caminho da issue e produz o mesmo risco.

**Independent Test**: com duas pessoas designadas pelo Laboratório A em
processos diferentes, inativar o laboratório e confirmar que as duas perdem o
acesso dos cargos laboratoriais.

**Acceptance Scenarios**:

1. **Given** designações laboratoriais efetivas em nome do Laboratório A,
   **When** o Laboratório A é inativado, **Then** todas deixam de conceder
   acesso no pedido seguinte.
2. **Given** designações laboratoriais efetivas em nome de laboratórios da
   Instituição X, **When** a Instituição X é inativada, **Then** todas deixam
   de conceder acesso, mesmo que os laboratórios não tenham sido inativados um
   a um.
3. **Given** um usuário com vínculo ativo com o Laboratório B e designação em
   nome do Laboratório B, **When** o Laboratório A é inativado, **Then** a
   designação dele pelo Laboratório B não é afetada.

---

### User Story 3 - Exibição e autorização dizem a mesma coisa (Priority: P1)

A pessoa consulta `/auth/me` e o gestor consulta os participantes do processo.
Para cada designação, o que aparece como efetivo ou não efetivo é exatamente o
que a autorização aplica.

**Why this priority**: hoje a tela pode dizer "não efetiva" enquanto o acesso
continua liberado, ou o contrário. O gestor precisa confiar no que vê.

**Independent Test**: para uma matriz de situações (vínculo ativo, vínculo
encerrado, laboratório inativo, instituição inativa, usuário inativo), comparar
o campo de efetividade exibido com o resultado real de acesso a uma atividade
do cargo.

**Acceptance Scenarios**:

1. **Given** qualquer designação, **When** `/auth/me`, a listagem de
   participantes e a autorização são consultados no mesmo estado, **Then** os
   três dão o mesmo resultado sobre a efetividade.
2. **Given** um vínculo com laboratório ativo mas instituição inativa, **When**
   os três são consultados, **Then** os três tratam a designação como não
   efetiva.

---

### User Story 4 - A perda e a volta da validade ficam na trilha (Priority: P2)

Quem tem acesso ao histórico do processo encontra um evento quando uma
designação laboratorial deixa de ser efetiva por fim de vínculo ou inativação
de laboratório ou instituição, com o motivo, o laboratório, a pessoa e o
responsável pela ação institucional.

**Why this priority**: é critério de aceite da issue e sustenta a
rastreabilidade (RF034). Não muda o acesso em si, por isso vem depois das
histórias de autorização.

**Independent Test**: encerrar um vínculo que torna não efetivas designações
em dois processos e confirmar um evento na trilha de cada processo.

**Acceptance Scenarios**:

1. **Given** uma pessoa com designação laboratorial efetiva em dois processos,
   **When** o vínculo dela com o laboratório é encerrado, **Then** a trilha de
   cada processo recebe um evento de perda de validade daquela designação.
2. **Given** uma designação que já não era efetiva, **When** outra ação
   institucional a afeta de novo, **Then** nenhum evento duplicado de perda é
   registrado.
3. **Given** uma ação institucional que não afeta nenhuma designação ativa,
   **When** ela é concluída, **Then** nenhum evento de processo é registrado.

---

### User Story 5 - Vínculo restabelecido (Priority: P2)

A pessoa volta a ter vínculo ativo com o Laboratório A (novo vínculo), ou o
laboratório ou a instituição são reativados. O que acontece com a designação
ainda ativa no processo segue a regra decidida nesta spec.

**Why this priority**: a issue pede a regra explícita. Afeta menos casos que a
perda de acesso.

**Independent Test**: encerrar o vínculo, confirmar a perda de acesso, criar
novo vínculo com o mesmo laboratório e verificar o acesso conforme a regra.

**Acceptance Scenarios**:

1. **Given** uma designação ativa que deixou de ser efetiva por fim de
   vínculo, **When** a pessoa recebe um novo vínculo ativo com o mesmo
   laboratório, **Then** [NEEDS CLARIFICATION: a designação volta a ser efetiva
   automaticamente (decisão 6 da Spec 006: o ciclo não é reescrito, a
   efetividade é recalculada a cada pedido), ou só uma nova designação feita
   por quem gere participantes devolve o acesso?]
2. **Given** a regra escolhida, **When** a validade volta, **Then** a trilha do
   processo registra o evento correspondente.

---

### Edge Cases

- **Tarefas em andamento do cargo**: tarefas são atribuídas ao cargo, não à
  pessoa (Spec 018). Quando alguém perde a efetividade, a tarefa, os rascunhos
  e os dados já enviados permanecem; outra pessoa com o mesmo cargo efetivo no
  processo continua a partir deles. [NEEDS CLARIFICATION: quando a pessoa que
  perde a validade era a única com o cargo efetivo no processo, o sistema só
  mantém a tarefa aberta (o gestor vê a designação como não efetiva e designa
  outra pessoa), ou deve também sinalizar a atividade como sem responsável
  efetivo?]
- Vínculo encerrado durante uma edição em curso: o pedido de gravação seguinte
  já é negado. O que foi gravado antes permanece.
- Pessoa com dois cargos laboratoriais no mesmo processo por laboratórios
  diferentes: cada designação é avaliada pelo próprio laboratório; perder um
  vínculo não afeta a outra designação.
- Pessoa com mais de um vínculo ativo com o mesmo laboratório: a designação
  continua efetiva enquanto existir ao menos um vínculo ativo com ele.
- Admin e BraCVAM: o acesso global vem do perfil, não da designação, e não
  muda com esta spec.
- Designação revogada: continua sem efeito, como hoje. A perda de validade não
  se sobrepõe à revogação nem gera evento para ciclo revogado.
- Designações que já estavam não efetivas antes desta entrega (vínculos
  encerrados no passado): passam a ter o acesso negado a partir da entrega, sem
  eventos retroativos na trilha.
- Conflito de interesse: a checagem de conflito (Spec 006) continua valendo
  sobre as designações ativas; esta spec não muda o bloqueio por conflito.

## Requirements *(mandatory)*

### Functional Requirements

**Definição única de efetividade**

- **FR-001**: Uma designação é efetiva quando não está revogada nem excluída,
  o usuário está ativo e, para `lead_laboratory` e `participating_laboratory`,
  o laboratório está ativo, a instituição do laboratório está ativa e existe ao
  menos um vínculo institucional ativo do usuário com esse laboratório.
- **FR-002**: O sistema MUST aplicar a definição do FR-001 em todo ponto que
  decide ou mostra efetividade: autorização de atividades (ver e editar),
  lista de tarefas e o indicador "posso agir", visibilidade do processo e da
  sua linha do tempo, `/auth/me` e listagem de participantes.
- **FR-003**: A validação de uma nova designação laboratorial (direta ou por
  aceite de convite) MUST usar a mesma definição de vínculo ativo do FR-001,
  incluindo laboratório e instituição ativos.

**Autorização**

- **FR-004**: Uma designação não efetiva MUST NOT conceder nenhum acesso que
  dependa do seu cargo, a partir do pedido seguinte à mudança, sem exigir nova
  autenticação.
- **FR-005**: A negação por designação não efetiva MUST ter a mesma resposta de
  quem nunca teve o cargo, sem revelar que a designação existe.
- **FR-006**: A perda de efetividade MUST NOT revogar, apagar nem alterar a
  designação, as tarefas, os rascunhos, os dados enviados ou o histórico.
- **FR-007**: Os demais cargos efetivos da mesma pessoa no processo MUST
  continuar concedendo o próprio acesso.

**Trilha de auditoria**

- **FR-008**: Ao concluir o encerramento de vínculo, a inativação de
  laboratório ou a inativação de instituição, o sistema MUST registrar, na
  trilha de cada processo afetado, um evento por designação ativa que deixou de
  ser efetiva por essa ação.
- **FR-009**: O evento MUST identificar o processo, a designação, o usuário
  designado, o cargo, o laboratório, o motivo (fim de vínculo, laboratório
  inativado ou instituição inativada), o responsável pela ação institucional e
  o momento.
- **FR-010**: O sistema MUST NOT registrar evento de perda para designação que
  já não era efetiva antes da ação, nem para designação revogada.
- **FR-011**: O evento MUST ser gravado na mesma transação da ação
  institucional: se a ação falhar, nenhum evento fica registrado.

**Vínculo restabelecido**

- **FR-012**: A volta da validade MUST seguir a regra decidida para a história
  5 e MUST ser registrada na trilha do processo com o mesmo conjunto de dados
  do FR-009.

**Preservação**

- **FR-013**: Esta feature MUST NOT criar papéis, permissões ou perfis, nem
  mudar o acesso global de Admin e BraCVAM.
- **FR-014**: Esta feature MUST NOT alterar a geração de códigos cegos, que
  segue vinculada ao laboratório e não à pessoa (Spec 031).

### Key Entities

- **Designação** *(existente, Spec 006)*: pessoa, cargo e processo; nos cargos
  laboratoriais, também o laboratório. Ativa enquanto não revogada; efetiva
  segundo o FR-001.
- **Vínculo institucional** *(existente, Spec 005)*: liga a pessoa a uma
  instituição e, opcionalmente, a um laboratório. Pode ser encerrado; um novo
  vínculo é um novo registro.
- **Evento de validade da designação** *(novo tipo de evento na trilha
  existente)*: registra a perda ou a volta da efetividade de uma designação,
  com motivo e responsável.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das tentativas, uma pessoa com designação laboratorial
  não efetiva tem negado o acesso às atividades que dependiam só desse cargo,
  já no primeiro pedido após o encerramento do vínculo ou a inativação.
- **SC-002**: Para toda combinação de estado de usuário, vínculo, laboratório,
  instituição e revogação, `/auth/me`, a listagem de participantes e a
  autorização apresentam o mesmo resultado para a mesma designação.
- **SC-003**: 100% das designações ativas que perdem a efetividade por ação
  institucional têm um evento correspondente na trilha do processo, sem
  duplicatas.
- **SC-004**: Nenhuma designação, tarefa, rascunho ou dado enviado é apagado
  ou alterado pela perda de efetividade.
- **SC-005**: Os testes existentes de designação, convite, atividades, tarefas
  e amostras continuam passando, salvo os que dependiam do defeito corrigido.

## Assumptions

- A definição de vínculo ativo segue a consulta dos próprios vínculos da Spec
  005: vínculo, usuário, instituição e laboratório ativos.
- A inativação da instituição não inativa os laboratórios um a um; a
  efetividade da designação considera a instituição diretamente.
- A pessoa continua vendo o próprio histórico de designações quando consulta
  os participantes com escopo próprio, como hoje; isso não concede acesso às
  atividades.
- A inativação do usuário já retira o acesso hoje (Spec 028, desativação de
  conta) e fica fora desta spec, exceto pela definição única do FR-001.
- Não há notificação assíncrona (e-mail, alerta) da perda de validade; o
  registro fica na trilha e na efetividade exibida.
- Isolamento de dados entre laboratórios (#59) e execução por laboratório
  (#58) ficam fora do escopo.
