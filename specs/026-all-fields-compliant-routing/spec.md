# Feature Specification: 026 - Regra de Consolidação: Todos os Campos Conformes para Avançar à Triagem

**Feature Branch**: `026-all-fields-compliant-routing`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Altera a regra de voltar a submissão pra o usuario ou não, só vai para o BraCVAM se todos os campos forem `conformes`"

## Contexto e Motivação

A Spec 013 definiu a regra de consolidação da pré-avaliação por IA (FR-030/FR-030a):
o resultado é **negativo** (retorna ao proponente) quando existe **pelo menos uma**
não conformidade de severidade **alta ou crítica**; não conformidades de severidade
baixa/média viram apenas alertas e **não** impedem o avanço automático para a
triagem do BraCVAM.

Esta feature substitui esse critério por uma regra mais estrita: a submissão só
avança automaticamente para a triagem do BraCVAM quando **todos** os critérios
avaliados pela IA concluírem como **conformes**. Qualquer não conformidade — de
qualquer severidade — passa a devolver a submissão ao proponente. O roteamento fixo
em si (positivo → triagem; negativo → proponente), as opções do proponente diante de
um retorno negativo (corrigir e reenviar / solicitar intervenção direta do BraCVAM) e
a decisão humana de triagem (100% manual, inalterada) continuam exatamente como
especificado nas Specs 013, 014 e 020.

## Clarifications

### Session 2026-09-18

- Q: Um critério **indeterminado** (hoje só possível em critérios de documento/OCR/imagem,
  que permanecem mockados) conta como não conformidade para a regra "todos os campos
  conformes"? → A: Sim. Indeterminado bloqueia o avanço automático exatamente como
  não conforme/parcialmente conforme. Se um campo do tipo documento marcado para
  avaliação por IA sempre retornar indeterminado (e, portanto, negativo), isso é
  aceito como comportamento esperado, não um defeito — o caminho do proponente nesse
  caso é solicitar intervenção direta do BraCVAM (já previsto na Spec 013).
- Q: Quando o bloqueio for causado exclusivamente por critério(s) indeterminado(s),
  o sistema deve sinalizar explicitamente que o caminho recomendado é a intervenção
  direta (em vez de "corrigir e reenviar")? → A: Não. A síntese apresenta as duas
  opções (corrigir e reenviar / solicitar intervenção direta) da mesma forma
  genérica de hoje, sem distinguir se a causa do bloqueio é corrigível pelo
  proponente ou depende de capacidade mockada; nenhuma mensagem ou destaque especial
  é introduzido por esta feature para o caso de indeterminado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submissão só chega à triagem quando 100% conforme (Priority: P1)

Como membro do BraCVAM, quero que uma submissão só chegue à minha fila de triagem
quando **todos** os critérios avaliados pela IA tiverem concluído como conformes,
para não gastar tempo analisando propostas com pendências que o próprio proponente
ainda pode corrigir sozinho, independentemente de a pendência ser de severidade
baixa, média, alta ou crítica.

**Why this priority**: É a mudança de regra de negócio central solicitada; sem ela
nada mais desta feature faz sentido.

**Independent Test**: Submeter um formulário cujos critérios resultem em conclusões
mistas (alguns conformes, um único não conforme de severidade **baixa**) e confirmar
que a submissão **não** avança para a triagem — comportamento diferente do da regra
anterior, que só bloquearia em severidade alta/crítica.

**Acceptance Scenarios**:

1. **Given** uma pré-avaliação em que **todos** os critérios concluíram como
   conformes, **When** a execução termina, **Then** o resultado consolidado é
   positivo e a submissão avança automaticamente para a triagem do BraCVAM.
2. **Given** uma pré-avaliação com **pelo menos um** critério concluído como não
   conforme ou parcialmente conforme, de **qualquer** severidade (inclusive baixa),
   **When** a execução termina, **Then** o resultado consolidado é negativo e a
   submissão retorna ao proponente, mesmo que nenhum critério tenha severidade
   alta/crítica.

---

### User Story 2 - Proponente entende exatamente por que a submissão voltou (Priority: P2)

Como Proponente, quero ver claramente, na síntese da pré-avaliação, quais campos
impediram o avanço para a triagem — mesmo quando a pendência é de severidade baixa —
para poder corrigi-los e reenviar sem confusão sobre por que algo que antes "passava"
agora está bloqueando.

**Why this priority**: A mudança de regra altera o que o proponente pode esperar do
sistema; a comunicação precisa acompanhar a mudança de comportamento.

**Independent Test**: Provocar um retorno negativo causado exclusivamente por um
critério de severidade baixa e confirmar que a síntese apresentada identifica esse
critério como o motivo do bloqueio, com a mesma estrutura de evidência/justificativa
já usada para severidades altas.

**Acceptance Scenarios**:

1. **Given** um retorno negativo causado apenas por não conformidades de severidade
   baixa/média, **When** o proponente consulta o resultado, **Then** a síntese lista
   esses critérios como pontos que impediram o avanço, com a mesma evidência e
   recomendação já fornecidas hoje para qualquer não conformidade.

---

