# Feature Specification: 009 - Submissão de Método Alternativo

**Feature Branch**: `feat/009-alternative-method-submission`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Implementar exclusivamente o RF007 — Submissão de método alternativo — com cadastro estruturado das informações técnicas e científicas, reutilização da infraestrutura da Feature 004, associação do proponente, formulário definido por configuração persistida, validação estrita e autorização contextual conforme RF004."

## Clarifications

### Session 2026-09-03

- **Q1: Relação entre `crCode` e processo**
  - **Decisão**: `ProcessInstance.code` representa o `crCode` do método submetido. A feature preserva um único identificador para a submissão e sua instância de processo, sem criar um identificador paralelo.
- Q: O proponente pode salvar informações parciais durante a elaboração da submissão? → A: Sim. O proponente pode registrar valores parciais durante a elaboração; o sistema valida tipo, opções e limites dos valores fornecidos, e RF014 definirá a exigência de completude para o envio formal.
- Q: Durante o RF007, quais participantes podem consultar uma submissão em elaboração? → A: Somente o proponente ativo pode consultar e gravar sua própria submissão durante a elaboração.

## Current Coverage and Minimal Gap

### CONFIRMADO

- A Feature 004 já permite que um usuário autenticado crie uma instância de processo a partir de uma definição ativa e versionada, cria as atividades e execuções configuradas e associa o criador como proponente local do processo ([processes.py](../../src/pivma/routers/processes.py), [process_engine.py](../../src/pivma/core/process_engine.py), [test_process_router.py](../../tests/api/routers/test_process_router.py)).
- A Feature 004 já obtém a definição do formulário e seus campos do cadastro persistido, cria o preenchimento ligado à execução da atividade e persiste valores estruturados por campo ([forms.py](../../src/pivma/routers/forms.py), [process_engine.py](../../src/pivma/core/process_engine.py), [full_validation_v1.yaml](../../src/pivma/templates_data/full_validation_v1.yaml)).
- A Feature 006 disponibiliza a participação local no processo e uma verificação de escopo de leitura baseada em designações ([authorization.py](../../src/pivma/core/authorization.py), [test_participant_authorization.py](../../tests/integration/database/test_participant_authorization.py)).

### ATENDE PARCIALMENTE

- A validação atual verifica a presença de campos obrigatórios na conclusão do formulário, mas não aplica de modo completo tipos, opções e demais regras definidas para cada campo.
- As operações atuais exigem autenticação, mas as consultas de processos e as leituras e mutações de formulário não restringem todas as operações pela participação do usuário no processo.
- **LACUNA IDENTIFICADA, FORA DO ESCOPO DE RF007**: `GET /tasks` e `GET /tasks/{id}` (Feature 004) listam e detalham tarefas de qualquer processo para qualquer usuário autenticado, sem verificar participação. RF007 não usa esses endpoints em sua sequência documentada em `contracts/submission-api.md` e o plano desta feature não altera `routers/tasks.py`; corrigir essa lacuna exige decisão de escopo própria (provavelmente junto de RF009 ou de uma feature de tarefas), não uma extensão silenciosa de RF007.

### MENOR IMPLEMENTAÇÃO ADICIONAL NECESSÁRIA

- Aplicar o escopo de participação existente à consulta da submissão, à consulta do formulário e à gravação de seus valores.
- Rejeitar campos desconhecidos e valores incompatíveis com o tipo, as opções e as regras declaradas na definição persistida.
- Garantir que o cadastro coberto por RF007 permaneça em elaboração e não dependa de documentos nem produza o envio formal para análise.
- Preservar a infraestrutura e os contratos já adequados da Feature 004, sem criar um segundo modelo de processos, formulários, execuções ou atribuições.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Iniciar e registrar uma proposta (Priority: P1)

Como proponente autenticado, quero iniciar uma submissão de método alternativo e registrar suas informações técnicas e científicas em campos estruturados, para que a proposta fique identificada e pronta para continuidade posterior.

**Why this priority**: RF007 estabelece a entrada do método no sistema. Sem a instância, o proponente e os dados estruturados, nenhuma etapa posterior pode operar sobre a proposta.

