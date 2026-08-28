# Feature Specification: 004 - Estrutura Base de Processos e Fase 1: Submissão e Triagem

**Feature Branch**: `004-process-submission-triage`

**Created**: 2026-08-21

**Status**: Implemented

**Input**: User description: "Os dois documentos de referência para a implementação estão em docs/planejamento/PIVMA_contexto_problemas.md e docs/planejamento/PIVMA_diretrizes_especificacoes.md. Implemente apenas a primeira fase do produto: Submissão e Triagem. Entretanto, a solução deve estabelecer as abstrações necessárias para que as fases posteriores possam utilizar o mesmo modelo de ProcessTemplate, ProcessInstance, Activity, ActivityRun, Task, Artifact, Form e dependências. Não assuma detalhes de negócio que não estejam definidos. Identifique ambiguidades e faça perguntas antes de estabelecer regras."

## Clarifications

### Session 2026-08-21

- **Q1: Fluxo de Diligência / Solicitação de Ajustes na Triagem**
  - **Decisão**: Opção A. Ao solicitar diligência, o triador registra o parecer apontando as correções necessárias; o sistema gera uma nova execução (`ActivityRun #2`) da atividade de submissão atribuída ao Proponente para reenvio, preservando a submissão anterior no histórico imutável.
- **Q2: Avaliação Assistida por IA na Fase 1**
  - **Decisão**: Opção A. **Estrutura Habilitadora**: Definir entidades, interfaces e rastreabilidade para avaliações de IA (vinculadas a formulários e versões de execução), mas sem acoplamento obrigatório a modelos externos na Fase 1, priorizando a validação determinística e a triagem humana.
- **Q3: Templates Iniciais de Processo e Formulários**
  - **Decisão**: Opção A com semente declarativa. Um template padrão inicial de **Validação Completa (Full Validation)**, com a Fase 1 (Submissão e Triagem) totalmente operável e as fases futuras declaradas em sua estrutura. O provisionamento inicial dos templates e formulários deve utilizar representação declarativa (YAML/Seed) para facilitar manutenibilidade e futura importação de formulários existentes.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submissão de Proposta de Validação (Priority: P1)

Como um Proponente (pesquisador ou instituição proponente), quero iniciar uma nova solicitação de validação de método alternativo preenchendo o formulário estruturado de submissão e anexando a documentação inicial necessária, para que a proposta seja registrada com rastreabilidade completa e entre na fila de triagem.

**Why this priority**: A submissão é o ponto de entrada de todo o ciclo de vida do processo na plataforma. Sem o registro da instância de processo, suas fases, atividades e formulários de entrada, nenhuma etapa subsequente pode existir.

**Independent Test**: Um proponente autenticado inicia um novo processo baseado no template de validação, preenche os campos obrigatórios do formulário de submissão, anexa os arquivos exigidos e conclui a submissão. O sistema registra a instância do processo, a primeira execução da atividade de submissão, os artefatos gerados e disponibiliza a tarefa de triagem para a equipe gestora.

**Acceptance Scenarios**:

1. **Given** um proponente autenticado e um template de processo ativo de validação, **When** o proponente cria uma nova submissão com dados válidos e submete o formulário, **Then** o sistema cria uma `ProcessInstance` no estado de Submissão, registra o `FormInstance` versionado, gera o `Artifact` da submissão, conclui a `ActivityRun` de submissão e avança o processo para a etapa de Triagem (`TRIAGE`).
2. **Given** um proponente preenchendo um formulário de submissão, **When** faltarem campos obrigatórios ou forem fornecidos dados em formato inválido, **Then** o sistema impede a finalização, destaca os erros de validação campo a campo e mantém o formulário em edição sem gerar artefatos finais ou avançar de fase.
3. **Given** um proponente com uma submissão em rascunho, **When** ele salva o formulário sem submeter, **Then** o sistema preserva os dados preenchidos em estado de rascunho para conclusão posterior sem transicionar o processo para triagem.

