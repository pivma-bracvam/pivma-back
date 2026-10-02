# Feature Specification: Isolamento de acesso por laboratório

**Feature Branch**: `feat/037-per-laboratory-access-isolation`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: issue #59, "[Feature]: Isolamento de acesso por
laboratório nas atividades executadas por laboratório". Nas atividades
executadas por laboratório (Spec 036), a autorização de leitura e escrita
considera o laboratório da designação efetiva do usuário, além do cargo.
Inclui as decisões da sessão de 2026-10-02.

## Contexto

O Plano de Trabalho exige que "cada laboratório acessará exclusivamente seus
próprios dados durante a execução dos ensaios" (módulo de ensaios
interlaboratoriais; RF044, RF050). Todos os laboratórios participantes
compartilham o cargo `participating_laboratory`, e a concessão de uma
atividade (Spec 030) vale para o cargo inteiro.

- **CONFIRMADO, Spec 036**: `GET /tasks` e `GET /tasks/{id}` mostram a tarefa
  da execução de um laboratório só ao próprio laboratório e à gestão do
  processo (Admin, BraCVAM, `group_manager` efetivo). Os demais cargos não a
  veem. A tarefa de outro laboratório responde `404`.
- **CONFIRMADO, Spec 036**: a linha do tempo oculta os eventos de execução de
  outro laboratório e mostra a dispensa só à gestão.
- **CONFIRMADO, Spec 036**: as rotas de formulário e de anexo respondem `409`
  para atividade executada por laboratório. Conteúdo e anexos dessas
  atividades ganham rotas próprias nas issues #28 a #31.
- **CONFIRMADO, implementação atual**: concluir a execução de outro
  laboratório no motor responde "proibido" (`403`). A resposta difere da dada
  a um laboratório inexistente (`404`) e confirma que a execução existe.
- **CONFIRMADO, implementação atual**: a regra "quem vê a execução de um
  laboratório" está escrita em três lugares (filtro de tarefas, filtro da
  linha do tempo, rotas de dispensa e reabertura). Não existe verificação de
  leitura de uma execução isolada que as issues #28 a #31 possam chamar.
- **CONFIRMADO, implementação atual**: o índice único de designação ativa
  cobre processo, usuário e cargo. Uma segunda designação
  `participating_laboratory` do mesmo usuário no mesmo processo, por qualquer
  laboratório, já é rejeitada com `409 duplicate`. Nenhum teste cobre esse
  caso como regra de isolamento.

## Clarifications

### Session 2026-10-02

- Q: O que o Laboratório Líder (`lead_laboratory`) vê das execuções dos
  laboratórios participantes? → A: Nada. O Plano pede avaliação independente
  do laboratório desenvolvedor. O usuário só vê a execução de um laboratório
  pelo qual também tenha designação efetiva de `participating_laboratory`.
- Q: Um usuário pode ser `participating_laboratory` por dois laboratórios no
  mesmo processo? → A: Não. A segunda designação é rejeitada com `409`.
- Q: O que o Grupo de Seleção de Amostras (`sample_selection_group`) vê das
  execuções por laboratório? → A: Nada, igual ao estatístico.
- Q: Admin, BraCVAM e `group_manager` efetivo continuam vendo todas as
  execuções com o laboratório identificado? → A: Sim. O cegamento dos
  resultados para o estatístico pertence à issue #30.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Laboratório não alcança dados de outro laboratório (Priority: P1)

O usuário do laboratório A tenta listar, ler e concluir a execução do
laboratório B. Toda tentativa falha com a mesma resposta dada a uma execução
que não existe.

**Why this priority**: É a exigência central do Plano de Trabalho. Uma
resposta diferente para "existe, mas é de outro" já entrega ao laboratório A
a informação de que o laboratório B tem execução naquela atividade.

**Independent Test**: Processo com dois laboratórios participantes e
amostras congeladas. Autenticado como A, tente ler e concluir a execução de
B pelo motor e pela API. Compare cada resposta com a de um laboratório sem
execução no processo.

**Acceptance Scenarios**:

1. **Given** a execução de B em andamento, **When** o usuário de A tenta
   concluí-la, **Then** o sistema nega com "não encontrado" e a execução de
   B não muda.
2. **Given** a execução de B em andamento, **When** o usuário de A pede para
   ler essa execução, **Then** o sistema nega com "não encontrado".
