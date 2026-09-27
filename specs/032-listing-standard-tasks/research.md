# Research: Padrão de listagens e lista de tarefas

**Feature**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Não havia `NEEDS CLARIFICATION` no contexto técnico. As decisões abaixo resolvem como implementar cada requisito sobre o código atual.

## R1. "Pode agir" como expressão SQL, igual para filtro e item

**Decision**: Uma expressão booleana SQL, montada uma vez por pedido, alimenta o campo `can_act` de cada item e o filtro `actionable=true`. A expressão é verdadeira quando:

1. `ActivityInstance.edit_roles` intersecta os cargos globais do usuário (`global_cargos`, calculados em Python e passados como array), **ou** existe atribuição ativa do usuário no processo da atividade com `role_key = any(edit_roles)` (`process_cargos_scope`, correlacionada); **e**
2. não existe conflito de interesse vigente do usuário no processo (R2).

**Rationale**: `require_activity_access(..., 'edit')` já decide com esses dois critérios. Reproduzir a mesma regra em SQL mantém a consistência entre o que a lista promete e o que a ação aceita (SC-002). Uma só expressão evita divergência entre filtro e campo, e permite paginar e contar no banco.

**Alternatives considered**:
- Calcular `can_act` em Python chamando `require_activity_access` por item: N+1 consultas, e o filtro não poderia paginar no banco.
- Considerar também as permissões RBAC específicas (ex.: `triage.review`) e o estado da atividade: fora do escopo. A regra de acesso por atividade da Spec 030 é o critério de "pode agir". A tarefa só existe enquanto a execução está aberta, então o estado já vem implícito.

**Nota**: o conflito de interesse está ligado a uma atribuição no processo. Admin e BraCVAM sem atribuição no processo nunca têm conflito ali. O cenário "BraCVAM com conflito" exige que o usuário também tenha uma atribuição no processo com declaração de conflito, o mesmo caso que `require_activity_access` já trata.

## R2. Conflito de interesse vigente em SQL correlacionado

**Decision**: Nova função `current_conflict_clause(user_id)` em `authorization.py`. Ela devolve um `EXISTS` correlacionado por `ActivityInstance.process_instance_id`: existe declaração com `has_conflict = true` numa atribuição ativa do usuário no processo, e não existe declaração mais recente para a mesma atribuição (ordem `declared_at`, `id`).

**Rationale**: `has_current_conflict` resolve por processo com `DISTINCT ON` e é assíncrona. Para a lista, a regra precisa ser uma subconsulta correlacionada. O `NOT EXISTS` da declaração mais nova expressa "a última declaração" sem `DISTINCT ON` dentro da correlação.

**Alternatives considered**: carregar em Python os processos com conflito do usuário e passar como lista. Funciona, mas separa a regra em dois lugares e cresce com o número de processos.

## R3. Rodada vigente

**Decision**: `current_run=true` (padrão) filtra `ActivityRun.run_number` igual ao maior `run_number` não excluído da mesma `activity_instance_id`, por subconsulta correlacionada. O índice único `uq_activity_runs_number_active (activity_instance_id, run_number)` atende a busca.

**Rationale**: é a regra que o README já dá ao frontend ("a vigente é a de maior `activity_run_number`"), agora aplicada no servidor.

**Alternatives considered**: janela `row_number()` sobre as tarefas. Mais custosa e confusa quando a execução tem mais de uma tarefa.

## R4. Envelope genérico e blocos opcionais

**Decision**: Modelos Pydantic em `schemas.py`:

- `Pagination` (`page`, `per_page`, `total_items`, `total_pages`, `has_next`, `has_prev`);
- `SortApplied` (`by`, `order`);
- `ListEnvelope[ItemT, FiltersT, FacetsT, SummaryT]` genérico, com `data`, `pagination`, `filters_applied`, `sort`, `facets | None` e `summary | None`.

Um `model_serializer(mode='wrap')` no envelope remove `facets` e `summary` quando forem `None`. Um helper em `core/listing.py` calcula `Pagination` a partir de `page`, `per_page` e `total`.

**Rationale**: o genérico dá à Spec 033 o mesmo envelope, e cada listagem continua tipando seus filtros e contagens para a documentação. O serializer atua só no nível do envelope. `response_model_exclude_none` também apagaria `due_date: null` dentro dos itens.

