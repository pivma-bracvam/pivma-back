# Feature Specification: Alerts na plataforma

**Feature Branch**: `feat/047-alerts`

**Created**: 2026-11-21

**Status**: Draft

**Input**: Pedido do usuário: centralizar em uma caixa de avisos dentro da plataforma, chamada de alerts, os acontecimentos que pedem a atenção de cada usuário, como uma tarefa nova que ele ainda não viu. O alert é separado do e-mail: tem texto curto e leva o usuário ao lugar certo no front. Fontes: RF011 e RF033 do Plano de Trabalho da Fase II.

## Contexto

**CONFIRMADO** (código em `develop`, commit `9a60855`): o módulo `pivma.notifications` (Spec 036) é uma fila de envio de e-mail. A tabela `notifications` guarda destinatário, conteúdo cifrado e situação da entrega (`pending`, `sent`, `failed`, `cancelled`), e apaga o conteúdo quando o envio termina. Ela não tem estado de leitura nem dono na plataforma.

**CONFIRMADO**: hoje cinco acontecimentos geram e-mail: convite, recuperação de senha, problema no recebimento de amostra, decisão sobre esse problema e devolução da submissão (`manual/explicacao/notificacoes.md`). Nenhum gera aviso dentro da plataforma.

**CONFIRMADO**: `GET /tasks` lista as tarefas que o usuário pode ver, e `can_act` indica onde ele pode agir: cargo ativo no processo ou cargo global em `edit_roles`, designação pelo laboratório da execução quando ela é por laboratório, e nenhum conflito de interesse vigente (`routers/tasks.py`, `_can_act_clause`). A lista não diz quais tarefas o usuário ainda não viu.

**CONFIRMADO**: as tarefas nascem em sete pontos: seis em `process_engine.py` e um em `sample_receipt_service.py`. A liberação de atividade dependente, a devolução ao proponente, a reabertura de atividade e a abertura da resolução de recebimento passam por eles.

**CONFIRMADO**: a linha do tempo (`AuditEvent`) já registra os acontecimentos que esta spec usa como gatilho: `TRIAGE_APPROVED`, `TRIAGE_REJECTED`, `AI_PRE_EVALUATION_COMPLETED`, `STRUCTURE_APPROVED`, `PROCESS_WITHDRAWN`, `PARTICIPANT_ASSIGNED`, `PARTICIPANT_REVOKED`, `PARTICIPANT_EFFECTIVENESS_LOST`, `PARTICIPANT_EFFECTIVENESS_RESTORED`, `LABORATORY_RUN_COMPLETED`, `LABORATORY_WAIVED` e `SAMPLE_NONCONFORMITY_RESOLVED`. A linha do tempo pertence ao processo, e não registra quem já viu cada evento.

**CONFIRMADO**: o proponente não vê quem fez a triagem nem que a IA falhou (Spec 046). O laboratório não vê nome químico, CAS nem SDS, e não vê nada de outro laboratório (Specs 031 e 037).

**INFERÊNCIA**: o RF033 pede avisos sobre "solicitações, pendências, prazos, devolutivas e mudanças de status", e o RF011 pede avisos dos retornos da IA e da validação. O Plano de Trabalho não define canal, texto nem gatilhos. As decisões desta spec vêm do pedido do usuário e estão em `docs/observacoes-e-pendencias.md`, seção "Alerts na plataforma (Spec 047)".

## Clarifications

### Session 2026-11-21

- Q: O alert é a mesma coisa que o e-mail? → A: Não. O e-mail avisa quem está fora da plataforma e acompanha a entrega. O alert avisa o usuário dentro da plataforma, guarda se ele já leu e tem texto curto. Um acontecimento pode gerar e-mail, alert, os dois ou nenhum.
- Q: Como o front sabe para onde levar o usuário? → A: O alert traz um destino estruturado, com o tipo do objeto e os identificadores (por exemplo, tarefa com processo e tarefa). O front traduz o destino em rota. O backend não guarda URL do front.
- Q: Quem monta o texto? → A: O front, a partir do tipo do alert e de parâmetros mínimos: identificadores e códigos que o destinatário já pode ver, como o código do processo e o nome da atividade.
- Q: O alert dá acesso ao destino? → A: Não. Ao abrir o destino, a rota de sempre confere a permissão. Se a designação foi revogada, a tarefa saiu do alcance do usuário ou o processo foi excluído, a leitura do destino responde `404`, como `GET /tasks/{id}` já faz. Tentar agir sem permissão responde `403`.
- Q: Qual o nome? → A: `alerts`, para não confundir com `notifications`, a fila de e-mail.
- Q: O que acontece com o alert de tarefa quando alguém conclui a tarefa? → A: Nada. O alert segue lido ou não lido como estava, e o destino mostra a tarefa concluída. É a opção mais simples, e o usuário que quiser limpar a caixa marca todos como lidos.
- Q: Quem fez a ação que abriu uma tarefa também recebe o alert dessa tarefa? → A: Não. Quem fez a ação nunca recebe alert, em nenhum tipo. O proponente que cria o processo não recebe o alert da própria submissão, e as colegas de quem fez a ação continuam recebendo.

