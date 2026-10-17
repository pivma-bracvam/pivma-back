# Feature Specification: Homologação da estrutura do estudo

**Feature Branch**: `feat/042-structure-approval`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "vamos fazer a issue #27 que foi designada a mim;
analise atentamente ela e a situacao do codigo e docmuentacao. lembre-se de
criar uma branch para implementacao e utilizar boas praticas. evite
complexidade desnecessária e lacunas ou debitos tecnicos."

- #27 ([E2-06] Aprovação Formal da Estrutura Montada): portão de governança.
  O método só chega à bancada (Etapa 3) depois que o BraCVAM homologa a
  equipe e as amostras montadas na Etapa 2. A reprovação de um ponto devolve
  a atividade correspondente para nova execução.

## Contexto

- **CONFIRMADO, fonte oficial**: o Plano de Trabalho cobre o pedido nos
  RF024 (etapas, responsáveis e critérios do fluxo), RF026 (aprovar,
  devolver ou rejeitar), RF027 (registro de deliberações e justificativas) e
  RF034 (logs e auditoria).
- **CONFIRMADO, issue #27 (atualização de 2026-10-04)**: a Análise
  Estatística (#25) saiu do escopo; a Atribuição de Cargo (#23) e a
  Definição de Amostras (#24) estão concluídas. A conclusão da issue exige
  um teste de jornada em `tests/integration/journeys/` que percorra
  reprovar, reexecutar e aprovar pela API pública, e um tutorial no
  `manual/` com essa história.
- **CONFIRMADO, implementação atual**: a Etapa 2
  (`phase_2_role_assignment`) é igual nos cinco templates de processo. Ela
  tem oito atividades de atribuição de cargo e a definição das amostras. A
  Etapa 3 (`phase_3_validation_execution`) abre quando a definição das
  amostras conclui. Nada entre as duas exige decisão do BraCVAM.
- **CONFIRMADO, implementação atual**: uma atribuição de cargo conclui na
  primeira designação do cargo sem convite pendente. Designar e revogar
  continuam permitidos depois da conclusão, então uma atividade concluída
  pode ficar sem nenhuma designação ativa.
- **CONFIRMADO, implementação atual**: a definição das amostras gera um
  código cego por substância e laboratório participante ativo no momento da
  conclusão. Um laboratório designado depois fica sem códigos; um revogado
  depois mantém os seus. A Etapa 3 abre execução para os laboratórios que
  têm códigos.
- **CONFIRMADO, implementação atual**: a triagem já decide sobre a
  submissão e, ao pedir ajustes, abre nova execução da atividade devolvida,
  guarda a anterior e bloqueia a triagem até o retorno. A homologação segue
  o mesmo padrão, com vários pontos em vez de um formulário.
- **CONFIRMADO, decisão da equipe (#26, decisão 5)**: a Etapa 3 começava na
  conclusão das amostras, e o template de coleta travava nesse momento.
  Esta feature muda as duas regras (ver Clarifications).
- **CONFIRMADO, revisão do PR #76 (2026-10-16)**: a equipe incluiu o plano
  estatístico na homologação e pediu que a atribuição de cargo reaberta não
  conclua sozinha na primeira designação (ver Clarifications, sessão
  2026-10-16).

## Clarifications

### Session 2026-10-14 (usuário)

- Q: A homologação exige plano estatístico? → A: Não. A homologação audita a
  equipe (atribuições de cargo) e as amostras. A #25 saiu do escopo e
  nenhuma fonte define o plano estatístico. Se ela voltar, acrescenta o
  ponto. A decisão vai para a descrição da PR e para a issue.
  **Substituída na sessão 2026-10-16.**
- Q: Quais atividades da Etapa 2 bloqueiam a aprovação? → A: As nove: as
  oito atribuições de cargo e a definição das amostras. **Passam a dez na
  sessão 2026-10-16.**
- Q: Quando o template de coleta trava, se a homologação pode reabrir as
  amostras? → A: Quando a Etapa 3 de algum processo vinculado começa. Nos
  processos novos isso acontece na aprovação da homologação. Nos processos
  criados antes desta feature, a Etapa 3 continua começando na conclusão
  das amostras, então a trava deles não muda. Esta regra substitui a
  decisão 5 da #26.
- Q: Como uma atribuição de cargo reaberta conclui de novo? → A: Na próxima
  designação ou na próxima revogação do cargo, desde que reste ao menos uma
  designação ativa e nenhum convite pendente. Não existe rota nova de
  conclusão. **Substituída na sessão 2026-10-16.**

- Q: Um convite adicional criado depois da conclusão do cargo bloqueia a
  homologação? → A: Não. Ele não reabre a atividade nem constitui, por si
  só, pendência. A aprovação considera as designações ativas e a
  consistência das amostras no momento da decisão. Em atividades abertas
  ou reabertas, os convites pendentes continuam impedindo a conclusão.

### Session 2026-10-16 (revisão do PR #76, equipe)

- Q: A homologação exige plano estatístico? → A: Sim, nesta entrega. A
  Etapa 2 ganha a atividade `statistical_plan`, do Estatístico, que abre
  quando a atribuição do estatístico conclui. Ela usa o formulário
  existente: plano em anexo, obrigatório, e resumo opcional. A homologação
  depende dela, e o plano vira um ponto que pode ser reprovado; a nova
  execução cria formulário novo e guarda o anterior. Sem avaliação por IA
  nesta entrega. O envio de formulário só cria o Dossiê de Submissão e só
  aciona a pré-avaliação e a triagem na submissão da proposta.
- Q: Quais atividades da Etapa 2 bloqueiam a aprovação? → A: As dez: as
  oito atribuições de cargo, o plano estatístico e a definição das
  amostras.
- Q: Como uma atribuição de cargo reaberta conclui de novo? → A: Quem gere o
  cargo declara que terminou a correção por uma rota de conclusão. A rota
  só aceita o cargo com ao menos uma designação ativa e nenhum convite
  pendente e recusa quem tem conflito de interesse vigente. Designar ou
  revogar não conclui a atividade reaberta, então a ordem entre designar a
  pessoa nova e revogar a antiga não importa. Na primeira execução, a
  atividade continua concluindo na designação ou na revogação.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - BraCVAM homologa a estrutura e libera a Etapa 3 (Priority: P1)

A equipe está montada e as amostras definidas. Uma tarefa de homologação
aparece para o BraCVAM. Ele abre o painel, confere cada ponto da Etapa 2 e
aprova com uma justificativa. Os laboratórios passam a ver o recebimento de
amostras.

**Why this priority**: sem a aprovação, nenhum processo novo chega à Etapa
3. É o caminho feliz e entrega o portão de governança.

**Independent Test**: num ambiente recém-provisionado, criar o processo,
passar pela triagem, designar os oito cargos, enviar o plano estatístico,
concluir as amostras, aprovar
a homologação e confirmar que o laboratório participante tem o recebimento
em andamento.

**Acceptance Scenarios**:

1. **Given** as dez atividades da Etapa 2 concluídas, **When** o BraCVAM
   consulta o processo, **Then** a homologação está em andamento com uma
   tarefa para o cargo BraCVAM, e o recebimento de amostras continua
   bloqueado.
2. **Given** a homologação em andamento, **When** o BraCVAM consulta o
   painel, **Then** vê os dez pontos com o estado de cada um, as pessoas e
   laboratórios designados em cada cargo, a contagem de substâncias,
   laboratórios e códigos das amostras e a lista de pendências, vazia.
3. **Given** o painel sem pendências, **When** o BraCVAM aprova com
   justificativa, **Then** a homologação conclui, a Etapa 2 conclui, o
   recebimento abre para cada laboratório com códigos e a linha do tempo
   registra quem aprovou, quando e com que justificativa.
4. **Given** a homologação aprovada, **When** alguém consulta a decisão,
   **Then** vê autor, data e justificativa, sem poder alterá-los.

---

### User Story 2 - BraCVAM reprova um ponto e a atividade volta para nova execução (Priority: P1)

O BraCVAM encontra um problema, por exemplo um laboratório errado. Ele
reprova o ponto com o motivo. A atividade volta para o responsável, que
corrige. Quando todos os pontos reprovados concluem de novo, a homologação
reabre e o BraCVAM aprova.

**Why this priority**: a issue chama este fluxo de ponto crítico. Sem ele o
processo trava sem caminho de correção, e a conclusão da issue depende do
teste de jornada deste fluxo.

**Independent Test**: a partir da homologação em andamento, reprovar a
atribuição de laboratórios participantes, conferir a nova execução com
tarefa para o Grupo Gestor, corrigir a designação, refazer as amostras se
preciso, aprovar e confirmar o recebimento aberto.

**Acceptance Scenarios**:

1. **Given** a homologação em andamento, **When** o BraCVAM reprova um ou
   mais pontos, cada um com motivo, e informa a justificativa da decisão,
   **Then** cada atividade reprovada volta a ficar em andamento com uma
   execução nova e uma tarefa para o cargo responsável, a homologação fica
   bloqueada aguardando a reexecução e a Etapa 3 continua bloqueada.
2. **Given** um ponto reprovado, **When** alguém consulta a atividade,
   **Then** a execução anterior continua visível, concluída, e a nova traz o
   motivo da reprovação.
3. **Given** uma atribuição de cargo reaberta, **When** o responsável
   designa alguém ou revoga uma designação, **Then** a atividade continua
   em andamento. **When** ele declara que terminou a correção e o cargo tem
   ao menos uma designação ativa e nenhum convite pendente, **Then** a
   atividade conclui.
4. **Given** a definição das amostras reaberta, **When** o Grupo de Seleção
   ajusta as substâncias e conclui de novo, **Then** os códigos passam a
   corresponder aos laboratórios participantes ativos e a atividade conclui.
5. **Given** todos os pontos reprovados concluídos de novo, **When** o
   último conclui, **Then** a homologação volta a ficar em andamento com
   execução e tarefa novas, e as decisões anteriores continuam no histórico.
6. **Given** a homologação reaberta e sem pendências, **When** o BraCVAM
   aprova, **Then** a Etapa 3 abre como na User Story 1.
7. **Given** uma atribuição de cargo reaberta, **When** o responsável
   designa a pessoa nova antes de revogar a antiga, **Then** a atividade e a
   homologação não avançam; depois que ele revoga a antiga e declara que
   terminou, a atividade conclui com só a pessoa nova no cargo.
8. **Given** uma atribuição de cargo reaberta com o cargo vazio ou com
   convite pendente, **When** o responsável declara que terminou, **Then** a
   declaração é recusada com conflito e nada muda.

---

### User Story 3 - A aprovação só acontece sobre uma estrutura completa e por quem pode decidir (Priority: P2)

O sistema recusa a aprovação quando a estrutura tem pendência, quando quem
decide não pode decidir e quando duas decisões chegam ao mesmo tempo.

**Why this priority**: são os critérios de aceite de bloqueio e de
autorização da issue. Sem eles o portão existe só no papel.

**Independent Test**: provocar cada recusa pela API e conferir que nenhum
estado muda.

**Acceptance Scenarios**:

1. **Given** alguma das dez atividades sem concluir, **When** o BraCVAM
   tenta decidir, **Then** a decisão é recusada com conflito, porque a
   homologação ainda não está aberta.
2. **Given** a homologação em andamento e um cargo sem designação ativa,
   **When** o BraCVAM tenta aprovar, **Then** a aprovação é recusada com
   conflito e o painel aponta o cargo como pendência.
3. **Given** a homologação em andamento e um laboratório participante ativo
   sem códigos cegos, ou códigos de laboratório que não participa mais,
   **When** o BraCVAM tenta aprovar, **Then** a aprovação é recusada com
   conflito e o painel aponta as amostras como pendência.
4. **Given** um usuário que vê o processo sem o cargo BraCVAM, **When** ele
   tenta decidir, **Then** recebe 403. Quem não vê o processo recebe 404.
5. **Given** um BraCVAM com conflito de interesse vigente no processo,
   **When** ele tenta decidir, **Then** a decisão é recusada.
6. **Given** duas decisões enviadas ao mesmo tempo para a mesma homologação,
   **When** as duas são processadas, **Then** só uma vale e a outra recebe
   conflito.
7. **Given** o processo encerrado, cancelado ou arquivado, **When** o
   BraCVAM tenta decidir, **Then** a decisão é recusada.
8. **Given** uma reprovação sem pontos, com ponto fora da Etapa 2, com ponto
   repetido ou sem motivo, **When** o BraCVAM envia, **Then** recebe erro de
   validação e nada muda.

---

### User Story 4 - O Estatístico envia o plano e o BraCVAM o confere (Priority: P1)

Quando o Grupo Gestor designa o Estatístico, uma tarefa de plano
estatístico aparece para ele. Ele anexa o plano, escreve um resumo se
quiser e envia. O plano vira um ponto da homologação. Se o BraCVAM o
reprovar, o Estatístico recebe um formulário novo e o plano anterior fica
no histórico.

**Why this priority**: a revisão do PR #76 tornou o plano obrigatório
para a homologação. Sem ele, nenhum processo novo chega à Etapa 3.

**Independent Test**: designar o Estatístico, enviar o plano com anexo,
concluir as amostras, conferir o ponto no painel, reprovar o plano,
enviar outro e aprovar.

**Acceptance Scenarios**:

1. **Given** a atribuição do estatístico concluída, **When** o Estatístico
   consulta as tarefas, **Then** vê a tarefa do plano estatístico pronta.
2. **Given** o formulário do plano sem anexo, **When** o Estatístico
   envia, **Then** recebe erro de validação e a atividade continua em
   andamento.
3. **Given** o plano anexado, **When** o Estatístico envia, **Then** a
   atividade conclui, a linha do tempo registra o envio e o processo não
   ganha Dossiê de Submissão, pré-avaliação por IA nem mudança na triagem.
4. **Given** a homologação em andamento, **When** o BraCVAM consulta o
   painel, **Then** vê o plano estatístico como ponto e lê o formulário
   enviado com o anexo.
5. **Given** o plano reprovado, **When** o Estatístico abre a tarefa,
   **Then** encontra um formulário novo, e o formulário anterior continua
   enviado na execução anterior e pode ser consultado pelo BraCVAM pelo
   número da execução.

---

### Edge Cases

- Ponto reprovado cujo trabalho não precisa de mudança: o responsável
  declara que terminou a atribuição de cargo sem mudar a equipe, conclui as
  amostras sem alteração ou envia o plano de novo.
- Reprovação de um cargo do qual outros dependem (por exemplo, o Grupo
  Gestor): só a atividade reprovada reabre. As dependentes já concluídas
  continuam concluídas; o BraCVAM reprova também as que quiser rever.
- Correção da equipe que não passou pela reprovação: designar e revogar
  continuam permitidos. O painel mostra o estado atual na hora da decisão,
  e as pendências da User Story 3 barram a aprovação.
- Convite adicional criado após a conclusão de um cargo já preenchido:
  a atividade continua concluída e o convite não bloqueia a homologação.
  Em atividade aberta ou reaberta, os convites pendentes impedem a conclusão.
- Laboratório excluído do cadastro depois da conclusão das amostras, com a
  designação ainda ativa: o painel aponta códigos de laboratório que não é
  participante ativo. A nova conclusão das amostras descarta esses códigos.
- Revogação enviada ao mesmo tempo que a aprovação: se a aprovação ganha, o
  resultado é o de uma revogação logo depois da aprovação, que já é
  permitida. A Etapa 3 segue com os laboratórios que têm códigos.
- Laboratório designado depois da conclusão das amostras: o painel aponta a
  divergência e a aprovação fica barrada até o BraCVAM reprovar as amostras
  e o Grupo de Seleção concluí-las de novo.
- Reprovação das amostras depois da impressão das etiquetas: os códigos dos
  laboratórios que continuam no estudo não mudam; a nova conclusão gera só
  os que faltam e descarta os de laboratório que saiu, como hoje.
- Processo criado antes desta feature: não ganha a homologação e segue o
  fluxo antigo, com a Etapa 3 abrindo na conclusão das amostras.
- Template de coleta vinculado a processo cujas amostras foram reabertas: o
  template continua travado se a Etapa 3 de algum processo vinculado já
  começou, e continua livre se nenhuma começou.

## Requirements *(mandatory)*

### Functional Requirements

**Atividade de homologação**

- **FR-001**: Os cinco templates de processo MUST ganhar, na Etapa 2, a
  atividade de homologação da estrutura, que só o cargo BraCVAM edita e que
  depende da conclusão das dez atividades da Etapa 2.
- **FR-002**: O recebimento de amostras (Etapa 3) MUST depender da
  conclusão da homologação, e não mais da conclusão das amostras.
- **FR-003**: Processos criados antes desta feature MUST manter o fluxo
  atual, sem homologação.

**Painel**

- **FR-004**: Quem vê a homologação MUST poder consultar o painel do
  processo com, para cada um dos dez pontos: chave, nome, estado, número
  da execução atual e pendências.
- **FR-005**: Nos pontos de atribuição de cargo, o painel MUST listar as
  designações ativas (pessoa e, quando houver, laboratório).
- **FR-006**: No ponto das amostras, o painel MUST mostrar só contagens de
  substâncias, laboratórios e códigos e os laboratórios com divergência.
  Ele NÃO DEVE mostrar nome químico, CAS, SDS nem códigos cegos.
- **FR-007**: O painel MUST trazer o estado da homologação e o histórico
  das decisões anteriores (resultado, autor, data, justificativa e pontos
  reprovados com motivo).
- **FR-008**: São pendências: atividade da Etapa 2 sem concluir; cargo sem
  designação ativa; laboratório participante ativo sem códigos; códigos
  ativos de laboratório que não é participante ativo. Laboratório
  participante ativo é o que tem designação ativa de participante e não foi
  excluído do cadastro, o mesmo conjunto que a conclusão das amostras usa.
  Convite adicional criado após a conclusão do cargo não constitui, por si
  só, pendência nem reabre a atividade.

**Decisão**

- **FR-009**: O cargo BraCVAM MUST poder aprovar a homologação em andamento
  com justificativa obrigatória.
- **FR-010**: A aprovação MUST ser recusada com conflito enquanto houver
  pendência (FR-008), calculada no momento da decisão.
- **FR-011**: A aprovação MUST concluir a homologação e a Etapa 2 e abrir a
  Etapa 3 pelo mecanismo de dependências existente.
- **FR-012**: O cargo BraCVAM MUST poder reprovar um ou mais pontos com
  justificativa da decisão e motivo obrigatório por ponto. Os pontos MUST
  ser atividades da Etapa 2 do processo, sem repetição.
- **FR-013**: A reprovação MUST concluir a execução atual da homologação,
  bloqueá-la aguardando a reexecução e, para cada ponto, abrir uma execução
  nova da atividade com o motivo e uma tarefa para o cargo responsável. As
  execuções anteriores MUST continuar intactas.
- **FR-014**: Quando o último ponto reprovado conclui de novo, a homologação
  MUST voltar a ficar em andamento com execução e tarefa novas, uma única
  vez, mesmo quando os últimos pontos concluem ao mesmo tempo.
- **FR-015**: Uma atribuição de cargo na primeira execução MUST concluir
  na designação ou na revogação do cargo, quando restar ao menos uma
  designação ativa e nenhum convite pendente. Uma atribuição reaberta pela
  homologação NÃO DEVE concluir na designação nem na revogação; ela conclui
  pela rota de FR-028.
- **FR-016**: A definição das amostras reaberta MUST aceitar alterações e
  nova conclusão pelas regras atuais.
- **FR-017**: A decisão MUST ser recusada se: a homologação não está em
  andamento (conflito); o processo não está aberto; quem decide tem
  conflito de interesse vigente; quem decide não vê o processo (404) ou não
  tem o cargo BraCVAM (403).
- **FR-018**: Duas decisões simultâneas sobre a mesma execução da
  homologação MUST resultar em uma aceita e outra recusada com conflito.
- **FR-019**: As rotas de escrita MUST exigir sessão e origem confiável.

**Plano estatístico**

- **FR-025**: Os cinco templates MUST ganhar, na Etapa 2, a atividade
  `statistical_plan`, que só o cargo Estatístico edita, que depende da
  atribuição do estatístico e que tem um formulário com o plano em anexo,
  obrigatório, e um resumo opcional. A homologação MUST depender dela.
- **FR-026**: O envio do formulário do plano MUST concluir a atividade,
  liberar as dependentes e registrar o envio na linha do tempo. Ele NÃO
  DEVE criar Dossiê de Submissão, abrir pré-avaliação por IA nem mudar a
  triagem; esses efeitos ficam restritos à submissão da proposta.
- **FR-027**: A reprovação do plano MUST abrir uma execução com formulário
  novo. O formulário anterior MUST continuar enviado na execução anterior.

**Conclusão da atribuição reaberta**

- **FR-028**: Quem pode designar um cargo MUST poder declarar concluída a
  atribuição desse cargo em andamento. A declaração MUST ser recusada com
  conflito se a atividade não está em andamento, se o cargo não tem
  designação ativa ou se há convite pendente para o cargo, com `403
  forbidden` quando a pessoa tem conflito de interesse vigente no processo,
  e com `process_closed` se o processo não aceita alterações. A declaração
  MUST concluir a execução, liberar as dependentes e registrar quem declarou
  na linha do tempo.

**Auditoria**

- **FR-020**: Cada decisão MUST ficar gravada com resultado, autor, data,
  justificativa e pontos reprovados com motivo, sem edição posterior.
- **FR-021**: A linha do tempo do processo MUST registrar a aprovação, a
  reprovação (com os pontos), a reabertura de cada atividade, o envio do
  plano estatístico e a declaração de conclusão da atribuição reaberta.

**Template de coleta**

- **FR-022**: Um template de coleta MUST travar quando a Etapa 3 de algum
  processo vinculado começa, e não mais na conclusão das amostras.

**Documentação**

- **FR-023**: O `manual/` MUST ganhar um tutorial com a história de
  reprovar, reexecutar e aprovar, e as páginas de referência (rotas,
  estados, eventos, erros, templates, escopo) MUST descrever a homologação.
- **FR-024**: `docs/observacoes-e-pendencias.md` MUST registrar as decisões
  desta feature e a mudança da decisão 5 da #26.

### Key Entities

- **Homologação da estrutura**: atividade da Etapa 2, do cargo BraCVAM, que
  depende das dez atividades da etapa e da qual a Etapa 3 depende. Cada
  abertura é uma execução.
- **Decisão de homologação**: resultado (aprovada ou reprovada), autor,
  data e justificativa, ligados à execução da homologação. Na reprovação,
  traz a lista de pontos com motivo.
- **Ponto auditado**: uma das dez atividades da Etapa 2, com seu estado,
  suas execuções e as pendências calculadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos processos novos, nenhum laboratório recebe tarefa
  da Etapa 3 antes de uma homologação aprovada.
- **SC-002**: O teste de jornada percorre, pela API pública e a partir de um
  ambiente recém-provisionado, reprovar um ponto, reexecutá-lo e aprovar,
  e termina com o recebimento aberto.
- **SC-003**: Cada pendência do FR-008 tem um teste que mostra a aprovação
  recusada e o estado intacto.
- **SC-004**: Para toda decisão, um auditor reconstrói pela API autor, data,
  justificativa, pontos reprovados e execuções reabertas, sem consultar o
  banco.
- **SC-005**: O painel de um processo não expõe nome químico, CAS, SDS nem
  código cego a nenhum perfil, provado por teste.
- **SC-006**: Os testes de jornada e de fluxo já existentes da Etapa 3
  passam depois de incluir a aprovação no preparo.

## Assumptions

- **INFERÊNCIA**: decide o cargo BraCVAM, como na triagem. Admin vê a
  homologação, mas só decide se tiver o cargo BraCVAM.
- **INFERÊNCIA**: o painel segue a visibilidade da atividade de
  homologação: Admin e BraCVAM. Os demais cargos não veem o painel.
- **INFERÊNCIA**: a reprovação não encerra o processo. Encerrar continua a
  cargo das rotas de ciclo de vida existentes.
- **INFERÊNCIA**: esta feature não envia notificações novas. O responsável
  vê a reexecução pela sua lista de tarefas, como na diligência da triagem.
- **INFERÊNCIA**: designar e revogar fora de uma reprovação continuam
  permitidos; o painel e as pendências cobrem o risco.
- Os testes e fábricas que levam um processo à Etapa 3 passam a aprovar a
  homologação no preparo.
- Reuniões e atas (RF028) e a avaliação por IA do plano estatístico ficam
  fora desta feature.
