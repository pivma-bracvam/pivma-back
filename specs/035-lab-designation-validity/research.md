# Research: Validade da designação laboratorial

Levantamento feito sobre a `develop` em `edd6db5`.

## R1 — Onde a autorização decide pelo cargo

**Decisão**: corrigir em dois pontos centrais de `src/pivma/core/authorization.py`:
`process_cargos_scope` e `active_participant_process_scope`.

**Justificativa**: todo acesso por cargo de processo passa por eles.

| Consumidor | Usa |
|---|---|
| `user_cargos` → `require_activity_access` (atividades, formulários, anexos, amostras), `_events_of_visible_activities` (linha do tempo) | `process_cargos_scope` |
| `activity_view_clause` (listagens de atividades e tarefas) | `process_cargos_scope` |
| `_can_act_clause` em `routers/tasks.py` ("posso agir") | `process_cargos_scope` |
| `process_visibility_clause` (listar e ver processos) | `active_participant_process_scope` |

Nenhum outro ponto concede acesso a cargo laboratorial.
`is_effective_group_manager`, `active_proponent_process_scope` e
`has_process_review_access` tratam só de cargos não laboratoriais e ficam como
estão. `participant_read_scope` devolve `'self'` para quem tem qualquer
designação, inclusive revogada, e mostra só o próprio histórico; continua igual
(premissa da spec).

**Alternativas consideradas**:

- Filtrar em cada consumidor: seis pontos para manter em sincronia, que é a
  origem do defeito atual.
- Revogar a designação quando o vínculo acaba: rejeitado pela Spec 006
  (research, decisão 6) e pela spec (FR-006).

## R2 — Uma única definição de efetividade

**Decisão**: criar em `authorization.py` um predicado SQL
`effective_assignment_clause()` sobre `Assignment`:

- cargo não laboratorial: nenhuma condição extra;
- cargo laboratorial: existe vínculo (`UserInstitutionalAffiliation`) ativo do
  mesmo usuário com o mesmo laboratório, e o laboratório e a instituição do
  laboratório estão ativos.

As condições comuns (não revogada, não excluída, usuário ativo) continuam onde
já estão. O predicado passa a ser usado por:

1. `process_cargos_scope` e `active_participant_process_scope` (autorização);
2. `compute_effectiveness_map` (exibição em `/auth/me` e na listagem de
   participantes), reescrita para consultar os ids efetivos com o mesmo
   predicado em vez de recalcular em Python;
3. `has_active_laboratory_affiliation` (validação de nova designação e do
   aceite de convite), que passa a conferir também o laboratório ativo.

**Justificativa**: hoje há três regras diferentes. A validação confere a
instituição e não o laboratório; o cálculo de efetividade confere o
laboratório e não a instituição. Com um só predicado, a exibição e a
autorização não divergem (FR-002, SC-002).

**Detalhe**: o filtro global de soft-delete (Spec 022) acrescenta
`deleted_at IS NULL` às entidades `AuditMixin` nas consultas ORM. O predicado
mantém os filtros explícitos, no padrão de `authorization.py`, sem depender
desse filtro.

**Alternativas consideradas**: manter o cálculo em Python e só acrescentar a
instituição. Resolve a exibição, mas não serve para as subconsultas SQL da
autorização, e deixaria duas implementações da mesma regra.

## R3 — Custo da checagem

**Decisão**: `EXISTS` correlacionado, sem índice novo.

**Justificativa**: o índice único parcial `uq_affiliations_active_laboratory`
(`user_id`, `institution_id`, `laboratory_id`, ativos) atende à busca do
vínculo. Laboratório e instituição são buscados pela chave primária. A
subconsulta só é avaliada para linhas de cargo laboratorial.

## R4 — Eventos de perda e volta da validade

**Decisão**: comparar o antes e o depois dentro da transação da ação
institucional.

