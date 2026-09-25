# Feature Specification: Atribuição de Cargo por Convite com Link Compartilhável

**Feature Branch**: `028-role-assignment-invites`

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "Vamos implementar essa issue [pivma-bracvam/pivma-back#23], mas desenvolva o plano levando alguns pontos em consideração: (1) Sobre a titularidade única, revi essa ideia, não vamos implementar isso. (2) Sobre o convite por e-mail, vamos postergar; no lugar desenvolva um sistema que permita enviar um convite, ele vai gerar um link que pode ser compartilhado — ao acessar a plataforma você faz login ou cria uma conta e automaticamente ganha o cargo dentro daquele processo. Associa o convite SEMPRE a um e-mail. A implementação deve levar em consideração que teremos mais opções de compartilhamento no futuro (WhatsApp, e-mail, Telegram); desenvolva pensando nesse espaço. Sobre o que não foi implementado, criar três issues (uma para cada meio) anexadas à milestone da Etapa 2. (3) Escopo exato do convite: reenvio permitido por quem é responsável pela execução da atividade até que ela se encerre; a atividade se encerra quando o cargo é preenchido devidamente — no caso de convites, quando todos os enviados forem confirmados/aceitos; tempo de expiração de 1 hora, parametrizado por variável de ambiente. Sim, o novo `activity_type` entra no escopo, mesmo a issue original estando incompleta nesse ponto."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preencher um papel do processo com alguém que já tem conta (Priority: P1)

Uma pessoa responsável pela gestão de um processo abre o roteiro (Fase de Planejamento), vê que um papel obrigatório (ex.: Estatístico, Laboratório Líder) ainda está pendente como uma etapa própria do roteiro, escolhe um usuário já ativo no sistema e o designa para esse papel. A etapa correspondente do roteiro se fecha sozinha assim que a designação é criada.

**Why this priority**: é a base sobre a qual o convite por link (User Story 2) se apoia — sem uma etapa do roteiro que represente "este papel precisa ser preenchido" e feche sozinha quando preenchido, nenhuma das duas formas de preenchimento (direta ou por convite) tem onde produzir efeito visível. Reaproveita majoritariamente mecanismo já existente (designação/revogação, Spec 006).

**Independent Test**: Com um processo na fase de Planejamento e uma etapa de atribuição de cargo pendente para um papel específico, uma pessoa autorizada designa um usuário ativo para aquele papel; a etapa some das pendências abertas do roteiro sem nenhuma ação manual adicional de "concluir".

**Acceptance Scenarios**:

1. **Given** uma instância de processo na fase de Planejamento com uma etapa de atribuição de cargo pendente para o papel X, **When** uma pessoa autorizada especificamente para o papel X (ver "Papéis Contextuais e Autorização de Designação") designa um usuário ativo para esse papel nesse processo, **Then** a designação é criada pelo mesmo mecanismo já existente (Spec 006) e a etapa de atribuição de cargo correspondente é concluída automaticamente, sem exigir uma ação separada de "marcar como concluída".
2. **Given** uma etapa de atribuição de cargo já concluída, **When** a etapa seguinte do roteiro depender dela, **Then** a etapa seguinte é destravada pelo mesmo mecanismo genérico de avanço já usado pelas demais atividades do roteiro (Spec 017).
3. **Given** um papel que aceita mais de um titular ao mesmo tempo, **When** duas pessoas diferentes são designadas para o mesmo papel no mesmo processo, **Then** o sistema aceita as duas designações ativas simultâneas — não existe restrição de titular único por papel.
4. **Given** o Proponente efetivo de um processo, **When** ele designa alguém para `sponsor` ou `group_manager` nesse processo, **Then** o sistema aceita a designação mesmo sem o Proponente ter a permissão genérica de gestão de participantes — essa autorização é específica desses dois papéis.
5. **Given** o Proponente efetivo de um processo, **When** ele tenta designar alguém para qualquer papel fora de `sponsor`/`group_manager` (ex.: `statistician`, `lead_laboratory`), **Then** o sistema nega a ação, a menos que ele também tenha a autorização genérica ou de Grupo Gestor para esse papel.

---

### User Story 2 - Convidar por link alguém que ainda não tem conta (Priority: P1)

