# Feature Specification: Helper Único de Conclusão de Atividade (Issue #22)

**Feature Branch**: `026-activity-completion-helper`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "Aceitos os riscos vamos resolver essa ISSUE, se lembre de fazer isso em uma branch separada, vamos criar um PR depois de acabar"

## Contexto

A sequência "concluir a execução atual de uma atividade e destravar as
dependentes" está hoje duplicada em quatro pontos do motor de processos
(`core/process_engine.py` e `core/pre_evaluation_service.py`): a submissão da
proposta, a decisão de triagem, a conclusão da pré-avaliação por IA e a
solicitação de revisão direta. Dois desses pontos usam o mecanismo genérico
já existente (`_advance_dependent_activities`, dirigido pela tabela
`ActivityDependency`); os outros dois usam um helper bespoke
(`_unblock_triage_activity`) que resolve a atividade de triagem por chave
fixa, em vez de pelo motor genérico de dependências — o próprio código já
documenta essa dívida como "caminho legado".

Na análise da issue (`pivma-bracvam/pivma-back#22`), identificou-se que o
helper bespoke também tem uma diferença de comportamento em relação ao
mecanismo genérico: ele reaproveita a mesma execução (`ActivityRun`) e a
mesma tarefa (`Task`) da triagem em todas as rodadas de diligência, em vez de
criar uma nova a cada rodada (como já acontece com a submissão da proposta,
via `_open_new_submission_run`). Isso produz efeitos observáveis
questionáveis: depois de uma diligência de triagem, a pessoa responsável pela
triagem não recebe uma tarefa pendente para a nova rodada, e o cálculo de
atraso (SLA) da triagem nunca reinicia — fica preso ao início da primeira
rodada do processo.

Esta spec cobre a unificação dos quatro pontos em um único helper **e**
trata essa diferença de comportamento da triagem como uma correção de bug
(decisão tomada nesta conversa, riscos aceitos), não como um efeito colateral
indesejado a evitar. O objetivo final é que os quatro pontos usem a mesma
implementação, e que essa implementação recrie execução e tarefa a cada
rodada de qualquer atividade dependente destravada — incluindo a triagem.

## Clarifications

### Session 2026-09-17