**Independent Test**: Um usuário autenticado inicia uma proposta usando uma definição disponível, registra valores válidos e consulta a proposta resultante. O cadastro apresenta identificação única, associa o usuário como proponente e conserva os valores por campo sem iniciar triagem.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado e uma definição ativa de submissão, **When** ele inicia uma nova proposta, **Then** o sistema cria uma única instância vinculada à versão vigente da definição, atribui uma identificação única e registra o usuário como proponente.
2. **Given** uma proposta em elaboração pertencente ao proponente, **When** ele informa valores parciais compatíveis com os campos técnicos e científicos apresentados, **Then** o sistema persiste cada valor em seu campo correspondente e devolve o conteúdo registrado.
3. **Given** uma proposta criada no escopo do RF007, **When** o proponente registra as informações estruturadas, **Then** o sistema mantém a proposta em elaboração, sem exigir documento e sem encaminhá-la para triagem ou análise.

---

### User Story 2 - Consultar o formulário definido para a proposta (Priority: P2)

Como proponente ativo da submissão, quero consultar os campos, orientações, opções e regras do formulário aplicável, para fornecer as informações esperadas sem depender de um conjunto fixo de campos na aplicação.

**Why this priority**: A definição persistida é a fonte dos dados solicitados e das validações. Isso preserva a estrutura científica configurada para a versão usada pela proposta.

**Independent Test**: O proponente ativo consulta uma proposta e recebe a definição persistida do formulário na ordem configurada, junto com os valores já registrados.

**Acceptance Scenarios**:

1. **Given** uma submissão associada a um formulário persistido, **When** o proponente consulta o formulário, **Then** o sistema apresenta somente os campos ativos daquela definição, na ordem configurada, com tipo, obrigatoriedade, opções, orientações e regras declaradas.
2. **Given** valores já registrados em campos da proposta, **When** o proponente consulta o formulário, **Then** o sistema retorna cada valor associado à chave do campo definido para aquela instância.
3. **Given** uma alteração posterior na definição disponível para novas propostas, **When** o proponente consulta uma proposta existente, **Then** o sistema preserva a definição aplicável à instância já iniciada.

---

### User Story 3 - Impedir dados inválidos e acesso indevido (Priority: P3)

Como proponente, quero que o sistema rejeite conteúdo incompatível com o formulário e impeça terceiros de acessar minha proposta, para preservar a integridade e a confidencialidade da submissão.

**Why this priority**: Dados aceitos sem validação comprometem o cadastro científico, e autenticação sem autorização contextual expõe propostas por enumeração de identificadores.

**Independent Test**: O teste envia campos desconhecidos, tipos e opções inválidos e tenta consultar ou alterar a proposta com outro usuário autenticado. O sistema rejeita cada tentativa sem persistir mudanças ou revelar o conteúdo protegido.

**Acceptance Scenarios**:

1. **Given** um formulário persistido, **When** o proponente envia uma chave que não pertence à definição, **Then** o sistema rejeita a operação inteira, identifica o campo desconhecido e não persiste nenhum valor do pedido.
2. **Given** um campo com tipo, opções ou limites declarados, **When** o proponente envia um valor incompatível, **Then** o sistema rejeita a operação inteira, identifica a violação e preserva os valores anteriores.
3. **Given** um usuário autenticado sem participação autorizada na proposta, **When** ele tenta localizar, consultar ou alterar a submissão usando o identificador do processo ou do formulário, **Then** o sistema nega a operação sem expor os dados protegidos.
4. **Given** um usuário que possui apenas um perfil global e nenhuma participação autorizada na proposta, **When** ele tenta consultar ou alterar a submissão, **Then** o sistema aplica a mesma negação contextual.
5. **Given** um participante local cujo papel não autoriza a gravação da proposta, **When** ele tenta alterar os valores do formulário, **Then** o sistema nega a operação e preserva o conteúdo anterior.

### Edge Cases