### User Story 3 - Intervenção direta continua disponível (Priority: P3)

Como Proponente que discorda do resultado da IA, quero continuar podendo ignorar os
conselhos da IA e solicitar a intervenção direta do BraCVAM mesmo quando a nova regra
"todos conformes" bloquear o avanço automático, para não ficar preso a uma conclusão
automática que considero incorreta.

**Why this priority**: Garante que a régua mais rígida não elimine a válvula de
escape já garantida pela Spec 013; é uma condição de não regressão.

**Independent Test**: Provocar um retorno negativo sob a nova regra e confirmar que
as duas opções de sempre (corrigir e reenviar / solicitar intervenção direta)
continuam disponíveis e funcionam como antes.

**Acceptance Scenarios**:

1. **Given** uma submissão devolvida ao proponente pela nova regra de "todos
   conformes", **When** o proponente solicita intervenção direta do BraCVAM, **Then**
   o sistema encaminha a submissão para a triagem preservando o relatório original da
   IA, exatamente como no comportamento já especificado na Spec 013.

---

### Edge Cases

- **Formulário sem nenhuma avaliação associada**: continua avançando direto para a
  triagem com relatório vazio, sem erro — a regra "todos conformes" é vacuamente
  satisfeita quando não há critérios a avaliar (reafirma FR-027 da Spec 013).
- **Todos os critérios indeterminados** (ex.: formulário só com critérios de
  documento/OCR, hoje mockados): o resultado consolidado é **negativo** — indeterminado
  bloqueia o avanço automático assim como não conforme/parcial (Clarifications
  Session 2026-09-18). Diferente do comportamento da Spec 013 (onde indeterminado
  isolado nunca tornava o resultado negativo), aqui a submissão retorna ao
  proponente; como uma capacidade mockada nunca deixa de ser indeterminada, o único
  caminho de avanço é o proponente solicitar intervenção direta do BraCVAM.
- **Campo do tipo documento marcado para avaliação por IA**: por depender de leitura
  de documento (capacidade mockada), esse critério é sempre indeterminado e, portanto,
  sempre bloqueia o avanço automático sob esta regra. Isso é esperado e aceito — não
  é tratado como defeito. O proponente vê as mesmas duas opções genéricas de sempre
  (corrigir e reenviar / solicitar intervenção direta do BraCVAM); o sistema não
  destaca ou recomenda uma opção especificamente para esse caso (Clarifications
  Session 2026-09-18).
- **Único critério de severidade baixa não conforme, todo o restante conforme**:
  agora **bloqueia** o avanço — mudança de comportamento em relação à regra anterior,
  que só bloqueava em severidade alta/crítica.
- **Reenvio após correção parcial** (ainda resta um critério não conforme ou
  parcialmente conforme, de qualquer severidade): a nova pré-avaliação continua
  retornando a submissão ao proponente até que todos os critérios fiquem conformes.
- **Execuções de pré-avaliação concluídas antes desta mudança**: mantêm o resultado
  histórico calculado pela regra anterior; não são reprocessadas nem reclassificadas
  retroativamente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST alterar a regra de consolidação da pré-avaliação por IA
  (que substitui FR-030 da Spec 013): o resultado consolidado é **positivo** se e
  somente se **todos** os critérios avaliados concluírem como **conformes**; **qualquer**
  critério concluído como **não conforme**, **parcialmente conforme** ou
  **indeterminado** torna o resultado **negativo**, independentemente da severidade
  atribuída ao critério.
- **FR-002**: O sistema MUST NOT usar a severidade do critério (baixa, média, alta,
  crítica) como fator que decide sozinho o avanço ou o retorno da submissão; a
  severidade permanece registrada e exibida como metadado e como critério de
  agrupamento de alertas na tela de triagem, mas deixa de ser o gatilho da
  consolidação.
- **FR-003**: O sistema MUST tratar um critério com conclusão **indeterminada**
  (ex.: documento/OCR/imagem, capacidades mockadas) como **bloqueante** para efeito
  desta regra, no mesmo nível que "não conforme" e "parcialmente conforme" — um
  formulário com pelo menos um critério indeterminado MUST NOT produzir resultado
  consolidado positivo, mesmo que nenhum outro critério seja não conforme
  (Clarifications Session 2026-09-18). Um critério indeterminado que, pela natureza
  mockada da capacidade, nunca deixará de ser indeterminado MUST continuar
  permitindo ao proponente o caminho de intervenção direta do BraCVAM (FR-005) como
  única via de avanço.
- **FR-004**: O sistema MUST manter inalterado o roteamento fixo já existente
  (FR-030a da Spec 013): resultado positivo encaminha automaticamente a submissão
  para a triagem do BraCVAM; resultado negativo retorna a submissão ao proponente com
  o relatório completo da pré-avaliação.
- **FR-005**: O sistema MUST manter inalteradas, diante de um resultado negativo, as
  duas opções já garantidas ao proponente pela Spec 013 (FR-034 a FR-038): corrigir e
  reenviar (nova pré-avaliação) ou ignorar os conselhos da IA e solicitar intervenção
  direta do BraCVAM, preservando o relatório original.