**Alternatives considered**:
- Sempre enviar `facets: null`: contraria a US2, cenário 4.
- `fastapi-pagination`: dependência nova para um cálculo de poucas linhas, com um envelope que não é o escolhido.

## R5. Contagem, página e contagens por valor

**Decision**: A consulta filtrada (sem ordem e sem paginação) é montada uma vez. Dela saem:

- `total_items`: `count(*)` sobre a subconsulta;
- a página: com ordem, `offset((page-1)*per_page)` e `limit(per_page)`;
- as contagens, só com `include=facets`: um `GROUP BY` por dimensão (`activity_key`, `status`).

**Rationale**: todas as contagens vêm do mesmo conjunto filtrado, o que garante a SC-005. São no máximo 4 consultas além do resumo, independentemente do número de tarefas.

## R6. Resumo de pré-avaliação por IA

**Decision**: Com `include=summary`, `ai_pre_evaluation_in_progress` conta os `EvaluationRun.process_instance_id` distintos com `status = 'in_progress'` e `deleted_at` nulo. A consulta passa pela atividade da execução (`EvaluationRun.activity_run_id` → `ActivityRun` → `ActivityInstance`) e aplica `process_visibility_clause`, `activity_view_clause` e o filtro `process_id`, quando houver. Os demais filtros de tarefa não se aplicam, porque a pré-avaliação não é tarefa.

**Rationale**: a pré-avaliação pertence à execução da submissão, e o conteúdo dela segue a concessão de ver dessa atividade (Spec 030). O reprocessamento administrativo cria uma execução nova e deixa a anterior como `failed`. Contar processos distintos em andamento conta cada processo uma vez.

**Alternatives considered**: transformar a pré-avaliação em atividade. Rejeitada na spec (Assumptions).

## R7. Ordenação estável

**Decision**: `sort_by` ∈ {`due_date`, `created_at`} (padrão `due_date`) e `sort_order` ∈ {`asc`, `desc`} (padrão `asc`). As tarefas sem prazo ficam sempre por último (`NULLS LAST`), nas duas direções. Os desempates são `Task.created_at` e depois `Task.id`, sempre crescentes.

**Rationale**: `Task.id` é único, então a ordem é total e a paginação é estável (SC-004). Deixar os nulos sempre por último atende "sem prazo por último" sem inverter o significado na ordem decrescente.

## R8. Atrasadas

**Decision**: `overdue=true` filtra `Task.status = 'READY'` e `Task.due_date < agora`, com "agora" como `datetime` naive em UTC, calculado no servidor da aplicação.

**Rationale**: `Task.due_date` é uma coluna naive em UTC (Spec 024). Comparar com `func.now()` do banco misturaria valores com e sem fuso.

## R9. Validação dos parâmetros

**Decision**: `status`, `sort_by`, `sort_order` e `include` usam `Literal`. `status`, `activity_key` e `include` são listas (`Query`, parâmetro repetido). `page >= 1`, `1 <= per_page <= 100`. Valor inválido responde `422` no formato de validação atual.

**Rationale**: FR-003 e FR-019 pedem recusa, não lista vazia. O formato do erro muda só na Spec 034.

## R10. Referências resumidas

**Decision**: `ProcessRef` (`id`, `code`, `title`) e `PhaseRef` (`key`, `order`) em `schemas.py`, numa seção "Referências", com `Field(description=...)` em todos os campos. `TaskSummary` troca `process_id`, `process_code`, `process_title`, `phase_key` e `phase_order` por `process` e `phase`, e ganha `can_act`. `TaskDetail` não muda (FR-026).

**Rationale**: é a convenção da spec (FR-009 a FR-012), aplicada só onde esta spec mexe. A Spec 033 cria as demais referências.

## R11. Testes existentes afetados

**Decision**: Os 14 arquivos de teste que leem `GET /tasks` passam a ler `response.json()['data']` e os campos `process`/`phase`. O helper `process_tasks` das jornadas também muda. Testes que dependem de rodadas anteriores passam `current_run=false`.

**Rationale**: a mudança quebra o contrato de propósito. Ajustar os testes antigos mostra que o comportamento deles continua o mesmo com o formato novo.
