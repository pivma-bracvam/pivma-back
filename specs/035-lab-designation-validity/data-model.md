# Data Model: Validade da designação laboratorial

Nenhuma tabela, coluna, índice ou migração nova. A feature muda uma regra de
leitura e acrescenta dois tipos de evento a uma tabela existente.

## Designação (`assignments`, Spec 006) — sem mudança de esquema

| Estado | Condição |
|---|---|
| Ativa | `revoked_at IS NULL` e `deleted_at IS NULL` |
| Efetiva | ativa, usuário ativo e, se `role_key` for `lead_laboratory` ou `participating_laboratory`, vínculo ativo com `laboratory_id` e laboratório e instituição ativos |

Transições de efetividade (a designação continua ativa em todas):

```text
efetiva ──(vínculo encerrado | laboratório inativado | instituição inativada)──▶ não efetiva
não efetiva ──(novo vínculo com o mesmo laboratório, laboratório e instituição ativos)──▶ efetiva
```

A revogação continua sendo a única forma de encerrar o ciclo (Spec 006,
FR-007).

## Vínculo institucional (`user_institutional_affiliations`, Spec 005) — sem mudança

Ativo quando `deleted_at IS NULL`, com usuário, instituição e laboratório
ativos. O índice `uq_affiliations_active_laboratory` garante no máximo um
vínculo ativo por usuário, instituição e laboratório.

## Evento de auditoria (`audit_events`) — novos valores de `event_type`

| Campo | Valor |
|---|---|
| `event_type` | `PARTICIPANT_EFFECTIVENESS_LOST` ou `PARTICIPANT_EFFECTIVENESS_RESTORED` |
| `process_instance_id` | processo da designação (só processos em andamento, FR-008a) |
| `user_id` | responsável pela ação institucional |
| `activity_run_id` | `NULL` |
| `occurred_at` | momento da ação |
| `context_data.assignment_id` | designação afetada |
| `context_data.participant_user_id` | pessoa designada |
| `context_data.role_key` | `lead_laboratory` ou `participating_laboratory` |
| `context_data.laboratory_id` | laboratório da designação |
| `context_data.result` | `success` |
| `context_data.source` | `institutional` |
| `context_data.reason` | `affiliation_ended`, `laboratory_deactivated`, `institution_deactivated` ou `affiliation_created` |

Regras:

- Um evento por designação por ação. Não há evento quando o estado de
  efetividade não muda (FR-010).
- O evento é gravado na mesma transação da ação institucional (FR-011).
- Os eventos são imutáveis, como os demais de `audit_events` (Spec 006,
  FR-026).