- **FR-006**: O sistema MUST manter inalterado o comportamento para formulários sem
  nenhuma avaliação associada: a submissão segue direto para a triagem com relatório
  de pré-avaliação vazio, sem erro (reafirma FR-027 da Spec 013).
- **FR-007**: O sistema MUST aplicar a nova regra de consolidação apenas às
  execuções de pré-avaliação processadas a partir da entrada em vigor desta mudança;
  execuções concluídas anteriormente MUST NOT ser reprocessadas nem ter seu resultado
  histórico recalculado retroativamente.
- **FR-008**: O sistema MUST apresentar, na síntese exibida ao proponente e no painel
  do triador, qualquer critério não conforme, parcialmente conforme ou indeterminado
  como motivo do bloqueio, com a mesma evidência, justificativa e recomendação já
  fornecidas hoje, independentemente de sua severidade ser baixa ou média.
- **FR-009**: A decisão humana de triagem (`execute_triage_decision`: aprovar,
  rejeitar, solicitar diligência) MUST permanecer inalterada e independente desta
  regra — a mudança afeta exclusivamente o gate automático de entrada na triagem
  (pré-avaliação por IA), não a deliberação manual do BraCVAM sobre uma submissão já
  admitida na triagem.

### Key Entities *(include if feature involves data)*

- **Resultado de Critério (Criterion Result)**: mantém as conclusões já existentes
  (conforme / não conforme / parcialmente conforme / indeterminado); passa a ser
  consultado individualmente (sem agregação por severidade) pela nova regra de
  consolidação.
- **Relatório de Pré-avaliação (Pre-evaluation Report)**: o **resultado consolidado**
  (positivo/negativo) passa a significar "positivo sse 100% dos critérios avaliados
  concluíram estritamente como conformes (não conforme, parcial e indeterminado
  bloqueiam)", em vez de "positivo sse nenhuma não conformidade alta/crítica".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das pré-avaliações com pelo menos um critério não conforme ou
  parcialmente conforme, de qualquer severidade, resultam em retorno automático da
  submissão ao proponente.
- **SC-002**: 100% das pré-avaliações em que todos os critérios avaliados concluem
  estritamente como conformes (nenhum não conforme, parcial ou indeterminado)
  resultam em avanço automático da submissão para a triagem do BraCVAM.
- **SC-003**: Submissões com pendências de severidade baixa ou média deixam de
  chegar à fila de triagem do BraCVAM sem terem sido corrigidas pelo proponente —
  redução mensurável do volume de submissões incompletas que hoje chegam à triagem.
- **SC-004**: O proponente consegue identificar, a partir da síntese apresentada,
  exatamente quais campos impediram o avanço em 100% dos retornos negativos, mesmo
  quando a única não conformidade é de severidade baixa.
- **SC-005**: Execuções de pré-avaliação concluídas antes da entrada em vigor desta
  mudança preservam seu resultado histórico em 100% dos casos consultados após a
  entrega.

## Assumptions

- Esta mudança substitui exclusivamente a regra de consolidação definida em
  FR-030/FR-030a da Spec 013 (severidade → conformidade total); nenhuma outra parte
  do fluxo de pré-avaliação, do roteamento fixo, das opções do proponente ou da
  observabilidade é alterada.
- A expressão "todos os campos conformes" do pedido do usuário refere-se aos
  **critérios avaliados pela IA** na pré-avaliação (`Conclusion = compliant`), não aos
  pareceres livres do triador humano (`FieldReview.status`, texto livre sem efeito
  automático). A decisão humana de triagem (`execute_triage_decision`) permanece
  100% manual, sem nenhum gate automático de "todos os `FieldReview` conformes"
  introduzido por esta feature.
- Indeterminado (critérios de documento/OCR/imagem, hoje mockados) conta como
  bloqueante para esta regra (Clarifications Session 2026-09-18). Como consequência
  aceita, um formulário com esse tipo de critério nunca atingirá "100% conforme"
  automaticamente enquanto a capacidade permanecer mockada; a intervenção direta do
  proponente (Spec 013, US3) é o caminho previsto para esses casos.
- A mudança não afeta a autorização de triagem (perfil BraCVAM/Administrador,
  Spec 014) nem a estrutura de `FieldReview`/`Decision` desacoplada de formulário
  (Spec 020).

## Out of Scope

- Alterar a decisão humana de triagem (`execute_triage_decision`) ou introduzir
  qualquer gate automático sobre `FieldReview`.
- Alterar o fluxo de intervenção direta do proponente (Spec 013, User Story 3).
- Reprocessar, migrar ou reclassificar execuções de pré-avaliação históricas.
- Alterar a autorização ou os perfis de acesso à triagem (Spec 014).
- Alterar a configuração de avaliações, critérios, severidades ou o editor de
  templates de formulário (Specs 012 e 013).
- Introduzir mensagem, destaque ou recomendação diferenciada para bloqueios causados
  exclusivamente por critérios indeterminados; a apresentação ao proponente
  permanece genérica, igual à de qualquer outro motivo de bloqueio (Clarifications
  Session 2026-09-18).
