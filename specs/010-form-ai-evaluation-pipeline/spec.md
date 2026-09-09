# Feature Specification: Pipeline de IA para Formulários (Fase 1 - Estrutura Base e Mock)

**Feature Branch**: `010-form-ai-evaluation-pipeline`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Implementar a arquitetura inicial para avaliação automatizada de campos de formulários via IA. Nesta etapa, o objetivo é construir o fluxo de execução com respostas simuladas (mock), estruturar o pipeline de dados e viabilizar a observabilidade do processo. Essa spec é uma derivação do que já existe na spec 004. O índice operacional de eventos registra em JSONL o que acontece de relevante na plataforma (visão cronológica e consultável com duração total da execução). Os detalhes de IA ficam no log granular de etapas (independente de qual pipeline ou processo, registrando entradas, saídas, resultado, latência individual da etapa, custo simulado e correlation ID com o índice geral). Interface padrão: logging da biblioteca padrão do Python com structlog para serialização JSON. Sem OpenTelemetry nesta fase. Organização de arquivos em logs/ fora de src (logs/application/ para o índice geral e logs/ai/ para pipelines de IA), com retenção de 7 dias. Para validação conforme AGENTS.md: dois módulos de demonstração (um para visualização geral e outro para visualização da IA). Endpoints de observabilidade acessíveis para administradores com output em tempo real; no caso da IA, agrupados pela pipeline que puxou os registros."

---

## Análise Prévia de Gaps e Alinhamento Arquitetural

Antes de avançar com a implementação, validou-se a base de código herdada da Spec 004:

1. **Suporte a Flag de IA no Construtor de Formulários:**
   - *Diagnóstico*: O modelo `FormField` e a definição declarativa de templates suportam regras genéricas de validação, mas não possuem um atributo explícito para sinalizar a avaliação automatizada por IA.
   - *Direcionamento nesta Fase*: Adicionar a flag formal `ai_evaluation_enabled: bool` e metadados contextuais de instrução do campo no esquema de campos de formulário, preservando total compatibilidade retroativa com os campos existentes.

2. **Estratégia de Logs e Observabilidade para Administradores:**
   - *Diagnóstico*: O sistema atual conta com `AuditEvent` para transições de estado de negócio da máquina de processos, mas não possui a separação formal entre **Índice Operacional** e **Logs Granulares de Etapas de IA**.
   - *Direcionamento nesta Fase*: Implementar a arquitetura de logging em duas camadas independentes em formato JSONL, gravadas fora de `src/` no diretório `logs/`:
     - `logs/application/`: **Índice Operacional de Eventos**, leve e cronológico, registrando o que aconteceu na plataforma, duração total da execução, status e chave de correlação (`correlation_id`);
     - `logs/ai/`: **Log Granular de Etapas de IA**, registrando dados detalhados de cada etapa executada (entradas, saídas, latência da etapa, custo simulado, status, erros e referência ao índice geral).
   - *Interface e Dependências*: Utilizar a biblioteca padrão `logging` do Python como interface da aplicação acoplada ao `structlog` para a serialização dos eventos em JSONL. Adiar adoção de OpenTelemetry e Grafana para fases posteriores.

3. **Exposição em Tempo Real com Controle de Acesso Administrativo:**
   - *Diagnóstico*: A observabilidade operacional e de IA não deve ser pública na API geral de domínio. No entanto, é autorizada a criação de rotas administrativas dedicadas para consulta e streaming de logs.
   - *Direcionamento nesta Fase*: Implementar rotas administrativas protegidas (restritas a usuários com perfil de Administrador) que disponibilizam o output dos logs em tempo real (ex.: Server-Sent Events / SSE ou streaming de eventos). Na visão de IA, a API deve fornecer os eventos estruturados e agrupados por pipeline (`correlation_id` / `pipeline_run_id`).

4. **Diretrizes de Demonstração (AGENTS.md):**
   - *Direcionamento nesta Fase*: Construir dois módulos interativos distintos no catálogo `demos/`:
     - **Módulo Geral (`demos/operational-index/`):** Visualização cronológica em tempo real do Índice Operacional de Eventos da plataforma;
     - **Módulo de IA (`demos/ai-pipeline/`):** Visualização em tempo real dos pipelines de IA, com eventos agrupados pela pipeline de execução, exibindo as etapas sequenciais, latências, custos e payloads.
   - As duas páginas devem ser catalogadas em `demos/index.html` e validadas contra a API real usando massa de dados gerada por seed em `scripts/seeds/`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Execução do Pipeline Simulado de IA para Campos Sinalizados (Priority: P1)