A mesma pessoa gestora, ao invés de escolher um usuário já cadastrado, informa o e-mail de quem deve ocupar o papel e o sistema gera um link de convite. Ela compartilha esse link por fora da plataforma (hoje, manualmente — copiar e colar). Quem recebe o link acessa a plataforma, faz login ou cria uma conta usando aquele mesmo e-mail e, ao concluir, recebe automaticamente o papel naquele processo, sem nenhuma etapa manual de designação.

**Why this priority**: é a parte realmente nova desta entrega (a issue original só teria pessoa já cadastrada); sem ela, papéis como Patrocinador ou especialistas ad hoc que ainda não têm conta no sistema não podem ser incorporados ao processo.

**Independent Test**: Gerar um convite para um e-mail sem conta associada, abrir o link como visitante anônimo, concluir cadastro com aquele e-mail e confirmar que a pessoa passa a aparecer como participante ativa do papel convidado, sem que ninguém tenha designado manualmente.

**Acceptance Scenarios**:

1. **Given** uma pessoa autorizada para o papel-alvo desejado (ver "Papéis Contextuais e Autorização de Designação"), **When** ela cria um convite informando um e-mail e um papel do processo, **Then** o sistema gera um link único de uso único, associado a esse e-mail, esse papel e esse processo.
2. **Given** um link de convite válido e não expirado, **When** uma pessoa sem conta o acessa e conclui o cadastro usando o mesmo e-mail do convite, **Then** o sistema autentica a nova conta e concede automaticamente o papel do convite naquele processo, pelo mesmo mecanismo de designação já existente.
3. **Given** um link de convite válido e não expirado, **When** uma pessoa que já tem conta com aquele e-mail o acessa e faz login, **Then** o sistema concede automaticamente o papel do convite naquele processo, sem exigir novo cadastro.
4. **Given** um link de convite, **When** a pessoa autentica com uma conta cujo e-mail é diferente do e-mail do convite, **Then** o sistema recusa a concessão do papel e não altera o convite.
5. **Given** um convite ainda pendente, **When** o prazo de expiração é atingido sem aceite, **Then** o link deixa de conceder o papel e informa que o convite expirou.

---

### User Story 3 - Reenviar ou revogar um convite pendente (Priority: P2)

Enquanto a etapa de atribuição de cargo correspondente ainda estiver aberta, a pessoa responsável por ela consegue reenviar (renovar o prazo de) um convite que ainda não foi aceito, ou revogá-lo caso não seja mais necessário — por exemplo, porque a pessoa convidada não respondeu a tempo ou porque o e-mail estava errado.

**Why this priority**: sem isso, um convite que expira em 1 hora (Apontamento 3) se torna inútil na primeira tentativa malsucedida, e a pessoa gestora não teria como corrigir um endereço errado sem recriar tudo manualmente.

**Independent Test**: Criar um convite, deixá-lo expirar (ou aguardar o prazo configurado), reenviá-lo e confirmar que o link renovado funciona; separadamente, revogar um convite pendente e confirmar que o link revogado não concede mais o papel.

**Acceptance Scenarios**:

1. **Given** um convite pendente ou expirado para uma etapa de atribuição de cargo ainda aberta, **When** a pessoa responsável pela etapa o reenvia, **Then** o sistema gera um novo link com novo prazo de expiração, invalida o link anterior e preserva o histórico do convite original.
2. **Given** um convite pendente, **When** a pessoa responsável pela etapa o revoga, **Then** o link revogado deixa de conceder o papel e o convite some da lista de pendências que bloqueiam o fechamento da etapa.
3. **Given** uma etapa de atribuição de cargo já concluída (papel preenchido), **When** alguém tenta reenviar ou revogar um convite associado a ela, **Then** o sistema rejeita a ação.
4. **Given** uma pessoa sem nenhuma autorização válida para o papel-alvo do convite — nem a genérica de gestão de participantes, nem a específica do FR-003 —, **When** ela tenta criar, reenviar ou revogar um convite, **Then** o sistema nega a ação.

### Edge Cases

