# Research: Homologação da estrutura do estudo

Nenhum item do Technical Context ficou em aberto. As decisões abaixo saem da
leitura do código e das respostas do usuário em 2026-10-14.

## R1. A homologação é uma atividade da Etapa 2

- **Decision**: os cinco templates ganham, no fim de `phase_2_role_assignment`,
  a atividade `structure_approval` (`activity_type: "structure_approval"`,
  `access.edit: ["bracvam"]`). Ela depende, com `ACTIVITY_COMPLETED`, das nove
  atividades da etapa. `sample_receipt` passa a depender de
  `structure_approval` em vez de `sample_definition`. A versão de cada template
  sobe um número: 01, 02, 03 e 05 de 4 para 5; 04 de 6 para 7.
- **Rationale**: o motor já abre uma atividade quando todas as dependências
  concluem (`_advance_dependent_activities`) e a reabre quando elas concluem
  de novo, desde que ela esteja `BLOCKED`. O portão "aprovação bloqueada
  enquanto houver atividade pendente" sai desse mecanismo sem código novo.
  As dependências ficam gravadas por instância, então processos criados com
  as versões anteriores seguem o fluxo antigo (FR-003).
- **Alternatives considered**: uma flag no processo ou um status novo. Ambas
  exigiriam um segundo mecanismo de liberação ao lado das dependências, e a
  Etapa 3 teria que consultá-lo.

## R2. Os pontos auditados são as dependências da homologação

- **Decision**: o serviço lê os pontos nas linhas de `ActivityDependency` da
  atividade `structure_approval` do processo. Não há lista fixa de chaves no
  código. A pendência de cada ponto depende do `activity_type`:
  `role_assignment` e `sample_definition`.
- **Rationale**: a issue pede um portão generalizado. Se um template
  acrescentar um ponto à Etapa 2, basta declarar a dependência no YAML. O
  plano estatístico entrou assim (R13).
- **Alternatives considered**: lista fixa das nove chaves. Duplicaria o YAML
  e quebraria com a primeira mudança de template.

## R3. Pendências calculadas na hora, sem marcador gravado

- **Decision**: o painel e a aprovação calculam as pendências pela mesma
  função:
  - `activity_not_completed`: o ponto não está `COMPLETED`;
  - `role_without_designation`: ponto `role_assignment` cujo cargo-alvo não
    tem designação ativa (não revogada, não excluída);
  - `laboratory_without_codes`: laboratório de `active_laboratories` sem
    código cego ativo;
  - `codes_without_laboratory`: laboratório com código cego ativo que não
    está em `active_laboratories`.
- **Rationale**: designar e revogar continuam permitidos depois da conclusão
  da atividade. Só um cálculo no momento da decisão garante "de fato
  concluída". `active_laboratories` (designação ativa de participante e
  laboratório não excluído) é o conjunto que `complete_sample_definition`
  usa para gerar e descartar códigos; com a mesma definição, reprovar as
  amostras e concluí-las de novo sempre zera as duas pendências. Um
  laboratório excluído do cadastro com designação ainda ativa gera
  `codes_without_laboratory`.
- **Alternatives considered**: considerar a efetividade da designação
  laboratorial (Spec 035). Ela muda com o vínculo institucional, fora do
  controle de quem monta a equipe. O painel mostra a efetividade de cada
  designação; a pendência usa só designação ativa, a mesma regra de
  `active_laboratories`.

Convite adicional criado depois que a atribuição de cargo concluiu não
reabre a atividade nem constitui, por si só, pendência da homologação
(decisão do usuário em 2026-10-14, Clarifications). Em atribuições abertas
ou reabertas, os convites pendentes continuam impedindo a conclusão.

## R4. Reabrir um ponto reaproveita `_activate_activity`

- **Decision**: para cada ponto reprovado, o serviço chama
  `_activate_activity` com o motivo como `execution_reason`. A função cria a
  execução seguinte, a tarefa do cargo responsável e põe a atividade em
  `IN_PROGRESS`. A execução anterior continua `COMPLETED`, como na diligência
  da triagem. Cada reabertura grava `ACTIVITY_REOPENED`.
