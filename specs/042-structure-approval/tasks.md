---

description: "Tarefas da Spec 042: homologação da estrutura do estudo"
---

# Tasks: Homologação da estrutura do estudo

**Input**: Design documents from `specs/042-structure-approval/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, quickstart.md

**Tests**: obrigatórios (AGENTS.md, constituição V, `testing-methodology`).
- Cada história começa pela jornada. Depois vêm os testes focados, um por
  comportamento observável, e só então a implementação.
- As três jornadas ficam no mesmo módulo,
  `tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py`,
  uma função por história. A docstring do módulo descreve personas, estado
  inicial e as três jornadas em prosa, no formato de
  `etapa_3_execucao_validacao/test_sample_receipt_journey.py`. Cada passo
  numerado no comentário verifica o que o ator vê naquele momento: tarefas
  em `GET /tasks`, painel, linha do tempo (`GET /processes/{id}/timeline`).
  Troca de ator explícita por logout/login públicos. O preparo usa
  `bootstrap_fresh_deploy`, cadastro público, concessão de perfil pela API
  de RBAC e cadastro de laboratórios e vínculos pela API institucional.
- A jornada não consulta o banco. O histórico de execuções aparece em
  `GET /tasks` (`activity_run_number` e `status` de cada tarefa) e na linha
  do tempo.
- Nos testes focados, confira o `code` do erro, não a mensagem. Toda recusa
  confere também que nada mudou: nenhuma `Decision` nova, homologação no
  mesmo status e execução, `sample_receipt` sem execução.
- Usuário BraCVAM: fixture `bracvam_user` (perfil `bracvam`, que dá o cargo
  global). Admin: fixture `ai_eval_admin`. Usuário sem cargo: fixture
  `user`. Escritas pelo `client` levam `ORIGIN = {'Origin': 'https://testserver'}`.
- Nomes de teste descrevem o objetivo e o desfecho
  (`test_reprovar_ponto_reabre_a_atividade_com_o_motivo`).

**Regras de código** (`karpathy-guidelines`):
- Nada de lista fixa das nove chaves: os pontos são as `ActivityDependency`
  da homologação (research R2).
- Reaproveitar `_lock_process`, `ensure_process_mutable`,
  `require_activity_access`, `_activate_activity`, `_complete_activity_run`
  e `_advance_dependent_activities`. O código novo não entra em
  `process_engine.py` (plan, Structure Decision).
- Serviço recebe `session` e o ator e devolve dados; o router monta os
  esquemas e converte erros de domínio, como `routers/sample_receipt.py`.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Rodar `poe lint` e `poetry run pytest -q` na branch antes de qualquer mudança e anotar em `specs/042-structure-approval/tasks.md` (seção Notes) as falhas que já existiam, para não atribuí-las a esta feature

---

## Phase 2: Foundational

**Purpose**: coluna nova, templates e fábricas, usados por todas as histórias.

**⚠️ CRITICAL**: nenhuma história começa antes desta fase.

### Testes da fundação

- [X] T002 [P] Teste de migração em `tests/integration/migrations/test_decision_rejected_points_migration.py`, no padrão de `test_collection_template_migration.py` (`PREVIOUS = 'e8a4c2f61b37'`):
  - o upgrade cria `decisions.rejected_points` do tipo JSONB, "anulável";
  - uma decisão de triagem gravada antes do upgrade fica com `rejected_points` nulo;
  - o downgrade remove a coluna e preserva as linhas.
- [X] T003 [P] Atualizar `tests/integration/bootstrap/test_template_phase_2.py`:
  - `NEW_VERSIONS` passa a `5, 5, 5, 7, 5` (01, 02, 03, 04, 05);
  - teste novo: nos cinco templates, a última atividade da fase 2 é `structure_approval`, com `activity_type: "structure_approval"`, `assigned_role: "bracvam"`, `access` `edit: ["bracvam"]` e `view: []`, e `dependencies` com exatamente as nove atividades da fase 2, cada uma com `required_status: "COMPLETED"` e `condition_type: "ACTIVITY_COMPLETED"`;
  - teste novo: o processo instanciado da versão mais recente tem `structure_approval` em `BLOCKED`, sem execução, com `edit_roles == ['bracvam']` e `view_roles == ['admin', 'bracvam']`.
- [X] T004 [P] Atualizar `tests/integration/bootstrap/test_template_phase_3.py`: `sample_receipt` depende só de `structure_approval` (hoje confere `sample_definition`).
- [X] T005 [P] Atualizar `tests/api/routers/test_activity_type_extension.py`: o dicionário da fase 2 inclui `'structure_approval': 'structure_approval'`, e o teste do padrão `form` trata `structure_approval` como tipo declarado.

### Implementação da fundação

- [X] T006 Em `src/pivma/core/database/models.py`, `Decision.rejected_points: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True, default=None)`, depois de `decided_at` (data-model.md, "Mudança de esquema").
- [X] T007 Migração `migrations/versions/<rev>_decision_rejected_points.py` com `down_revision = 'e8a4c2f61b37'`: `op.add_column('decisions', sa.Column('rejected_points', postgresql.JSONB(), nullable=True))`; downgrade com `op.drop_column`; docstring citando a Spec 042 e a research R5. Fazer T002 passar.
- [X] T008 Nos cinco arquivos `src/pivma/templates_data/0[1-5]_*.yaml`, com blocos idênticos:
  - subir `process_template.version` (01, 02, 03 e 05 de 4 para 5; 04 de 6 para 7);
  - acrescentar, depois de `sample_definition`, a atividade de data-model.md ("Template de processo"): `key: "structure_approval"`, `name: "Homologação da Estrutura do Estudo"`, `order_index: 10`, `assigned_role: "bracvam"`, `access` `edit: ["bracvam"]` e `view: []`, `activity_type: "structure_approval"` e as nove dependências `ACTIVITY_COMPLETED`, com comentário citando a Spec 042;
  - em `sample_receipt`, trocar a dependência `sample_definition` por `structure_approval` e ajustar o comentário da fase 3.
  Fazer T003, T004 e T005 passarem.
- [X] T009 [P] Atualizar `src/pivma/templates_data/README.md` (seção 1.1): a fase 2 termina na homologação do BraCVAM, que depende das nove atividades; o recebimento da fase 3 depende da homologação; `test_template_phase_2.py` compara as cópias.
- [X] T010 [P] Em `tests/factories/sample_receipt_factory.py`:
  - `_phase_3()` troca a dependência de `sample_receipt` de volta para `sample_definition`, com comentário citando a research R10 (o template de teste não tem a Etapa 2 completa);
  - renomear `_attach_sds` para `attach_sds` e ajustar as chamadas, para a fábrica de T011 reaproveitar.
  Rodar `tests/api/routers/test_sample_receipt_*.py`, `test_sample_nonconformity_*.py` e `test_collection_template_*.py` e confirmar que continuam verdes.
- [X] T011 Fábrica `tests/factories/structure_approval_factory.py` com `structure_process(client, session, bracvam, *, lab_count=2, collection_template_id=None, complete_samples=True, previous_version=False)`:
  - carrega os templates (`bootstrap_all_templates`) e cria proponente, Grupo Gestor, Grupo de Seleção, patrocinador, estatístico, colaborador, avaliador ad hoc e um usuário vinculado a cada laboratório novo (`new_laboratory`, `lab_user` de `sample_factory.py`);
  - `previous_version_payload()`: o YAML real de `pre_validated_method` sem `structure_approval`, com `sample_receipt` dependendo de `sample_definition` e `version` um número abaixo, publicado por `sync_template_from_dict`. É o template que os processos criados antes desta feature usam (FR-003);
  - cria o processo `pre_validated_method` por `instantiate_process` com o proponente como criador, na versão mais recente ou, com `previous_version`, na de `previous_version_payload()`; depois envia a submissão e aprova a triagem pela API, como `_process_in_triage` de `test_triage_authorization.py`;
  - designa os oito cargos por `participant_service.create_assignment` (o primeiro laboratório também como `lead_laboratory`), o que conclui as atribuições;
  - cadastra uma substância por `sample_service.create_substance`, anexa a SDS com `attach_sds` e, com `complete_samples`, conclui as amostras;
  - devolve um `SimpleNamespace` com `process_id`, os usuários, `laboratories` e `lab_users`;
  - helpers `panel(client, process_id)` e `decide(client, process_id, **body)` que chamam as rotas de contracts/http-api.md com `ORIGIN`.
  Resultado verificável: com `complete_samples=True`, as nove atividades ficam `COMPLETED` e `structure_approval` fica `IN_PROGRESS` com uma tarefa `READY` do cargo `bracvam`; com `previous_version=True`, o recebimento já abre na conclusão das amostras. Conferir com os testes de fumaça e de versão anterior de T013.

**Checkpoint**: fundação pronta; as jornadas existentes da Etapa 3 e do template de coleta ficam vermelhas até T024.

---

## Phase 3: User Story 1 - BraCVAM homologa a estrutura e libera a Etapa 3 (Priority: P1) 🎯 MVP

**Goal**: painel da homologação e aprovação que abre o recebimento por laboratório.

**Independent Test**: jornada de T012 verde a partir de um ambiente recém-provisionado.

### Tests for User Story 1

- [X] T012 [US1] Jornada `test_bracvam_homologa_a_estrutura_e_libera_o_recebimento` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py`, com a docstring do módulo (Spec 042, US1 a US3; personas: Helena, BraCVAM; Marcos, Grupo Gestor; Ricardo, Grupo de Seleção; Thiago, laboratório participante). Passos, todos pela API:
  1. o proponente, Marcos e Helena montam a equipe completa e Ricardo conclui as amostras (helpers de T022);
  2. Helena vê a tarefa `READY` "Homologação da Estrutura do Estudo" em `GET /tasks`; Thiago não vê tarefa de recebimento;
  3. Helena abre o painel: nove pontos `COMPLETED`, `pending` vazio, contagens das amostras, sem nome químico nem CAS;
  4. Helena aprova com justificativa: `200`, `status` `COMPLETED`;
  5. Thiago vê a tarefa `READY` de recebimento do seu laboratório;
  6. a linha do tempo mostra `STRUCTURE_APPROVED` com a justificativa e a autora; o painel mostra a decisão.