- Duas solicitações de criação não podem receber a mesma identificação, inclusive quando ocorrem ao mesmo tempo.
- Uma falha ao criar o processo, atribuir o proponente ou preparar o formulário não pode deixar uma submissão parcial acessível.
- Um pedido que combina valores válidos e inválidos deve falhar por inteiro.
- Ausência, valor nulo, cadeia vazia e zero devem ser tratados conforme o tipo e a regra declarada do campo; zero e `false` não podem ser confundidos com ausência quando forem valores válidos.
- Uma opção de seleção deve corresponder a um valor configurado na definição aplicável.
- Uma designação revogada, excluída ou ineficaz não concede acesso à submissão.
- A consulta de listas não pode revelar submissões sem participação autorizada nem incluí-las na contagem ou paginação retornada.
- Uma definição ausente, inativa ou sem formulário aplicável deve impedir a criação completa e informar que a submissão não pode ser iniciada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir que um usuário autenticado inicie uma nova submissão de método alternativo a partir de uma definição de processo ativa e disponível para esse fim.
- **FR-002**: Cada nova submissão DEVE criar uma única instância de processo vinculada à versão da definição usada no momento da criação.
- **FR-003**: O sistema DEVE associar o usuário que iniciou a submissão como proponente ativo daquele processo e registrar a atribuição de forma auditável.
- **FR-004**: O sistema DEVE obter o formulário da submissão e seus campos da definição persistida aplicável à instância, sem depender de campos científicos ou técnicos fixados no ponto de entrada da operação.
- **FR-005**: Durante a elaboração coberta por RF007, o sistema DEVE permitir que somente o proponente ativo consulte a definição aplicável do formulário e os valores já registrados na própria submissão.
- **FR-006**: O sistema DEVE aceitar valores estruturados identificados pelas chaves dos campos definidos e persistir cada valor com vínculo ao campo, ao formulário, à atividade e à instância de processo correspondentes.
- **FR-007**: Durante a elaboração coberta por RF007, o sistema DEVE aceitar valores parciais e validar cada valor fornecido conforme o tipo, as opções e as regras declaradas na definição persistida do campo. A exigência de completude dos campos obrigatórios pertence ao envio formal definido em RF014.
- **FR-008**: O sistema DEVE rejeitar a operação completa quando ela contiver campo desconhecido ou valor incompatível e não DEVE persistir parcialmente os demais valores do mesmo pedido.
- **FR-009**: Durante a elaboração coberta por RF007, o sistema DEVE restringir a listagem, a consulta da submissão, a consulta do formulário e toda mutação de seus valores ao proponente ativo e eficaz da própria submissão. Conhecer o identificador, possuir apenas um perfil global ou participar com outro papel não DEVE conceder acesso.
- **FR-010**: Somente o proponente ativo da submissão DEVE poder registrar ou substituir os valores do formulário durante a elaboração coberta por RF007.
- **FR-011**: As respostas negadas por falta de autorização contextual NÃO DEVEM revelar o conteúdo, os valores, a definição do formulário nem a existência de dados protegidos além do necessário para informar a negação.
- **FR-012**: Cada método submetido DEVE receber um `crCode` único, armazenado como código de sua instância de processo, sem a criação de um identificador paralelo para o método.
- **FR-013**: A criação da submissão, a atribuição do proponente e a preparação do formulário inicial DEVEM produzir um resultado atômico: todos os registros necessários ficam disponíveis juntos ou nenhum deles fica disponível.
- **FR-014**: As operações de criação e gravação DEVEM registrar o autor, a data, a submissão e o resultado necessários à rastreabilidade.
- **FR-015**: O cadastro coberto por RF007 DEVE permanecer em elaboração e NÃO DEVE, por si só, encaminhar a proposta para triagem ou análise.
- **FR-016**: O cadastro coberto por RF007 NÃO DEVE exigir nem simular a anexação de documentos.
- **FR-017**: A feature DEVE reutilizar o motor de processos, as definições e instâncias de processo, atividades, execuções, formulários, valores e atribuições existentes, sem introduzir abstrações paralelas para representar os mesmos conceitos.

### Scope Boundaries

