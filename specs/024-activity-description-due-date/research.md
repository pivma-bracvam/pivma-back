# Phase 0 Research: Prazo Real (due_date) das Atividades

Nenhum `NEEDS CLARIFICATION` restou no `spec.md` — as três decisões de
escopo já foram resolvidas em `/speckit-clarify` (sem descrição, sem
backfill, identificadores técnicos em inglês). Este documento cobre as
decisões técnicas necessárias para a Fase 1, todas derivadas do código já
existente, sem alternativas externas a avaliar.

## 1. Onde calcular e persistir `due_date`

**Decision**: Calcular `due_date` no momento da criação da `Task`, nos
**quatro** pontos do motor de processos que criam `Task` hoje —
`_init_first_activity` (primeira atividade do processo), `_activate_activity`
(atividade desbloqueada por dependência, motor genérico da Spec 017) e mais
dois caminhos legados, anteriores à Spec 017, que resolvem uma atividade pela
chave em vez do motor genérico: `_unblock_triage_activity`
(`proposal_submission` → `triage_evaluation`, usado por toda submissão sem
avaliação por IA pendente) e `_open_new_submission_run` (reabertura de
`proposal_submission` para retrabalho, usado por diligência de triagem e pelo
retorno automático da pré-avaliação por IA). Persistir o valor calculado em
`Task.due_date` ao inserir cada linha.

**Rationale**: A validação manual (T010) contra a API real revelou que a
suposição inicial — "só dois pontos criam `Task`" — estava errada:
`_unblock_triage_activity` cria a `Task` de `triage_evaluation` **sem passar
por `_activate_activity`**, e é o caminho usado por 100% dos processos reais
hoje (todos os 5 templates oficiais dependem dele para desbloquear a
triagem). Sem corrigir os quatro pontos, o card mais comum do kanban
(`triage_evaluation`) continuaria com `due_date` sempre nulo, apesar de
declarar `sla_hours=72` em todo template oficial — o teste unitário inicial
(baseado num template sintético só com o motor genérico) não pegou essa
lacuna; só pegou ao trocar para o template oficial `validated_method_dossier`
e exercitar o fluxo real de submissão. `_template_activity_data` (novo
helper) busca `sla_hours` da mesma fonte (`template_version.definition_payload`)
para os dois caminhos legados, que não recebem `a_data` como parâmetro.

**Alternatives considered**:
- Calcular sob demanda a cada leitura (como `classify_kanban_column` já faz
  hoje) e só expor via um campo computado na resposta: rejeitado porque é
  exatamente o comportamento atual que gera a lacuna — nenhum outro
  consumidor (notificação futura, relatório) teria acesso a um valor
  persistido, só quem já consulta o kanban.
- Um job/rotina assíncrona separada para preencher `due_date` depois da
  criação da `Task`: rejeitado por complexidade desnecessária para o escopo
  básico desta spec — o valor já é conhecido de forma síncrona e determinística
  no momento da criação, não depende de nada externo.

## 2. Fórmula de cálculo e consistência com a classificação do kanban (FR-003)

**Decision**: Reaproveitar literalmente a mesma fórmula já usada em
`classify_kanban_column` — `due_date = run_started_at + timedelta(hours=sla_hours)`
— extraída (ou reutilizada diretamente) como a única fonte de verdade para os
dois consumidores: o cálculo ao vivo da coluna do kanban continua funcionando
como hoje (não depende de `Task`), e o valor persistido em `Task.due_date` usa
os mesmos dois insumos (`run_started_at` do `ActivityRun` recém-criado,
`sla_hours` da definição da atividade). Como os dois usam a mesma fórmula e os
mesmos insumos, a consistência exigida por FR-003 é garantida por construção,
sem acoplar `Task` e `classify_kanban_column` em tempo de execução.

**Rationale**: `classify_kanban_column` é função pura e não depende de
`Task` (confirmado em `process_engine.py`) — os dois cálculos já são
estruturalmente independentes hoje. Bastava garantir que usam a mesma
fórmula; não há necessidade (nem benefício) de fazer um consumir o outro.

**Alternatives considered**:
- Fazer `classify_kanban_column` ler `Task.due_date` em vez de recalcular:
  rejeitado — a montagem do card do kanban hoje não carrega `Task` (usa
  `ActivityInstance`/`ActivityRun` diretamente), então acoplar essa leitura
  introduziria uma junção nova só para reproduzir um valor que já é derivável
  dos mesmos dois campos que o kanban já tem em mãos.

## 3. Migração de schema

**Decision**: Nenhuma migração Alembic nova é necessária — `Task.due_date`
já existe na tabela `tasks` (`models.py:757`), sempre `NULL` até hoje. A
mudança é só de comportamento (passar a escrever o campo), não de estrutura.

**Rationale**: Confirmado por leitura direta do modelo e por
`grep` não encontrar nenhuma atribuição a `.due_date` em todo `src/pivma/`
antes desta spec.

## 4. Contrato de API

**Decision**: `TaskSummary` (`schemas.py`) já declara
`due_date: datetime | None = None` — `GET /tasks` passa a retornar um valor
não nulo quando a atividade correspondente declara `sla_hours`, sem nenhuma
mudança de schema. `TaskDetail`, por outro lado, **não** declara `due_date`
hoje (confirmado em `schemas.py` e em `get_task_detail`,
`routers/tasks.py`) — é preciso acrescentar o campo a esse schema e ao
retorno de `GET /tasks/{id}` para que a User Story 1 (consultar o prazo de
*uma* tarefa) valha tanto na listagem quanto no detalhe. Isso é uma extensão
de um endpoint já existente (novo campo na resposta), não um endpoint novo.

**Rationale**: Sem essa correção, `GET /tasks/{id}` — o endpoint mais natural
para "a pessoa responsável por uma tarefa consulta seu prazo" (User Story 1)
— continuaria sem expor o dado, mesmo depois de `Task.due_date` passar a ser
escrito no banco. Consistente com a Regra 4 do `AGENTS.md` (nenhum endpoint
*novo* facilitador) — aqui só um campo é adicionado a um endpoint que já
existe, mesmo padrão já usado pelo projeto (ex.: `activity_type` foi
acrescentado a respostas existentes na Spec 017 sem criar rota nova).

## 5. Cobertura de demo (AGENTS.md, critério de conclusão)

**Decision**: Estender `demos/kanban/index.html` (já consome a API real, já
exibe `sla_hours`/`run_started_at` por card) para também exibir a data-limite
concreta, buscando-a via `GET /tasks`. `scripts/seeds/seed_kanban.py` **não
precisa mudar**: os cinco templates oficiais já declaram `sla_hours` em
`proposal_submission` (168h) e `triage_evaluation` (72h), e o seed já
instancia centenas de processos passando por essas atividades
(`instantiate_process`/`submit_proposal_form`/`execute_triage_decision`) — a
massa qualificada para observar `due_date` já existe hoje.

**Rationale**: A capacidade entregue por esta spec é uma extensão pontual do
módulo de Atividades/Kanban já demonstrado — não é um módulo novo pelo
critério do `AGENTS.md` (§1), então não exige uma nova página/índice de demo,
só a atualização da existente. E como o seed já cobre atividades com
`sla_hours`, o esforço de demo fica restrito ao front-end estático.
