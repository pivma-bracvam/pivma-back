# Research: Execução de atividades por laboratório participante

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Cada decisão cita os requisitos da spec que atende. Os caminhos de código
referem-se à `develop` em 2026-10-02.

## R1 — Declaração no template e cópia para a instância

- **Decision**: duas chaves novas por atividade no YAML: `execution_scope`
  (`"process"` por padrão, ou `"per_laboratory"`) e `custody` (booleano,
  padrão `false`). Na instanciação, `_create_phases_and_activities` copia as
  duas para colunas novas de `activity_instances` (`execution_scope`,
  `is_custody`), como já faz com `view_roles`/`edit_roles` (Spec 030).
- **Rationale**: o motor e `GET /tasks` precisam desses valores em consulta
  SQL e em cada conclusão. A cópia segue o precedente das concessões e
  preserva a imutabilidade de versão (o processo lê a versão gravada).
- **Alternatives considered**: ler do `definition_payload` a cada uso, como
  `_advance_dependent_activities` faz para `a_data`. Rejeitada: obriga
  carregar e percorrer o payload em `/tasks` e em cada transição.

## R2 — Validação do template na carga

- **Decision**: uma função pura `validate_execution_scopes(data)` em
  `process_engine.py`, chamada por `sync_template_from_dict` logo depois de
  `_validate_activity_access`. Recusa com `ValidationError` que cita template
  e atividade (FR-003):
  1. `execution_scope` fora de `{"process", "per_laboratory"}`;
  2. atividade `per_laboratory` sem caminho de dependências, direto ou
     transitivo, até uma atividade com `activity_type: "sample_definition"`;
  3. atividade `per_laboratory` sem `participating_laboratory` no conjunto de
     edição devolvido por `resolve_activity_access`;
  4. `custody: true` em atividade que não é `per_laboratory`.
- **Rationale**: o grafo de dependências só existe no template inteiro, por
  isso a regra 2 não cabe em `resolve_activity_access`, que vê uma atividade
  por vez. Falhar na carga segue a Spec 030 (FR-013).
- **Alternatives considered**: validar com Pydantic. Rejeitada: o payload é
  um dicionário livre hoje e trocar isso está fora do escopo.

## R3 — Conjunto congelado de laboratórios

- **Decision**: o conjunto é o `laboratory_id` distinto dos `BlindSampleCode`
  ativos do processo, ordenado pelo nome do laboratório e pelo id. A consulta
  fica em `process_engine.py` (`_frozen_laboratory_ids`), que importa só os
  modelos.
- **Rationale**: os códigos cegos já são o retrato congelado (Spec 031,
  FR-013 e R10). `sample_service` importa o motor, então o motor não pode
  importar `sample_service` sem ciclo.
- **Alternatives considered**: designações ativas (rejeitada pelo usuário na
  Clarification 1); tabela própria de retrato (rejeitada: duplica os códigos).

## R4 — Execução ligada ao laboratório e numeração

- **Decision**: `activity_runs.laboratory_id` (FK opcional para
  `laboratories`). O índice único parcial `uq_activity_runs_number_active`
  passa a `(activity_instance_id, laboratory_id, run_number)` com
  `NULLS NOT DISTINCT`, filtrado por `deleted_at IS NULL`. A "execução
  vigente" de um laboratório é a de maior `run_number` para o par atividade e
  laboratório. A `Task` não ganha coluna: o laboratório vem da execução.
- **Rationale**: `NULLS NOT DISTINCT` (PostgreSQL 15+, o projeto usa 17)
  mantém a unicidade atual das execuções únicas, que têm `laboratory_id`
  nulo. A chave é a mesma da Spec 031, como pede o 1º comentário da issue.
- **Alternatives considered**: `laboratory_id` também em `tasks` (rejeitada:
  redundante); `run_number` global da atividade (rejeitada: a issue pede
  `prev_run_number + 1` por laboratório).

## R5 — Estados