---

### User Story 2 - Triagem e Revisão da Submissão (Priority: P2)

Como um Membro do Grupo Gestor / Triador, quero acessar a tarefa de triagem de uma proposta submetida, revisar as informações e documentos campo a campo, registrar pareceres/notas de avaliação e emitir uma decisão inicial fundamentada (aprovação para planejamento, rejeição com justificativa ou solicitação de diligência/ajustes), para garantir a conformidade técnica antes do planejamento do estudo.

**Why this priority**: A triagem é o gate de governança inicial que valida a viabilidade e completude da proposta antes que recursos laboratoriais, estatísticos e financeiros sejam alocados nas fases seguintes.

**Independent Test**: Um membro do Grupo Gestor visualiza a lista de propostas em triagem, abre a tarefa correspondente, inspeciona os dados do formulário e artefatos anexados, preenche o formulário de parecer de triagem e emite a decisão. O sistema atualiza o estado da atividade e da instância do processo de forma rastreável.

**Acceptance Scenarios**:

1. **Given** uma proposta submetida aguardando triagem, **When** o triador avalia positivamente todos os critérios e aprova a submissão, **Then** a atividade de triagem é marcada como concluída (`COMPLETED`), o artefato de Parecer de Triagem é gerado no estado aprovado, e a instância do processo atinge a conclusão da Fase 1, tornando-se apta para a fase de Planejamento.
2. **Given** uma proposta submetida aguardando triagem, **When** o triador identifica que a proposta é inviável ou não atende aos requisitos mínimos regulatórios e emite parecer de rejeição com justificativa, **Then** a atividade de triagem é concluída como rejeitada, o processo é encerrado no estado rejeitado/arquivado (`CLOSED`) e o histórico completo é preservado.
3. **Given** uma proposta submetida com pendências sanáveis, **When** o triador emite uma solicitação de diligência com justificativa, **Then** o sistema registra o parecer da triagem, cria uma nova execução (`ActivityRun #2`) da atividade de submissão atribuída ao Proponente com os dados preenchidos anteriormente carregados para ajuste, mantendo a submissão anterior (`ActivityRun #1`) preservada no histórico.

---

### User Story 3 - Visualização Operacional de Tarefas e Acompanhamento de Processos (Priority: P3)

Como um Usuário do sistema (Proponente ou Membro do Grupo Gestor), quero consultar a lista/quadro de tarefas pendentes e o histórico detalhado da minha instância de processo (com status das atividades, execuções, artefatos gerados e eventuais bloqueios explicáveis), para entender o andamento e saber exatamente quais ações são necessárias.

**Why this priority**: Garante a transparência, explicabilidade e usabilidade operacional do motor de processos, permitindo que os atores identifiquem bloqueios e responsabilidades sem depender de consultas manuais.

**Independent Test**: Consultar o painel de tarefas de um usuário atribuído e a linha do tempo/histórico do processo, verificando se cada tarefa exibe seu estado (Aguardando, Disponível, Em Andamento, Bloqueada, Concluída), suas dependências e o histórico de execuções anteriores.

**Acceptance Scenarios**:

1. **Given** um usuário logado com papel de triador, **When** ele consulta suas tarefas pendentes, **Then** o sistema exibe apenas as tarefas para as quais ele tem atribuição ou papel correspondente e cujas pré-condições estejam satisfeitas (`READY` ou `IN_PROGRESS`).
2. **Given** uma atividade cujas pré-condições não foram atendidas, **When** o usuário consulta o status da atividade, **Then** o sistema exibe o estado `BLOCKED` acompanhado da explicação clara das dependências faltantes (ex.: "Aguardando conclusão da Submissão").
3. **Given** um processo que passou por diligência ou reexecução de atividade, **When** o usuário consulta o histórico, **Then** o sistema exibe tanto a execução original quanto a nova execução com seus respectivos timestamps, autores, tarefas e artefatos associados.

---