1. Selecionar e travar (`FOR UPDATE`) as designações candidatas: ativas, de
   cargo laboratorial, dos laboratórios atingidos (e do usuário, no caso de
   vínculo), em processos em andamento (FR-008a).
2. Guardar os ids efetivos entre elas (predicado de R2).
3. Aplicar a ação e dar `flush`.
4. Calcular de novo os ids efetivos.
5. Gravar `PARTICIPANT_EFFECTIVENESS_LOST` para quem saiu do conjunto e
   `PARTICIPANT_EFFECTIVENESS_RESTORED` para quem entrou.

| Ação | Laboratórios atingidos | Filtro de usuário | Evento possível |
|---|---|---|---|
| `DELETE /users/{user_id}/affiliations/{id}` | o do vínculo (se houver) | o usuário | perda |
| `POST /users/{user_id}/affiliations` | o do vínculo (se houver) | o usuário | volta |
| `DELETE /laboratories/{id}` | o laboratório | nenhum | perda |
| `DELETE /institutions/{id}` | os laboratórios da instituição | nenhum | perda |

**Justificativa**: comparar o antes e o depois cobre sozinho os casos da spec.
Designação que já não valia não gera evento (FR-010), assim como a revogada,
que nem entra entre as candidatas. Não precisa de lógica por motivo, e tudo
fica na mesma transação da ação (FR-011).

**Concorrência**: travar as designações candidatas antes da primeira leitura
serializa duas ações institucionais simultâneas sobre as mesmas designações.
Em READ COMMITTED, a segunda transação espera a trava e, ao seguir, lê o
estado já confirmado pela primeira; assim não há evento de perda duplicado.

**Local**: `src/pivma/core/participant_service.py`, que já grava os eventos de
designação (`_assignment_event_context`). Os quatro endpoints de
`routers/institutional.py` chamam o serviço antes do `commit`.

**Alternativas consideradas**:

- Gatilho no banco: esconde regra de negócio fora do código e dos testes do
  projeto.
- Evento calculado na leitura da linha do tempo: não identifica quem fez a
  ação nem o momento exato.

## R5 — Formato do evento

**Decisão**: `AuditEvent` existente, sem migração.

- `event_type`: `PARTICIPANT_EFFECTIVENESS_LOST` ou
  `PARTICIPANT_EFFECTIVENESS_RESTORED` (cabem em `String(64)`).
- `user_id`: quem fez a ação institucional.
- `context_data`: o mesmo formato de `_assignment_event_context`
  (`assignment_id`, `participant_user_id`, `role_key`, `laboratory_id`,
  `result`, `source`) com `source = 'institutional'` e o campo novo `reason`:
  `affiliation_ended`, `laboratory_deactivated`, `institution_deactivated` ou
  `affiliation_created`.

Os dois tipos entram em `PARTICIPANT_EVENT_TYPES` (`routers/processes.py`).
Assim a linha do tempo mostra o evento a quem gere participantes e à própria
pessoa, com a regra já aplicada a `PARTICIPANT_ASSIGNED` e
`PARTICIPANT_REVOKED`.

## R6 — Dados existentes

**Decisão**: nenhuma migração nem carga retroativa.

**Justificativa**: a efetividade é calculada a cada pedido. Designações que já
não valiam passam a ter o acesso negado assim que a entrega sobe, sem evento
retroativo (Edge Cases da spec).

## R7 — Testes

**Decisão**: seguir `fastapi-testing-methodology`, aplicada no
`/speckit-tasks`. Base existente para reaproveitar:

- `tests/api/routers/test_participant_router.py`
  (`test_listing_signals_ineffective_after_losing_affiliation`);
- `tests/api/routers/test_activity_access.py` (matriz de concessões por cargo);
- `tests/api/routers/test_institutional_router.py` e
  `test_institutional_concurrency.py`.

Os testes rodam com testcontainers (`pgvector/pgvector:pg17`) e exigem Docker.