- [X] T013 [P] [US1] Contrato do painel e da aprovação em `tests/api/routers/test_structure_approval_router.py`, um teste por item, usando a fábrica de T011:
  - fumaça da fábrica: nove atividades `COMPLETED`, homologação `IN_PROGRESS` com tarefa `READY` do cargo `bracvam`;
  - painel com a homologação aberta: `status` `IN_PROGRESS`, `run_number` 1, `points` na ordem de `order_index`, `designations` só nos pontos `role_assignment` (com `user`, `laboratory` e `is_effective`), `samples` só em `sample_definition` com `substance_count`, `laboratory_count` e `code_count`;
  - painel antes da abertura (`complete_samples=False`): `status` `BLOCKED`, `run_number` nulo;
  - aprovação: `200` com `decision_id`, `outcome` `APPROVED`, `status` `COMPLETED`, `reopened` vazio;
  - depois da aprovação: fase 2 `COMPLETED`, uma execução `IN_PROGRESS` de `sample_receipt` por laboratório com códigos, tarefa da homologação `COMPLETED`;
  - `Decision` gravada com `decision_type` `STRUCTURE_APPROVAL`, `justification`, `decided_by` e `rejected_points` nulo;
  - evento `STRUCTURE_APPROVED` na execução da homologação, com `decision_id` e `justification`;
  - painel depois da aprovação lista a decisão com `decided_by` e `decided_at`;
  - segunda aprovação: `409 invalid_transition`, uma única `Decision`;
  - processo da versão anterior (`previous_version=True`, FR-003): não tem `structure_approval`, e a conclusão das amostras abre uma execução `IN_PROGRESS` de `sample_receipt` por laboratório.
