# Feature Specification: Exclusão, Cancelamento e Arquivamento de Processos

**Feature Branch**: `022-process-retirement`

**Created**: 2026-09-12

**Status**: Implemented

**Input**: User description: "Issue #14: rascunhos nunca submetidos devem sofrer exclusão física do agregado e de seus documentos; processos que entraram no pipeline de validação devem usar cancelamento e arquivamento, sem complexidade desnecessária e com contrato simples para o front-end."

## Contexto e classificação

- **CONFIRMADO**: a issue #14 solicita uma forma de interromper, arquivar ou excluir uma instância de processo, com autorização, tratamento das operações pendentes, preservação de integridade e auditoria com usuário e justificativa.
- **CONFIRMADO**: instâncias de processo possuem exclusão lógica, estado macro, momento e motivo de encerramento; tarefas, atividades, execuções, formulários, documentos e eventos permanecem vinculados ao processo.
- **CONFIRMADO**: no comportamento atual, `SUBMISSION` também representa a elaboração inicial e pode voltar a ocorrer após uma devolução para correção; portanto, o estado isolado não comprova que um processo nunca entrou no pipeline.
- **CONFIRMADO por decisão do responsável da demanda**: um processo é considerado rascunho descartável somente enquanto nunca tiver sido formalmente submetido. Sua retirada elimina fisicamente o agregado inteiro, incluindo documentos armazenados, e não cria um estado `DELETED`.
- **PROPOSTA desta feature**: um processo que já foi formalmente submetido não pode mais ser excluído; sua interrupção usa o estado terminal `CANCELLED`, preservando todo o histórico.
- **PROPOSTA desta feature**: `ARCHIVED` organiza processos históricos e só pode suceder estados terminais (`CLOSED` ou `CANCELLED`). Rascunhos não podem ser arquivados e processos ativos não podem usar arquivamento como atalho para cancelamento.
- **PROPOSTA desta feature**: a grafia canônica é `CANCELLED`, já utilizada nas entidades operacionais do domínio e na issue original. Não serão introduzidos os estados redundantes `CANCELED` ou `DELETED`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Excluir permanentemente um rascunho não submetido (Priority: P1)

Como proponente, quero excluir permanentemente uma submissão que ainda é apenas um rascunho e nunca entrou no pipeline de validação, para remover registros e documentos descartados sem poluir as listagens ou consumir armazenamento.

**Why this priority**: É o caso mais simples e frequente, elimina o agregado sem histórico de pipeline e evita que rascunhos descartados sejam confundidos com processos cancelados.

**Independent Test**: Criar um processo com dados e anexo sem realizar o primeiro envio formal, excluí-lo com uma justificativa e confirmar que não restam processo, registros vinculados, eventos ou arquivo armazenado.

**Acceptance Scenarios**:

1. **Given** um rascunho que nunca foi formalmente submetido, **When** seu proponente informa uma justificativa válida e solicita a exclusão, **Then** o sistema exclui fisicamente o processo, seus registros vinculados e seus documentos armazenados, e não cria estado `ARCHIVED` ou `DELETED`.
2. **Given** um rascunho de outro proponente, **When** um usuário comum tenta excluí-lo, **Then** a operação é negada e nenhum dado é alterado.
3. **Given** um rascunho que nunca foi formalmente submetido, **When** um Administrador ou usuário BraCVAM autorizado o exclui com justificativa, **Then** a exclusão física do agregado é concluída.
4. **Given** um processo que já teve ao menos um envio formal, mesmo que esteja novamente em `SUBMISSION` para correção, **When** qualquer usuário tenta excluí-lo como rascunho, **Then** a operação é rejeitada e o histórico permanece íntegro.

---

### User Story 2 - Cancelar um processo em validação (Priority: P1)

Como Administrador ou usuário BraCVAM autorizado, quero cancelar um processo que já entrou no pipeline de validação, informando o motivo, para interromper de maneira segura todo trabalho pendente sem apagar submissões, decisões ou evidências anteriores.

**Why this priority**: Resolve a lacuna central da issue #14 e impede que tarefas humanas ou automáticas continuem operando sobre um processo oficialmente interrompido.

**Independent Test**: Preparar um processo formalmente submetido com tarefa, atividade, execução e formulário pendentes; cancelá-lo; confirmar o estado `CANCELLED`, o encerramento das operações ainda ativas, o bloqueio de novas mutações, a preservação do histórico e o evento de auditoria.

