# Feature Specification: Padrão de listagens e lista de tarefas para o quadro de atividades

**Feature Branch**: `feat/032-listing-standard-tasks`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: alinhamento de 2026-09-27. "Uma das ideias da plataforma é ter um kanban para controle das atividades. O BraCVAM tem acesso a visualizar todas as atividades de todos os usuários, pode ficar um pouco confuso. Gostaria que fosse possível filtrar as atividades no endpoint /tasks [...] e outras informações adicionadas ao schema de forma que não polua demais o endpoint, mas seja possível entender, por exemplo, que existem X processos sendo avaliados pela IA nesse momento, dois em estado de rascunho/submissão e que eu preciso validar três outras submissões." Na mesma conversa, o usuário pediu uma padronização de todas as listagens da API, com envelope, paginação por página, filtros aplicados, ordenação, contagens sob demanda e referências resumidas às entidades relacionadas.

## Contexto

A lista de tarefas é a base do quadro de atividades (kanban) do frontend. A Spec 029 removeu o Kanban antigo porque "a forma de expor atividades será remodelada". Esta spec faz essa remodelação.

Hoje a lista de tarefas tem estes problemas:

- Admin e BraCVAM veem todas as atividades de todos os processos, porque têm concessão de ver em todas. A lista não diz em quais tarefas o usuário pode agir, então o BraCVAM recebe as tarefas do proponente, do Grupo Gestor e do Grupo de Seleção misturadas com as dele. As tarefas são atribuídas a um cargo, nunca a uma pessoa, e o filtro por cargo compara só o cargo da tarefa.
- A lista traz as tarefas de todas as execuções (rodadas) de cada atividade. O frontend precisa descobrir sozinho qual é a vigente.
- A lista não tem paginação nem ordem definida. A resposta cresce com cada processo e cada rodada, e a ordem pode mudar entre chamadas.
- A pré-avaliação por IA não é uma atividade e não gera tarefa. Enquanto ela roda, o processo não aparece na lista, e não há como saber quantos processos estão sendo avaliados.

A API também não tem um padrão de listagem. Das 21 listagens, 15 devolvem uma lista simples e 6 usam envelopes em três formatos diferentes. As entidades relacionadas aparecem de três jeitos: identificador solto (participantes, convites), campos achatados com prefixo (tarefas) e objeto embutido (afiliações).

Esta spec define o padrão de listagem e a convenção de referências resumidas, e os aplica à lista de tarefas. A Spec 033 migra as outras 20 listagens e a Spec 034 padroniza as respostas de erro. As três chegam ao frontend juntas, num único changelog.

## Clarifications

### Session 2026-09-27

Decisões tomadas na conversa de alinhamento, antes desta spec:

- Q: A rodada vigente deve ser o padrão da lista de tarefas? → A: Sim. O histórico passa a exigir um pedido explícito.
- Q: Paginação por página ou por deslocamento? → A: Por página, com total de itens, total de páginas e indicação de página seguinte e anterior.
- Q: As contagens do quadro ficam num endpoint separado? → A: Não. Ficam na própria listagem, como contagens por valor de filtro e um resumo, entregues só quando pedidas.
- Q: A resposta leva um bloco de metadados (tempo de execução, cache, carimbo de hora)? → A: Não por enquanto. Pode entrar depois sem quebrar o contrato.
- Q: Rascunho e "ainda não iniciado" da submissão precisam ser distinguidos? → A: Não. Ambos aparecem como tarefa aberta de submissão.
- Q: Como representar entidades relacionadas? → A: Referências resumidas, pequenas e fixas, embutidas em um nível só, com descrição em cada campo.
- Q: Padronizar listagens e erros agora, mesmo quebrando contratos? → A: Sim. As mudanças são separadas em três specs e entregues ao frontend de uma vez.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver só as tarefas em que posso agir (Priority: P1)

O BraCVAM abre o quadro e pede só as tarefas em que pode agir. Vê as triagens que precisa decidir, sem as submissões do proponente nem as atividades de outros cargos. Qualquer outro usuário faz o mesmo e vê só o que é dele.

