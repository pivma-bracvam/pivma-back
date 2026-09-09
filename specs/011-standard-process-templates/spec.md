# Feature Specification: 011 - Processos Padrão do Sistema (5 Pipelines Oficiais e Fase 1: Submissão, Avaliação por IA e Deliberação BraCVAM)

**Feature Branch**: `011-standard-process-templates`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Quero que o existam 5 processos padrão do sistema, eles tem os seguintes nomes:
1. Método 100% novo já desenvolvido, protocolo estabelecido e validação AINDA por ser executada (Opção principal: Método Pré-Validado ou Candidato à Validação Interlaboratorial / Curta: Método Otimizado – Validação Pendente)
2. Método (já validado) sendo proposta UMA NOVA aplicação (Opção principal: Extensão de Escopo de Aplicação / Regulatória: Validação para Nova Finalidade de Uso)
3. Método (já validado) sendo proposto UM NOVO sistema teste (Opção principal: Validação Me-Too ou Método Mecanisticamente e Funcionalmente Semelhante / Alternativa: Transferência de Sistema-Teste)
4. Método 100% novo já desenvolvido, protocolo estabelecido e toda validação JÁ concluída – dossiê pronto (Opção principal: Método Validado – Dossiê Submetido ou Dossiê para Revisão por Pares / Status regulatório: Método com Validação Concluída)
5. IDEIA de Método ainda a ser desenvolvido (Opção principal: Prova de Conceito (PoC) ou Método Conceitual / Estágio inicial: Método em Desenvolvimento e Otimização)
Hoje existe um arquivo chamado @src/pivma/templates_data/full_validation_v1.yaml que guarda o schema que é utilizado para demonstração, quero que ele deixe de existir e vamos manter apenas os 5 que são reais.
Para todos eles você vai manter apenas a etapa de submissao e triagem, ela consistem em:
1. Proponente elaborar a sua submissão e enviar
2. A IA avaliar o que foi enviado
3. O BraCVAM fazer a validação para dar a decisão final.
É necessário avaliar o que foi desenvolvido na etapa 004 para ter certeza do que já existe no sistema e como alteração do processo padrão do sistema altera / quebra."

## Clarifications

### Session 2026-09-09

- **Q1: Convenção Canônica de Chaves e Nomes dos 5 Processos**
  - **Decisão**: Opção A (Chaves Semânticas + Nomes Principais):
    1. `pre_validated_method` – "Método Pré-Validado"
    2. `scope_extension` – "Extensão de Escopo de Aplicação"
    3. `me_too_validation` – "Validação Me-Too"
    4. `validated_method_dossier` – "Método Validado – Dossiê Submetido"
    5. `proof_of_concept` – "Prova de Conceito (PoC)"
    *As descrições e status regulatórios detalhados integram o campo `description` e metadados dos templates.*
- **Q2: Orquestração e Pipeline da Avaliação por IA**
  - **Decisão**: Reutilizar integralmente a infraestrutura construída na Feature 010 (`FormAIPipelineEngine` com as 3 etapas de mock). A IA é disparada automaticamente na submissão e retorna resultado negativo por padrão (`NEEDS_ADJUSTMENT` / `REPROVED`) com inconformidades e recomendações simuladas, anexando esses apontamentos como subsídio para a atividade de triagem do BraCVAM.
- **Q3: Estrutura dos Formulários de Entrada**
  - **Decisão**: Opção A (5 Formulários Declarativos Dedicados). Cada template possui seu próprio formulário declarativo em YAML com campos adaptados ao estágio de maturidade de cada método (ex.: `submission_pre_validated_v1`, `submission_scope_extension_v1`, `submission_me_too_v1`, `submission_validated_dossier_v1`, `submission_proof_of_concept_v1`), com campos críticos sinalizados com `ai_evaluation_enabled: true`.

---

## Avaliação de Impacto e Compatibilidade com a Etapa 004

Antes de estabelecer as especificações funcionais, realizou-se a análise de impacto em relação ao que foi implementado na Feature 004 e suas evoluções (Features 006, 009 e 010):