**Acceptance Scenarios**:

1. **Given** um processo formalmente submetido e ainda não terminal, **When** um Administrador ou usuário BraCVAM autorizado informa uma justificativa e o cancela, **Then** o processo passa para `CANCELLED`, registra momento e motivo de encerramento e deixa de aceitar novas edições ou execuções.
2. **Given** tarefas, atividades, execuções humanas ou automáticas ainda pendentes no processo, **When** o cancelamento é concluído, **Then** todas deixam de ser acionáveis e assumem seu estado terminal de cancelamento quando esse estado existir no respectivo ciclo de vida.
3. **Given** formulários pendentes ou já enviados, **When** o processo é cancelado, **Then** seus conteúdos são preservados como histórico somente leitura, sem transformar formulários pendentes em enviados e sem excluir registros.
4. **Given** um usuário sem autorização administrativa, **When** ele tenta cancelar um processo, **Then** a operação é negada sem revelar dados além daqueles que ele já poderia consultar e sem alterações parciais.
5. **Given** um processo já `CLOSED`, `CANCELLED` ou `ARCHIVED`, **When** alguém solicita seu cancelamento, **Then** a transição é rejeitada de forma previsível e o estado existente é preservado.

---

### User Story 3 - Arquivar um processo terminal (Priority: P2)

Como Administrador ou usuário BraCVAM autorizado, quero arquivar um processo concluído ou cancelado, para retirá-lo das visões operacionais padrão sem perder sua consulta histórica e sua trilha de auditoria.

**Why this priority**: Arquivamento melhora a organização do volume histórico, mas depende de o processo já ter alcançado um resultado terminal e não é necessário para interromper trabalho ativo.

**Independent Test**: Partir de um processo `CLOSED` e outro `CANCELLED`, arquivá-los com justificativa e confirmar que deixam de aparecer na visão operacional padrão, continuam recuperáveis por consulta histórica autorizada e preservam todos os vínculos e eventos anteriores.

**Acceptance Scenarios**:

1. **Given** um processo `CLOSED` ou `CANCELLED`, **When** um Administrador ou usuário BraCVAM autorizado o arquiva com justificativa, **Then** ele passa para `ARCHIVED`, deixa de aparecer nas listagens operacionais padrão e continua disponível em consultas históricas explícitas.
2. **Given** um rascunho ou processo ainda ativo, **When** alguém tenta arquivá-lo, **Then** a operação é rejeitada e orienta que rascunhos sejam excluídos ou processos em validação sejam cancelados conforme o caso.
3. **Given** um processo arquivado, **When** um usuário autorizado consulta seu detalhe ou histórico, **Then** os dados anteriores, o resultado terminal precedente e a justificativa do arquivamento permanecem identificáveis e somente leitura.
4. **Given** um usuário sem autorização administrativa, **When** ele tenta arquivar ou consultar processos arquivados fora de seu escopo, **Then** o acesso é negado sem alteração de estado.

---

### User Story 4 - Front-end conhece as ações permitidas (Priority: P3)

Como integrante da equipe de front-end, quero receber códigos de ação e motivos de recusa estáveis, além das ações atualmente permitidas para cada processo consultado, para exibir somente comandos válidos sem reproduzir toda a regra de ciclo de vida no cliente.

**Why this priority**: Reduz divergências entre interface e backend com uma extensão pequena do contrato; a regra continua sendo validada pelo sistema mesmo se o cliente estiver desatualizado.

**Independent Test**: Consultar rascunhos próprios e alheios, processos ativos, terminais e arquivados com usuários de perfis distintos e confirmar que as ações informadas correspondem às operações que o sistema aceita naquele momento.

**Acceptance Scenarios**:

1. **Given** qualquer processo visível, **When** o usuário consulta sua representação, **Then** recebe a condição de ciclo de vida e somente as ações de retirada que pode executar naquele estado e contexto de autorização.
2. **Given** uma tentativa inválida, **When** o sistema a rejeita, **Then** a resposta distingue de forma estável ao menos recurso inexistente ou invisível, falta de autorização, justificativa inválida e transição incompatível.
3. **Given** um cliente que envia uma ação mesmo sem ela constar como permitida, **When** a solicitação chega ao sistema, **Then** todas as regras são novamente validadas antes de qualquer alteração.