- **Decision**:
  - Execução: os estados atuais `IN_PROGRESS`, `COMPLETED` e `CANCELLED`,
    mais `BLOCKED` (laboratório com dependência por laboratório pendente,
    sem tarefa), `WAIVED` (dispensada) e `SUPERSEDED` (substituída).
  - Terminais: `COMPLETED`, `CANCELLED`, `WAIVED`, `SUPERSEDED`
    (`IMMUTABLE_RUN_STATUSES`, R14). Abertos: `IN_PROGRESS`, `BLOCKED`.
  - Tarefa: sem estado novo. Execução `BLOCKED` não tem tarefa. Execução
    `WAIVED` sempre tem tarefa `CANCELLED` (criada se não havia). Tarefa de
    execução substituída ou cancelada fica como estava ou `CANCELLED`.
  - Atividade por laboratório: `BLOCKED` antes da ativação. Depois,
    `COMPLETED` se e somente se **para todo laboratório do conjunto
    congelado** a execução vigente está `COMPLETED` ou `WAIVED`; senão
    `IN_PROGRESS`. Como a ativação cria uma execução para cada laboratório
    (R6) e toda execução encerrada por cascata é substituída por uma nova
    (R10), todo laboratório congelado tem sempre uma execução vigente depois
    da ativação; a regra confere contra a lista congelada mesmo assim.
- **Rationale**: o estado da tarefa já é contrato público (`TaskStatus`). O
  status da execução, exposto em `/tasks` (R11), distingue os casos (FR-028).
  A execução `BLOCKED` concilia "uma execução por laboratório desde a
  ativação" (FR-004) com a cadeia por laboratório (FR-011).
- **Alternatives considered**: estados novos em `Task` (rejeitada: muda um
  `Literal` público); criar a execução só quando o laboratório fica pronto
  (rejeitada pelo usuário na análise: a conclusão deve conferir contra a
  lista congelada com execução para todos desde a ativação).

## R6 — Ativação e dependências por laboratório

- **Decision**:
  - **Ativação** (`_activate_laboratory_activity`): uma atividade por
    laboratório é ativada quando todas as dependências de atividade única
    estão satisfeitas e todas as dependências por laboratório já estão
    ativadas (FR-004a). Na mesma operação, cria uma execução para cada
    laboratório do conjunto congelado, nesta ordem de decisão:
    1. laboratório dispensado na fase e atividade sem `is_custody` →
       `WAIVED`, com `Task` `CANCELLED` (FR-007);
    2. dependências resolvidas para o laboratório → `IN_PROGRESS`, com `Task`
       `READY` e `FormInstance` nova se houver `form_template_key`;
    3. caso contrário → `BLOCKED`, sem tarefa nem formulário.

    Levanta `ConflictError` com conjunto congelado vazio (FR-006). Depois de
    ativar, ativa em cascata os dependentes por laboratório que ficaram
    ativáveis e recalcula o status (R5).
  - **Dependência resolvida para o Lab X**: de atividade única, quando ela
    está no `required_status` (`_dependency_satisfied`); de atividade por
    laboratório, quando a execução vigente do Lab X nela está `COMPLETED` ou
    `WAIVED` (FR-011).
  - **Desbloqueio por laboratório** (`_unblock_laboratory`): quando a
    execução do Lab X numa atividade fica `COMPLETED` ou `WAIVED`, cada
    dependente por laboratório em que a execução vigente do Lab X está
    `BLOCKED` e cujas dependências ficaram resolvidas para o Lab X passa a
    `IN_PROGRESS` com tarefa e formulário, ou a `WAIVED` com tarefa
    `CANCELLED` se o Lab X está dispensado na fase e a atividade não é de
    custódia. A propagação continua para os dependentes deles enquanto
    houver mudança.
  - **Desbloqueio ao passar a `IN_PROGRESS`**: `started_at` da execução passa
    a ser o momento do desbloqueio, e o prazo da tarefa é calculado a partir
    dele (Spec 024), não da criação da execução `BLOCKED` (FR-011).
  - **Pontos de chamada**: `_advance_dependent_activities` (dependente
    `per_laboratory` ainda `BLOCKED` → ativação; dependente `per_laboratory`
    já ativado → desbloqueio para cada laboratório congelado, porque uma
    dependência de atividade única pode ter voltado a ser satisfeita depois
    de uma reabertura; a condição atual "só se `BLOCKED`" continua valendo
    para atividade única), conclusão (R7) e dispensa (R9).
  - **Evento**: a ativação de atividade por laboratório grava um
    `ACTIVITY_UNBLOCKED` sem `activity_run_id` (ligado ao processo, com
    `activity_key` no contexto), visível a quem vê a atividade; nenhum
    laboratório fica de fora por o evento apontar para a execução de outro.
  - Ao chegar a `COMPLETED`, a atividade chama
    `_advance_dependent_activities` para os dependentes de atividade única.
- **Rationale**: a ativação em cadeia cria todas as execuções de uma vez,
  como pede a conclusão contra a lista congelada, e a execução `BLOCKED`
  mantém a cadeia por laboratório da Clarification 5. A ordem de decisão
  resolve a custódia do laboratório dispensado sem passo extra: quando a
  devolução é ativada, as execuções dele a montante já estão `WAIVED`.
