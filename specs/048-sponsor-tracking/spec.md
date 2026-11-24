# Feature Specification: Acompanhamento do Patrocinador

**Feature Branch**: `feat/047-sponsor-tracking`

**Created**: 2026-11-23

**Status**: Draft

**Input**: Pedido do usuário: o Patrocinador acompanha os processos em que tem o cargo `sponsor`. A API deve permitir (1) listar esses processos e (2) consultar, para cada um, código, título, estado do ciclo de vida, início, data da designação como patrocinador, quem ocupa os cargos do processo (inclusive o proponente), a fase atual e a lista das atividades em andamento (nome e desde quando). Vale do início ao fim do processo, inclusive na Fase 3 (execução da validação). Não pode expor dados internos do estudo: amostras, nomes químicos, CAS, SDS, códigos cegos, conteúdo de formulários e resultados. Decisões da equipe em `docs/observacoes-e-pendencias.md`, seção "Acompanhamento do patrocinador".

## Contexto

**CONFIRMADO** (mensagem do desenvolvedor do front, 2026-11-21, e print do deploy de dev): o Patrocinador tem o item de menu "Acompanhamento". Ele lista os processos em que a pessoa é patrocinadora. O detalhe mostra código, título, estado, proponente, "patrocinador desde", início do projeto, fase atual e atividade atual. No deploy, proponente aparece como "Não atribuído" e fase e atividade como "Ainda não disponível".

**CONFIRMADO** (código em `develop`, commit `9a60855`): `GET /processes` e `GET /processes/{id}` mostram ao Patrocinador os processos em que ele tem designação ativa, em qualquer cargo. O detalhe traz código, título, ciclo de vida (`OPEN`, `CLOSED`, `CANCELLED`, `ARCHIVED`), template e início. Ele não traz proponente, fase nem atividades. `GET /processes` não filtra por cargo: o filtro `mine` cobre só o proponente.

**CONFIRMADO**: `GET /processes/{id}/participants` mostra a quem não gere participantes só a própria designação. Por isso o front não acha o proponente.

**CONFIRMADO**: o processo não guarda a etapa. Fases e atividades têm status próprio, e várias atividades podem estar abertas ao mesmo tempo, como as designações da Fase 2 e o recebimento de amostras de cada laboratório na Fase 3. Nenhuma rota entrega essa posição a quem não executa a atividade.

**CONFIRMADO**: o BraCVAM designa o Patrocinador na Fase 2 (`assign_sponsor`), depois da triagem aprovada. O Patrocinador não tem atividade própria no template e não tem acesso às atividades.

**INFERÊNCIA**: o Plano de Trabalho não cita o Patrocinador. A feature se apoia na descrição das "páginas de monitoramento destinadas [...] às demais partes interessadas" (objeto do Plano de Trabalho) e na decisão da equipe registrada em `docs/observacoes-e-pendencias.md`.

## Clarifications

### Session 2026-11-23

- Q: O Patrocinador pode ver quem é o proponente e quem ocupa os outros cargos? → A: Sim. As pessoas envolvidas se conhecem. O sigilo fica nos dados internos do estudo: amostras, nomes químicos, CAS, SDS, códigos cegos, conteúdo de formulários e resultados. Decisão da equipe, confirmada pelo usuário.
- Q: Até quando o acompanhamento vale? → A: Do início ao fim do processo, inclusive na Fase 3, com o mesmo limite de sigilo.
- Q: Como a API entrega "fase atual" e "atividade atual", se várias atividades podem estar abertas? → A: A fase atual e a lista das atividades em andamento. O front decide como exibir.
- Q: Que informações o cartão da lista traz? → A: Além de código, título, estado, datas e "patrocinador desde", a fase atual e a quantidade de atividades em andamento. A lista não exige uma chamada de detalhe por processo. Decisão da equipe de backend, a partir do pedido do front de "informações úteis no cartão" (2026-11-23).
- Q: O acompanhamento muda o que o Patrocinador pode acessar? → A: Não. A tela é só informativa: não bloqueia nem libera ação, e as rotas de dados internos do estudo continuam recusando o Patrocinador. Decisão da equipe de backend (2026-11-23).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver os processos que patrocino (Priority: P1)

A pessoa designada como Patrocinadora abre o "Acompanhamento" e vê a lista dos processos em que tem esse cargo. Cada cartão mostra código, título, estado, a data em que foi designada, a fase atual e quantas atividades estão em andamento.

**Why this priority**: é a porta de entrada da tela. Sem a lista, o Patrocinador não chega ao detalhe.

**Independent Test**: designar um usuário como Patrocinador em dois processos e como outro cargo em um terceiro, e conferir que a lista dele traz só os dois primeiros, cada um com fase atual e quantidade de atividades em andamento.

**Acceptance Scenarios**:

