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
    mais `WAIVED` (dispensada) e `SUPERSEDED` (substituída na reabertura).
  - Tarefa: sem estado novo. A tarefa de execução dispensada ou substituída
    fica `CANCELLED`; a de execução concluída fica `COMPLETED`.
  - Atividade por laboratório: status derivado das execuções vigentes do
    conjunto congelado. `BLOCKED` sem nenhuma execução viva; `COMPLETED`
    quando todos os laboratórios têm execução vigente `COMPLETED` ou
    `WAIVED`; `IN_PROGRESS` nos demais casos.
- **Rationale**: o estado da tarefa já é contrato público (`TaskStatus`). O
  status da execução, exposto em `/tasks` (R11), distingue os casos (FR-028).
  A issue cita `DISQUALIFIED` ou `WAIVED` e `REJECTED` ou `SUPERSEDED`; um
  estado de cada basta, porque o motivo vai no evento.
- **Alternatives considered**: estados novos em `Task` (rejeitada: muda um
  `Literal` público sem necessidade).

## R6 — Abertura e dependências por laboratório

- **Decision**: uma função idempotente `_open_ready_laboratory_runs(session,
  process, act, a_data, user_id, reason)`. Para cada laboratório do conjunto
  congelado sem execução vigente viva (nenhuma, `CANCELLED` ou `SUPERSEDED`)
  cujas dependências estão resolvidas para ele, abre a execução:
  - Dependência de atividade única: resolvida quando a atividade está no
    `required_status`, como hoje (`_dependency_satisfied`).
  - Dependência de atividade por laboratório: resolvida quando a execução
    vigente do laboratório nela está `COMPLETED` ou `WAIVED` (FR-011).
  - Laboratório dispensado na fase e atividade sem `is_custody`: a execução
    nasce `WAIVED`, com a tarefa já `CANCELLED` (FR-007).
  - Nos demais casos: execução `IN_PROGRESS`, `Task` `READY` e, se houver
    `form_template_key`, uma `FormInstance` nova.

  Depois recalcula o status da atividade (R5). Se ela chegou a `COMPLETED`,
  chama `_advance_dependent_activities`. Os pontos que a chamam:
  1. `_advance_dependent_activities`, quando o dependente é `per_laboratory`.
     A condição atual "só se `BLOCKED`" passa a valer só para atividade única.
  2. A conclusão e a dispensa de um laboratório (R7, R9), para cada
     dependente por laboratório da atividade alterada.
- **Rationale**: uma função só cobre os três casos da tabela da Clarification
  5, e a idempotência evita controlar "já abri para este laboratório". A
  recursão via `_advance_dependent_activities` cobre cadeias que concluem
  sozinhas (ex.: todos os laboratórios dispensados, FR-018).
- **Alternatives considered**: espera por todos em toda dependência (texto
  original da issue). Rejeitada pelo usuário na Clarification 5.

## R7 — Conclusão da execução de um laboratório

- **Decision**: `complete_laboratory_run(session, process_id, activity_key,
  laboratory_id, user_id) -> ActivityRun` no motor. Ela:
  1. verifica que o processo é mutável e trava o processo (R12);
  2. aplica a autorização por laboratório (R8);
  3. exige execução vigente `IN_PROGRESS`, senão `ConflictError`;
  4. conclui a execução e as tarefas;
  5. registra `LABORATORY_RUN_COMPLETED`;
  6. abre a cadeia do laboratório nos dependentes por laboratório (R6);
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
    - Autorização: `is_effective_group_manager` ou `has_platform_wide_access`
      (FR-017); recusa com 403.
    - Validações:
      - processo mutável (409);
      - fase existe no processo (404);
      - laboratório no conjunto congelado (422 `laboratory_not_frozen`);
      - motivo não vazio (422);
      - dispensa duplicada (409 `already_waived`, pelo índice).
  - **Efeito**:
    - Nas atividades `per_laboratory` sem `is_custody` da fase, a execução
      vigente `IN_PROGRESS` do laboratório vira `WAIVED`, com as tarefas
      `CANCELLED`. As `COMPLETED` não mudam (FR-018).
    - Em seguida roda R6 nos dependentes por laboratório e recalcula cada
      atividade afetada.
    - Grava `LABORATORY_WAIVED` com `phase_key`, `laboratory_id` e `reason`,
      sem `activity_run_id`.