### Edge Cases

- Duas pessoas solicitam simultaneamente ações diferentes sobre o mesmo processo. Apenas uma transição compatível com o estado confirmado é concluída; a outra é rejeitada sem sobrescrever o resultado nem duplicar efeitos.
- Um processo aparece em `SUBMISSION`, mas já possui envio formal anterior por ter sido devolvido para correção. Ele pertence ao histórico do pipeline e pode ser cancelado, nunca excluído como rascunho.
- Uma execução automática está em andamento no instante do cancelamento. O sistema impede que sua conclusão tardia reative, avance ou altere o processo cancelado.
- Uma tarefa ou execução já está concluída quando o processo é cancelado. Seu estado histórico não é reescrito; somente itens ainda não terminais são cancelados.
- Um rascunho possui formulários, anexos ou outros registros vinculados. A exclusão remove o agregado inteiro e seus arquivos; processos submetidos preservam esses registros em cancelamento e arquivamento.
- A justificativa contém somente espaços, excede o limite aceito ou não é fornecida. A operação é rejeitada antes de alterar qualquer entidade.
- Uma consulta padrão combina filtros de estado com processos arquivados. `ARCHIVED` só aparece quando solicitado explicitamente; rascunhos excluídos fisicamente não entram em nenhuma consulta histórica comum.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer três intenções distintas e inequívocas: excluir rascunho, cancelar processo em validação e arquivar processo terminal.
- **FR-002**: O sistema DEVE considerar excluível como rascunho apenas um processo que nunca tenha sido formalmente submetido, independentemente do nome de seu estado atual.
- **FR-003**: A exclusão de rascunho DEVE remover fisicamente o agregado do processo e seus documentos armazenados; a feature NÃO DEVE introduzir um estado `DELETED`.
- **FR-004**: A exclusão de rascunho DEVE remover, sem deixar registros órfãos, o processo, fases, atividades, execuções, tarefas, formulários, valores, atribuições, decisões, avaliações, artefatos e eventos a ele vinculados.
- **FR-005**: O proponente criador DEVE poder excluir seu próprio rascunho; Administradores e usuários BraCVAM autorizados DEVEM poder excluir qualquer rascunho visível a seu escopo administrativo.
- **FR-006**: Um processo que já tenha sido formalmente submetido NÃO DEVE aceitar exclusão de rascunho, inclusive durante uma elaboração causada por devolução para correção.
- **FR-007**: Somente Administradores e usuários BraCVAM autorizados DEVEM poder cancelar ou arquivar processos.
- **FR-008**: O cancelamento DEVE ser aceito apenas para processo formalmente submetido que ainda não esteja em estado terminal e DEVE produzir o estado canônico `CANCELLED`.
- **FR-009**: Ao cancelar, o sistema DEVE registrar o momento e o motivo de encerramento e cancelar todas as tarefas, atividades, execuções humanas e execuções automáticas ainda não terminais vinculadas ao processo.
- **FR-010**: O cancelamento NÃO DEVE alterar o estado de itens já terminais, apagar formulários, anexos, valores, decisões, avaliações ou eventos, nem marcar formulários pendentes como formalmente enviados.
- **FR-011**: Depois do cancelamento, toda tentativa de editar dados, enviar formulários, iniciar ou concluir tarefas, emitir decisões, iniciar ou concluir avaliações ou avançar o fluxo DEVE ser impedida.
- **FR-012**: Uma conclusão tardia de trabalho iniciado antes do cancelamento NÃO DEVE alterar o processo `CANCELLED` nem reativar entidades subordinadas.
- **FR-013**: O arquivamento DEVE ser aceito somente para processos em `CLOSED` ou `CANCELLED` e DEVE produzir o estado `ARCHIVED`.
- **FR-014**: Ao arquivar, o sistema DEVE preservar de forma consultável o estado terminal anterior, o momento do arquivamento, sua justificativa e o responsável.
- **FR-015**: O arquivamento NÃO DEVE reescrever estados ou dados das entidades subordinadas e NÃO DEVE permitir novas mutações no processo.
- **FR-016**: Processos `ARCHIVED` DEVEM ser omitidos das listagens operacionais padrão e DEVEM poder ser recuperados por consulta histórica explícita e autorizada; rascunhos excluídos fisicamente NÃO DEVEM ser recuperados por essa mesma consulta comum.
- **FR-017**: Rascunhos NÃO DEVEM aceitar arquivamento, e processos ativos NÃO DEVEM aceitar arquivamento como substituto do cancelamento.
- **FR-018**: Excluir, cancelar e arquivar DEVEM exigir uma justificativa textual não vazia, com limites publicados e aplicados de forma consistente.
- **FR-019**: Cada cancelamento ou arquivamento concluído DEVE gerar um evento de auditoria imutável contendo processo, ação, estado anterior, estado resultante, usuário responsável, justificativa e momento. A exclusão física de rascunho remove os eventos do próprio agregado.
- **FR-020**: A exclusão física de rascunho DEVE remover o agregado completo sem registros órfãos. O cancelamento e o arquivamento DEVEM concluir mudança de estado, tratamento das entidades subordinadas e auditoria como uma única unidade.
- **FR-021**: Tentativas sem autorização ou com transição inválida NÃO DEVEM provocar alteração parcial, cancelar trabalho subordinado nem criar evento que represente falsamente uma operação concluída.
- **FR-022**: Solicitações concorrentes DEVEM ser resolvidas contra um único estado confirmado, impedindo que uma ação posterior sobrescreva outra já concluída sem registrar o conflito.
- **FR-023**: O sistema DEVE fornecer uma operação consistente para receber uma das ações `DELETE_DRAFT`, `CANCEL` ou `ARCHIVE` com a mesma estrutura de justificativa, sem exigir que o cliente monte alterações diretas de estado.
- **FR-024**: A representação consultável de um processo DEVE informar suas ações de retirada permitidas para o usuário atual, usando os mesmos códigos de FR-023; essa informação é auxiliar e NÃO substitui a autorização no momento da operação.
- **FR-025**: As rejeições DEVEM usar categorias estáveis e distinguíveis para recurso inexistente ou invisível, falta de autorização, justificativa inválida e transição incompatível, permitindo tratamento previsível pelo front-end.
- **FR-026**: A entrega DEVE incluir uma demonstração interativa desacoplada do núcleo da aplicação, registrada no catálogo central de demonstrações e operando contra o comportamento real do backend.
- **FR-027**: A entrega DEVE incluir uma massa de dados mínima e repetível que permita demonstrar ao menos: rascunho excluível, processo ativo cancelável, processo concluído arquivável e tentativa bloqueada.
- **FR-028**: A feature NÃO DEVE criar exclusão física para processos submetidos, restauração, reabertura, desarquivamento, exclusão em massa, agendamento de cancelamento ou novos endpoints facilitadores exclusivos para a demonstração.