**Why this priority**: É a queixa que motivou a spec. Sem isso, o quadro do BraCVAM mistura o que ele precisa fazer com o que só acompanha.

**Independent Test**: Com processos em várias etapas, o BraCVAM pede as tarefas em que pode agir e recebe só as de triagem abertas e as atividades da Fase 2 que cabem ao BraCVAM. Cada tarefa da lista completa informa se o usuário pode agir.

**Acceptance Scenarios**:

1. **Given** três processos aguardando triagem e dois com submissão em aberto, **When** o BraCVAM pede as tarefas em que pode agir, **Then** recebe as três triagens e nenhuma submissão.
2. **Given** o mesmo cenário, **When** o BraCVAM pede todas as tarefas que vê, **Then** recebe as cinco, e cada uma informa se ele pode agir (três sim, duas não).
3. **Given** um proponente com uma submissão em aberto e uma triagem pendente no mesmo processo, **When** ele pede as tarefas em que pode agir, **Then** recebe só a submissão.
4. **Given** um membro do BraCVAM com conflito de interesse vigente em um processo, **When** ele pede as tarefas em que pode agir, **Then** a triagem desse processo não aparece. Na lista completa, ela aparece com a indicação de que ele não pode agir.
5. **Given** o Admin, que vê a triagem mas não a decide, **When** ele pede as tarefas em que pode agir, **Then** a triagem não aparece.

---

### User Story 2 - Montar o quadro de uma etapa com contagens em uma chamada (Priority: P1)

O BraCVAM monta o quadro da etapa 1. Numa só chamada recebe as tarefas vigentes da etapa e as contagens por coluna: quantas submissões estão abertas, quantas triagens aguardam decisão, quantas revisões de retorno estão com o proponente e quantos processos estão em avaliação pela IA.

**Why this priority**: É a visão que o quadro precisa mostrar. Sem as contagens na resposta, o frontend teria de baixar todas as páginas para contar.

**Independent Test**: Com 4 processos em avaliação pela IA, 2 submissões abertas, 3 triagens pendentes e 1 revisão de retorno aberta, o BraCVAM pede as tarefas abertas da etapa 1 com contagens e resumo. As contagens por atividade dão 2, 3 e 1, e o resumo informa 4 processos em avaliação pela IA.

**Acceptance Scenarios**:

1. **Given** o cenário acima, **When** o BraCVAM pede as tarefas abertas da etapa 1 com contagens, **Then** as contagens por atividade são: submissão 2, triagem 3, revisão do retorno 1.
2. **Given** o cenário acima, **When** o pedido inclui o resumo, **Then** o resumo informa 4 processos em avaliação pela IA.
3. **Given** um pedido com página de 2 itens, **When** a resposta chega, **Then** as contagens continuam refletindo todos os 6 itens filtrados, não só os 2 da página.
4. **Given** um pedido sem contagens nem resumo, **When** a resposta chega, **Then** esses blocos não aparecem.
5. **Given** um processo cuja submissão foi reenviada duas vezes, **When** o quadro é montado com o padrão, **Then** só a rodada vigente de cada atividade entra na lista e nas contagens.
6. **Given** um proponente sem acesso aos processos de outros, **When** ele pede o resumo, **Then** o número de processos em avaliação pela IA conta só os processos dele.

---

### User Story 3 - Filtrar, ordenar e paginar a lista de tarefas (Priority: P1)

Quem usa o quadro filtra por etapa, por atividade, por status (um ou vários), por processo, por cargo e pelas tarefas atrasadas. Pode pedir o histórico de rodadas quando precisar. A lista chega em páginas, numa ordem estável, e a resposta informa os filtros e a ordenação aplicados, inclusive os padrões.

**Why this priority**: Sem paginação e ordem estável, a lista do BraCVAM cresce sem limite e não dá para paginar com segurança.

**Independent Test**: Com 45 tarefas visíveis, pedir a página 2 com 20 itens devolve os itens 21 a 40, informa 45 itens, 3 páginas, que há página seguinte e anterior, e a ordem se repete em chamadas seguidas.

