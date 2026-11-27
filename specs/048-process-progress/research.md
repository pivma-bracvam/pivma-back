# Research: Andamento do processo por cargo

Não restou `NEEDS CLARIFICATION`. As referências de linha valem para o commit
`9a60855`. A versão de 2026-11-23 tinha rotas só para o Patrocinador
(`/sponsor-tracking`); R1 a R4 e R9 registram o redesenho de 2026-11-25.

## R1. Onde mora o acompanhamento

**Decision**: nas rotas de processo, sem prefixo novo:

- `GET /processes`: a lista (US1), com o filtro `role` e três campos novos
  por item (`current_phase`, `open_activity_count`, `my_roles`).
- `GET /processes/{id}/progress`: o andamento (US2 a US4), ao lado de
  `/timeline` e `/participants`.

**Rationale**: o acompanhamento serve a todo cargo do processo. Uma rota por
cargo multiplicaria os endpoints, como apontou a revisão da PR #83. A lista
já existe e já aplica `process_visibility_clause`; os campos novos são
aditivos e não quebram quem a consome (constituição VI). O andamento é uma
leitura do processo, então fica sob `/processes/{id}`.

**Alternatives considered**:

- `/sponsor-tracking` (versão de 2026-11-23): resolve o Patrocinador e pede
  outra rota para cada cargo seguinte.
- Ampliar `GET /tasks`: `/tasks` é a caixa de trabalho e mostra só as
  tarefas das atividades que o cargo abre (`activity_view_clause`). Abrir as
  tarefas de todos encheria a caixa do Patrocinador com tarefas que não são
  dele, ou pediria um modo novo com regra própria, um segundo endpoint
  dentro de um parâmetro. A tarefa não traz quem ocupa os cargos, e as fases
  sem tarefa não aparecem: o front teria de cruzar `/tasks`,
  `/participants` e o template, e o cartão da lista pediria uma chamada por
  processo. Decidido pelo usuário em 2026-11-25. Os alerts (Spec 047) não
  pesam nessa escolha: os destinatários saem de `can_act`, que parte de
  `edit_roles`, e não mudam quando a visibilidade de `/tasks` muda
  (correção da revisão de 2026-11-27).
- Ampliar `GET /processes/{id}/participants`: resolve as pessoas, mas não a
  fase nem as atividades. A rota traz `assigned_by` e a declaração de
  conflito, que o recorte teria de esconder campo a campo, e
  `participant_read_scope` serve também o histórico.

## R2. Filtro `role` na lista

**Decision**: `role: ParticipantRole | None`. A cláusula
`role_process_clause(user_id, role_key)` (`src/pivma/core/process_engine.py`)
usa `process_cargos_scope`, a mesma base de `proponent_process_clause`, que
passa a chamar a nova. `filters_applied` devolve `role`. Os arquivados seguem
a regra da lista: só com `status=ARCHIVED`, para quem tem acesso de revisão.

**Rationale**: o convite pendente não cria `Assignment` (só o aceite cria),
e `process_cargos_scope` já exige designação ativa e efetiva, então FR-002
sai sem filtro extra. Cargo fora do catálogo responde `422`.

**Alternatives considered**: manter os arquivados no filtro por cargo, como
na versão de 2026-11-23. Criaria uma exceção à regra de arquivados de
`GET /processes` só para um filtro.

## R3. Campos do item da lista

