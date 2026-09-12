# Feature Specification: Atualização de Instância de Submissão

**Feature Branch**: `021-update-process-submission`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "fazer a feature #15 usando boas praticas. O PUT e o PATCH devem contemplar todos os campos do template de submissao selecionado. Arquiteture de uma aforma simples, nao aumente o escopo da complexidade. Essa fix DEVE contemplar tudo que é necessário em um endpoint desse tipo para um sistema."

## Contexto e classificação

- **CONFIRMADO**: a issue #15 requer atualização total e parcial de instâncias de processo, autorização para o criador ou a gestão BraCVAM, bloqueio em estados terminais e auditoria.
- **CONFIRMADO**: cada instância de submissão está associada a um template de formulário que define seus campos e regras.
- **CONFIRMADO**: quando uma decisão solicita revisão, o workflow já abre uma nova execução numerada da submissão e pré-carrega nela os valores da execução anterior.
- **PROPOSTA desta feature**: a atualização da instância engloba o título editável e os valores dos campos do formulário de submissão somente na execução atual ainda não submetida; não altera o template, a identidade, o responsável, o fluxo ou o histórico da instância.
- **PROPOSTA desta feature**: uma submissão devolvida para revisão possui uma versão histórica imutável, identificada pelo número da execução, com o conteúdo que foi formalmente enviado e a justificativa da devolução.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Substituir uma submissão completa (Priority: P1)

Como proponente responsável por uma submissão em elaboração, quero substituir de uma só vez seu título e todos os valores editáveis definidos no template selecionado, para corrigir ou consolidar o rascunho sem deixar uma mistura não intencional entre o conteúdo anterior e o novo.

**Why this priority**: A atualização integral dá ao proponente um modo determinístico de salvar uma versão completa do rascunho, independentemente da quantidade e dos tipos de campos do template escolhido.

**Independent Test**: Criar uma submissão a partir de um template com campos de tipos distintos, preencher todos os campos editáveis e executar uma atualização integral com outro título e um novo conjunto completo de valores. A consulta posterior exibe somente o estado enviado, conforme as regras do template associado à instância.

**Acceptance Scenarios**:

1. **Given** uma submissão editável cujo template possui campos de texto, seleção, número, data e booleano, **When** o responsável envia uma atualização integral com título e valores para todos esses campos, **Then** a instância passa a apresentar exatamente o título e os valores válidos informados.
2. **Given** uma submissão cujo template possui um campo opcional sem valor, **When** o responsável envia atualização integral declarando esse campo sem valor, **Then** qualquer valor anterior desse campo é removido e os demais valores válidos são preservados conforme o pedido.
3. **Given** uma atualização integral com um campo obrigatório ausente, desconhecido ou inválido, **When** o pedido é processado, **Then** ele é recusado, nenhum dado da instância é alterado e a resposta identifica os campos que exigem correção.

---

### User Story 2 - Corrigir parte de uma submissão (Priority: P2)

Como proponente responsável ou gestor BraCVAM autorizado, quero alterar somente o título ou os campos necessários de uma submissão, para corrigir informações pontuais sem reenviar dados que não mudaram.

**Why this priority**: Correções pequenas são frequentes e devem respeitar a mesma definição dinâmica de formulário sem exigir uma atualização integral desnecessária.

**Independent Test**: Em uma submissão com vários valores previamente gravados, alterar apenas um campo e, em outro pedido, apenas o título. A consulta confirma que somente os atributos solicitados mudaram.

**Acceptance Scenarios**:

1. **Given** uma submissão editável com valores já gravados, **When** um usuário autorizado altera apenas um campo existente do template, **Then** apenas esse campo muda e todos os demais valores permanecem inalterados.
2. **Given** uma submissão editável, **When** um usuário autorizado altera apenas o título para um valor válido, **Then** os valores do formulário permanecem inalterados.
3. **Given** uma alteração parcial que inclui uma chave ausente do template ou um valor incompatível com sua definição, **When** o pedido é processado, **Then** ele é recusado integralmente sem gravar nem mesmo os campos válidos enviados junto dele.