**Acceptance Scenarios**:

1. **Given** 45 tarefas visíveis, **When** o usuário pede a página 2 com 20 por página, **Then** recebe 20 itens, total de 45, 3 páginas, página seguinte e anterior disponíveis.
2. **Given** o mesmo cenário, **When** pede a página 5, **Then** recebe lista vazia com os totais corretos, sem erro.
3. **Given** um pedido sem ordenação, **When** a resposta chega, **Then** as tarefas vêm por prazo crescente, as sem prazo por último, e a ordenação aplicada aparece na resposta.
4. **Given** um pedido sem filtro de rodada, **When** a resposta chega, **Then** os filtros aplicados mostram que só a rodada vigente foi considerada.
5. **Given** um pedido com o histórico de rodadas, **When** a resposta chega, **Then** as tarefas de rodadas anteriores também aparecem.
6. **Given** tarefas abertas com prazo vencido e no prazo, **When** o usuário pede as atrasadas, **Then** recebe só as abertas com prazo vencido.
7. **Given** um pedido com dois status, **When** a resposta chega, **Then** traz tarefas de qualquer um dos dois.
8. **Given** um pedido com valor de status, ordenação ou tamanho de página inválido, **When** a API responde, **Then** recusa com erro de validação e não devolve lista vazia.

---

### User Story 4 - Referências resumidas às entidades relacionadas (Priority: P2)

O frontend mostra o código e o título do processo e a etapa de cada tarefa sem outra chamada. A lista traz esses dados como referências resumidas, no mesmo formato que as outras listagens vão usar.

**Why this priority**: Define a convenção que a Spec 033 aplica ao resto da API. Aqui ela se aplica só às tarefas.

**Independent Test**: Cada tarefa traz o processo como uma referência com identificador, código e título, e a etapa como uma referência com chave e ordem, sem campos achatados com prefixo.

**Acceptance Scenarios**:

1. **Given** uma tarefa de um processo, **When** ela aparece na lista, **Then** o processo vem como referência com identificador, código e título.
2. **Given** a mesma tarefa, **When** ela aparece na lista, **Then** a etapa vem como referência com chave e ordem.
3. **Given** a documentação interativa da API, **When** alguém consulta os schemas de referência, **Then** cada campo tem descrição.

---

### User Story 5 - Envelope único de listagem (Priority: P2)

O frontend usa um componente de listagem único. A lista de tarefas chega no envelope padrão: os itens, a paginação, os filtros aplicados, a ordenação e, quando pedidos, as contagens e o resumo. As próximas specs aplicam o mesmo envelope às outras listagens.

**Why this priority**: O formato do envelope é o contrato mais caro de mudar depois. Esta spec o fixa.

**Independent Test**: A resposta da lista de tarefas tem exatamente os blocos do envelope, com os mesmos nomes e tipos descritos na documentação, e os campos opcionais só aparecem quando pedidos.

**Acceptance Scenarios**:

1. **Given** qualquer pedido válido à lista de tarefas, **When** a resposta chega, **Then** ela tem os blocos de itens, paginação, filtros aplicados e ordenação.
2. **Given** um pedido que inclui contagens e resumo, **When** a resposta chega, **Then** esses blocos aparecem além dos obrigatórios.

---

### Edge Cases

- Usuário sem nenhuma tarefa visível: lista vazia, total 0, 0 páginas, sem página seguinte nem anterior.
- Tarefa sem prazo: fica por último na ordenação por prazo e nunca entra no filtro de atrasadas.
- Tarefa concluída ou cancelada com prazo vencido: não conta como atrasada.
- Processo com avaliação por IA reprocessada pelo administrador: conta uma vez no resumo, pela execução mais recente.
- Atividade de amostras cegas: a tarefa aparece para Admin e BraCVAM, que têm concessão de ver, marcada como "não pode agir". A lista e as contagens nunca trazem conteúdo das amostras.
- Filtro "só onde posso agir" combinado com o histórico: tarefas concluídas de rodadas antigas continuam marcadas pela concessão atual do usuário.
- Pedido de contagens com filtro por atividade: as contagens refletem o conjunto filtrado, então só aquela atividade aparece.
- Processo encerrado, cancelado ou arquivado: suas tarefas continuam na lista com o status que tiverem. Nenhum filtro esconde processos por ciclo de vida nesta spec.