Como um desenvolvedor ou operador do motor de validação, quero que o sistema identifique automaticamente os campos de formulário que possuem a flag `ai_evaluation_enabled = true` e os submeta a um pipeline sequencial desacoplado de 3 etapas simuladas (*mock*), retornando uma resposta no formato canônico de produção com resultado negativo por padrão, para que a esteira de validação opere de ponta a ponta com contratos estáveis antes da integração com modelos reais de IA.

**Why this priority**: Define a mecânica central do processamento automatizado, a identificação dos campos elegíveis e o contrato canônico de resposta utilizado pelo sistema.

**Independent Test**: Submeter uma instância de formulário com campos marcados para análise de IA. O sistema processa os campos elegíveis através das 3 etapas simuladas e gera o veredito canônico negativo (ex.: reprovado / pendente de ajustes) contendo justificativas e recomendações simuladas, ignorando campos não marcados.

**Acceptance Scenarios**:

1. **Given** um formulário preenchido com campos marcados com `ai_evaluation_enabled = true` e campos comuns (`false`), **When** o pipeline de avaliação for acionado, **Then** o sistema processa apenas os campos marcados e ignora os demais.
2. **Given** um campo elegível em processamento, **When** o pipeline for executado, **Then** ele percorre estritamente 3 etapas sequenciais simuladas:
   - *Etapa 1 (Extração de Contexto)*: coleta o valor preenchido e instruções do campo;
   - *Etapa 2 (Validação de Conformidade)*: simula a análise de regras e gera apontamentos;
   - *Etapa 3 (Consolidação do Veredito)*: estrutura a resposta final.
3. **Given** a finalização da avaliação de um campo, **When** o resultado for consolidado, **Then** o sistema retorna o formato canônico de produção com status negativo padrão (`REPROVED` ou `NEEDS_ADJUSTMENT`), pontuação de confiança simulada, lista de inconformidades e recomendações de adequação.

---

### User Story 2 - Registro Estruturado e Streaming em Tempo Real para Administradores (Priority: P2)

Como um administrador ou engenheiro de software, quero que as execuções sejam registradas em arquivos JSONL (`logs/application/` e `logs/ai/`) com rotação de 7 dias, e que a plataforma exponha endpoints administrativos com transmissão em tempo real das mensagens geradas, agrupando as etapas de IA pela pipeline correspondente, para viabilizar monitoramento e auditoria em tempo de execução.

**Why this priority**: Garante rastreabilidade, auditoria e diagnósticos imediatos, viabilizando o consumo em tempo real tanto pela infraestrutura quanto pelas páginas interativas de observabilidade.

**Independent Test**: Disparar avaliações de formulário via API e, simultaneamente, conectar-se aos endpoints administrativos em tempo real. O canal do Índice Operacional recebe os eventos da plataforma conforme ocorrem, e o canal da IA recebe os eventos agrupados sob o identificador da pipeline, contendo latência da etapa, custo simulado e payloads.

**Acceptance Scenarios**:

1. **Given** uma requisição de autenticação de administrador, **When** o administrador conecta ao endpoint de stream do Índice Operacional, **Then** o sistema transmite eventos em tempo real em formato JSONL à medida que operações e pipelines ocorrem, contendo a duração total e o `correlation_id`.
2. **Given** uma requisição de autenticação de administrador, **When** o administrador conecta ao endpoint de stream de IA, **Then** o sistema transmite eventos em tempo real onde os registros das etapas são associados e agrupados sob a pipeline (`correlation_id`) que os originou.
3. **Given** um usuário não administrador (ex.: proponente comum ou anônimo), **When** ele tenta acessar os endpoints de logs ou stream, **Then** o sistema rejeita a requisição com erro de autorização (`403 Forbidden` ou `401 Unauthorized`).
4. **Given** arquivos de log acumulados no diretório `logs/`, **When** a rotina de rotação for acionada, **Then** registros com mais de 7 dias são purgados automaticamente.

---

### User Story 3 - Demonstração: Módulo de Visualização Geral (Índice Operacional em Tempo Real) (Priority: P3)

Como um administrador de sistema ou avaliador técnico, quero acessar uma página de demonstração interativa (`demos/operational-index/`) que exiba em tempo real o fluxo cronológico de eventos operacionais da plataforma, permitindo filtrar por tipo de operação e status, para validar o comportamento do índice geral de forma desacoplada da aplicação.

