# Feature Specification: Designações e Conflito de Interesse

**Feature Branch**: `feat/process-participant-designations`

**Created**: 2026-08-28

**Status**: Ready for Implementation

**Input**: User description: "Criar a especificação da feature 006 para cobrir RF005, RF006 e a auditoria exigida por RF034, com designação e revogação de participantes por processo, papéis locais, validação de vínculos laboratoriais, declaração imutável de conflito de interesse, bloqueio de tarefas avaliativas ou decisórias e controle de acesso no backend, sem ampliar a complexidade."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Designar e revogar participantes (Priority: P1)

Uma pessoa responsável pela gestão de um processo designa usuários para os papéis locais necessários e, nos papéis laboratoriais, identifica o laboratório representado. A mesma pessoa encerra a designação quando a participação termina.

**Why this priority**: RF005 depende da identificação de quem pode atuar em cada processo. Sem uma designação válida, o backend não consegue conceder responsabilidade local nem limitar o acesso ao processo.

**Independent Test**: Uma pessoa com capacidade de gestão escolhe um processo, designa um usuário ativo para um papel permitido, consulta a designação vigente e a revoga. O sistema aplica cada mudança no pedido seguinte e preserva o ciclo encerrado.

**Acceptance Scenarios**:

1. **Given** um processo existente, um usuário ativo e uma pessoa autorizada a gerir participantes, **When** ela designa o usuário para `group_manager`, **Then** o sistema cria uma designação ativa vinculada ao processo, ao papel, ao usuário e ao responsável pela operação.
2. **Given** um usuário ativo com vínculo vigente a um laboratório ativo, **When** uma pessoa autorizada o designa para `lead_laboratory` ou `participating_laboratory` e informa esse laboratório, **Then** o sistema registra o usuário e o laboratório no mesmo ciclo de designação.
3. **Given** um usuário sem vínculo vigente com o laboratório informado, **When** uma pessoa autorizada tenta criar uma designação laboratorial, **Then** o sistema rejeita a operação sem criar designação nem conceder acesso.
4. **Given** uma designação ativa para o mesmo processo, usuário e papel, **When** uma pessoa tenta repetir a designação, **Then** o sistema rejeita a duplicidade, inclusive quando as solicitações concorrem.
5. **Given** uma designação ativa, **When** uma pessoa autorizada a revoga, **Then** o sistema encerra seu efeito no pedido seguinte e mantém o ciclo disponível no histórico.
6. **Given** uma pessoa sem capacidade global de gestão nem designação ativa de `group_manager` naquele processo, **When** ela tenta designar ou revogar um participante, **Then** o backend nega a ação sem alterar ou expor dados protegidos.
7. **Given** uma pessoa com capacidade global de gestão e um identificador de processo inexistente, **When** ela tenta designar um participante, **Then** o sistema responde que o processo não foi encontrado sem criar designação ou evento concluído.
8. **Given** uma pessoa com capacidade global de gestão e um processo logicamente excluído, **When** ela tenta designar um participante, **Then** o sistema rejeita a operação como estado inativo sem criar designação ou evento concluído.

---

### User Story 2 - Declarar conflito de interesse (Priority: P2)

Um usuário designado registra a existência ou a ausência de conflito de interesse para sua própria designação. O registro permite que os gestores identifiquem o impedimento e evita que esse usuário execute tarefas avaliativas ou decisórias no processo enquanto houver conflito vigente.

**Why this priority**: RF006 protege a imparcialidade das avaliações e decisões. A declaração precisa produzir efeito na autorização, além de compor o histórico.

**Independent Test**: Um participante com designação ativa declara conflito, tenta executar uma ação avaliativa do processo e recebe a negação. Um gestor vê o sinal de conflito, e o participante registra depois uma nova declaração sem conflito sem apagar o registro anterior.

**Acceptance Scenarios**:

