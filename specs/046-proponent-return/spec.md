# Feature Specification: Retorno ao Proponente

**Feature Branch**: `feat/046-proponent-return`

**Created**: 2026-11-06

**Status**: Draft

**Input**: Pedido do usuário: agrupar em uma entrega o fluxo de devolução ao proponente. (1) Issue #73: pareceres por campo acessíveis depois da escolha `REVISE`, com consulta histórica do retorno decidido. (2) RF011: e-mail ao proponente quando a submissão é devolvida, usando a base de notificações existente. (3) Testes de concorrência adiados, marcados como `TODO(spec-030)` em `return_review_service.py` e `pre_evaluation_service.py`. Evitar bloat, complexidade e abstrações desnecessárias, sem deixar débitos nem lacunas técnicas.

## Contexto

**CONFIRMADO** (código em `develop`, commit `de4a614`): os pareceres por campo (`FieldReview`) ficam ligados ao formulário da execução avaliada. A escolha `REVISE` abre uma nova execução da submissão e copia só os valores. `GET /processes/{id}/activities/proposal_submission/form` resolve a execução mais recente e passa a devolver `reviews: {}`.

**CONFIRMADO**: `GET /processes/{id}/submission-versions/{run_number}` devolve valores, anexos e a justificativa geral, sem os pareceres. `GET /processes/{id}/return-review` responde `404` depois da decisão.

**CONFIRMADO**: só a triagem grava pareceres por campo. A devolução pela IA (`AI_PRE_EVALUATION`) não os tem, e o proponente continua lendo o resultado em `GET /processes/{id}/pre-evaluation`.

**CONFIRMADO**: a devolução nasce em dois caminhos: a decisão `NEEDS_REVISION` da triagem e a pré-avaliação por IA negativa ou com falha. Os dois chamam `open_return_review`. O reprocessamento da IA cancela o retorno ainda não decidido com `cancel_open_return_review`.

**CONFIRMADO**: a devolução hoje vira tarefa, sem e-mail (`manual/explicacao/escopo.md`, RF011 parcial). A base de notificações já entrega e-mails de convite, recuperação de senha e recebimento de amostras, e o recebimento já trata o canal indisponível sem travar a operação.

**CONFIRMADO**: as respostas de formulário e de retorno não mostram ao proponente quem fez a triagem nem quem escreveu cada parecer. O autor fica guardado em `reviewed_by`. A exceção era `RETURN_REVIEW_OPENED` na linha do tempo, com o `user_id` do triador, corrigida nesta entrega (FR-006).

**CONFIRMADO**: `return_review_service.py:169` e `pre_evaluation_service.py:159` guardam os `TODO(spec-030)` dos testes de concorrência adiados (FR-040 e FR-031 da Spec 030).

**INFERÊNCIA**: o e-mail se apoia no RF011 (notificação assíncrona com retornos da IA e da validação) e no RF033 (devolutivas). O Plano de Trabalho não define texto nem gatilhos, e a fonte desses detalhes é a seção "Retorno ao proponente (Spec 046)" de `docs/observacoes-e-pendencias.md`.

**PONTO A VALIDAR**: `GET .../form` devolve `reviews` sem conferir se a triagem já decidiu, então o proponente lê pareceres ainda em edição durante a triagem. Este comportamento já existe, o triador usa o mesmo campo para ler o próprio rascunho, e ele fica fora desta entrega até a equipe decidir.

## Clarifications

### Session 2026-11-06

