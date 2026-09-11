# Phase 0 Research: Kanban de Pendências e Revisão de Cargos

## Auditoria do estado atual (achados verificados em código)

Antes de decidir o desenho, a revisão de cargos pedida pelo usuário (spec, User Story 2)
exigiu auditar como autorização funciona hoje. Três achados concretos, confirmados por
leitura direta do código, motivam as decisões abaixo:

**A1. `GET /processes` e `GET /tasks` não restringem visibilidade por participação.**
`list_processes` (`src/pivma/routers/processes.py:363`) só filtra processos fora de
`PROPONENT_SCOPED_STATUSES` (ou processos do próprio proponente); qualquer usuário
autenticado, com **qualquer** cargo global ou nenhum, vê todo processo em `TRIAGE`,
`PLANNING`, `CLOSED` etc., mesmo sem nenhuma atribuição nele. `list_tasks`
(`src/pivma/routers/tasks.py:26`) é ainda mais aberto: nenhum filtro de visibilidade,
apenas soft-delete — qualquer usuário autenticado lista **todas** as tarefas de
**todos** os processos da plataforma. Isso confirma a lacuna que a spec (FR-006/FR-014)
pede para corrigir.

**A2. Três vocabulários de "cargo" distintos e parcialmente inconsistentes coexistem:**
- `AccessProfile.system_key`/`name` (RBAC global, tabela `access_profiles`): inclui os
  dois cargos globais reais (`administrator`, `bracvam`) **e**, por herança de uma
  migração anterior à Spec 006, uma pilha de perfis com nomes de cargo de processo
  (`proponent`, `management_group`, `study_manager`, `participating_laboratory`,
  `ad_hoc_evaluator`, `reviewer`, `specialist`, `statistical_analyst`) que hoje não são
  usados para nada no domínio.
- `Assignment.role_key` (atribuição por processo, validado pelo `Literal`
  `ParticipantRole` em `schemas.py:565`): `group_manager`, `study_manager`,
  `statistician`, `adhoc_evaluator`, `peer_reviewer`, `lead_laboratory`,
  `participating_laboratory`, `proponent`.
- `Task.assigned_role` (string livre, sem validação, declarada em cada YAML de
  template): hoje só três valores existem, `PROPONENT`, `TRIAGE_LEAD`,
  `BRACVAM_ADMIN` — nenhum dos dois últimos corresponde a nenhum `role_key` de
  `Assignment` nem a nenhum `system_key` de `AccessProfile`. `TRIAGE_LEAD` não é
  resolvido por atribuição alguma: a autorização real da triagem usa a permissão global
  `triage.review` (Spec 014), concedida ao perfil `bracvam`/`administrator` —
  coincidentemente compatível com "Admin/BraCVAM veem tudo", mas por um caminho
  totalmente desconectado do texto `TRIAGE_LEAD` gravado na `Task`.

**A3. A primeira tarefa de cada processo é gravada com pessoa E cargo, as demais só com
cargo.** `_init_first_activity` (`process_engine.py:167-174`) cria a `Task` de
`proposal_submission` com `assigned_role='PROPONENT'` **e**
`assigned_user_id=creator_id`. Todo o resto do motor (`_activate_activity`,
`_unblock_triage_activity`, `_open_new_submission_run`) cria `Task` só com
`assigned_role`, nunca com `assigned_user_id`. Como `Assignment` permite múltiplas
pessoas com o mesmo `role_key` no mesmo processo (constraint única é
`process_instance_id + user_id + role_key`, não `process_instance_id + role_key`), fixar
`assigned_user_id` no criador é uma inconsistência real com "atividade pertence ao
cargo" — confirma o achado que motivou a FR-016/FR-017 da spec.