- Duas pessoas diferentes tentam aceitar o mesmo link de convite ao mesmo tempo (ex.: link encaminhado por engano): apenas o primeiro aceite bem-sucedido concede o papel; o segundo encontra o convite já aceito.
- Um convite é enviado para um papel que já está preenchido por outra via (designação direta) enquanto o convite ainda está pendente: o convite continua podendo ser aceito normalmente (múltiplos titulares são permitidos, Apontamento 1); ao ser aceito, cria mais uma designação ativa.
- Uma etapa de atribuição de cargo tem mais de um convite pendente ao mesmo tempo (ex.: três convites para o mesmo papel de especialista ad hoc): a etapa continua aberta até que todos os convites emitidos para ela alcancem um estado final — aceito ou revogado; um convite simplesmente deixado expirar sem reenvio nem revogação mantém a etapa aberta indefinidamente até ação humana.
- O processo é excluído logicamente ou chega a um status imutável enquanto há convite pendente: o link deixa de conceder o papel, e criar, reenviar ou revogar convites nesse processo passa a ser rejeitado — mesma regra já aplicada à designação direta (Spec 006).
- Alguém aceita um convite para um papel de laboratório (líder ou participante) sem ter vínculo institucional vigente com o laboratório indicado: a concessão automática do papel falha pela mesma validação já aplicada à designação direta; o convite permanece pendente até uma solução (reenvio para outro e-mail, ou a pessoa regularizar o vínculo).
- A pessoa que criou o convite perde a permissão de gestão do processo antes do aceite: o convite continua válido até expirar; reenviar ou revogar passa a exigir outra pessoa que ainda tenha a autorização para aquele papel.
- Um processo ainda não tem ninguém ocupando `group_manager`: as etapas de atribuição de cargo dos papéis cujo executor é o Grupo Gestor (`sample_selection_group`, `lead_laboratory`, `participating_laboratory`, `statistician`) ficam sem ninguém com autorização específica para preenchê-las até que o Proponente (ou quem tenha autorização genérica) designe um Grupo Gestor primeiro; quem tem a autorização genérica de gestão de participantes (Spec 006) sempre pode agir independentemente dessa ordem.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A autorização para criar, reenviar ou revogar uma designação ou convite DEVE ser decidida pelo papel-alvo específico, não por uma única regra genérica de "gestão de participantes" — ver "Papéis Contextuais e Autorização de Designação".
- **FR-002**: Quem já tem a autorização genérica de gestão de participantes do processo (Spec 006: permissão global ou Grupo Gestor efetivo naquele processo) MANTÉM a capacidade de designar, convidar, reenviar e revogar para qualquer um dos papéis desta feature, além da autorização específica do FR-003.
- **FR-003**: O Proponente efetivo de um processo, mesmo sem a autorização genérica de gestão de participantes, DEVE poder criar, reenviar e revogar designação ou convite exclusivamente para os papéis `sponsor` e `group_manager` nesse processo; para qualquer outro papel, o Proponente sem a autorização genérica DEVE ser negado.
- **FR-004**: Todo convite DEVE estar sempre associado a um endereço de e-mail informado no momento da criação; não existe convite sem e-mail.
- **FR-005**: Todo convite DEVE gerar um link único, de uso único, intransferível por adivinhação, que concede o papel somente quando aceito nas condições desta especificação.
- **FR-006**: Nesta entrega, a distribuição do link é manual — o sistema não envia o convite automaticamente por nenhum canal (e-mail, WhatsApp, Telegram ou outro). A pessoa que cria o convite é responsável por compartilhar o link por fora da plataforma.
- **FR-007**: O convite DEVE registrar um canal de distribuição pretendido, com um único valor disponível nesta entrega ("link manual"); a modelagem DEVE permitir adicionar novos canais no futuro sem quebrar convites já existentes, para suportar os canais automatizados previstos (e-mail, WhatsApp, Telegram) como entregas futuras separadas.
- **FR-008**: Todo convite DEVE expirar automaticamente um período fixo após sua criação (ou após seu reenvio mais recente). O valor padrão é 1 hora e DEVE ser configurável por implantação através de configuração de ambiente, não fixado por convite individual nem codificado no sistema.
- **FR-009**: Um convite expirado NÃO DEVE conceder o papel a quem acessar o link; o acesso a um link expirado DEVE informar claramente que o prazo passou.
- **FR-010**: Aceitar um convite DEVE exigir autenticação — login em conta existente ou criação de conta nova — usando exatamente o e-mail do convite. Autenticação com e-mail diferente do convite NÃO DEVE conceder o papel nem alterar o estado do convite.
- **FR-011**: Ao ser aceito nas condições do FR-010, o sistema DEVE conceder automaticamente, sem etapa manual adicional, o papel do convite à pessoa autenticada, usando o mesmo mecanismo e as mesmas regras já existentes para designação direta (Spec 006): usuário ativo, vínculo laboratorial vigente quando o papel exigir laboratório, sem duplicar uma designação ativa idêntica.
- **FR-012**: O sistema DEVE permitir que quem tem autorização para o papel-alvo do convite (FR-001/FR-002/FR-003) reenvie um convite ainda não aceito, gerando um novo link com novo prazo de expiração e invalidando o link anterior, enquanto a etapa correspondente não tiver se encerrado.
- **FR-013**: O sistema DEVE permitir que quem tem autorização para o papel-alvo do convite (FR-001/FR-002/FR-003) revogue um convite ainda não aceito a qualquer momento antes do encerramento da etapa; um convite revogado NÃO DEVE mais conceder o papel.
- **FR-014**: O sistema DEVE preservar o histórico completo de cada convite (criação, reenvio, aceite, expiração, revogação) como trilha imutável, com autoria e momento de cada ação, no mesmo padrão de auditoria já usado para designações diretas (Spec 006/RF034).
- **FR-015**: O roteiro de um processo DEVE suportar um novo tipo de etapa dedicado a preencher um papel do processo ("atribuição de cargo"), declarável por papel na definição do template, ao lado dos tipos de etapa já existentes (formulário, decisão, tarefa externa, marcador — Spec 017).
- **FR-016**: Uma etapa de atribuição de cargo sem nenhum convite emitido DEVE se encerrar automaticamente assim que o papel correspondente tiver ao menos uma designação ativa no processo — por designação direta ou por aceite de convite — sem exigir uma ação manual separada de "concluir".
- **FR-017**: Uma etapa de atribuição de cargo que teve ao menos um convite emitido NÃO DEVE se encerrar enquanto existir, para essa etapa, algum convite ainda pendente (nem aceito, nem expirado, nem revogado); ela se encerra quando todo convite emitido para ela estiver aceito ou revogado e o papel tiver ao menos uma designação ativa.
- **FR-018**: O encerramento de uma etapa de atribuição de cargo DEVE destravar as etapas seguintes do roteiro que dependerem dela, pelo mesmo mecanismo genérico de avanço já usado pelas demais atividades (Spec 017).
- **FR-019**: O sistema NÃO DEVE impor titularidade única por papel: qualquer papel contextual pode ter mais de uma designação ativa simultânea no mesmo processo, seja por designação direta, seja por aceite de convite — o mesmo comportamento já definido pela Spec 006 permanece inalterado.
- **FR-020**: O sistema DEVE rejeitar a criação, o reenvio, a revogação e o aceite de convite para um processo logicamente excluído ou em status imutável, na mesma regra já aplicada à designação direta (Spec 006 FR-005/FR-008).

