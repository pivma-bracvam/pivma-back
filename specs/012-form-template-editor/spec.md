# Feature Specification: 012 - Editor e Customização de Templates de Formulários de Processo (Versão 1.1)

**Feature Branch**: `012-form-template-editor`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Vamos desenvolver uma versao 1.1 do nosso sistema, deixar ele mais completo para conseguir resolver essas pendências, é importante manter os padrões definidos na spec anterior. Com essa especificação quero desenvolver os endpoints faltando para conseguir editar os templates dos formulários. É importante que a edição me permita customizar os campos, as sessões desse formulário, tipos, se é obrigatório, todo o kit basico de um form editor. Vamos manter a parte da IA simplificada (spec 010) vamos precisar de uma spec apenas para trabalhar com esse ponto, mas o restante já deve ser possivel executar agora. Como validação preciso que você finalize a demo de edição do formulário seguindo o que foi acordado nas conversas anteriores, editar o template, salvar, e toda vez que o proponente for criar uma instancia aquele processos ele dê de cara com esse formulário especifico que foi editado."

---

## Clarifications

### Session 2026-09-09

- **Q1: Papéis de Usuário e Permissões de Customização**
  - **Decisão**: A edição de templates de formulários e processos é restrita exclusivamente a usuários com perfil de gestão/administração da equipe **BraCVAM** (ex.: Administradores do Sistema / Grupo Gestor). Proponentes têm acesso exclusivamente à criação de instâncias de processos e preenchimento de seus dados.
- **Q2: Escopo de Configuração e Agrupamento (Seções)**
  - **Decisão**: Os campos do formulário devem suportar atributos canônicos de edição (chave do campo, rótulo, descrição/instruções de ajuda, tipo do dado, obrigatoriedade, opções de seleção e regras de validação) além do agrupamento por **seções** (ex.: Dados Gerais, Justificativa Técnica, Protocolo Experimental), organizadas por ordem sequencial.
- **Q3: Integração Simplificada de IA (Alinhamento com Spec 010)**
  - **Decisão**: Nesta versão 1.1, a parametrização de IA permanece no escopo simplificado estabelecido na Spec 010 (flag booleana `ai_evaluation_enabled`, texto de instruções de contexto `ai_context_instructions` e regras de validação `ai_validation_rules`), permitindo ligar/desligar e instruir a esteira mock sem acoplamento a serviços externos complexos nesta etapa.
- **Q4: Governança de Versionamento e Instanciação**
  - **Decisão**: Ao salvar um template editado, a nova definição passa a ser a versão ativa vigente para novas instanciações. Processos já criados anteriormente preservam imutabilidade histórica de seus formulários e valores preenchidos. Quando o proponente instancia um novo processo, a atividade correspondente carrega o formulário gerado a partir do template editado.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edição e Persistência de Templates de Formulários pelo BraCVAM (Priority: P1)

Como Administrador ou Gestor do BraCVAM, quero selecionar um processo do catálogo oficial, visualizar seus templates de formulários e seções, editar/adicionar/remover campos com suas regras (tipo de dado, obrigatoriedade, seções e flag simplificada de IA), e salvar as alterações no sistema, para que os requisitos de coleta de dados do método alternativo possam evoluir conforme as diretrizes regulatórias vigentes.

**Why this priority**: É o núcleo funcional da versão 1.1. Sem a capacidade de consultar e persistir alterações estruturais de templates de formulários no backend, não há como customizar processos dinamicamente.

**Independent Test**: Um usuário autenticado com perfil BraCVAM acessa o editor de templates, seleciona um processo padrão (ex.: "Método Pré-Validado"), adiciona um novo campo ou edita um campo existente (alterando rótulo, tipo, obrigatoriedade e ativando a flag de IA), clica em salvar e o sistema confirma a persistência das alterações na definição do template com retorno de sucesso.

**Acceptance Scenarios**:

1. **Given** um usuário BraCVAM autenticado e um template de processo selecionado, **When** ele altera o rótulo de um campo, a ordem ou a obrigatoriedade e salva as alterações, **Then** o sistema atualiza a definição do template de formulário no banco de dados e retorna o esquema atualizado com status de sucesso.
2. **Given** um formulário com múltiplas seções, **When** o usuário BraCVAM adiciona um novo campo vinculado a uma seção específica ou cria uma nova seção, **Then** o sistema registra o campo na hierarquia e ordenação definidas.
3. **Given** um campo do template, **When** o usuário marca a opção `ai_evaluation_enabled: true` e preenche instruções contextuais para a IA, **Then** essas configurações são preservadas no esquema do campo e mantêm total compatibilidade com a esteira da Spec 010.
4. **Given** um usuário não autenticado ou com perfil de proponente comum, **When** tentar submeter alterações na definição de um template de formulário, **Then** o sistema rejeita a operação com erro de autorização (`403 Forbidden` ou `401 Unauthorized`).