1. **Given** um usuário designado como Patrocinador em dois processos, **When** ele consulta a lista do acompanhamento, **Then** recebe os dois processos, cada um com código, título, estado, início, data da designação, fase atual e quantidade de atividades em andamento.
2. **Given** um usuário que é Patrocinador em um processo e Colaborador em outro, **When** ele consulta a lista, **Then** recebe só o processo em que é Patrocinador.
3. **Given** um Patrocinador cuja designação foi revogada, **When** ele consulta a lista, **Then** o processo não aparece.
4. **Given** um usuário sem designação de Patrocinador, **When** ele consulta a lista, **Then** recebe a lista vazia.

---

### User Story 2 - Acompanhar o andamento de um processo (Priority: P1)

O Patrocinador abre um processo da lista e vê quem ocupa cada cargo, inclusive o proponente, a fase atual e as atividades em andamento, com o nome de cada uma e desde quando está aberta. O quadro acompanha o processo até o encerramento, inclusive na Fase 3.

**Why this priority**: é o conteúdo da tela pedida. Hoje os campos de proponente, fase e atividade aparecem vazios no deploy.

**Independent Test**: levar um processo da Fase 2 à Fase 3 e consultar o detalhe como Patrocinador em cada ponto, conferindo cargos, fase e atividades.

**Acceptance Scenarios**:

1. **Given** um processo na Fase 2 com proponente, Patrocinador e Grupo Gestor designados, **When** o Patrocinador consulta o detalhe, **Then** recebe as pessoas em cada cargo, inclusive o proponente, sem e-mail.
2. **Given** o mesmo processo com várias designações da Fase 2 abertas, **When** o Patrocinador consulta o detalhe, **Then** recebe a Fase 2 como fase atual e cada atividade em andamento com nome e data de abertura.
3. **Given** um processo na Fase 3 com o recebimento de amostras aberto em dois laboratórios, **When** o Patrocinador consulta o detalhe, **Then** recebe a Fase 3 como fase atual e uma atividade em andamento por laboratório, identificada pelo nome do laboratório.
4. **Given** um processo encerrado ou arquivado, **When** o Patrocinador consulta o detalhe, **Then** recebe o estado do processo, a data de encerramento, fase atual vazia e nenhuma atividade em andamento.
5. **Given** um processo aberto em que todos os laboratórios confirmaram o recebimento sem problema, sem atividade em andamento, **When** o Patrocinador consulta o detalhe, **Then** recebe o estado `OPEN`, fase atual vazia e nenhuma atividade em andamento.
6. **Given** um processo em que o usuário não é Patrocinador, ainda que tenha outro cargo, **When** ele consulta o detalhe, **Then** recebe `404`, igual a um processo inexistente.

---

### User Story 3 - Acompanhar sem ver dados internos do estudo (Priority: P1)

O Patrocinador acompanha o processo e não vê amostras, nomes químicos, CAS, SDS, códigos cegos, conteúdo de formulários, plano estatístico nem resultados, em nenhuma fase.

**Why this priority**: um vazamento de identidade de substância invalida o ensaio cego (constituição, princípio III).

**Independent Test**: com amostras, códigos cegos e formulários preenchidos no processo, consultar a lista e o detalhe do acompanhamento e procurar esses valores na resposta; consultar as rotas de amostras, formulários e plano estatístico como Patrocinador.

**Acceptance Scenarios**:

1. **Given** um processo com amostras definidas e códigos cegos gerados, **When** o Patrocinador consulta o detalhe do acompanhamento, **Then** a resposta não contém nome químico, CAS, SDS, código cego nem quantidade de amostras.
2. **Given** o mesmo processo, **When** o Patrocinador chama as rotas de leitura de amostras, recebimento, homologação, retorno, formulários de atividade e plano estatístico, ou as ações sobre execuções de laboratório, **Then** recebe `403` ou `404`, como hoje, sem nenhum dado interno no corpo.
3. **Given** um processo com formulário de submissão enviado, **When** o Patrocinador consulta o detalhe do acompanhamento, **Then** a resposta não traz valores nem anexos do formulário.

---

### Edge Cases

