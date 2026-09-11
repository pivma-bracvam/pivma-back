# Feature Specification: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Feature Branch**: `020-decouple-triage-form`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Configure essa migração como uma spec, gere o plano, as tasks e implemente" (Desacoplar a atividade de triagem de templates de formulário e remover triage_review_v1 dos arquivos YAML, consolidando a triagem como uma avaliação pericial realizada diretamente sobre a instância do formulário submetido).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Execução da Triagem sem Dependência de Formulário Próprio (Priority: P1)

Como membro da equipe de triagem (BraCVAM), quero acessar uma proposta submetida, revisar os dados e documentos do formulário do proponente campo a campo e registrar uma deliberação formal (aprovação, rejeição ou diligência) com justificativa, sem que o sistema exija ou instancie um formulário exclusivo de triagem.

**Why this priority**: A triagem é uma análise pericial sobre a submissão do proponente. Eliminar a exigência de uma entidade de formulário fantasma simplifica o fluxo, previne inconsistências de dados e alinha o motor de processos ao comportamento real da operação.

**Independent Test**: Um usuário com papel de triador acessa um processo em estado de triagem, avalia os campos da proposta do proponente, emite a decisão fundamentada e o processo avança corretamente para o próximo estado (Planejamento, Fechado ou Diligência) sem criar instâncias órfãs de formulário de triagem.

**Acceptance Scenarios**:

1. **Given** um processo com proposta submetida em estado de triagem, **When** o triador acessa a atividade de triagem e submete a deliberação com resultado de aprovação e justificativa, **Then** a atividade de triagem é concluída, a decisão é persistida com autoria e timestamp, e o processo transiciona para a etapa de Planejamento sem depender de preenchimento de formulário próprio.
2. **Given** um processo em estado de triagem, **When** o triador emite uma solicitação de diligência apontando correções na proposta, **Then** a nova execução da atividade de submissão é disponibilizada ao proponente mantendo o histórico de revisões de campo, e a atividade de triagem é finalizada com êxito.
3. **Given** um processo em estado de triagem, **When** o triador emite rejeição com justificativa formal, **Then** o processo é encerrado no estado fechado sem deixar formulários pendentes.

---

### User Story 2 - Definição Declarativa Limpa nos Templates de Processo (Priority: P2)

Como gestor do sistema e arquiteto de processos, quero que as definições em YAML de todos os templates de processo expressem a atividade de triagem como uma atividade de governança/deliberação sem formulário associado, e que a lista de formulários dos arquivos contenha apenas os formulários de entrada preenchidos pelos proponentes.

**Why this priority**: Remove ruído e sobrecarga cognitiva na manutenção dos templates YAML, garantindo que o catálogo de formulários reflita exclusivamente os instrumentos de coleta de dados reais.

**Independent Test**: Carregar os 5 templates oficiais de processo e verificar que nenhum deles declara formulário para a atividade de triagem e nenhum deles inclui a definição `triage_review_v1` em seu bloco de formulários.

**Acceptance Scenarios**:

1. **Given** os arquivos YAML de processo na plataforma, **When** os templates são inspecionados, **Then** cada processo declara exatamente 1 formulário de submissão em sua lista de formulários e a atividade de triagem não referencia `form_template_key`.
2. **Given** a sincronização de templates via bootstrap, **When** os arquivos são processados, **Then** apenas os formulários de submissão ativos são provisionados e vinculados, sem erros de referência nula ou integridade relacional.

---

### User Story 3 - Rastreabilidade e Não Degradação de Processos Existentes (Priority: P3)

Como auditor do sistema, quero que os processos criados anteriormente continuem íntegros, com seus históricos e decisões de triagem preservados, mesmo após a desativação do template de formulário legado de triagem.

**Why this priority**: Garante a conformidade regulatória e o princípio de imutabilidade histórica do PIVMA, assegurando que mudanças estruturais de template não causem efeitos colaterais em instâncias históricas.

**Independent Test**: Consultar instâncias de processos submetidas ou triadas em ciclos anteriores e verificar que suas decisões, revisões de campo e linha do tempo permanecem totalmente auditáveis e legíveis.

