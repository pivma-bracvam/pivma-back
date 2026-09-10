# Phase 1 Data Model: Anexos de Arquivo em Formulários

## Visão geral

A feature **reaproveita** o esquema existente. Não há tabela nova. O modelo
`Artifact` passa a ter uma segunda finalidade (anexo de campo, além de dossiê e
relatório de IA), distinguida pela coluna `key`.

## Entidades

### `Artifact` (existente — `src/pivma/core/database/models.py`)

Usada agora também para anexos de formulário.

| Campo | Tipo | Uso para anexo |
|---|---|---|
| `id` | UUID (PK) | Nome do arquivo em disco (`\{id\}\{ext\}`). |
| `process_instance_id` | UUID FK | Processo dono. |
| `activity_run_id` | UUID FK | Execução da atividade do formulário. |
| `key` | String(64) | Constante `'form_attachment'`. |
| `name` | String(255) | Nome original do arquivo (truncado a 255). |
| `file_path` | String(500) | Caminho relativo a `ATTACHMENTS_DIR` (`\{process_id\}/\{artifact_id\}\{ext\}`). |
| `file_size` | BigInteger | Bytes gravados. |
| `mime_type` | String(128) | `content_type` informado pelo cliente. |
| `checksum_sha256` | String(64) | SHA-256 do conteúdo gravado. |
| `metadata_payload` | JSONB | `\{ "field_key": str, "original_filename": str, "extension": str \}`. |
| `status` | String(32) | `'DRAFT'` enquanto o formulário é rascunho; passa a `'SUBMITTED'` na submissão. |
| `AuditMixin` | — | `created_by` = proponente; `set_deletion_audit` na substituição/remoção. |

**Regras**:
- Remoção sempre lógica (`deleted_at`); o arquivo em disco é removido em
  best-effort após o commit.
- Um `Artifact` de anexo só é criado por upload autenticado do proponente.

### `FormValue` (existente)

O vínculo campo ↔ anexo já existe: `file_attachment_id: UUID | None` FK →
`artifacts.id`.

| Campo | Uso |
|---|---|
| `file_attachment_id` | Aponta para o `Artifact` **ativo** do campo (`None` = sem anexo). |
| `text_value` etc. | Permanecem `NULL` para campos `file_upload`. |
| Índice `uq_form_values_active` | `(form_instance_id, form_field_id)` único onde `deleted_at IS NULL` → no máximo 1 `FormValue` por campo, logo no máximo 1 anexo ativo. |

**Transições de `file_attachment_id`**:

```
(sem valor)  --upload-->  A1
   A1        --replace-->  A2   (A1 recebe deleted_at)
   A2        --remove -->  NULL (A2 recebe deleted_at)   [só em rascunho]
   A2        --submit -->  A2   (imutável; status A2 -> SUBMITTED)
```

### `FormField` (existente — sem mudança)

Campo `file_upload` com `validation_rules` opcional:

```yaml
- field_key: "pop_document"
  label: "POP do Método"
  field_type: "file_upload"
  is_required: true
  order_index: 3
  section: "Documentação de Suporte"
  validation_rules:
    allowed_extensions: ["pdf", "docx"]
    max_size_mb: 25
```

### `EvaluationRun` / `EvaluationRunItem` (existente)

Sem coluna nova. Campos de anexo alcançados por uma `EvaluationAssignment` são
registrados como "não avaliados" dentro de `EvaluationRun.evaluated_content_snapshot`
(JSONB já existente) e/ou no `metadata_payload` do `Artifact`
`ai_pre_evaluation_report`, no formato:

```json
{ "field_key": "pop_document", "label": "POP do Método",
  "ai_status": "not_evaluated", "reason": "attachment_not_ai_evaluable" }
```

Nenhum `EvaluationRunItem` é criado para campos de anexo.

## Migração Alembic

**Provavelmente nenhuma.** Todas as colunas necessárias já existem.

Gerar revisão **apenas se** a implementação decidir:
- adicionar `CHECK`/índice para `Artifact.status` ou um índice parcial
  `(activity_run_id, key) WHERE key='form_attachment'` para acelerar a listagem; ou
- qualquer ajuste em `models.py`.

Se gerada, a revisão MUST ter teste de `upgrade` e `downgrade`
(`tests/integration/migrations/`). Caso contrário, registrar em `tasks.md` a
verificação explícita de que `alembic check` não acusa drift.

## Configuração (`Settings` — `src/pivma/core/settings.py`)

| Chave | Tipo | Padrão | Uso |
|---|---|---|---|
| `ATTACHMENTS_DIR` | `str` | `var/attachments` | Raiz do armazenamento em disco. |
| `ATTACHMENT_MAX_SIZE_MB` | `int` | `25` | Teto quando o campo não declara `max_size_mb`. |
| `ATTACHMENT_DEFAULT_EXTENSIONS` | `list[str]` | `["pdf","docx","doc","png","jpg","jpeg"]` | Allowlist quando o campo não declara `allowed_extensions`. |

Todas lidas somente via `Settings` (proibida leitura ad hoc de env — constituição).

## Invariantes

1. No máximo um `Artifact` de anexo ativo (`deleted_at IS NULL`) por
   `(form_instance, field)`.
2. `FormValue.file_attachment_id` só referencia `Artifact` com
   `key='form_attachment'` e `deleted_at IS NULL`, ou é `NULL`.
3. Após `FormInstance.is_submitted = True`, nenhum anexo do formulário muda.
4. O conteúdo binário de um anexo nunca compõe o payload enviado ao provedor de
   IA.
5. `checksum_sha256` grava o hash do que foi persistido; o download entrega bytes
   idênticos.