---

### User Story 3 - Consultar submissões devolvidas (Priority: P3)

Como responsável por uma etapa posterior do processo, quero visualizar por padrão a versão mais recente da submissão e, quando necessário, abrir as versões que foram devolvidas para ajustes, para entender a evolução da proposta e as justificativas sem confundir conteúdo histórico com o conteúdo vigente.

**Why this priority**: A devolução para revisão perde valor de governança se o conteúdo rejeitado puder ser sobrescrito ou não puder ser confrontado com o reenvio posterior.

**Independent Test**: Submeter uma proposta, devolvê-la para revisão, alterar seu título e valores na nova execução, reenviá-la e consultar o processo como responsável da etapa seguinte. A consulta padrão mostra o reenvio mais recente; a consulta histórica mostra a primeira versão, seu conteúdo congelado e a justificativa da devolução.

**Acceptance Scenarios**:

1. **Given** uma submissão devolvida para revisão, **When** o proponente altera e reenvia a nova execução, **Then** o conteúdo que havia sido enviado antes da devolução permanece disponível como versão histórica e não é alterado pelo reenvio.
2. **Given** um responsável autorizado consulta uma proposta que possui versões, **When** abre a visão padrão da submissão, **Then** vê a versão mais recente formalmente enviada ou em elaboração, conforme o estado atual do processo.
3. **Given** um responsável autorizado consulta o histórico, **When** seleciona uma versão devolvida, **Then** vê seu número, momento do envio, conteúdo congelado e justificativa da devolução, sem possibilidade de edição.
4. **Given** uma pessoa sem permissão para consultar o processo ou seu conteúdo histórico, **When** tenta acessar versões devolvidas, **Then** o sistema impede o acesso sem ampliar a visibilidade existente.

---

### User Story 4 - Proteger a integridade da submissão (Priority: P4)

Como gestor do sistema, quero que atualizações de submissões ocorram somente por pessoas autorizadas, em estados que permitem edição, e deixem evidência rastreável, para que o conteúdo científico e o histórico do processo permaneçam confiáveis.

**Why this priority**: A edição de uma instância pode alterar informações submetidas; autorização, regras de estado, validação e auditoria são indispensáveis para um endpoint seguro e operável.

**Independent Test**: Tentar atualizar a mesma instância como terceiro não autorizado e após ela chegar a estado terminal; depois consultar a trilha de uma atualização válida. As tentativas proibidas não alteram dados e a alteração válida contém autor, momento, modo de atualização e campos afetados.

**Acceptance Scenarios**:

1. **Given** um usuário que não é o criador nem gestor BraCVAM, **When** tenta atualizar uma submissão existente, **Then** o sistema recusa o pedido sem revelar ou modificar dados protegidos.
2. **Given** uma submissão encerrada ou cancelada, **When** até mesmo seu criador ou um gestor tenta atualizá-la, **Then** o sistema recusa o pedido e mantém o conteúdo inalterado.
3. **Given** uma atualização válida realizada por um usuário autorizado, **When** ela é concluída, **Then** a linha do tempo registra a operação com o autor, data e hora, modalidade de atualização e os nomes dos atributos alterados, sem registrar valores sensíveis desnecessários.
4. **Given** uma submissão já enviada formalmente, **When** seu criador ou um gestor tenta atualizar título ou valores, **Then** o sistema recusa o pedido e preserva integralmente a execução submetida.

### Edge Cases

