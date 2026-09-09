# Data Model: Pipeline de IA para Formulários (Fase 1 - Estrutura Base e Mock)

**Feature**: `010-form-ai-evaluation-pipeline`  
**Date**: 2026-09-09  
**Status**: Completed

---

## 1. Visão Geral das Entidades e Esquemas

O modelo de dados desta funcionalidade é composto por:
1. **Extensão de Definição de Campo (`FormField`)**: Configuração declarativa de habilitação de IA.
2. **Registro do Índice Operacional (`OperationalEventIndex`)**: Formato JSONL append-only para o log geral da plataforma.
3. **Registro de Etapa do Pipeline de IA (`AIStepExecutionLog`)**: Formato JSONL append-only para telemetria granular.
4. **Grupo de Execução da Pipeline (`PipelineExecutionGroup`)**: Estrutura agregada utilizada na API administrativa e em tempo real.
5. **Veredito Canônico de Produção (`AIEvaluationVerdict`)**: Contrato padronizado de resposta da avaliação.

---

## 2. Modelos e Esquemas

### 2.1 Extensão no Esquema de `FormField`

Na tabela `form_fields` (e nos esquemas Pydantic / definições YAML):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `ai_evaluation_enabled` | `bool` | Sim (default `False`) | Determina se o campo é analisado pelo pipeline de IA |
| `ai_context_instructions`| `str \| None` | Não (default `None`) | Diretrizes ou critérios específicos para a IA analisar o campo |
| `ai_validation_rules` | `dict \| None` | Não (default `None`) | Regras de validação complementares direcionadas à IA (JSONB) |

---

### 2.2 Índice Operacional de Eventos (`OperationalEventIndex`)

Formato de cada linha gravada em `logs/application/events_YYYY-MM-DD.jsonl`:

```json
{
  "event_id": "c1f7a23b-489e-4c28-941d-d248b61ad1b2",
  "timestamp": "2026-09-09T10:15:30.123456Z",
  "operation_type": "FORM_AI_EVALUATION",
  "correlation_id": "9f273010-53bc-426b-8d5f-9aa07119f390",
  "actor_user_id": "3b29c54e-128a-40a8-b647-7977a4eb14c8",
  "resource_id": "form_instance_id_uuid",
  "status": "SUCCESS",
  "total_duration_ms": 142.5,
  "specialized_log_ref": "logs/ai/ai_steps_2026-09-09.jsonl#9f273010-53bc-426b-8d5f-9aa07119f390",
  "error_summary": null,
  "metadata": {
    "fields_evaluated_count": 2,
    "total_simulated_cost": 0.0042
  }
}
```

#### Atributos:
- **`event_id`**: Identificador único global do evento.
- **`timestamp`**: Data/hora ISO 8601 em UTC.
- **`operation_type`**: Tipo da operação de alto nível (ex.: `FORM_AI_EVALUATION`, `HTTP_REQUEST`, `SUBMISSION_TRIAGE`).
- **`correlation_id`**: Chave de rastreabilidade única que interliga o evento aos logs especializados.
- **`status`**: `SUCCESS` | `FAILED` | `INTERRUPTED`.
- **`total_duration_ms`**: Duração total da execução em milissegundos.
- **`specialized_log_ref`**: Ponteiro/referência para o log granular especializado.
- **`error_summary`**: Mensagem resumida em caso de falha.

---

### 2.3 Log Granular de Etapas de IA (`AIStepExecutionLog`)

Formato de cada linha gravada em `logs/ai/ai_steps_YYYY-MM-DD.jsonl`:

```json
{
  "event_id": "8a32b11e-913a-4428-b80c-03d8b11cf291",
  "timestamp": "2026-09-09T10:15:30.150000Z",
  "correlation_id": "9f273010-53bc-426b-8d5f-9aa07119f390",
  "pipeline_name": "form_ai_field_evaluation",
  "field_key": "scientific_justification",
  "step_order": 1,
  "step_name": "context_extraction",
  "status": "SUCCESS",
  "step_duration_ms": 12.3,
  "simulated_cost": 0.0005,
  "input_payload": {
    "field_key": "scientific_justification",
    "field_label": "Justificativa Científica",
    "submitted_value": "Texto preliminar da proposta...",
    "instructions": "Verificar se o mecanismo biológico alternativo está fundamentado."
  },
  "output_payload": {
    "sanitized_context": "Texto preliminar da proposta...",
    "token_count_estimate": 45
  },
  "error_details": null
}
```

#### Atributos:
- **`correlation_id`**: Chave de correlação associada ao Índice Operacional.
- **`pipeline_name`**: Identificador do pipeline (`form_ai_field_evaluation`).
- **`field_key`**: Identificador do campo de formulário em análise.
- **`step_order`**: Ordem sequencial da etapa (`1`, `2` ou `3`).
- **`step_name`**: Nome semântico da etapa (`context_extraction`, `mock_evaluation`, `verdict_synthesis`).
- **`status`**: `SUCCESS` | `FAILED`.
- **`step_duration_ms`**: Tempo de execução daquela etapa isolada em milissegundos.
- **`simulated_cost`**: Custo financeiro simulado da etapa em USD (ex.: `$0.0012`).
- **`input_payload`**: Objeto JSON com as entradas recebidas pela etapa.
- **`output_payload`**: Objeto JSON com as saídas geradas pela etapa.
- **`error_details`**: Detalhes estruturados de erro/stack trace em caso de falha.

---

### 2.4 Grupo Agrupado por Pipeline (`PipelineExecutionGroup`)

Estrutura consolidada fornecida na API e nas mensagens de stream para permitir a visualização agrupada das etapas:

```json
{
  "correlation_id": "9f273010-53bc-426b-8d5f-9aa07119f390",
  "pipeline_name": "form_ai_field_evaluation",
  "form_instance_id": "2e09c85b-b99f-431f-a589-9a7065964cf5",
  "field_key": "scientific_justification",
  "status": "COMPLETED",
  "started_at": "2026-09-09T10:15:30.123456Z",
  "completed_at": "2026-09-09T10:15:30.265956Z",
  "total_duration_ms": 142.5,
  "total_cost": 0.0035,
  "steps": [
    { "step_order": 1, "step_name": "context_extraction", "status": "SUCCESS", "step_duration_ms": 12.3, "simulated_cost": 0.0005, ... },
    { "step_order": 2, "step_name": "mock_evaluation", "status": "SUCCESS", "step_duration_ms": 98.2, "simulated_cost": 0.0020, ... },
    { "step_order": 3, "step_name": "verdict_synthesis", "status": "SUCCESS", "step_duration_ms": 32.0, "simulated_cost": 0.0010, ... }
  ],
  "verdict": {
    "status": "REPROVED",
    "confidence_score": 0.88,
    "issues": [
      "A justificativa técnica não apresenta dados comparativos de citotoxicidade prévia.",
      "Ausência de detalhamento quanto aos controles positivos e negativos utilizados."
    ],
    "recommendations": [
      "Incluir referências bibliográficas de estudos de viabilidade celular com os mesmos reagentes.",
      "Descrever explicitamente os controles metodológicos de validação."
    ]
  }
}
```

---

### 2.5 Veredito Canônico de Produção (`AIEvaluationVerdict`)

| Atributo | Tipo | Descrição |
|---|---|---|
| `field_key` | `str` | Identificador do campo avaliado |
| `status` | `str` | `REPROVED` \| `NEEDS_ADJUSTMENT` \| `APPROVED` (negativo por padrão na Fase 1) |
| `confidence_score` | `float` | Grau de confiança simulado da análise (0.0 a 1.0) |
| `issues` | `list[str]` | Lista de inconformidades ou pendências identificadas |
| `recommendations` | `list[str]` | Sugestões acionáveis para o proponente adequar o preenchimento |
| `evaluated_at` | `datetime` | Timestamp da emissão do veredito |