### Scope Boundaries

**Incluído**:

- Exclusão física em cascata de rascunho nunca submetido, incluindo documentos armazenados.
- Cancelamento terminal de processo que já entrou no pipeline.
- Arquivamento de processo concluído ou cancelado.
- Encerramento consistente do trabalho pendente, bloqueio de mutações e auditoria.
- Consulta explícita de históricos arquivados e indicação das ações permitidas ao front-end.
- Demonstração interativa e seed mínimo conectados ao comportamento real.

**Fora do escopo**:

- Exclusão física de processo que já tenha tido envio formal.
- Estado `DELETED` ou grafias alternativas de `CANCELLED`.
- Arquivamento de rascunho ou de processo ainda ativo.
- Restauração, reabertura, desarquivamento, retomada ou clonagem de processo.
- Operações em massa, retenção automática, expurgo ou agendamento.
- Redesenho geral do motor de estados ou da matriz de papéis da plataforma.

### Key Entities *(include if feature involves data)*

- **Instância de processo**: submissão concreta cujo histórico determina se ainda é um rascunho removível ou se já entrou no pipeline; contém o estado macro e os dados de encerramento.
- **Trabalho subordinado**: fases, atividades, tarefas e execuções humanas ou automáticas vinculadas ao processo; itens pendentes são interrompidos no cancelamento e itens históricos são preservados.
- **Formulário e conteúdo vinculado**: dados de elaboração ou submissão preservados como histórico; tornam-se somente leitura após cancelamento ou arquivamento.
- **Evento de auditoria**: evidência imutável de cancelamento ou arquivamento, com autor, justificativa, momento e transição produzida. A exclusão física de rascunho remove os eventos do agregado.
- **Ação permitida**: indicação contextual de `DELETE_DRAFT`, `CANCEL` ou `ARCHIVE`, derivada do estado, histórico e autorização do usuário atual.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% dos cenários de rascunho nunca submetido, a exclusão autorizada remove processo, registros vinculados e documentos armazenados, sem criar estado `DELETED`.
- **SC-002**: Em 100% dos processos com envio formal anterior, a exclusão de rascunho é impedida, inclusive após devolução para correção.
- **SC-003**: Em 100% dos cancelamentos válidos, o processo e todo trabalho ainda não terminal deixam de ser acionáveis, enquanto itens já concluídos e conteúdos vinculados permanecem inalterados e consultáveis conforme autorização.
- **SC-004**: Em 100% das tentativas de mutação posteriores a `CANCELLED` ou `ARCHIVED`, o processo não avança e nenhum dado operacional é alterado.
- **SC-005**: Em 100% dos arquivamentos válidos, o processo sai da visão operacional padrão e permanece recuperável por consulta histórica explícita com seu resultado terminal anterior identificável.
- **SC-006**: Em 100% das tentativas sem autorização, com justificativa inválida, transição incompatível ou disputa concorrente perdida, não ocorre alteração parcial nem evento de sucesso falso.
- **SC-007**: Em 100% dos cancelamentos e arquivamentos concluídos, uma pessoa autorizada consegue identificar ação, processo, estado anterior, resultado, responsável, justificativa e momento na trilha de auditoria.
- **SC-008**: Na demonstração conectada ao backend real, uma pessoa autorizada consegue identificar a ação disponível e concluir a exclusão, o cancelamento ou o arquivamento de um processo aplicável em até 1 minuto por caso.
- **SC-009**: Em 100% dos processos amostrados nos estados de rascunho, ativo, concluído, cancelado e arquivado, as ações informadas ao front-end coincidem com as ações efetivamente aceitas pelo sistema.
- **SC-010**: A massa mínima de demonstração pode ser reaplicada sem criar estados contraditórios e cobre os quatro casos exigidos em FR-027.