- Um usuário Patrocinador e Proponente no mesmo processo vê o processo uma vez na lista do acompanhamento.
- Dois Patrocinadores no mesmo processo: cada um vê a própria data de designação, e os dois aparecem no cargo.
- Designação de Patrocinador ainda em convite pendente não conta: o processo não aparece até o aceite.
- Usuário designado que foi desativado não aparece entre as pessoas do cargo, como na listagem de participantes de hoje.
- Cargo sem ninguém designado aparece vazio, para o front mostrar "Não atribuído" só quando de fato não houver pessoa.
- Processo excluído logicamente some da lista e o detalhe responde `404`. Hoje só a exclusão leva o processo a `CANCELLED`, então o processo cancelado segue essa regra.
- Hoje o processo só fica encerrado na Fase 1, antes de existir Patrocinador. O arquivamento exige processo encerrado ou cancelado, e o cancelado já está excluído. A regra de processo encerrado ou arquivado (FR-006) vale para quando o encerramento depois da Fase 3 existir, e os testes montam esse estado direto no banco.
- Processo aberto sem nenhuma atividade em andamento, como depois do último recebimento confirmado no template 1, vem com fase atual vazia e quantidade zero na lista e no detalhe.
- Processo com atividade reaberta pela reprovação da homologação mostra a execução reaberta como em andamento, com a data da reabertura.
- Execução de laboratório dispensada (`WAIVED`) não aparece como em andamento.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir ao usuário listar os processos em que tem designação ativa e efetiva de Patrocinador, com código, título, estado do ciclo de vida, início, encerramento, a data da designação, a fase atual (FR-004) e a quantidade de atividades em andamento (FR-005), sem exigir uma consulta de detalhe por processo.
- **FR-002**: A lista do FR-001 DEVE excluir processos em que o usuário só tem outros cargos, designações revogadas, convites pendentes e processos excluídos, e DEVE seguir o envelope paginado e a ordenação padrão da API.
- **FR-003**: O sistema DEVE permitir ao Patrocinador consultar, para cada processo da lista, as pessoas designadas em cada cargo do processo, inclusive o proponente, com nome de usuário e nome completo, sem e-mail. Pessoas de cargos por laboratório DEVEM vir com o laboratório.
- **FR-004**: O sistema DEVE entregar ao Patrocinador a fase atual do processo (chave, nome e ordem), definida como a fase de maior ordem com atividade em andamento, pela mesma regra na lista e no detalhe. Sem atividade em andamento, a fase atual vem vazia.
- **FR-005**: O sistema DEVE entregar ao Patrocinador a lista das atividades em andamento, cada uma com chave, nome, fase e data de abertura da execução atual. Execuções por laboratório DEVEM vir uma por laboratório, com o nome do laboratório.
- **FR-006**: Em processo encerrado ou arquivado, a fase atual DEVE vir vazia, a lista de atividades em andamento vazia e a quantidade zero.
- **FR-007**: O acompanhamento NÃO DEVE expor amostras, nomes químicos, CAS, SDS, códigos cegos, contagens de amostras, valores ou anexos de formulários, plano estatístico, resultados, pareceres, decisões e justificativas.
- **FR-008**: O acompanhamento NÃO DEVE ampliar o acesso do Patrocinador às atividades: as rotas de leitura de formulário de atividade, amostras, recebimento, homologação e retorno DEVEM continuar recusando o Patrocinador com `403` ou `404`, como hoje, e as ações sobre execuções de laboratório (dispensa e reabertura) também.
- **FR-009**: Usuário sem designação de Patrocinador no processo DEVE receber `404` ao consultar o acompanhamento desse processo, salvo Administrador e BraCVAM, que já veem todos os processos.
- **FR-010**: Consultar o acompanhamento NÃO DEVE gravar evento na linha do tempo, por ser leitura.
- **FR-011**: O manual DEVE descrever o acompanhamento do Patrocinador e o que ele vê e não vê.

### Key Entities

- **Acompanhamento do processo**: visão de leitura de um processo para o Patrocinador. Junta cabeçalho do processo, data da designação, pessoas por cargo, fase atual e atividades em andamento. Não é entidade nova: deriva de processo, designações, fases e execuções.
- **Item da lista do acompanhamento**: resumo de um processo patrocinado para o cartão. Junta cabeçalho do processo, data da designação, fase atual e quantidade de atividades em andamento, pela mesma regra do detalhe.
- **Atividade em andamento**: execução atual aberta de uma atividade, com nome, fase, data de abertura e, quando houver, laboratório.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em um processo com proponente designado, a tela do Patrocinador mostra o nome do proponente em vez de "Não atribuído".
- **SC-002**: Em qualquer ponto entre a designação do Patrocinador e o encerramento do processo, a tela mostra a fase atual e as atividades em andamento sempre que houver alguma, e mostra que não há atividade em andamento quando não houver.
- **SC-003**: O front monta a página da lista com uma chamada, já com fase atual e quantidade de atividades de cada cartão, e o detalhe de um processo com uma chamada.
- **SC-004**: Nenhuma resposta do acompanhamento contém nome químico, CAS, SDS, código cego, valor de formulário ou resultado, verificado por teste com esses dados presentes no processo.
- **SC-005**: As rotas de dados internos do estudo respondem ao Patrocinador igual a antes da entrega, verificado por teste.

## Assumptions

- A data de designação mostrada é a da designação ativa mais antiga do usuário como Patrocinador no processo.
- O Patrocinador vê só designações ativas e efetivas. Histórico de designações, convites pendentes e revogações ficam fora.
- Prazos das atividades e o responsável por cada uma ficam fora desta entrega: o front pediu nome e desde quando.
- Administrador e BraCVAM já veem todos os processos e não precisam da tela do Patrocinador. A lista traz só os processos que a própria pessoa patrocina, então vem vazia para quem não é Patrocinador. O detalhe abre para os dois perfis em qualquer processo, com "patrocinador desde" vazio quando não forem Patrocinadores.
- A linha do tempo continua com as regras atuais. O acompanhamento não substitui a linha do tempo.
- Os outros cargos (Colaborador, Observador, Avaliador ad hoc) ficam fora. Um acompanhamento parecido para eles pede outra decisão da equipe.