1. **Given** uma designação ativa pertencente ao usuário autenticado, **When** ele declara `has_conflict=true` com justificativa, **Then** o sistema registra uma nova declaração imutável com o momento da submissão e sinaliza o conflito aos gestores do processo.
2. **Given** uma designação pertencente a outro usuário, **When** uma pessoa tenta declarar conflito em nome do titular, **Then** o backend nega a ação sem criar declaração.
3. **Given** um usuário com conflito vigente em qualquer designação ativa do processo, **When** ele tenta iniciar, executar, concluir ou decidir uma tarefa avaliativa ou decisória nesse processo, **Then** o backend bloqueia a ação.
4. **Given** um usuário com mais de uma designação ativa no processo e uma delas com conflito vigente, **When** ele tenta usar outro papel para executar uma tarefa avaliativa ou decisória, **Then** o backend mantém o bloqueio.
5. **Given** uma declaração vigente com conflito, **When** o próprio titular registra nova declaração `has_conflict=false` para a mesma designação, **Then** o sistema preserva ambas as declarações e usa a mais recente para avaliar o conflito daquela designação.
6. **Given** uma designação revogada, **When** o antigo titular tenta acrescentar uma declaração, **Then** o sistema rejeita a submissão e conserva o histórico existente.

---

### User Story 3 - Consultar participantes e histórico (Priority: P3)

Uma pessoa responsável pela gestão do processo consulta os participantes atuais, os conflitos vigentes e o histórico de designações, revogações e declarações. Um participante consulta somente suas próprias designações e declarações.

**Why this priority**: RF034 exige que a equipe consiga identificar responsáveis, datas e mudanças. A separação entre estado atual e histórico evita que uma revogação ou nova declaração apague o contexto anterior.

**Independent Test**: Criar, revogar e recriar uma designação, registrar duas declarações e consultar o estado atual e a sequência histórica com uma pessoa autorizada.

**Acceptance Scenarios**:

1. **Given** um processo com designações ativas e revogadas, **When** uma pessoa com capacidade de gestão lista os participantes atuais, **Then** o sistema retorna somente os ciclos ativos e indica os conflitos vigentes.
2. **Given** o mesmo processo, **When** a pessoa autorizada consulta o histórico, **Then** o sistema apresenta os ciclos ativos e encerrados, as declarações em ordem determinística e a autoria e o momento de cada ação concluída.
3. **Given** um participante sem capacidade de gestão, **When** ele consulta suas designações e declarações, **Then** o sistema retorna somente os registros pertencentes a esse usuário no processo.
4. **Given** uma pessoa sem participação nem capacidade de gestão, **When** ela tenta listar participantes ou consultar o histórico, **Then** o backend nega o acesso sem confirmar o conteúdo protegido.
5. **Given** uma designação, revogação ou declaração concluída, **When** uma pessoa autorizada consulta a trilha do processo, **Then** encontra um evento imutável com o processo, a ação, o responsável, o alvo, o resultado, o momento e o contexto relevante.

### Edge Cases

