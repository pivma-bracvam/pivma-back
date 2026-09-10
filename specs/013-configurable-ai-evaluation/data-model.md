# Phase 1 — Data Model

Feature: Avaliação Configurável por IA na Submissão e Triagem · Branch `013-configurable-ai-evaluation`

Convenções: toda tabela herda `AuditMixin` (`created_at/by`, `updated_at/by`, `deleted_at/by`) e usa **exclusão lógica**. PK `UUID` com `default_factory=uuid4` (padrão de `models.py`). Índices únicos parciais com `postgresql_where=deleted_at IS NULL` (padrão do repositório). Todos os enums são `String(N)` com validação na camada Pydantic/serviço (padrão atual — não usam `Enum` nativo do Postgres).

Uma única migração autogerada: `<hash>_configurable_ai_evaluation.py`, com teste up/down.

---

## Enums (valores canônicos)

| Enum | Valores |
|---|---|
| `evaluation_mode` | `simple`, `advanced` |
| `evaluation_version_status` | `draft`, `published` |
| `criterion_check_type` | `presence`, `conformity`, `quality`, `comparison`, `cross_field_consistency` |
| `criterion_polarity` | `positive`, `negative`, `consistency` |
| `criterion_severity` | `info`, `low`, `medium`, `high`, `critical` |
| `criterion_on_missing` | `non_compliant`, `indeterminate` |
| `assignment_target_type` | `field`, `field_set`, `document`, `form`, `process` |
| `evaluation_run_status` | `in_progress`, `completed`, `failed` |
| `consolidated_result` | `positive`, `negative` |
| `item_conclusion` | `compliant`, `non_compliant`, `partial`, `indeterminate` |
| `evidence_completeness` | `sufficient`, `partial`, `insufficient` |
| `reviewer_verdict` | `agree`, `disagree`, `inconclusive` |

---

## 1. `evaluation_definitions` — item da biblioteca

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `name` | String(255) | rótulo (ex.: "Verificação de estrutura de POP") |
| `slug` | String(80) | único ativo; gerado de `name` |
| `description` | Text? | |
| `mode` | `evaluation_mode` | default `simple` |

Relações: 1—N `evaluation_versions`, 1—N `evaluation_assignments`.
Índice: único parcial `(slug)`.

## 2. `evaluation_versions` — versão publicável e imutável

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `definition_id` | UUID FK → evaluation_definitions | |
| `version_number` | Integer | ≥ 1 |
| `status` | `evaluation_version_status` | default `draft` |
| `objective` | Text | o "objetivo" em linguagem natural |
| `references` | JSONB | snapshot: `[{reference_id, identifier, version_label}]` |
| `test_run_count` | Integer | default 0; alimenta o aviso de publicação (FR-020) |
| `published_at` | datetime? | |
| `published_by` | UUID? FK → users | |

Relações: 1—N `evaluation_criteria`, 1—N `evaluation_runs`.
Índices: único parcial `(definition_id, version_number)`; único parcial `(definition_id)` **onde `status='draft'`** (garante 1 draft por vez).

**Transições de estado**:

```
(novo)  ──create──▶  draft
draft   ──PATCH────▶  draft          (edição livre)
draft   ──test─────▶  draft          (test_run_count++)
draft   ──publish──▶  published      (valida ≥1 critério; congela objective/criteria/references)
published ──PATCH──▶  409  (obrigatório POST /versions → novo draft clonado)
```

Regra: uma vez `published`, nenhuma linha de `evaluation_criteria` da versão pode ser inserida, alterada ou logicamente excluída (validado no serviço + teste de integração).

## 3. `evaluation_criteria` — unidade de verificação

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `version_id` | UUID FK → evaluation_versions | |
| `order_index` | Integer | default 0 |
| `statement` | Text | enunciado em linguagem natural |
| `check_type` | `criterion_check_type` | |
| `polarity` | `criterion_polarity` | default `positive` |
| `required_evidence` | Text? | "o que a IA deve considerar como evidência" |
| `severity` | `criterion_severity` | default `medium` |
| `on_missing_info` | `criterion_on_missing` | default `indeterminate` |
| `recommendation_hint` | Text? | recomendação sugerida ao triador em caso de não conformidade |

Índice: `(version_id, order_index)`.

## 4. `evaluation_references` — catálogo de referências normativas

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `identifier` | String(64) | ex.: `OECD 442B` |
| `label` | String(255) | descrição |
| `version_label` | String(64) | ex.: `2024` |
| `reference_date` | Date? | |

Índice: único parcial `(identifier, version_label)`.
Sem ingestão de texto, sem embeddings nesta versão.

## 5. `evaluation_assignments` — associação avaliação ↔ alvo de formulário

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `form_template_id` | UUID FK → form_templates | |
| `definition_id` | UUID FK → evaluation_definitions | |
| `pinned_version_id` | UUID? FK → evaluation_versions | `null` = usar a última **publicada** |
| `target_type` | `assignment_target_type` | |
| `field_keys` | JSONB | lista de `field_key` do template (vazia p/ `form`/`process`) |
| `enabled` | Boolean | default true |

Índice: `(form_template_id)`; único parcial `(form_template_id, definition_id, target_type, field_keys)`.
Nota: `form_fields.ai_evaluation_enabled` permanece e passa a significar apenas "disponível para avaliação automatizada"; `ai_context_instructions`/`ai_validation_rules` mantidos por compat. com a Spec 012 (não removidos).