### Key Entities

- **Convite de Designação**: representa a intenção de preencher um papel de um processo por alguém identificado por e-mail, antes de ela necessariamente ter conta no sistema. Guarda o processo, o papel (e o laboratório, quando o papel exigir), o e-mail, o canal de distribuição pretendido, o momento de criação, o prazo de expiração vigente e seu estado (pendente, aceito, expirado ou revogado), além de quem criou e, quando aplicável, reenviou ou revogou. Um reenvio produz um novo prazo e um novo link preservando a identidade e o histórico do convite original, no mesmo espírito de ciclo rastreável já usado pela designação (Spec 006).
- **Etapa de Atribuição de Cargo**: novo tipo de etapa do roteiro do processo (ao lado de formulário, decisão, tarefa externa e marcador). Representa "este papel precisa estar preenchido" em vez de uma interação a preencher; seu encerramento é derivado do estado das designações e convites do papel correspondente, não de uma submissão.
- **Designação** *(já existente, Spec 006, reaproveitada sem alteração de regra)*: vínculo efetivo entre uma pessoa, um papel e um processo, criado tanto pela via direta quanto pelo aceite de um convite.

## Papéis Contextuais e Autorização de Designação

Esta feature cobre exatamente os 8 papéis abaixo — os mesmos 8 da Issue #23, agora com o
executor confirmado. "Executor" é quem pode criar, reenviar e revogar designação/convite
daquele papel especificamente (FR-001/FR-002/FR-003), além de quem já tem a autorização
genérica de gestão de participantes (Spec 006), que sempre pode agir sobre qualquer papel.