- Duas pessoas tentam criar ao mesmo tempo a mesma designação ativa. O sistema mantém um único ciclo ativo e não registra uma segunda mudança concluída.
- Uma pessoa tenta designar um usuário inativo ou excluído. O sistema rejeita a operação.
- Um usuário ou laboratório perde o estado ativo depois da designação. A designação permanece no histórico, mas deixa de conceder acesso enquanto a condição de elegibilidade não estiver vigente.
- Um vínculo institucional laboratorial é encerrado depois da designação. O usuário perde o acesso derivado do papel laboratorial no pedido seguinte, sem alteração retroativa do histórico.
- Uma pessoa informa laboratório em um papel não laboratorial ou omite o laboratório em `lead_laboratory` ou `participating_laboratory`. O sistema rejeita a combinação.
- Um usuário possui vínculos com vários laboratórios. A designação laboratorial identifica um único laboratório por ciclo e exige vínculo vigente com ele.
- Um participante envia declarações sucessivas. O sistema mantém todas e calcula o estado atual pela declaração mais recente de cada designação ativa.
- Um usuário possui conflito vigente em uma designação e ausência de conflito em outra. O conflito vigente prevalece para tarefas avaliativas ou decisórias do processo.
- Uma designação é revogada e o mesmo usuário recebe depois o mesmo papel. O sistema cria outro ciclo, preserva as declarações anteriores e não as transfere para a nova designação.
- Uma tentativa negada ou inválida termina sem mudança. O sistema não registra evento de ação concluída nem deixa alteração parcial.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE exigir identidade autenticada para consultar dados protegidos, designar, revogar ou declarar conflito de interesse.
- **FR-002**: O sistema DEVE manter designações locais vinculadas a uma única instância de processo, um usuário ativo e um dos seguintes papéis: `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`, `lead_laboratory`, `participating_laboratory` ou `proponent`.
- **FR-003**: Uma designação nos papéis `lead_laboratory` ou `participating_laboratory` DEVE identificar um laboratório ativo e um usuário com vínculo institucional ativo nesse laboratório.
- **FR-004**: Uma designação nos demais papéis NÃO DEVE conter laboratório. Esta feature NÃO DEVE criar designação de laboratório sem identificar o usuário responsável.
- **FR-005**: O sistema DEVE rejeitar processo, usuário, papel, laboratório ou vínculo institucional ausente, inativo ou incompatível antes de criar a designação. Para esta feature, uma instância de processo está ativa enquanto não tiver sido logicamente excluída; seu estado de fase ou encerramento não cria outra restrição de designação.
- **FR-006**: O sistema DEVE impedir mais de uma designação ativa para a mesma combinação de processo, usuário e papel, mesmo em solicitações concorrentes e ainda que um laboratório diferente seja informado.
- **FR-007**: A revogação DEVE encerrar o efeito da designação sem apagar nem reativar o ciclo. Uma nova designação equivalente DEVE criar outro ciclo rastreável.
- **FR-008**: A perda de atividade do usuário, do laboratório ou do vínculo institucional DEVE retirar no pedido seguinte o acesso que dependia dessa designação, sem apagar o histórico.
- **FR-009**: O sistema DEVE preservar a designação de proponente criada no início do processo e tratá-la como o papel local `proponent`, sem duplicar nem invalidar processos existentes.
- **FR-010**: O sistema DEVE permitir designar e revogar somente a uma pessoa com capacidade global de gestão de participantes ou com designação ativa de `group_manager` na mesma instância de processo.
- **FR-011**: A capacidade global de gestão DEVE alcançar todas as instâncias de processo; a designação de `group_manager` DEVE conceder gestão somente no processo correspondente. O perfil protegido de Administrador DEVE receber a capacidade global na carga inicial.
- **FR-012**: O backend DEVE reavaliar a capacidade de gestão e as designações vigentes em cada pedido protegido. Uma revogação ou inativação DEVE produzir efeito sem exigir nova autenticação.
- **FR-013**: O sistema DEVE oferecer operações para listar participantes atuais de um processo, adicionar uma designação, revogar uma designação e consultar o histórico de participantes.
- **FR-014**: Uma pessoa com capacidade de gestão DEVE consultar o estado atual e o histórico completo do processo. Um participante sem essa capacidade DEVE consultar somente as próprias designações e declarações. Outras pessoas NÃO DEVEM receber esses dados.
- **FR-015**: O sistema DEVE permitir que somente o usuário identificado em uma designação ativa registre uma declaração de conflito para esse ciclo.
- **FR-016**: Cada declaração DEVE registrar `has_conflict`, uma justificativa textual não vazia e o momento atribuído pela plataforma.
- **FR-017**: As declarações DEVEM formar um histórico imutável. O sistema NÃO DEVE alterar nem excluir uma declaração e DEVE aceitar uma nova declaração para atualizar o estado vigente da mesma designação ativa.
- **FR-018**: A declaração mais recente de cada designação ativa DEVE definir seu estado atual. A ausência de declaração NÃO DEVE bloquear tarefas nesta feature.
- **FR-019**: Um usuário DEVE ser considerado em conflito no processo quando ao menos uma de suas designações ativas possuir declaração vigente com `has_conflict=true`.
- **FR-020**: Enquanto houver conflito vigente, o backend DEVE impedir que o usuário inicie, execute, conclua ou decida tarefas avaliativas ou decisórias naquela instância, mesmo que outra designação ativa pudesse autorizar a ação.
- **FR-021**: Para o efeito desta feature, ações executadas sob `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator` ou `peer_reviewer` DEVEM receber a verificação de conflito. A feature NÃO DEVE reclassificar tarefas do proponente nem tarefas operacionais dos laboratórios como avaliativas ou decisórias.
- **FR-022**: O bloqueio por conflito NÃO DEVE revogar a designação, apagar tarefas nem alterar o histórico. Uma nova declaração sem conflito ou o encerramento do ciclo correspondente DEVE retirar apenas o bloqueio que dependia desse ciclo.
- **FR-023**: A lista de participantes para gestores DEVE sinalizar quais usuários possuem conflito vigente. A justificativa DEVE ficar restrita ao próprio titular e às pessoas com capacidade de gestão do processo.
- **FR-024**: O sistema DEVE registrar um evento na trilha `audit_events` para cada designação, revogação e declaração de conflito concluída.
- **FR-025**: Cada evento DEVE identificar a instância do processo, o tipo de ação, o responsável autenticado, o ciclo de designação, o usuário designado, o papel, o laboratório quando existir, o resultado, o momento e os dados relevantes da mudança. O evento DEVE identificar a atividade, a execução e a origem quando esses contextos existirem. O evento de declaração DEVE incluir o valor declarado e a justificativa.
- **FR-026**: Os eventos de `audit_events` e as declarações de conflito DEVEM permanecer imutáveis e disponíveis somente em consultas históricas autorizadas.
- **FR-027**: A consulta histórica DEVE ordenar ciclos, declarações e eventos de forma determinística e distinguir o estado atual dos registros encerrados.
- **FR-028**: As operações públicas de designar, revogar e declarar conflito DEVEM aplicar a proteção de origem já exigida para a autenticação por cookie. Esta feature não altera a proteção de origem das rotas legadas de triagem.
- **FR-029**: O sistema DEVE preservar os contratos aprovados de cadastro, autenticação, RBAC, vínculos institucionais e submissão e triagem, salvo a adaptação necessária para reconhecer os papéis locais canônicos desta feature.
- **FR-030**: A evolução dos dados DEVE preservar processos, designações, tarefas e eventos existentes, sem criar participantes, vínculos laboratoriais ou declarações implícitas.
- **FR-031**: A feature DEVE validar os contratos de designação, revogação, consulta e declaração; as fronteiras de autorização; a imutabilidade e a exposição do histórico; o bloqueio por conflito; as regras laboratoriais; a duplicidade concorrente; a preservação dos dados existentes; e a regressão das features 001 a 005.
- **FR-032**: Esta feature NÃO DEVE criar novos papéis, matrizes de tarefas de fases futuras, notificações assíncronas, revisão gerencial de declarações, cegamento, seleção de laboratórios para ensaios ou regras de conflito fora da instância designada.