- **Rationale**: a função já numera a execução pelo maior número existente,
  porque a triagem passa pelo mesmo ciclo. `sample_service` aceita edição
  sempre que a atividade está `IN_PROGRESS` com execução aberta, e
  `complete_sample_definition` já descarta códigos de laboratório que saiu e
  gera os que faltam.
- **Alternatives considered**: marcar a execução anterior como `SUPERSEDED`,
  como a reabertura por laboratório (Spec 036). A spec pede que a execução
  anterior continue concluída, e a triagem segue o mesmo padrão.
- Dependentes de um ponto reaberto que já concluíram continuam concluídos.
  O BraCVAM reprova também os que quiser rever (Edge Cases da spec).

## R5. Decisão gravada em `decisions`, com os pontos numa coluna nova

- **Decision**: a decisão usa a tabela `decisions` com
  `decision_type = 'STRUCTURE_APPROVAL'`, `outcome` `APPROVED` ou `REJECTED`
  e `activity_run_id` da execução da homologação. A migração acrescenta
  `decisions.rejected_points` (JSONB, anulável), com a lista
  `[{activity_key, reason}]` nas reprovações.
- **Rationale**: a triagem já grava ali autor, data e justificativa, e a
  tabela tem `AuditMixin`. Com os pontos na própria linha, a decisão se
  reconstrói sem consultar a linha do tempo (SC-004).
- **Alternatives considered**: tabela filha de pontos. Mais uma tabela,
  modelo e migração para uma lista que nunca muda depois de gravada. Guardar
  os pontos só no `AuditEvent` faria a leitura de negócio depender do log.

## R6. Fluxo da decisão e concorrência

- **Decision**: `execute_structure_decision` trava o processo
  (`_lock_process`), confere que ele está aberto, recarrega a homologação com
  `populate_existing` e exige `require_activity_access(..., 'edit')`, que já
  cobre 404, 403 e conflito de interesse. Sem execução em andamento: 409
  `invalid_transition`. Na aprovação com pendência: 409 `structure_pending`.
  - Aprovar: grava a decisão, conclui a execução (`_complete_activity_run`),
    conclui a fase 2, trava a linha do template de coleta quando houver
    vínculo e chama `_advance_dependent_activities`, que abre o recebimento
    por laboratório.
  - Reprovar: grava a decisão, conclui a execução, põe a homologação em
    `BLOCKED` com o motivo "Aguardando a reexecução dos pontos reprovados." e
    reabre cada ponto (R4).
- **Rationale**: a trava do processo é a mesma das transições por
  laboratório. A segunda decisão simultânea espera a primeira e encontra a
  homologação sem execução em andamento (FR-018).
- **Alternatives considered**: travar só a atividade. A aprovação também
  mexe na fase 2 e abre a Etapa 3; travar o processo serializa com as outras
  transições que já o travam.
- **Risco aceito, revogação simultânea**: designar e revogar não travam o
  processo. Uma revogação que chega durante a aprovação termina como uma
  revogação logo depois da aprovação, que já é permitida: a Etapa 3 abre
  para os laboratórios com códigos (`_frozen_laboratory_ids`) e a
  designação revogada perde o acesso pelas regras atuais. Travar o processo
  nas rotas de participantes não mudaria esse resultado e acrescentaria
  espera a toda designação.

## R7. Autorização pela atividade, sem permissão nova

- **Decision**: as duas rotas usam `CurrentUser` e checam a concessão da
  atividade `structure_approval`: ver para o painel, editar para decidir. A
  decisão exige também `TrustedOrigin`. Não há permissão global nova nem
  migração de catálogo de permissões.
- **Rationale**: desde a Spec 030 o acesso às atividades vem de `access` no
  template. As rotas de amostras e de recebimento seguem esse padrão. O
  processo invisível para o usuário responde 404, igual à atividade.
- **Alternatives considered**: `require_permission(TRIAGE_REVIEW)` como a
  triagem. A triagem é anterior à Spec 030; replicar o padrão criaria dois
  controles para a mesma decisão.

## R8. Fechamento de atribuição de cargo reaberta