- [X] T014 [P] [US1] Segurança em `tests/api/routers/test_structure_approval_security.py`, um teste por linha:
  - sem sessão: `401 not_authenticated` no painel e na decisão;
  - usuário sem vínculo com o processo: `404 not_found` no painel e na decisão;
  - Grupo Gestor do processo (vê o processo, não vê a homologação): `404` no painel e na decisão;
  - laboratório participante do processo: `404` no painel e na decisão (o painel lista designações de outros laboratórios);
  - Grupo de Seleção de Amostras do processo: `404` no painel e na decisão;
  - Admin: painel `200`, decisão `403 forbidden`;
  - BraCVAM com conflito de interesse vigente (`ConflictInterestDeclarationFactory`): decisão `403 forbidden`, nada muda;
  - decisão sem `Origin` confiável: `403 invalid_origin`;
  - processo sem a atividade (`previous_version=True`): `404` no painel e na decisão;
  - cegamento (SC-005): o JSON do painel não contém o nome químico, o CAS, o id da SDS nem nenhum código cego do processo (buscar cada valor no texto da resposta).
- [X] T015 [P] [US1] Trava do template de coleta em `tests/api/routers/test_collection_template_lock.py`, com processo da fábrica de T011 vinculado (`collection_template_id`):
  - concluir as amostras não trava: incluir coluna responde `201`;
  - aprovar a homologação trava: incluir coluna responde `409 template_locked`;
  - os testes existentes com `linked_process` (template de teste, Etapa 3 abre na conclusão das amostras) continuam verdes sem mudança.
- [X] T016 [P] [US1] Concorrência entre aprovação e mudança estrutural em `tests/api/routers/test_collection_template_concurrency.py`, espelhando os dois testes de ordem que já existem nele (`test_column_waits_for_sample_completion_and_is_refused` e `test_sample_completion_waits_for_structural_change`):
  - a inclusão de coluna espera a aprovação e é recusada com `409 template_locked`;
  - a aprovação espera a inclusão de coluna em andamento; a coluna fica criada e o template termina travado.

### Implementation for User Story 1

