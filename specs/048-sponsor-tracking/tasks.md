---

description: "Tarefas da Spec 048, acompanhamento do Patrocinador"
---

# Tasks: Acompanhamento do Patrocinador

**Input**: documentos de `specs/048-sponsor-tracking/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/sponsor-tracking.md](contracts/sponsor-tracking.md), [quickstart.md](quickstart.md)

**Tests**: obrigatórios (AGENTS.md, constituição V). Cada história começa pela
jornada, depois os testes focados, depois a implementação. Os testes da
história devem falhar antes da implementação dela.

**Organization**: as três histórias são P1. US1 e US2 compartilham o router e
a função que calcula a fase atual. US3 só acrescenta testes, porque o sigilo
sai do desenho dos schemas de US1 e US2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: história de origem (US1, US2, US3)

## Regras para quem implementa

- Reaproveite sem alterar: `process_cargos_scope` e
  `effective_assignment_clause` (`src/pivma/core/authorization.py`),
  `has_platform_wide_access`, `laboratory_refs`
  (`src/pivma/core/references.py`), `paginate_query` e `build_pagination`
  (`src/pivma/core/listing.py`), `http_error`.
- Nada de service, repositório ou helper público novo: as consultas ficam em
  funções privadas do router, como o plano define. A única função
  compartilhada pelas duas rotas é `_open_runs` (T004), porque a fase do
  cartão e a do detalhe precisam sair da mesma regra.
- Não mude `GET /processes`, `GET /processes/{id}`, `/participants`,
  `participant_read_scope` nem as rotas de atividade, amostras, recebimento,
  homologação, retorno e plano estatístico.
- Testes focados verificam o `code` do erro, não a mensagem. Montagem de
  estado: `planning_process`, `structure_process` e `designate`
  (`tests/factories/structure_approval_factory.py`), `grant_cargo`
  (`tests/factories/participant_factory.py`), `frozen_lab_process`, `waive`,
  `reopen`, `end_affiliation` (`tests/factories/laboratory_run_factory.py`).
  Não crie factory nova se uma destas resolver.
- A jornada usa só a API pública, com os passos de
  `tests/integration/journeys/sample_steps.py` (`study_team`,
  `open_sample_definition`, `complete_study_team`, `register_substance`,
  `approve_structure`, `designate`, `ok`).

---

## Phase 1: Setup

**Purpose**: o router vazio registrado na aplicação.

- [X] T001 Criar `src/pivma/routers/sponsor_tracking.py` com `router = APIRouter(prefix='/sponsor-tracking', tags=['Sponsor Tracking'])`, sem rotas, e registrá-lo com `app.include_router(sponsor_tracking.router)` em `src/pivma/__init__.py`, ao lado dos outros routers

---

## Phase 2: Foundational

**Purpose**: as regras que a lista e o detalhe usam: "designação efetiva de Patrocinador" e "execuções em andamento e fase atual".

- [X] T002 Em `src/pivma/routers/sponsor_tracking.py`, escrever a função privada `_sponsor_assignments(user_id)` que devolve `process_cargos_scope(user_id).with_only_columns(Assignment.process_instance_id).where(Assignment.role_key == 'sponsor')` (R2), usada no `IN` da lista, e `_sponsored_since(session, user_id, process_ids)`, que acrescenta `min(Assignment.assigned_at)` agrupado por processo (R3) e serve à lista e ao detalhe. `process_cargos_scope` seleciona só `role_key`, por isso o `with_only_columns`, como em `is_active_effective_proponent`. A função não aceita outro cargo como parâmetro. **Desvio na revisão**: as duas funções viraram `_sponsorships(user_id)`, uma subconsulta com `process_instance_id` e `min(assigned_at)` agrupada por processo. A lista faz `JOIN` com ela e o detalhe filtra pelo processo. Com duas consultas, uma revogação entre a página e as datas levava a `KeyError` (500)
- [X] T003 Em `src/pivma/schemas.py`, junto dos schemas de processo, criar `TrackingPhase` (`key: str`, `name: str`, `order: int`) com `model_config = ConfigDict(extra='forbid')`
- [X] T004 Em `src/pivma/routers/sponsor_tracking.py`, escrever duas funções privadas (R6): `_open_runs(session, process_ids)` faz uma consulta só, devolve `[]` sem consultar se `process_ids` estiver vazio, e busca as `ActivityRun` com `status == 'IN_PROGRESS'` desses processos, unidas a `ActivityInstance` e `Phase`, com junção externa a `Laboratory`, ordenadas por `Phase.order_index`, `ActivityInstance.order_index`, `Laboratory.name`, `ActivityRun.id`. Cada linha traz `process_instance_id`, chave e nome da atividade, chave, nome e `order_index` da fase, `ActivityRun.started_at` e o laboratório. `_current_phase(rows)` devolve o `TrackingPhase` da linha de maior `Phase.order_index`, ou `None` sem linhas. Quem chama passa só processos `OPEN`

**Checkpoint**: `poe lint` passa; a aplicação sobe com o router vazio.

---

## Phase 3: User Story 1 - Ver os processos que patrocino (Priority: P1) 🎯 MVP

**Goal**: `GET /sponsor-tracking/processes` lista os processos em que o usuário é Patrocinador, com `sponsored_since`, `current_phase` e `open_activity_count`.

**Independent Test**: designar o usuário como Patrocinador em dois processos e Colaborador em um terceiro; a lista traz só os dois primeiros, cada um com fase e quantidade de atividades.

### Jornada de US1

- [X] T005 [US1] Criar `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sponsor_tracking_journey.py` com a docstring de módulo (Spec 048; personas: Helena do BraCVAM, Paula Patrocinadora, o proponente; estado inicial comum; as três jornadas) e `test_patrocinadora_ve_so_os_processos_que_patrocina`: (1) dois processos chegam à Fase 2 por `open_sample_definition`; (2) Helena designa Paula `sponsor` no primeiro e `collaborator` no segundo; (3) Paula entra e chama `GET /sponsor-tracking/processes`: recebe só o primeiro, com `code`, `title`, `status == 'OPEN'`, `started_at`, `sponsored_since` igual ao `assigned_at` devolvido na designação, `current_phase.key == 'phase_2_role_assignment'` e `open_activity_count >= 1`; (4) Helena revoga a designação de Paula; (5) Paula consulta de novo e recebe `data == []`

### Testes focados de US1

Em `tests/api/routers/test_sponsor_tracking.py`, um teste por linha:

- [X] T006 [P] [US1] `test_lista_traz_campos_do_contrato`: o item tem exatamente as chaves `id, code, title, status, started_at, closed_at, sponsored_since, current_phase, open_activity_count`; `current_phase` tem exatamente `key, name, order`; o envelope tem `pagination`, `filters_applied == {}` e `sort == {'by': 'created_at', 'order': 'desc'}`
- [X] T007 [P] [US1] `test_lista_traz_fase_e_contagem_na_fase_2`: com `planning_process`, `current_phase == {'key': 'phase_2_role_assignment', 'name': 'Fase 2: Composição da Governança', 'order': <order_index da fase>}` e `open_activity_count` igual ao número de `ActivityRun` `IN_PROGRESS` do processo
- [X] T008 [P] [US1] `test_lista_conta_uma_execucao_por_laboratorio_na_fase_3`: com `structure_process(previous_version=True)`, `current_phase.key == 'phase_3_validation_execution'` e `open_activity_count` conta um `sample_receipt` por laboratório
- [X] T009 [P] [US1] `test_lista_sem_fase_para_processo_aberto_sem_atividade`: com `structure_process` e todas as execuções `IN_PROGRESS` marcadas `COMPLETED` na sessão (o estado do template 1 depois do último recebimento confirmado), o item vem com `status == 'OPEN'`, `current_phase is None` e `open_activity_count == 0`
- [X] T010 [P] [US1] `test_lista_exclui_processo_so_com_outro_cargo`: o usuário `group_manager` em um processo e `sponsor` em outro vê só o segundo
- [X] T011 [P] [US1] `test_lista_exclui_designacao_revogada`: com `revoked_at` preenchido, o processo some
- [X] T012 [P] [US1] `test_lista_exclui_convite_pendente`: um convite de `sponsor` ainda não aceito (`tests/factories/invite_factory.py`) não põe o processo na lista
- [X] T013 [P] [US1] `test_lista_exclui_processo_excluido`: depois de `delete_process`, o processo some
- [X] T014 [P] [US1] `test_lista_mostra_processo_uma_vez_com_dois_cargos`: Patrocinador e Proponente no mesmo processo aparece uma vez, com `total_items == 1`
- [X] T015 [P] [US1] `test_lista_inclui_processo_arquivado`: com `planning_process` e `status = 'ARCHIVED'`, `closed_at` e `closure_reason` gravados na sessão (ver Notes), o processo aparece, com `closed_at` preenchido, `current_phase is None` e `open_activity_count == 0`
- [X] T016 [P] [US1] `test_lista_vazia_para_admin_sem_designacao`: o usuário com acesso a toda a plataforma e sem designação de `sponsor` recebe `data == []` e `total_items == 0`
- [X] T017 [P] [US1] `test_lista_ordena_por_criacao_decrescente`: três processos patrocinados vêm do mais novo ao mais antigo
- [X] T018 [P] [US1] `test_lista_pagina`: com três processos e `per_page=2`, a página 1 traz dois itens com `has_next is True` e `total_pages == 2`; a página 2 traz um
- [X] T019 [P] [US1] `test_lista_recusa_per_page_fora_do_intervalo`: `per_page=0` e `per_page=101` respondem `422` (parametrizado)
- [X] T020 [P] [US1] `test_lista_exige_sessao`: sem cookie responde `401`

### Implementação de US1

- [X] T021 [US1] Em `src/pivma/schemas.py`, criar `SponsoredProcessSummary` (`id: UUID`, `code: str`, `title: str`, `status: ProcessLifecycle`, `started_at: datetime | None`, `closed_at: datetime | None`, `sponsored_since: datetime`, `current_phase: TrackingPhase | None`, `open_activity_count: int`) e `class SponsoredProcessListResponse(ListPage[SponsoredProcessSummary, NoFilters])`, como as outras listagens de `schemas.py`, com `model_config = ConfigDict(extra='forbid')` como em [data-model.md](data-model.md)
- [X] T022 [US1] Em `src/pivma/routers/sponsor_tracking.py`, criar `GET /processes` (`response_model=SponsoredProcessListResponse`, `page: PageQuery = 1`, `per_page: PerPageQuery = 20`, `CurrentUser`): (1) `paginate_query` sobre `select(ProcessInstance).where(ProcessInstance.id.in_(<_sponsor_assignments só com process_instance_id>))`, `order_by=(ProcessInstance.created_at.desc(), ProcessInstance.id.desc())`; (2) uma consulta `min(Assignment.assigned_at)` agrupada por processo, só para os ids da página (R3); (3) uma chamada a `_open_runs` com os ids dos processos `OPEN` da página, agrupando as linhas por processo para `_current_phase` e `len` (R3, R6); (4) envelope com `build_pagination`, `NoFilters()` e `SortApplied(by='created_at', order='desc')`. Página vazia não faz (2) nem (3). Nenhuma consulta por item. **Desvio na revisão**: (1) e (2) viraram uma consulta só, `select(ProcessInstance, since)` com `JOIN` em `_sponsorships`, paginada no router como em `routers/tasks.py`, porque `paginate_query` devolve só a primeira coluna (T002)
- [X] T023 [US1] Rodar `poetry run pytest tests/api/routers/test_sponsor_tracking.py -k lista` e o teste da jornada de US1; todos passam

**Checkpoint**: a lista funciona sozinha; o cartão mostra "patrocinador desde", fase atual e quantidade de atividades.

---

## Phase 4: User Story 2 - Acompanhar o andamento de um processo (Priority: P1)

**Goal**: `GET /sponsor-tracking/processes/{process_id}` devolve cabeçalho, pessoas por cargo, fase atual e atividades em andamento.

**Independent Test**: levar um processo da Fase 2 à Fase 3 e consultar o detalhe como Patrocinador em cada ponto.

### Jornada de US2

- [X] T024 [US2] Em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sponsor_tracking_journey.py`, `test_patrocinadora_acompanha_da_fase_2_a_fase_3`: (1) processo com dois laboratórios até a definição de amostras aberta (`study_team`, `open_sample_definition`) e equipe completa (`complete_study_team`, que designa o Patrocinador); (2) a Patrocinadora entra, abre o detalhe e vê o proponente em `roles`, o Grupo Gestor com a pessoa designada, nenhuma chave `email` no JSON, `current_phase.key == 'phase_2_role_assignment'` e `sample_definition` entre as `open_activities`, todas com `phase_key == 'phase_2_role_assignment'`; o cartão do processo na lista tem o mesmo `current_phase` e `open_activity_count == len(open_activities)`; (3) o Grupo de Seleção cadastra uma substância (`register_substance`) e conclui as amostras; Helena aprova a estrutura (`approve_structure`); (4) a Patrocinadora consulta de novo: `current_phase.key == 'phase_3_validation_execution'`, há um `sample_receipt` por laboratório, cada um com o `laboratory.name` do seu laboratório, e o cartão da lista continua igual ao detalhe; (5) entra como o Colaborador do mesmo processo e recebe `404` no detalhe