3. **Given** um laboratório sem execução na atividade, **When** o usuário de
   A tenta concluir a execução desse laboratório, **Then** a resposta tem o
   mesmo código e a mesma mensagem do cenário 1.
4. **Given** a execução de B, **When** o usuário de A lista ou abre as
   tarefas e a linha do tempo, **Then** nada da execução de B aparece.

---

### User Story 2 - Laboratório segue trabalhando nos próprios dados (Priority: P1)

O usuário do laboratório A lê e conclui a própria execução normalmente.

**Why this priority**: O isolamento não pode bloquear o trabalho do próprio
laboratório.

**Independent Test**: Mesmo processo; autenticado como A, leia e conclua a
execução de A.

**Acceptance Scenarios**:

1. **Given** a execução de A em andamento, **When** o usuário de A a lê,
   **Then** o acesso é concedido.
2. **Given** a execução de A em andamento, **When** o usuário de A a
   conclui, **Then** a execução fica concluída.
3. **Given** a execução de A, **When** o usuário de A lista as tarefas e a
   linha do tempo, **Then** a tarefa e os eventos de A aparecem.

---

### User Story 3 - Regras por perfil (Priority: P2)

Cada perfil tem uma regra explícita para as execuções por laboratório:

- **Admin e BraCVAM**: veem todas, com o laboratório identificado. Agem
  quando o cargo global está entre os que editam a atividade.
- **`group_manager` efetivo**: vê todas, com o laboratório identificado. Não
  age na execução de um laboratório.
- **Laboratório líder, Grupo de Seleção de Amostras, estatístico e demais
  cargos**: não veem nenhuma execução de laboratório.
- **Usuário com cargos laboratoriais em laboratórios distintos** (líder por
  X e participante por Y): vê e age só na execução de Y.

**Why this priority**: A issue exige as regras de laboratório líder e de
gestão, cobertas por uma matriz de testes.

**Independent Test**: Matriz de perfil por operação (listar tarefas, abrir
tarefa, linha do tempo, ler execução, concluir execução) sobre o mesmo
processo.

**Acceptance Scenarios**:

1. **Given** um `group_manager` efetivo, **When** ele lê a execução de B,
   **Then** o acesso é concedido. **When** tenta concluí-la, **Then** o
   sistema responde "proibido", porque ele já vê a execução.
2. **Given** Admin, **When** lê ou conclui a execução de B numa atividade
   que concede editar a `admin`, **Then** o acesso é concedido.
3. **Given** um laboratório líder, um membro do Grupo de Seleção de Amostras
   ou um estatístico, **When** tenta ler a execução de B, **Then** recebe
   "não encontrado".
4. **Given** um usuário líder por X e participante por Y, **When** lê ou
   conclui a execução de Y, **Then** o acesso é concedido. **When** tenta
   ler a execução de X ou de outro laboratório, **Then** recebe "não
   encontrado".

---

### User Story 4 - Uma designação de participante por usuário no processo (Priority: P2)

O gestor designa um usuário como laboratório participante pelo laboratório
A. Uma segunda designação do mesmo usuário como participante, pelo
laboratório B, é rejeitada.

**Why this priority**: Uma pessoa com dados de dois laboratórios quebra a
independência dos resultados.

**Independent Test**: Designe o mesmo usuário, com vínculo com A e com B,
como participante por A e depois por B, pela rota de participantes.

**Acceptance Scenarios**:

1. **Given** um usuário participante ativo por A, **When** o gestor o
   designa participante por B no mesmo processo, **Then** o sistema responde
   `409` e não cria a designação.
2. **Given** a designação por A revogada, **When** o gestor o designa
   participante por B, **Then** a designação é criada.
3. **Given** um usuário líder por A, **When** o gestor o designa
   participante por B, **Then** a designação é criada.

### Edge Cases

- Usuário de A perde o vínculo institucional: perde o acesso à execução de A
  e recebe "não encontrado" (Spec 035).
- Execução de processo inteiro (sem laboratório): segue a regra de cargo da
  Spec 030, sem filtro de laboratório.
- Execução de B já concluída, dispensada ou substituída: a resposta ao
  usuário de A continua "não encontrado". O status não é revelado.
- Usuário de A sem concessão de editar a atividade: recebe "proibido" da
  atividade, antes de qualquer verificação de laboratório. A mensagem não
  cita laboratório nem execução.
