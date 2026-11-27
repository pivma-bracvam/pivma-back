# Feature Specification: Visibilidade da triagem e cegamento na linha do tempo

**Feature Branch**: `fix/049-triage-timeline-visibility` (sobre `develop`, que recebeu a PR #83 em `9f06d31`)

**Created**: 2026-11-27

**Status**: Implemented

**Input**: User description: "Três correções de visibilidade levantadas na revisão de segurança de 2026-11-27. (1) Issue #81: o proponente ganha a visão, sem edição, da atividade `triage_evaluation` nos cinco templates, com migração dos processos existentes, sem saber quem avaliou; `FIELD_REVIEWED` sai da linha do tempo de quem não tem `triage.review`. (2) Pendência da Spec 046: `reviews` em `GET .../form` mostra só pareceres de triagem concluída para quem não tem `triage.review`. (3) Issue #84: os eventos de convite viram eventos de participante, e quem só tem cargos de revisão cega não recebe a identidade do proponente nem de outro avaliador em nenhum evento. Decisões em `docs/observacoes-e-pendencias.md`, seção 'Visibilidade da triagem e cegamento na linha do tempo (Spec 049)'."

## Contexto

**CONFIRMADO** (código em `feat/047-sponsor-tracking`, commit `abe9eed`): `triage_evaluation` tem `access.view: []` nos cinco templates de `src/pivma/templates_data/`. A concessão é copiada para `ActivityInstance.view_roles` na criação do processo. Os eventos `TRIAGE_APPROVED`, `TRIAGE_REJECTED`, `REVISION_REQUESTED` e `FIELD_REVIEWED` são gravados com a execução da triagem, e a linha do tempo os descarta para o proponente. As atividades que abrem depois da triagem também são só da BraCVAM, então o proponente não distingue "com a BraCVAM" de "triagem aprovada" (issue #81).

**CONFIRMADO**: a visão de `triage_evaluation` libera ao proponente a tarefa em `GET /tasks` e `GET /tasks/{id}` (status, prazo e rodada, sem responsável) e os eventos da execução da triagem. A triagem não tem formulário próprio, e as rotas `POST /processes/{id}/triage/*` exigem `triage.review`.

**CONFIRMADO**: os eventos de decisão guardam o triador como autor e a justificativa no contexto. `FIELD_REVIEWED` guarda o triador e a quantidade de campos revisados. Hoje a linha do tempo só esconde o autor de `RETURN_REVIEW_OPENED`, para quem não tem `triage.review` (Spec 046).

**CONFIRMADO**: `GET /processes/{id}/activities/{key}/form` devolve em `reviews` todos os pareceres do formulário da execução pedida, inclusive o rascunho do triador antes da decisão. `GET .../submission-versions/{run_number}` e `previous_reviews` já filtram pela triagem concluída (Spec 046).

**CONFIRMADO**: `INVITE_CREATED`, `INVITE_RESENT`, `INVITE_REVOKED` e `INVITE_ACCEPTED` não têm execução e não entram na regra dos eventos de designação. Qualquer participante os recebe com e-mail, cargo e designação do convidado (issue #84).

**CONFIRMADO**: `PROCESS_CREATED`, `PROCESS_WITHDRAWN`, `DIRECT_REVIEW_REQUESTED` e o `ACTIVITY_UNBLOCKED` gravado na abertura das execuções por laboratório não têm execução e chegam a qualquer participante com o autor, que pode ser o proponente.

**CONFIRMADO**: a BraCVAM já designa o avaliador ad hoc na Fase 2 (`assign_adhoc_evaluator`), e a designação dá acesso ao processo. No andamento (Spec 048), avaliador ad hoc e revisor por pares não veem o proponente nem outro avaliador; com mais de um cargo, vale a união.

**CONFIRMADO**: `LABORATORY_WAIVED` e os eventos de execução de laboratório já passam pelo isolamento por laboratório (Spec 036). `PROCESS_ARCHIVED` e `PROCESS_DELETED` têm como autor o administrador ou a BraCVAM, que não estão sob cegamento. Esses eventos ficam como estão.

**INFERÊNCIA**: a migração dos processos existentes é um acréscimo de `proponent` à concessão de visão das instâncias de `triage_evaluation`, sem tabela nem coluna nova.

## Clarifications

### Session 2026-11-27

- Q: O proponente vê a triagem? → A: Sim, só a visão. A edição continua só com a BraCVAM. Decisão da equipe na issue #81.
- Q: O proponente vê quem fez a triagem? → A: Não. Segue a decisão 1 da Spec 046: rodada, data, status e comentário, sem o autor, que fica gravado para auditoria. Vale para todos os eventos da execução da triagem.
- Q: O proponente vê `FIELD_REVIEWED`? → A: Não. O evento só conta campos revisados durante a edição do triador, antes da decisão. Os pareceres chegam ao proponente pelo formulário depois da decisão. Aprovado pelo usuário em 2026-11-27.
- Q: `reviews` em `GET .../form` mostra pareceres em edição? → A: Só para quem tem `triage.review`, que edita no mesmo campo. Os demais veem só pareceres de triagem concluída, como em `submission-versions` e `previous_reviews`. Aprovado pelo usuário em 2026-11-27; fecha a pendência da Spec 046.
- Q: Quem vê os eventos de convite? → A: Quem gerencia participantes vê todos, com e-mail e autor. Os demais veem só o aceite do próprio convite. Mesma regra dos eventos de designação. Aprovado pelo usuário em 2026-11-27 (issue #84).
- Q: O que o cargo de revisão cega vê do autor dos eventos? → A: Quem só tem cargos de revisão cega (`adhoc_evaluator`, `peer_reviewer`) não recebe a identidade do proponente nem de outro avaliador em nenhum evento. Com outro cargo no processo, vale a união, como no andamento (Spec 048). Aprovado pelo usuário em 2026-11-27 (issue #84).
- Q: O que muda depois da revisão do Codex na PR? → A: Aprovado pelo usuário em 2026-11-27. (a) `AI_CRITERION_FEEDBACK_RECORDED` também chega sem autor a quem não tem `triage.review`, porque vai na execução da submissão. (b) Os `NOTIFICATION_*` do envio de convite seguem a regra dos convites. (c) Sem cargo efetivo, o cegamento vale, para não falhar aberto se a designação for revogada durante a leitura. (d) A união de cargos continua no código, mas o teste dela sai, como na Spec 048: a issue #85 proíbe o acúmulo de cargos. (e) A corrida entre salvar parecer e decidir a triagem é anterior a esta spec e fica registrada em `docs/observacoes-e-pendencias.md`. (f) O downgrade da migração não despublica as versões dos templates, como nas mudanças de template anteriores.
- Q: Os processos já criados ganham a visão do proponente na triagem? → A: Sim, por migração de dados, como pede a issue #81. O usuário decidiu em 2026-11-27 fazer a migração por ser simples, apesar da regra de 2026-10-24 de não planejar migração de dados do deploy de dev.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - O proponente acompanha a triagem (Priority: P1)

Depois do envio e da pré-avaliação, o proponente vê a tarefa de triagem com status e prazo. Quando a BraCVAM decide, ele vê a decisão e a justificativa na linha do tempo, sem saber quem avaliou.

**Why this priority**: sem isso, um processo aprovado aparece ao proponente como "Com a BraCVAM" para sempre (issue #81).

**Independent Test**: enviar uma submissão, deixar a pré-avaliação aprovar, decidir a triagem como BraCVAM nos três desfechos e conferir, como proponente, as tarefas e a linha do tempo.

**Acceptance Scenarios**:

1. **Given** uma submissão enviada e aprovada na pré-avaliação, **When** o proponente consulta as tarefas do processo, **Then** recebe a tarefa de triagem pronta, sem permissão de agir.
2. **Given** a triagem aprovada, **When** o proponente consulta as tarefas e a linha do tempo, **Then** vê a tarefa de triagem concluída e o evento `TRIAGE_APPROVED` com a justificativa e sem autor.
3. **Given** a triagem reprovada, **When** o proponente consulta a linha do tempo, **Then** vê `TRIAGE_REJECTED` com a justificativa e sem autor.
4. **Given** a triagem devolvida para ajustes, **When** o proponente consulta a linha do tempo, **Then** vê `REVISION_REQUESTED` com a justificativa e sem autor.
5. **Given** a BraCVAM salvou pareceres por campo, **When** o proponente consulta a linha do tempo, **Then** não recebe `FIELD_REVIEWED`.
6. **Given** um proponente, **When** ele tenta salvar pareceres ou decidir a triagem, **Then** recebe `403`.
7. **Given** um usuário com `triage.review`, **When** ele consulta a linha do tempo, **Then** vê os eventos da triagem com o autor.
8. **Given** um processo criado antes da mudança, **When** a migração roda e o proponente consulta as tarefas, **Then** ele vê a tarefa de triagem como num processo novo.

---

### User Story 2 - O proponente lê só pareceres decididos (Priority: P2)

O proponente abre o formulário da submissão e vê só os pareceres de uma triagem já decidida. O triador continua lendo o próprio rascunho no mesmo campo.

**Why this priority**: o rascunho pode mudar antes da decisão, e mostrá-lo antecipa uma decisão que a BraCVAM ainda não tomou. O defeito já existia antes desta spec.

**Independent Test**: salvar pareceres como BraCVAM sem decidir e comparar o formulário da submissão como proponente e como triador; depois decidir e comparar de novo.

**Acceptance Scenarios**:

1. **Given** pareceres salvos e triagem sem decisão, **When** o proponente consulta o formulário da submissão, **Then** `reviews` vem vazio.
2. **Given** a mesma situação, **When** o triador consulta o formulário, **Then** `reviews` traz os pareceres em edição.
3. **Given** a triagem decidida, **When** o proponente consulta o formulário daquela execução, **Then** `reviews` traz os pareceres, sem autor.

---

### User Story 3 - Convites ficam com quem gerencia participantes (Priority: P1)

Quem gerencia os participantes vê os convites do processo. Os demais participantes não leem o e-mail nem o cargo de quem foi convidado.

**Why this priority**: hoje o proponente lê o e-mail do avaliador ad hoc convidado, e um laboratório lê os convites dos outros (issue #84).

**Independent Test**: convidar um avaliador ad hoc e membros de dois laboratórios, aceitar os convites e conferir a linha do tempo como gestor, como proponente e como cada laboratório.

**Acceptance Scenarios**:

1. **Given** convites criados, reenviados, revogados e aceitos, **When** quem gerencia participantes consulta a linha do tempo, **Then** vê os quatro tipos de evento com e-mail e autor.
2. **Given** um convite para o avaliador ad hoc, **When** o proponente consulta a linha do tempo, **Then** não recebe nenhum evento desse convite.
3. **Given** convites aceitos por dois laboratórios, **When** um membro do laboratório A consulta a linha do tempo, **Then** recebe o aceite do próprio convite e nenhum evento de convite do laboratório B.
4. **Given** eventos de convite ocultos, **When** o usuário pagina a linha do tempo, **Then** o total conta só os eventos que ele vê.

---

### User Story 4 - O avaliador cego não identifica o proponente (Priority: P1)

O avaliador ad hoc e o revisor por pares leem a linha do tempo sem descobrir quem é o proponente nem quem são os outros avaliadores.

**Why this priority**: a revisão cega é requisito explícito (RF050), e a designação do avaliador ad hoc já existe.

**Independent Test**: criar um processo, designar dois avaliadores ad hoc e conferir, como um deles, que nenhum evento traz a identidade do proponente nem do outro avaliador.

**Acceptance Scenarios**:

1. **Given** um processo criado e enviado pelo proponente, **When** um avaliador ad hoc consulta a linha do tempo, **Then** `PROCESS_CREATED` e os demais eventos de autoria do proponente vêm sem autor.
2. **Given** dois avaliadores ad hoc no processo, **When** um deles consulta a linha do tempo, **Then** não recebe a identidade do outro em nenhum evento e recebe a própria.
3. **Given** um avaliador ad hoc que também é do Grupo Gestor no processo, **When** ele consulta a linha do tempo, **Then** vê os autores, pela união dos cargos. Sem teste: a issue #85 proíbe o acúmulo de cargos.
4. **Given** um evento da BraCVAM ou do administrador, **When** o avaliador ad hoc o recebe, **Then** o autor vem preenchido.

### Edge Cases

- Proponente que também tem `triage.review`: vê o autor, porque a regra segue a permissão.
- Devolução pela triagem: `RETURN_REVIEW_OPENED` continua sem autor para quem não tem `triage.review`.
- Triagem reaberta por contestação da IA: os pareceres da nova execução ficam ocultos ao proponente até a nova decisão.
- Migração rodada duas vezes ou num processo em que o proponente já tem a visão: a concessão não se repete.
- Quem não gerencia participantes e não tem cargo de revisão cega continua vendo o autor dos eventos do processo, como hoje.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Os cinco templates MUST conceder a visão de `triage_evaluation` ao cargo `proponent`, mantendo a edição só com `bracvam`, e cada template MUST ter a versão incrementada.
- **FR-002**: Uma migração de dados MUST conceder a mesma visão às instâncias de `triage_evaluation` já criadas, sem repetir a concessão, e o downgrade MUST retirá-la.
- **FR-003**: O proponente MUST ver a tarefa de triagem nas rotas de tarefas, sem poder agir sobre ela.
- **FR-004**: A linha do tempo MUST omitir o autor de `TRIAGE_APPROVED`, `TRIAGE_REJECTED`, `REVISION_REQUESTED`, `RETURN_REVIEW_OPENED` e `AI_CRITERION_FEEDBACK_RECORDED` para quem não tem `triage.review`. O autor continua gravado.
- **FR-005**: A linha do tempo MUST omitir `FIELD_REVIEWED` para quem não tem `triage.review`.
- **FR-006**: O formulário de uma atividade MUST devolver em `reviews` só os pareceres de triagem concluída para quem não tem `triage.review`.
- **FR-007**: A linha do tempo MUST tratar `INVITE_CREATED`, `INVITE_RESENT`, `INVITE_REVOKED` e `INVITE_ACCEPTED` como eventos de participante: quem gerencia participantes vê todos, e os demais veem só o `INVITE_ACCEPTED` de autoria própria. Os `NOTIFICATION_*` do envio de convite seguem a mesma regra.
- **FR-008**: Para quem só tem cargos de revisão cega no processo, a linha do tempo MUST omitir o autor quando ele for o proponente ou outro titular de cargo de revisão cega. Quem não tem acesso amplo nem cargo efetivo recebe o mesmo cegamento.
- **FR-009**: A paginação da linha do tempo MUST contar no total só os eventos visíveis ao usuário.
- **FR-010**: As rotas de escrita da triagem MUST continuar exigindo `triage.review`.
- **FR-011**: O manual MUST descrever a visão da triagem pelo proponente, o filtro de `reviews` e a visibilidade da linha do tempo por cargo.

### Key Entities *(include if feature involves data)*

- **Concessão da atividade**: os cargos que veem e os que editam uma atividade de um processo, copiados do template na criação.
- **Evento da linha do tempo**: tipo, autor, execução e contexto. O filtro decide se o evento aparece e se o autor aparece.
- **Parecer por campo**: status e comentário da triagem sobre um campo, ligado ao formulário de uma execução.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nos três desfechos da triagem, o proponente identifica a decisão pela tarefa e pela linha do tempo, sem outra consulta.
- **SC-002**: Nenhuma resposta ao proponente traz a identidade de quem fez a triagem.
- **SC-003**: Nenhuma resposta ao proponente ou a um laboratório traz e-mail ou cargo de um convite de outra pessoa.
- **SC-004**: Nenhum evento da linha do tempo entregue a um avaliador sob cegamento traz a identidade do proponente ou de outro avaliador. As outras respostas do processo já não a trazem: a listagem de participantes devolve só a própria designação, o processo não expõe o criador e os convites ficam com quem gerencia participantes.
- **SC-005**: Quem gerencia participantes e quem tem `triage.review` continuam vendo os mesmos eventos e autores de antes.
- **SC-006**: Depois da migração, 100% das instâncias de triagem existentes concedem a visão ao proponente.

## Assumptions

- "Triagem concluída" segue o critério que a Spec 046 já usa em `submission-versions` e `previous_reviews`.
- A regra de cegamento reaproveita a do andamento (Spec 048) e não cria cargo novo. A avaliação ad hoc (E4) ainda não existe, então os testes usam a designação do cargo.
- A visão da triagem não abre formulário nem outra rota de leitura, porque a triagem não tem formulário próprio.
- O cegamento usa a regra do andamento da Spec 048 (`progress_view` e `viewer_assignments` de `pivma.core.process_progress`), que entrou em `develop` com a PR #83. A matriz de acesso da issue #87 vai absorver as regras desta spec para a linha do tempo.
- Fora do escopo: `PROCESS_ARCHIVED`, `PROCESS_DELETED`, `LABORATORY_WAIVED` e os eventos de execução de laboratório, que já seguem regras adequadas.
