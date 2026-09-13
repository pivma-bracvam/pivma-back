# Modelo de Dados: Exclusão (Soft-Delete) e Arquivamento de Processos

## ProcessInstance

Entidade persistida em `process_instances`; não requer coluna nova (`deleted_at`/`deleted_by` já existem via `AuditMixin`).

| Campo | Uso nesta feature |
|---|---|
| `status` | Recebe `CANCELLED` na exclusão e `ARCHIVED` no arquivamento. Estados existentes continuam inalterados. |
| `closed_at` | Preenchido na exclusão; preservado no arquivamento. |
| `deleted_at` / `deleted_by` | Preenchidos pela exclusão via `AuditMixin.set_deletion_audit`; nunca preenchidos pelo arquivamento (arquivar não é excluir). |
| `closure_reason` | Mantém razões de fechamento técnico já existentes; não recebe exclusão nem arquivamento. |
| `created_by` | Apoia a rastreabilidade; a autorização local efetiva usa a atribuição ativa de proponente. |

### Derivação de ciclo de vida

- `operational`: processo existente, com status diferente de `CLOSED`, `CANCELLED` e `ARCHIVED`, e `deleted_at IS NULL`.
- `archivable`: processo existente e com status `CLOSED` ou `CANCELLED` (independentemente de `CANCELLED` ter sido produzido por exclusão ou por um cancelamento histórico anterior).
- `immutable`: processo com status `CLOSED`, `CANCELLED` ou `ARCHIVED`; nenhuma mutação operacional é aceita.

Não existe mais a derivação `never_submitted`: o histórico de submissão formal deixou de determinar a autorização ou o resultado da exclusão.

### Transições

| Ação | Pré-condição | Resultado |
|---|---|---|
| `DELETE` | Processo não-terminal (`status` fora de `{CLOSED, CANCELLED, ARCHIVED}`); proponente efetivo OU perfil global Admin/BraCVAM | `status=CANCELLED`, `closed_at=agora`, `deleted_at=agora`, `deleted_by=ator`; agregado, registros vinculados e documentos permanecem intactos. |
| `ARCHIVE` | `status=CLOSED` ou `CANCELLED`; `triage.review`, sem conflito | `status=ARCHIVED`; o evento retém o status anterior. |

Nenhuma operação de ciclo de vida exige justificativa. A exclusão registra ação, estado antes/depois, autor, momento e contagens de filhos cancelados; o arquivamento registra ação, estado antes/depois, autor e momento. A regra de ação e a atualização persistem sob o mesmo bloqueio de processo e a mesma transação.

## Trabalho subordinado

| Entidade | Relação | Tratamento na exclusão |
|---|---|---|
| `Phase` | Pertence ao processo | Estado não terminal passa a `CANCELLED`; `COMPLETED` é preservado. |
| `ActivityInstance` | Pertence ao processo/fase | Estado não terminal passa a `CANCELLED`; não é desbloqueada depois. |
| `ActivityRun` | Pertence à atividade | Estado não terminal passa a `CANCELLED`, com encerramento quando o modelo já o suporta. |
| `Task` | Pertence a uma execução | Estado não terminal passa a `CANCELLED`; itens concluídos não mudam. |
| `EvaluationRun` | Vinculada ao processo/executa pré-avaliação | Execução `in_progress` passa a `CANCELLED`; o worker não roteia resultado tardio. |
| `FormInstance` | Vinculada à execução | Não ganha estado novo, não é submetida artificialmente e permanece somente leitura por causa da guarda do processo/run. |
| `Artifact`, `Decision`, `FormValue`, `AuditEvent` | Histórico vinculado | Não são removidos nem reescritos. |

## Preservação de documentos

A exclusão **nunca** remove arquivos de `ATTACHMENTS_DIR/{process_id}/`, independentemente de o processo já ter sido formalmente submetido ou não. A remoção física do agregado e dos anexos, existente na versão anterior desta feature, deixa de existir como comportamento do sistema.

## AuditEvent

Eventos novos, imutáveis e com `context_data` estruturado:

| `event_type` | Campos mínimos em `context_data` |
|---|---|
| `PROCESS_DELETED` | `previous_status`, `result_status` (`CANCELLED`) e `cancelled_counts` por tipo de filho. Único tipo para toda exclusão, independentemente de o ator ser o proponente efetivo ou um Admin/BraCVAM. |
| `PROCESS_ARCHIVED` | `previous_status`, `result_status` (`ARCHIVED`) |

`user_id` e `occurred_at` são persistidos pelo próprio `AuditEvent`. O status terminal anterior do arquivamento é obtido deste evento na linha do tempo histórica. Uma pessoa auditando distingue "o proponente se excluiu" de "um administrador excluiu de terceiro" comparando `AuditEvent.user_id` com o proponente efetivo do processo — não pelo `event_type`. Os eventos `PROCESS_CANCELLED` e `PROCESS_WITHDRAWN_BY_PROPONENT` deixam de ser produzidos por esta feature (permanecem no histórico de processos já excluídos/arquivados antes desta revisão).

## Filtro de soft-delete (infraestrutura global)

Um listener `do_orm_execute`, registrado em `core/database/__init__.py` sobre a `Session` síncrona subjacente, aplica `with_loader_criteria(AuditMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)` a toda consulta `SELECT` via ORM sobre qualquer classe mapeada que herde `AuditMixin` — não apenas `ProcessInstance`. Uma consulta que precise enxergar registros soft-deletados passa `execution_options(skip_soft_delete_filter=True)` explicitamente. Esse filtro:

- não substitui os filtros manuais `deleted_at.is_(None)` já existentes em `authorization.py` e outros módulos — funciona como camada adicional (rede de segurança), não como refatoração deles;
- não cobre `UPDATE`/`DELETE` em massa (bulk, via `update(Model)...`/`delete(Model)...` sem carregar instâncias) nem SQL fora do ORM;
- é a decisão explícita do usuário (Clarification 2026-09-13, Q5) de aplicar o filtro a todo o sistema, e não apenas a processos, apesar do raio de impacto maior — ver `plan.md` (Complexity Tracking).

## Projeção para a interface

`ProcessInstanceDetail` expõe `available_actions`, lista de códigos restrita a `DELETE` e `ARCHIVE`, calculada para o usuário autenticado. A lista é vazia para recurso terminal sem ação permitida e nunca substitui a revalidação do comando.