### Testes focados de US2

Em `tests/api/routers/test_sponsor_tracking.py`:

- [X] T025 [P] [US2] `test_detalhe_traz_um_cargo_por_participant_role`: `[r['role_key'] for r in roles] == list(get_args(ParticipantRole))`, e cargo sem ninguém vem com `people == []`
- [X] T026 [P] [US2] `test_detalhe_traz_proponente_sem_email`: o proponente aparece com `username` e `full_name`, e o JSON não contém a chave `email` nem o e-mail de ninguém
- [X] T027 [P] [US2] `test_detalhe_traz_laboratorio_so_em_cargo_de_laboratorio`: `participating_laboratory` e `lead_laboratory` têm `laboratory` com o nome certo; os demais cargos têm `laboratory is None`
- [X] T028 [P] [US2] `test_detalhe_traz_dois_patrocinadores_e_cada_um_ve_a_propria_data`: os dois aparecem em `sponsor`, ordenados por `assigned_at`, e o `sponsored_since` de cada um é a própria designação
- [X] T029 [P] [US2] `test_detalhe_omite_usuario_desativado`: o usuário com `deleted_at` preenchido some do cargo
- [X] T030 [P] [US2] `test_detalhe_omite_laboratorio_sem_vinculo_ativo`: depois de `end_affiliation`, a pessoa some de `participating_laboratory`
- [X] T031 [P] [US2] `test_detalhe_na_fase_2_lista_execucoes_abertas`: com `planning_process`, `current_phase` igual ao de T007, e cada item de `open_activities` corresponde a uma `ActivityRun` `IN_PROGRESS`, com `started_at` igual ao da execução
- [X] T032 [P] [US2] `test_detalhe_na_fase_3_traz_uma_execucao_por_laboratorio`: com `structure_process(previous_version=True)`, `current_phase.key == 'phase_3_validation_execution'` mesmo com execução da Fase 2 aberta, e os `sample_receipt` vêm um por laboratório, em ordem de nome do laboratório
- [X] T033 [P] [US2] `test_detalhe_omite_laboratorio_dispensado`: com `frozen_lab_process` e `waive` do laboratório 0, a execução `WAIVED` não aparece e as dos outros laboratórios sim
- [X] T034 [P] [US2] `test_detalhe_mostra_execucao_reaberta_com_data_da_reabertura`: depois de `reopen`, a atividade aparece uma vez para aquele laboratório, com `started_at` da execução nova
- [X] T035 [P] [US2] `test_detalhe_de_processo_aberto_sem_atividade`: no estado de T009, responde `200` com `status == 'OPEN'`, `current_phase is None` e `open_activities == []`
- [X] T036 [P] [US2] `test_detalhe_de_processo_encerrado_ou_arquivado_sem_fase[CLOSED]`: com `planning_process` e `status = 'CLOSED'`, `closed_at` e `closure_reason` gravados na sessão (ver Notes), o processo responde `200` com `current_phase is None`, `open_activities == []` e `closed_at` preenchido
- [X] T037 [P] [US2] `test_detalhe_de_processo_encerrado_ou_arquivado_sem_fase[ARCHIVED]`: mesmo resultado para `ARCHIVED`, montado como em T015 (T036 e T037 são um teste parametrizado por estado)
- [X] T038 [P] [US2] `test_detalhe_para_admin_e_bracvam_sem_designacao`: os dois perfis recebem `200` com `sponsored_since is None` (parametrizado por perfil)