**Why this priority**: Cumpre a exigência normativa do `AGENTS.md` de comprovar o funcionamento prático do módulo geral com dados reais e interface visual independente.

**Independent Test**: Abrir `demos/index.html`, navegar para o módulo "Visualização Geral - Índice Operacional", disparar ações no backend usando a semente de dados (`scripts/seeds/`) e constatar a renderização dinâmica em tela dos eventos operacionais recebidos em tempo real.

**Acceptance Scenarios**:

1. **Given** o catálogo central de demonstrações (`demos/index.html`), **When** o usuário acessa o índice, **Then** o módulo de Visualização Geral está devidamente catalogado e funcional.
2. **Given** a página do módulo de visualização geral aberta e conectada à API real, **When** uma operação é executada na plataforma, **Then** a interface exibe imediatamente uma nova linha de evento com timestamp, fluxo executado, status, duração total e `correlation_id`.
3. **Given** o código da demonstração, **When** inspecionado, **Then** ele reside estritamente em `demos/` e consome exclusivamente a API real com autenticação de administrador.

---

### User Story 4 - Demonstração: Módulo de Visualização da IA (Pipelines Agrupados em Tempo Real) (Priority: P4)

Como um desenvolvedor ou engenheiro de IA, quero acessar uma página de demonstração interativa (`demos/ai-pipeline/`) que apresente os pipelines de IA em tempo real agrupados por execução, exibindo o detalhamento das 3 etapas sequenciais (inputs, outputs, latências e custos simulados), para inspecionar visualmente o comportamento e a consistência das avaliações simuladas.

**Why this priority**: Cumpre a exigência normativa do `AGENTS.md` para o módulo especializado de IA, permitindo auditar o agrupamento por pipeline e inspecionar os dados granulares de cada etapa.

**Independent Test**: Acessar `demos/ai-pipeline/`, carregar uma submissão de formulário elegível via seed e acionar a avaliação. A interface agrupa os cards de pipeline pela execução e atualiza visualmente em tempo real as etapas 1, 2 e 3 com suas respectivas métricas e payloads JSON expansíveis.

**Acceptance Scenarios**:

1. **Given** o catálogo central de demonstrações (`demos/index.html`), **When** o usuário acessa o índice, **Then** o módulo de Visualização da IA está listado e acessível.
2. **Given** uma avaliação disparada no backend, **When** os dados chegam à interface em tempo real, **Then** a tela agrupa os registros sob a mesma pipeline de execução (`correlation_id`) e apresenta as 3 etapas em ordem sequencial.
3. **Given** o card de uma etapa na tela, **When** o usuário clica para expandir, **Then** os payloads JSON de entrada e saída, o custo simulado e o tempo de execução da etapa são exibidos com formatação legível.

---

### Edge Cases

- **Formulário sem campos marcados para IA**: O Índice Operacional registra a conclusão do fluxo geral sem etapas registradas no log de IA, e a interface da IA indica ausência de etapas a processar.
- **Interrupção de conexão no stream em tempo real**: As páginas em `demos/` devem reconectar automaticamente ao stream sem travar a interface nem duplicar eventos já recebidos.
- **Falha em uma das etapas do pipeline de IA**: A etapa com erro emite o status `FAILED` com detalhamento da exceção no log de IA; a interface destaca a etapa em vermelho e a pipeline é exibida como interrompida/falha.
- **Campos com payloads extensos ou arquivos anexados**: A etapa de extração sanitiza e registra referências aos arquivos (metadados e hashes) em vez de serializar o conteúdo binário bruto no JSONL.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE suportar a identificação de campos de formulário elegíveis para IA através do atributo explícito `ai_evaluation_enabled: bool` na definição do campo (`FormField`).
- **FR-002**: O sistema DEVE filtrar os valores preenchidos em uma instância de formulário (`FormInstance`) e selecionar exclusivamente os campos com `ai_evaluation_enabled = true` para processamento no pipeline.
- **FR-003**: O sistema DEVE estruturar o processamento em um pipeline desacoplado composto por **3 etapas sequenciais**:
  - **Etapa 1 - Extração de Contexto (Context Extraction & Preprocessing)**;
  - **Etapa 2 - Validação de Conformidade Simulada (Mock Evaluation & Rule Check)**;
  - **Etapa 3 - Consolidação do Veredito (Verdict Synthesis & Formatting)**.
