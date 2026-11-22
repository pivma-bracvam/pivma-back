# Research: Alerts na plataforma

Leitura feita em `feat/047-alerts`, a partir de `develop` no commit `9a60855`.

## R1. Tabela própria

- **Decision**: os alerts ficam em uma tabela nova, `alerts`, com o modelo `Alert` herdando `AuditMixin`.
- **Rationale**: `notifications` guarda a entrega de um e-mail e apaga o conteúdo quando ela termina. `audit_events` pertence ao processo e não tem dono nem estado de leitura. Usar qualquer uma das duas misturaria finalidades que a spec separa (Clarifications).
- **Alternatives considered**: derivar os alerts da linha do tempo na leitura, guardando só a data da última leitura por usuário. A consulta teria de refazer a regra de destinatários a cada listagem, e a resposta mudaria quando o cargo do usuário mudasse, contra a premissa de destinatários calculados no acontecimento.

## R2. Destino e parâmetros

- **Decision**: o destino tem três colunas: `target_type` (`process`, `task` ou `sample_receipt`), `process_instance_id` (sempre preenchido) e `target_id` (tarefa ou frasco; nulo quando o destino é o processo). Os parâmetros ficam em `params`, JSONB.
- **Rationale**: os dez tipos da spec sempre nascem dentro de um processo. Com o processo em coluna própria, o índice e a chave estrangeira saem de graça, e o front sempre tem o identificador do processo para montar a rota.
- **Alternatives considered**: um JSON único para o destino. Atende ao front, mas perde a chave estrangeira para o processo.

## R3. Quem recebe `task_opened`

- **Decision**: a regra de `_can_act_clause` sai de `routers/tasks.py` e vai para `core/authorization.py` como `task_can_act_clause`, sem mudar o conteúdo. `routers/tasks.py` passa a importá-la. Para cada tarefa nova, `alert_service` reúne os candidatos e mantém só os que passam na regra:
  1. usuários com designação ativa no processo;
  2. usuários com perfil global (`administrator` ou `bracvam`) cujo cargo global esteja em `edit_roles` da atividade.

  Para cada candidato, uma consulta confere `task_can_act_clause` contra a tarefa recém-criada.
- **Rationale**: `can_act` já junta cargo, designação efetiva, laboratório da execução e conflito de interesse. Usar a mesma cláusula garante que o alert vai para quem vê `can_act = true` em `GET /tasks` (SC-001), sem uma segunda versão da regra. Há poucos candidatos por processo (dezenas), então uma consulta por candidato custa pouco.
- **Alternatives considered**: uma consulta só sobre `users`, com a cláusula correlacionada por `User.id`. A cláusula de hoje recebe `global_cargos` já calculados por usuário, então seria preciso reescrevê-la. Fica para quando o volume pedir.

## R4. Pontos de geração

- **Decision**: cada gatilho chama uma função de `alert_service` logo depois de gravar o próprio `AuditEvent`, na mesma sessão e sem `commit`.

| Tipo | Onde |
|---|---|
| `task_opened` | `process_engine._init_first_activity`, `_activate_activity`, `_start_laboratory_run`, `_open_new_submission_run`, `open_return_review`; `sample_receipt_service._open_resolution_run` |
| `submission_status_changed` | `pre_evaluation_service` (resultado positivo); decisões `TRIAGE_APPROVED` e `TRIAGE_REJECTED` em `process_engine` |
| `structure_approved` | `structure_approval_service`, ramo `APPROVED` |
| `process_withdrawn` | `return_review_service`, evento `PROCESS_WITHDRAWN` |
| `assignment_created` | `participant_service.create_assignment` |
| `assignment_revoked` | `routers/process_participants.py`, evento `PARTICIPANT_REVOKED` |
| `assignment_effectiveness_changed` | `participant_service.record_laboratory_validity_changes` |
| `laboratory_run_completed` | `process_engine`, evento `LABORATORY_RUN_COMPLETED` |
| `laboratory_run_waived` | `process_engine`, evento `LABORATORY_WAIVED` |
| `sample_nonconformity_decided` | `sample_receipt_service`, ao lado do e-mail da decisão, um alert por frasco decidido |

  A tarefa criada já cancelada em `_waive_laboratory_run` não gera alert. A designação do proponente na criação do processo também não, porque o autor é o próprio proponente (FR-006).
- **Rationale**: o projeto já pede o e-mail do mesmo jeito (Spec 036). A chamada explícita deixa cada gatilho visível no código e no teste.
- **Alternatives considered**: um ouvinte de `flush` do SQLAlchemy para cada `Task` nova. Roda em contexto síncrono, e a regra de destinatários precisa de consultas assíncronas. Também esconderia o gatilho.

## R5. Autor nas ações da IA