### Session 2026-11-22

- Q: Todas as pessoas do BraCVAM recebem o alert de toda tarefa de triagem, de designação e de homologação? → A: Sim, pela regra de `can_act`. Decidido em 2026-11-22: a regra fica até alguém do BraCVAM usar a caixa com dados reais.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Saber que há uma tarefa nova para mim (Priority: P1)

Uma pessoa do BraCVAM entra na plataforma e vê o contador de alerts não lidos. A lista mostra que chegou uma submissão para triar, com o código do processo e o nome da atividade. Ela abre o alert, o front a leva à tarefa e o alert fica lido. O mesmo vale para o proponente quando a submissão volta para ajuste, para o Grupo de Seleção de Amostras quando um laboratório relata problema no recebimento e para o laboratório quando a sua execução abre.

**Why this priority**: é o pedido que originou a feature. Sem ele, o usuário precisa abrir `GET /tasks` e comparar com o que lembra ter visto.

**Independent Test**: enviar uma proposta, esperar a pré-avaliação positiva e conferir que cada pessoa do BraCVAM tem um alert não lido apontando para a tarefa de triagem, e que o proponente não tem alert de tarefa.

**Acceptance Scenarios**:

1. **Given** uma proposta aprovada pela pré-avaliação, **When** a tarefa de triagem abre, **Then** cada usuário que pode agir nela recebe um alert não lido do tipo tarefa aberta, com destino na tarefa e o código do processo e o nome da atividade nos parâmetros.
2. **Given** uma submissão devolvida pela triagem ou pela IA, **When** a tarefa de revisão do retorno abre, **Then** o proponente recebe um alert de tarefa aberta, e os parâmetros não trazem justificativa, pareceres, nome de quem avaliou nem indicação de falha da IA.
3. **Given** uma atividade por laboratório que abre execuções para os laboratórios A e B, **When** as tarefas abrem, **Then** os designados pelo laboratório A recebem só o alert da execução de A, e os de B só o de B.
4. **Given** um usuário com conflito de interesse vigente no processo, **When** abre uma tarefa que o cargo dele poderia executar, **Then** ele não recebe alert dessa tarefa.
5. **Given** uma pessoa do BraCVAM que conclui uma designação e libera a seguinte, **When** a nova tarefa abre, **Then** ela não recebe alert, e as outras pessoas do BraCVAM recebem.
6. **Given** uma tarefa com alert não lido, **When** outra pessoa conclui a tarefa, **Then** o alert segue na lista, lido ou não lido como estava, e o destino mostra a tarefa concluída.

---

### User Story 2 - Ler e limpar a caixa de alerts (Priority: P1)

O usuário abre a caixa, vê os alerts mais recentes primeiro, filtra os não lidos, marca um como lido ao abrir e, quando quer, marca todos como lidos.

**Why this priority**: sem leitura e marcação, a história 1 não entrega nada ao front.

**Independent Test**: gerar três alerts para um usuário, listar, marcar um como lido, marcar todos e conferir o contador em cada passo.

**Acceptance Scenarios**:

1. **Given** um usuário com três alerts, dois não lidos, **When** ele lista a caixa, **Then** recebe os três do mais recente para o mais antigo, no envelope paginado padrão, e o contador de não lidos é 2.
2. **Given** a mesma caixa, **When** ele filtra só os não lidos, **Then** recebe os dois.
3. **Given** um alert não lido, **When** ele marca esse alert como lido, **Then** o contador cai para 1 e o alert traz a data da leitura.
4. **Given** um alert já lido, **When** ele marca de novo como lido, **Then** a resposta é de sucesso e a data da leitura não muda.
5. **Given** alerts não lidos, **When** ele marca todos como lidos, **Then** o contador vai a 0 e a resposta diz quantos mudaram.
6. **Given** um alert de outro usuário, **When** ele tenta marcar esse alert como lido, **Then** recebe `404`, igual a um alert inexistente.
7. **Given** um usuário sem alerts, **When** ele lista a caixa, **Then** recebe a lista vazia e o contador 0.
8. **Given** uma chamada sem sessão, **When** alguém lista ou marca alerts, **Then** recebe `401`.