- **FR-004**: O sistema DEVE operar todas as 3 etapas em modo **100% simulado (*mock*)** nesta Fase 1, sem chamadas externas a provedores de LLM.
- **FR-005**: O sistema DEVE emitir resposta no formato canônico de produção com status **negativo por padrão** (`REPROVED` ou `NEEDS_ADJUSTMENT`), pontuação de confiança simulada, lista de inconformidades e recomendações.
- **FR-006 (Índice Operacional em Arquivo)**: O sistema DEVE registrar em `logs/application/` eventos JSONL contendo timestamp, nome da operação, `correlation_id`, status, duração total da execução, referência ao log especializado e eventuais erros.
- **FR-007 (Log Granular de IA em Arquivo)**: O sistema DEVE registrar em `logs/ai/` eventos JSONL para cada etapa individual, contendo `correlation_id`, identificação e ordem da etapa, payload de entrada, payload de saída, status, latência individual da etapa e custo financeiro simulado.
- **FR-008 (Pilha e Rotação de Logs)**: O sistema DEVE utilizar a biblioteca padrão `logging` do Python como interface e `structlog` para serialização JSONL, com rotação automática preservando 7 dias de retenção.
- **FR-009 (Endpoints Administrativos em Tempo Real)**: O sistema DEVE disponibilizar rotas administrativas protegidas (acessíveis apenas por usuários com perfil de Administrador):
  - Rota de streaming em tempo real (Server-Sent Events / SSE) para o Índice Operacional de Eventos;
  - Rota de streaming em tempo real (Server-Sent Events / SSE) para os eventos de IA, estruturados e agrupados por pipeline (`correlation_id`).
- **FR-010 (Módulos de Demonstração em demos/)**: O sistema DEVE disponibilizar **dois módulos interativos** na pasta `demos/`, catalogados em `demos/index.html`:
  - **Módulo 1 (`demos/operational-index/`):** Visualização em tempo real do Índice Operacional;
  - **Módulo 2 (`demos/ai-pipeline/`):** Visualização em tempo real dos pipelines de IA agrupados por execução com detalhamento das etapas.
- **FR-011 (Scripts de Seed)**: O sistema DEVE fornecer script de carga em `scripts/seeds/` para provisionar formulários, campos com flag de IA e dados de submissão necessários para demonstrar os dois módulos de ponta a ponta.
- **FR-012 (Desacoplamento)**: Todo o código de demonstração em `demos/` DEVE ser totalmente desacoplado de `src/`, consumindo apenas a API real com os devidos cabeçalhos de autenticação administrativa.

---

### Key Entities / Concepts

- **FormField.ai_evaluation_enabled**: Booleano indicando elegibilidade do campo para análise por IA.
- **OperationalEventIndex**: Registro cronológico unitário no log geral com duração total e correlação.
- **AIStepExecutionLog**: Registro granular de etapa de IA com entradas, saídas, custo e latência individual.
- **PipelineExecutionGroup**: Agrupamento lógico dos eventos de etapas de IA vinculados ao mesmo `correlation_id` / pipeline de execução.
- **AIEvaluationVerdict**: Estrutura canônica de resultado de avaliação do campo.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos campos de formulário configurados com `ai_evaluation_enabled = true` são identificados e executados pelo pipeline simulado, sem impacto nos campos não marcados.
- **SC-002**: Cada execução gera 1 evento consolidado no Índice Operacional com duração total e exatamente 3 eventos granulares no Log de IA com latência e custo individuais.
- **SC-003**: 100% dos eventos transmitidos no canal de IA em tempo real são agrupados corretamente sob o mesmo identificador de pipeline (`correlation_id`).
- **SC-004**: Usuários não autenticados ou sem privilégio de administrador são bloqueados com código HTTP 401 ou 403 ao tentar acessar os fluxos de telemetria em tempo real.
- **SC-005**: Os dois módulos de demonstração em `demos/` (Índice Operacional e Visualização de IA) operam em tempo real integrados à API real e estão acessíveis a partir do catálogo `demos/index.html`.
- **SC-006**: A rotina de retenção de logs purga arquivos locais com mais de 7 dias de forma automatizada.

---

## Assumptions

- A autenticação administrativa utiliza a infraestrutura de autenticação e tokens existente no backend.
- A transmissão em tempo real utiliza Server-Sent Events (SSE) ou protocolo compatível suportado nativamente pelo FastAPI e navegadores modernos.
- O formato simulado (*mock*) é estritamente mantido na Fase 1, sem chamadas a modelos externos de IA.
- A organização dos arquivos em `logs/` reside na raiz do projeto fora de `src/`.
