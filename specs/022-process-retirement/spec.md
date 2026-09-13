# Feature Specification: Exclusão, Cancelamento e Arquivamento de Processos

**Feature Branch**: `022-process-retirement`

**Created**: 2026-09-12

**Status**: Implemented (em revisão pós-clarificação — ver Clarifications 2026-09-13)

**Input**: User description: "Issue #14: rascunhos nunca submetidos devem sofrer exclusão física do agregado e de seus documentos; processos que entraram no pipeline de validação devem usar cancelamento e arquivamento, sem complexidade desnecessária e com contrato simples para o front-end."

## Contexto e classificação

- **CONFIRMADO**: a issue #14 solicita uma forma de interromper, arquivar ou excluir uma instância de processo, com autorização, tratamento das operações pendentes, preservação de integridade e auditoria.
- **CONFIRMADO**: instâncias de processo possuem exclusão lógica, estado macro, momento e motivo de encerramento; tarefas, atividades, execuções, formulários, documentos e eventos permanecem vinculados ao processo.
- **CONFIRMADO por decisão do responsável da demanda (revisão 2026-09-13)**: a distinção entre "rascunho nunca submetido" e "processo já em pipeline" deixa de determinar exclusão física versus cancelamento. Existe uma única operação de exclusão lógica (o registro é marcado como excluído, com autor e momento, e nunca removido), aceita em qualquer estado não-terminal, independentemente do histórico de submissão.
- **CONFIRMADO por decisão do responsável da demanda (revisão 2026-09-13)**: a exclusão é permitida ao proponente efetivo do processo (autorização local) OU a um usuário com perfil global Administrador ou BraCVAM (autorização global), sem exigir ausência de submissão formal.
- **CONFIRMADO por decisão do responsável da demanda (revisão 2026-09-13)**: a exclusão NÃO remove fisicamente o agregado nem os documentos armazenados em disco; ela marca o processo como excluído (autor e momento registrados) e transiciona `process.status` para o estado terminal já existente `CANCELLED`, reaproveitando a mesma cascata de cancelamento de trabalho subordinado que a feature já usava.
- **CONFIRMADO por decisão do responsável da demanda (revisão 2026-09-13)**: `ARCHIVED` continua organizando processos históricos e só pode suceder estados terminais (`CLOSED` ou `CANCELLED`); um processo soft-deletado (agora `CANCELLED`) pode ser arquivado normalmente, sem regra especial.
- **CONFIRMADO por decisão do responsável da demanda (revisão 2026-09-13)**: o arquivamento continua exigindo a permissão `triage.review`, respeitando conflito de interesse; quem detém essa permissão é uma decisão de RBAC externa a esta spec (ver Feature 023).
- **CONFIRMADO**: a grafia canônica é `CANCELLED`; não serão introduzidos `CANCELED` ou `DELETED`.
- **DECISÃO TÉCNICA REGISTRADA (revisão 2026-09-13)**: a simplificação dos cargos globais da plataforma (Padrão/Admin/BraCVAM) é uma pré-condição externa desta spec, não parte do seu escopo — ver Feature 023 e Clarifications abaixo.

## Clarifications

### Session 2026-09-13