- **Alternatives considered**: espera por todos em toda dependência (texto
  original da issue), rejeitada pelo usuário na Clarification 5.

## R7 — Conclusão da execução de um laboratório

- **Decision**: `complete_laboratory_run(session, process_id, activity_key,
  laboratory_id, user_id) -> ActivityRun` no motor. Ela:
  1. verifica que o processo é mutável e trava o processo (R12);
  2. aplica a autorização por laboratório (R8);
  3. exige execução vigente `IN_PROGRESS` (não `BLOCKED`), senão
     `ConflictError`;
  4. conclui a execução e as tarefas;
  5. registra `LABORATORY_RUN_COMPLETED` (com `activity_run_id` e
     `laboratory_id`);
  6. desbloqueia a cadeia do laboratório nos dependentes por laboratório
     (`_unblock_laboratory`, R6);
  7. recalcula a atividade.

  A função **não** faz commit e não tem rota HTTP nesta feature. As issues
  #28 a #31 chamam a função dentro das próprias rotas, depois de gravar os
  próprios dados.
- **Rationale**: cada atividade da Etapa 3 tem dados próprios (recebimento,
  resultados, devolução). Uma rota genérica de "concluir" agora seria
  abstração preventiva e permitiria concluir sem os dados da atividade.
- **Alternatives considered**: tornar as rotas de formulário
  (`/activities/{key}/form`) cientes do laboratório. Adiada para a issue
  consumidora que usar formulário, porque exige decidir como a rota descobre
  o laboratório de quem chama.
- **Consequência**: `get_current_form_instance` e `get_current_activity_run`
  escolhem "a execução de maior número", o que numa atividade por laboratório
  seria uma execução de um laboratório qualquer. As duas passam a recusar
  atividade `per_laboratory` com `ConflictError` (409 `invalid_transition`
  nas rotas), até a issue consumidora as estender.

## R8 — Autorização por laboratório

- **Decision**:
  - Uma função `require_laboratory_run_access(session, user_id, act, run)` no
    motor. Ela aplica `require_activity_access(..., 'edit')` e, se a execução
    tem `laboratory_id`, exige cargo global (`admin` ou `bracvam`) em
    `edit_roles` **ou** uma designação efetiva de `participating_laboratory`
    pelo mesmo laboratório. Para isso usa `process_cargos_scope`, filtrado por
    `Assignment.laboratory_id` (FR-008).
  - Em `GET /tasks`, `_can_act_clause` ganha o mesmo ramo: quando
    `ActivityRun.laboratory_id` não é nulo, a concessão por designação exige
    `role_key = participating_laboratory` e `Assignment.laboratory_id =
    ActivityRun.laboratory_id` (FR-009).
- **Rationale**: reaproveita a regra de efetividade da Spec 035 sem duplicar.
  Um `group_manager` em `edit_roles` não age na execução de um laboratório
  (FR-008); ele dispensa e reabre.
- **Alternatives considered**: tratar na #59. Rejeitada: a #59 cuida de
  **visão**. Sem esta regra, a #58 permitiria escrita cruzada.

## R9 — Dispensa

- **Decision**:
  - **Tabela** `laboratory_waivers`: `process_instance_id`, `phase_id`,
    `laboratory_id`, `reason`, mais auditoria. Índice único parcial
    `(phase_id, laboratory_id)` onde `deleted_at IS NULL`. Sem rota de
    reversão (FR-020a).
  - **Rota** `POST /processes/{id}/phases/{phase_key}/laboratory-waivers`.
    - Autorização: gestor do processo (R13); demais com visão do processo
      recebem 403, sem visão 404.
    - Validações, nesta ordem:
      - processo mutável (409 `invalid_transition`);
      - fase existe no processo (404);
      - a atividade do tipo `sample_definition` do processo está `COMPLETED`
        (409 `sample_definition_not_frozen`, FR-017a);
      - laboratório no conjunto congelado (422 `laboratory_not_frozen`);
      - motivo não vazio (422);
      - dispensa duplicada (409 `already_waived`, pelo índice).
  - **Efeito**:
    - Nas atividades `per_laboratory` sem `is_custody` da fase, a execução
      vigente `IN_PROGRESS` ou `BLOCKED` do laboratório vira `WAIVED`; tarefas
      abertas viram `CANCELLED` e a execução sem tarefa ganha uma `CANCELLED`
      (FR-018). As `COMPLETED` não mudam.
    - Em seguida roda `_unblock_laboratory` (R6) e recalcula cada atividade
      afetada.
    - Grava um `LABORATORY_WAIVED` por execução marcada, com
      `activity_run_id`; sem execução marcada, um só, sem `activity_run_id`.
      `context_data`: `phase_key`, `activity_key` (quando há execução),
      `laboratory_id`, `reason` (FR-021).
    - A resposta traz `waived_activity_keys`: as chaves das atividades cujas
      execuções foram marcadas.