- Um pedido que não contenha nenhum atributo editável é recusado como inválido; ele não produz evento de auditoria nem altera data de atualização.
- A atualização integral não aceita campos adicionais, duplicados ou fora da definição de submissão vinculada à instância.
- Campos de anexo são contemplados pela definição e pela resposta da instância, mas seu conteúdo não é transportado no pedido de atualização de dados; anexar, substituir ou remover arquivo continua no fluxo próprio de anexos. Uma atualização de dados não pode apagar nem substituir anexo por acidente.
- Identificador da instância, código, template e sua versão, estado, criador, participantes, datas de ciclo e decisões de fluxo não são editáveis por nenhum dos dois modos de atualização.
- Se a instância não existir ou não puder ser vista pelo solicitante, a resposta não revela a existência de dados protegidos.
- Se o template associado tiver mudado após a criação da instância, a validação usa a definição histórica associada a essa instância, nunca a versão mais nova do catálogo.
- Se o workflow devolver a proposta para ajustes, ele cria uma nova execução de submissão em elaboração; os pedidos de atualização podem atingir somente essa nova execução, jamais a execução já submetida.
- Uma versão histórica deve conservar também o título que a submissão possuía no momento do envio, ainda que a execução posterior altere o título da instância.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer `PUT` para atualização integral e `PATCH` para atualização parcial de uma instância de processo identificada, retornando a representação atualizada somente após a persistência bem-sucedida.
- **FR-002**: Ambos os modos de atualização DEVEM contemplar o título editável e qualquer campo de dados não-anexo definido no template de submissão associado à instância, sem lista fixa de campos por modalidade de processo.
- **FR-003**: O `PUT` DEVE exigir um título válido e uma representação completa dos valores dos campos de dados não-anexo do template associado. Valores opcionais podem ser explicitamente informados como vazios; campos obrigatórios devem possuir valor válido.
- **FR-004**: O `PATCH` DEVE aceitar somente o título, qualquer subconjunto não vazio de campos do template associado, ou ambos; atributos e valores não enviados devem permanecer inalterados.
- **FR-005**: Para os dois modos, o sistema DEVE validar cada campo informado de acordo com sua definição histórica aplicável, incluindo tipo, obrigatoriedade quando pertinente, opções permitidas, formato, limites e demais regras configuradas.
- **FR-006**: Para os dois modos, o sistema DEVE rejeitar campos desconhecidos, valores para campos de anexo no corpo de dados e tentativas de alterar atributos não editáveis.
- **FR-007**: A validação e a persistência de cada pedido DEVEM ser atômicas: diante de qualquer erro de validação, autorização ou regra de negócio, nenhum título ou valor do pedido pode ser persistido.
- **FR-008**: O sistema DEVE permitir a atualização somente ao criador da instância ou a um usuário com permissão de gestão BraCVAM efetiva no momento do pedido.
- **FR-009**: O sistema DEVE exigir autenticação antes de avaliar uma atualização e não pode confiar em controles de interface como autorização.
- **FR-010**: O sistema DEVE permitir atualização somente enquanto a execução atual da submissão estiver em elaboração e seu formulário ainda não tiver sido submetido. Após o envio formal, deve impedir a alteração de título e de qualquer valor por todos os usuários, inclusive criador e gestão BraCVAM.
- **FR-011**: O sistema DEVE impedir atualização quando a instância estiver em estado terminal, incluindo encerrada ou cancelada, e preservar os dados existentes.
- **FR-012**: Se o workflow iniciar uma nova execução para revisão, o sistema DEVE vincular as atualizações somente a essa execução aberta e manter a execução anterior e seus valores imutáveis.
- **FR-013**: O sistema DEVE preservar o fluxo e a integridade da instância: atualização de conteúdo não pode trocar template ou versão, mudar estado, alterar participantes, criar atividade, concluir submissão nem acionar triagem, avaliações ou notificações.
- **FR-014**: Em uma atualização bem-sucedida, o sistema DEVE registrar evento auditável com identificador da instância, autor, data e hora, modalidade integral ou parcial e a relação de atributos alterados, sem guardar valores de formulário no evento além do que já seja obrigatório para a auditoria existente.
- **FR-015**: O sistema DEVE fornecer erros consistentes e acionáveis: pedido inválido ou semanticamente incompleto, falta de autenticação, falta de autorização, recurso inexistente ou oculto, conflito de estado e falha de validação de campo devem ser distinguíveis pelo consumidor.
- **FR-016**: A resposta de sucesso DEVE conter o estado atualizado do título e dos valores de dados da submissão, além da identificação e do template efetivamente usados, para que o consumidor não precise inferir quais alterações foram aplicadas.
- **FR-017**: A entrega DEVE incluir testes automatizados para atualização integral, atualização parcial, todos os tipos de campo suportados pelo template, limpeza explícita de campo opcional, rejeição atômica, permissões, submissão já enviada, estados terminais, atributos imutáveis e evidência de auditoria.
- **FR-018**: A entrega DEVE incluir demonstração interativa desacoplada do núcleo, no catálogo de `demos/`, e seed mínimo em `scripts/seeds/`, que use a API real para criar uma submissão baseada em template, executar os dois modos de atualização enquanto ela estiver em elaboração e exibir a resposta e a alteração resultante.
- **FR-019**: No envio formal, o sistema DEVE congelar uma versão da submissão que contenha o número sequencial da execução, o título, todos os valores de campos, as referências a anexos aplicáveis e o momento do envio.
- **FR-020**: Quando uma etapa devolver uma submissão para ajustes, o sistema DEVE associar a versão recém-congelada à devolução e à respectiva justificativa, mantendo-a imutável após a abertura e o reenvio de uma nova execução.
- **FR-021**: Atualizações de rascunho por `PUT` ou `PATCH` NÃO DEVEM criar versões históricas. Uma nova versão somente é criada pelo envio formal de uma execução.
- **FR-022**: A consulta padrão de uma submissão DEVE apresentar a versão vigente mais recente para os responsáveis pelas etapas subsequentes, sem exigir que escolham uma versão manualmente.
- **FR-023**: Usuários autorizados a consultar o processo DEVEM poder listar as versões devolvidas e consultar uma versão específica, recebendo seu número, datas relevantes, justificativa de devolução e conteúdo congelado. Versões históricas não podem ser atualizadas pelos endpoints de edição.
- **FR-024**: A visibilidade de versões históricas DEVE obedecer às mesmas regras contextuais de autorização e cegamento aplicáveis ao processo; o histórico não pode conceder acesso a quem não poderia consultar a submissão vigente.
- **FR-025**: A entrega DEVE incluir testes automatizados para congelamento de título, valores e anexos no envio; devolução para revisão; reenvio com conteúdo alterado; visão padrão da versão vigente; consulta autorizada de histórico; e negação de alteração ou leitura não autorizada das versões históricas.