- `group_manager` com conflito de interesse vigente: continua vendo as
  execuções e não age, como já acontece.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Toda negação de ler ou agir na execução de um laboratório que o
  usuário não vê MUST responder "não encontrado", com a mesma mensagem dada
  quando o laboratório não tem execução na atividade.
- **FR-002**: O sistema MUST oferecer uma verificação única de acesso à
  execução de um laboratório, com nível de leitura e de escrita, para as
  rotas de conteúdo e anexos das issues #28 a #31.
- **FR-003**: A leitura da execução de um laboratório MUST exigir a concessão
  de ver a atividade (Spec 030) e uma destas condições: designação efetiva
  de `participating_laboratory` pelo laboratório da execução, perfil Admin ou
  BraCVAM, ou designação efetiva de `group_manager` no processo.
- **FR-004**: A escrita na execução de um laboratório MUST exigir a concessão
  de editar a atividade e uma destas condições: designação efetiva de
  `participating_laboratory` pelo laboratório da execução, ou cargo global
  (`admin`, `bracvam`) entre os que editam a atividade.
- **FR-005**: Quem lê a execução sem poder escrevê-la MUST receber
  "proibido" ao tentar escrever.
- **FR-006**: O laboratório líder, o Grupo de Seleção de Amostras, o
  estatístico e os demais cargos MUST NOT ver nenhuma execução de
  laboratório: nem a tarefa, nem os eventos, nem a execução.
- **FR-007**: A designação de `lead_laboratory` MUST NOT conceder acesso a
  nenhuma execução de laboratório, nem à do próprio laboratório da
  designação.
- **FR-008**: O sistema MUST rejeitar com `409` uma designação ativa de
  `participating_laboratory` para um usuário que já tem outra ativa no mesmo
  processo, por qualquer laboratório, pela rota de participantes e pelo
  aceite de convite.
- **FR-009**: Os filtros de tarefas e da linha do tempo e as rotas de
  dispensa e reabertura MUST usar a mesma definição de gestão do processo
  (Admin, BraCVAM, `group_manager` efetivo) que a verificação do FR-002.
- **FR-010**: O comportamento entregue pela Spec 036 MUST se manter: filtros
  de `GET /tasks`, `GET /tasks/{id}` e da linha do tempo, dispensa visível só
  à gestão, `409` das rotas de formulário para atividade por laboratório.
- **FR-011**: A seção de permissões do README MUST descrever as regras deste
  documento.

### Key Entities

- **Execução de laboratório**: execução de uma atividade por laboratório,
  ligada a um laboratório (Spec 036).
- **Designação**: cargo de um usuário no processo; `participating_laboratory`
  e `lead_laboratory` levam o laboratório e só valem com vínculo ativo
  (Spec 035).
- **Gestão do processo**: Admin, BraCVAM e `group_manager` efetivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em um processo com dois laboratórios, 100% das tentativas do
  laboratório A de listar, ler ou concluir dados do laboratório B falham com
  "não encontrado".
- **SC-002**: A resposta à execução de outro laboratório é idêntica, em
  código e mensagem, à resposta a um laboratório sem execução.
- **SC-003**: 100% das operações do laboratório A sobre a própria execução
  seguem funcionando.
- **SC-004**: A matriz de testes cobre 9 perfis (laboratório dono, outro
  laboratório, líder, líder e participante por laboratórios distintos,
  Grupo de Seleção de Amostras, estatístico, `group_manager`, Admin,
  BraCVAM) por 5 operações (listar tarefas, abrir tarefa, linha do tempo,
  ler execução, concluir execução).
- **SC-005**: A suíte existente da Spec 036 passa sem alteração de
  expectativa.

## Assumptions

- Esta issue não cria rotas novas de conteúdo ou anexo. As issues #28 a #31
  criam essas rotas e chamam a verificação do FR-002.
- O cegamento de resultados para o estatístico e a revelação controlada na
  consolidação pertencem à issue #30.
- O `409` do FR-008 reaproveita o índice único existente e o código
  `duplicate`. A regra não exige migração.
- Não existem processos em produção com duas designações ativas de
  participante para o mesmo usuário: o índice único sempre impediu.
- Rotas de amostras (etiquetas, frascos, SDS) exigem editar
  `sample_definition` e ficam fora do alcance dos laboratórios. Não mudam.
