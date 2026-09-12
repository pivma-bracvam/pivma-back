# Modelo de Dados: Ciclo de Vida de Processos

## ProcessInstance

Entidade persistida em `process_instances`; não requer coluna nova.

| Campo | Uso nesta feature |
|---|---|
| `status` | Recebe `CANCELLED` no cancelamento e `ARCHIVED` no arquivamento. Estados existentes continuam inalterados. |
| `closed_at` | Preenchido no cancelamento; preservado no arquivamento. |
| `closure_reason` | Guarda a justificativa de cancelamento; não é reescrita ao arquivar. |
| `created_by` | Apoia a rastreabilidade; a autorização efetiva usa a atribuição ativa de proponente. |

### Derivação de ciclo de vida

- `never_submitted`: não existe `AuditEvent` com
  `event_type = SUBMISSION_SUBMITTED` para o processo; um envio formal
  histórico nunca reabre a condição de rascunho.
- `operational`: processo existente, submetido e com status diferente de `CLOSED`, `CANCELLED` e `ARCHIVED`.
- `archivable`: processo existente e com status `CLOSED` ou `CANCELLED`.
- `immutable`: processo com status `CANCELLED` ou `ARCHIVED`; nenhuma mutação operacional é aceita.

### Transições

| Ação | Pré-condição | Resultado |
|---|---|---|
| `DELETE_DRAFT` | `never_submitted`; proponente efetivo ou acesso de plataforma | O sistema remove fisicamente o agregado inteiro; o status não recebe `DELETED`. |
| `CANCEL` | Processo submetido e operacional; acesso de plataforma | `status=CANCELLED`, `closed_at=agora`, `closure_reason=justificativa`. |
| `ARCHIVE` | `status=CLOSED` ou `CANCELLED`; acesso de plataforma | `status=ARCHIVED`; o evento retém o status anterior e a justificativa. |

Todas exigem justificativa aparada, não vazia e limitada a 2.000 caracteres. Cancelamento e arquivamento registram ação, estado antes/depois, autor, justificativa, momento e contagens de filhos cancelados no evento de auditoria. A regra de ação e a atualização persistem sob o mesmo bloqueio de processo e a mesma transação.

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

`DELETE_DRAFT` remove o agregado inteiro: `ProcessInstance`, fases, atividades, execuções, tarefas, formulários, valores, atribuições, decisões, execuções de avaliação, artefatos e eventos vinculados. Os binários em `ATTACHMENTS_DIR/{process_id}/` também são removidos. A implementação deve eliminar referências de valores para artefatos antes do artefato e respeitar a ordem das chaves estrangeiras.

## AuditEvent

Eventos novos, imutáveis e com `context_data` estruturado:

| `event_type` | Campos mínimos em `context_data` |
|---|---|
| `PROCESS_CANCELLED` | campos acima e `cancelled_counts` por tipo de filho |
| `PROCESS_ARCHIVED` | `action`, `previous_status`, `result_status`, `justification` |

`user_id` e `occurred_at` são persistidos pelo próprio `AuditEvent`. O status terminal anterior do arquivamento é obtido deste evento na linha do tempo histórica. A exclusão física não cria evento: ela remove os eventos do agregado.

## Projeção para a interface

`ProcessInstanceDetail` passa a expor `available_actions`, lista de códigos de `DELETE_DRAFT`, `CANCEL` e `ARCHIVE` calculada para o usuário autenticado. A lista é vazia para recurso terminal sem ação permitida e nunca substitui a revalidação do comando.
