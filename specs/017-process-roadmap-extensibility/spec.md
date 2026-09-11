# Feature Specification: 017 - Roteiro Dinâmico e Extensibilidade de Atividades para Fases Futuras

**Feature Branch**: `017-process-roadmap-extensibility`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Incorpora os pontos que levantamos nessa conversa + o plano B em uma spec de melhoria da pipeline de validação"

## Contexto e Motivação

A Spec 004 estabeleceu o motor genérico de processos (`ProcessTemplate`, `Phase`,
`ActivityInstance`, `ActivityRun`, `Task`, `FormTemplate`/`FormInstance`) com a premissa
explícita de que as fases futuras (Planejamento, Execução Interlaboratorial, Revisão
Técnica, Deliberação Final) reutilizariam essas mesmas entidades em vez de um modelo
paralelo. Hoje só a Fase 1 (Submissão e Triagem) está declarada nos cinco métodos
oficiais do BraCVAM (Spec 011/015).

Ao planejar a tela do proponente que se abre após a escolha de um método (o "clique no
método" desta discussão), duas lacunas concretas foram identificadas:

1. Não existe uma forma de consultar, para uma instância de processo, o roteiro completo
   de fases e atividades declaradas no template — incluindo as que ainda não começaram.
   Hoje isso só é possível combinando a definição declarativa do template com a lista de
   tarefas (`GET /tasks`), uma inferência frágil que deixa de funcionar assim que uma
   atividade não tiver uma tarefa em correspondência 1:1.
2. Toda atividade hoje é implicitamente um formulário (`form_template_key`). Não há
   como declarar que uma atividade futura representa outro tipo de interação (uma
   decisão/parecer, uma tarefa de coordenação externa, ou um marcador reservado para
   fase futura), o que forçaria cada fase nova a improvisar um encaixe dentro do modelo
   de formulário ou a criar um caminho paralelo — o que a Constituição do projeto proíbe.

Esta spec entrega a correção mínima e real dessas duas lacunas (o "Plano B" discutido),
e valida o mecanismo de ponta a ponta, com a API real, acrescentando uma segunda fase de
exemplo — sem nenhuma regra de negócio inventada das fases futuras — a um dos métodos já
oficialmente ativos (`validated_method_dossier`, Spec 011), pelo mesmo padrão já usado
para validar o pipeline de avaliação por IA (Spec 013) diretamente nesse método.

**Decisão registrada nesta revisão**: ao contrário da primeira redação desta spec, que
prescrevia um template de demonstração isolado, ficou decidido reaproveitar um método
oficial ativo para a validação, aceitando que a fase de exemplo fique visível para
instâncias reais criadas a partir da nova versão desse template. O risco de afetar
retroativamente processos já em andamento é mitigado pela própria garantia de
imutabilidade de versão da Spec 004 (FR-001/SC-002): a fase de exemplo só é introduzida
publicando uma **nova versão** do template (`version_number` incrementado), nunca
sobrescrevendo a versão já usada por instâncias existentes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar o roteiro completo de uma instância de processo (Priority: P1)

Como participante autorizado de um processo (proponente no escopo de sua própria
submissão, ou membro do grupo gestor/BraCVAM), quero consultar o roteiro completo de
fases e atividades declaradas para a minha instância — incluindo as que ainda não
começaram — com o status atual de cada uma, para sempre saber o que vem a seguir e por
que algo está bloqueado, sem depender de inferência a partir de uma lista de tarefas
incidental.

**Why this priority**: resolve diretamente a fragilidade atual (inferir a estrutura via
tarefas) e é pré-requisito para qualquer tela de acompanhamento genérica no frontend; sem
isso, cada fase futura força uma nova solução improvisada no cliente.

**Independent Test**: Um usuário autorizado consulta o roteiro de uma instância existente
criada a partir de qualquer template ativo. Vê todas as fases e atividades declaradas na
versão do template usada, cada uma com seu status (`BLOCKED`, `READY`, `IN_PROGRESS`,
`WAITING_APPROVAL`, `COMPLETED` ou equivalente) e, quando bloqueada, o motivo textual —
a mesma garantia já existente para consulta individual de atividade (Spec 004 FR-007),
agora agregada para a instância inteira em uma única consulta.

**Acceptance Scenarios**:

1. **Given** uma instância de processo com a Fase 1 em andamento, **When** um participante
   autorizado consulta o roteiro da instância, **Then** o sistema retorna todas as fases e
   atividades declaradas na versão do template, cada uma com seu status atual, mesmo as
   que ainda não têm nenhuma execução ou tarefa criada.
2. **Given** uma atividade bloqueada por dependência não satisfeita, **When** o roteiro é
   consultado, **Then** o item correspondente aparece com status `BLOCKED` e o motivo
   textual da dependência faltante, sem exigir uma segunda consulta a outro recurso.
3. **Given** um usuário sem participação autorizada na instância, **When** ele tenta
   consultar o roteiro, **Then** o sistema nega a operação seguindo o mesmo escopo de
   leitura já aplicado às demais consultas do processo (Spec 009 FR-009, Spec 006).

---

### User Story 2 - Declarar atividades que não são formulário (Priority: P2)

Como equipe responsável por evoluir o pipeline de validação para as fases futuras
(Planejamento, Execução, Revisão, Deliberação), quero declarar, para cada atividade de um
template de processo, que tipo de interação ela representa (coleta de dados estruturados,
decisão/parecer, tarefa externa/coordenação, ou marcador reservado), para que novas fases
possam ser adicionadas ao pipeline por declaração, em vez de exigir um encaixe forçado no
modelo de formulário toda vez que surgir um tipo de etapa diferente.

**Why this priority**: sem um tipo declarado, toda etapa futura é presumida como
formulário, o que não se sustenta para Planejamento/Execução; esta é a correção
estrutural que permite ao frontend generalizar a renderização das atividades.

**Independent Test**: Um template é definido com ao menos uma atividade de tipo diferente
de "coleta de dados estruturados", sem formulário associado. Instanciar um processo a
partir dele tem sucesso, produz a atividade no roteiro com seu tipo declarado e status
inicial, sem gerar formulário nem exigir valores de campo, e sem alterar o comportamento
de nenhuma atividade que permaneça do tipo formulário.

**Acceptance Scenarios**:

1. **Given** um template com uma atividade classificada como decisão/parecer, **When** um
   processo é instanciado a partir dele, **Then** o sistema cria a atividade normalmente,
   sem exigir nem criar um `FormInstance` para ela.
2. **Given** uma atividade sem classificação explícita (templates já existentes das Specs
   004/009/011/015), **When** o roteiro é consultado, **Then** o sistema apresenta essa
   atividade com a classificação padrão de coleta de dados estruturados, preservando o
   comportamento atual sem exigir migração de dados.
3. **Given** um template com atividades de tipos variados, **When** uma delas depende da
   conclusão de outra de tipo diferente, **Then** a dependência é avaliada da mesma forma
   já garantida pela Spec 004 (FR-007), independentemente do tipo de cada lado.

---

### User Story 3 - Validar a extensão em um método oficial já ativo (Priority: P3)

Como equipe responsável por evoluir a plataforma com segurança, quero validar de ponta a
ponta — com a API real — que o roteiro dinâmico e os tipos de atividade funcionam para
múltiplas fases e tipos diferentes, acrescentando uma segunda fase de exemplo a um dos
métodos oficiais já ativos, para que a arquitetura do roteiro possa ser construída e
revisada no frontend com confiança antes de a spec de negócio da Fase 2 existir.

**Why this priority**: é o veículo de validação/demonstração das User Stories 1 e 2, não
uma capacidade que o usuário final precisa diretamente — mas é o critério de aceite
esperado pela Constituição do projeto (demonstração como critério de conclusão).

**Independent Test**: Alguém revisando a entrega abre uma página de demonstração dedicada
que instancia um processo a partir da nova versão do método oficial escolhido, avança até
a decisão de triagem aprovada, e observa a segunda fase de exemplo sair de bloqueada para
disponível, com um tipo de atividade diferente de formulário — usando exclusivamente
chamadas à API real do backend.

**Acceptance Scenarios**:

1. **Given** a nova versão publicada do método oficial escolhido, **When** um processo é
   instanciado a partir dela na página de demonstração, **Then** o roteiro exibe as duas
   fases e os tipos de atividade declarados, com a segunda fase bloqueada até a primeira
   ser concluída.
2. **Given** uma instância criada antes desta mudança, a partir da versão anterior do
   mesmo método, **When** seu roteiro é consultado, **Then** ela continua exibindo apenas
   a Fase 1, sem a fase de exemplo introduzida por esta spec.
3. **Given** a demonstração publicada, **When** ela é executada, **Then** todas as
   chamadas usam a API real do backend (sem endpoint criado exclusivamente para viabilizar
   a demonstração), conforme exigido pela Constituição do projeto.

---

### Edge Cases

- O que acontece quando o tipo declarado de uma atividade é desconhecido para a versão do
  cliente que consulta o roteiro? A atividade deve continuar aparecendo com seu status,
  permitindo que o cliente trate o tipo desconhecido de forma genérica, em vez de a
  consulta falhar ou omitir o item.
- O que acontece com instâncias já criadas a partir dos templates existentes quando esta
  extensão é introduzida? Suas atividades continuam funcionando com a classificação
  padrão de formulário, sem mudança de comportamento e sem exigir preenchimento
  retroativo de dado algum.
- O que acontece com uma instância real já aprovada na triagem (estado `PLANNING`) antes
  desta mudança, quando a nova versão do template é publicada? Ela permanece vinculada à
  versão anterior (sem a fase de exemplo) e não sofre nenhuma alteração retroativa.
- O que acontece se uma versão posterior de um template alterar o tipo declarado de uma
  atividade? Instâncias já criadas a partir da versão anterior mantêm o tipo declarado na
  versão em que foram instanciadas, seguindo a mesma imutabilidade de versão já garantida
  pela Spec 004 (FR-001 e edge case correspondente).
- O que acontece com uma atividade de tipo diferente de formulário que precisa registrar
  um resultado (ex.: uma decisão)? Fora do escopo desta spec — o registro de um resultado
  de negócio para tipos não-formulário pertence à spec que definir a regra real da fase
  correspondente; aqui a atividade existe apenas como nó do roteiro, rastreável e
  auditável.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir consultar, para uma instância de processo, o
  conjunto completo de fases e atividades declaradas na versão do template utilizada —
  incluindo as que ainda não começaram — junto com o status atual de cada uma.
- **FR-002**: Para cada atividade retornada nessa consulta, quando ela estiver bloqueada,
  o sistema DEVE incluir o motivo textual do bloqueio, consistente com a garantia já
  estabelecida para consulta individual de atividade (Spec 004 FR-007).
- **FR-003**: O sistema DEVE classificar toda atividade declarada em um template de
  processo com um tipo explícito que descreva a natureza da interação que ela representa.
- **FR-004**: O sistema DEVE suportar, no mínimo, as seguintes classificações de
  atividade: coleta de dados estruturados (formulário), decisão/parecer, tarefa
  externa/coordenação e marcador reservado para fase futura.
- **FR-005**: Quando uma atividade não for classificada como coleta de dados
  estruturados, o sistema DEVE permitir instanciá-la e acompanhá-la (status, bloqueio,
  tarefas) sem exigir uma definição de formulário associada e sem gerar `FormInstance`.
- **FR-006**: Atividades sem classificação previamente declarada (templates e instâncias
  já existentes) DEVEM assumir a classificação padrão de coleta de dados estruturados,
  preservando o comportamento atual sem exigir migração de dados existentes.
- **FR-007**: O sistema DEVE permitir publicar uma nova versão de um método oficial já
  ativo contendo, além da Fase 1 já suportada, uma segunda fase de exemplo com ao menos
  uma atividade de tipo diferente de formulário, exclusivamente para validar de ponta a
  ponta o mecanismo de roteiro e de tipos de atividade.
- **FR-008**: A publicação dessa nova versão NÃO DEVE alterar nem reinterpretar a versão
  do template já vinculada a instâncias existentes — toda instância criada antes da
  publicação permanece exatamente como estava, sem a fase de exemplo.
- **FR-009**: Todos os eventos de ciclo de vida (criação, transição de status) de
  atividades de qualquer tipo DEVEM continuar sendo registrados na trilha de auditoria
  imutável já exigida para o processo (Spec 004 FR-011), independentemente da
  classificação introduzida por esta feature.
- **FR-010**: O comportamento existente dos cinco métodos oficialmente suportados (Spec
  011/015), da triagem, do preenchimento de formulário, dos anexos (Spec 016) e da
  autorização (Spec 003/006/009/014) DEVE permanecer inalterado para toda atividade que
  mantenha a classificação de coleta de dados estruturados.

### Key Entities

- **Atividade (`ActivityInstance`)**: passa a carregar um atributo de classificação (tipo
  de interação), além dos atributos já existentes (chave, nome, ordem, status, motivo de
  bloqueio) definidos na Spec 004.
- **Roteiro do processo**: visão agregada, por instância, de todas as fases e atividades
  declaradas na versão do template usada, decoradas com o estado atual de cada uma. Não é
  uma entidade de persistência nova — é uma composição das entidades já existentes
  (`Phase`, `ActivityInstance`) definidas na Spec 004.
- **Nova versão do método oficial**: uma `ProcessTemplateVersion` adicional do template
  `validated_method_dossier` (Spec 011), com a Fase 1 inalterada mais uma fase de exemplo,
  cuja finalidade é validar a mecânica de roteiro e de tipos de atividade antes de existir
  uma spec de negócio para a Fase 2 — sem afetar instâncias vinculadas à versão anterior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das instâncias, existentes ou novas, a consulta do roteiro completo
  revela todas as fases e atividades declaradas no template, mesmo as que ainda não têm
  nenhuma tarefa ou execução iniciada.
- **SC-002**: Times de frontend/produto conseguem representar visualmente um roteiro de
  mais de uma fase, incluindo ao menos um tipo de atividade diferente de formulário,
  usando apenas dados retornados pela API real, sem inferir a estrutura a partir de listas
  de tarefas.
- **SC-003**: 100% dos cenários automatizados existentes das Specs 004, 009, 011-016
  continuam passando após a introdução da classificação de atividades e do roteiro
  agregado.
- **SC-004**: 100% das instâncias criadas antes da publicação da nova versão do template
  continuam exibindo apenas a Fase 1 ao terem seu roteiro consultado, sem nenhuma alteração
  retroativa.
- **SC-005**: Uma nova fase futura (por exemplo, Planejamento) pode ser declarada usando
  os tipos de atividade já suportados por esta spec sem exigir alteração no formato da
  consulta de roteiro nem no modelo de dados aqui introduzido.

## Assumptions

- A Spec 004 e suas sucessoras (006, 009, 011-016) permanecem a base reutilizada; esta
  spec não cria um modelo paralelo de processos, fases, atividades ou tarefas.
- As regras de negócio reais das fases futuras (Planejamento, Execução Interlaboratorial,
  Revisão Técnica, Deliberação Final) continuam fora de escopo; esta spec entrega apenas
  o mecanismo de extensibilidade e sua validação, não o conteúdo de nenhuma fase futura.
- A demonstração desta spec segue as regras de demonstração do projeto (páginas em
  `demos/`, seed dedicado em `scripts/seeds/`, desacoplado do núcleo) e não introduz
  nenhum endpoint cujo único propósito seja viabilizá-la.
- A autorização e o escopo de leitura/gravação já estabelecidos (Spec 003 RBAC, Spec 006
  participantes, Spec 009 escopo do proponente, Spec 014 triagem BraCVAM) aplicam-se sem
  alteração às atividades de qualquer classificação.
- A classificação de atividade é definida na origem declarativa do template (o mesmo
  mecanismo de seed já usado desde a Spec 004) e permanece imutável para instâncias já
  criadas, seguindo a mesma regra de vínculo de versão da Spec 004.
- A fase de exemplo é publicada como uma nova versão do template `validated_method_dossier`
  (Spec 011), reaproveitando o mesmo método que já serve de veículo para validar outras
  capacidades novas da plataforma (ex.: avaliação por IA, Spec 013). Isso significa que
  instâncias reais criadas a partir dessa nova versão passarão a exibir a fase de exemplo;
  o risco correspondente é aceito nesta spec e mitigado apenas pela imutabilidade de
  versão (instâncias anteriores não são afetadas), não pelo isolamento do template.

## Dependencies

- **Spec 004 — Estrutura Base de Processos e Fase 1**: fornece `Phase`,
  `ActivityInstance`, `ActivityRun`, `Task`, `FormTemplate`/`FormInstance` e o motor de
  instanciação, reutilizados integralmente por esta spec.
- **Spec 009 — Submissão de Método Alternativo**: fornece o padrão de escopo de leitura
  por participação que continua se aplicando à consulta do roteiro agregado.
- **Spec 011 — Templates Oficiais do BraCVAM**: define os cinco métodos reais cujo
  comportamento não pode regredir com a introdução da classificação de atividade; esta
  spec publica uma nova versão do método `validated_method_dossier` definido ali.
- **Spec 013 — Avaliação Configurável por IA**: precedente de reaproveitar esse mesmo
  método oficial (`validated_method_dossier`) como veículo de validação de uma capacidade
  nova da plataforma, em vez de um template isolado.
- **Spec 014 — Autorização de Triagem BraCVAM**: define quem pode agir sobre atividades de
  triagem, papel que se estende à leitura de atividades de outros tipos no roteiro.
- **Spec 016 — Anexos de Formulário**: referência de como uma capacidade adicional foi
  introduzida sem quebrar a estrutura de atividades existente — o mesmo padrão de
  compatibilidade é esperado aqui.

## Out of Scope

- Qualquer regra de negócio das fases de Planejamento, Execução Interlaboratorial,
  Revisão Técnica ou Deliberação Final.
- A interface de usuário final do roteiro no frontend consumidor — esta spec entrega
  apenas o contrato de dados que a viabiliza, não a tela em si.
- Novas permissões ou papéis de RBAC além dos já existentes.
- Um editor administrativo para configurar tipos de atividade (equivalente ao editor de
  formulários da Spec 012) — a classificação desta spec é provisionada apenas via seed
  declarativo.