- Q: A diferença de comportamento da triagem (execução/tarefa reaproveitadas entre rodadas, sem tarefa nova para o triador) deve ser preservada como está (refactor mecânico puro) ou corrigida junto com a unificação? → A: Corrigida — tratar como correção de bug. A triagem passa a criar execução e tarefa novas a cada rodada, alinhada ao padrão já usado pela submissão.
- Q: Essa correção exige mudança de contrato de API (endpoints, schemas de request/response)? → A: Não. A análise dos consumidores existentes (Kanban, lista de tarefas, timeline) mostrou que eles já foram desenhados para múltiplas execuções/tarefas por atividade (é assim que a submissão já se comporta hoje); a mudança é só de dado observável (número de execução incrementando, tarefa nova aparecendo, data de SLA recalculada por rodada), não de forma.
- Q: O trabalho deve ser feito na branch atual (`develop`) ou em uma branch separada? → A: Branch separada, com PR ao final (`chore/026-activity-completion-helper`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver a pendência da nova rodada de triagem depois de uma diligência (Priority: P1)

A pessoa responsável pela triagem (perfil BraCVAM) pede uma diligência
("Necessita Revisão") em uma proposta. O proponente ajusta e reenvia. Hoje,
ao reenviar, nenhuma tarefa nova de triagem aparece na lista de pendências
dessa pessoa — a atividade de triagem é destravada, mas reaproveita
silenciosamente a execução e a tarefa da rodada anterior, já concluídas.

**Why this priority**: É o bug concreto que motivou tratar esta unificação
como correção, não só como refactor interno. Sem essa tarefa visível, a
pendência da segunda rodada de triagem em diante pode passar despercebida
por quem deveria agir sobre ela.

**Independent Test**: Rodar o fluxo completo (submissão → diligência de
triagem → reenvio do proponente) e confirmar que a listagem de tarefas
pendentes da pessoa responsável pela triagem passa a conter uma tarefa nova,
distinta da tarefa (já concluída) da primeira rodada.

**Acceptance Scenarios**:

1. **Given** uma triagem que solicitou diligência e cuja execução já está
   concluída, **When** o proponente reenvia a submissão corrigida, **Then**
   uma nova execução da atividade de triagem é criada, com sua própria
   tarefa pendente visível para o cargo responsável.
2. **Given** a atividade de triagem tem uma nova execução ativa, **When** o
   sistema classifica essa etapa quanto a prazo/atraso, **Then** a contagem é
   calculada a partir do início dessa nova execução, não da execução
   anterior.
3. **Given** a execução anterior da triagem já está concluída, **When** a
   nova execução é criada, **Then** a execução e a tarefa anteriores
   permanecem com seu status final preservado, sem serem reabertas ou
   removidas.

---

### User Story 2 - Manter um único ponto de manutenção para "concluir e destravar" no motor de processos (Priority: P2)

Quem mantém o motor de processos precisa alterar ou depurar a sequência de
conclusão de atividade (por exemplo, mudar o formato de um evento de
auditoria, ou adicionar uma nova verificação antes de destravar dependentes)
sem precisar localizar e replicar a mudança em quatro lugares diferentes,
alguns dos quais resolvendo a atividade dependente por chave fixa em vez de
pelo mecanismo genérico de dependências.

**Why this priority**: É o propósito original da issue (chore de
infraestrutura interna) e reduz o risco de os quatro pontos divergirem
silenciosamente à medida que novas atividades forem adicionadas nas próximas
etapas do roadmap.

**Independent Test**: Inspecionar os quatro pontos de conclusão (submissão,
decisão de triagem, pré-avaliação por IA, revisão direta) e confirmar que
todos chamam a mesma função para concluir a execução atual e destravar
dependentes, sem lógica duplicada de conclusão de atividade fora dela.

**Acceptance Scenarios**:

1. **Given** os quatro pontos de conclusão de atividade do motor, **When** o
   código é revisado, **Then** todos usam o mesmo helper para marcar a
   execução/atividade/tarefas como concluídas e para destravar dependentes.
2. **Given** o helper único, **When** uma atividade dependente é destravada
   por qualquer um dos quatro pontos, **Then** o mecanismo usado é sempre o
   genérico, dirigido pela tabela de dependências declaradas no template —
   nenhum ponto resolve mais a atividade dependente por chave fixa.

---

### User Story 3 - Auditar o desbloqueio da triagem de forma consistente com as demais atividades (Priority: P3)

Alguém auditando o histórico de um processo (linha do tempo) espera ver um
evento registrado sempre que uma atividade dependente é destravada — hoje
isso já acontece para atividades destravadas pelo mecanismo genérico, mas
não para a triagem, destravada pelo caminho bespoke sem gerar esse evento.

**Why this priority**: Efeito colateral desejável da unificação, mas não é o
motivador principal nem bloqueia as User Stories 1 e 2.

**Independent Test**: Destravar a atividade de triagem por qualquer um dos
três caminhos que hoje a acionam (submissão sem avaliação por IA associada,
pré-avaliação por IA com resultado positivo, revisão direta) e confirmar que
a linha do tempo do processo passa a registrar um evento de desbloqueio
consistente com o já emitido para outras atividades dependentes.

**Acceptance Scenarios**:

1. **Given** a atividade de triagem é destravada por qualquer um dos
   caminhos existentes, **When** a linha do tempo do processo é consultada,
   **Then** ela contém um evento de desbloqueio para a triagem, no mesmo
   formato usado para o desbloqueio de outras atividades dependentes.

---

### Edge Cases

- O que acontece quando a atividade de triagem é destravada mais de duas
  vezes ao longo do mesmo processo (múltiplas diligências sucessivas)? Cada
  rodada deve gerar sua própria execução e tarefa, numeradas
  sequencialmente, sem afetar o histórico das rodadas anteriores.
- O que acontece com a tarefa da rodada anterior da triagem quando uma nova é
  criada? Permanece com seu status final (concluída) preservado, servindo de
  histórico; não é reaberta, alterada nem removida.
- Como o helper único deve se comportar quando o processo foi cancelado ou
  arquivado entre a conclusão de uma atividade e o avanço das dependentes?
  Deve preservar as mesmas checagens de processo mutável já existentes no
  motor, sem impedir a conclusão da atividade que disparou o avanço.
- O que acontece com processos que já têm uma triagem em andamento (rodada
  única, reaproveitada) no momento em que esta mudança entra em produção?
  Não há necessidade de correção retroativa — o novo comportamento vale a
  partir da próxima vez que a triagem desses processos for destravada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer um único ponto de entrada para
  "concluir a execução atual de uma atividade e destravar as dependentes",
  usado pelos quatro pontos do motor que hoje reimplementam essa sequência
  isoladamente: submissão da proposta, decisão de triagem, conclusão da
  pré-avaliação por IA e solicitação de revisão direta.
- **FR-002**: Para os efeitos já cobertos hoje pelo mecanismo genérico de
  dependências, o helper único DEVE preservar a ordem exata dos efeitos
  colaterais observados atualmente (marcação de execução/atividade/tarefas
  como concluídas, registro de evento de auditoria, avanço de dependentes).
- **FR-003**: Ao destravar a atividade de triagem, o sistema DEVE passar a
  criar uma nova execução e uma nova tarefa a cada rodada, em vez de
  reaproveitar a execução/tarefa de uma rodada anterior.
- **FR-004**: O número de execução da atividade de triagem DEVE incrementar
  a cada nova rodada, em vez de permanecer fixo na primeira rodada
  indefinidamente.
- **FR-005**: O sistema DEVE calcular o prazo/atraso de cada rodada da
  triagem a partir do início dessa própria rodada, não do início da primeira
  rodada do processo.
- **FR-006**: O sistema DEVE registrar um evento de auditoria para o
  desbloqueio da atividade de triagem, consistente em formato com o evento já
  emitido para o desbloqueio de outras atividades dependentes.
- **FR-007**: Nenhum endpoint, schema de requisição ou resposta da API DEVE
  ter sua forma alterada (nomes e tipos de campos existentes preservados); os
  únicos efeitos visíveis a consumidores da API são os descritos nos FR-003 a
  FR-006, e são efeitos de dado, não de forma.
- **FR-008**: A suíte de testes existente DEVE continuar passando
  integralmente; os testes que hoje presumem o comportamento antigo da
  triagem (execução única reaproveitada entre rodadas) DEVEM ser atualizados
  para refletir o novo comportamento pretendido, e essa atualização deve ficar
  documentada como intencional.
- **FR-009**: O helper único DEVE ser coberto por teste unitário isolado,
  independente dos testes de integração dos quatro pontos que passam a
  usá-lo.

### Key Entities *(include if feature involves data)*

- **ActivityInstance**: atividade dentro de um processo; seu status
  (bloqueada/pronta/em andamento/concluída) muda conforme execuções são
  concluídas e dependentes avançam.
- **ActivityRun**: uma execução/rodada de uma atividade, identificada por um
  número sequencial dentro da atividade; após esta mudança, a triagem passa a
  poder ter mais de uma, assim como já acontece com a submissão.
- **Task**: tarefa de trabalho associada a uma execução, com cargo
  responsável e prazo; a mudança garante uma tarefa nova por rodada da
  triagem.
- **ActivityDependency**: declaração de dependência entre atividades (já
  existente), usada pelo helper único para decidir quais atividades
  destravar após uma conclusão.
- **AuditEvent**: evento de auditoria; ganha um emissor consistente também
  para o desbloqueio da triagem.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Depois de uma diligência de triagem seguida de reenvio da
  proposta, a pessoa responsável pela triagem enxerga uma pendência própria
  daquela rodada em sua lista de tarefas, em 100% dos casos (hoje, 0%).
- **SC-002**: O prazo de atraso exibido para a etapa de triagem reflete o
  início da rodada corrente, não da primeira rodada do processo, em 100% dos
  processos com mais de uma rodada de triagem.
- **SC-003**: Os quatro pontos de conclusão de atividade do motor de
  processos usam a mesma implementação para "concluir e destravar
  dependentes" — verificável por inspeção de código, sem nenhum bloco
  duplicado remanescente.
- **SC-004**: 100% dos fluxos e testes automatizados existentes continuam
  passando após a mudança, com exceção dos testes explicitamente atualizados
  para refletir o novo comportamento da triagem, documentados como tal.
- **SC-005**: Nenhuma alteração de contrato de API é necessária para esta
  mudança (nenhum endpoint, request ou schema de resposta muda de forma).

## Assumptions

- A correção do comportamento da triagem (nova execução/tarefa por rodada)
  é tratada como correção de bug, e não como quebra de compatibilidade —
  decisão já validada com o responsável pelo produto nesta conversa, com os
  riscos de dado observável (listados em "Clarifications") aceitos.
- Os consumidores existentes da API (painel Kanban, listagem de tarefas,
  linha do tempo do processo) já lidam com múltiplas execuções e tarefas
  históricas por atividade, pois é assim que a submissão da proposta já se
  comporta hoje; não é necessária nenhuma mudança de contrato ou de interface
  para suportar o mesmo padrão na triagem.
- Não há necessidade de corrigir retroativamente processos já em andamento;
  o novo comportamento vale a partir de quando esta mudança entrar em
  produção, para as próximas rodadas de triagem que ocorrerem dali em
  diante.
- O escopo cobre a Etapa 1 do motor de processos (submissão e triagem) e os
  quatro pontos hoje identificados; não cobre novos tipos de atividade das
  próximas etapas do roadmap além de garantir que, quando implementados,
  usem o mesmo helper único.
