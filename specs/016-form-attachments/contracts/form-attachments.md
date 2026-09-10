# Contrato HTTP: Anexos de Formulário

Base: rotas aninhadas ao formulário de uma atividade, no router
`src/pivma/routers/forms.py` (prefixo `/processes`, tag `Forms`).

Todas exigem autenticação (`CurrentUser`, cookie `access_token` ou
`Authorization: Bearer`). `POST` e `DELETE` exigem também `Origin` confiável
(`TrustedOrigin`).

`\{field_key\}` deve referenciar um `FormField` do formulário cujo
`field_type == 'file_upload'`.

---

## 1. Enviar / substituir anexo

```
POST /processes/{id}/activities/{activity_key}/form/fields/{field_key}/attachment
Content-Type: multipart/form-data
```

**Form fields**: `file` (binário, obrigatório).

**Pré-condições**: chamador é o proponente efetivo ativo; formulário em rascunho
(`is_submitted = false`); campo existe e é `file_upload`.

**Comportamento**: valida extensão e tamanho; calcula SHA-256; grava em disco;
se já havia anexo no campo, o anterior é removido logicamente; `FormValue.
file_attachment_id` passa a apontar para o novo `Artifact`; registra `AuditEvent`
`FORM_ATTACHMENT_UPLOADED`.

**200 OK**

```json
{
  "field_key": "pop_document",
  "attachment": {
    "artifact_id": "0e1c…",
    "filename": "POP-irritacao-cutanea.pdf",
    "size": 184320,
    "mime_type": "application/pdf",
    "extension": "pdf",
    "checksum_sha256": "9f2b…",
    "uploaded_at": "2026-09-10T13:40:12Z",
    "replaced_previous": false
  }
}
```

**Erros**

| Status | `code` | Situação |
|---|---|---|
| 400 | `empty_file` | Sem parte `file` ou arquivo de 0 byte. |
| 403 | `Invalid origin` | `Origin` fora de `AUTH_ALLOWED_ORIGINS`. |
| 404 | — | Processo/atividade/formulário não visível ao chamador, ou `field_key` inexistente. |
| 409 | `form_submitted` | Formulário já submetido (imutável). |
| 413 | `file_too_large` | Excede `max_size_mb` do campo ou `ATTACHMENT_MAX_SIZE_MB`. |
| 422 | `extension_not_allowed` | Extensão fora de `allowed_extensions` / allowlist padrão. |
| 422 | `not_a_file_field` | `field_key` não é `file_upload`. |

Toda recusa preserva o anexo anterior do campo, se houver.

---

## 2. Baixar anexo

```
GET /processes/{id}/activities/{activity_key}/form/fields/{field_key}/attachment
```

**Pré-condições**: chamador tem escopo de leitura sobre o formulário do processo
(mesma regra de `get_current_form_instance`: proponente dono enquanto sob o
proponente; avaliador de triagem autorizado e admin depois).

**200 OK**: corpo = bytes do arquivo original.
Headers: `Content-Type: <mime_type>`,
`Content-Disposition: attachment; filename*=UTF-8''<nome-sanitizado>`,
`Content-Length: <file_size>`, `ETag: "<checksum_sha256>"`.

**Erros**

| Status | Situação |
|---|---|
| 401 | Sem autenticação. |
| 404 | Sem escopo de leitura, campo sem anexo, ou recurso inexistente (não revela qual). |

---

## 3. Remover anexo

```
DELETE /processes/{id}/activities/{activity_key}/form/fields/{field_key}/attachment
```

**Pré-condições**: proponente efetivo ativo; formulário em rascunho.

**Comportamento**: `Artifact` recebe `set_deletion_audit`;
`FormValue.file_attachment_id` → `NULL`; arquivo em disco removido best-effort;
`AuditEvent` `FORM_ATTACHMENT_REMOVED`.

**200 OK**

```json
{ "field_key": "pop_document", "removed": true }
```

**Erros**

| Status | `code` | Situação |
|---|---|---|
| 403 | `Invalid origin` | Origin não confiável. |
| 404 | — | Recurso não visível / `field_key` inexistente / campo sem anexo. |
| 409 | `form_submitted` | Formulário já submetido. |

---

## 4. Efeitos nas rotas existentes de formulário

### `GET /processes/{id}/activities/{activity_key}/form`

Para cada campo `file_upload`, a resposta passa a incluir os metadados do anexo
presente (ou `null`):

```json
{
  "fields": [
    {
      "field_key": "pop_document",
      "field_type": "file_upload",
      "is_required": true,
      "attachment": {
        "artifact_id": "0e1c…",
        "filename": "POP-irritacao-cutanea.pdf",
        "size": 184320,
        "mime_type": "application/pdf",
        "checksum_sha256": "9f2b…",
        "uploaded_at": "2026-09-10T13:40:12Z"
      }
    }
  ],
  "values": { "method_title": "…" }
}
```

`values` **não** contém chaves de campos `file_upload`.

### `PUT /processes/{id}/activities/{activity_key}/form` (rascunho)

- Concluir com sucesso quando o formulário contém campos `file_upload` sem valor
  no corpo (nenhuma regressão).
- Se o corpo trouxer uma chave de campo `file_upload`, `422` com
  `code: "invalid_form_values"` e erro de campo
  `code: "file_upload_uses_attachment_endpoint"`.

### `POST /processes/{id}/activities/{activity_key}/form` (submissão)

- Se um campo `file_upload` `is_required` não tiver `Artifact` ativo vinculado,
  `422` com erro de campo `code: "attachment_required"` (a submissão inteira
  falha, atômica).
- Na submissão bem-sucedida, o dossiê (`Artifact` `key='proposal_dossier'`)
  ganha `metadata_payload["attachments"]` e os `Artifact` de anexo passam a
  `status='SUBMITTED'`.

### Pré-avaliação por IA

- Campos `file_upload` são excluídos do conteúdo enviado ao provedor.
- Cada campo de anexo alcançado por uma `EvaluationAssignment` é registrado no
  `evaluated_content_snapshot`/relatório como
  `\{ "ai_status": "not_evaluated", "reason": "attachment_not_ai_evaluable" \}`.
- Execução com apenas campos de anexo alcançados conclui `completed` e o processo
  segue para triagem (equivalente a "sem IA associada").
