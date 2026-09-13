# Modelo de Dados: Ciclo de Vida de Processos

## ProcessInstance

Entidade persistida em `process_instances`; não requer coluna nova.

| Campo | Uso nesta feature |
|---|---|
| `status` | Recebe `CANCELLED` no cancelamento e `ARCHIVED` no arquivamento. Estados existentes continuam inalterados. |
| `closed_at` | Preenchido no cancelamento; preservado no arquivamento. |
| `closure_reason` | Mantém razões de fechamento técnico já existentes; não recebe cancelamento, desistência ou arquivamento. |
| `created_by` | Apoia a rastreabilidade; a autorização efetiva usa a atribuição ativa de proponente. |

### Derivação de ciclo de vida

- `never_submitted`: não existe `AuditEvent` com
  `event_type = SUBMISSION_SUBMITTED` para o processo; um envio formal
  histórico nunca reabre a condição de rascunho.
- `operational`: processo existente, submetido e com status diferente de `CLOSED`, `CANCELLED` e `ARCHIVED`.
- `archivable`: processo existente e com status `CLOSED` ou `CANCELLED`.
- `immutable`: processo com status `CLOSED`, `CANCELLED` ou `ARCHIVED`; nenhuma mutação operacional é aceita.

### Transições

| Ação | Pré-condição | Resultado |
|---|---|---|
| `DELETE_DRAFT` | `never_submitted`; proponente efetivo | O sistema remove fisicamente o agregado inteiro; o status não recebe `DELETED`. |
| `WITHDRAW` | `status=SUBMISSION`, evento `REVISION_REQUESTED`; proponente efetivo | `status=CANCELLED`, `closed_at=agora`; preserva o histórico. |
| `CANCEL` | Processo submetido e operacional; `triage.review`, sem conflito | `status=CANCELLED`, `closed_at=agora`. |
| `ARCHIVE` | `status=CLOSED` ou `CANCELLED`; `triage.review`, sem conflito | `status=ARCHIVED`; o evento retém o status anterior. |

Nenhuma operação de ciclo de vida exige justificativa. Cancelamento e desistência registram ação, estado antes/depois, autor, momento e contagens de filhos cancelados; arquivamento registra ação, estado antes/depois, autor e momento. A regra de ação e a atualização persistem sob o mesmo bloqueio de processo e a mesma transação.

## Trabalho subordinado

| Entidade | Relação | Tratamento no cancelamento |
|---|---|---|
| `Phase` | Pertence ao processo | Estado não terminal passa a `CANCELLED`; `COMPLETED` é preservado. |
| `ActivityInstance` | Pertence ao processo/fase | Estado não terminal passa a `CANCELLED`; não é desbloqueada depois. |
| `ActivityRun` | Pertence à atividade | Estado não terminal passa a `CANCELLED`, com encerramento quando o modelo já o suporta. |
| `Task` | Pertence a uma execução | Estado não terminal passa a `CANCELLED`; itens concluídos não mudam. |
| `EvaluationRun` | Vinculada ao processo/executa pré-avaliação | Execução `in_progress` passa a `CANCELLED`; o worker não roteia resultado tardio. |
| `FormInstance` | Vinculada à execução | Não ganha estado novo, não é submetida artificialmente e permanece somente leitura por causa da guarda do processo/run. |
| `Artifact`, `Decision`, `FormValue`, `AuditEvent` | Histórico vinculado | Não são removidos nem reescritos. |

### Remoção física do rascunho

`DELETE_DRAFT` remove o agregado inteiro: `ProcessInstance`, fases, atividades, execuções, tarefas, formulários, valores, atribuições, decisões, execuções de avaliação, artefatos e eventos vinculados. Os binários em `ATTACHMENTS_DIR/{process_id}/` também são removidos. A implementação deve eliminar referências de valores para artefatos antes do artefato e respeitar a ordem das chaves estrangeiras. Um processo com submissão formal nunca usa essa remoção.

## AuditEvent

Eventos novos, imutáveis e com `context_data` estruturado:

| `event_type` | Campos mínimos em `context_data` |
|---|---|
| `PROCESS_CANCELLED` | campos acima e `cancelled_counts` por tipo de filho |
| `PROCESS_WITHDRAWN_BY_PROPONENT` | `previous_status`, `result_status` e `cancelled_counts` por tipo de filho |
| `PROCESS_ARCHIVED` | `previous_status`, `result_status` |

`user_id` e `occurred_at` são persistidos pelo próprio `AuditEvent`. O status terminal anterior do arquivamento é obtido deste evento na linha do tempo histórica. A exclusão física não cria evento: ela remove os eventos do agregado.

## Projeção para a interface

`ProcessInstanceDetail` expõe `available_actions`, lista de códigos de `DELETE_DRAFT`, `WITHDRAW`, `CANCEL` e `ARCHIVE` calculada para o usuário autenticado. A lista é vazia para recurso terminal sem ação permitida e nunca substitui a revalidação do comando.
