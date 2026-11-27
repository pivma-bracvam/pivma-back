# Feature Specification: Andamento do processo por cargo

**Feature Branch**: `feat/047-sponsor-tracking`

**Created**: 2026-11-23

**Updated**: 2026-11-25 (redesenho para todos os cargos, revisão da PR #83)

**Status**: Draft

**Input**: Pedido do usuário: o Patrocinador acompanha os processos em que tem o cargo `sponsor`. A API deve permitir (1) listar esses processos e (2) consultar, para cada um, código, título, estado do ciclo de vida, início, data da designação como patrocinador, quem ocupa os cargos do processo (inclusive o proponente), a fase atual e a lista das atividades em andamento (nome e desde quando). Vale do início ao fim do processo, inclusive na Fase 3 (execução da validação). Não pode expor dados internos do estudo: amostras, nomes químicos, CAS, SDS, códigos cegos, conteúdo de formulários e resultados. Decisões da equipe em `docs/observacoes-e-pendencias.md`, seção "Andamento do processo". Em 2026-11-25, depois da revisão da PR #83, o usuário pediu o mesmo acompanhamento para todos os cargos relevantes, cada um com o recorte que as regras de sigilo permitem, sem uma rota por cargo.

## Contexto

**CONFIRMADO** (mensagem do desenvolvedor do front, 2026-11-21, e print do deploy de dev): o Patrocinador tem o item de menu "Acompanhamento". Ele lista os processos em que a pessoa é patrocinadora. O detalhe mostra código, título, estado, proponente, "patrocinador desde", início do projeto, fase atual e atividade atual. No deploy, proponente aparece como "Não atribuído" e fase e atividade como "Ainda não disponível".

**CONFIRMADO** (código em `develop`, commit `9a60855`): `GET /processes` e `GET /processes/{id}` mostram a quem tem designação ativa, em qualquer cargo, os processos dele. O detalhe traz código, título, ciclo de vida (`OPEN`, `CLOSED`, `CANCELLED`, `ARCHIVED`), template e início. Ele não traz proponente, fase nem atividades. `GET /processes` não filtra por cargo: o filtro `mine` cobre só o proponente.

**CONFIRMADO**: `GET /processes/{id}/participants` mostra a quem não gere participantes só a própria designação. Por isso o front não acha o proponente.

**CONFIRMADO**: o processo não guarda a etapa. Fases e atividades têm status próprio, e várias atividades podem estar abertas ao mesmo tempo, como as designações da Fase 2 e o recebimento de amostras de cada laboratório na Fase 3. `GET /tasks` mostra só as tarefas das atividades que o cargo pode abrir (`view_roles`), e o Patrocinador não abre nenhuma.

**CONFIRMADO** (revisão da PR #83, 2026-11-25): o coordenador da equipe apontou que o proponente e outros cargos precisam do mesmo acompanhamento, e que uma rota por cargo multiplicaria os endpoints. O Plano de Trabalho prevê páginas de monitoramento para a BraCVAM, os laboratórios, o estatístico, os especialistas "e às demais partes interessadas", e o RF030 pede as etapas concluídas, em andamento, pendentes e futuras do processo.

**CONFIRMADO**: as regras de sigilo em vigor são o isolamento por laboratório (constituição III, RF044; `laboratory_run_visibility_clause`), a revisão cega (RF050) e a autoria oculta da triagem para o proponente (Spec 046).

## Clarifications

### Session 2026-11-23

- Q: O Patrocinador pode ver quem é o proponente e quem ocupa os outros cargos? → A: Sim. As pessoas envolvidas se conhecem. O sigilo fica nos dados internos do estudo: amostras, nomes químicos, CAS, SDS, códigos cegos, conteúdo de formulários e resultados. Decisão da equipe, confirmada pelo usuário.
- Q: Até quando o acompanhamento vale? → A: Do início ao fim do processo, inclusive na Fase 3, com o mesmo limite de sigilo.
- Q: Como a API entrega "fase atual" e "atividade atual", se várias atividades podem estar abertas? → A: A fase atual e a lista das atividades em andamento. O front decide como exibir.
- Q: Que informações o cartão da lista traz? → A: Além de código, título, estado e datas, a data da designação, a fase atual e a quantidade de atividades em andamento. A lista não exige uma chamada de detalhe por processo. Decisão da equipe de backend, a partir do pedido do front de "informações úteis no cartão" (2026-11-23).
- Q: O acompanhamento muda o que o Patrocinador pode acessar? → A: Não. A tela é só informativa: não bloqueia nem libera ação, e as rotas de dados internos do estudo continuam recusando o Patrocinador. Decisão da equipe de backend (2026-11-23).

### Session 2026-11-25

- Q: Uma rota para o Patrocinador ou uma para todos? → A: Uma para todos. A lista fica em `GET /processes`, com o filtro `role` e os campos de andamento em cada item. O detalhe fica em `GET /processes/{id}/progress`, aberto a quem vê o processo. `/sponsor-tracking` sai. Pedido do coordenador na revisão da PR #83, confirmado pelo usuário.
- Q: Por que não ampliar `GET /tasks`? → A: `/tasks` é a caixa de trabalho. Mudar quem vê cada tarefa encheria a caixa do Patrocinador com tarefas que não são dele, e a tarefa não traz quem ocupa os cargos nem as fases sem tarefa. Decisão do usuário, depois da comparação das duas propostas.
- Q: O que cada cargo vê? → A: Admin, BraCVAM, Grupo Gestor, Gerente do Estudo e Patrocinador veem todas as pessoas e todas as execuções. Proponente, Estatístico, Colaborador, Grupo de Seleção e Observador regulatório veem a coordenação (Grupo Gestor, Gerente do Estudo, Patrocinador e proponente), o próprio cargo e as execuções de atividade única. O laboratório participante vê também a própria equipe e a própria execução. Avaliador ad hoc e revisor por pares não veem o proponente nem outro avaliador. Com mais de um cargo, vale a união. O usuário pediu em 2026-11-25 que o backend liberasse todos os cargos relevantes pelas práticas usuais de sigilo; os critérios vêm das regras em vigor (Contexto).
- Q: As fases entram no detalhe? → A: Sim, todas, com a situação, iguais para todos os cargos. Atende o RF030.
- Q: A lista por cargo mostra os arquivados? → A: Segue a regra de `GET /processes`: arquivado só com `status=ARCHIVED`, para quem tem acesso de revisão.

### Session 2026-11-27

- Q: O andamento mostra os próximos passos? → A: Sim. Cada fase lista as próprias atividades com a situação, e as que só abrem por evento (revisão do retorno, problema no recebimento) vêm marcadas como condicionais. As execuções abertas ficam dentro da atividade, e a lista plana de execuções sai. Pedido da revisão da PR #83 (2026-11-27), confirmado pelo usuário.
- Q: Como mostrar um cargo ocupado por alguém que o usuário não pode ver? → A: Cada cargo traz se está ocupado, sem contar pessoas. Pedido da mesma revisão.
- Q: A matriz de acesso central entra nesta spec? → A: Não. Fica para uma spec própria, registrada na issue #87. Decisão do usuário em 2026-11-27; motivos em [research.md](research.md#r12-o-que-fica-para-a-matriz-de-acesso).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver os processos em que tenho um cargo (Priority: P1)

A pessoa abre o acompanhamento e vê os processos em que tem um cargo, filtrados pelo cargo que escolher. Cada cartão mostra código, título, estado, as designações dela com a data, a fase atual e quantas atividades em andamento ela pode ver.

**Why this priority**: é a porta de entrada da tela. Sem a lista, ninguém chega ao detalhe.

**Independent Test**: designar um usuário como Patrocinador em dois processos e como outro cargo em um terceiro, e conferir que a lista com `role=sponsor` traz só os dois primeiros, cada um com fase atual e quantidade de atividades em andamento.

**Acceptance Scenarios**:

1. **Given** um usuário designado como Patrocinador em dois processos, **When** ele consulta a lista com `role=sponsor`, **Then** recebe os dois processos, cada um com o cabeçalho, as designações dele com a data, a fase atual e a quantidade de atividades em andamento.
2. **Given** um usuário que é Patrocinador em um processo e Colaborador em outro, **When** ele consulta a lista com `role=sponsor`, **Then** recebe só o processo em que é Patrocinador; sem o filtro, recebe os dois, cada um com o próprio cargo.
3. **Given** um Patrocinador cuja designação foi revogada, **When** ele consulta a lista com `role=sponsor`, **Then** o processo não aparece.
4. **Given** um usuário sem designação de Patrocinador, **When** ele consulta a lista com `role=sponsor`, **Then** recebe a lista vazia.

---

### User Story 2 - Acompanhar o andamento de um processo (Priority: P1)

O Patrocinador abre um processo da lista e vê as fases com a situação, quem ocupa cada cargo, inclusive o proponente, a fase atual e as atividades em andamento, com o nome de cada uma e desde quando está aberta. O quadro acompanha o processo até o encerramento, inclusive na Fase 3.

**Why this priority**: é o conteúdo da tela pedida. Hoje os campos de proponente, fase e atividade aparecem vazios no deploy.

**Independent Test**: levar um processo da Fase 2 à Fase 3 e consultar o andamento como Patrocinador em cada ponto, conferindo fases, cargos e atividades.

**Acceptance Scenarios**:

1. **Given** um processo na Fase 2 com proponente, Patrocinador e Grupo Gestor designados, **When** o Patrocinador consulta o andamento, **Then** recebe as pessoas em cada cargo, inclusive o proponente, sem e-mail.
2. **Given** o mesmo processo com várias designações da Fase 2 abertas, **When** o Patrocinador consulta o andamento, **Then** recebe a Fase 2 como fase atual, todas as fases com a situação e cada atividade em andamento com nome e data de abertura.
3. **Given** um processo na Fase 3 com o recebimento de amostras aberto em dois laboratórios, **When** o Patrocinador consulta o andamento, **Then** recebe a Fase 3 como fase atual e uma atividade em andamento por laboratório, identificada pelo nome do laboratório.
4. **Given** um processo encerrado ou arquivado, **When** o Patrocinador consulta o andamento, **Then** recebe fase atual vazia e nenhuma atividade em andamento.
5. **Given** um processo aberto em que todos os laboratórios confirmaram o recebimento sem problema, sem atividade em andamento, **When** o Patrocinador consulta o andamento, **Then** recebe fase atual vazia e nenhuma atividade em andamento.
6. **Given** um usuário que não vê o processo, **When** ele consulta o andamento, **Then** recebe `404`, igual a um processo inexistente.

---

### User Story 3 - Acompanhar sem ver dados internos do estudo (Priority: P1)

Nenhum cargo vê pelo acompanhamento amostras, nomes químicos, CAS, SDS, códigos cegos, conteúdo de formulários, plano estatístico nem resultados, em nenhuma fase.

**Why this priority**: um vazamento de identidade de substância invalida o ensaio cego (constituição, princípio III).

**Independent Test**: com amostras, códigos cegos e formulários preenchidos no processo, consultar a lista e o andamento com cada cargo e procurar esses valores na resposta; consultar as rotas de amostras, formulários e plano estatístico como Patrocinador.

**Acceptance Scenarios**:

1. **Given** um processo com amostras definidas e códigos cegos gerados, **When** qualquer cargo consulta o andamento, **Then** a resposta não contém nome químico, CAS, SDS, código cego nem quantidade de amostras.
2. **Given** o mesmo processo, **When** o Patrocinador chama as rotas de leitura de amostras, recebimento, homologação, formulários de atividade e plano estatístico, ou as ações sobre execuções de laboratório, **Then** recebe `403` ou `404`, como hoje, sem nenhum dado interno no corpo.
3. **Given** um processo com formulário de submissão enviado, **When** o Patrocinador consulta o andamento, **Then** a resposta não traz valores nem anexos do formulário.

---

### User Story 4 - Cada cargo acompanha com o próprio recorte (Priority: P1)

O proponente, os laboratórios, os cargos de apoio e os avaliadores abrem o mesmo andamento. Todos veem a mesma fase. Cada um vê só as pessoas e as execuções que as regras de sigilo liberam.

**Why this priority**: sem o recorte, abrir o andamento a todos quebraria o isolamento por laboratório e a revisão cega.

**Independent Test**: num processo na Fase 3 com dois laboratórios, consultar o andamento como proponente, como cada laboratório e como avaliador, e conferir as pessoas e as execuções de cada um.

**Acceptance Scenarios**:

1. **Given** um processo na Fase 3, **When** o proponente consulta o andamento, **Then** vê a mesma fase do Patrocinador, o Grupo Gestor, o Gerente do Estudo e o Patrocinador, e nenhum avaliador, laboratório ou execução de laboratório.
2. **Given** o mesmo processo, **When** um laboratório participante consulta o andamento, **Then** vê a própria equipe e o próprio recebimento, e nada do outro laboratório.
3. **Given** o mesmo processo, **When** um avaliador ad hoc ou revisor por pares consulta o andamento, **Then** não vê o proponente nem outro avaliador.
4. **Given** o mesmo processo, **When** o Grupo Gestor ou o Gerente do Estudo consulta o andamento, **Then** vê todos os cargos e todas as execuções.
5. **Given** um usuário com dois cargos no processo, **When** ele consulta o andamento, **Then** vê a união do que cada cargo libera.
6. **Given** um laboratório participante, **When** ele consulta a lista, **Then** a quantidade de atividades do cartão é igual à do andamento que ele vê.

---

### Edge Cases

- Um usuário com dois cargos no mesmo processo vê o processo uma vez na lista, com as duas designações em `my_roles`.
- Dois Patrocinadores no mesmo processo: cada um vê a própria data de designação, e os dois aparecem no cargo.
- Designação ainda em convite pendente não conta: o processo não aparece no filtro até o aceite.
- Usuário designado que foi desativado não aparece entre as pessoas do cargo, como na listagem de participantes de hoje.
- Cargo visível sem ninguém designado aparece vazio, para o front mostrar "Não atribuído" só quando de fato não houver pessoa.
- Cargo de laboratório sem vínculo ativo com o laboratório não é efetivo: não abre o processo nem aparece entre as pessoas.
- Processo excluído logicamente some da lista e o andamento responde `404`. Hoje só a exclusão leva o processo a `CANCELLED`, então o processo cancelado segue essa regra.
- Hoje o processo só fica encerrado na Fase 1. A regra de processo encerrado ou arquivado (FR-006) vale para quando o encerramento depois da Fase 3 existir, e os testes montam esse estado direto no banco.
- Processo aberto sem nenhuma atividade em andamento, como depois do último recebimento confirmado no template 1, vem com fase atual vazia e quantidade zero na lista e no andamento.
- Processo com atividade reaberta pela reprovação da homologação mostra a execução reaberta como em andamento, com a data da reabertura.
- Execução de laboratório dispensada (`WAIVED`) não aparece como em andamento.
- A fase atual conta todas as execuções, inclusive as que o usuário não vê: um laboratório vê a mesma fase do Patrocinador.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `GET /processes` DEVE trazer, em cada item, a fase atual (FR-004), a quantidade de execuções em andamento que o usuário vê (FR-005, FR-012) e as designações efetivas do usuário no processo, com cargo, laboratório e data, sem exigir uma consulta por processo.
- **FR-002**: `GET /processes` DEVE aceitar o filtro `role`, que deixa só os processos em que o usuário tem esse cargo efetivo. Designações revogadas, convites pendentes e processos excluídos não contam. A lista mantém o envelope, a ordenação e a regra de arquivados atuais.
- **FR-003**: O andamento DEVE trazer as pessoas designadas nos cargos que o usuário vê, com nome de usuário e nome completo, sem e-mail. Pessoas de cargos por laboratório DEVEM vir com o laboratório.
- **FR-004**: O sistema DEVE entregar a fase atual do processo (chave, nome e ordem), definida como a fase de maior ordem com atividade em andamento, pela mesma regra na lista e no andamento e igual para todos os cargos. Sem atividade em andamento, a fase atual vem vazia.
- **FR-005**: O andamento DEVE trazer as execuções em andamento que o usuário vê, dentro da atividade de cada uma, com a data de abertura. Execuções por laboratório DEVEM vir uma por laboratório, com o nome do laboratório.
- **FR-006**: Em processo encerrado ou arquivado, a fase atual DEVE vir vazia, nenhuma atividade DEVE trazer execução aberta e a quantidade DEVE ser zero.
- **FR-007**: O acompanhamento NÃO DEVE expor a nenhum cargo amostras, nomes químicos, CAS, SDS, códigos cegos, contagens de amostras, valores ou anexos de formulários, plano estatístico, resultados, pareceres, decisões e justificativas.
- **FR-008**: O acompanhamento NÃO DEVE ampliar o acesso às atividades: as rotas de leitura de formulário de atividade, amostras, recebimento e homologação DEVEM continuar recusando o Patrocinador com `403` ou `404`, como hoje, e as ações sobre execuções de laboratório (dispensa e reabertura) também.
- **FR-009**: Quem não vê o processo em `GET /processes/{id}` DEVE receber `404` ao consultar o andamento. Administrador e BraCVAM abrem qualquer processo.
- **FR-010**: Consultar a lista ou o andamento NÃO DEVE gravar evento na linha do tempo.
- **FR-011**: O manual DEVE descrever o andamento e o que cada cargo vê.
- **FR-012**: O sistema DEVE aplicar o recorte por cargo das Clarifications de 2026-11-25 numa regra só, usada pela lista e pelo andamento.
- **FR-013**: O andamento DEVE trazer todas as fases do processo, em ordem, com a situação (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED` ou `CANCELLED`), iguais para todos os cargos.
- **FR-014**: Cada fase do andamento DEVE listar as próprias atividades, na ordem do template, com a situação (`BLOCKED`, `IN_PROGRESS`, `COMPLETED` ou `CANCELLED`) e a marca de condicional, iguais para todos os cargos.
- **FR-015**: Cada cargo do andamento DEVE dizer se está ocupado, mesmo quando o usuário não vê quem o ocupa, sem contar pessoas.

### Key Entities

- **Andamento do processo**: visão de leitura de um processo. Junta as designações do usuário, as fases com a situação, a fase atual, as pessoas por cargo visível e as execuções em andamento visíveis. Não é entidade nova: deriva de processo, designações, fases e execuções.
- **Item da lista de processos**: cabeçalho do processo mais fase atual, quantidade de execuções visíveis em andamento e designações do usuário, pela mesma regra do andamento.
- **Recorte por cargo**: o que um usuário vê no andamento, calculado dos cargos efetivos dele no processo e do perfil de plataforma.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em um processo com proponente designado, a tela do Patrocinador mostra o nome do proponente em vez de "Não atribuído".
- **SC-002**: Em qualquer ponto entre a designação e o encerramento do processo, a tela mostra a fase atual e as atividades em andamento sempre que houver alguma, e mostra que não há atividade em andamento quando não houver.
- **SC-003**: O front monta a página da lista com uma chamada, já com fase atual e quantidade de atividades de cada cartão, e o andamento de um processo com uma chamada.
- **SC-004**: Nenhuma resposta do acompanhamento contém nome químico, CAS, SDS, código cego, valor de formulário ou resultado, para nenhum cargo, verificado por teste com esses dados presentes no processo.
- **SC-005**: As rotas de dados internos do estudo respondem ao Patrocinador igual a antes da entrega, verificado por teste.
- **SC-006**: Nenhum laboratório vê pessoa ou execução de outro laboratório, e nenhum avaliador vê o proponente, verificado por teste.

## Assumptions

- `my_roles` traz uma linha por designação efetiva do usuário, da mais antiga para a mais nova.
- O andamento mostra só designações ativas e efetivas. Histórico de designações, convites pendentes e revogações ficam fora.
- Prazos das atividades e o responsável por cada uma ficam fora desta entrega: o front pediu nome e desde quando.
- O Laboratório líder sem designação de participante não tem laboratório próprio para o isolamento, como em `/tasks`: vê a coordenação e a própria designação, e as execuções de atividade única.
- A linha do tempo e `GET /tasks` continuam com as regras atuais.