**Decision**: `ProcessListItem` estende `ProcessInstanceDetail` com
`current_phase`, `open_activity_count` e `my_roles`. A página faz três
consultas a mais, sem consulta por item: as designações do usuário nos
processos da página (`viewer_assignments`), as execuções em andamento dos
processos `OPEN` (`open_runs`, [R6](#r6-fase-atual-e-atividades-em-andamento))
e os laboratórios das designações. `open_activity_count` conta só as
execuções que o recorte ([R9](#r9-recorte-por-cargo)) deixa o usuário ver.
`GET /processes/{id}` e `POST /processes` continuam com
`ProcessInstanceDetail`.

**Rationale**: o front pediu "informações úteis no cartão". Usar as funções
do andamento garante que o cartão e o andamento mostrem a mesma fase e a
mesma contagem. `my_roles` substitui `sponsored_since` e serve a qualquer
cargo. Com `paginate_query` de volta, a página não junta a data da
designação na mesma consulta: se uma revogação cair entre as consultas, o
item vem sem aquela designação em `my_roles`, sem erro.

**Alternatives considered**:

- Sem fase no cartão: o front chamaria o andamento de cada processo (N+1 no
  cliente).
- Os campos também em `GET /processes/{id}`: o andamento já os traz, e
  `POST /processes` usa o mesmo schema.

## R4. Quem consulta o andamento

**Decision**: quem vê o processo em `GET /processes/{id}`
(`process_visibility_clause`) recebe `200`. Os demais recebem `404` com a
mensagem "Processo não encontrado.". Processo excluído também dá `404`.
Admin e BraCVAM abrem qualquer processo, com `my_roles` vazio quando não têm
cargo nele.

**Rationale**: FR-009 e a constituição III. Quem vê o cabeçalho do processo
já sabe que ele existe; o recorte (R9) decide o resto.

## R5. Pessoas por cargo

**Decision**: o andamento traz `roles`, uma entrada por cargo do catálogo
`ParticipantRole` (`src/pivma/schemas.py:1064`) que o recorte (R9) deixa o
usuário ver, na ordem de `typing.get_args(ParticipantRole)`, cada uma com as
`people` visíveis. Cada pessoa tem
`user` (`UserRef`, sem e-mail) e `laboratory` (`LaboratoryRef`, nulo fora dos
cargos de laboratório). A consulta usa as mesmas condições de
`effective_assignment_ids` (`src/pivma/core/authorization.py:672`):
designação ativa, não excluída, usuário ativo e `effective_assignment_clause`.
Dentro do cargo, a ordem é `assigned_at` e depois `id`. Os laboratórios vêm de
`laboratory_refs` (`src/pivma/core/references.py:43`).

**Rationale**: o cargo vazio aparece com `people: []`, e o front mostra "Não
atribuído" só quando não houver ninguém (edge case da spec). Usar a regra de
efetividade da autorização evita mostrar uma pessoa que o resto da API não
reconhece no cargo, como o laboratório sem vínculo ativo. A data da
designação dos outros fica de fora: a spec pede quem ocupa o cargo, não o
histórico (Assumptions).

**Alternatives considered**: listar só os cargos ocupados. O front teria de
manter a lista de cargos para mostrar os vazios, e ela já existe no backend.

## R6. Fase atual e atividades em andamento

**Decision**: `open_runs` (`src/pivma/core/process_progress.py`) recebe os
processos da página, separa os `OPEN` e busca, numa consulta, as execuções `ActivityRun.status ==
'IN_PROGRESS'` desses processos, unidas a `ActivityInstance` e `Phase`, com
`Laboratory` em junção externa. A ordem é `Phase.order_index`,
`ActivityInstance.order_index`, nome do laboratório e `ActivityRun.id`, para
ser determinística. Cada linha vira uma execução aberta, com `started_at` e
`laboratory`, dentro da atividade dela em `phases[].activities[].open_runs`
([R10](#r10-atividades-de-cada-fase)). A fase atual de um
processo é a de maior `order_index` entre as linhas dele, inclusive as que o
usuário não vê, e fica nula quando ele não tem linha. O andamento e a
contagem da lista mostram só as linhas que o recorte libera. A lista chama a função com os processos `OPEN` da página e
usa só a fase e a contagem; o andamento chama com um processo e usa as linhas.
Processo fora de `OPEN` não entra na consulta: fase nula, lista vazia,
contagem zero.

**Rationale**: o processo não guarda a etapa (`ProcessInstance`, Spec 030).
A execução `IN_PROGRESS` é o que o motor abre em toda atividade
(`_init_first_activity`, `src/pivma/core/process_engine.py:765`, e as demais
criações de `ActivityRun`). A reabertura cria execução nova, então
`started_at` já é a data da reabertura. `WAIVED`, `SUPERSEDED`, `CANCELLED` e
`COMPLETED` ficam fora pelo filtro. O cancelamento do processo cancela as
execuções (`process_engine.py:488`), e o teste de FR-006 prova que o desvio
por estado não esconde nada que deveria aparecer. Processo `OPEN` sem
execução aberta existe: no template 1, depois que o último laboratório
confirma o recebimento sem problema, nenhuma atividade fica em andamento, e a
resposta traz fase nula, como pede FR-004.

**Alternatives considered**:

- `ActivityInstance.status == 'IN_PROGRESS'`: em atividade por laboratório,
  daria uma linha só, sem o laboratório (FR-005).
- `Phase.status == 'IN_PROGRESS'` para a fase atual: as fases 2 e 3 podem
  ficar em andamento juntas enquanto houver designação aberta. A regra da
  spec (FR-004) é a fase de maior ordem com atividade aberta.

## R7. O que fica fora da resposta

**Decision**: os schemas novos têm `extra='forbid'` e só os campos do
[contrato](contracts/process-progress.md). Nenhum campo vem de `FormValue`,
`FormInstance`, `StudySubstance`, `BlindSampleCode`, `SampleReceipt`,
`Decision`, `FieldReview`, `Artifact` nem `Task`. As rotas de atividade não
mudam (FR-008).

**Rationale**: FR-007 e a constituição III. O acompanhamento é só
informativo (Clarifications): não muda nenhuma regra de acesso. Nome de atividade e nome de
laboratório não identificam substância: a equipe liberou quem participa e em
que ponto o processo está. A presença de uma execução de recebimento por
laboratório mostra que o laboratório recebeu amostras, sem quantidade, código
ou conteúdo, e não dá acesso à execução de outro laboratório.

**Alternatives considered**: um campo `activity_type` ou `execution_scope`.
Ninguém pediu, e o front não precisa deles para a tela do print.

## R8. Auditoria

**Decision**: a lista e o andamento são leituras e não gravam `AuditEvent`
(FR-010). Não exigem `TrustedOrigin`, como os outros `GET`.

**Rationale**: constituição II pede evento para ação de negócio. Consulta não
é ação, e a linha do tempo de leitura não existe para outras rotas.

## R9. Recorte por cargo

**Decision**: `ProgressView` (`src/pivma/core/process_progress.py`) é a única
regra. Ela parte dos cargos efetivos do usuário no processo e do perfil de
plataforma:

| Quem | Pessoas | Execuções |
|---|---|---|
| Admin, BraCVAM, `group_manager`, `study_manager`, `sponsor` | todas | todas |
| `proponent`, `statistician`, `collaborator`, `sample_selection_group`, `regulatory_observer` | coordenação (`group_manager`, `study_manager`, `sponsor`, `proponent`) e o próprio cargo | atividade única |
| `participating_laboratory` | as anteriores e a equipe do próprio laboratório | atividade única e o próprio laboratório |
| `adhoc_evaluator`, `peer_reviewer` | coordenação sem o proponente; no próprio cargo, só a própria designação | atividade única |

Com mais de um cargo, vale a união. A própria designação aparece sempre.
`phases` e `current_phase` são iguais para todos.

**Rationale**:

- Grupo Gestor e Gerente do Estudo coordenam o estudo e recebem os dados dos
  laboratórios (RF045). O Grupo Gestor já vê toda execução de laboratório
  (`is_process_manager`). O Patrocinador ficou com a decisão de 2026-11-23.
- O isolamento por laboratório usa os laboratórios das designações
  `participating_laboratory`, a mesma base de `laboratory_run_visibility_clause`
  e de `effective_laboratory_ids`, para o andamento não divergir de `/tasks`
  nem da linha do tempo.
- O proponente não vê laboratório nem avaliador: a transferibilidade se
  avalia de forma independente do desenvolvedor, e a Spec 046 já esconde
  dele quem avaliou.
- O avaliador não vê o proponente nem outro avaliador, pela revisão cega do
  RF050.
- Os cargos de apoio precisam saber quem conduz o processo, sem mais.

**Alternatives considered**:

- Liberar a lista de pessoas a todos: quebra o isolamento por laboratório e
  a revisão cega.
- Usar `view_roles` das atividades para filtrar as execuções: misturaria o
  acesso ao conteúdo (Spec 030) com a posição no fluxo, e o Patrocinador não
  veria nada.
- Responder `403` a cargos sem recorte próprio: todo cargo do processo tem o
  que ver, ao menos a fase e a coordenação.

## R10. Atividades de cada fase

**Decision**: cada item de `phases` traz `activities`, as `ActivityInstance`
da fase na ordem do template, com `key`, `name`, `status` (`BLOCKED`,
`IN_PROGRESS`, `COMPLETED` ou `CANCELLED`, o valor gravado), `conditional` e
`open_runs`. `conditional` é verdadeiro quando o `activity_type` está em
`EVENT_OPENED_ACTIVITY_TYPES` (`src/pivma/core/process_engine.py`): a revisão
do retorno e a resolução de problemas no recebimento. A lista plana
`open_activities` sai; as mesmas execuções passam a vir em `open_runs`, dentro
da atividade. A lista de atividades e a situação são iguais para todos os
cargos; `open_runs` segue o recorte de R9.

**Rationale**: o RF030 pede as etapas concluídas, em andamento, pendentes e
futuras. Com só as execuções abertas, o front não via o que vem depois dentro
da fase e teria de cruzar a resposta com o template. A atividade guarda a
situação (`ActivityInstance.status`), então basta uma consulta. Nomes e
situação vêm do template e do motor, sem conteúdo nem autoria, no mesmo nível
de `current_phase`, que já é igual para todos. A marca `conditional` evita que
o front mostre como etapa certa uma atividade que só abre se algo der errado.
Manter `open_activities` ao lado das atividades repetiria as mesmas execuções
em dois lugares.

**Alternatives considered**:

- Manter `open_activities` e acrescentar `activities`: a mesma execução em
  dois campos.
- Calcular a situação da atividade por laboratório para o laboratório que
  olha: a situação deixaria de ser igual para todos, e o laboratório já vê a
  própria execução em `open_runs`.

## R11. Cargo ocupado

**Decision**: cada item de `roles` traz `occupied`, verdadeiro quando há
designação efetiva no cargo, vista ou não pelo usuário. `people` continua com
só quem o recorte libera.

**Rationale**: com o recorte, um cargo visível podia vir com `people: []`
estando ocupado. O laboratório participante via `lead_laboratory` vazio quando
o líder era de outro laboratório, e o front mostraria "Não atribuído". O
booleano não conta pessoas: com dois ou três laboratórios, uma contagem
indicaria quem é quem.

**Alternatives considered**:

- Uma contagem por cargo: identifica laboratórios.
- Esconder o cargo quando o usuário não vê ninguém nele: o laboratório
  deixaria de saber que há um líder.

## R12. O que fica para a matriz de acesso

A revisão de 2026-11-27 (`revisao-acompanhamento.md`) propõe uma matriz de
acesso central, declarada como dado, lida por `/progress`, `/tasks`, linha do
tempo e `/participants`, com testes gerados dela. Esta spec não a implementa.

**Decision**: a matriz vira uma spec própria, registrada numa issue. Esta spec
mantém `ProgressView` como a regra do andamento e corrige os pontos 3 e 5 da
revisão (R10, R11 e o filtro explícito de `deleted_at`).

**Rationale**:

- **Escopo**: a matriz reescreve a autorização de `/tasks`, a parte mais
  sensível do backend, e mexe na linha do tempo e em `/participants`. Numa PR
  de acompanhamento, uma regressão de sigilo ficaria escondida entre mudanças
  de outra natureza.
- **Formato antes das respostas**: o BraCVAM ainda não respondeu às perguntas
  de acesso. Se a resposta depender da fase ou da situação da atividade, o
  esquema cargo × atividade × nível não comporta, e a matriz teria de ser
  refeita. A própria revisão deixa aberta a decisão de resolver as concessões
  pela versão do template ou copiá-las e migrar.
- **Sem duplicar rotas**: a revisão sugere que `/tasks` ganhe um modo de
  acompanhamento. Com as atividades de cada fase em `/progress` (R10), esse
  modo entregaria as mesmas atividades com a situação por outra rota.
- **Troca local depois**: o recorte do andamento mora só em `ProgressView`.
  Quando a matriz existir, a classe passa a lê-la, sem mudar o contrato.
- **Front**: a matriz não muda o contrato. O front não ganha nem perde nada
  com ela nesta entrega.

**O que a matriz deve resolver**, para a issue:

- a divergência entre `/progress` e `/tasks`: o Patrocinador vê as execuções
  de todos os laboratórios no andamento e nenhuma tarefa em `/tasks`;
- os grupos fixos `FULL_VIEW_ROLES`, `COORDINATION_ROLES` e
  `BLIND_REVIEW_ROLES`, que pedem deploy a cada mudança;
- a linha do tempo (#84) usando a mesma regra, em vez de copiar a de
  `ProgressView`;
- o nível de resumo por tipo de atividade, montado por lista de campos
  permitidos, quando a execução nos laboratórios e a revisão por pares
  existirem (ponto 4 da revisão);
- a escolha entre resolver pela versão do template e migrar as concessões
  copiadas.

**Acúmulo de cargos**: a #85 limita a pessoa a um cargo ativo por processo. A
união em `ProgressView` continua correta com um cargo só e cobre Admin e
BraCVAM com cargo no processo, então o código fica. O teste
`test_avaliador_com_outro_cargo_ve_a_uniao` sai, porque descrevia o caso que a
#85 proíbe.