- **Decision**: `_maybe_close_role_assignment_activity` ganha uma condição:
  o cargo precisa ter ao menos uma designação ativa. A revogação de
  designação (`DELETE /processes/{id}/participants/{assignment_id}`) passa a
  chamá-la. A revogação de convite já a chama
  (`routers/process_participants.py`, `revoke_participant_invite`).
- **Rationale**: é a regra escolhida pelo usuário (Clarifications). Os
  chamadores que acabaram de criar uma designação não mudam de
  comportamento.
- **Lacuna anterior corrigida**: hoje, revogar o único convite pendente de um
  cargo sem designação conclui a atribuição com o cargo vazio. Nenhum teste
  cobre esse caso. Com a condição nova a atividade fica em andamento, o que
  a homologação exige (pendência `role_without_designation`). Ganha teste de
  regressão.
- **Alternatives considered**: rota explícita de conclusão. Recusada pelo
  usuário em 2026-10-14 e adotada na revisão do PR #76 (R14).
- **Revisão de 2026-10-16**: a condição de designação ativa continua, mas
  só vale para a primeira execução. Ver R14.

## R9. Trava do template de coleta pelo início da Etapa 3

- **Decision**: `locked_template_ids` passa a contar processos vinculados com
  ao menos uma execução de atividade da fase `phase_3_validation_execution`.
  A aprovação chama `lock_template_row` antes de abrir a Etapa 3.
  `complete_sample_definition` mantém a chamada atual: nos processos das
  versões anteriores, a conclusão das amostras ainda abre a Etapa 3.
- **Rationale**: a primeira execução por laboratório abre no mesmo instante
  em que a Etapa 3 começa, nas duas versões de template. As execuções nunca
  somem: o template continua travado depois que o processo termina ou é
  excluído. O status da fase não serve: excluir o processo antes da Etapa 3
  muda a fase de `NOT_STARTED` para `CANCELLED`, e a regra travaria um
  template que nenhum laboratório usou (encontrado na implementação). Uma
  regra cobre processos novos e antigos. Todo processo com template de
  coleta foi criado com a fase 3 no template: a fase 3 entrou em 2026-10-04
  (Spec 040) e o vínculo em 2026-10-09 (Spec 041). Nenhum processo vinculado
  perde a trava.
- **Alternatives considered**: travar pela atividade `structure_approval`
  concluída. Deixaria sem trava os processos anteriores já vinculados.

## R10. Testes e fábricas existentes

- **Decision**:
  - `RECEIPT_TEMPLATE` (`tests/factories/sample_receipt_factory.py`) copia a
    fase 3 do YAML. A fábrica passa a trocar a dependência do recebimento
    para `sample_definition`, porque o template de teste não tem a Etapa 2
    completa. Os testes focados da Etapa 3 e do template de coleta continuam
    medindo o que medem hoje.
  - As jornadas com templates reais (`test_sample_receipt_journey.py`,
    `test_collection_template_journey.py`) passam pela homologação. O helper
    `sample_steps.py` ganha os passos de designar a equipe completa e
    aprovar.
  - `test_template_phase_2.py` e `test_template_phase_3.py` passam a
    verificar a atividade nova e a dependência nova.
- **Rationale**: a fábrica de teste não é contrato; manter a dependência
  antiga nela evita montar oito designações em cada teste focado.

## R11. Sem notificação nova

- **Decision**: a reprovação não envia e-mail. O responsável vê a tarefa nova
  em `/tasks`, como na diligência da triagem e na reabertura por
  laboratório.
- **Rationale**: nenhuma fonte pede a notificação; a Spec 036 restringe os
  envios aos casos listados.

## R12. Liberação por dependências sob trava da atividade dependente

- **Decision**: em `_advance_dependent_activities`, para cada dependente de
  escopo `process` em `BLOCKED`, o motor relê a atividade com
  `with_for_update()` e `populate_existing`, e `_dependency_satisfied` relê a
  atividade exigida com `populate_existing` em vez de `session.get`. O ramo
  por laboratório não muda.
