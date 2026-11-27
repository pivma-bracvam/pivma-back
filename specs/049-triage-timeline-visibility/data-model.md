# Data Model: Visibilidade da triagem e cegamento na linha do tempo

Nenhuma tabela ou coluna nova. A feature muda dados de uma coluna e a leitura de três entidades.

## ActivityInstance (`activity_instances`)

| Campo | Mudança |
|---|---|
| `view_roles` (`text[]`) | Em `key = 'triage_evaluation'`, passa a conter `proponent`. Processos novos recebem pelo template (R1); existentes, pela migração (R2). |
| `edit_roles` (`text[]`) | Sem mudança: `['bracvam']`. |

Regras:
- A migração não duplica `proponent` (idempotente) e o downgrade o retira.
- `admin` e `bracvam` continuam vendo toda atividade pela regra da Spec 030.

## ProcessTemplateVersion

Cada um dos cinco templates ganha uma versão nova com a concessão. Processos já criados continuam ligados à versão antiga; a migração cobre as instâncias deles.

## AuditEvent (`audit_events`), leitura em `GET /processes/{id}/timeline`

Nada muda na gravação: `user_id`, `activity_run_id` e `context_data` continuam completos.

Visibilidade do evento (antes da paginação):

| Tipo | Quem recebe |
|---|---|
| `FIELD_REVIEWED` | Só quem tem `triage.review` (e passa pelo filtro de atividade). |
| `INVITE_CREATED`, `INVITE_RESENT`, `INVITE_REVOKED` | Só quem gerencia participantes. |
| `INVITE_ACCEPTED` | Quem gerencia participantes, e o autor do aceite. |
| Demais | Regras atuais (atividade, laboratório, designação). |

Visibilidade do autor (`user_id` na resposta):

| Condição | `user_id` |
|---|---|
| Tipo em `TRIAGE_AUTHOR_EVENTS` e usuário sem `triage.review` | nulo |
| Usuário só com cargos de revisão cega e autor é proponente ou titular de cargo de revisão cega do processo (exceto ele mesmo) | nulo |
| Demais | o autor gravado |

## FieldReview (`field_reviews`), leitura em `GET .../form`

| Leitor | `reviews` |
|---|---|
| Com `triage.review` | Todos os pareceres do formulário (inclui rascunho). |
| Sem `triage.review` | Só os pareceres cuja execução de triagem (`activity_run_id`) está `COMPLETED`. |

`reviewed_by` continua fora da resposta (`FieldReviewSummary`).