Em `tests/api/routers/test_sponsor_tracking_security.py`:

- [X] T039 [P] [US2] `test_detalhe_responde_404_a_outro_cargo`: parametrizado por todo `ParticipantRole` exceto `sponsor`; cada um recebe `404` com `code == 'not_found'`
- [X] T040 [P] [US2] `test_detalhe_responde_404_a_patrocinador_revogado`
- [X] T041 [P] [US2] `test_detalhe_responde_404_igual_a_processo_inexistente`: o corpo da resposta para um processo alheio e para um UUID aleatório é idêntico
- [X] T042 [P] [US2] `test_detalhe_responde_404_a_processo_excluido`: depois de `delete_process`, que deixa o processo `CANCELLED`
- [X] T043 [P] [US2] `test_detalhe_recusa_id_que_nao_e_uuid`: `422`
- [X] T044 [P] [US2] `test_detalhe_exige_sessao`: `401`
- [X] T045 [P] [US2] `test_consultas_nao_gravam_evento`: o número de `AuditEvent` do processo é o mesmo antes e depois de chamar a lista e o detalhe (FR-010)

### Implementação de US2

- [X] T046 [US2] Em `src/pivma/schemas.py`, criar `TrackingPerson` (`user: UserRef`, `laboratory: LaboratoryRef | None`), `TrackingRole` (`role_key: ParticipantRole`, `people: list[TrackingPerson]`), `TrackingActivity` (`key: str`, `name: str`, `phase_key: str`, `started_at: datetime`, `laboratory: LaboratoryRef | None`) e `SponsorTrackingDetail` (`id`, `code`, `title`, `status`, `started_at`, `closed_at` como em `SponsoredProcessSummary`, `sponsored_since: datetime | None`, `current_phase: TrackingPhase | None`, `roles: list[TrackingRole]`, `open_activities: list[TrackingActivity]`), todos com `extra='forbid'`
- [X] T047 [US2] Em `src/pivma/routers/sponsor_tracking.py`, criar `GET /processes/{process_id}` (`response_model=SponsorTrackingDetail`): carregar o processo; se ele não existir, `http_error(404, 'Processo não encontrado.')`; calcular `sponsored_since` com `min(assigned_at)` de `_sponsor_assignments` para o processo; se for nulo e `has_platform_wide_access` for falso, o mesmo `404` (R4). `has_platform_wide_access` só roda quando a pessoa não é Patrocinadora
- [X] T048 [US2] No mesmo arquivo, função privada que monta `roles` (R5): uma consulta de `Assignment` + `User` do processo com `revoked_at` nulo, `Assignment.deleted_at` nulo, `User.deleted_at` nulo e `effective_assignment_clause()`, ordenada por `assigned_at`, `id`; laboratórios resolvidos por `laboratory_refs`; uma entrada por `get_args(ParticipantRole)` na ordem do `Literal`
- [X] T049 [US2] No mesmo arquivo, montar `open_activities` e `current_phase` com `_open_runs([process.id])` e `_current_phase` (T004) quando `status == 'OPEN'`; fora de `OPEN`, `None` e `[]` sem consultar
- [X] T050 [US2] Rodar `poetry run pytest tests/api/routers/test_sponsor_tracking.py tests/api/routers/test_sponsor_tracking_security.py` e a jornada de US2; todos passam