- **Rationale**: duas transações que concluem, ao mesmo tempo, os dois
  últimos pontos reprovados liam uma a outra como ainda em andamento, e a
  homologação ficava `BLOCKED` sem ninguém para reabri-la. Com a trava, a
  segunda transação espera a primeira terminar e, no nível READ COMMITTED
  do PostgreSQL, a nova leitura vê o ponto que a primeira concluiu. Sem
  `populate_existing`, a sessão devolveria o objeto em cache e a correção não
  teria efeito. O mesmo defeito já existia na abertura de `sample_definition`
  (duas atribuições concluídas ao mesmo tempo); a correção cobre os dois.
- **Deadlock**: o caminho de liberação trava só a linha do dependente, depois
  das linhas que cada operação já trava (designação ou atividade de
  amostras). A decisão trava o processo e não passa por esse caminho para a
  homologação. Não há ciclo.
- **Alternatives considered**: travar o processo em toda conclusão de ponto.
  Funciona, mas espalha `_lock_process` por designação, revogação, convites e
  amostras, e serializa operações que não disputam nada.

## R13. Plano estatístico como atividade de formulário (revisão do PR #76)

- **Decision**: a Etapa 2 ganha `statistical_plan` (`order_index` 10;
  a homologação passa a 11), com `assigned_role` e `access.edit`
  `statistician`, dependência `assign_statistician` e
  `form_template_key: "statistical_plan_v1"`. O formulário tem
  `plan_file` (`file_upload`, obrigatório, PDF ou DOCX) e `summary`
  (`textarea`, opcional). A homologação ganha a dependência
  `statistical_plan`. As versões dos templates não sobem de novo: a
  homologação ainda não saiu da branch, e a versão 5 (7 no template 04)
  ainda não chegou a nenhum ambiente.
- **Envio**: `submit_activity_form` (antes `submit_proposal_form`,
  renomeada porque deixou de ser só da proposta) valida, grava e conclui a
  execução para qualquer formulário. Os efeitos da proposta (Dossiê de Submissão,
  `SUBMISSION_SUBMITTED`, pré-avaliação por IA e triagem) passam a valer
  só para `proposal_submission`. Os demais formulários gravam
  `FORM_SUBMITTED` (`activity_key`, `run_number`) e chamam
  `_advance_dependent_activities`. Sem esse corte, uma avaliação por IA
  configurada para o formulário do plano mexeria na triagem.
- **Painel**: o ponto do plano usa só a pendência `activity_not_completed`.
  O BraCVAM lê o plano pelo formulário (`GET .../activities/statistical_plan/form`)
  e baixa o anexo pela rota de anexos, porque Admin e BraCVAM veem toda
  atividade.
- **Reprovação**: `_activate_activity` já cria `FormInstance` nova na
  execução nova; a anterior continua enviada.
- **Alternatives considered**: uma tabela própria para o plano, com rota
  dedicada. Repetiria o que o formulário já faz (anexo, rascunho, envio,
  histórico por execução).

## R14. Conclusão explícita da atribuição reaberta (revisão do PR #76)

- **Decision**: `_maybe_close_role_assignment_activity` deixa de concluir
  execuções com `run_number > 1`. A rota
  `POST /processes/{id}/participants/roles/{role_key}/complete` conclui a
  atribuição em andamento do cargo. Autorização: `can_manage_role_assignment`,
  a mesma da designação. Com a atividade travada e relida, a rota confere
  que ela está `IN_PROGRESS` com execução aberta (409
  `invalid_transition`), que não há convite pendente (409
  `pending_invites`) e que o cargo tem designação ativa (409
  `role_without_designation`). Depois conclui a execução, libera as
  dependentes e grava `ROLE_ASSIGNMENT_COMPLETED` (`activity_key`,
  `role_key`, `run_number`).
- **Rationale**: a gestora pode designar a pessoa nova antes de revogar a
  antiga. Com o fechamento automático, a atividade concluía na designação,
  a homologação reabria com as duas pessoas no cargo e o painel não
  acusava nada, porque só aponta cargo vazio. A rota faz a gestora dizer
  quando terminou. Na primeira execução não há pessoa antiga a trocar, e o
  fechamento automático continua.
- **Alternatives considered**: pendência para cargo com mais de uma
  designação. Cargos como laboratórios participantes e colaboradores
  aceitam várias pessoas, então a regra não separa erro de equipe
  legítima.