---

### User Story 2 - Instanciação pelo Proponente com Formulário Customizado (Priority: P2)

Como Proponente de um método alternativo, quero criar uma nova solicitação/instância de processo a partir de um dos templates padrão e receber imediatamente o formulário de submissão estruturado com os campos e seções recentemente customizados pela equipe BraCVAM, para que minhas informações sejam coletadas em conformidade com as exigências mais recentes.

**Why this priority**: Comprova a integração de ponta a ponta entre o desenho do formulário (design-time) e a execução operacional da proposta (run-time).

**Independent Test**: Um proponente autenticado inicia um novo processo do tipo recém-editado. Ao abrir a atividade de submissão da proposta, o formulário exibido contém exatamente os campos, tipos, seções e obrigatoriedades configurados na edição prévia pelo BraCVAM.

**Acceptance Scenarios**:

1. **Given** um template de processo cujo formulário foi customizado pelo BraCVAM, **When** um proponente cria uma nova instância desse processo (`POST /processes`), **Then** a atividade de submissão (`GET .../form`) apresenta a estrutura idêntica aos campos e seções vigentes no template editado.
2. **Given** um campo recém-configurado como obrigatório no template, **When** o proponente tenta submeter a proposta sem preencher esse campo, **Then** o sistema bloqueia a submissão e indica erro de validação para aquele campo específico.
3. **Given** instâncias de processos criadas antes da edição do template, **When** consultadas pelo proponente ou pela triagem, **Then** preservam com exatidão a estrutura e os valores da época em que foram instanciadas, sem corrupção de dados históricos.

---

### User Story 3 - Demonstração Interativa Completa e Validação Operacional (Priority: P3)

Como avaliador técnico do sistema, quero acessar a página de demonstração interativa (`demos/forms/index.html`), listar os processos disponíveis, editar os campos e seções do template como usuário BraCVAM, salvar na API real e, em seguida, alternar para a visão de proponente criando uma nova instância desse processo para comprovar que o novo formulário é renderizado com fidelidade.

**Why this priority**: Cumpre a exigência do `AGENTS.md` e o critério explícito de aceite do usuário de ter a demonstração funcional e comprovada contra a API real.

**Independent Test**: Abrir `demos/forms/`, entrar como BraCVAM, selecionar o processo "Método Pré-Validado", editar o template adicionando ou renomeando um campo com IA ativada, salvar via API real (`PUT /processes/templates/{key}`), alternar a sessão para Proponente, instanciar esse processo e constatar que o formulário de submissão renderiza o campo customizado pronto para preenchimento.

**Acceptance Scenarios**:

1. **Given** o catálogo central (`demos/index.html`), **When** o usuário navega para o Módulo 2 (`demos/forms/`), **Then** a interface apresenta a listagem dos 5 processos oficiais e o painel de edição de templates.
2. **Given** a edição realizada e salva pelo BraCVAM, **When** o proponente cria um processo de teste na mesma interface, **Then** o formulário de submissão do processo criado exibe imediatamente as alterações persistidas no backend.
3. **Given** a execução das operações na interface, **When** o Inspetor de API é verificado, **Then** todas as interações com o backend refletem status de sucesso (`200 OK` / `201 Created`) com payloads consistentes.

---

### Edge Cases

- **Tentativa de salvar um campo sem `field_key` ou com chave duplicada no mesmo formulário**: O sistema deve validar a unicidade da chave e rejeitar a alteração com erro explicativo (`422 Unprocessable Entity`).
- **Remoção de um campo em template que possui instâncias antigas**: O sistema não deve remover colunas ou dados de instâncias legadas; a alteração deve afetar exclusivamente a definição para novas instanciações (isolamento de versão).
- **Inclusão de campo de seleção (`select`) sem lista de opções**: O sistema deve alertar o usuário para informar ao menos uma opção válida.
- **Instruções de IA vazias quando `ai_evaluation_enabled` está marcado**: O sistema deve aceitar a marcação adotando uma instrução contextual padrão ou solicitar preenchimento de diretrizes básicas.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE disponibilizar endpoint para consulta detalhada da definição completa de templates de processos e seus respectivos formulários e campos (`GET /processes/templates/{key}`).
- **FR-002**: O sistema DEVE disponibilizar endpoint para atualização e persistência da definição de templates de processos e seus formulários (`PUT /processes/templates/{key}` ou equivalente), permitindo ao usuário BraCVAM salvar modificações estruturais.
- **FR-003**: O sistema DEVE permitir a customização dos atributos essenciais de cada campo do template:
  - Identificador técnico único (`field_key`);
  - Rótulo visível ao usuário (`label`);
  - Texto de ajuda e instruções (`help_text`);
  - Tipo de dado (`field_type`): `text`, `textarea`, `select`, `integer`, `float`, `boolean`, `date`, `file_upload`;
  - Indicador de obrigatoriedade (`is_required`);
  - Posição e índice de ordenação (`order_index`);
  - Opções para campos de seleção (`options`);
  - Regras de validação de formato e limites (`validation_rules`);
  - Identificador ou nome do agrupamento/seção do formulário (`section`).