- [X] T017 [US1] Esquemas em `src/pivma/schemas.py`, conforme contracts/http-api.md: `StructurePending` (`code`, `message`, `laboratory: LaboratoryRef | None`), `StructureDesignation` (`assignment_id`, `user: UserRef`, `laboratory: LaboratoryRef | None`, `is_effective`), `StructureSamples`, `StructurePoint`, `RejectedPoint` (`activity_key`, `reason`), `StructureDecisionPublic`, `StructureApprovalPanel`, `StructureDecisionRequest` (`extra='forbid'`, `outcome: Literal['APPROVED', 'REJECTED']`, `justification: str = Field(min_length=3)`, `rejected_points: list[RejectedPoint] | None = None`) e `StructureDecisionResponse`.
- [X] T018 [US1] Serviço `src/pivma/core/structure_approval_service.py`, com docstring citando a Spec 042 e as research R2, R3 e R6:
  - `STRUCTURE_APPROVAL_KEY = 'structure_approval'` e `DECISION_TYPE = 'STRUCTURE_APPROVAL'`;
  - `_approval_activity(session, process_id, user_id, level)`: carrega a atividade com `populate_existing` e chama `require_activity_access`; sem a atividade, `NotFoundError`;
  - `_points(session, act)`: atividades das `ActivityDependency` da homologação, ordenadas por `order_index`;
  - `_pending(session, process_id, points)`: as quatro regras de data-model.md ("Pendências"), com o cargo-alvo do `role_assignment` lido do payload da versão do template (como `_find_role_assignment_activity`), designação ativa = `revoked_at` e `deleted_at` nulos, e os conjuntos de laboratórios das mesmas consultas de `active_laboratories` e `_frozen_laboratory_ids`;
  - `get_panel(session, process_id, user_id)`: monta o painel com `user_refs`/`laboratory_refs`, `compute_effectiveness_map` e o histórico de `Decision` com `decision_type` `STRUCTURE_APPROVAL`, da mais recente para a mais antiga; só contagens das amostras;
  - `execute_structure_decision(session, process_id, user_id, outcome, justification, rejected_points)`, ramo `APPROVED`: `_lock_process`, `ensure_process_mutable`, `_approval_activity(..., 'edit')`, execução em andamento ou `ConflictError(code='invalid_transition')`, grava a `Decision`, `_complete_activity_run`, fase 2 `COMPLETED`, `lock_template_row` quando houver `collection_template_id`, `_advance_dependent_activities`, evento `STRUCTURE_APPROVED` (`decision_id`, `justification`), commit.
- [X] T019 [US1] Router `src/pivma/routers/structure_approval.py` com `GET /processes/{id}/structure-approval` (`CurrentUser`) e `POST /processes/{id}/structure-approval/decision` (`CurrentUser`, `TrustedOrigin`), convertendo `NotFoundError` em 404, `AuthorizationError` em 403, `ConflictError` em 409 com o `code` do erro e `ValidationError` em 422; registrar em `src/pivma/__init__.py`. Fazer T013 e T014 passarem.
- [X] T020 [US1] Em `src/pivma/core/collection_template_service.py` (research R9):
  - `locked_template_ids` conta os processos vinculados com ao menos uma execução de atividade da fase `phase_3_validation_execution`, mantendo `skip_soft_delete_filter` (o status da fase não serve: a exclusão antes da Etapa 3 o muda para `CANCELLED`; teste em T015);
  - mensagem de `_ensure_unlocked`: "um processo vinculado já começou a Etapa 3.";
  - docstrings do módulo e de `lock_template_row` citam a aprovação da homologação e a conclusão das amostras como os dois chamadores.
  Fazer T015 e T016 passarem.
- [X] T021 [US1] Rodar `tests/integration/bootstrap/`, `tests/api/routers/test_structure_approval_*.py`, `test_collection_template_*.py`, `test_sample_receipt_*.py` e `test_activity_type_extension.py`.

### Jornadas existentes afetadas (US1)

- [X] T022 [US1] Em `tests/integration/journeys/sample_steps.py`:
  - `study_team` cria também patrocinador, estatístico, colaborador e avaliador ad hoc;
  - `complete_study_team(client, team, process_id, bracvam_user)`: o proponente designa o patrocinador; o Grupo Gestor designa o estatístico e o primeiro laboratório como laboratório líder; o BraCVAM designa colaborador e avaliador ad hoc;
  - `approve_structure(client, process_id, bracvam_user)`: aprova pela rota de T019 e confere `200`.
- [X] T023 [US1] Fazer a jornada de T012 passar com os helpers de T022.
- [X] T024 [US1] Atualizar as jornadas que chegam à Etapa 3 com o template real:
  - `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`: `_etapa_3_aberta` monta a equipe completa e aprova a homologação depois de concluir as amostras; docstring do estado inicial diz que a Etapa 3 abre na homologação;
  - `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`: a trava passa a ser verificada depois da aprovação, e a conclusão das amostras deixa o template ainda editável.

**Checkpoint**: MVP. O BraCVAM aprova e a Etapa 3 abre; nenhum processo novo chega à Etapa 3 sem homologação.

---

## Phase 4: User Story 2 - BraCVAM reprova um ponto e a atividade volta para nova execução (Priority: P1)

**Goal**: reprovação com motivo por ponto, reexecução e reabertura automática da homologação.

**Independent Test**: jornada de T025 verde. É o critério de conclusão obrigatório da issue #27.

### Tests for User Story 2