### Scope Boundaries

- **Incluído**: alteração integral ou parcial do título e dos valores dinâmicos de dados exclusivamente na execução de submissão atual e não submetida; congelamento e consulta de versões devolvidas; validação pelo template histórico associado; autorização; bloqueio após envio formal e em estados terminais; respostas de erro; auditoria; testes e demonstração ponta a ponta.
- **Excluído**: edição de templates; criação, remoção ou gestão de anexos; alteração de participantes, template, versão, estado ou workflow; envio formal, triagem, avaliações, notificações; versionamento a cada salvamento de rascunho; comparação visual ou mesclagem entre versões; controle de concorrência além das garantias já presentes no sistema.

### Key Entities *(include if feature involves data)*

- **Instância de processo**: submissão concreta identificada, com título, estado, criador e vínculo imutável ao template e à versão usados na criação.
- **Template de submissão associado**: definição histórica que determina o conjunto de campos, seus tipos e regras aplicáveis à instância.
- **Valor de campo de submissão**: dado estruturado associado a um campo da definição histórica; pode ser substituído integralmente ou alterado pontualmente conforme o modo de atualização.
- **Usuário autorizado**: criador da instância ou gestor BraCVAM com autorização efetiva para alterar seu conteúdo.
- **Evento de auditoria**: registro imutável da atualização efetuada, suficiente para rastrear quem a realizou, quando, de que modo e quais atributos foram afetados.
- **Versão de submissão**: retrato imutável de uma execução formalmente enviada, identificado por seu número sequencial e composto por título, valores, referências de anexos e momento do envio; quando devolvida, inclui a justificativa correspondente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das atualizações integrais válidas testadas para cada template oficial de submissão, o título e todos os campos de dados não-anexo definidos para a instância são retornados com os valores enviados e passam pela validação da definição associada.
- **SC-002**: Em 100% das atualizações parciais válidas testadas, somente os atributos enviados são alterados; todos os demais valores permanecem idênticos ao estado anterior.
- **SC-003**: Em 100% dos pedidos que contenham campo desconhecido, valor inválido, corpo incompleto para atualização integral, atributo imutável ou dados incompatíveis com anexo, nenhuma alteração parcial é persistida.
- **SC-004**: Em 100% das tentativas de usuário não autorizado ou contra instância terminal, o sistema impede a alteração e preserva o estado anterior.
- **SC-004a**: Em 100% das tentativas de alteração após o envio formal da submissão, inclusive por seu criador ou gestor BraCVAM, o sistema impede a alteração e preserva a execução submetida.
- **SC-005**: Em 100% das atualizações bem-sucedidas, existe uma evidência de auditoria consultável que identifica autor, momento, modalidade e atributos afetados.
- **SC-006**: Um usuário autorizado consegue concluir uma atualização parcial ou integral de uma submissão com ao menos cinco campos de dados em até 2 minutos pela demonstração conectada à API real.
- **SC-007**: Em 100% dos cenários de devolução e reenvio testados, a versão devolvida conserva exatamente o título, os valores e as referências de anexos que possuía no envio, enquanto a visão padrão mostra o conteúdo da versão mais recente.
- **SC-008**: Em 100% das tentativas de modificar uma versão histórica ou consultá-la sem autorização contextual, o sistema impede a operação e preserva a versão original.