- **FR-004**: O sistema DEVE permitir adicionar novos campos, alterar campos existentes e remover campos de um template de formulário.
- **FR-005**: O sistema DEVE suportar a configuração simplificada de IA para cada campo (Spec 010):
  - Ativação/desativação da avaliação por IA (`ai_evaluation_enabled: bool`);
  - Instruções textuais de contexto para a IA (`ai_context_instructions: str`);
  - Regras de validação da IA (`ai_validation_rules: dict`).
- **FR-006**: O sistema DEVE sincronizar as alterações salvas do template com os modelos de dados persistidos (`ProcessTemplate`, `ProcessTemplateVersion`, `FormTemplate` e `FormField`), assegurando que a versão vigente seja atualizada.
- **FR-007**: O sistema DEVE restringir o acesso a endpoints de edição de templates exclusivamente a usuários autenticados com perfis institucionais autorizados da equipe BraCVAM.
- **FR-008**: Ao instanciar um novo processo (`POST /processes`), o sistema DEVE utilizar a definição vigente do template, gerando as instâncias de formulário (`FormInstance` e `FormField`) fiéis às alterações salvas.
- **FR-009**: O sistema DEVE preservar a imutabilidade histórica das instâncias de processos criadas antes da edição do template, garantindo que propostas anteriores não sejam corrompidas ou alteradas retroativamente.
- **FR-010**: Conforme `AGENTS.md`, o sistema DEVE disponibilizar uma página de demonstração interativa em `demos/forms/index.html` conectada à API real que evidencie:
  1. Listagem dos processos padrão do sistema;
  2. Interface de edição dos templates de formulários (campos, tipos, seções, obrigatoriedade, IA);
  3. Salvamento real via API;
  4. Fluxo do proponente instanciando um processo e deparando-se com o formulário customizado.

---

### Key Entities

- **ProcessTemplate**: Entidade que define uma modalidade de processo de validação no sistema.
- **ProcessTemplateVersion**: Versão publicada de um template de processo contendo o payload estruturado de fases, atividades e formulários.
- **FormTemplate**: Definição reutilizável de um formulário de coleta de dados vinculado a atividades de um processo.
- **FormField**: Definição de cada campo do formulário, contendo tipo, rótulo, regras, seção e parâmetros de avaliação por IA.
- **FormInstance**: Instância concreta de um formulário gerada no momento em que um proponente inicia um processo, vinculada à versão vigente do template.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Usuários BraCVAM conseguem selecionar um processo, editar campos de seu formulário e salvar as alterações em menos de 3 minutos.
- **SC-002**: 100% dos novos processos instanciados por proponentes após a edição de um template carregam com exatidão a estrutura, seções e regras de validação recém-salvas.
- **SC-003**: 100% dos processos instanciados em versões anteriores do template permanecem inalterados, preservando a integridade histórica de submissões passadas.
- **SC-004**: A demonstração em `demos/forms/index.html` valida com sucesso o fluxo completo de ponta a ponta interagindo exclusivamente com a API real.
- **SC-005**: Tempo de resposta do endpoint de atualização do template inferior a 500ms sob condições normais de operação.

---

## Assumptions

- A infraestrutura básica de autenticação por cookies (`CurrentUser`) e RBAC global já está ativa no backend.
- Os 5 templates de processos oficiais estabelecidos na Feature 011 (`pre_validated_method`, `scope_extension`, `me_too_validation`, `validated_method_dossier`, `proof_of_concept`) servem como base para a customização.
- A esteira de IA opera no formato mock de 3 etapas da Spec 010, sem necessidade de conexão com provedores externos de LLM nesta entrega da Versão 1.1.