- **Rationale**: a dispensa precisa persistir para as atividades da fase que
  ainda vão ser ativadas (FR-007). Exigir o congelamento evita dispensar um
  laboratório que a conclusão de `sample_definition` ainda pode descartar, e
  tira a disputa entre as duas rotinas: a dispensa lê um estado já imutável.
  O código de erro segue a convenção minúscula da Spec 034.
- **Alternatives considered**: dispensa por atividade (rejeitada pelo usuário
  na Clarification 4).

## R10 — Reabertura

- **Decision**:
  - **Motor**: `reopen_laboratory_run(session, process_id, activity_key,
    laboratory_id, reason, user_id) -> ActivityRun`, sem autorização própria
    (quem chama verifica) e sem commit.
  - **Recusas** (409): atividade não `per_laboratory` (`invalid_transition`);
    laboratório sem execução vigente `COMPLETED` (`invalid_transition`);
    laboratório dispensado na fase em atividade sem `is_custody`
    (`laboratory_waived`) (FR-026).
  - **Efeito**:
    1. A execução vigente vira `SUPERSEDED`. Valores, anexos e decisões dela
       não mudam (FR-024).
    2. Abre uma execução nova `n + 1` `IN_PROGRESS`, com `Task` `READY` e
       `FormInstance` nova e vazia (o 2º comentário da issue pede um conjunto
       novo de valores).
    3. A atividade volta a `IN_PROGRESS`.
    4. Roda `_reblock_dependents(act, laboratory_id)` em cadeia (FR-025):
       - Dependente por laboratório: a execução vigente do laboratório
         `IN_PROGRESS` vira `CANCELLED` (tarefas `CANCELLED`); `COMPLETED`
         vira `SUPERSEDED`; nos dois casos cria a execução `n + 1` `BLOCKED`
         do laboratório. `BLOCKED` e `WAIVED` ficam como estão. A cadeia segue
         nos dependentes dele para o mesmo laboratório.
       - Dependente único em `IN_PROGRESS` ou `COMPLETED`: volta a `BLOCKED`
         com `blocked_reason`. A execução aberta dele vira `CANCELLED`; a
         concluída fica como está. A cadeia segue nos dependentes dele para
         todos os laboratórios.
       - Ao final, o status de cada atividade por laboratório tocada é
         recalculado (R5). Uma atividade por laboratório reabloqueada continua
         ativada; quando a atividade única de que depende conclui de novo,
         `_advance_dependent_activities` roda o desbloqueio dela (R6).
    5. Grava `LABORATORY_RUN_REOPENED`, com `activity_run_id` da execução
       nova, `laboratory_id`, os números anterior e novo, `reason` e as chaves
       reabloqueadas.
  - **Rota**: `POST /processes/{id}/activities/{activity_key}/laboratories/
    {laboratory_id}/reopen`, com a mesma autorização da dispensa (FR-022).