| # | Papel Contextual | Chave (`ParticipantRole`) | Executor específico | Papel já existe hoje? |
|---|---|---|---|---|
| 1 | Patrocinador | `sponsor` | Proponente efetivo do processo | Não — Issue #41 |
| 2 | Grupo Gestor | `group_manager` | Proponente efetivo do processo | Sim |
| 3 | Grupo de Seleção de Amostras | `sample_selection_group` | Grupo Gestor efetivo do processo | Não — Issue #41 |
| 4 | Laboratório Líder | `lead_laboratory` | Grupo Gestor efetivo do processo | Sim |
| 5 | Laboratórios Participantes | `participating_laboratory` | Grupo Gestor efetivo do processo | Sim |
| 6 | Estatístico | `statistician` | Grupo Gestor efetivo do processo | Sim |
| 7 | Colaboradores e Observadores | `collaborator` | BraCVAM (autorização global) | Não — Issue #41 (papel distinto de `regulatory_observer`, que cobre só observadores regulatórios ANVISA/MAPA) |
| 8 | Especialistas Temáticos (Comitê ADHOC) | `adhoc_evaluator` | BraCVAM (autorização global) | Sim |

Duas linhas (3 e 4–6) resolvem sozinhas pela autorização genérica de Grupo Gestor já
existente hoje (`is_effective_group_manager`, Spec 006) — nenhum mecanismo novo de
autorização é necessário para elas. As linhas 7–8 já resolvem pela permissão global de
plataforma que Admin/BraCVAM sempre têm (Spec 023) — também sem mecanismo novo. A única
autorização genuinamente nova desta feature é a das linhas 1–2: o Proponente, que hoje não
tem nenhuma autorização de gestão de participantes, passa a poder designar/convidar
especificamente para `sponsor` e `group_manager` no próprio processo (FR-003).

`sponsor`, `sample_selection_group` e `collaborator` não existem hoje no vocabulário
`ParticipantRole`/`ACTIVITY_CARGOS` — sua adição é escopo da Issue #41 (já atualizada para
incluir os quatro papéis novos, incluindo `collaborator`), pré-requisito desta feature para
esses três papéis especificamente. `study_manager` e `peer_reviewer` (já existentes no
vocabulário) não fazem parte dos 8 papéis desta feature.

## Sequência de Preenchimento (insumo decidido para o plano)

A ordem e as dependências entre as 8 etapas de atribuição de cargo já foram decididas pelo
usuário e ficam registradas aqui para o `/speckit-plan` usar diretamente no template, sem
precisar rederivar — a spec continua definindo só o mecanismo genérico (FR-015 a FR-018),
não este conteúdo declarativo.

| Ordem | Papel | Tarefa no roteiro | Dependência |
|---|---|---|---|
| 1 | `sponsor` | Definir o Patrocinador | Início da fase de Planejamento, sem pré-requisito |
| 2 | `group_manager` | Definir os integrantes do Grupo Gestor | Início da fase de Planejamento, sem pré-requisito |
| 3 | `sample_selection_group` | Definir o Grupo de Seleção de Amostras | Depende de `group_manager` (2) concluída |
| 4 | `lead_laboratory` | Definir o Laboratório Líder | Depende de `group_manager` (2) concluída |
| 5 | `participating_laboratory` | Definir os Laboratórios Participantes | Depende de `group_manager` (2) concluída |
| 6 | `statistician` | Definir o Estatístico | Depende de `group_manager` (2) concluída |
| 7 | `collaborator` | Definir Colaboradores e Observadores | Depende de `group_manager` (2) concluída |
| 8 | `adhoc_evaluator` | Definir Especialistas Temáticos (Comitê ADHOC) | Depende de `group_manager` (2) concluída |

As etapas 1 e 2 são atribuídas pelo Proponente e não dependem uma da outra — podem ser
preenchidas em qualquer ordem entre si, ambas liberadas desde o início da fase. As etapas 3
a 8 dependem apenas da conclusão da etapa 2 (`group_manager`), não umas das outras — podem
ser preenchidas em paralelo assim que o Grupo Gestor existir, coerente com FR-003 (o
Proponente só tem autorização específica para as etapas 1 e 2) e com o edge case já
registrado sobre a ordem "Grupo Gestor antes do resto".