1. **Abstrações e Modelos do Motor de Processos (Compatibilidade Total)**:
   - A infraestrutura da etapa 004 (`ProcessTemplate`, `ProcessTemplateVersion`, `Phase`, `ActivityInstance`, `ActivityRun`, `Task`, `FormTemplate`, `FormField`, `FormInstance`, `FormValue`, `Artifact`, `Decision` e `FieldReview`) é inteiramente agnóstica em relação à quantidade e ao conteúdo dos templates de processo.
   - O mecanismo de carga declarativa (`bootstrap_process_templates.py`) lê dinamicamente todos os arquivos `.yaml` em `src/pivma/templates_data/`. A exclusão de `full_validation_v1.yaml` e a substituição pelos 5 novos arquivos de template operam nativamente sobre o carregador existente.

2. **Acoplamento Identificado no Código (`process_engine.py`)**:
   - Em `process_engine.py`, algumas transições da Fase 1 continham referências literais a chaves de atividade (`proposal_submission`, `triage_evaluation`) e formulário de parecer (`triage_review_v1`).
   - Para garantir total compatibilidade com o motor sem refatoração destrutiva, todos os 5 processos oficiais devem seguir um padrão unificado de chaves de atividade na Fase 1 (Submissão e Triagem), garantindo a continuidade das transições de parecer, diligência e auditoria.

3. **Impacto em Testes, Seeds e Demonstrações**:
   - **Testes**: Várias suítes de testes unitários e de integração (`test_process_router.py`, `test_form_submission.py`, `test_process_engine.py`, `test_template_loader.py`) referenciavam `template_key == "full_validation"`. Esses testes devem ser atualizados para validar o catálogo com os 5 novos templates padrão ou utilizar o template canônico de método pré-validado.
   - **Seeds e Demos**: `scripts/seeds/` (`seed_forms.py`, `seed_triage.py`, `seed_form_ai_demo.py`) e as interfaces em `demos/` vinculadas a `full_validation` devem ser migradas para os novos identificadores oficiais dos 5 processos.

4. **Escopo da Fase 1 e Novo Pipeline de 3 Passos**:
   - O template demonstrativo anterior continha uma segunda fase declarada (`phase_2_planning_governance`). Conforme solicitado, os 5 processos oficiais devem manter **exclusivamente** a Fase 1 (Submissão e Triagem).
   - O ciclo da Fase 1 é composto por 3 etapas sequenciais claras:
     1. **Submissão**: Elaboração e envio da proposta pelo Proponente;
     2. **Avaliação por IA**: Processamento automatizado das justificativas e dados técnicos pelo pipeline de inteligência artificial;
     3. **Deliberação BraCVAM**: Triagem humana e parecer final fundamentado pela comissão do BraCVAM (Aprovação, Diligência/Revisão ou Rejeição).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seleção e Instanciação dos Processos Oficiais do BraCVAM (Priority: P1)

Como um Proponente (pesquisador, desenvolvedor de método ou instituição parceira), quero consultar o catálogo dos 5 processos oficiais do BraCVAM e escolher a modalidade exata correspondente ao estágio de maturidade e finalidade do meu método, para que a submissão seja conduzida com as diretrizes regulatórias e técnicas adequadas desde a sua criação.

**Why this priority**: É a porta de entrada institucional do sistema. Sem os 5 processos reais disponíveis, o usuário não pode enquadrar corretamente a sua proposta na esteira regulatória do BraCVAM.

**Independent Test**: Um proponente autenticado consulta a lista de processos disponíveis (`GET /processes/templates`), constata a presença exclusiva dos 5 processos padrão com suas nomenclaturas e descrições oficiais (e a ausência do template mock `full_validation`), e instancia com sucesso um processo para qualquer um dos 5 tipos.

**Acceptance Scenarios**:

1. **Given** o sistema inicializado e populado com os templates oficiais, **When** um usuário autenticado listar os templates de processo disponíveis, **Then** o sistema retorna exatamente os 5 processos padrão do BraCVAM (Método Pré-Validado, Extensão de Escopo, Validação Me-Too, Método Validado/Dossiê Concluído e Prova de Conceito), com versão ativa e publicada, sem exibir o template descartado `full_validation`.
2. **Given** um proponente autenticado, **When** ele cria um novo processo selecionando a chave de qualquer um dos 5 templates oficiais, **Then** o sistema instancia o processo com código rastreável (`VAL-YYYY-...`), vincula o proponente como autor da proposta e inicializa a atividade de submissão no estado em andamento (`IN_PROGRESS`).

---

### User Story 2 - Elaboração e Envio da Submissão pelo Proponente (Priority: P2)

Como um Proponente, quero preencher o formulário técnico da submissão com os dados e justificativas pertinentes ao tipo de método selecionado, salvar rascunhos durante a elaboração e submeter formalmente a proposta, para que ela avance para a etapa de avaliação automatizada por IA.

**Why this priority**: Viabiliza a coleta estruturada das evidências técnicas e científicas que alimentarão o pipeline de IA e a deliberação do BraCVAM.

**Independent Test**: O proponente salva informações parciais no formulário do processo criado, completa os campos obrigatórios e confirma a submissão. O sistema registra o formulário como submetido, emite o artefato de dossiê inicial e encerra a tarefa do proponente.

**Acceptance Scenarios**:

1. **Given** um processo em fase de submissão, **When** o proponente salva alterações parciais sem submeter, **Then** o sistema persiste os valores de rascunho sem bloquear a edição e sem disparar a avaliação de triagem.
2. **Given** o formulário de submissão preenchido com todos os requisitos obrigatórios, **When** o proponente confirma o envio formal, **Then** a atividade de submissão é concluída com sucesso, o artefato de dossiê de submissão é gerado e o processo transiciona para a etapa de avaliação de triagem.

---

### User Story 3 - Avaliação Automatizada por IA e Pré-Análise Técnica (Priority: P3)

Como membro da equipe de triagem do BraCVAM ou operador do sistema, quero que o envio da proposta acione a avaliação automatizada dos campos elegíveis via pipeline de IA, gerando pareceres preliminares, apontamentos de conformidade e notas de contexto antes da deliberação humana, para subsidiar a decisão dos avaliadores.

**Why this priority**: Garante agilidade, padronização e redução de carga operacional na triagem preliminar dos métodos submetidos ao BraCVAM.

**Independent Test**: Após a submissão do formulário, os campos com avaliação de IA habilitada são processados pelo motor de IA, gerando o relatório/veredito técnico estruturado vinculado à execução da proposta.

**Acceptance Scenarios**:

1. **Given** uma proposta formalmente enviada pelo proponente contendo campos sinalizados para análise de IA, **When** o pipeline de IA processar a submissão, **Then** o sistema analisa os campos correspondentes através das etapas analíticas e registra o veredito técnico estruturado com recomendações e inconsistências encontradas.
2. **Given** um processo com avaliação de IA concluída, **When** o avaliador do BraCVAM acessar a tarefa de triagem, **Then** os apontamentos gerados pela IA devem estar acessíveis como subsídio para o parecer final.

---

### User Story 4 - Validação e Deliberação Final pelo BraCVAM (Priority: P4)

Como um Avaliador ou Membro do Grupo Gestor do BraCVAM (`TRIAGE_LEAD`), quero revisar a submissão do proponente em conjunto com as análises da IA, registrar notas campo a campo e emitir a decisão final de triagem (Aprovação, Rejeição ou Diligência para Ajustes), para concluir o ciclo da Fase 1 com total governança e rastreabilidade.

**Why this priority**: É o portão de controle regulatório e científico definitivo que encerra a triagem e determina se a proposta é aceita, descartada ou reenviada para complementação.

**Independent Test**: O triador do BraCVAM analisa a submissão, preenche o formulário de parecer de triagem e emite uma deliberação fundamentada. Em caso de aprovação, o processo conclui a Fase 1; em caso de diligência, uma nova rodada de submissão é aberta para o proponente; em caso de rejeição, o processo é arquivado.

**Acceptance Scenarios**:

1. **Given** uma proposta em triagem avaliada positivamente pelo BraCVAM, **When** o triador emitir decisão `APPROVED` com parecer técnico, **Then** a atividade de triagem e a Fase 1 são concluídas com status `COMPLETED` e o processo é marcado como apto para planejamento (`PLANNING`).
2. **Given** uma proposta com inconsistências sanáveis, **When** o triador emitir decisão `NEEDS_REVISION` com a justificativa da diligência, **Then** o sistema gera uma nova execução (`ActivityRun #2`) da atividade de submissão para o proponente com os dados anteriores preservados para correção.
3. **Given** uma proposta que não atenda aos critérios regulatórios do BraCVAM, **When** o triador emitir decisão `REJECTED`, **Then** o processo é arquivado como rejeitado (`CLOSED`) com registro imutável do parecer no histórico de auditoria.

---

### Edge Cases

- **Tentativa de instanciar processo com o template legado `full_validation`**: O sistema deve retornar erro 404 (Template não encontrado), impedindo a criação de instâncias com definições descontinuadas.
- **Falha ou indisponibilidade temporária no serviço de IA**: Se a avaliação por IA sofrer falha técnica, o processo não deve ser corrompido; o evento de erro deve ser registrado no log operacional e a tarefa de triagem humana do BraCVAM deve permanecer acessível com indicação de que a pré-análise automatizada não foi concluída.
- **Conflito de interesse de membro do BraCVAM**: Avaliadores com conflito de interesse registrado para o processo em análise devem ser sumariamente impedidos de emitir parecer ou registrar avaliações.
- **Reenvio de proposta após diligência**: Quando o proponente submete a versão revisada (Run #2), a IA e o BraCVAM devem avaliar a nova versão da submissão com preservação do histórico comparativo de execuções.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE remover e descontinuar o arquivo e template legado `full_validation_v1.yaml` (`full_validation`), garantindo que ele não seja carregado no banco de dados nem exposto na listagem pública de templates.
- **FR-002**: O sistema DEVE disponibilizar 5 templates declarativos oficiais de processos padrão em `src/pivma/templates_data/`, estruturados estritamente com a **Fase 1 (Submissão e Triagem)**, com chaves semânticas e nomes principais oficiais:
  1. **Template 1**: Chave `pre_validated_method` – Nome "Método Pré-Validado" (Candidato à Validação Interlaboratorial);
  2. **Template 2**: Chave `scope_extension` – Nome "Extensão de Escopo de Aplicação" (Validação para Nova Finalidade de Uso);
  3. **Template 3**: Chave `me_too_validation` – Nome "Validação Me-Too" (Transferência / Semelhança de Sistema-Teste);
  4. **Template 4**: Chave `validated_method_dossier` – Nome "Método Validado – Dossiê Submetido" (Revisão por Pares Concluída);
  5. **Template 5**: Chave `proof_of_concept` – Nome "Prova de Conceito (PoC)" (Método Conceitual / Em Desenvolvimento).
- **FR-003**: Para todos os 5 templates oficiais, o fluxo do ciclo de vida DEVE conter exclusivamente o ciclo de **Submissão e Triagem** estruturado em 3 etapas sequenciais integradas:
  1. Elaboração e envio formal da submissão pelo Proponente (`proposal_submission`);
  2. Avaliação técnica automatizada dos dados e justificativas submetidas através do pipeline de IA da Feature 010 (`FormAIPipelineEngine`), gerando por padrão resultado negativo simulado (`NEEDS_ADJUSTMENT` / `REPROVED`) com lista de inconformidades e recomendações;
  3. Validação e deliberação final pelo BraCVAM (`triage_evaluation` por `TRIAGE_LEAD`), utilizando as análises da IA como subsídio.
- **FR-004**: O sistema DEVE fornecer 5 esquemas de formulário de submissão declarativos dedicados em YAML (`submission_pre_validated_v1`, `submission_scope_extension_v1`, `submission_me_too_v1`, `submission_validated_dossier_v1`, `submission_proof_of_concept_v1`), contemplando campos técnicos e regulatórios específicos por modalidade, com a flag `ai_evaluation_enabled = true` e instruções de contexto (`ai_context_instructions`) configuradas nos campos de mérito e justificativa científica.
- **FR-005**: O sistema DEVE integrar o encerramento da atividade de submissão com a execução do pipeline de avaliação de IA da Feature 010, disponibilizando os resultados da avaliação automatizada na tarefa de triagem do BraCVAM.
- **FR-006**: O sistema DEVE manter o suporte a decisões de triagem pelo BraCVAM: aprovação (`APPROVED`), diligência com preservação de versão e histórico (`NEEDS_REVISION`) e rejeição fundamentada (`REJECTED`).
- **FR-007**: O sistema DEVE atualizar todos os scripts de sementes (`scripts/seeds/`) e interfaces de demonstração (`demos/`) para operar nativamente sobre os novos templates oficiais.
- **FR-008**: Todas as operações de criação, submissão, avaliação por IA, parecer e deliberação DEVEM registrar eventos imutáveis na trilha de auditoria (`AuditEvent`) e no índice operacional de eventos (`logs/application/`).

---

### Key Entities

- **ProcessTemplate & ProcessTemplateVersion**: Representa os 5 tipos de processos canônicos cadastrados e suas versões publicadas, contendo a definição da Fase 1 de Submissão e Triagem.
- **ProcessInstance**: A instância concreta de validação criada a partir de um dos 5 templates oficiais, identificada pelo código institucional (`crCode`).
- **ActivityInstance & ActivityRun**: Unidades de trabalho e execuções no ciclo da proposta:
  - Atividade de Submissão (atribuída ao Proponente);
  - Atividade ou Etapa Automatizada de Avaliação por IA;
  - Atividade de Triagem e Deliberação (atribuída ao BraCVAM).
- **FormTemplate & FormField**: Os esquemas declarativos dos formulários de entrada específicos para cada uma das modalidades de validação.
- **FormInstance & FormValue**: Preenchimento versionado dos dados da proposta, distinguindo valores de rascunho e submissão final.
- **AI Evaluation Group / Verdict**: Estrutura de dados contendo o resultado da avaliação automatizada por IA dos campos do formulário.
- **Decision & FieldReview**: O parecer formal e notas técnicas emitidas pelos avaliadores do BraCVAM na triagem.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O catálogo de templates de processos expõe exatamente os 5 processos oficiais do BraCVAM, com 0% de ocorrência do template de demonstração descontinuado `full_validation`.
- **SC-002**: 100% das novas instâncias criadas para qualquer um dos 5 processos oficiais concluem o ciclo completo de Fase 1 (Submissão pelo Proponente → Avaliação por IA → Triagem BraCVAM).
- **SC-003**: Na solicitação de diligência pelo BraCVAM, 100% dos dados submetidos anteriormente permanecem preservados em histórico e carregados na nova execução para revisão pelo proponente.
- **SC-004**: Todas as suítes de testes automatizados executam e passam com sucesso validando os 5 novos processos sem erros de regressão decorrentes da remoção do template anterior.
- **SC-005**: As demonstrações do sistema em `demos/` e os scripts de seed inicializam e operam comprovadamente utilizando os 5 templates oficiais.

---

## Assumptions

- Os 5 processos oficiais compartilham o mesmo modelo conceitual de ciclo de vida para a Fase 1 (Submissão e Triagem), variando apenas nos requisitos técnicos de entrada do formulário, diretrizes de enquadramento e critérios de avaliação do BraCVAM.
- A fase posterior (Planejamento) e as etapas interlaboratoriais permanecem fora da definição do template nesta fase, conforme orientação explícita do usuário de manter apenas Submissão e Triagem.
- O pipeline de IA utiliza a arquitetura base simulada/mock estabelecida na Feature 010 para avaliar os campos sinalizados com `ai_evaluation_enabled = true`.
- As regras de governança, restrição de acesso do proponente em elaboração e bloqueio de usuários com conflito de interesse continuam vigentes e aplicadas aos 5 processos.