- [X] T025 [US2] Jornada `test_bracvam_reprova_o_laboratorio_e_a_estrutura_volta_para_correcao` no módulo de T012, seguindo quickstart.md:
  1. estado de T012 até o painel aberto, com dois laboratórios;
  2. Helena reprova `assign_participating_laboratory` com o motivo "Laboratório errado.": `200`, `status` `BLOCKED`, `reopened` com `run_number` 2;
  3. Marcos vê em `GET /tasks` a tarefa "Definir os Laboratórios Participantes" da execução 2 `READY` e a da execução 1 `COMPLETED`; Helena não tem tarefa de homologação `READY`; Thiago não vê recebimento;
  4. a linha do tempo mostra `STRUCTURE_REJECTED` e `ACTIVITY_REOPENED` com o motivo;
  5. Marcos revoga o laboratório errado e designa outro: o ponto conclui e a homologação reabre (tarefa `READY` de Helena na execução 2);
  6. o painel aponta `laboratory_without_codes` e `codes_without_laboratory` no ponto das amostras; aprovar responde `409 structure_pending`;
  7. Helena reprova `sample_definition`; Ricardo vê a tarefa, conclui as amostras de novo;
  8. Helena vê a homologação na execução 3, sem pendência, e aprova;
  9. o laboratório certo vê a tarefa de recebimento; o laboratório revogado não vê;
  10. o painel mostra três decisões, da mais recente para a mais antiga, com os pontos reprovados e os motivos.
- [X] T026 [P] [US2] Contrato da reprovação em `tests/api/routers/test_structure_approval_rejection.py`, um teste por item:
  - reprovar um ponto: `200`, `outcome` `REJECTED`, `status` `BLOCKED`, `reopened` `[{activity_key, run_number: 2}]`;
  - o ponto reprovado fica `IN_PROGRESS` com execução 2 cujo `execution_reason` é o motivo e tarefa `READY` do cargo responsável (`group_manager` para `assign_participating_laboratory`);
  - a execução 1 do ponto continua `COMPLETED`, com `completed_at` intacto;
  - a homologação fica `BLOCKED` com `blocked_reason` "Aguardando a reexecução dos pontos reprovados.", execução e tarefa `COMPLETED`;
  - `Decision` com `outcome` `REJECTED` e `rejected_points` igual ao enviado;
  - eventos: um `STRUCTURE_REJECTED` (`decision_id`, `justification`, `rejected_points`) e um `ACTIVITY_REOPENED` por ponto (`activity_key`, `previous_run_number`, `run_number`, `reason`);
  - dois pontos reprovados: a homologação continua `BLOCKED` quando só um conclui; reabre na execução 2, com tarefa `READY` e `ACTIVITY_UNBLOCKED`, quando o segundo conclui;
  - reprovar `assign_group_manager`: as atribuições que dependem dele continuam `COMPLETED`;
  - `sample_definition` reaberta aceita alteração de substância e nova conclusão; os códigos dos laboratórios que continuam não mudam, os do laboratório revogado são descartados e o laboratório novo ganha códigos;
  - `sample_receipt` continua `BLOCKED` e sem execução depois da reprovação.
- [X] T027 [P] [US2] Validação da decisão em `tests/api/routers/test_structure_approval_validation.py`, um teste por linha de data-model.md ("Regras de validação da decisão"), cada um conferindo que nada mudou:
  - `outcome` fora de `APPROVED`/`REJECTED`: `422 validation_error`;
  - `justification` com menos de 3 caracteres: `422 validation_error`;
  - `APPROVED` com `rejected_points`, um teste com lista preenchida e outro com lista vazia: `422 validation_error`;
  - `REJECTED` sem `rejected_points` e com lista vazia: `422 validation_error`;
  - `activity_key` repetida: `422 validation_error`;
  - `reason` com menos de 3 caracteres: `422 validation_error`;
  - campo extra no corpo: `422 validation_error`;
  - `activity_key` que não é ponto (`triage_evaluation`, `structure_approval`, chave inexistente): `422 invalid_point`.
- [X] T028 [P] [US2] Fechamento da atribuição de cargo em `tests/api/routers/test_participant_router.py`, com a fábrica de T011:
  - atribuição reaberta conclui na revogação que deixa ao menos uma designação ativa e nenhum convite pendente (execução 2 `COMPLETED`);
  - atribuição reaberta não conclui na revogação que deixa o cargo sem designação ativa;
  - atribuição reaberta conclui na designação nova.
- [X] T029 [P] [US2] Regressão em `tests/api/routers/test_invites_router.py` (research R8): revogar o único convite pendente de um cargo sem designação deixa a atribuição em andamento, com a tarefa `READY`. `test_accept_and_revoke_pending_sibling_closes_activity` continua verde.
- [X] T030 [P] [US2] Concorrência na liberação por dependências em `tests/integration/database/test_dependency_release_concurrency.py` (research R12), no padrão de `test_sample_concurrency.py` (dados confirmados fora da transação do teste e `TRUNCATE` ao final). Ordem forçada, sem depender de sorte:
  - a sessão A conclui o primeiro ponto reaberto (designação pelo serviço de participantes, que chama `_complete_activity_run` e `_advance_dependent_activities`) sem confirmar; numa tarefa assíncrona, a sessão B conclui o segundo ponto pelo mesmo serviço e confirma; o teste espera até B terminar ou aparecer aguardando trava em `pg_stat_activity` (`wait_event_type = 'Lock'`), com limite de tempo, e só então A confirma; ao final a homologação está `IN_PROGRESS` com exatamente uma execução nova e um `ACTIVITY_UNBLOCKED` nela;
  - regressão do mesmo defeito na abertura de `sample_definition`: concluir `assign_sample_selection_group` e `assign_participating_laboratory` na mesma ordem forçada deixa `sample_definition` `IN_PROGRESS`, com uma execução.
  Os dois testes falham antes de T035.