## 6. `evaluation_runs` — execução de pré-avaliação (imutável)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `process_instance_id` | UUID FK → process_instances | |
| `activity_run_id` | UUID FK → activity_runs | a run de submissão avaliada |
| `form_instance_id` | UUID FK → form_instances | |
| `correlation_id` | UUID | = chave de correlação nos logs |
| `status` | `evaluation_run_status` | default `in_progress` |
| `consolidated_result` | `consolidated_result`? | preenchido ao concluir |
| `provider_name` | String(32)? | `openai` \| `fake` |
| `models_used` | JSONB | `{extraction, fast, reasoning}` |
| `real_cost` | Numeric(12,6) | default 0 |
| `started_at` | datetime | |
| `finished_at` | datetime? | |
| `error_summary` | Text? | mensagem genérica em caso de `failed` |

Relações: 1—N `evaluation_run_items`, 0/1 `direct_review_requests`.
Índice: `(process_instance_id, started_at desc)`, `(status)` (para a varredura de presas).
Regra: após `status ∈ {completed, failed}`, a linha e seus itens são imutáveis (FR-046).

## 7. `evaluation_run_items` — resultado por critério (append-only, snapshot)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK → evaluation_runs | |
| `criterion_id` | UUID FK → evaluation_criteria | referência (para métricas) |
| `criterion_statement` | Text | **snapshot** |
| `check_type` | `criterion_check_type` | snapshot |
| `polarity` | `criterion_polarity` | snapshot |
| `severity` | `criterion_severity` | snapshot |
| `conclusion` | `item_conclusion` | |
| `is_alert` | Boolean | true = ponto de atenção que não barra |
| `evidence_excerpt` | Text? | trecho citado |
| `evidence_location` | Text? | ex.: "Seção 5 — Procedimento" |
| `justification` | Text? | |
| `recommendation` | Text? | |
| `inference_confidence` | Float? | secundário, não exibido como primário |
| `evidence_completeness` | `evidence_completeness`? | |
| `model_layer` | String(16) | `extraction`\|`fast`\|`reasoning` usado |

Índice: `(run_id)`, `(criterion_id)`.

## 8. `direct_review_requests` — proponente ignora a IA (append-only)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `evaluation_run_id` | UUID FK → evaluation_runs | |
| `process_instance_id` | UUID FK → process_instances | |
| `requested_by` | UUID FK → users | |
| `justification` | Text? | |

Índice: único parcial `(evaluation_run_id)` (impede duplicidade — FR-038).

## 9. `reviewer_feedback` — concordância do triador por critério (append-only)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `run_item_id` | UUID FK → evaluation_run_items | |
| `reviewer_id` | UUID FK → users | |
| `verdict` | `reviewer_verdict` | |
| `reason` | Text? | |

Índice: único parcial `(run_item_id, reviewer_id)`.
Uso: apenas auditoria e métricas de concordância (FR-041/FR-042). Nunca alimenta treino.

## 10. `evaluation_test_runs` — execução do modo de teste

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | |
| `version_id` | UUID FK → evaluation_versions | deve estar `draft` |
| `sample_content` | Text | conteúdo de exemplo fornecido |
| `result_payload` | JSONB | resultado por critério (não normalizado em tabela) |
| `real_cost` | Numeric(12,6) | default 0 |

Índice: `(version_id, created_at desc)`.

---

## Relações (resumo)

```
evaluation_definitions 1─N evaluation_versions 1─N evaluation_criteria
evaluation_definitions 1─N evaluation_assignments N─1 form_templates
evaluation_versions   1─N evaluation_runs 1─N evaluation_run_items 1─N reviewer_feedback
evaluation_runs        1─0/1 direct_review_requests
evaluation_versions   1─N evaluation_test_runs
evaluation_references  (catálogo; snapshot em evaluation_versions.references JSONB)

process_instances 1─N evaluation_runs        (nova relação)
activity_runs     1─N evaluation_runs        (a run de submissão avaliada)
```

## Métricas de concordância (derivadas, sem tabela)

`GET /ai-evaluations/agreement-metrics` calcula on-the-fly a partir de `reviewer_feedback` ⨝ `evaluation_run_items`:
- taxa de concordância global e por `check_type`;
- critérios (`criterion_id`) com maior taxa de `disagree`;
- execuções com maior nº de `disagree`.

## Impacto em modelos existentes

| Modelo | Mudança |
|---|---|
| `FormField` | Sem mudança de coluna; `ai_evaluation_enabled` reinterpretado (documentação/serviço). |
| `ProcessInstance` | Sem coluna nova; novo `status` lógico durante pré-avaliação continua sendo `SUBMISSION` (a triagem permanece `BLOCKED` até o resultado). |
| `Artifact` | Reuso: artefato `key='ai_pre_evaluation_report'` com `metadata_payload` = relatório consolidado (substitui `ai_evaluation_report` da Spec 010). |
| `AuditEvent` | Novos `event_type`: `AI_PRE_EVALUATION_STARTED`, `AI_PRE_EVALUATION_COMPLETED`, `AI_PRE_EVALUATION_FAILED`, `DIRECT_REVIEW_REQUESTED`, `AI_CRITERION_FEEDBACK_RECORDED`. |