**Acceptance Scenarios**:

1. **Given** processos concluídos ou em andamento antes da migração, **When** seus dados e auditoria forem consultados, **Then** todas as decisões de triagem emitidas permanecem associadas às execuções de atividade correspondentes sem quebras visuais ou estruturais.

---

## Edge Cases

- O que acontece se uma chamada de API tentar buscar o formulário da atividade de triagem via rota genérica de formulário? O sistema deve responder informando de forma clara que a atividade não possui formulário associado (ex.: status HTTP adequado ou indicação de inexistência de formulário para a atividade).
- O que acontece com templates legados `triage_review_v1` armazenados no banco de dados? O sistema deve inativá-los ou marcá-los logicamente sem apagar dados históricos de processos que possam ter referenciado a chave no passado.
- O que acontece durante a transição da atividade de submissão para a triagem quando o processo não possui avaliação por IA? O motor deve desbloquear a atividade de triagem e criar a execução e a tarefa correspondentes sem tentar instanciar nenhum formulário.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir a configuração e execução de atividades de processo sem vinculação obrigatória a um modelo de formulário (`form_template_key` nulo ou ausente).
- **FR-002**: A atividade de triagem (`triage_evaluation`) em todos os templates de processo (YAML) NÃO DEVE possuir formulário associado (`form_template_key` ausente/nulo).
- **FR-003**: O modelo de formulário `triage_review_v1` DEVE ser removido das definições declarativas (bloco `forms`) em todos os arquivos YAML de templates de processo.
- **FR-004**: O mecanismo de inicialização e desbloqueio da atividade de triagem DEVE criar a execução da atividade (`ActivityRun`) e a respectiva tarefa operacional (`Task`) sem instanciar qualquer registro de formulário (`FormInstance`).
- **FR-005**: A operação de registro de decisão de triagem DEVE localizar a atividade e a execução vigentes diretamente pela estrutura do processo, sem depender da existência ou consulta de uma instância de formulário associada à atividade de triagem.
- **FR-006**: O processo de sincronização de templates (bootstrap) DEVE desativar ou gerenciar o ciclo de vida de templates de formulário que não estejam mais presentes nas definições em arquivo, mantendo o histórico de auditoria intacto.
- **FR-007**: As interfaces operacionais de triagem, kanban e linha do tempo DEVEM continuar operando normalmente de ponta a ponta contra a API real, avaliando campos do formulário de proposta e registrando deliberações.

---

### Key Entities *(include if feature involves data)*

- **ActivityInstance**: Instância da atividade no processo; para a triagem, passa a operar de forma autônoma sem requerer vínculo com formulário.
- **ActivityRun**: Execução da atividade de triagem; registra início, término e hospeda as decisões formais e tarefas, sem instâncias filhas de formulário.
- **FieldReview**: Registros periciais dos triadores emitidos sobre os campos do formulário da submissão do proponente.
- **Decision**: Deliberação formal vinculada à execução da atividade de triagem contendo o parecer (Aprovado, Rejeitado, Diligência) e fundamentação.
- **FormTemplate**: Definição de esquema de formulário; deixa de conter a chave legada de triagem no catálogo ativo.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Todos os 5 templates YAML oficiais contêm exatamente 1 formulário declarado (o respectivo formulário de submissão).
- **SC-002**: 100% dos fluxos de triagem de ponta a ponta (aprovação, rejeição e solicitação de ajustes) executam com sucesso sem gerar registros na tabela de instâncias de formulário para a atividade de triagem.
- **SC-003**: A suite completa de testes de regressão automatizados e testes de contratos executam com 100% de sucesso.
- **SC-004**: Todas as páginas de demonstração operacionais continuam funcionando sem regressão visual ou funcional ao interagir com a API real.

---

## Assumptions

- A avaliação da triagem continua sendo realizada campo a campo sobre o formulário de proposta via `FieldReview` e consolidada via `Decision`.
- O catálogo de formulários dinâmicos é reservado estritamente para formulários que recebem preenchimento de dados de entrada dos atores do processo.
- Não há novos campos ou telas adicionais criados nesta migração; trata-se de um refatoramento e saneamento arquitetural.