- **Rationale**: a dispensa precisa persistir para as atividades da fase que
  ainda vão abrir (FR-007); um estado só nas execuções não cobriria isso.
- **Alternatives considered**: dispensa por atividade (rejeitada pelo usuário
  na Clarification 4).

## R10 — Reabertura

- **Decision**:
  - **Motor**: `reopen_laboratory_run(session, process_id, activity_key,
    laboratory_id, reason, user_id) -> ActivityRun`, sem autorização própria
    (quem chama verifica) e sem commit.
  - **Recusas** (409): atividade não `per_laboratory`; execução vigente fora de
    `COMPLETED`; laboratório dispensado na fase em atividade sem `is_custody`
    (FR-026).
  - **Efeito**:
    1. A execução vigente vira `SUPERSEDED`. Valores, anexos e decisões dela
       não mudam (FR-024).
    2. Abre uma execução nova `n + 1`, com `Task` `READY` e `FormInstance` nova
       e vazia. O 2º comentário da issue pede um conjunto novo de valores, sem
       sobrescrever o anterior.
    3. A atividade volta a `IN_PROGRESS`.
    4. Roda `_reblock_dependents(act, laboratory_id)` em cadeia (FR-025):
       - Dependente por laboratório: só a execução vigente daquele laboratório
         muda. `IN_PROGRESS` vira `CANCELLED` (tarefas `CANCELLED`);
         `COMPLETED` vira `SUPERSEDED`. A cadeia segue nos dependentes dele
         para o mesmo laboratório.
       - Dependente único em `IN_PROGRESS` ou `COMPLETED`: volta a `BLOCKED`
         com `blocked_reason`. A execução aberta dele vira `CANCELLED`; a
         concluída fica como está. A cadeia segue nos dependentes dele para
         todos os laboratórios.
       - Ao final, o status de cada atividade por laboratório tocada é
         recalculado (R5).
    5. Grava `LABORATORY_RUN_REOPENED`, com `activity_run_id` da execução
       nova, os números anterior e novo, `reason` e as chaves reabloqueadas.
  - **Rota**: `POST /processes/{id}/activities/{activity_key}/laboratories/
    {laboratory_id}/reopen`, com a mesma autorização da dispensa (FR-022).
- **Rationale**: a liberação seguinte reaproveita R6 (abre nova execução
  quando a cadeia do laboratório se resolver) e `_activate_activity`, que já
  numera `max + 1` (Issue #22).
- **Alternatives considered**: copiar os valores da execução anterior, como
  `_open_new_submission_run`. Rejeitada para dados experimentais (BPL).

## R11 — Exposição em `/tasks` e na linha do tempo

- **Decision**:
  - **Campos novos**: `TaskSummary` e `TaskDetail` ganham `laboratory:
    LaboratoryRef | None`, montado em lote por `references.laboratory_refs`
    (Spec 033), e `activity_run_status: str` (FR-028).
  - **Rodada vigente**: `_current_run_clause` passa a comparar com o máximo
    por `(activity_instance_id, laboratory_id)`, usando
    `is_not_distinct_from` (FR-029).
  - **Linha do tempo**: os eventos novos levam `laboratory_id` em
    `context_data` (FR-030). Seguem a regra atual de visibilidade: com
    `activity_run_id`, pela visão da atividade; sem ele, para quem vê o
    processo.
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
- **Alternatives considered**: travar só a `ActivityInstance` (como a Spec
  031). Rejeitada: não cobre cascatas entre atividades diferentes.
