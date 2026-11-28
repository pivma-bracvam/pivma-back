# Research: Visibilidade da triagem e cegamento na linha do tempo

Base da pesquisa: `feat/047-sponsor-tracking`, commit `abe9eed`, que entrou em `develop` com a PR #83. O Technical Context não tem `NEEDS CLARIFICATION`; cada item abaixo resolve uma escolha de desenho.

## R1. Visão do proponente na triagem

- **Decision**: trocar `access.view: []` por `access.view: ["proponent"]` em `triage_evaluation` nos cinco YAML de `src/pivma/templates_data/` e subir `process_template.version` de cada um (01, 02 e 03: 6 → 7; 04: 8 → 9; 05: 2 → 3).
- **Rationale**: `resolve_activity_access` copia a concessão para `ActivityInstance.view_roles` na criação. `GET /tasks` (`activity_view_clause`) e `GET /tasks/{id}` (`require_activity_access(..., 'view')`) passam a mostrar a tarefa sem mudança de código. A edição continua só com `bracvam`, e `/triage/*` exige `triage.review`. Subir a versão cria uma `ProcessTemplateVersion` nova no bootstrap (`_sync_process_template_and_version`); com a mesma versão, o bootstrap sobrescreveria o payload da versão já usada por processos.
- **Alternatives considered**: conceder a visão por código para o proponente, fora do template. Rejeitada: o template é a fonte das concessões (Spec 030), e a exceção ficaria escondida.

## R2. Migração dos processos existentes

- **Decision**: migração Alembic só de dados, com `down_revision = 'b7d3e9a1c5f2'` (head atual). `upgrade` faz `UPDATE activity_instances SET view_roles = array_append(view_roles, 'proponent') WHERE key = 'triage_evaluation' AND NOT ('proponent' = ANY(view_roles))`. `downgrade` faz `array_remove(view_roles, 'proponent')` nas mesmas linhas.
- **Rationale**: decisão do usuário em 2026-11-27. A condição torna o `upgrade` idempotente (edge case da spec). Segue o formato de `3c9a1f2d7e40_process_lifecycle_activity_access.py`.
- **Alternatives considered**: sem migração, por a produção começar vazia. Rejeitada pelo usuário, porque a migração é simples. Downgrade sem efeito: rejeitado, porque deixaria o banco diferente da revisão anterior.

## R3. Autor dos eventos da triagem

- **Decision**: em `get_process_timeline`, o conjunto `TRIAGE_AUTHOR_EVENTS = {TRIAGE_APPROVED, TRIAGE_REJECTED, REVISION_REQUESTED, RETURN_REVIEW_OPENED}` substitui a comparação com `'RETURN_REVIEW_OPENED'`. Para quem não tem `has_process_review_access`, `user_id` vem nulo nesses tipos.
- **Rationale**: generaliza a regra já entregue na Spec 046, no mesmo ponto e com a mesma permissão. `context_data` desses eventos só tem a justificativa e o `run_number`, sem identificadores de pessoa.
- **Alternatives considered**: esconder o autor de todo evento com execução da triagem. Rejeitada: o conjunto explícito evita esconder eventos futuros de outra natureza sem decisão.

## R4. `FIELD_REVIEWED`

- **Decision**: `_visible_events` descarta `FIELD_REVIEWED` para quem não tem `has_process_review_access`.
- **Rationale**: o evento só registra a edição do triador antes da decisão (Clarifications). Com o descarte antes da paginação, `total` continua certo (Spec 033, R2).
- **Alternatives considered**: manter o evento com autor nulo. Rejeitada na Clarification.

## R5. Pareceres em `GET .../form`

- **Decision**: para quem não tem `has_process_review_access`, `get_activity_form` só põe em `reviews` os `FieldReview` cuja `activity_run_id` aponta para execução `COMPLETED`. Uma consulta busca os status das execuções referenciadas pelos pareceres do formulário.
- **Rationale**: mesmo critério de `submission_run_reviews` (`triage_run.status == 'COMPLETED'`), usado em `submission-versions` e `previous_reviews`. O triador continua lendo o rascunho no mesmo campo.
- **Alternatives considered**: reaproveitar `submission_run_reviews`. Rejeitada: ela é só de `proposal_submission` e indexa por `run_number`, enquanto a rota atende qualquer atividade de formulário e já tem os pareceres carregados.

## R6. Eventos de convite

- **Decision**: `INVITE_EVENT_TYPES = {INVITE_CREATED, INVITE_RESENT, INVITE_REVOKED, INVITE_ACCEPTED}` em `routers/processes.py`. Em `_visible_events`, depois do atalho de quem gerencia participantes, os demais só recebem `INVITE_ACCEPTED` com `event.user_id == current_user.id`.
- **Rationale**: `INVITE_ACCEPTED` grava como autor quem aceitou (`invite_service.py`, linha 448), então o autor identifica "o próprio convite". Os outros três tipos não têm o convidado como usuário, só o e-mail. A regra fica junto da de `PARTICIPANT_EVENT_TYPES`, que já usa `can_manage_participants`.
- **Alternatives considered**: comparar o e-mail do convite com o do usuário. Rejeitada: o e-mail do convite pode diferir do da conta que aceitou.

## R7. Cegamento do autor

- **Decision**: função `_blind_hidden_authors(session, current_user, process_id) -> set[UUID]`. Com `progress_view(...)` sobre `viewer_assignments`, se a visão não é `full` e `view.roles` não é vazio e `view.roles <= BLIND_REVIEW_ROLES`, devolve os `user_id` das designações do processo com cargo `proponent` ou em `BLIND_REVIEW_ROLES`, inclusive revogadas, menos o próprio usuário. Senão, conjunto vazio. Na montagem da resposta, `user_id` vem nulo quando está nesse conjunto.
- **Rationale**: reaproveita a regra da Spec 048 (`ProgressView`, `BLIND_REVIEW_ROLES`), com a união de cargos que ela já faz. Incluir designações revogadas cobre eventos antigos de quem deixou o cargo. Comparar o autor, e não o tipo do evento, cobre `PROCESS_CREATED`, `PROCESS_WITHDRAWN`, `DIRECT_REVIEW_REQUESTED`, `ACTIVITY_UNBLOCKED` e os eventos que ainda vão existir. Os eventos de designação que trazem `participant_user_id` já chegam só ao próprio titular.
- **Alternatives considered**: lista de tipos de evento de autoria do proponente. Rejeitada: quebra a cada evento novo. Chamar `ProgressView.sees_person` por autor: exigiria o cargo de cada autor e trataria do mesmo jeito os casos que importam aqui.

## R8. Testes afetados

- `tests/integration/database/test_activity_access_columns.py:153` afirma que `proponent` não está em `view_roles` da triagem. A asserção muda para o novo contrato.
- `tests/api/routers/test_timeline_router.py` cobre a ordem e o filtro por atividade; os testes novos de linha do tempo entram nele.
- A jornada da Etapa 1 fica em `tests/integration/journeys/etapa_1_submissao_triagem/`.
- A migração segue `tests/integration/migrations/test_process_lifecycle_migration.py` (`run_migration`, `run_downgrade`).