- Q: O proponente vê o autor do parecer? → A: Não. Ele vê rodada, data, status e comentário. O autor fica guardado para auditoria. Mantém o que a API já faz e segue a revisão por pares comum, em que o autor do trabalho não conhece o revisor. As fontes do projeto não tratam da triagem: o RF050 cobre a revisão ad hoc.
- Q: Como fica a consulta histórica do retorno decidido? → A: Por `GET /processes/{id}/submission-versions/{run_number}`, que ganha os pareceres. `GET /processes/{id}/return-review` continua só para retorno pendente e mantém o `404`.
- Q: Quais devoluções geram e-mail? → A: Todas: triagem, IA negativa e falha da IA. As três abrem uma tarefa com prazo para o proponente.
- Q: Um e-mail ainda não enviado continua valendo se o retorno for cancelado? → A: Não. O reprocessamento da IA e a exclusão do processo cancelam o envio pendente, porque a tarefa citada deixou de existir.
- Q: Quando o reprocessamento da IA é aceito? → A: Só para a execução mais recente, com status `failed` e com retorno da IA ainda aberto. Um retorno aberto pela triagem depois de uma contestação não conta, porque é decisão humana sobre a submissão. A leitura do código na fase de plano mostrou que `retry_run` não trava a execução e aceita `in_progress`, o que permite efeito duplicado. A regra acompanha o que o manual já descreve: reprocessar uma pré-avaliação que falhou. Nos demais casos a rota responde `409`.
- Q: A versão devolvida mostra pareceres que a triagem ainda edita depois de uma contestação da IA? → A: Não. Só entram pareceres de execução da triagem concluída, e a versão passa a mostrá-los quando a triagem decide. Uma consulta histórica não muda depois de publicada, e um filtro na leitura resolve, sem campo nem estado novo.
- Q: Quem responde pelo cancelamento do retorno no reprocessamento? → A: O administrador que pediu o reprocessamento, em um evento próprio na linha do tempo, com ou sem e-mail pendente. A nova execução mantém como criador quem criou a anterior, para não mudar a autoria dos eventos da IA.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Corrigir a proposta com os pareceres à mão (Priority: P1)

O proponente recebe uma submissão devolvida pela triagem e escolhe revisá-la. Ele edita a nova versão em várias sessões e continua lendo o que a triagem apontou em cada campo. Depois, ele e quem acompanha o processo consultam os pareceres de cada versão devolvida.

**Why this priority**: sem os pareceres, o proponente corrige no escuro depois de recarregar a página. O formulário tem 56 campos, e a issue #73 é o único bug aberto de prioridade alta.

**Independent Test**: devolver uma submissão com pareceres, escolher `REVISE`, abrir o formulário em uma nova sessão e consultar a versão devolvida.

**Acceptance Scenarios**:

1. **Given** uma submissão devolvida pela triagem com pareceres em dois campos, **When** o proponente escolhe `REVISE` e abre o formulário em uma nova sessão, **Then** ele recebe os pareceres da rodada anterior, com status, comentário e data, separados dos pareceres da rodada atual.
2. **Given** a mesma submissão, **When** o proponente consulta a versão devolvida, **Then** a resposta traz os pareceres daquela rodada junto dos valores e da justificativa geral.
3. **Given** uma submissão em correção, **When** o proponente salva o rascunho e reenvia, **Then** os pareceres da rodada anterior não mudam.
4. **Given** a rodada 2 devolvida com novos pareceres, **When** o proponente consulta as versões 1 e 2, **Then** cada uma mostra só os pareceres da própria rodada.
5. **Given** uma submissão devolvida pela IA, **When** o proponente escolhe `REVISE`, **Then** o formulário não traz pareceres da rodada anterior e o resultado da IA segue disponível na pré-avaliação.
6. **Given** um parecer devolvido ao proponente, **When** ele consulta o formulário ou a versão devolvida, **Then** a resposta não identifica quem avaliou.

---

### User Story 2 - Saber da devolução por e-mail (Priority: P2)

O proponente envia a submissão e fecha o sistema. Quando a triagem ou a pré-avaliação por IA devolve a submissão, ele recebe um e-mail avisando que há um retorno a responder e até quando.

**Why this priority**: o prazo do retorno corre desde a abertura, e hoje o proponente só descobre a devolução ao entrar na plataforma.

**Independent Test**: devolver uma submissão pela triagem e pela IA e conferir o e-mail entregue pelo canal falso.

**Acceptance Scenarios**:

1. **Given** uma submissão em triagem, **When** a triagem decide `NEEDS_REVISION`, **Then** o proponente recebe um e-mail com o código e o título do processo, a origem do retorno, o prazo e a orientação de acessar a plataforma.
2. **Given** uma submissão em pré-avaliação, **When** a IA devolve a submissão, por resultado negativo ou por falha, **Then** o proponente recebe o mesmo aviso, com a origem correspondente.
3. **Given** uma devolução, **When** o e-mail chega, **Then** ele não traz justificativa, pareceres nem o nome de quem avaliou.
4. **Given** um ambiente sem canal de e-mail configurado, **When** a submissão é devolvida, **Then** a devolução conclui e a tarefa abre, sem envio.
5. **Given** um e-mail ainda pendente, **When** o BraCVAM reprocessa a pré-avaliação e cancela o retorno, **Then** o envio é cancelado e fica registrado como cancelado.
6. **Given** um e-mail ainda pendente, **When** o processo é excluído, **Then** o envio é cancelado e o proponente não recebe o aviso.

---

### User Story 3 - Decisões simultâneas sobre o mesmo retorno (Priority: P3)

O proponente clica duas vezes, ou abre duas abas e escolhe caminhos diferentes. O BraCVAM reprocessa a IA enquanto o proponente contesta o resultado. O processo termina em um estado único e coerente.

**Why this priority**: as travas existem desde a Spec 030, mas nenhum teste com duas sessões reais as prova. Os dois `TODO(spec-030)` são a dívida técnica deste fluxo.

**Independent Test**: disparar as operações em conexões independentes contra o banco real e conferir vencedor e efeitos.

**Acceptance Scenarios**:

1. **Given** um retorno pendente, **When** duas escolhas chegam ao mesmo tempo, **Then** uma vence, a outra recebe conflito e o processo registra um único efeito.
2. **Given** uma execução da IA em andamento, **When** a gravação do resultado, o reprocessamento e a contestação disputam a mesma execução, **Then** só um deles produz efeito.

---

### Edge Cases

- O formulário da submissão mudou depois da rodada avaliada: o parecer continua aparecendo com a chave do campo avaliado, inclusive em campo removido da definição.
- A primeira rodada não tem rodada anterior: o formulário devolve o conjunto de pareceres anteriores vazio.
- A rodada anterior foi devolvida pela IA, e uma rodada mais antiga tinha pareceres da triagem: o formulário mostra só a rodada imediatamente anterior, e as mais antigas seguem nas versões devolvidas.
- Atividades que não são `proposal_submission`: o formulário devolve o conjunto de pareceres anteriores vazio.
- Nenhuma pessoa tem o cargo `proponent` ativo no processo: a devolução conclui sem envio.
- Duas pessoas têm o cargo `proponent` ativo: cada uma recebe o próprio e-mail.
- A conta do proponente foi desativada: ela não recebe o aviso.
- A IA devolve de novo depois de um reprocessamento: o novo retorno gera um novo e-mail.
- A triagem devolve depois de uma contestação da IA que falhou: o retorno aberto é da triagem, e o reprocessamento daquela execução responde `409`.
- O proponente desiste com um e-mail pendente: o envio segue, como nas demais decisões do retorno.
- A falha de entrega do e-mail não desfaz a devolução. O envio segue as tentativas da base de notificações.

## Requirements *(mandatory)*

### Functional Requirements

