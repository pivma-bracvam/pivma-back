# Research: Ciclo de vida do processo e acesso por atividade

**Feature**: [spec.md](spec.md) · **Plano**: [plan.md](plan.md)

Cada decisão cita o código atual que a motivou. Os caminhos são relativos à
raiz do repositório.

## R1. Nome e domínio do campo de ciclo de vida

**Decision**: Manter a coluna e o campo de API `status` em `process_instances`,
trocando o domínio para `OPEN | CLOSED | CANCELLED | ARCHIVED`, com `CHECK`
constraint no banco e `Literal` nos schemas. Default passa a `OPEN`.

**Rationale**: A coluna já é filtrada e lida em 5 pontos do roteador
(`routers/processes.py:364, 389, 408, 410, 430, 477`) e nos auditores de ciclo
de vida (`core/process_engine.py:244, 276, 315`). Renomear multiplica a
mudança sem ganho de comportamento; o que muda para o cliente é o conjunto de
valores, e isso já é incompatível. O `CHECK` cumpre o FR-004, que hoje não
existe (a coluna é `String(32)` livre, `core/database/models.py:552`).

**Alternatives considered**:
- Renomear para `lifecycle_status`: nome mais explícito, mas obriga mexer em
  índice, schemas, filtros e testes sem mudar comportamento.
- Derivar o ciclo de vida de `closed_at`, `deleted_at` e um novo `archived_at`:
  descartado pela decisão do usuário (campo explícito) e por complicar filtro e
  índice.

## R2. Onde guardar as concessões de ver e editar

**Decision**: Duas colunas novas em `activity_instances`: `view_roles` e
`edit_roles`, ambas `ARRAY(String(64))`, `NOT NULL`, preenchidas na
instanciação a partir da definição da atividade no template.

**Rationale**:
- O payload da versão do template é **sobrescrito** na carga dos templates
  quando a versão não muda (`bootstrap_process_templates.py:141-146`). Ler as
  concessões do payload faria uma edição de YAML alterar processos já
  instanciados, contrariando a premissa da spec. Copiar na instanciação segue o
  mesmo padrão de `name`, `order_index` e `activity_type`
  (`core/process_engine.py:521-530`).
- As concessões precisam entrar em SQL para filtrar tarefas e listagens
  (`routers/tasks.py:44-46`). Um array na própria linha permite
  `ActivityInstance.view_roles.overlap(user_cargos)` sem join extra.
- Os 5 templates somam 23 atividades (18 atuais mais 5 de revisão do retorno) e
  poucos cargos por atividade; tabela própria não se paga.

**Alternatives considered**:
- Tabela `activity_access_grants (activity_instance_id, role_key, level)`: mais
  normalizada e pronta para granularidade por campo, mas acrescenta join em
  toda leitura de atividade e tarefa. Fica como evolução se a granularidade por
  campo for pedida (premissa da spec).
- Ler do `definition_payload`: descartado pelo motivo acima.

## R3. Concessão implícita de ver para `admin` e `bracvam`

**Decision**: Derivar do perfil global, sem gravar atribuição por processo.
O conjunto de cargos efetivos de um usuário num processo inclui `admin` quando
ele tem o perfil `administrator` e `bracvam` quando tem o perfil `bracvam`
(o mesmo critério de `has_platform_wide_access`,
`core/authorization.py:390-397`). Na instanciação, `view_roles` sempre recebe
`admin` e `bracvam`, e a carga de templates recusa definições que tentem
removê-los.

