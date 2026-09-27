# Feature Specification: Definição e Preparação das Amostras — estudo cego

**Feature Branch**: `feat/031-blind-sample-coding`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Vamos implementar essa issue" — issue #24,
"[E2-03] Definição e Preparação das Amostras — estudo cego, códigos por
laboratório e etiquetas".

## Contexto

O ensaio interlaboratorial precisa de amostras codificadas para que os
laboratórios participantes não saibam qual substância estão testando. O Plano
de Trabalho da Fase II pede o cadastro, a codificação e o embaralhamento das
amostras (RF038) e a preservação do cegamento (RF050). Também exige que o
sistema impeça a troca de informações entre laboratórios.

O protótipo (`docs/guia-prototipo.md`, seção 5, `CONFIRMADO NO MATERIAL`)
mostra a tarefa "Definição e Preparação das Amostras", executada pelo Grupo
de Seleção de Amostras. O Grupo cadastra a substância com o documento SDS em
PDF, vê o código cego na tabela e imprime etiquetas com estudo, laboratório
destinatário, código cego e QR code. Depois disso, conclui o cadastro. O
protótipo não mostra como o código é gerado nem para onde o QR code leva
(`DÚVIDA / PONTO A VALIDAR`). Esta spec decide esses dois pontos.

Hoje só o template 04 tem a Fase 2, com as oito atividades de atribuição de
cargo da Spec 028. Os templates 01, 02, 03 e 05 terminam na Fase 1. Todo
laboratório participante é designado com um laboratório cadastrado, e é por
esse laboratório que os códigos cegos são gerados.

## Clarifications

### Session 2026-09-26

- Q: Para onde o QR code do frasco leva? → A: Para uma rota que exige login e
  mostra só a visão cega do frasco. Nome químico, CAS e SDS original nunca
  aparecem por ela (FR-020, FR-021).
- Q: O mesmo CAS pode ser cadastrado duas vezes no processo, para duplicata
  cega? → A: Não. O CAS é único dentro do processo e pode se repetir em outro
  processo. A duplicata cega fica fora do escopo (FR-005).
- Q: Quem monta a etiqueta? → A: O backend entrega os dados e o QR code em
  imagem; o frontend faz o layout e a impressão (FR-018).
- Q: Onde fica a atividade? → A: Na Fase 2 de todos os templates. Os
  templates que ainda não têm Fase 2 recebem a Fase 2 completa do template 04
  (as oito atribuições de cargo) mais esta atividade (FR-001, FR-002).
- Q: Quem executa a atividade? → A: O cargo `sample_selection_group` (Grupo de
  Seleção de Amostras), sem vínculo com laboratório (FR-003).
- Q: Quando os códigos são gerados? → A: Ao cadastrar a substância, para os
  laboratórios já vinculados. Na conclusão, o sistema cria as combinações que
  faltam e congela o conjunto (FR-010, FR-013).
- Q: Quem mais vê os códigos, o mapeamento e a SDS? → A: Ninguém. Nem os
  laboratórios participantes, nem o Grupo Gestor, nem admin ou BraCVAM, que
  pela Spec 030 veem toda atividade. Eles veem só o status da atividade
  (FR-022 a FR-024).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cadastrar substâncias e gerar códigos cegos (Priority: P1)

O Grupo de Seleção de Amostras abre a atividade "Definição e Preparação das
Amostras" do processo e cadastra cada substância do estudo. Ao salvar, o
sistema gera um código cego diferente para cada laboratório participante
vinculado. O Grupo vê a tabela com substância, CAS, lote e os códigos de cada
laboratório.