- **Incluído**: criação da submissão; associação do proponente; identificação única; leitura contextual; registro estruturado; validação determinística baseada na definição persistida; auditoria das operações introduzidas ou consolidadas.
- **Excluído**: upload ou gestão de documentos (RF008 e RF012); regras completas de edição por estado ou ciclo (RF009); versionamento da submissão (RF010); notificações (RF011); IA (RF013); envio formal para análise (RF014); triagem e fases posteriores; configuração administrativa de formulários.

### Key Entities *(include if feature involves data)*

- **Método submetido**: proposta científica individualizada que entra no sistema e recebe a identificação única definida pelo domínio.
- **Instância de processo**: execução concreta criada para a submissão, vinculada à versão da definição vigente no início.
- **Proponente**: usuário autenticado que inicia a submissão e recebe participação local ativa no processo.
- **Definição de formulário e campo**: configuração persistida que determina quais informações podem ser registradas e quais regras cada valor deve cumprir.
- **Preenchimento e valor de campo**: conteúdo estruturado registrado para a proposta, ligado à definição aplicável e à execução da atividade.
- **Participação no processo**: vínculo local que concede ao usuário autorizado o escopo para consultar ou operar sobre a submissão.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das criações bem-sucedidas, a submissão recebe uma identificação única, conserva a versão da definição usada e possui exatamente uma participação ativa do criador como proponente.
- **SC-002**: Em 100% dos formulários consultados, os campos, a ordem, os tipos, as opções e as regras apresentados correspondem à definição persistida aplicável à submissão.
- **SC-003**: Em 100% dos pedidos com campos desconhecidos ou valores incompatíveis, o sistema rejeita o pedido inteiro e preserva o estado anterior da submissão.
- **SC-004**: Em 100% das tentativas feitas por usuários autenticados sem participação ativa e eficaz, o sistema impede listagem, consulta e mutação dos dados da submissão.
- **SC-005**: Um proponente consegue iniciar a submissão e registrar um conjunto válido de informações técnicas e científicas em até 3 minutos, sem anexar documentos e sem iniciar uma etapa posterior.
- **SC-006**: Todos os cenários automatizados existentes da infraestrutura de processos e formulários continuam atendidos após a consolidação do RF007, salvo contratos que conflitem de forma explícita com os limites desta especificação.

## Assumptions

- A autenticação, o motor de processos e a infraestrutura de formulários e participações das Features 002, 004 e 006 permanecem disponíveis e serão reutilizados.
- RF007 cobre o primeiro registro estruturado enquanto a proposta está em elaboração. RF009 definirá quando e como o proponente poderá editar o conteúdo ao longo dos estados posteriores.
- O proponente pode registrar valores parciais durante a elaboração. RF014 definirá a verificação de todos os campos obrigatórios no envio formal.
- RF014 definirá a ação de envio formal e seus efeitos no estado do processo. RF007 não conclui a atividade de submissão nem libera triagem.
- `ProcessInstance.code` representa o `crCode` do método submetido; a feature preserva um único identificador para o método e sua instância de processo.
- A participação autorizada exige uma designação local ativa e eficaz. No RF007, somente o proponente pode ler e gravar sua submissão; esta feature não concede acesso a participantes em outros papéis.
- O formulário aplicável já foi criado e publicado por mecanismos existentes. A administração dessas definições pertence a outra feature.
- Campos de documento presentes em definições existentes não integram os dados exigidos por RF007 e não podem bloquear o cadastro estruturado coberto por esta feature.

## Dependencies and Traceability

- **RF007 — Submissão de método alternativo**: requisito funcional principal; fundamenta o cadastro estruturado das informações técnicas e científicas.
- **RF004 — Controle de acesso**: requisito transversal; fundamenta o bloqueio de consultas e mutações quando o usuário não participa do processo.
- **Feature 004 — Estrutura Base de Processos e Fase 1**: dependência existente para instâncias, atividades, execuções, formulários e persistência estruturada.
- **Feature 006 — Designação de Participantes**: dependência existente para participação local e seu escopo de autorização.
