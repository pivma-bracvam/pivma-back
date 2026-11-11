# Data Model: Retorno ao Proponente

Sem tabela, coluna ou migração.

## Entidades existentes

| Entidade | Uso nesta entrega |
|---|---|
| `FieldReview` | Leitura por execução da submissão. Não muda. |
| `FormField` | Fornece `field_key`, inclusive de campo com exclusão lógica. |
| `ActivityRun` de `submission_return_review` | Identifica os envios do retorno. O cancelamento passa a travar a linha e só alcança retorno de origem `AI_PRE_EVALUATION`. |
| `EvaluationRun` | O reprocessamento passa a travar a linha. |
| `Notification` | Novo `kind`, sem alteração de estrutura. |
| `AuditEvent` | Novo `event_type`, `RETURN_REVIEW_CANCELLED`, com `source` e `run_number`. |

## Novo tipo de envio

| Campo | Valor |
|---|---|
| `kind` | `submission_returned_email` |
| `channel` | `email` |
| `subject_type` | `submission_return_review` |
| `subject_id` | ID da `ActivityRun` do retorno |
| `process_instance_id` | ID do processo |
| `expires_at` | nulo |

Payload criptografado: `process_code`, `process_title`, `source` e `due_date`
(ISO ou nulo).

## Transições

```text
retorno aberto -> e-mail pending
pending -> sent | failed       (worker)
pending -> cancelled           (reprocessamento ou exclusão do processo; error_code return_review_cancelled)
```

`EvaluationRun` `failed` só gera nova execução se for a mais recente e se o
retorno da IA estiver aberto. A execução antiga continua `failed`, e a nova
mantém o `created_by` da antiga.