**Pareceres (issue #73)**

- **FR-001**: `GET /processes/{id}/activities/proposal_submission/form` MUST devolver o novo campo `previous_reviews`, com os pareceres por campo da execução imediatamente anterior. O campo `reviews` mantém o significado atual: pareceres do formulário da execução vigente.
- **FR-002**: `previous_reviews` MUST usar o mesmo formato de `reviews` e vir vazio quando não houver execução anterior, quando ela não tiver pareceres ou em outras atividades.
- **FR-003**: `GET /processes/{id}/submission-versions/{run_number}` MUST devolver o novo campo `reviews`, com os pareceres daquela execução já decididos pela triagem. A listagem de versões não muda.
- **FR-004**: Os pareceres MUST aparecer mesmo quando o campo avaliado tiver saído da definição do formulário depois da avaliação.
- **FR-005**: Os pareceres de uma execução anterior MUST permanecer sem alteração durante a correção e as avaliações seguintes.
- **FR-006**: As respostas ao proponente MUST NOT identificar quem avaliou. O autor continua guardado para auditoria.
- **FR-007**: As duas consultas MUST manter as regras de acesso atuais, com `404` para quem não vê a submissão.
- **FR-008**: `GET /processes/{id}/return-review` MUST manter o comportamento atual.

**E-mail de devolução (RF011)**

- **FR-009**: Toda abertura de retorno, pela triagem ou pela IA, MUST pedir um e-mail para cada pessoa com o cargo `proponent` ativo no processo e conta ativa, na mesma transação da devolução.
- **FR-010**: O e-mail MUST trazer código e título do processo, origem do retorno, prazo quando houver e a orientação de acessar a plataforma.
- **FR-011**: O e-mail MUST NOT trazer justificativa, pareceres, resultado da IA nem o nome de quem avaliou.
- **FR-012**: A devolução MUST concluir normalmente quando o canal de e-mail não estiver configurado.
- **FR-013**: O cancelamento de um retorno pelo reprocessamento da IA ou pela exclusão do processo MUST cancelar os envios pendentes daquele retorno.
- **FR-013a**: O cancelamento de um retorno pelo reprocessamento da IA MUST gravar o evento `RETURN_REVIEW_CANCELLED`, com o administrador como autor, mesmo sem envio pendente.
- **FR-014**: Cada envio MUST ficar ligado ao processo e ao retorno que o originou, com o mesmo rastro de auditoria dos demais envios.

**Concorrência (Spec 030)**

- **FR-015**: Um teste com duas sessões reais MUST provar que escolhas simultâneas sobre o mesmo retorno têm um único vencedor, que a outra recebe conflito e que o processo registra um único efeito (FR-040 da Spec 030).
- **FR-016**: Um teste com sessões reais MUST provar que a gravação do resultado, o reprocessamento e a contestação sobre a mesma execução de IA têm um único vencedor (FR-031 da Spec 030).
- **FR-016a**: `POST /admin/pre-evaluations/{run_id}/retry` MUST aceitar só a execução mais recente do processo, com status `failed` e retorno da IA ainda aberto, e responder `409` nos demais casos.
- **FR-017**: A entrega MUST remover os dois `TODO(spec-030)`. Se um teste revelar uma corrida real, a correção entra nesta entrega.

**Documentação**

- **FR-018**: A entrega MUST atualizar no manual os contratos das duas rotas, o guia de resposta ao retorno, a página de notificações, a página da pré-avaliação por IA, a referência de eventos e o estado do RF011 e do RF033 em `manual/explicacao/escopo.md`.

### Key Entities

- **Parecer por campo**: avaliação de um campo em uma execução da submissão, com status, comentário, data e autor. Já existe e não muda de estrutura.
- **Retorno ao proponente**: execução da atividade `submission_return_review`, com origem e prazo. Já existe e passa a identificar os envios ligados a ela.
- **Envio de notificação**: registro da base de notificações. Ganha um novo tipo, o aviso de devolução.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Depois de escolher revisar, o proponente lê 100% dos pareceres da rodada devolvida em uma sessão nova, sem depender de dados guardados no navegador.
- **SC-002**: Toda versão devolvida mostra os pareceres da própria rodada, e nenhum parecer muda depois de gravado na rodada avaliada.
- **SC-003**: Todo proponente ativo recebe um aviso por devolução, nas três origens, em ambiente com e-mail configurado.
- **SC-004**: Nenhuma devolução falha por causa do envio de e-mail.
- **SC-005**: Nenhum e-mail ou resposta ao proponente revela quem avaliou.
- **SC-006**: As corridas testadas terminam com um único vencedor, sem efeito duplicado, e não resta nenhum `TODO(spec-030)` no código.

## Assumptions

- O envio usa o e-mail da conta. Preferências e contatos adicionais ficam com a issue #66, que depois passa a governar este aviso.
- O aviso cobre só a abertura do retorno. Lembrete de prazo e aviso de aprovação ou rejeição ficam fora.
- A plataforma não tem configuração de URL do frontend, então o e-mail orienta acessar a pi\*VMA, sem link direto, como os avisos de recebimento de amostras.
- `previous_reviews` e `reviews` nas versões são campos novos e aditivos: o frontend atual segue funcionando sem usá-los.
- A entrega não cria tabela nem migração.
- A resposta da versão devolvida não ganha a origem do retorno, porque nenhum critério da issue a exige.