---

### User Story 3 - Acompanhar a decisão sobre a minha submissão (Priority: P2)

O proponente envia a proposta e fecha a plataforma. Quando volta, encontra alerts dizendo que a pré-avaliação aprovou e a submissão foi para a triagem, depois que a triagem aprovou ou rejeitou, e mais tarde que a estrutura do estudo foi homologada.

**Why this priority**: o RF011 pede o aviso dos retornos da IA e da validação. A devolução já chega pela história 1; esta cobre as decisões que não abrem tarefa para o proponente.

**Independent Test**: levar uma proposta até a homologação da estrutura e conferir os alerts do proponente em cada decisão.

**Acceptance Scenarios**:

1. **Given** uma proposta em pré-avaliação, **When** a IA aprova, **Then** cada proponente ativo no processo recebe um alert de mudança de situação da submissão, com a situação "em triagem" e destino no processo.
2. **Given** uma submissão em triagem, **When** a triagem aprova ou rejeita, **Then** o proponente recebe o alert com a situação correspondente, sem justificativa nem nome de quem decidiu.
3. **Given** uma estrutura do estudo em homologação, **When** o BraCVAM homologa, **Then** o proponente e cada participante com designação ativa e efetiva no processo recebem um alert de estrutura homologada.
4. **Given** um proponente com conta desativada, **When** a triagem decide, **Then** ele não recebe alert.

---

### User Story 4 - Saber das minhas designações (Priority: P2)

Uma pessoa é designada como estatística de um processo e recebe um alert com o código do processo e o cargo. Mais tarde, a validade do vínculo dela com o laboratório vence, a designação deixa de valer e ela recebe outro alert. Se for revogada, também recebe.

**Why this priority**: a designação muda o que a pessoa vê e faz no processo, e hoje ela só descobre pela lista de processos.

**Independent Test**: designar um usuário, revogar a designação e conferir os dois alerts dele.

**Acceptance Scenarios**:

1. **Given** um usuário sem cargo no processo, **When** alguém o designa diretamente, **Then** ele recebe um alert de designação com o código do processo e o cargo, e destino no processo.
2. **Given** um usuário que aceita um convite de designação, **When** a designação é criada, **Then** ele não recebe alert, porque ele mesmo fez a ação.
3. **Given** um usuário designado, **When** a designação é revogada, **Then** ele recebe um alert de revogação.
4. **Given** um usuário designado por laboratório, **When** a designação perde ou recupera a efetividade, **Then** ele recebe o alert correspondente.

---

### User Story 5 - Acompanhar a execução nos laboratórios (Priority: P3)

O Grupo Gestor e o Gerente do Estudo recebem um alert quando um laboratório conclui a execução. O laboratório recebe um alert quando o Grupo Gestor dispensa a sua execução e quando o Grupo de Seleção de Amostras decide sobre o problema que ele relatou no recebimento.

**Why this priority**: o fluxo de laboratório ainda está em construção, e parte dele já tem tarefa (história 1) ou e-mail.

**Independent Test**: concluir a execução do laboratório A, dispensar a do laboratório B e decidir um problema de recebimento de A, conferindo os alerts de cada parte.

**Acceptance Scenarios**:

1. **Given** execuções dos laboratórios A e B, **When** A conclui, **Then** cada pessoa com designação ativa e efetiva como Grupo Gestor ou Gerente do Estudo recebe um alert com o nome do laboratório e da atividade, e os designados por B não recebem nada.
2. **Given** a execução do laboratório B, **When** o Grupo Gestor a dispensa, **Then** os designados por B recebem um alert de dispensa, e os de A não.
3. **Given** um problema de recebimento relatado por A, **When** o Grupo decide, **Then** os designados por A recebem um alert com o código cego e a situação resultante, sem nome químico, CAS, SDS, justificativa nem código do frasco novo.

---

### User Story 6 - Saber da desistência do proponente (Priority: P3)