**Checkpoint**: o detalhe preenche proponente, fase e atividades da tela, e a fase do cartão bate com a do detalhe.

---

## Phase 5: User Story 3 - Acompanhar sem ver dados internos do estudo (Priority: P1)

**Goal**: provar que a lista e o detalhe não carregam dados internos e que as rotas de dados internos continuam fechadas ao Patrocinador.

**Independent Test**: com substâncias, códigos cegos e formulário enviado no processo, procurar esses valores nas respostas.

### Jornada de US3

- [X] T051 [US3] Em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sponsor_tracking_journey.py`, `test_patrocinadora_acompanha_sem_ver_o_estudo`: (1) processo na Fase 3 como na jornada de US2, com duas substâncias de `chemical_name` e `cas_number` conhecidos; (2) a Patrocinadora chama a lista e o detalhe; o JSON das duas respostas não contém nenhum `chemical_name`, `cas_number`, código cego (`substance['blind_codes']`), nome do arquivo SDS nem o texto enviado em `submission_values`; (3) ela chama `GET /processes/{id}/samples` e o formulário de `statistical_plan` e recebe `403` ou `404`, sem nenhum desses valores no corpo

### Testes focados de US3

Em `tests/api/routers/test_sponsor_tracking_security.py`:

- [X] T052 [P] [US3] `test_detalhe_tem_so_as_chaves_do_contrato`: as chaves do topo, de cada `roles[]`, `people[]`, `current_phase` e `open_activities[]` são exatamente as de [data-model.md](data-model.md). Um campo novo quebra o teste e obriga a revisar o sigilo
- [X] T053 [P] [US3] `test_detalhe_nao_contem_identidade_da_substancia`: com `structure_process`, o JSON não contém `ctx.substance['chemical_name']`, o CAS nem os códigos cegos
- [X] T054 [P] [US3] `test_rotas_de_leitura_internas_continuam_fechadas_ao_patrocinador`: com `structure_process` e o Patrocinador designado, parametrizado por `GET /processes/{id}/samples`, `/samples/labels`, `/sample-receipt/vials`, `/sample-receipt/nonconformities`, `/structure-approval`, `/activities/sample_definition/form` e `/activities/statistical_plan/form`; cada uma responde `403` ou `404` e o corpo não contém `ctx.substance['chemical_name']`. Nenhuma rota muda nesta feature. Em `structure_process`, `/return-review` poderia responder `404` mesmo sem a checagem de acesso, pois não há retorno pendente. `test_get_return_review_404_for_sponsor` (`tests/api/routers/test_return_review.py`, Spec 046) verifica a recusa com um retorno aberto.
- [X] T055 [P] [US3] `test_acoes_de_execucao_continuam_fechadas_ao_patrocinador`: com `frozen_lab_process` e o Patrocinador designado, `POST /processes/{id}/phases/phase_execution/laboratory-waivers` e `POST /processes/{id}/activities/receipt/laboratories/{laboratory_id}/reopen` (fase e atividade do template de `frozen_lab_process`) respondem `403` ou `404`, e a execução do laboratório mantém o status de antes (parametrizado)

### Implementação de US3

Sem código novo. Se T052 a T055 falharem, corrija os schemas de T003, T021 e T046, não as rotas internas.

- [X] T056 [US3] Rodar `poetry run pytest tests/api/routers/test_sponsor_tracking_security.py` e a jornada de US3; todos passam

**Checkpoint**: sigilo provado com dados reais no processo.

---

## Phase 6: Polish & Cross-Cutting Concerns

Use `stop-slop` nas páginas do manual. Descreva o estado atual, sem histórico.

- [X] T057 [P] Criar `manual/guias/acompanhar-como-patrocinador.md`: as duas rotas; o cartão da lista (fase atual e quantidade de atividades em andamento); o que o Patrocinador vê no detalhe (cargos, fase atual, atividades em andamento, uma por laboratório na Fase 3) e o que não vê (FR-007); que a tela é só informativa e não muda o acesso às atividades; o `404` para quem não é Patrocinador; fase vazia em processo aberto sem atividade, encerrado ou arquivado. Adicionar a página ao `nav` de `mkdocs.yml`, na seção de guias
- [X] T058 [P] Em `manual/referencia/perfis-permissoes-cargos.md`, na linha ou seção do cargo `sponsor`, dizer que ele acompanha os processos pelas rotas `/sponsor-tracking` e continua sem acesso às atividades, com link para o guia
- [X] T059 [P] Em `manual/referencia/listagens-e-referencias.md`, registrar `GET /sponsor-tracking/processes` no envelope padrão, sem filtros, com ordem `created_at` decrescente e incluindo processos arquivados
- [X] T060 [P] Em `manual/explicacao/escopo.md`, incluir o acompanhamento do Patrocinador no que está entregue
- [X] T061 Rodar `poe lint`, `poe test` e `poe docs-build`; os três passam. Informar só o que de fato rodou

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)** → **Foundational (T002 a T004)** → histórias.
- **US1 (Phase 3)**: depende de T002 a T004.
- **US2 (Phase 4)**: depende de T002 a T004 e de T021, porque `SponsorTrackingDetail` repete os campos de `SponsoredProcessSummary` e a jornada compara o cartão com o detalhe. Os testes de US2 podem ser escritos junto com US1.
- **US3 (Phase 5)**: depende de US1 e US2, porque testa as respostas das duas rotas.
- **Polish (Phase 6)**: depois das três histórias.

### Within Each User Story

- Jornada → testes focados → implementação → execução dos testes.
- Os testes de cada história rodam vermelhos antes da implementação dela.
- T003 vem antes de T004. T046 vem antes de T047; T048 e T049 dependem de T047 (mesmo arquivo, mesma rota).

### Parallel Opportunities

- T006 a T020 ficam no mesmo arquivo, mas são funções independentes: o [P] vale para escrever, não para editar o arquivo ao mesmo tempo. Na prática, uma pessoa escreve os testes de um arquivo em sequência.
- `tests/api/routers/test_sponsor_tracking.py` (T025 a T038) e `tests/api/routers/test_sponsor_tracking_security.py` (T039 a T045) podem ser escritos em paralelo.
- T057 a T060 tocam arquivos diferentes e podem andar em paralelo.

## Parallel Example: User Story 2

```bash
# Duas pessoas, arquivos diferentes:
Task: "T025 a T038 em tests/api/routers/test_sponsor_tracking.py"
Task: "T039 a T045 em tests/api/routers/test_sponsor_tracking_security.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 a T004.
2. US1 (T005 a T023). Para aqui e valida: o front já lista os processos com "patrocinador desde", fase atual e quantidade de atividades.