## Assumptions

- A autorização existente já diferencia o criador da instância e a gestão BraCVAM; esta feature a reutiliza, sem introduzir novos papéis ou matrizes de permissão.
- O envio formal encerra a possibilidade de alterar diretamente o título e os valores da execução submetida. Uma nova oportunidade de ajuste somente existe quando o workflow existente cria uma nova execução de submissão ainda não submetida; esta feature não redesenha o ciclo de vida do processo.
- A definição de formulário aplicada a uma instância permanece disponível como referência histórica para validar seus valores, mesmo que administradores publiquem versão posterior do template.
- Campos de anexo já possuem fluxo próprio e metadados associados. Eles são preservados na representação da instância, mas não são modificados por atualização de dados.
- A numeração de execuções de submissão existente é a identificação de versão apresentada ao usuário; não será criado um segundo mecanismo de versionamento para a mesma submissão.
- Não há requisito de versionar cada revisão de título ou valor, de reconciliação colaborativa, de comparação visual entre versões nem de edição em massa; esses recursos permanecem fora do escopo para manter a solução simples.

## Dependencies and Traceability

- **Issue #15 — Implementar endpoints PUT e PATCH para instâncias de processo**: origem confirmada dos requisitos de atualização, autorização, estados terminais, auditoria e cobertura de testes.
- **Feature 009 — Submissão de Método Alternativo**: fornece a submissão estruturada, o vínculo com formulário e a validação dinâmica de valores.
- **Feature 012 — Editor e Customização de Templates de Formulários**: fornece a definição configurável de campos e a preservação da definição aplicável a novas instâncias.
- **Feature 016 — Anexos de Formulário**: mantém o ciclo de anexos fora do corpo de atualização de dados.
- **AGENTS.md**: exige demonstração interativa desacoplada e seed mínimo, ambos conectados à API real, como critério de conclusão da implementação.