## Assumptions

- A primeira submissão formal é o marco de entrada no pipeline. Salvar um formulário ou anexo sem submetê-lo não retira a condição de rascunho; uma devolução posterior para correção não devolve ao processo a condição de descartável.
- O perfil global Administrador e o perfil global BraCVAM são as autoridades administrativas desta entrega. Papéis contextuais como proponente, gestor de grupo ou gerente de estudo não recebem, por si sós, poder de cancelar ou arquivar.
- O criador do processo continua identificado por sua atribuição ativa de proponente durante a elaboração inicial; essa regra existente será reutilizada para autorizar a exclusão do próprio rascunho.
- `CLOSED`, `CANCELLED` e `ARCHIVED` são estados terminais para mutações operacionais. `ARCHIVED` representa organização histórica, não um resultado científico adicional.
- O motivo de encerramento existente pode registrar a justificativa de cancelamento; a trilha de auditoria preserva o estado terminal anterior quando um processo é arquivado.
- A exclusão física de rascunho não mantém uma trilha de auditoria persistida do agregado, pois ela também é removida com o processo.

## Dependencies and Traceability

- **Issue #14: Implementar cancelamento ou arquivamento de processo em validação**: origem confirmada para interrupção/arquivamento, autorização, dependências, auditoria e testes.
- **Feature 004: Submissão e Triagem**: fornece estados do processo, atividades, execuções, tarefas, formulários e trilha de auditoria.
- **Feature 009: Submissão de Método Alternativo**: define o envio formal e a elaboração inicial usada para distinguir rascunho de processo em pipeline.
- **Features 010 e 013: Pipeline de avaliação por IA**: fornecem execuções automáticas que também precisam parar sem conclusão tardia após cancelamento.
- **Feature 018: Kanban e cargos**: define perfis globais Administrador/BraCVAM e as visões operacionais que devem deixar de oferecer trabalho cancelado ou arquivado.
- **Feature 021: Atualização de submissão**: define a devolução para correção e reforça que um processo já submetido não volta a ser rascunho descartável.
- **AGENTS.md**: exige demonstração interativa em `demos/`, catálogo central, seed mínimo em `scripts/seeds/`, integração com o backend real e proíbe endpoints exclusivos para demonstração.