- **Decision**: a função de alert recebe `actor_id` à parte do `user_id` de auditoria. Os caminhos da pré-avaliação por IA passam `actor_id=None`. Para isso, `_advance_dependent_activities` e `_activate_activity` ganham o argumento nomeado `alert_actor_id`, e `pre_evaluation_service` passa `None`. `open_return_review` sempre passa `None`.
- **Rationale**: a IA grava `run.created_by`, o proponente, como autor de auditoria. Sem essa separação, a regra do FR-006 tiraria do proponente o alert da devolução pela IA e o da ida para a triagem. Em `open_return_review` os destinatários são proponentes, e nenhum proponente devolve a própria submissão.
- **Alternatives considered**: guardar o autor em `session.info`. Funciona, mas a dependência fica implícita.

## R6. Um alert por usuário e acontecimento

- **Decision**: cada função junta os destinatários em um `set` de ids, tira quem fez a ação e cria um alert por id. Nenhuma restrição de unicidade no banco.
- **Rationale**: cada acontecimento dispara uma chamada. A deduplicação só precisa cobrir o usuário com dois cargos qualificados (FR-005).
- **Alternatives considered**: um índice único por usuário, tipo e destino. Bloquearia a reabertura de uma atividade, que gera nova tarefa, e a decisão de dois frascos no mesmo processo.

## R7. Conta ativa

- **Decision**: só recebem alert usuários com `User.deleted_at` nulo, a mesma condição de `_active_proponent_emails` e `_laboratory_emails`.
- **Rationale**: é a regra atual de conta desativada (Spec 028).

## R8. Listagem

- **Decision**: `GET /alerts`, com `page`, `per_page` e `unread` (booleano, opcional). A resposta segue `ListPage` e acrescenta `unread_count` no topo. A ordem é `created_at` decrescente e, no empate, `id` decrescente.
- **Rationale**: o FR-013 pede o contador em toda resposta, e `summary` do `ListEnvelope` só sai com `include=summary`. Um campo fixo deixa o contrato mais simples para o front.
- **Alternatives considered**: uma rota só para o contador. Fica dispensável, porque `per_page=1` traz o contador com custo baixo.

## R9. Marcar como lido

- **Decision**: `POST /alerts/{alert_id}/read` e `POST /alerts/read-all`. As duas fazem `UPDATE ... WHERE user_id = :me AND read_at IS NULL`. A primeira devolve o alert, e a segunda devolve `{"updated": n}`. Um alert de outro usuário ou inexistente responde `404 not_found`.
- **Rationale**: o `UPDATE` com a condição `read_at IS NULL` deixa a operação idempotente e segura em chamadas simultâneas, sem trava explícita (FR-014 e o caso de duas marcações simultâneas). `POST` segue o padrão das ações do projeto e passa por `TrustedOrigin`.
- **Alternatives considered**: `PATCH /alerts/{id}` com `{"read": true}`. Abriria a porta para desmarcar, que a spec não pede.

## R10. Índices

- **Decision**: `ix_alerts_user_created` em `(user_id, created_at DESC)` e o índice parcial `ix_alerts_user_unread` em `(user_id)` com `WHERE read_at IS NULL`.
- **Rationale**: atendem à listagem e ao contador de não lidos.

## R11. Auditoria

- **Decision**: o alert preenche `created_by` com o autor da ação, ou nulo quando ela é automática. A marcação de leitura preenche `updated_by` com o dono. Nenhuma das duas grava `AuditEvent`.
- **Rationale**: o princípio II pede `AuditMixin` em todo modelo novo e `AuditEvent` em ação de negócio. A ação de negócio já grava o próprio evento, e a leitura é estado pessoal (FR-019).

## R12. Parâmetros por tipo

- **Decision**: cada função monta os parâmetros com chaves fixas. A lista de cada tipo está em [data-model.md](data-model.md#parâmetros-por-tipo). Nenhuma chave guarda justificativa, parecer, resultado da IA, nome de pessoa, nome químico, CAS ou SDS.
- **Rationale**: o teste de cegamento e de autoria (SC-002) confere essas chaves por tipo.

## R13. Alcance do BraCVAM

- **Decision**: cada pessoa com o perfil BraCVAM recebe o alert de toda tarefa de triagem, de designação e de homologação, em todos os processos, cerca de onze por processo, pela regra do R3.
- **Rationale**: o usuário decidiu em 2026-11-22 manter a regra de `can_act`, que é o que `GET /tasks` já mostra, até alguém do BraCVAM usar a caixa com dados reais. Registrado em `docs/observacoes-e-pendencias.md`, seção "Alerts na plataforma".
- **Alternatives considered**: deixar as oito designações da Fase 2 de fora; criar um responsável do BraCVAM por processo; apagar o alert das colegas quando uma conclui a tarefa. Qualquer corte futuro fica dentro de `alert_task_opened`, sem mudar o contrato.