- Q: A redução dos cargos globais (Padrão/Admin/BraCVAM, com Admin e BraCVAM ganhando todas as permissões) deve ser absorvida dentro do escopo da Spec 022, ou tratada como uma spec própria da qual a 022 passa a depender? → A: Opção B — spec própria (`023-rbac-global-roles`); a 022 permanece restrita ao ciclo de vida de processos e apenas passa a exigir, como pré-condição externa, que a permissão de revisão usada por esta feature seja outorgada somente a Admin/BraCVAM.
- Q: Os endpoints `/withdrawal` e `/cancellation` somem em favor de um único `DELETE`; isso torna `CANCELLED` órfão como status do processo, e o `DELETE` deve ser aceito em qualquer estado? → A: Não fica órfão — `CANCELLED` continua sendo o status terminal de subordinados (fases/atividades/execuções/tarefas) independente destes dois endpoints, e o `DELETE` unificado reaproveita a mesma cascata de cancelamento (`_cancel_process_locked`) para também definir `process.status = CANCELLED`, apenas removendo a exigência de submissão formal prévia. Isso mantém `ARCHIVE` com a checagem inalterada (`status in {CLOSED, CANCELLED}`) e torna `DELETE` naturalmente não-idempotente sobre processos já terminais (`CLOSED`/`CANCELLED`/`ARCHIVED`), sem precisar de uma regra nova baseada em `deleted_at`.
- Q: No soft-delete unificado, os anexos em `ATTACHMENTS_DIR/{process_id}/` devem ser preservados em disco ou continuar sendo removidos fisicamente para rascunhos nunca submetidos? → A: Opção A — preservar sempre os arquivos em disco no soft-delete, sem exceção por histórico de submissão. A exclusão física de rascunhos deixa de existir como comportamento: `DELETE` nunca mais apaga arquivos do disco, apenas marca `deleted_at`/`deleted_by` e oculta o processo das visões padrão.
- Q: O evento de auditoria do `DELETE` unificado deve usar um único `event_type` para todos os casos, ou continuar distinguindo proponente vs. Admin/BraCVAM? → A: Opção B — um único `event_type` novo, `PROCESS_DELETED`, para toda chamada ao `DELETE`, independente do ator; a distinção de quem agiu fica implícita comparando `AuditEvent.user_id` com o proponente efetivo do processo, sem precisar de um tipo de evento por ator.
- Q: O listener global de soft-delete (`do_orm_execute` + `with_loader_criteria`) deve cobrir todos os modelos `AuditMixin`, ou só `ProcessInstance`? → A: Opção A — listener global em `database.py` cobrindo todo `AuditMixin`, aplicado a toda a base (fora do escopo desta feature isoladamente; qualquer entidade soft-deletada em qualquer módulo passa a ser filtrada por padrão em toda consulta SELECT via ORM, com opção explícita de bypass por `execution_options(skip_soft_delete_filter=True)`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Excluir (soft-delete) um processo (Priority: P1)

Como proponente efetivo de um processo, ou como administrador da plataforma (Admin/BraCVAM), quero excluir um processo em qualquer estado não-terminal, para interromper e ocultá-lo das visões padrão sem perder seu histórico, documentos ou trilha de auditoria.

**Why this priority**: Unifica em uma única operação os três casos antes fragmentados (rascunho descartável, cancelamento administrativo e desistência do proponente), simplificando o contrato para o front-end e reduzindo a superfície de autorização.

**Independent Test**: Criar um processo em cada estágio (nunca submetido, em validação com trabalho pendente, submissão devolvida para correção); excluí-lo como proponente e, em outro caso, como Admin/BraCVAM; confirmar que o processo fica marcado como excluído (autor e momento registrados), `status = CANCELLED`, trabalho pendente cancelado em cascata, documentos preservados em disco e o processo ausente de qualquer listagem padrão.

**Acceptance Scenarios**:

1. **Given** um processo em qualquer estado não-terminal pertencente a um proponente efetivo, **When** esse proponente solicita a exclusão, **Then** o sistema marca o processo como excluído (registrando autor e momento), define `status = CANCELLED`, cancela em cascata o trabalho subordinado ainda não terminal e preserva os documentos em disco.
2. **Given** qualquer processo em estado não-terminal, **When** um usuário com perfil global Admin ou BraCVAM solicita a exclusão, **Then** a mesma operação é aceita independentemente de quem seja o proponente do processo.
3. **Given** um processo de outro proponente, **When** um usuário comum (que não é o proponente efetivo nem tem perfil Admin/BraCVAM) tenta excluí-lo, **Then** a operação é negada e nenhum dado é alterado.
4. **Given** um processo já `CLOSED`, `CANCELLED` ou `ARCHIVED`, **When** alguém solicita sua exclusão, **Then** a transição é rejeitada de forma previsível e o estado existente é preservado.
5. **Given** tarefas, atividades, execuções humanas ou automáticas ainda pendentes no processo, **When** a exclusão é concluída, **Then** todas deixam de ser acionáveis e assumem seu estado terminal de cancelamento quando esse estado existir no respectivo ciclo de vida.
6. **Given** formulários pendentes ou já enviados, **When** o processo é excluído, **Then** seus conteúdos são preservados como histórico somente leitura, sem transformar formulários pendentes em enviados e sem excluir registros nem documentos.

---

### User Story 2 - Arquivar um processo terminal (Priority: P2)

Como usuário autorizado na triagem, quero arquivar um processo concluído ou cancelado (incluindo um excluído via soft-delete), para retirá-lo das visões operacionais padrão sem perder sua consulta histórica e sua trilha de auditoria.

**Why this priority**: Arquivamento melhora a organização do volume histórico, mas depende de o processo já ter alcançado um resultado terminal e não é necessário para interromper trabalho ativo.

**Independent Test**: Partir de um processo `CLOSED` e de outro `CANCELLED` (produzido tanto pela exclusão quanto por um estado terminal anterior), arquivá-los e confirmar que deixam de aparecer na visão operacional padrão, continuam recuperáveis por consulta histórica autorizada e preservam todos os vínculos e eventos anteriores.

**Acceptance Scenarios**:

1. **Given** um processo `CLOSED` ou `CANCELLED` (inclusive um excluído via soft-delete), **When** um usuário com `triage.review` o arquiva, **Then** ele passa para `ARCHIVED`, deixa de aparecer nas listagens operacionais padrão e continua disponível em consultas históricas explícitas.
2. **Given** um processo ainda ativo (não-terminal e não excluído), **When** alguém tenta arquivá-lo, **Then** a operação é rejeitada e orienta que o processo seja excluído (se aplicável) antes de ser arquivado.
3. **Given** um processo arquivado, **When** um usuário autorizado consulta seu detalhe ou histórico, **Then** os dados anteriores, o resultado terminal precedente, o responsável e o momento do arquivamento permanecem identificáveis e somente leitura.
4. **Given** um usuário sem `triage.review`, **When** ele tenta arquivar ou consultar processos arquivados, **Then** o acesso é negado sem alteração de estado.

---

### User Story 3 - Front-end conhece as ações permitidas (Priority: P3)

Como integrante da equipe de front-end, quero receber operações permitidas e motivos de recusa estáveis para cada processo consultado, para exibir somente comandos válidos sem reproduzir toda a regra de ciclo de vida no cliente.

**Why this priority**: Reduz divergências entre interface e backend com uma extensão pequena do contrato; a regra continua sendo validada pelo sistema mesmo se o cliente estiver desatualizado.

**Independent Test**: Consultar processos próprios e alheios, em estados ativos, terminais e arquivados, com usuários de perfis distintos, e confirmar que as ações informadas (`DELETE`, `ARCHIVE`) correspondem às operações que o sistema aceita naquele momento.

**Acceptance Scenarios**:

1. **Given** qualquer processo visível, **When** o usuário consulta sua representação, **Then** recebe a condição de ciclo de vida e somente as ações de retirada (`DELETE` e/ou `ARCHIVE`) que pode executar naquele estado e contexto de autorização.
2. **Given** uma tentativa inválida, **When** o sistema a rejeita, **Then** a resposta distingue de forma estável ao menos recurso inexistente ou invisível, falta de autorização e transição incompatível.
3. **Given** um cliente que envia uma ação mesmo sem ela constar como permitida, **When** a solicitação chega ao sistema, **Then** todas as regras são novamente validadas antes de qualquer alteração.

### Edge Cases

- Duas pessoas solicitam simultaneamente ações diferentes sobre o mesmo processo. Apenas uma transição compatível com o estado confirmado é concluída; a outra é rejeitada sem sobrescrever o resultado nem duplicar efeitos.
- Uma execução automática está em andamento no instante da exclusão. O sistema impede que sua conclusão tardia reative, avance ou altere o processo já excluído.
- Uma tarefa ou execução já está concluída quando o processo é excluído. Seu estado histórico não é reescrito; somente itens ainda não terminais são cancelados.
- Um processo excluído (soft-delete) possui formulários, anexos ou outros registros vinculados. Nenhum deles é removido: tanto os registros quanto os documentos em disco permanecem, apenas ocultos das visões padrão.
- Um processo já excluído (status `CANCELLED`, já marcado como excluído) é solicitado para arquivamento. A operação é aceita normalmente, pois `CANCELLED` já satisfaz a pré-condição de `ARCHIVE`; o processo passa a `ARCHIVED` preservando o histórico de exclusão.
- Uma consulta padrão combina filtros de estado com processos arquivados ou excluídos. `ARCHIVED` só aparece quando solicitado explicitamente pela consulta histórica dedicada; processos excluídos (exclusão lógica) não entram em nenhuma consulta padrão desta feature.
- Uma consulta em qualquer módulo do sistema (não somente processos) busca uma entidade sujeita a exclusão lógica que já foi excluída. O mecanismo de filtragem de leitura aplicado a todo o sistema a omite por padrão, a menos que a consulta autorizada solicite explicitamente enxergar registros excluídos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer duas intenções distintas e inequívocas: excluir (soft-delete) um processo e arquivar um processo terminal.
- **FR-002**: A exclusão DEVE ser aceita para um processo em qualquer estado que não seja `CLOSED`, `CANCELLED` ou `ARCHIVED`, independentemente de já ter sido formalmente submetido ou de ser um rascunho nunca submetido.
- **FR-003**: A exclusão DEVE ser lógica: marcar o processo como excluído (registrando autor e momento, no mesmo padrão de auditoria de exclusão já usado por todo o sistema) e definir `process.status = CANCELLED`; a feature NÃO DEVE remover fisicamente o agregado, seus registros vinculados ou seus documentos armazenados, e NÃO DEVE introduzir um estado `DELETED` distinto de `CANCELLED`.
- **FR-004**: Ao excluir, o sistema DEVE cancelar em cascata, sem deixar pendências ativas, as fases, atividades, execuções humanas, execuções automáticas e tarefas ainda não terminais vinculadas ao processo, preservando o estado de itens já concluídos.
- **FR-005**: A exclusão NÃO DEVE alterar o estado de itens já terminais, apagar formulários, anexos, valores, decisões, avaliações ou eventos, nem marcar formulários pendentes como formalmente enviados.
- **FR-006**: A exclusão DEVE ser permitida ao proponente efetivo do processo (autorização local/contextual) OU a um usuário com perfil global Administrador ou BraCVAM (autorização global); nenhum outro usuário DEVE poder excluir o processo.
- **FR-007**: Usuários com a permissão `triage.review` DEVEM poder arquivar processos terminais no escopo desta feature, desde que não possuam conflito de interesse vigente.
- **FR-008**: O arquivamento DEVE ser aceito somente para processos em `CLOSED` ou `CANCELLED` (incluindo um `CANCELLED` produzido por exclusão) e DEVE produzir o estado `ARCHIVED`.
- **FR-009**: Ao arquivar, o sistema DEVE preservar de forma consultável o estado terminal anterior, o momento do arquivamento e o responsável.
- **FR-010**: O arquivamento NÃO DEVE reescrever estados ou dados das entidades subordinadas e NÃO DEVE permitir novas mutações no processo.
- **FR-011**: Depois da exclusão ou do arquivamento, toda tentativa de editar dados, enviar formulários, iniciar ou concluir tarefas, emitir decisões, iniciar ou concluir avaliações ou avançar o fluxo DEVE ser impedida.
- **FR-012**: Uma conclusão tardia de trabalho iniciado antes da exclusão ou do arquivamento NÃO DEVE alterar o processo nem reativar entidades subordinadas.
- **FR-013**: Processos excluídos (exclusão lógica) e processos `ARCHIVED` DEVEM ser omitidos de toda consulta padrão do sistema, através de um mecanismo de filtragem de leitura aplicado globalmente a toda entidade sujeita a exclusão lógica no sistema — não somente a processos —, com possibilidade explícita de bypass por consulta para casos administrativos autorizados.
- **FR-014**: Processos `ARCHIVED` DEVEM poder ser recuperados por consulta histórica explícita e autorizada (`status=ARCHIVED`), restrita a usuários com `triage.review`; esta feature NÃO define uma consulta histórica equivalente dedicada a processos apenas excluídos (soft-delete) além do bypass genérico de infraestrutura do FR-013.
- **FR-015**: A exclusão e o arquivamento NÃO DEVEM exigir justificativa textual; justificativas pertencem às decisões de review.
- **FR-016**: Cada exclusão concluída DEVE gerar um evento de auditoria imutável `PROCESS_DELETED` contendo processo, estado anterior, estado resultante (`CANCELLED`), usuário responsável e momento — o mesmo tipo de evento independentemente de o autor ser o proponente efetivo ou um Admin/BraCVAM agindo administrativamente.
- **FR-017**: Cada arquivamento concluído DEVE gerar um evento de auditoria imutável `PROCESS_ARCHIVED` contendo processo, estado anterior, estado resultante (`ARCHIVED`), usuário responsável e momento.
- **FR-018**: A exclusão e o arquivamento DEVEM concluir mudança de estado, tratamento das entidades subordinadas e auditoria como uma única unidade transacional.
- **FR-019**: Tentativas sem autorização ou com transição inválida NÃO DEVEM provocar alteração parcial, cancelar trabalho subordinado nem criar evento que represente falsamente uma operação concluída.
- **FR-020**: Solicitações concorrentes DEVEM ser resolvidas contra um único estado confirmado, impedindo que uma ação posterior sobrescreva outra já concluída sem registrar o conflito.
- **FR-021**: O sistema DEVE fornecer exatamente dois endpoints REST de ciclo de vida: `DELETE /processes/{id}` (exclusão lógica) e `PATCH /processes/{id}/archive` (arquivamento), sem exigir que o cliente monte alterações diretas de estado. Os endpoints `PATCH .../withdrawal` e `PATCH .../cancellation` da versão anterior desta feature NÃO DEVEM ser mantidos.
- **FR-022**: A representação consultável de um processo DEVE informar suas operações permitidas para o usuário atual, restritas a `DELETE` e `ARCHIVE`; essa informação é auxiliar e NÃO substitui a autorização no momento da operação.
- **FR-023**: As rejeições DEVEM usar categorias estáveis e distinguíveis para recurso inexistente ou invisível, falta de autorização e transição incompatível, permitindo tratamento previsível pelo front-end.
- **FR-024**: O mecanismo de filtragem de exclusão lógica DEVE ser aplicado de forma centralizada (não repetido rota a rota), cobrindo toda entidade sujeita a exclusão lógica em todo o sistema, com uma forma explícita de bypass por consulta para os casos que precisem enxergar registros excluídos logicamente.
- **FR-025**: A entrega DEVE incluir uma demonstração interativa desacoplada do núcleo da aplicação, registrada no catálogo central de demonstrações e operando contra o comportamento real do backend.
- **FR-026**: A entrega DEVE incluir uma massa de dados mínima e repetível que permita demonstrar ao menos: processo excluível pelo proponente, processo excluível por Admin/BraCVAM, processo concluído arquivável e tentativa bloqueada.
- **FR-027**: A feature NÃO DEVE criar restauração, reabertura, desarquivamento, exclusão em massa, agendamento de exclusão ou arquivamento, redesenho geral da matriz de papéis da plataforma (tratado pela Feature 023) ou novos endpoints facilitadores exclusivos para a demonstração.

### Scope Boundaries

**Incluído**:

- Exclusão lógica (soft-delete) de processo em qualquer estado não-terminal, pelo proponente efetivo ou por um usuário com perfil global Admin/BraCVAM.
- Preservação de documentos em disco em toda exclusão, sem exceção por histórico de submissão.
- Arquivamento de processo concluído ou cancelado (incluindo um excluído via soft-delete).
- Encerramento consistente do trabalho pendente, bloqueio de mutações e auditoria (`PROCESS_DELETED`, `PROCESS_ARCHIVED`).
- Mecanismo de filtragem de leitura aplicado globalmente a toda entidade sujeita a exclusão lógica no sistema, com bypass explícito por consulta.
- Consulta explícita de históricos arquivados e indicação das ações permitidas (`DELETE`, `ARCHIVE`) ao front-end.
- Demonstração interativa e seed mínimo conectados ao comportamento real.

**Fora do escopo**:

- Exclusão física de qualquer processo — o soft-delete substitui integralmente o comportamento de exclusão física da versão anterior desta feature.
- Estado `DELETED` ou grafias alternativas de `CANCELLED`.
- Arquivamento de processo ainda ativo (não-terminal e não excluído).
- Endpoints REST dedicados de desistência (`/withdrawal`) e cancelamento administrativo (`/cancellation`) — descontinuados nesta revisão em favor de um único `DELETE`.
- Restauração, reabertura, desarquivamento, retomada ou clonagem de processo.
- Uma consulta histórica de API dedicada a processos apenas excluídos (soft-delete), além do bypass genérico de infraestrutura (ver FR-014).
- Operações em massa, retenção automática, expurgo ou agendamento.
- Redesenho geral do motor de estados ou da matriz de papéis da plataforma. A simplificação dos cargos globais para Padrão/Admin/BraCVAM é tratada pela Spec 023 (dependência externa; ver Clarifications 2026-09-13 e Dependencies and Traceability).

### Key Entities *(include if feature involves data)*

- **Instância de processo**: sujeita a exclusão lógica (fica marcada como excluída, com autor e momento registrados) em qualquer estado não-terminal; `status` distingue o resultado (`CANCELLED` para excluído, `CLOSED` para concluído normalmente, `ARCHIVED` para organizado historicamente).
- **Trabalho subordinado**: fases, atividades, tarefas e execuções humanas ou automáticas vinculadas ao processo; itens pendentes são interrompidos na exclusão e itens históricos são preservados.
- **Formulário e conteúdo vinculado**: dados de elaboração ou submissão preservados como histórico; tornam-se somente leitura após exclusão ou arquivamento.
- **Evento de auditoria**: evidência imutável de exclusão (`PROCESS_DELETED`) ou arquivamento (`PROCESS_ARCHIVED`), com autor, momento e transição produzida; o tipo do evento não distingue o ator, que é inferido comparando `user_id` com o proponente efetivo do processo.
- **Operação permitida**: indicação contextual de `DELETE` ou `ARCHIVE`, derivada do estado, de o processo já estar excluído ou não, e da autorização do usuário atual.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das exclusões autorizadas (proponente efetivo ou Admin/BraCVAM), o processo e todo trabalho subordinado ainda não terminal deixam de ser acionáveis, o processo some de toda listagem padrão, e nenhum documento armazenado é removido do disco.
- **SC-002**: Em 100% das tentativas de exclusão por um usuário que não é o proponente efetivo nem tem perfil Admin/BraCVAM, a operação é impedida e nenhum dado é alterado.
- **SC-003**: Em 100% das exclusões válidas, itens já concluídos e conteúdos vinculados permanecem inalterados e consultáveis conforme autorização.
- **SC-004**: Em 100% das tentativas de mutação posteriores a `CANCELLED` (por exclusão) ou `ARCHIVED`, o processo não avança e nenhum dado operacional é alterado.
- **SC-005**: Em 100% dos arquivamentos válidos, o processo sai da visão operacional padrão e permanece recuperável por consulta histórica explícita com seu resultado terminal anterior identificável.
- **SC-006**: Em 100% das tentativas sem autorização, com transição incompatível ou disputa concorrente perdida, não ocorre alteração parcial nem evento de sucesso falso.
- **SC-007**: Em 100% das exclusões e arquivamentos concluídos, uma pessoa autorizada consegue identificar ação, processo, estado anterior, resultado, responsável e momento na trilha de auditoria (`PROCESS_DELETED`/`PROCESS_ARCHIVED`), inferindo o papel do ator ao comparar o responsável com o proponente efetivo do processo.
- **SC-008**: Na demonstração conectada ao backend real, uma pessoa autorizada consegue identificar a ação disponível e concluir a exclusão ou o arquivamento de um processo aplicável em até 1 minuto por caso.
- **SC-009**: Em 100% dos processos amostrados nos estados ativo, concluído, excluído e arquivado, as ações informadas (`DELETE`, `ARCHIVE`) ao front-end coincidem com as ações efetivamente aceitas pelo sistema.
- **SC-010**: A massa mínima de demonstração pode ser reaplicada sem criar estados contraditórios e cobre os quatro casos exigidos em FR-026.
- **SC-011**: Em 100% das consultas de leitura padrão sobre qualquer entidade sujeita a exclusão lógica no sistema, um registro excluído é omitido por padrão, exceto quando a consulta usa explicitamente o mecanismo de bypass administrativo.

## Assumptions

- A autorização de exclusão reaproveita as verificações já existentes na plataforma de perfil global (Administrador/BraCVAM) e de proponente efetivo do processo; esta spec não cria nenhuma infraestrutura nova de RBAC.
- A permissão `triage.review` continua sendo a autoridade de revisão para arquivamento nesta entrega. Quem detém essa permissão (hoje potencialmente perfis além de Admin/BraCVAM) é uma decisão de RBAC tratada pela Feature 023, não por esta spec.
- Um processo excluído (soft-delete, `status = CANCELLED`) pode ser posteriormente arquivado sem regra especial, pois já satisfaz a pré-condição existente de `ARCHIVE`.
- **INFERÊNCIA**: não foi confirmado se uma trilha administrativa dedicada de consulta a processos soft-deletados (diferente de `ARCHIVED`) é necessária; por ora, o único mecanismo de recuperação é o bypass genérico de infraestrutura do filtro de soft-delete (FR-013/FR-024), sem uma rota de API própria. Reavaliar no plano se essa lacuna afetar auditoria administrativa.
- `CLOSED`, `CANCELLED` e `ARCHIVED` são estados terminais para mutações operacionais. `ARCHIVED` representa organização histórica, não um resultado científico adicional.
- Justificativas pertencem às decisões de review; exclusão e arquivamento registram apenas a transição e o responsável. A trilha de auditoria preserva o estado terminal anterior quando um processo é arquivado.
- O mecanismo de filtragem global de exclusão lógica coexiste com verificações manuais equivalentes já existentes no código; ele funciona como rede de segurança adicional para consultas de leitura comuns, mas NÃO cobre atualizações ou remoções em lote nem acessos que contornem a camada de leitura padrão da aplicação — esses continuam dependendo de verificação manual explícita.

## Dependencies and Traceability

- **Issue #14: Implementar cancelamento ou arquivamento de processo em validação**: origem confirmada para interrupção/arquivamento, autorização, dependências, auditoria e testes.
- **Feature 004: Submissão e Triagem**: fornece estados do processo, atividades, execuções, tarefas, formulários e trilha de auditoria.
- **Feature 009: Submissão de Método Alternativo**: define o envio formal, hoje sem efeito na autorização de exclusão desta feature, mas ainda relevante para o histórico de pipeline preservado.
- **Features 010 e 013: Pipeline de avaliação por IA**: fornecem execuções automáticas que também precisam parar sem conclusão tardia após a exclusão.
- **Feature 018: Kanban e cargos**: define perfis globais Administrador/BraCVAM e as visões operacionais que devem deixar de oferecer trabalho excluído ou arquivado.
- **Feature 021: Atualização de submissão**: define a devolução para correção, hoje sem efeito na autorização de exclusão desta feature.
- **Feature 023: Simplificação de cargos globais (RBAC)**: pré-condição externa desta spec (ver Clarifications 2026-09-13); define os cargos globais canônicos (Padrão/Admin/BraCVAM) e garante que a permissão de revisão usada aqui seja outorgada somente a Admin/BraCVAM.
- **AGENTS.md**: exige demonstração interativa em `demos/`, catálogo central, seed mínimo em `scripts/seeds/`, integração com o backend real e proíbe endpoints exclusivos para demonstração.