### Edge Cases

- O que acontece se dois triadores tentarem emitir decisão sobre a mesma tarefa de triagem simultaneamente? O sistema deve tratar controle de concorrência garantindo que apenas a primeira decisão seja processada e a segunda rejeitada informando que a tarefa já foi concluída.
- O que acontece se o template de processo for atualizado após a criação de uma instância? A instância iniciada deve permanecer vinculada à versão original do template (`ProcessTemplate`) em que foi instanciada, sem alterações silenciosas ou retroativas.
- O que acontece se o upload de um arquivo obrigatório falhar durante a submissão? O formulário não deve ser submetido com integridade comprometida; o sistema deve abortar a transição e manter o rascunho.
- O que acontece se uma submissão for rejeitada na triagem e o proponente tentar reeditá-la? Processos em estado terminal/fechado (`CLOSED`) devem ter seus formulários e atividades bloqueados para edição, permitindo apenas consulta histórica.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir a instanciação de um processo (`ProcessInstance`) a partir de um template (`ProcessTemplate`) versionado, isolando a definição do template das instâncias em execução.
- **FR-002**: O sistema DEVE decompor a instância de processo em Fases (`Phase`), Atividades (`Activity`) e Execuções de Atividade (`ActivityRun`), suportando múltiplas execuções da mesma atividade sem sobrescrever ou apagar históricos anteriores.
- **FR-003**: O sistema DEVE suportar a criação e renderização de formulários dinâmicos via `FormTemplate` e a persistência de submissões estruturadas em `FormInstance` vinculadas a uma versão de template.
- **FR-004**: O sistema DEVE suportar os tipos fundamentais de campos de formulário: `text`, `integer`, `float`, `boolean`, `select`, `date` e `file_upload`, com regras de obrigatoriedade e validação de formato.
- **FR-005**: O sistema DEVE gerar instâncias de `Task` para atividades disponíveis, atribuindo-as a papéis locais do processo (ex.: Proponente, Grupo Gestor) ou a usuários específicos.
- **FR-006**: O sistema DEVE gerenciar estados de atividades (`DRAFT`, `BLOCKED`, `READY`, `IN_PROGRESS`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`) e estados macro do processo (`SUBMISSION`, `TRIAGE`, `PLANNING`, `CLOSED`).
- **FR-007**: O sistema DEVE representar dependências entre atividades e entre artefatos como pré-condições explícitas, bloqueando atividades (`BLOCKED`) até que todas as entradas obrigatórias estejam satisfeitas e fornecendo justificativa textual do bloqueio.
- **FR-008**: O sistema DEVE registrar artefatos (`Artifact`) gerados por cada atividade (incluindo dados de submissão, documentos anexados e pareceres de triagem), contendo metadados, versão, autor, estado e vínculo com a `ActivityRun` originadora.
- **FR-009**: O sistema DEVE implementar o fluxo da **Fase 1: Submissão e Triagem**, composto pelas etapas de preenchimento da proposta pelo Proponente e revisão/deliberação inicial pelo Grupo Gestor.
- **FR-010**: O sistema DEVE permitir ao Triador emitir decisão de triagem:
  - **Aprovação**: conclui a Fase 1 e sinaliza prontidão para o Planejamento;
  - **Rejeição**: encerra o processo com registro formal do parecer de recusa no estado `CLOSED`;
  - **Diligência / Solicitação de Ajustes**: gera uma nova execução (`ActivityRun #2`) da atividade de submissão com os dados carregados para revisão pelo Proponente, preservando a submissão original no histórico.
- **FR-011**: O sistema DEVE manter registro imutável de trilha de auditoria para todos os eventos de ciclo de vida (criação de processo, submissão de formulário, mudança de estado de atividade, atribuição de tarefa, geração de artefato e emissão de parecer).
- **FR-012**: O sistema DEVE estruturar o modelo de dados para suportar avaliações assistidas por IA vinculadas a formulários e execuções, sem dependência mandatória de chamadas externas ativas na Fase 1.
- **FR-013**: O sistema DEVE disponibilizar consulta de tarefas operacionais (estilo Kanban / lista filtrada por usuário e estado) e consulta macro do histórico da instância do processo.
- **FR-014**: O sistema DEVE fornecer inicialmente o template padrão de **Validação Completa (Full Validation)** com a Fase 1 totalmente configurada e operável, suportando seed declarativo via arquivos (YAML) para templates e formulários.

### Key Entities

- **ProcessTemplate**: Representa a definição reutilizável e versionada de um pipeline de validação, incluindo fases, atividades, formulários associados e regras de dependência.
- **ProcessInstance**: Representa a execução concreta de um processo específico iniciado por uma submissão, mantendo estado macro, template de origem, datas e participantes.
- **Phase**: Representa um agrupamento lógico de atividades dentro do ciclo de vida do processo (ex.: Fase 1 - Submissão e Triagem).
- **Activity**: Representa uma unidade de trabalho declarada no processo (ex.: Submissão da Proposta, Triagem Inicial).
- **ActivityRun**: Representa uma execução concreta de uma atividade, guardando entradas, saídas, autor, estado, timestamps de início e término e justificativa (em caso de repetição).
- **Task**: Representa a atribuição operacional de trabalho para um usuário ou papel em uma `ActivityRun`, com status de acompanhamento.
- **FormTemplate & FormField**: Representam o esquema e os campos parametrizáveis de coleta de dados.
- **FormInstance & FormValue**: Representam o preenchimento concreto e versionado de um formulário.
- **Artifact**: Representa o documento, dado estruturado ou resultado gerado por uma atividade que pode ser consumido como entrada por outras atividades.
- **Dependency**: Representa uma pré-condição exigida para que uma atividade ou tarefa se torne `READY`.
- **Assignment**: Representa a atribuição de um papel local do processo (ex.: Proponente, Triador) a um usuário dentro de uma `ProcessInstance`.
- **AuditEvent**: Registro imutável de auditoria de cada evento ocorrido na instância.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Proponentes conseguem submeter uma proposta de validação completa com formulário e anexos em um único fluxo consistente.
- **SC-002**: 100% das instâncias de processo criadas preservam o vínculo com a versão exata do template no momento de sua instanciação, mesmo após alterações subsequentes no template.
- **SC-003**: 100% das reexecuções ou solicitações de diligência preservam as submissões e artefatos anteriores no histórico de auditoria sem sobrescrita destrutiva de dados.
- **SC-004**: Triadores conseguem acessar tarefas pendentes, inspecionar dados submetidos e emitir decisão de aprovação, rejeição ou diligência com registro do parecer.
- **SC-005**: 100% das atividades com pré-condições pendentes apresentam o estado de bloqueio (`BLOCKED`) com mensagem explicativa clara identificando a dependência faltante.
- **SC-006**: O tempo para consultar a lista operacional de tarefas ou a linha do tempo de um processo é imediato para os usuários atribuídos.

## Assumptions

- A infraestrutura transversal de autenticação, usuários e RBAC global já está disponível no sistema e será utilizada para autenticar os atores (Proponente, Triador/Gestor).
- As fases posteriores (Planejamento, Execução Interlaboratorial, Revisão Técnica, Deliberação Final) não terão seus fluxos de negócio executados nesta entrega, mas reutilizarão as entidades e mecanismos de `ProcessTemplate`, `ProcessInstance`, `Activity`, `ActivityRun`, `Task`, `Artifact` e `Dependency` definidos nesta fase.
- O provisionamento de templates e formulários via sementes declarativas (YAML) estabelece a base para futuros importadores ou conversores de formulários legados/externos.
- O armazenamento de arquivos anexados aos artefatos e formulários utilizará os padrões já estabelecidos no backend.
- A exclusão lógica e rastreabilidade seguem o padrão `AuditMixin` adotado no projeto.