## Requirements *(mandatory)*

### Functional Requirements

**Envelope de listagem (padrão para toda a API)**

- **FR-001**: Toda listagem que adotar o padrão DEVE responder com um envelope contendo: os itens, a paginação, os filtros aplicados e a ordenação aplicada.
- **FR-002**: A paginação DEVE ser por página e informar a página atual, o tamanho da página, o total de itens, o total de páginas e se existem página seguinte e anterior.
- **FR-003**: A página DEVE começar em 1. O tamanho padrão DEVE ser 20 e o máximo 100. Valores fora desses limites DEVEM ser recusados com erro de validação.
- **FR-004**: Uma página além da última DEVE devolver lista vazia com os totais corretos, sem erro.
- **FR-005**: Os filtros aplicados DEVEM incluir os valores padrão que a API aplicou sem pedido explícito.
- **FR-006**: A ordenação aplicada DEVE informar o campo e a direção. Toda listagem DEVE ter ordem estável: para um mesmo conjunto de dados, pedidos iguais devolvem a mesma ordem.
- **FR-007**: As contagens por valor de filtro e o resumo DEVEM ser opcionais e aparecer só quando pedidos. Quando pedidos, DEVEM ser calculados sobre todo o conjunto filtrado, independentemente da paginação.
- **FR-008**: O envelope NÃO DEVE conter bloco de metadados de execução nesta entrega.

**Referências resumidas (padrão para toda a API)**

- **FR-009**: Entidades relacionadas exibidas em respostas DEVEM ser representadas por referências resumidas: objetos pequenos com formato fixo por tipo de entidade.
- **FR-010**: Uma referência PODE conter outra referência, mas NÃO DEVE conter listas nem a entidade completa.
- **FR-011**: Todo campo de uma referência DEVE ter descrição na documentação da API.
- **FR-012**: Campos de auditoria (quem criou, alterou, excluiu) DEVEM continuar como identificadores.

**Lista de tarefas**

- **FR-013**: A lista de tarefas DEVE adotar o envelope padrão (FR-001 a FR-007).
- **FR-014**: Cada tarefa DEVE trazer o processo como referência (identificador, código, título) e a etapa como referência (chave, ordem), no lugar dos campos achatados atuais.
- **FR-015**: Cada tarefa DEVE informar se o usuário pode agir nela. O usuário pode agir quando algum cargo que ocupa no processo (por designação ativa ou, para Admin e BraCVAM, pelo perfil global) tem concessão de editar a atividade, e ele não tem conflito de interesse vigente no processo.
- **FR-016**: A lista DEVE aceitar o filtro "só onde posso agir", com o mesmo critério do FR-015.
- **FR-017**: A lista DEVE considerar só a rodada vigente de cada atividade por padrão. Um filtro explícito DEVE permitir incluir as rodadas anteriores.
- **FR-018**: A lista DEVE aceitar filtro por ordem da etapa, por atividade (um ou vários valores) e por status (um ou vários valores).
- **FR-019**: O filtro de status DEVE aceitar só os status existentes da tarefa (aberta, concluída, cancelada). Valor desconhecido DEVE ser recusado com erro de validação.
- **FR-020**: A lista DEVE aceitar o filtro de atrasadas: tarefas abertas com prazo anterior ao momento do pedido.
- **FR-021**: A lista DEVE manter os filtros por processo e por cargo da tarefa que já existem.
- **FR-022**: A ordenação padrão DEVE ser por prazo crescente, com tarefas sem prazo por último. O usuário DEVE poder ordenar também por data de criação, em qualquer direção. O desempate DEVE ser determinístico.
- **FR-023**: As contagens por valor de filtro DEVEM cobrir atividade e status.
- **FR-024**: O resumo DEVE informar quantos processos estão em pré-avaliação por IA no momento, contando só processos em que o usuário vê a atividade de submissão e respeitando o filtro por processo.
- **FR-025**: A lista, as contagens e o resumo DEVEM respeitar as mesmas regras de visibilidade de processo e de atividade que a lista já aplica hoje. Nenhuma tarefa, contagem ou resumo pode revelar processos ou atividades que o usuário não vê.
- **FR-026**: A consulta de uma tarefa individual NÃO muda nesta spec.