### Key Entities

- **Instância de processo**: Processo específico no qual os participantes recebem responsabilidades locais e no qual a autorização contextual produz efeito.
- **Designação**: Ciclo que relaciona processo, usuário, papel local e, nos papéis laboratoriais, laboratório. Mantém responsável e momento da atribuição, estado vigente ou revogado e referência às declarações.
- **Participante designado**: Usuário ativo que possui uma designação local. Um mesmo usuário pode acumular papéis distintos no processo.
- **Laboratório representado**: Laboratório ativo associado a uma designação laboratorial por meio de um vínculo institucional vigente do participante.
- **Declaração de conflito de interesse**: Registro imutável de existência ou ausência de conflito, com justificativa, momento e vínculo a um único ciclo de designação.
- **Estado de conflito do participante**: Resultado corrente calculado a partir da declaração mais recente de cada designação ativa do usuário no processo.
- **Tarefa protegida por conflito**: Tarefa avaliativa ou decisória cuja execução exige a verificação do estado de conflito do participante.
- **Evento de auditoria do processo**: Registro imutável de uma designação, revogação ou declaração concluída, com autoria, momento, resultado e contexto suficiente para reconstruir a mudança.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários de aceitação, somente uma pessoa com capacidade global de gestão ou uma designação ativa de `group_manager` no processo conclui uma designação ou revogação.
- **SC-002**: Em 100% dos cenários com processo, usuário, papel, laboratório ou vínculo institucional ausente, inativo ou incompatível, o sistema rejeita a designação sem criar estado parcial.
- **SC-003**: Em 100% dos cenários de duplicidade sequencial ou concorrente, existe no máximo uma designação ativa para o mesmo processo, usuário e papel.
- **SC-004**: Em 100% dos cenários com conflito vigente, o usuário não consegue executar nenhuma tarefa avaliativa ou decisória do processo, inclusive por outro papel ativo.
- **SC-005**: Em 100% das declarações aceitas, somente o titular da designação atua como declarante, e o histórico preserva o valor, a justificativa e o momento sem alteração do registro anterior.
- **SC-006**: Em 100% das designações, revogações e declarações concluídas, uma pessoa autorizada localiza na trilha o processo, a ação, o responsável, o alvo, o resultado, o momento e o contexto relevante.
- **SC-007**: Em validação manual cronometrada, uma pessoa autorizada designa um participante, confirma seu estado e o revoga em até 2 minutos.
- **SC-008**: Em um processo com até 200 ciclos de designação e declarações, pelo menos 95% das consultas de participantes e histórico apresentam o resultado ao usuário em até 2 segundos.
- **SC-009**: Em 100% dos cenários de visibilidade, gestores acessam o histórico completo, participantes acessam somente os próprios registros e pessoas externas não recebem o conteúdo protegido.
- **SC-010**: Todos os cenários aprovados das features 001 a 005 continuam válidos após a inclusão das designações e dos conflitos de interesse.