O proponente desiste do processo ao responder ao retorno. Cada pessoa do BraCVAM e cada participante com designação ativa no processo recebe um alert de desistência.

**Why this priority**: o processo fecha, e quem acompanha não tem outra forma de saber.

**Independent Test**: devolver uma submissão, desistir como proponente e conferir os alerts do BraCVAM.

**Acceptance Scenarios**:

1. **Given** uma submissão devolvida, **When** o proponente desiste, **Then** cada usuário com o perfil BraCVAM e cada participante com designação ativa no processo recebe um alert de desistência com destino no processo, e o proponente não recebe.

### Edge Cases

- A operação de negócio falha depois de gerar os alerts: nenhum alert fica gravado (FR-003).
- O mesmo usuário tem dois cargos que podem agir na tarefa: ele recebe um só alert por tarefa.
- O processo é excluído: os alerts continuam na lista, e o destino responde `404`.
- O alert aponta para uma tarefa que mudou de mãos ou para um processo de que o usuário saiu: a leitura do destino responde `404`, e o alert segue lido ou não lido como estava.
- Uma atividade reaberta cria uma nova execução e uma nova tarefa: cada usuário que pode agir recebe um novo alert, com o número da execução nos parâmetros.
- A pré-avaliação falha e a submissão volta ao proponente: o alert é o mesmo da devolução pela IA, sem indicar a falha.
- Um usuário pede uma página além da última: recebe a lista vazia, com o contador correto.
- Duas marcações de "todos como lidos" ao mesmo tempo: as duas terminam com sucesso e nenhum alert fica não lido.

## Requirements *(mandatory)*

### Functional Requirements

**Geração**

- **FR-001**: O sistema DEVE gerar um alert por destinatário para cada acontecimento do catálogo de tipos (FR-010).
- **FR-002**: Cada alert DEVE pertencer a um único usuário, ter um tipo, um destino, parâmetros, a data de criação e a data de leitura, vazia enquanto não lido.
- **FR-003**: O sistema DEVE gravar os alerts na mesma transação da operação de negócio que os gerou. Se a operação for desfeita, nenhum alert fica gravado.
- **FR-004**: O sistema NÃO DEVE gerar alert para conta desativada.
- **FR-005**: O sistema DEVE gerar no máximo um alert por usuário para o mesmo acontecimento, mesmo que ele tenha mais de um cargo que o qualifique.
- **FR-006**: O sistema NÃO DEVE gerar alert para quem fez a ação, em nenhum tipo. Quando a ação vem de um processo automático, como a pré-avaliação por IA, ninguém conta como autor.
- **FR-007**: A geração de alerts NÃO DEVE depender da configuração do e-mail e NÃO DEVE gerar nem cancelar envios de e-mail.

**Destino e parâmetros**

- **FR-008**: O destino DEVE ter o tipo do objeto e os identificadores necessários para o front montar a rota: `process` (processo), `task` (processo e tarefa) ou `sample_receipt` (processo e frasco). O sistema NÃO DEVE guardar URL do front.
- **FR-009**: Os parâmetros DEVEM conter só identificadores e textos que o destinatário pode ver no destino quando o alert nasce. Eles NÃO DEVEM conter nome químico, CAS, SDS, justificativa, pareceres, resultado detalhado da IA, indicação de falha da IA nem o nome de quem avaliou ou decidiu.

**Catálogo de tipos**

- **FR-010**: O sistema DEVE oferecer estes tipos, com estes destinatários:

| Tipo | Gatilho | Destinatários | Destino | Parâmetros |
|---|---|---|---|---|
| `task_opened` | Uma tarefa abre | Quem pode agir na tarefa, pela regra de `can_act` | `task` | código do processo, título do processo, chave e nome da atividade, número da execução, prazo, laboratório quando a execução for por laboratório |
| `submission_status_changed` | A IA aprova a proposta; a triagem aprova ou rejeita | Proponentes ativos no processo | `process` | código e título do processo, situação: `in_triage`, `approved` ou `rejected` |
| `structure_approved` | A estrutura do estudo é homologada | Proponentes e participantes com designação ativa e efetiva no processo | `process` | código e título do processo |
| `process_withdrawn` | O proponente desiste | Usuários com o perfil BraCVAM e participantes com designação ativa no processo, fora o proponente | `process` | código e título do processo |
| `assignment_created` | Alguém designa o usuário diretamente | O designado | `process` | código e título do processo, cargo, laboratório quando houver |
| `assignment_revoked` | A designação é revogada | O designado | `process` | código e título do processo, cargo, laboratório quando houver |
| `assignment_effectiveness_changed` | A designação perde ou recupera a efetividade | O designado | `process` | código e título do processo, cargo, laboratório, `effective` verdadeiro ou falso |
| `laboratory_run_completed` | Um laboratório conclui a execução | Designação ativa e efetiva como Grupo Gestor ou Gerente do Estudo | `process` | código e título do processo, nome da atividade, laboratório |
| `laboratory_run_waived` | O Grupo Gestor dispensa um laboratório em uma fase | Designados por aquele laboratório no processo | `process` | código e título do processo, nome da fase, laboratório |
| `sample_nonconformity_decided` | O Grupo de Seleção de Amostras decide um problema de recebimento | Designados pelo laboratório do frasco | `sample_receipt` | código e título do processo, laboratório, código cego, situação resultante |