### Implementation for User Story 2

- [X] T031 [US2] Em `src/pivma/schemas.py`, `RejectedPoint.reason: str = Field(min_length=3)` e `model_validator` em `StructureDecisionRequest`: `APPROVED` exige `rejected_points` ausente ou nulo (lista vazia também é recusada); `REJECTED` exige lista não vazia sem `activity_key` repetida. Fazer as linhas `validation_error` de T027 passarem.
- [X] T032 [US2] Ramo `REJECTED` de `execute_structure_decision` em `src/pivma/core/structure_approval_service.py` (research R4 e R6):
  - toda `activity_key` precisa estar em `_points`, senão `ValidationError` com `code='invalid_point'` antes de qualquer escrita;
  - grava a `Decision` com `rejected_points`, conclui a execução da homologação (`_complete_activity_run`) e a deixa `BLOCKED` com o `blocked_reason` de T026;
  - para cada ponto, `_activate_activity` com `reason` como motivo e `_template_activity_data` para o cargo da tarefa, e evento `ACTIVITY_REOPENED`;
  - evento `STRUCTURE_REJECTED`; resposta com `reopened`.
  Fazer T026 e a linha `invalid_point` de T027 passarem.
- [X] T033 [US2] Em `_maybe_close_role_assignment_activity` (`src/pivma/core/process_engine.py`), retornar sem fechar quando o cargo não tem designação ativa (`Assignment` do processo e do `role_key` com `revoked_at` e `deleted_at` nulos); atualizar a docstring. Fazer T029 passar.
- [X] T034 [US2] Em `revoke_participant` (`src/pivma/routers/process_participants.py`), chamar `_maybe_close_role_assignment_activity` depois de gravar a revogação e antes do commit, como já faz `revoke_participant_invite`. Fazer T028 passar.
- [X] T035 [US2] Em `_advance_dependent_activities` e `_dependency_satisfied` (`src/pivma/core/process_engine.py`), research R12: para dependente de escopo `process` em `BLOCKED`, reler a atividade com `with_for_update()` e `populate_existing` antes de checar as dependências; `_dependency_satisfied` relê a atividade exigida com `populate_existing` em vez de `session.get`. O ramo por laboratório não muda. Atualizar a docstring. Fazer T030 passar e rodar `tests/integration/database/` e `tests/integration/journeys/`.
- [X] T036 [US2] Fazer a jornada de T025 passar e rodar `test_participant_*.py`, `test_invite*.py` e `test_structure_approval_*.py`.

**Checkpoint**: o ciclo reprovar → reexecutar → aprovar funciona pela API pública.

---

## Phase 5: User Story 3 - A aprovação só acontece sobre uma estrutura completa e por quem pode decidir (Priority: P2)

**Goal**: aprovação recusada com pendência, decisão única sob concorrência e recusa em processo terminal.

**Independent Test**: jornada de T037 e os testes de T038 a T040 verdes.

### Tests for User Story 3

- [X] T037 [US3] Jornada `test_bracvam_so_aprova_a_estrutura_completa` no módulo de T012:
  1. com as amostras ainda em definição, Helena não vê tarefa de homologação e a decisão responde `409 invalid_transition`;
  2. Ricardo conclui as amostras; Helena vê a tarefa;
  3. Marcos designa um terceiro laboratório; o painel aponta `laboratory_without_codes`;
  4. Helena tenta aprovar: `409 structure_pending`; Thiago continua sem recebimento;
  5. Marcos tenta decidir: `404`;
  6. Helena reprova as amostras; Ricardo conclui de novo; Helena aprova e os três laboratórios veem o recebimento.
- [X] T038 [P] [US3] Pendências em `tests/api/routers/test_structure_approval_pending.py`, um teste por regra, cada um conferindo o `code` no ponto certo do painel e, quando a homologação está aberta, a aprovação recusada com `409 structure_pending` e nada mudado:
  - `activity_not_completed` (`complete_samples=False`): aparece em `sample_definition`;
  - `role_without_designation`: revogar o colaborador depois da conclusão;
  - `laboratory_without_codes`: designar laboratório depois da conclusão das amostras;
  - `codes_without_laboratory`: revogar um laboratório depois da conclusão das amostras;
  - `codes_without_laboratory` com laboratório excluído do cadastro e designação ainda ativa; reprovar e concluir as amostras de novo zera a pendência;
  - cálculo na hora: depois de `role_without_designation`, designar outro colaborador e aprovar com `200`.