**A4. `GET /auth/me` já computa exatamente a visão de cargos que a spec pede.** O
endpoint (`routers/auth.py:98`) já retorna `access.profiles` (cargos globais do
usuário) e `access.scopes` (lista agrupada por `process_id` dos `role_key` ativos do
usuário naquele processo — já é literalmente "Proponente no processo A, Gestor no
processo B"). Nenhuma mudança é necessária aqui; é a fonte que já resolve a User Story 2
do lado do cliente. O problema nunca foi a modelagem de `Assignment`/`AccessProfile` —
foi a aplicação inconsistente dela nas listagens de processo/tarefa.

## Decisões

### D1 — Cargo global (`Padrão`/`Admin`/`BraCVAM`): reaproveitar `AccessProfile`, sem tabela nova

**Decision**: `Admin` e `BraCVAM` continuam sendo os perfis já existentes
`AccessProfile.system_key IN ('administrator', 'bracvam')`. `Padrão` continua sendo a
ausência de qualquer perfil dessa natureza — não ganha uma linha própria. Uma função
pura nova, `has_platform_wide_access(session, user_id) -> bool`, centraliza esse
cálculo (hoje espalhado ad hoc em `can_manage_process_templates`) e passa a ser o único
lugar que decide "este usuário vê a plataforma inteira".

**Rationale**: a informação já existe e já é exposta por `GET /auth/me`; criar um
campo/tabela `global_role` duplicaria uma fonte de verdade e arriscaria os dois
ficarem dessincronizados.

**Alternatives considered**: adicionar uma coluna `global_role` enumerada em `User` —
rejeitado por duplicar `AccessProfile`, que já é a fonte de verdade do RBAC global no
projeto (usada por 6+ specs anteriores).

### D2 — Correção de visibilidade: uma função de escopo reaproveitada nas 3 listagens

**Decision**: nova função pura `active_participant_process_scope(user_id)` (irmã de
`active_proponent_process_scope`, já existente) retorna a subquery de processos onde o
usuário tem **qualquer** `Assignment` ativa (qualquer `role_key`), não só proponente.
`GET /processes`, `GET /processes/{id}` e `GET /tasks` passam a filtrar por: usuário tem
acesso de plataforma (`D1`) **OU** processo está nesse escopo. Nenhuma rota nova de
RBAC é criada — é a mesma regra hoje parcial em `list_processes`, generalizada e
também aplicada a `list_tasks`, que hoje não tem regra nenhuma (achado A1).

**Rationale**: resolve FR-003/FR-004/FR-006/FR-014 com uma única função reaproveitada em
vez de lógica duplicada por rota — e corrige `list_tasks`, que era o maior vazamento.

**Alternatives considered**: restringir a correção só ao novo endpoint de Kanban —
descartado porque o usuário escolheu explicitamente "plataforma inteira" na clarificação
da spec (FR-014), e deixar `GET /tasks` aberto manteria o vazamento mais grave.

### D3 — SLA por etapa (`Em Atraso`): campo declarativo opcional no template, sem tabela nova

**Decision**: cada atividade no YAML/`definition_payload` ganha uma chave opcional
`sla_hours: int | null` (ausente/`null` = sem prazo, nunca "Em Atraso" — default
explícito exigido pela spec). O motor não grava nada novo em `ActivityRun`: o prazo é
resolvido em tempo de leitura comparando `ActivityRun.started_at` (já existe) + o
`sla_hours` da definição da atividade na versão do template ao qual a instância está
presa (`ProcessTemplateVersion.definition_payload`, já congelada por instância) contra o
instante da consulta.

**Rationale**: a resposta da clarificação com o usuário foi explícita — SLA por etapa,
declarado no template, não configurável por atividade individual via API. Guardar o
prazo no payload já congelado por versão também herda de graça a garantia de
imutabilidade da Spec 004 (FR-001/SC-002): publicar SLA novo em uma versão nova do
template nunca muda o prazo de instâncias já criadas a partir de versões antigas.

**Alternatives considered**: coluna `due_date` em `ActivityRun`, calculada e gravada no
momento em que a run começa — rejeitado por introduzir estado derivado que pode
dessincronizar do template (e a tabela `Task` já tem uma coluna `due_date` não usada por
ninguém hoje, o que sugere que gravar prazo por linha já foi tentado/abandonado antes;
não reaproveitar esse campo evita reviver ambiguidade sobre sua fonte de verdade).

### D4 — Atividade sempre por cargo: remover o vínculo direto a pessoa

**Decision**: `_init_first_activity` deixa de definir `assigned_user_id` na `Task` de
`proposal_submission` — passa a criar a tarefa só com `assigned_role`, como todo o
resto do motor já faz. `created_by` (herdado de `AuditMixin`) continua registrando quem
disparou a submissão; isso não se perde, só deixa de ser usado como "dono" da pendência.

**Rationale**: resolve FR-016/FR-017 diretamente no único ponto do motor que hoje viola
a regra (achado A3); é uma correção pontual, não uma reformulação.

**Alternatives considered**: remover a coluna `Task.assigned_user_id` do schema —
rejeitado por ser mudança estrutural desnecessária para o objetivo (o campo nullable
sem uso não impede a regra de cargo; removê-lo quebraria compatibilidade sem ganho
adicional) e por estar fora do escopo desta spec.

### D5 — Vocabulário de cargo compartilhado entre template, `Task` e `Assignment`

**Decision**: `Task.assigned_role`/o `assigned_role` declarado no YAML de cada atividade
passam a usar o mesmo vocabulário de `Assignment.role_key` (`ParticipantRole`) para
cargos contextuais (`proponent`, `group_manager`, `study_manager`, `statistician`,
`adhoc_evaluator`, `peer_reviewer`, `lead_laboratory`, `participating_laboratory`), mais
dois valores reservados para cargo global (`admin`, `bracvam`) usados por atividades cujo
responsável é inerentemente a equipe BraCVAM/Admin (ex.: a etapa de triagem, o
placeholder de exemplo da Spec 017), resolvidos via `AccessProfile` (D1) em vez de via
`Assignment`. Os valores hoje gravados (`PROPONENT`, `TRIAGE_LEAD`, `BRACVAM_ADMIN`) são
normalizados por migração de dados (`UPDATE`, não estrutural) e os 5 YAML de template são
atualizados para declarar o novo vocabulário.

**Rationale**: sem um vocabulário único, a resolução "quem ocupa este cargo agora"
(necessária tanto para o Kanban quanto para o alerta de cargo vazio da spec) precisaria
de um mapa manual por template — frágil e o tipo de encaixe forçado que a Constituição
(e a Spec 017, no mesmo espírito) já rejeita para `activity_type`. Alinhar ao vocabulário
que `Assignment`/`ParticipantRole` já validam evita inventar um quarto vocabulário.

**Alternatives considered**: manter `Task.assigned_role` livre e adicionar uma tabela de
mapeamento cargo-do-template → `role_key` — rejeitado por adicionar uma tabela nova só
para contornar uma inconsistência de nomenclatura que pode ser corrigida na fonte.

### D6 — Resolução de cargo: uma função pura reaproveitada

**Decision**: nova função `resolve_activity_holders(session, process_id, cargo) ->
list[User]`: se `cargo` é `admin`/`bracvam`, consulta `UserAccessProfile`/`AccessProfile`
(global); caso contrário, consulta `Assignment` ativa naquele processo com aquele
`role_key`. Usada (a) pelo endpoint de Kanban para decidir "esta atividade é minha", e
(b) pelo alerta de cargo sem ocupante (Edge Case da spec) quando a lista vier vazia.

**Rationale**: um único ponto de resolução evita duas implementações divergentes para a
mesma pergunta ("quem é responsável por este cargo agora").

### D7 — Novo endpoint de leitura para o Kanban, baseado em `ActivityInstance`

**Decision**: novo endpoint `GET /activities/kanban` (nome definitivo confirmado em
`contracts/`). Consulta `ActivityInstance` (não `Task`) porque toda atividade declarada
já existe como linha desde a instanciação do processo (Spec 004/017), inclusive as
`BLOCKED` sem `ActivityRun`/`Task` nenhum — é a única fonte que cobre a coluna
`Não Iniciado` sem inferência (o mesmo argumento já usado pela Spec 017 US1 para o
roteiro de uma única instância; aqui generalizado para todas as instâncias visíveis ao
usuário de uma vez). Decorada com `column` (`NAO_INICIADO`/`EM_ANDAMENTO`/`EM_ATRASO`/
`CONCLUIDO`, calculada a partir de `ActivityInstance.status` + D3), `cargo` (via D5),
contexto do processo e, quando bloqueada, o motivo + a atividade predecessora (reaproveita
`ActivityDependency`, já gravada desde a Spec 004).

**Rationale**: não é um endpoint facilitador de demo (Constituição Princípio II) — é a
capacidade de domínio pedida explicitamente pela User Story 1, que nenhum endpoint
existente cobre (nem `GET /tasks`, que não vê atividades sem `Task`; nem
`GET /processes/templates/{key}` + `GET /tasks` combinados, que é o truque usado pela
Spec 017 para **uma** instância, mas não escala para "todos os processos associados a
mim" sem uma consulta por processo, violando FR-001/FR-012 diretamente).

**Alternatives considered**: estender `GET /tasks` para também emitir uma linha
sintética por atividade `BLOCKED` sem `Task` — rejeitado por misturar duas semânticas
(tarefa acionável vs. atividade do roteiro) na mesma resposta, tornando o contrato
ambíguo para quem já consome `GET /tasks` hoje.

### D8 — Demonstração e seed

**Decision**: `demos/kanban/index.html` (quadro Kanban real,
consumindo os endpoints acima) + `scripts/seeds/seed_kanban.py` criando
~300 processos (distribuídos pelos 5 templates oficiais, em estágios variados incluindo
alguns propositalmente `Em Atraso`) atribuídos a um usuário `BraCVAM` semeado, mais 2
usuários `Padrão` com cargos contextuais cruzados (Proponente em uns métodos, Gestor em
outros) para demonstrar a User Story 2 na mesma passada.

**Rationale**: atende à Constituição Princípio III (demo como critério de conclusão) e
exercita as três user stories de ponta a ponta contra a API real.