## Assumptions

- **CONFIRMADO, fonte oficial**: RF005 exige a designação de gestores, laboratórios, avaliadores ad hoc, revisores, especialistas e analistas para cada processo de validação, conforme `docs/plano-de-trabalho-fase-ii.md`.
- **CONFIRMADO, fonte oficial**: RF006 exige que participantes registrem a existência ou a ausência de conflito de interesse. RF034 exige logs e auditoria das ações da plataforma.
- **DIVERGÊNCIA REGISTRADA**: RF005 cita especialistas, mas a lista de papéis fornecida pelo usuário para a feature 006 não contém esse papel. Pela precedência da instrução atual, esta especificação limita o catálogo aos oito papéis informados e mantém `specialist` fora do escopo.
- **DECISÃO TÉCNICA REGISTRADA**: O backend trata vínculos institucionais e designações como dados de autorização, e o conflito deve afetar elegibilidade e acesso conforme regras aprovadas, conforme `docs/planejamento/gestao-de-usuarios.md`.
- **DECISÃO TÉCNICA REGISTRADA**: O processo mantém atribuições locais separadas do RBAC global; as atividades podem limitar seus executores por papel; a trilha de auditoria preserva histórico imutável, conforme as seções 14 e 26 de `docs/planejamento/PIVMA_diretrizes_especificacoes.md`.
- **CONFIRMADO, constituição 1.0.0**: O backend valida autorização e preserva rastreabilidade. Controles de interface não concedem acesso.
- **CONFIRMADO, implementação atual**: `ProcessInstance` já se relaciona com `Assignment` e `AuditEvent`; `Assignment` identifica processo, usuário e papel e impede duplicidade ativa; `Task` aceita papel ou usuário; `AuditEvent` aceita contexto por processo; `UserInstitutionalAffiliation` representa vínculos institucionais ativos. `src/pivma/core/authorization.py` consulta permissões e vínculos vigentes.
- **CONFIRMADO, implementação atual**: A criação de processo designa o criador como `PROPONENT`. Esta feature preserva esse comportamento e adota a chave canônica `proponent` indicada pelo usuário.
- **DECISÃO EXPLÍCITA DESTA FEATURE**: Os papéis suportados são somente `group_manager`, `study_manager`, `statistician`, `adhoc_evaluator`, `peer_reviewer`, `lead_laboratory`, `participating_laboratory` e `proponent`.
- **PROPOSTA delimitadora**: `lead_laboratory` e `participating_laboratory` identificam um usuário responsável e o laboratório que ele representa. A feature não cria participação para uma entidade laboratorial sem usuário designado.
- **PROPOSTA delimitadora**: A plataforma aceita mais de um usuário por papel e mais de um laboratório participante. O único limite desta feature é a ausência de duplicidade ativa para o mesmo processo, usuário e papel.
- **DECISÃO EXPLÍCITA DESTA FEATURE**: Uma instância de processo logicamente excluída é inativa para novas designações. `status`, `closed_at` e as transições de fase não recebem semântica adicional nesta feature.
- **PROPOSTA delimitadora**: A declaração não constitui pré-condição para qualquer tarefa. A declaração mais recente de cada ciclo ativo determina o estado corrente, e qualquer conflito vigente prevalece sobre declarações sem conflito em outros papéis.
- **PROPOSTA delimitadora**: A sinalização aos gestores ocorre no estado consultável dos participantes. Alertas assíncronos e integrações de mensageria ficam fora do escopo.
- **PROPOSTA delimitadora**: A feature registra somente ações concluídas em `audit_events`. Tentativas negadas ou inválidas não geram um evento de mudança concluída.

