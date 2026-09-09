# Research & Architectural Decisions: Pipeline de IA para Formulários (Fase 1 - Estrutura Base e Mock)

**Feature**: `010-form-ai-evaluation-pipeline`  
**Date**: 2026-09-09  
**Status**: Completed

---

## 1. Contexto e Objetivos Técnicos

Esta pesquisa estabelece as decisões arquiteturais para a implementação da Fase 1 da avaliação automatizada de formulários por IA:
1. Pipeline desacoplado em 3 etapas sequenciais totalmente simuladas (*mock*);
2. Retorno canônico de produção com resultado negativo por padrão (`REPROVED` / `NEEDS_ADJUSTMENT`);
3. Arquitetura de observabilidade em duas camadas: **Índice Operacional Geral** e **Log Granular de Etapas de IA**;
4. Formato JSONL fora de `src/` em `logs/`, com retenção de 7 dias;
5. Interface padrão `logging` do Python com `structlog` para serialização;
6. Endpoints administrativos com streaming em tempo real (Server-Sent Events / SSE), agrupando logs de IA pela pipeline de origem;
7. Dois módulos de demonstração interativa em `demos/` e carga via `scripts/seeds/` conforme `AGENTS.md`.

---

## 2. Decisões Arquiteturais

### Decisão 1: Interface de Logging e Serialização JSONL (`logging` + `structlog`)

- **Decisão**: Utilizar `logging.getLogger` da biblioteca padrão do Python em toda a aplicação, integrando formatadores/processadores do `structlog` que serializam os eventos diretamente em JSON Lines (uma linha JSON por evento).
- **Racional**:
  - A interface padrão de `logging` evita acoplamento excessivo do código de domínio a bibliotecas externas.
  - `structlog` oferece renderização JSON estruturada ultrarrápida, adicionando campos padronizados (timestamp ISO 8601, correlation_id, log_level) sem overhead complexo.
  - Sem necessidade de OpenTelemetry ou coletores distribuídos nesta etapa, minimizando complexidade operacional.
- **Alternativas Consideradas**:
  - *OpenTelemetry SDK*: Descartado por ser desnecessariamente complexo para a Fase 1 e introduzir overhead de agentes/coletores externos.
  - *Loguru*: Descartado por substituir o subsistema nativo de logging e gerar acoplamento proprietário.

---

### Decisão 2: Organização de Arquivos e Política de Retenção de 7 Dias

- **Decisão**: Gravação local nos diretórios `logs/application/` (para o Índice Operacional) e `logs/ai/` (para as etapas do pipeline de IA), utilizando `TimedRotatingFileHandler` com rotação diária (`when="midnight"`, `interval=1`, `backupCount=7`).
- **Racional**:
  - Mantém arquivos de log fora de `src/` e devidamente segregados por responsabilidade.
  - O descarte automático dos arquivos com mais de 7 dias é gerenciado nativamente pelo handler da biblioteca padrão sem requerer cron jobs externos no ambiente de desenvolvimento/teste.
  - Formato append-only (JSONL) garante escrita atômica por linha, ideal para streaming e auditoria.
- **Alternativas Consideradas**:
  - *Persistência exclusiva em banco de dados relacional*: Descartada para evitar poluir o banco operacional com grandes volumes de telemetria por etapa e payload.
  - *Stdout puro*: Recomendado para containers em produção, mas a especificação exige explicitamente retenção local de 7 dias em arquivos para depuração.

---

### Decisão 3: Arquitetura do Pipeline de 3 Etapas e Vínculo por `correlation_id`

- **Decisão**: Implementar o pipeline com uma classe orquestradora (`FormAIPipelineEngine`) e 3 etapas modulares com contratos bem definidos:
  - **Etapa 1 - `ContextExtractionStep`**: Extrai os valores submetidos no `FormInstance` para campos onde `ai_evaluation_enabled == True`, agregando rótulos, metadados e regras do `FormField`.
  - **Etapa 2 - `MockEvaluationStep`**: Aplica regras de validação simuladas baseadas em heurísticas estáticas/parametrizadas, gerando inconformidades simuladas realistas.
  - **Etapa 3 - `VerdictSynthesisStep`**: Consolida as inconformidades no contrato canônico de produção (`AIEvaluationVerdict`), definindo status `REPROVED` / `NEEDS_ADJUSTMENT`, score de confiança simulado e recomendações de correção.