- **FR-011**: A devolução da submissão, a chegada de submissão para triagem, o reenvio após ajuste, a abertura da homologação, a rejeição da estrutura que reabre atividades, o problema no recebimento e a reabertura de execução de laboratório DEVEM chegar pelo tipo `task_opened`, pela tarefa que cada um abre. O sistema NÃO DEVE gerar um segundo alert para o mesmo acontecimento.

**Leitura**

- **FR-012**: O usuário DEVE poder listar só os próprios alerts, do mais recente para o mais antigo, no envelope paginado padrão, com filtro opcional de não lidos.
- **FR-013**: A listagem DEVE trazer o total de alerts não lidos do usuário, independente do filtro e da página.
- **FR-014**: O usuário DEVE poder marcar um alert como lido. Marcar de novo um alert lido DEVE ter sucesso sem mudar a data da leitura.
- **FR-015**: O usuário DEVE poder marcar todos os seus alerts não lidos como lidos, e a resposta DEVE dizer quantos mudaram.
- **FR-016**: Um alert de outro usuário DEVE responder `404`, igual a um inexistente.
- **FR-017**: As rotas de alert DEVEM exigir sessão, e as de escrita DEVEM exigir origem confiável.
- **FR-018**: O alert NÃO DEVE dar acesso ao destino. A rota do destino confere a permissão como hoje: sem acesso, a leitura responde `404`.
- **FR-019**: Marcar como lido NÃO DEVE gravar evento na linha do tempo do processo, porque é estado pessoal do usuário, e NÃO DEVE mudar a tarefa nem o processo.
- **FR-020**: Concluir, cancelar ou reabrir uma tarefa NÃO DEVE mudar os alerts já gerados para ela.

### Key Entities

- **Alert**: aviso de um acontecimento para um usuário. Tem o dono, o tipo, o destino (tipo do objeto e identificadores), os parâmetros, o processo de origem, a data de criação, a data de leitura e os campos de auditoria do projeto. Não guarda texto pronto nem URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em uma jornada da submissão até a homologação, cada usuário que pode agir em uma tarefa recebe o alert dela, e nenhum outro usuário recebe.
- **SC-002**: Nenhum alert de laboratório traz dado de outro laboratório, e nenhum alert de laboratório ou de proponente traz nome químico, CAS, SDS, justificativa, pareceres ou o nome de quem avaliou.
- **SC-003**: O contador de não lidos bate com a lista de não lidos em todos os passos da história 2.
- **SC-004**: Uma operação de negócio desfeita não deixa nenhum alert gravado.
- **SC-005**: Com cem alerts, o usuário recebe a primeira página e o contador em uma única chamada.

## Assumptions

- O front consulta a lista ou o contador quando o usuário navega. Aviso em tempo real (push, websocket) fica fora desta entrega.
- Os alerts não expiram nesta entrega. A paginação dá conta do volume.
- Os alerts continuam na lista depois que o usuário perde o acesso ao processo. Eles trazem só o que ele já podia ver quando nasceram.
- Os destinatários são calculados quando o acontecimento ocorre. Quem ganha o cargo depois não recebe os alerts anteriores.
- O texto em português fica no front, a partir do tipo e dos parâmetros.

## Out of Scope

- Lembretes de prazo e de tarefa vencida, que exigem uma rotina agendada.
- Preferências do usuário por tipo de alert.
- E-mail para os novos tipos e qualquer mudança na fila de e-mail.
- Exclusão ou arquivamento de alerts pelo usuário.
- Alerts para o administrador sobre e-mails que falharam.