### Incremental Delivery

1. US1 → lista no ar.
2. US2 → detalhe com proponente, fase e atividades; a tela do print fica completa.
3. US3 → prova de sigilo, sem código novo.
4. Manual e verificação final na mesma entrega (constituição VII).

## Cobertura dos requisitos

| Requisito | Tarefas |
|---|---|
| FR-001 | T005 a T009, T021, T022 |
| FR-002 | T010 a T020 |
| FR-003 | T024 a T030, T048 |
| FR-004 | T004, T007 a T009, T024, T031, T032, T035, T049 |
| FR-005 | T004, T024, T031 a T034, T049 |
| FR-006 | T015, T036, T037, T049 |
| FR-007 | T026, T051 a T053 |
| FR-008 | T051, T054, T055 |
| FR-009 | T024, T038 a T044, T047 |
| FR-010 | T045 |
| FR-011 | T057 a T060 |
| SC-002 | T009, T024, T035 |
| SC-003 | T005, T006, T022 |
| SC-004 | T051, T053 |
| SC-005 | T054, T055 |

## Notes

- Concorrência não se aplica: as rotas só leem.
- Teste de quantidade de consultas fica de fora. SC-003 conta chamadas do front, provadas por T005 e T006, que leem fase e contagem direto da lista. T022 chama `_open_runs` uma vez por página, com todos os ids, e a revisão confere isso.
- Hoje o processo só fica `CLOSED` na Fase 1, pela reprovação na triagem ou pela desistência no retorno, antes de existir Patrocinador. O arquivamento exige `CLOSED` ou `CANCELLED`, e o processo `CANCELLED` já está excluído. Pela API, então, não há processo encerrado ou arquivado com Patrocinador. T015, T036 e T037 montam esse estado na sessão para provar a regra `status != 'OPEN'` (FR-006), que protege o caminho quando o encerramento depois da Fase 3 existir.
- `CANCELLED` sem exclusão não existe hoje (`delete_process` é o único caminho), por isso não há teste de `200` para `CANCELLED`. A regra `status != 'OPEN'` de T022 e T049 cobre o caso se ele surgir.
- FR-008 aceita `403` ou `404` porque cada rota interna já escolhe um dos dois hoje, e esta feature não as muda. O teste prova a recusa e a ausência de dado interno, não o código de cada rota.
- Commit ao fim de cada fase, só quando o usuário pedir.