## Scope and Traceability

| Fonte | Natureza | Cobertura nesta feature |
|---|---|---|
| RF005 | Requisito oficial | Designação e revogação de participantes por instância, consulta do estado atual e histórico, limitada aos oito papéis definidos pelo usuário para esta feature. |
| RF006 | Requisito oficial | Declarações de existência ou ausência de conflito, autoria exclusiva do titular e efeito na autorização de tarefas avaliativas ou decisórias. |
| RF034 | Requisito oficial transversal | Eventos imutáveis de designação, revogação e declaração com autoria, momento, resultado e contexto. |
| Backlog de Gestão de Usuários | Decisão técnica registrada | Designações e vínculos como dados de autorização e conflito como condição de elegibilidade e acesso. |
| Diretrizes, seções 14 e 26 | Decisão técnica registrada | Papéis locais por processo, vínculo com atividades e trilha imutável separada do estado atual. |
| Feature 003 | Especificação e implementação existentes | Reutiliza identidade, perfis e permissões globais para a capacidade administrativa. |
| Feature 004 | Especificação e implementação existentes | Evolui `Assignment` e integra a verificação às tarefas e aos eventos do processo, preservando o fluxo de submissão e triagem. |
| Feature 005 | Especificação e implementação existentes | Usa somente vínculos institucionais vigentes para validar designações laboratoriais. |
| Observações e pendências | Controle de lacunas | A lista de papéis desta feature resolve somente o escopo de RF005 e RF006; não define a lista canônica de papéis para outros módulos nem regras futuras de cegamento. |

## Required Technical Coverage for Planning

Esta seção registra os pontos que o plano deve resolver a partir do código existente, sem criar estruturas paralelas.

| Área | Cobertura necessária |
|---|---|
| Dados | Evoluir o ciclo de `Assignment` para representar os papéis e o contexto laboratorial aprovados; manter declarações imutáveis vinculadas ao ciclo; preservar processos e atribuições existentes. |
| Autorização | Combinar a capacidade global de gestão, a designação local de `group_manager`, o vínculo institucional vigente e o bloqueio de conflito no pedido atual. |
| Tarefas | Aplicar o bloqueio antes de ações avaliativas ou decisórias sem alterar os fluxos e papéis fora desta feature. |
| Auditoria | Usar `AuditEvent` para designação, revogação e declaração com o contexto exigido e sem permitir alteração do histórico. |
| Interface | Disponibilizar listagem de participantes, criação e revogação de designação, submissão da própria declaração e consulta histórica conforme a visibilidade aprovada. |
| Compatibilidade | Reconciliar as chaves canônicas desta feature com os registros de proponente e tarefas existentes sem mudar os contratos aprovados da feature 004. |
| Testes | Cobrir contratos de entrada e saída, API, autorização e exposição, persistência e concorrência, evolução e preservação de dados e regressão. Cada teste deve focar um comportamento observável. |

## Out of Scope

- Criação ou administração dos perfis globais do RBAC e dos catálogos institucionais da feature 005.
- Papéis diferentes dos oito listados nesta especificação e cardinalidades adicionais por papel.
- Designação de laboratório sem usuário responsável ou concessão automática de acesso a todos os usuários vinculados a um laboratório.
- Obrigatoriedade de declarar conflito antes de iniciar tarefas, análise ou aprovação gerencial da declaração e sanções fora do processo.
- Novos fluxos, fases, tipos de tarefa ou matrizes completas de responsabilidade para etapas posteriores.
- Notificações assíncronas, e-mail, mensageria e escalonamento de alertas.
- Seleção de laboratórios para ensaios, protocolos interlaboratoriais, cegamento, códigos cegos e revelação de identidades.
- Conflitos institucionais ou organizacionais sem vínculo com um usuário designado e uma instância de processo.
- Retificação ou exclusão de declarações e eventos; correções exigem novo registro quando permitido.