- [X] T039 [P] [US3] Concorrência em `tests/api/routers/test_structure_approval_concurrency.py`, no padrão de `test_sample_receipt_concurrency.py` (dados confirmados fora da transação, `run_concurrently` e `TRUNCATE` ao final):
  - duas aprovações simultâneas: uma `200`, outra `409 invalid_transition`; uma `Decision` e um `STRUCTURE_APPROVED`;
  - aprovação e reprovação simultâneas: uma `200`, outra `409 invalid_transition`; uma `Decision`.
- [X] T040 [P] [US3] Processo terminal em `tests/api/routers/test_structure_approval_router.py`: com a homologação aberta, excluir o processo por `DELETE /processes/{id}` (ele fica `CANCELLED`; arquivar só vale para processo já `CLOSED` ou `CANCELLED`) e conferir que a decisão responde `409 invalid_transition` e nada muda.

### Implementation for User Story 3

- [X] T041 [US3] No ramo `APPROVED` de `execute_structure_decision`, depois da trava do processo, calcular `_pending` e, se houver alguma, levantar `ConflictError` com `code='structure_pending'` e mensagem sem dados enviados. Fazer T037 e T038 passarem.
- [X] T042 [US3] Rodar T039 e T040; se falharem, corrigir em `src/pivma/core/structure_approval_service.py` sem trava nova além de `_lock_process` (research R6).

**Checkpoint**: todos os critérios de aceite da issue cobertos por teste.

---

## Phase 6: Polish & Cross-Cutting Concerns

Prosa revisada com a skill `stop-slop`. O manual descreve só o estado atual.

- [X] T043 Tutorial `manual/tutorial/homologacao-da-estrutura.md` (critério de conclusão da issue): a história de T025, com diagrama `sequenceDiagram`, personagens, "Antes de começar" apontando para `equipe-e-amostras.md` e blocos "Como fazer pela API" no formato dos outros tutoriais. Incluir no `nav` de `mkdocs.yml`, depois de "Montar a equipe e preparar as amostras", e em `manual/tutorial/index.md`.
- [X] T044 [P] `manual/tutorial/equipe-e-amostras.md`: designar os oito cargos e terminar apontando para o tutorial novo. `manual/tutorial/recebimento-com-avaria.md`: o "Antes de começar" inclui a homologação.
- [X] T045 [P] `manual/referencia/rotas.md`: as duas rotas novas, com permissão, `Origin` e respostas de contracts/http-api.md.
- [X] T046 [P] `manual/referencia/erros.md`: `409 structure_pending`, `422 invalid_point`; ajustar a linha de `template_locked` ("depois que a Etapa 3 de um processo vinculado começa").
- [X] T047 [P] `manual/referencia/eventos.md`: `STRUCTURE_APPROVED`, `STRUCTURE_REJECTED` e `ACTIVITY_REOPENED`, com o `context_data` de data-model.md.
- [X] T048 [P] `manual/referencia/estados.md`: estados da homologação e do ponto reaberto (data-model.md, "Entidades usadas").
- [X] T049 [P] `manual/referencia/templates.md` e `manual/referencia/templates-yaml.md`: a atividade nova, a dependência do recebimento e as versões; `manual/referencia/perfis-permissoes-cargos.md`: o cargo BraCVAM edita a homologação.
- [X] T050 [P] `manual/explicacao/modelo-de-processo.md` (portão entre as etapas, reexecução, fechamento da atribuição na revogação) e `manual/explicacao/escopo.md` (entra a homologação; o plano estatístico fica fora, com a pendência registrada).
- [X] T051 [P] Guias: `manual/guias/designar-participantes.md` (fechamento na designação e na revogação, com ao menos uma designação ativa), `manual/guias/montar-template-de-coleta.md` (trava no início da Etapa 3), `manual/guias/definir-amostras-cegas.md` e `manual/guias/receber-amostras.md` (a Etapa 3 abre na homologação).
- [X] T052 Revisar com `stop-slop` toda prosa nova ou alterada em `manual/`, `src/pivma/templates_data/README.md` e `specs/042-structure-approval/`; rodar `poe docs-build`.
- [X] T053 Verificação final: `poe lint`, `poetry run pytest` completo, `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`, e o roteiro de quickstart.md. Comparar as falhas com as anotadas em T001 e relatar só o que rodou.
- [X] T054 Rascunho da descrição da PR para `develop` em `specs/042-structure-approval/pr-description.md`, com: a decisão de não exigir plano estatístico (Clarifications), a mudança da trava do template de coleta, a correção do fechamento com cargo vazio (research R8) e a lista de testes. O comentário na issue #27 só sai com aprovação do usuário.

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (T001) → Foundational (T002–T011) → US1 (T012–T024) → US2 (T025–T036) → US3 (T037–T042) → Polish (T043–T054).
- US2 depende de US1: a reprovação usa o painel, o serviço e o router de US1.
- US3 depende de US1 e US2: a jornada de T037 reprova as amostras.

### Within Each User Story

- Jornada primeiro, depois os testes focados, depois a implementação.
- Esquemas (T017, T031) → serviço (T018, T032, T041) → router (T019).
- As jornadas existentes (T024) só passam depois de T019 e T022.