Depois das 8 etapas concluídas, a fase de Planejamento continua com atividades fora do
escopo desta feature (cadastro de amostras, confecção de templates de coleta, Aprovação
Formal — Issues #24, #26, #27); a última etapa desta feature a concluir não precisa ser
necessariamente a 8ª em wall-clock, só a última cujas dependentes fora desta feature
esperam pelo conjunto das 8, não por uma ordem específica entre elas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos processos na fase de Planejamento, cada papel obrigatório aparece como uma pendência própria e individualmente rastreável no roteiro, sem depender de nenhuma consulta fora do roteiro para saber quais papéis ainda faltam.
- **SC-002**: Uma pessoa gestora consegue gerar um convite e compartilhar o link em menos de 1 minuto a partir da tela de participantes do processo.
- **SC-003**: Em 100% dos aceites concluídos com o e-mail correto do convite, o papel aparece concedido e a pendência correspondente do roteiro desaparece sem nenhuma ação manual adicional.
- **SC-004**: Em 100% das tentativas de aceite com e-mail diferente do convidado, o sistema recusa a concessão do papel.
- **SC-005**: 100% dos links de convite deixam de conceder o papel após o prazo de expiração configurado, sem exigir qualquer intervenção manual para "desativá-los".
- **SC-006**: Uma pessoa gestora consegue reenviar um convite pendente e renovar seu prazo em menos de 30 segundos, sem perder o histórico do convite original.
- **SC-007**: Em 100% das ações de convite (criação, reenvio, aceite, expiração, revogação) e de designação (direta ou por convite), uma pessoa autorizada localiza na trilha do processo a ação, o responsável, o alvo, o resultado e o momento — mesma garantia já existente para designação direta (RF034).
- **SC-008**: Todos os cenários aprovados da Spec 006 (designação, revogação, conflito de interesse) continuam válidos sem alteração de comportamento para quem usa apenas a via direta, sem convites.

## Out of Scope

- Envio automatizado do convite por qualquer canal (e-mail, WhatsApp, Telegram ou outro) — cada canal fica registrado como uma issue própria na Milestone "Etapa 2: Planejamento e Preparação", a serem implementadas separadamente sobre o mecanismo genérico de convite desta feature.
- Titularidade única por papel — decisão revista nesta rodada (Apontamento 1); não faz parte desta entrega.
- A redação literal do YAML do template (chaves de atividade, `order_index`, títulos de tarefa) fica para o plano de implementação — a ordem e as dependências já estão decididas (ver "Sequência de Preenchimento"), só a codificação declarativa é que é conteúdo de plano, não de spec.
- Qualquer mudança no fluxo de cadastro público em si (Spec 001) além do necessário para reconhecer um e-mail de convite pendente no momento da autenticação.
- Notificação assíncrona de que um convite está prestes a expirar, foi aceito ou foi revogado — permanece fora do escopo, como já registrado pela Spec 006 para eventos de designação em geral.

## Assumptions

- Revogar um convite pendente o retira do conjunto que a etapa de atribuição de cargo precisa ver resolvido para se encerrar (FR-017) — equivale a retirar o convite, não a uma tentativa fracassada que continue bloqueando indefinidamente.
- Um convite que expira sem reenvio nem revogação mantém a etapa correspondente aberta indefinidamente até ação humana (reenviar, revogar, ou preencher o papel por designação direta); não existe expiração automática da etapa em si.
- Os 8 papéis desta feature e seus executores específicos estão fechados (ver "Papéis Contextuais e Autorização de Designação"); a Issue #41 foi atualizada para cobrir os 4 papéis que ainda não existem no vocabulário (`sponsor`, `sample_selection_group`, `regulatory_observer`, `collaborator`) e é pré-requisito desta feature para esses papéis especificamente.
- A pessoa que cria, reenvia ou revoga um convite ou designação precisa ter, no momento da ação, a autorização válida para aquele papel específico — genérica (Spec 006) ou a autorização específica do FR-003 — no momento da ação; perder essa autorização depois de criar um convite não invalida o convite já emitido, mas impede novas ações de gestão sobre ele.
- "Grupo Gestor efetivo" e "Proponente efetivo", para efeito da matriz de autorização, seguem a mesma checagem já existente no código para `group_manager` (designação ativa daquele papel no processo) — nenhum conceito novo de "efetividade" é introduzido.
- O valor de expiração padrão (1 hora) é uma configuração de implantação (variável de ambiente), não um parâmetro por convite; convites de um mesmo ambiente compartilham o mesmo prazo padrão.