### Key Entities

- **Envelope de listagem**: resposta padrão de qualquer listagem. Reúne itens, paginação, filtros aplicados, ordenação e, sob demanda, contagens e resumo.
- **Paginação**: página atual, tamanho da página, total de itens, total de páginas, existência de página seguinte e anterior.
- **Filtros aplicados**: os filtros efetivamente usados, incluindo os padrões.
- **Ordenação**: campo e direção aplicados.
- **Contagens por valor de filtro**: para cada dimensão pedida, quantos itens do conjunto filtrado têm cada valor.
- **Resumo**: agregados que não são contagens dos próprios itens, como processos em pré-avaliação por IA.
- **Referência de processo**: identificador, código e título.
- **Referência de etapa**: chave e ordem.
- **Tarefa (item da lista)**: identificador, processo, atividade, rodada, etapa, título, cargo, status, prazo e indicação de que o usuário pode agir.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O BraCVAM monta o quadro da etapa 1, com as tarefas vigentes e as contagens de cada coluna, incluindo processos em avaliação pela IA, com uma única chamada.
- **SC-002**: Com o filtro "só onde posso agir", 100% das tarefas devolvidas são ações que o usuário consegue executar, sem recusa por falta de permissão ou por conflito de interesse.
- **SC-003**: Nenhuma resposta da lista de tarefas traz mais de 100 itens.
- **SC-004**: Pedidos repetidos com os mesmos parâmetros e os mesmos dados devolvem os itens na mesma ordem em 100% das vezes.
- **SC-005**: As contagens por atividade batem com o total de itens obtido percorrendo todas as páginas com o mesmo filtro.
- **SC-006**: Nenhuma tarefa, contagem ou resumo revela processo ou atividade fora da visibilidade do usuário, verificado para cada perfil (proponente, cargos da Fase 2, laboratório, Admin, BraCVAM).
- **SC-007**: O frontend consegue ler a lista de tarefas com o mesmo componente de listagem que vai usar nas demais listagens depois da Spec 033.

## Assumptions

- A concessão de editar a atividade é o critério de "pode agir", já usado pelo backend para aceitar ou recusar as ações. O conflito de interesse vigente também retira a possibilidade de agir, porque a triagem e as amostras já recusam o usuário nesse caso.
- A pré-avaliação por IA não vira atividade. Ela entra no resumo porque não é tarefa. Transformá-la em atividade do template fica fora do escopo.
- O resumo informa só o número de processos em pré-avaliação por IA. Outros agregados entram depois, sem quebrar o envelope.
- As contagens são calculadas sobre o conjunto com todos os filtros aplicados, inclusive o da própria dimensão.
- O tamanho padrão (20) e o máximo (100) de página seguem o que a listagem de processos já usa.
- Não há ordenação por campos fora de prazo e data de criação nesta entrega.
- O formato das respostas de erro continua o atual. A Spec 034 o padroniza.
- As demais listagens mantêm o formato atual até a Spec 033.
- A mudança quebra o contrato atual da lista de tarefas: o formato da resposta muda para o envelope, os campos do processo e da etapa passam a referências, e o padrão passa a ser só a rodada vigente. Isso vai para o changelog único do frontend junto com as Specs 033 e 034.
- O frontend usa um deploy direto da `develop`. Quebrar a `develop` por um período é aceito: cada spec entra por PR próprio na `develop` (histórico preservado, sem PRs empilhados), e o changelog único é enviado ao frontend quando as três specs estiverem integradas.