### Parallel Opportunities

- Fundação: T002, T003, T004 e T005 juntos; depois T009 e T010 junto com T006–T008.
- US1: T013, T014, T015 e T016 juntos, depois da jornada T012.
- US2: T026, T027, T028, T029 e T030 juntos.
- US3: T038, T039 e T040 juntos.
- Polish: T044 a T051 juntos.

## Parallel Example: User Story 1

```text
T013 test_structure_approval_router.py
T014 test_structure_approval_security.py
T015 test_collection_template_lock.py
T016 test_collection_template_concurrency.py
```

## Implementation Strategy

### MVP

Fundação e US1: o portão existe, o BraCVAM aprova e a Etapa 3 abre. As
jornadas da Etapa 3 voltam ao verde.

### Incremental Delivery

1. US2: reprovação e reexecução, o critério obrigatório da issue.
2. US3: recusas por pendência, concorrência e processo terminal.
3. Polish: tutorial, referências e verificação final, no mesmo PR.

## Notes

- `[P]` = arquivos diferentes, sem dependência de tarefa incompleta.
- T001 (2026-10-14), no `HEAD` e0ca7e9 sem as mudanças desta feature:
  `ruff check` sem erros; `pytest` com 2026 testes aprovados, 1 ignorado e
  nenhuma falha. Nenhuma falha anterior à feature.
- O cenário 8 da US3 (validação da decisão) é implementado na US2 (T027 e T031), porque a reprovação nasce ali.
- Risco aceito: revogação simultânea à aprovação (research R6). Não ganha teste próprio; o resultado equivale a revogar logo depois da aprovação.
- Rastreabilidade: FR-001–FR-003 → T003–T008, T011, T013, T014; FR-004–FR-008 → T013, T018, T038; FR-009–FR-011 → T012, T013, T018; FR-012–FR-016 → T025–T035 (concorrência de FR-014 em T030); FR-017–FR-019 → T014, T039, T040; FR-020–FR-021 → T013, T026; FR-022 → T015, T016, T020; FR-023 → T043–T051; FR-024 → já feito na spec.

---

## Phase 7: Convergence

- [X] T055 [P] Em `tests/api/routers/test_structure_approval_rejection.py`, depois de reprovar `assign_participating_laboratory`, o Grupo Gestor do processo lê `GET /processes/{id}/timeline` e vê o `ACTIVITY_REOPENED` do ponto com `reason` igual ao motivo enviado per US2/AC2 (partial)
- [X] T056 Em `tests/api/routers/test_structure_approval_rejection.py`, na mesma situação, a linha do tempo do Grupo Gestor não traz `STRUCTURE_REJECTED`, e a de quem é BraCVAM traz, como afirma `manual/referencia/eventos.md` per spec Assumptions: visibilidade da homologação (partial)
- [X] T057 No passo 3 de `manual/tutorial/homologacao-da-estrutura.md`, a gestora lê o motivo no `ACTIVITY_REOPENED` da linha do tempo (`jq` com `select(.event_type=="ACTIVITY_REOPENED") | .context_data.reason`); revisar a prosa com `stop-slop` e rodar `poe docs-build` per US2/AC2, FR-023 (partial)

## Phase 8: Ajustes da revisão

- [X] T058 [US1] Em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py`, preparar as três jornadas com `bootstrap_fresh_deploy`, cadastro e login públicos, concessão do perfil BraCVAM pela API e criação de instituições, laboratórios e vínculos pela API. Preservar as verificações de tarefas, painel, reexecução e recebimento de US1–US3; remover factories e cookies fabricados dessas jornadas (SC-002, constituição V).
- [X] T059 [US3] Em `tests/api/routers/test_structure_approval_pending.py`, criar pela API um convite adicional para um cargo já concluído e verificar: atividade e execução preservadas, painel sem pendência e aprovação permitida enquanto o convite permanece pendente (FR-008, Clarifications).
- [X] T060 Registrar a decisão sobre convites adicionais em `docs/observacoes-e-pendencias.md`, Clarifications e FR-008 da spec, research R3, data-model.md e manual; atualizar a rastreabilidade do plano e rodar os testes afetados, `poe lint` e `poe docs-build`.

Verificação dos ajustes (2026-10-14):

- `poetry run pytest -q --no-cov tests/api/routers/test_structure_approval_pending.py tests/integration/journeys/etapa_2_planejamento_preparacao/test_structure_approval_journey.py`: 10 aprovados. A execução usa Docker/Testcontainers fora do sandbox; dentro dele, o acesso ao socket foi negado antes dos testes.
- `poetry run poe lint`: sem erros.
- `PYTHONPATH=src poetry run poe docs-build`: build estrito aprovado. Sem `PYTHONPATH`, o hook de rotas não encontra o pacote `pivma` neste ambiente.
- `git diff --check`: sem erros. A suíte completa e as migrações não foram reexecutadas nestes ajustes, que alteram testes e documentação.