**Why this priority**: sem substâncias e códigos cegos não há estudo cego; as
etiquetas, a conclusão e as próximas etapas (recebimento, #28) dependem disso.

**Independent Test**: num processo com 3 laboratórios participantes,
cadastrar 4 substâncias e verificar 12 códigos únicos, sem padrão entre eles.

**Acceptance Scenarios**:

1. **Given** um processo com a atividade em andamento e 3 laboratórios
   participantes vinculados, **When** o Grupo de Seleção cadastra uma
   substância válida, **Then** a substância é salva e recebe 3 códigos cegos,
   um por laboratório, todos diferentes.
2. **Given** 4 substâncias cadastradas nesse processo, **When** o Grupo lista
   as substâncias, **Then** vê 12 códigos cegos únicos no processo.
3. **Given** uma substância já cadastrada com o CAS 50-00-0 no processo,
   **When** o Grupo cadastra outra substância com o mesmo CAS no mesmo
   processo, **Then** o cadastro é recusado com mensagem de CAS duplicado.
4. **Given** uma substância com o CAS 50-00-0 em outro processo, **When** o
   Grupo cadastra esse CAS neste processo, **Then** o cadastro é aceito.
5. **Given** um CAS com formato ou dígito verificador inválido, **When** o
   Grupo tenta cadastrá-lo, **Then** o cadastro é recusado.
6. **Given** a atividade em andamento, **When** o Grupo corrige os dados de
   uma substância, **Then** os dados mudam e os códigos cegos dela continuam
   os mesmos.
7. **Given** a atividade em andamento, **When** o Grupo remove uma substância,
   **Then** a substância e os códigos dela deixam de existir.
8. **Given** um usuário que não é do Grupo de Seleção de Amostras do processo,
   **When** tenta cadastrar, alterar ou remover uma substância, **Then** a
   ação é negada.

---

### User Story 2 - Concluir o cadastro e congelar os códigos (Priority: P1)

Quando todas as substâncias estão cadastradas, o Grupo de Seleção conclui a
atividade. O sistema completa as combinações que faltam (por exemplo, de um
laboratório vinculado depois do cadastro), descarta códigos de laboratórios
que deixaram o processo e congela o conjunto.

**Why this priority**: sem a conclusão o conjunto de códigos pode mudar a
qualquer momento, e a atividade nunca fecha na Fase 2.

**Independent Test**: cadastrar 2 substâncias com 2 laboratórios, vincular um
terceiro laboratório, concluir e verificar 6 códigos e a atividade concluída.

**Acceptance Scenarios**:

1. **Given** 2 substâncias cadastradas com 2 laboratórios e um terceiro
   laboratório vinculado depois, **When** o Grupo conclui a atividade,
   **Then** o sistema gera os 2 códigos que faltam e a atividade fica
   concluída com 6 códigos.
2. **Given** um laboratório com códigos gerados que deixou o processo antes
   da conclusão, **When** o Grupo conclui, **Then** os códigos desse
   laboratório são descartados.
3. **Given** uma atividade sem nenhuma substância, **When** o Grupo tenta
   concluir, **Then** a conclusão é recusada.
4. **Given** uma substância sem SDS anexada, **When** o Grupo tenta concluir,
   **Then** a conclusão é recusada e a resposta indica a substância sem SDS.
5. **Given** um processo sem nenhum laboratório participante vinculado,
   **When** o Grupo tenta concluir, **Then** a conclusão é recusada.
6. **Given** a atividade concluída, **When** o Grupo tenta cadastrar, alterar
   ou remover substância, **Then** a ação é recusada.

---

### User Story 3 - Emitir os dados das etiquetas (Priority: P2)

O Grupo de Seleção obtém, para cada frasco (substância × laboratório), os
dados da etiqueta: estudo, laboratório destinatário, código cego, lote e QR
code. O frontend monta e imprime as etiquetas.

**Why this priority**: o frasco físico precisa de etiqueta para ser enviado,
mas o cadastro e os códigos (P1) já têm valor antes dela.

**Independent Test**: com 4 substâncias e 3 laboratórios, pedir as etiquetas
e verificar 12 etiquetas com QR code legível que leva à rota do frasco.

**Acceptance Scenarios**:

1. **Given** 4 substâncias e 3 laboratórios, **When** o Grupo pede as
   etiquetas do processo, **Then** recebe 12 etiquetas, uma por frasco, com
   estudo, laboratório, código cego, lote e QR code.
2. **Given** uma etiqueta emitida, **When** o QR code é lido, **Then** ele
   contém o endereço da rota do frasco e nada mais: nem nome químico, nem CAS.
3. **Given** um usuário fora do Grupo de Seleção do processo, **When** pede
   as etiquetas, **Then** o pedido é negado.

---

### User Story 4 - Consultar o frasco pelo QR code sem quebrar o cegamento (Priority: P2)

Quem lê o QR code chega a uma rota que exige login. Ela mostra só a visão
cega do frasco: código cego, lote e instruções de manuseio seguro (perigos,
EPI, primeiros socorros). Nesta feature, só o Grupo de Seleção do processo
tem acesso; o acesso dos laboratórios fica para o recebimento (#28).

**Why this priority**: o QR code é o ponto de maior risco de quebra de
cegamento; a rota precisa existir com o controle certo antes que qualquer
frasco saia.

**Independent Test**: ler o QR code sem login, com um usuário de laboratório
participante e com o Grupo de Seleção, e verificar a resposta de cada um.

**Acceptance Scenarios**:

1. **Given** um QR code de frasco, **When** a rota é acessada sem login,
   **Then** o acesso é negado.
2. **Given** um membro do Grupo de Seleção do processo, **When** acessa a
   rota, **Then** vê código cego, lote e instruções de manuseio seguro, sem
   nome químico, CAS nem SDS original.
3. **Given** um usuário de laboratório participante, BraCVAM, admin ou Grupo
   Gestor, **When** acessa a rota, **Then** o acesso é negado.

---

### User Story 5 - Nenhum outro perfil vê o conteúdo das amostras (Priority: P1)

Só o Grupo de Seleção de Amostras do processo vê substâncias, códigos cegos,
correspondência entre código e substância e SDS original. Os demais perfis,
inclusive os que veem toda atividade pela Spec 030, veem só a existência e o
status da atividade.

**Why this priority**: um único vazamento do mapeamento invalida o estudo
inteiro.

**Independent Test**: com substâncias cadastradas, consultar as rotas de
amostras como laboratório participante, Grupo Gestor, BraCVAM e admin, e
verificar negação em todas.

**Acceptance Scenarios**:

1. **Given** substâncias cadastradas, **When** um laboratório participante
   consulta a lista de substâncias, os códigos ou as etiquetas, **Then** o
   acesso é negado.
2. **Given** substâncias cadastradas, **When** o Grupo Gestor, o BraCVAM ou o
   admin consulta a lista de substâncias, os códigos ou as etiquetas,
   **Then** o acesso é negado.
3. **Given** uma SDS anexada, **When** qualquer perfil fora do Grupo de
   Seleção tenta baixá-la, **Then** o acesso é negado.
4. **Given** um membro do Grupo de Seleção do processo A, **When** consulta as
   amostras do processo B, onde não tem esse cargo, **Then** o acesso é
   negado.
5. **Given** admin ou BraCVAM, **When** consultam as atividades do processo,
   **Then** veem a atividade de amostras e seu status, sem o conteúdo.

---

### User Story 6 - Fase 2 em todos os templates (Priority: P1)

Todos os templates de processo passam a ter a Fase 2 com as oito atribuições
de cargo e a atividade de amostras. A atividade de amostras abre quando o
Grupo de Seleção de Amostras e os laboratórios participantes já foram
atribuídos.

**Why this priority**: sem a Fase 2, processos dos templates 01, 02, 03 e 05
nunca chegam à atividade de amostras nem têm laboratórios vinculados.

**Independent Test**: criar um processo em cada template, concluir a triagem,
atribuir os cargos e verificar que a atividade de amostras abre só depois das
duas atribuições exigidas.

**Acceptance Scenarios**:

1. **Given** um processo novo de qualquer um dos cinco templates, **When** a
   triagem é aprovada, **Then** o processo tem a Fase 2 com as oito atividades
   de atribuição de cargo e a atividade de amostras.
2. **Given** a Fase 2 em andamento, **When** só o Grupo de Seleção foi
   atribuído, **Then** a atividade de amostras continua bloqueada.
3. **Given** a Fase 2 em andamento, **When** o Grupo de Seleção e ao menos um
   laboratório participante foram atribuídos, **Then** a atividade de
   amostras fica disponível ao Grupo de Seleção.
4. **Given** um processo criado numa versão anterior de um template, **When**
   a nova versão é publicada, **Then** o processo existente continua com a
   estrutura da versão em que foi criado.

---

### Edge Cases

- Laboratório vinculado depois da conclusão da atividade não recebe código;
  a reabertura da atividade fica fora do escopo.
- Dois cadastros simultâneos com o mesmo CAS no mesmo processo: só um é
  aceito.
- Colisão na geração de código: o sistema gera outro até obter um código
  único no processo, sem expor erro ao usuário.
- Mesmo usuário com dois cargos no processo (por exemplo, Grupo de Seleção e
  laboratório participante): o acesso segue o cargo de Grupo de Seleção. A
  spec não impede essa combinação.
- Processo encerrado, cancelado ou arquivado: cadastro, alteração, remoção e
  conclusão são recusados.
- SDS que não é PDF ou que excede o limite de tamanho: o anexo é recusado.
- Um laboratório com mais de um usuário designado: recebe um único código por
  substância, compartilhado pelos seus usuários.

## Requirements *(mandatory)*

### Functional Requirements

**Estrutura dos templates**

- **FR-001**: Os templates 01, 02, 03 e 05 MUST receber uma nova versão com a
  Fase 2 igual à do template 04: as oito atividades de atribuição de cargo,
  com os mesmos responsáveis e dependências.
- **FR-002**: Os cinco templates MUST ter, na Fase 2, a atividade "Definição e
  Preparação das Amostras", que só abre depois de concluídas as atividades de
  atribuição do Grupo de Seleção de Amostras e dos Laboratórios
  Participantes.
- **FR-003**: A atividade MUST conceder edição só ao cargo Grupo de Seleção de
  Amostras e nenhuma visualização a outros cargos.
- **FR-004**: Processos existentes MUST continuar na versão de template em
  que foram criados.

**Cadastro de substâncias**

- **FR-005**: O Grupo de Seleção MUST poder cadastrar substâncias no processo
  com nome químico, CAS, lote, pureza, solubilidade e instruções de manuseio
  seguro. Nome químico, CAS, lote e instruções de manuseio são obrigatórios.
  O CAS MUST ser único no processo.
- **FR-006**: O sistema MUST recusar CAS com formato ou dígito verificador
  inválido.
- **FR-007**: O Grupo de Seleção MUST poder anexar a SDS/FDS original em PDF a
  cada substância, e substituí-la enquanto a atividade estiver em andamento.
- **FR-008**: O Grupo de Seleção MUST poder alterar e remover substâncias
  enquanto a atividade estiver em andamento. Alterar não muda os códigos;
  remover apaga os códigos da substância.
- **FR-009**: Cadastro, alteração, remoção e anexo MUST ser recusados com a
  atividade concluída ou com o processo fora do ciclo de vida `OPEN`.

**Códigos cegos**

- **FR-010**: Ao cadastrar uma substância, o sistema MUST gerar um código cego
  para cada laboratório com designação ativa de laboratório participante no
  processo.
- **FR-011**: O código cego MUST ser curto (6 a 8 caracteres alfanuméricos),
  pseudoaleatório e único no processo, sem sequência nem parte que
  identifique substância ou laboratório.
- **FR-012**: Cada laboratório MUST ter um único código por substância,
  independentemente de quantos usuários dele estejam designados.
- **FR-013**: Ao concluir a atividade, o sistema MUST gerar os códigos das
  combinações substância × laboratório que faltam, descartar os de
  laboratórios sem designação ativa e congelar o conjunto.
- **FR-014**: A conclusão MUST ser recusada quando o processo não tiver
  substância, quando alguma substância não tiver SDS ou quando não houver
  laboratório participante vinculado.

**Etiquetas e QR code**

- **FR-015**: O Grupo de Seleção MUST poder obter os dados de etiqueta de cada
  frasco: identificação do estudo, nome do laboratório destinatário, código
  cego, lote e QR code em imagem.
- **FR-016**: O QR code MUST conter só o endereço da rota do frasco, sem nome
  químico, CAS ou outro dado da substância.
- **FR-017**: O endereço do QR code MUST identificar o frasco sem expor o
  identificador interno da substância.
- **FR-018**: O sistema MUST fornecer os dados e a imagem do QR code; o layout
  e a impressão ficam com o frontend.
- **FR-019**: Os dados de etiqueta MUST estar disponíveis enquanto houver
  códigos, com a atividade em andamento ou concluída.
- **FR-020**: A rota do frasco MUST exigir login.
- **FR-021**: A rota do frasco MUST responder só com código cego, lote e
  instruções de manuseio seguro, e só ao Grupo de Seleção do processo nesta
  feature.

**Isolamento**

- **FR-022**: Substâncias, códigos, correspondência código → substância,
  etiquetas e SDS original MUST ser acessíveis só ao Grupo de Seleção de
  Amostras do processo.
- **FR-023**: A visualização implícita de admin e BraCVAM em toda atividade
  (Spec 030) MUST se limitar à existência e ao status da atividade de
  amostras, sem o conteúdo.
- **FR-024**: Laboratórios participantes, laboratório líder e Grupo Gestor
  MUST ter acesso negado a todo o conteúdo de amostras nesta feature.

**Auditoria**

- **FR-025**: O sistema MUST registrar na trilha de auditoria o cadastro, a
  alteração e a remoção de substância, o anexo e o download da SDS, a geração
  de códigos e a conclusão da atividade, com autor e processo. O registro de
  auditoria MUST NOT conter nome químico nem CAS ao lado de código cego.

### Key Entities

- **Substância do estudo**: substância cadastrada num processo. Tem nome
  químico, CAS (único no processo), lote, pureza, solubilidade, instruções de
  manuseio seguro e a SDS original.
- **Código cego**: identificador opaco de um frasco, ligado a uma substância e
  a um laboratório participante do processo. Único no processo.
- **Etiqueta**: visão derivada de um código cego para impressão (estudo,
  laboratório, código, lote, QR code). Não é armazenada separadamente.
- **Atividade de amostras**: atividade da Fase 2 que controla em que momento
  o cadastro pode mudar e quando o conjunto de códigos é congelado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Com 4 substâncias e 3 laboratórios, o processo tem exatamente 12
  códigos cegos, todos diferentes.
- **SC-002**: Em 1.000 códigos gerados num processo de teste, nenhum se
  repete e nenhum revela substância ou laboratório por prefixo, sufixo ou
  ordem de geração.
- **SC-003**: 100% das consultas ao conteúdo de amostras feitas por perfis
  fora do Grupo de Seleção do processo são negadas.
- **SC-004**: Nenhuma resposta da rota do frasco nem nenhum QR code contém
  nome químico, CAS ou SDS.
- **SC-005**: Um processo novo de cada um dos cinco templates chega à
  atividade de amostras depois de atribuídos o Grupo de Seleção e ao menos um
  laboratório participante.
- **SC-006**: O Grupo de Seleção cadastra uma substância e vê seus códigos em
  uma única ação de salvar.

## Assumptions

- O laboratório líder não recebe códigos só por ser líder. Se também for
  participante, recebe como participante.
- O acesso dos laboratórios participantes aos próprios códigos e à rota do
  frasco é da issue #28 (recebimento de amostras).
- Despacho (RF039), recebimento (RF040), perda e devolução ficam fora do
  escopo.
- A SDS segue as regras de anexo já existentes na plataforma (tipo e tamanho);
  só PDF é aceito.
- A SDS é obrigatória para concluir, não para cadastrar, porque o Grupo pode
  receber a ficha depois da substância.
- A identificação do estudo na etiqueta usa o identificador do processo já
  exibido na plataforma.
- As atividades copiadas para a Fase 2 dos templates 01, 02, 03 e 05 mantêm
  nomes, responsáveis e dependências do template 04, incluindo as regras de
  convite da Spec 028.
- Seeds e demonstrações existentes continuam funcionando; os processos novos
  passam a usar as novas versões dos templates.
- Duplicata cega e reabertura da atividade após a conclusão ficam fora do
  escopo.