- **Racional**:
  - Desacoplamento estrito: cada etapa possui interface única (`execute(context: PipelineContext) -> StepResult`). No futuro, modelos reais (LLMs, RAG) substituirão a `MockEvaluationStep` sem alterar as etapas 1 e 3.
  - Um identificador único (`correlation_id` / `pipeline_run_id`) é gerado no início do pipeline e propagado por todas as etapas.
- **Alternativas Consideradas**:
  - *Função monolítica*: Rejeitada por dificultar a medição isolada de latência/custo por etapa e impedir substituição gradual de etapas futuras.

---

### Decisão 4: Endpoints Administrativos e Streaming em Tempo Real (SSE)

- **Decisão**: Expor endpoints administrativos protegidos por dependência de RBAC (`Role.ADMIN`):
  - `GET /admin/logs/operational/stream`: Stream SSE (`text/event-stream`) de eventos do Índice Operacional.
  - `GET /admin/logs/ai/stream`: Stream SSE (`text/event-stream`) de eventos de IA, emitindo mensagens estruturadas agrupadas por pipeline (`correlation_id`).
  - Endpoints auxiliares `GET /admin/logs/operational` e `GET /admin/logs/ai` para recuperação paginada/filtrada do histórico recente dos arquivos JSONL.
- **Racional**:
  - Server-Sent Events (SSE) é suportado nativamente por FastAPI via `StreamingResponse` e pelo navegador via `EventSource`, sem a complexidade de conexões bidirecionais via WebSocket.
  - A segurança é assegurada pelas dependências existentes de autenticação JWT e verificação de perfil administrador.
- **Alternativas Consideradas**:
  - *WebSockets*: Mais complexo de autenticar e gerenciar conexões persistentes para um fluxo que é estritamente unidirecional (servidor -> cliente).

---

### Decisão 5: Agrupamento dos Logs de IA por Pipeline

- **Decisão**: Tanto no armazenamento quanto na emissão em tempo real e na API, cada registro de etapa de IA inclui metadados de correlação:
  - `correlation_id`: Identificador compartilhado da execução;
  - `pipeline_name`: Ex.: `form_ai_field_evaluation`;
  - `step_order`: 1, 2 ou 3;
  - `step_name`: `context_extraction`, `mock_evaluation`, `verdict_synthesis`.
  Ao transmitir ou consultar via API administrativa, os eventos que compartilham o mesmo `correlation_id` são consolidados ou emitidos com a chave de agrupamento, permitindo que a interface agrupe as 3 etapas sob o mesmo card de pipeline.
- **Racional**:
  - Atende perfeitamente ao requisito do usuário: "no caso da IA eu quero agrupados pela pipeline que puxou todos aqueles registros".

---

### Decisão 6: Módulos de Demonstração em `demos/` e Sementes em `scripts/seeds/` (AGENTS.md)

- **Decisão**:
  - Criar `demos/index.html` como catálogo central de demonstrações;
  - Criar `demos/operational-index/index.html` (Módulo 1: Visão Geral da Plataforma com stream em tempo real do Índice Operacional);
  - Criar `demos/ai-pipeline/index.html` (Módulo 2: Visão da IA com stream em tempo real e agrupamento por pipeline);
  - Criar `scripts/seeds/seed_form_ai_demo.py` provisionando um template de formulário com campos marcados com `ai_evaluation_enabled: true`, instâncias de teste e credenciais de administrador para conexão aos streams.
- **Racional**:
  - Total desacoplamento do núcleo (`src/`): as páginas em `demos/` são arquivos HTML/JS estáticos puros que consomem a API HTTP/SSE do backend com token Bearer.
  - Conformidade estrita com as regras do [`AGENTS.md`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/AGENTS.md).