- **Rationale**: a nova execução `BLOCKED` mantém o invariante de R5 (todo
  laboratório congelado tem execução vigente) e é desbloqueada por
  `_unblock_laboratory` quando a cadeia do laboratório se resolver de novo.
  `_activate_activity` já numera `max + 1` para as atividades únicas (Issue
  #22).
- **Alternatives considered**: copiar os valores da execução anterior, como
  `_open_new_submission_run`. Rejeitada para dados experimentais (BPL).

## R11 — Exposição em `/tasks` e na linha do tempo

- **Decision**:
  - **Campos novos**: `TaskSummary` e `TaskDetail` ganham `laboratory:
    LaboratoryRef | None`, montado em lote por `references.laboratory_refs`
    (Spec 033), e `activity_run_status: Literal['IN_PROGRESS', 'COMPLETED',
    'CANCELLED', 'WAIVED', 'SUPERSEDED']` (FR-028). `BLOCKED` não aparece
    porque execução bloqueada não tem tarefa.
  - **Rodada vigente**: `_current_run_clause` passa a comparar com o máximo
    por `(activity_instance_id, laboratory_id)`, usando
    `is_not_distinct_from` (FR-029). Enquanto a execução vigente do
    laboratório está `BLOCKED`, ele não tem tarefa vigente naquela
    atividade.
  - **Linha do tempo**: os eventos novos levam `laboratory_id` em
    `context_data` e, salvo o caso do FR-021, `activity_run_id` (FR-030). A
    visibilidade segue R13.
- **Rationale**: campos aditivos não quebram clientes. O lote evita N+1.
- **Alternatives considered**: filtro `laboratory_id` em `/tasks`. Fica de
  fora porque a spec não pede (karpathy: nada especulativo).

## R12 — Concorrência

- **Decision**: conclusão, dispensa e reabertura começam travando a linha do
  processo (`SELECT ... FOR UPDATE` em `process_instances`). O padrão é o de
  `_locked_lifecycle_process`, mas sem o filtro de visibilidade, porque a
  autorização vem antes.
- **Rationale**: as cascatas tocam várias atividades. Uma trava por processo
  serializa as transições do mesmo processo e garante FR-015 (a atividade
  conclui uma vez) sem ordenar travas por atividade. A contenção é baixa:
  dezenas de laboratórios por processo, ações humanas.
  A dispensa exige `sample_definition` concluída (R9), então não disputa com
  `complete_sample_definition`, que trava só a própria atividade.
- **Alternatives considered**: travar só a `ActivityInstance` (como a Spec
  031). Rejeitada: não cobre cascatas entre atividades diferentes.

## R13 — Isolamento entre laboratórios em `/tasks` e na trilha

- **Decision**:
  - **Gestor do processo** (FR-035): `is_effective_group_manager` ou
    `has_platform_wide_access`. Um predicado SQL
    `laboratory_run_visibility_clause(session, user_id)` em
    `src/pivma/core/authorization.py` devolve `None` para Admin/BraCVAM e,
    para os demais, a condição:
    `ActivityRun.laboratory_id IS NULL` **ou** existe `group_manager`
    efetivo do usuário no processo da atividade **ou** existe designação
    efetiva `participating_laboratory` do usuário com
    `Assignment.laboratory_id = ActivityRun.laboratory_id`. Usa
    `process_cargos_scope`, que já aplica a Spec 035.
  - **`GET /tasks`**: o predicado entra no conjunto filtrado, antes da
    paginação, das facetas e do `summary`, somado à visão da atividade
    (Spec 030) (FR-036).
  - **`GET /tasks/{id}`**: o mesmo predicado; quem não passa recebe 404
    "Tarefa não encontrada.", igual a quem não vê a atividade.
  - **Trilha** (`_visible_events` em `src/pivma/routers/processes.py`), depois
    do filtro atual de visão da atividade:
    - `LABORATORY_WAIVED`: só gestor do processo (FR-038);
    - evento cuja `activity_run_id` é de execução com laboratório, e
      `LABORATORY_RUN_COMPLETED`/`LABORATORY_RUN_REOPENED`: gestor do
      processo ou pessoa com `participating_laboratory` efetivo pelo
      `laboratory_id` do evento (FR-037);
    - os demais eventos, inclusive os de designação com `laboratory_id` no
      contexto, seguem a regra atual (Specs 006 e 035).
- **Rationale**: o filtro fica nos dois pontos que esta spec passa a
  alimentar com dados de laboratório. A regra é a mesma nos dois, com um
  predicado só, como a Spec 035 fez com a efetividade.
- **Alternatives considered**: esconder só o nome do laboratório (rejeitada:
  ainda mostra quantos laboratórios participam e o andamento de cada um);
  entregar a #59 junto (rejeitada pelo usuário: escopo maior).

## R14 — Estados terminais e cancelamento do processo

- **Decision**: `IMMUTABLE_RUN_STATUSES = frozenset({'COMPLETED',
  'CANCELLED', 'WAIVED', 'SUPERSEDED'})` em `process_engine.py`.
  `_cancel_pending_children` passa a cancelar só execuções fora desse
  conjunto (hoje `IN_PROGRESS` e `BLOCKED`) (FR-039). Tarefas e atividades
  seguem a regra atual.
- **Rationale**: a regra atual (`not in {'COMPLETED', 'CANCELLED'}`)
  transformaria `WAIVED` e `SUPERSEDED` em `CANCELLED` ao cancelar ou excluir
  o processo, apagando a rastreabilidade (BPL).
- **Alternatives considered**: listar só os estados abertos
  (`in {'IN_PROGRESS', 'BLOCKED'}`). Equivalente hoje; a lista de terminais
  é a que o usuário pediu e falha de forma segura se surgir estado novo
  aberto (ele seria cancelado).