**Rationale**: É a proposta do usuário ("cargo local atribuído
automaticamente") com o mesmo comportamento observável e sem manutenção:
gravar uma `Assignment` por processo exigiria backfill a cada admin novo,
revogação em massa a cada perfil removido e crescimento de linhas processos ×
admins. O código já trata `admin` e `bracvam` como cargos resolvidos pelo
perfil (`GLOBAL_ACTIVITY_CARGOS`, `core/authorization.py:55`).

**Alternatives considered**: `Assignment` automática por processo, descartada
pelos custos acima.

## R4. Cargos efetivos de um usuário num processo

**Decision**: Uma função `user_cargos(session, user_id, process_id) -> set[str]`
em `core/authorization.py`: `role_key` das `Assignment` ativas do usuário no
processo (mesmos filtros de `active_participant_process_scope`: não revogada,
não removida, usuário ativo) mais os cargos globais do R3. Para SQL, uma
variante que devolve a expressão de subquery de `role_key`.

**Rationale**: Visibilidade de processo já usa esse critério
(`active_participant_process_scope`, `core/authorization.py:400-416`). A
efetividade temporal de laboratório (`compute_effectiveness_map`) só é usada em
`/auth/me` e não em autorização de atividade hoje; mantê-la fora evita mudar
comportamento de laboratório nesta feature.

**Alternatives considered**: Aplicar `compute_effectiveness_map`: mais
restritivo que o comportamento atual para cargos de laboratório, fora do
escopo.

## R5. Visibilidade de processo sem status

**Decision**: `process_visibility_clause` passa a ser: sem restrição para
acesso de plataforma (Admin/BraCVAM, que têm ver em tudo pelo R3); caso
contrário, `ProcessInstance.id IN active_participant_process_scope(user_id)`.
O ramo `PROPONENT_SCOPED_STATUSES` desaparece.

**Rationale**: FR-015 dá o cabeçalho a qualquer participante com atribuição
ativa. Como toda concessão a cargo de processo exige atribuição, "tem
atribuição ou tem concessão de ver" reduz a "tem atribuição", e Admin/BraCVAM
veem tudo. A regra fica mais simples que a atual (`core/process_engine.py:124-150`).

**Mudança de comportamento registrada**: um `sponsor` ou `group_manager` com
atribuição passa a ver o cabeçalho de um processo em submissão, o que hoje não
acontece. O conteúdo da submissão continua protegido pela concessão da
atividade. É o efeito da resposta Q1 = B.

## R6. Autorização por atividade

**Decision**: Duas funções em `core/authorization.py`:

- `require_activity_view(session, user_id, activity)`: `NotFoundError` se
  `user_cargos ∩ activity.view_roles` for vazio.
- `require_activity_edit(session, user_id, activity)`: primeiro exige ver
  (senão `NotFoundError`), depois `AuthorizationError` se
  `user_cargos ∩ activity.edit_roles` for vazio.

Os pontos que hoje checam `PROPONENT_SCOPED_STATUSES` ou nada chamam essas
funções: `get_current_form_instance` e `get_current_activity_run`
(`core/process_engine.py:698-710, 781-793`) recebem um parâmetro `access`
(`'view' | 'edit'`); rascunho, envio, anexos, avaliações de campo e decisão de
triagem pedem `edit`; leituras pedem `view`. A triagem mantém também
`require_permission(TRIAGE_REVIEW)` (premissa da spec).

**Rationale**: Hoje o envio do formulário não tem checagem de cargo além do
ramo por status (`core/process_engine.py:1930-1946`); depois da triagem,
qualquer usuário autenticado com visibilidade consegue ler a submissão. A
checagem por atividade fecha isso num ponto só.

**Status HTTP**: sem ver → 404 (não revela existência, FR-017); vê mas não edita
→ 403 (FR-018); edita mas a execução está fechada ou o processo não está
`OPEN` → 409 (FR-019), como hoje.

## R7. Guardas de fluxo sem status

**Decision**:
- Decisão de triagem (`core/process_engine.py:2314`): exige execução
  `IN_PROGRESS` da atividade `triage_evaluation` e atividade `IN_PROGRESS`;
  senão 409.
- Edição da submissão (`core/process_engine.py:1087`) e rascunho: exigem
  execução `IN_PROGRESS` de `proposal_submission` com formulário não enviado.
- Pré-avaliação pendente (FR-024): já garantida, porque o formulário da
  execução fica `is_submitted=True` a partir do envio.
- As escritas de status de fluxo (`process_engine.py:2027, 2061, 2232, 2259`;
  `pre_evaluation_service.py:218, 288, 335, 433`) são removidas.
  `_set_process_status` some; a checagem de cancelado/arquivado que ele fazia
  vai para `ensure_process_mutable`, que passa a exigir `OPEN`.

## R8. Trava de concorrência da pré-avaliação

**Decision**: Trocar o `SELECT ... FOR UPDATE` no processo filtrado por
`status == AI_PRE_EVALUATION` (`pre_evaluation_service.py:153-161`) por
`SELECT ... FOR UPDATE` na própria `EvaluationRun` com
`status == 'in_progress'`, mais `ProcessInstance.status == 'OPEN'` lido na
mesma transação. A checagem inicial (`pre_evaluation_service.py:88-93`) passa
a ser "a execução ainda está `in_progress`". A varredura de execuções presas
(`pre_evaluation_service.py:158`) filtra pela `EvaluationRun`.

**Rationale**: O estado "aguardando IA" pertence à execução, não ao processo.
Retry, revisão direta e `_execute` já disputam a mesma `EvaluationRun`; travar
a linha dela serializa os três. A unicidade de `DirectReviewRequest` por
execução (`core/database/models.py:1510-1513`) continua valendo.

**Alternatives considered**: Travar a `ActivityRun` da submissão: também
serializa, mas a disputa real é pela execução da IA.

## R9. Revisão do retorno

**Decision**:
- Nova atividade `submission_return_review` na fase 1 dos 5 YAMLs:
  `assigned_role: proponent`, `activity_type: return_review`, sem
  `form_template_key` (o motor só cria `FormInstance` quando a atividade o
  declara, `core/process_engine.py:574, 1708`), sem `dependencies`,
  `sla_hours: 168`.
  Nasce `BLOCKED` com `blocked_reason` "Sem retorno pendente".
- Abertura (FR-036): uma função `open_return_review(session, process_id,
  source, context, user_id)` cria nova `ActivityRun` (`run_number`
  incremental), `Task` para `proponent` e evento `RETURN_REVIEW_OPENED`.
  `source ∈ {'AI_PRE_EVALUATION', 'TRIAGE'}`, guardado em
  `ActivityRun.execution_reason` e no evento.
  Chamada em `_return_to_proponent` (IA negativa ou falha) e em
  `_handle_needs_revision` (triagem), no lugar de `_open_new_submission_run`.
- Escolha (FR-039): `POST /processes/{id}/return-review` com
  `{choice: REVISE | CONTEST_AI | WITHDRAW, justification?}`.
  - `REVISE` → `_open_new_submission_run` (já existe e copia os valores).
  - `CONTEST_AI` → reaproveita `pre_evaluation_service.request_direct_review`;
    só aceito se `source == 'AI_PRE_EVALUATION'` (senão 422).
  - `WITHDRAW` → `status = CLOSED`, `closed_at`, `closure_reason`, cancela
    tarefas pendentes (reaproveita `_cancel_pending_children`).
  A execução é concluída na mesma transação, com `SELECT ... FOR UPDATE` na
  `ActivityRun`; uma segunda escolha encontra a execução `COMPLETED` e recebe
  409 (FR-040).
- Leitura (FR-037): `GET /processes/{id}/return-review` devolve a execução
  aberta com o conteúdo do retorno: para IA, o mesmo payload de
  `GET /pre-evaluation`; para triagem, `outcome` e `justification` da `Decision`.
  As avaliações por campo seguem o cegamento atual (hoje o proponente já as
  recebe no formulário da nova execução).
- `POST /processes/{id}/submission/direct-review` é **removido**: a contestação
  passa a ser uma escolha. Mantê-lo criaria dois caminhos para a mesma
  transição, com a revisão do retorno aberta e sem escolha registrada.
- Retry administrativo de uma pré-avaliação com falha (`retry_run`) enquanto a
  revisão do retorno está aberta: cancela a execução aberta da revisão do
  retorno e sua tarefa antes de criar a nova `EvaluationRun`.

**Rationale**: Reaproveita os três efeitos que já existem
(`_open_new_submission_run`, `request_direct_review`, cancelamento de filhos) e
só acrescenta a atividade que os dispara. `activity_type` é texto livre com
valores `form` e `role_assignment` hoje; `return_review` identifica a atividade
sem acoplar o motor à chave.

**Instanciação sem abrir a atividade**: `instantiate_process` abre toda
atividade sem `dependencies` (`core/process_engine.py:652-657`), e
`_advance_dependent_activities` libera dependentes cujo requisito foi cumprido.
Para a revisão do retorno ficar parada até um evento, o motor pula atividades
com `activity_type == 'return_review'` nesses dois pontos. Ela nasce `BLOCKED`,
sem execução e sem tarefa. Descartado: uma dependência fictícia com
`condition_type` novo, que acoplaria o motor a um tipo de condição sem outro
uso.

**Alternatives considered**: Formulário de template com um campo de escolha:
reaproveitaria o envio de formulário, mas misturaria uma decisão de fluxo com
dados de submissão e exigiria validar a escolha fora do formulário.

## R10. Migração

**Decision**: Uma revisão Alembic que:

1. `UPDATE process_instances SET status = 'OPEN' WHERE status IN
   ('SUBMISSION','AI_PRE_EVALUATION','TRIAGE','PLANNING')`; altera o default;
   cria `ck_process_instances_status`.
2. Adiciona `view_roles` e `edit_roles` a `activity_instances` e faz backfill
   por `key`, usando a tabela de concessões dos YAMLs atuais embutida na
   migração (as chaves de atividade são estáveis); atividade de chave
   desconhecida recebe `edit_roles = [cargo da tarefa mais recente]` e
   `view_roles = edit_roles ∪ {admin, bracvam}`.
3. Cria a `submission_return_review` (`BLOCKED`) na fase 1 de cada processo
   existente que não a tenha.
4. `downgrade`: remove a atividade nova e as colunas, remove o `CHECK` e
   reconstrói o status de fluxo a partir das atividades: `ai_pending`
   (`EvaluationRun in_progress`) → `AI_PRE_EVALUATION`; triagem
   `IN_PROGRESS` → `TRIAGE`; fase 1 `COMPLETED` → `PLANNING`; demais `OPEN` →
   `SUBMISSION`.

**Rationale**: Mantém a regra do repositório de testar upgrade e downgrade
(`tests/integration/migrations/`). Processos com submissão reaberta por retorno
antigo não ganham revisão do retorno retroativa (premissa da spec).

## R11. Ações disponíveis, filtro de listagem e respostas

**Decision**:
- `lifecycle_available_actions` (`core/process_engine.py:108-121`) não muda de
  lógica; os conjuntos terminais passam a ser `{CLOSED, CANCELLED, ARCHIVED}`
  sobre o novo domínio.
- `GET /processes?status=` aceita `Literal['OPEN','CLOSED','CANCELLED',
  'ARCHIVED']`; valor antigo → 422 pela validação do FastAPI.
- `TriageDecisionResponse.new_process_status` → `process_status`, com o ciclo
  de vida (`OPEN` ou `CLOSED`); `next_activity_run` passa a indicar a execução
  da revisão do retorno aberta em `NEEDS_REVISION`.
- `DirectReviewResponse` sai junto com o endpoint (R9).

## R12. Tarefas e linha do tempo

**Decision**:
- `GET /tasks` (`routers/tasks.py:20-70`) filtra por
  `ActivityInstance.view_roles.overlap(<cargos do usuário no processo>)`, com os
  cargos globais do usuário somados como constantes e os de processo por
  subquery correlacionada em `Assignment`. `GET /tasks/{id}` exige ver na
  atividade.
- `GET /processes/{id}/timeline` (`routers/processes.py:645-680`): eventos com
  `activity_run_id` só aparecem se o usuário vê a atividade da execução;
  eventos de processo (criação, ciclo de vida, participantes) seguem a regra
  atual de `_visible_events`.
