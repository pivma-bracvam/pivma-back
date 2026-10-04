---

description: "Tarefas da Spec 040: recebimento de amostras, inconformidades e cadastro expandido"
---

# Tasks: Recebimento de amostras, inconformidades e cadastro expandido

**Input**: Design documents from `specs/040-sample-receipt-nonconformity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, quickstart.md

**Tests**: obrigatórios (AGENTS.md, constituição V, `testing-methodology`).
Cada história tem uma jornada antes da implementação e testes focados por
risco. Nos testes focados, verifique o `code` do erro, não a mensagem.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Adicionar `PUBCHEM_BASE_URL: str = 'https://pubchem.ncbi.nlm.nih.gov'` e `PUBCHEM_TIMEOUT_SECONDS: float = 10` (ge 1) em `src/pivma/core/settings.py`, com comentário da Spec 040

---

## Phase 2: Foundational

**Purpose**: modelo, migração, Etapa 3 nos templates e extrações no motor, que todas as histórias usam.

- [X] T002 [P] Teste de migração: upgrade cria as colunas novas de `study_substances` (`reserve_vials_count` não nula padrão 0, `ghs_hazard_pictograms` não nula padrão `{}`), `blind_sample_codes.replaces_code_id`, as tabelas `sample_receipts` e `sample_receipt_nonconformities` e o índice `uq_sample_receipts_code_active`; substância existente fica com reserva 0 e campos novos nulos; downgrade remove tudo, em `tests/integration/migrations/test_sample_receipt_migration.py`
- [X] T003 Modelos em `src/pivma/core/database/models.py`: colunas novas de `StudySubstance` exatamente como em data-model.md (`reference_classification Text nulo`, `storage_temperature_regime String(16) nulo`, `storage_temperature_min/max Float nulo`, `vial_nominal_quantity Float nulo`, `vial_unit String(16) nulo`, `packaging_type String(255) nulo`, `expiration_date Date nulo`, `reserve_vials_count Integer não nulo padrão 0`, `ghs_hazard_pictograms ARRAY(String(5)) não nulo padrão []`); `BlindSampleCode.replaces_code_id` FK nula; `SampleReceipt` e `SampleReceiptNonconformity` com `AuditMixin`, colunas e índices de data-model.md
- [X] T004 Migração Alembic `migrations/versions/<rev>_sample_receipt_nonconformity.py` com `down_revision = '6fe19f1c95e9'`, espelhando T003, com downgrade
- [X] T005 [P] Teste de provisionamento: os cinco templates têm `phase_3_validation_execution` idêntica, com `sample_receipt` (por laboratório, edição só `participating_laboratory`, depende de `sample_definition`) e `sample_receipt_resolution` (edição só `sample_selection_group`, sem dependências), e a carga passa em `validate_execution_scopes`, em `tests/integration/bootstrap/test_template_phase_3.py`
- [X] T006 [P] Teste de instanciação: processo novo do template 1 nasce com `sample_receipt_resolution` `BLOCKED`, sem execução nem tarefa, em `tests/api/routers/test_process_template_instantiation.py`
- [X] T007 Acrescentar a Etapa 3 (research R2) aos cinco arquivos `src/pivma/templates_data/0[1-5]_*.yaml` e a seção correspondente em `src/pivma/templates_data/README.md`
- [X] T008 Em `src/pivma/core/process_engine.py`: `EVENT_OPENED_ACTIVITY_TYPES = {RETURN_REVIEW_ACTIVITY_TYPE, 'sample_receipt_resolution'}` usado na instanciação no lugar da comparação com `return_review`
- [X] T009 Em `src/pivma/core/process_engine.py`: extrair de `complete_laboratory_run` o trecho de conclusão (status, tarefas, `LABORATORY_RUN_COMPLETED`, `_unblock_laboratory`, `_refresh_laboratory_activity`) para `_finish_laboratory_run(session, process, act, run, user_id)`, sem mudar o comportamento de `complete_laboratory_run` (os testes de `tests/api/routers/test_laboratory_*.py` continuam verdes)
- [X] T010 [P] Fábrica `tests/factories/sample_receipt_factory.py`: processo com o template mínimo de amostras + Etapa 3 de T007, substâncias com faixa 2–8 °C e reserva configurável, N laboratórios, definição concluída (recebimento em andamento) e helpers de registro

**Checkpoint**: migração aplicada, templates carregados, suíte existente verde.

---

## Phase 3: User Story 1 - Cadastro com gabarito, faixa térmica, frasco e GHS (P1) 🎯 MVP

**Goal**: o Grupo de Seleção cadastra os campos novos; laboratórios nunca veem o gabarito.

**Independent Test**: cadastrar com todos os campos; recusar sem gabarito; visão cega e etiqueta com GHS e faixa, sem nome, CAS, SDS e gabarito.

### Tests for User Story 1

- [X] T011 [US1] Jornada: Ricardo cadastra substância com os campos novos pela API pública, conclui a definição, consulta etiquetas e visão cega do frasco e vê GHS/faixa sem nome, CAS, SDS e gabarito, em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sample_registration_journey.py`
- [X] T012 [P] [US1] Contrato: criação sem `reference_classification` ou com ela em branco → `422` com o campo em `fields`, em `tests/api/routers/test_samples_router.py`
- [X] T013 [P] [US1] Contrato: regime `refrigerated` sem faixa grava 2/8 e `ambient` grava 15/25, em `tests/api/routers/test_samples_router.py`
- [X] T014 [P] [US1] Contrato: `frozen`, `deep_frozen` e `custom` sem os dois limites, faixa sem regime e mínimo > máximo → `422 invalid_temperature_range`, em `tests/api/routers/test_samples_router.py`
- [X] T015 [P] [US1] Contrato: `PATCH` que muda só `storage_temperature_min` acima do máximo gravado → `422 invalid_temperature_range` e nada muda, em `tests/api/routers/test_samples_router.py`
- [X] T016 [P] [US1] Contrato: pictograma fora de `GHS01`…`GHS09` ou repetido, reserva negativa, quantidade ≤ 0 → `422` com o campo, em `tests/api/routers/test_samples_router.py`
- [X] T017 [P] [US1] Contrato: `PATCH` com `reference_classification: null` ou `""` → `422`; `PATCH` sem ela em substância legada (sem gabarito) → `200`, em `tests/api/routers/test_samples_router.py`
- [X] T018 [P] [US1] Contrato: lista de substâncias traz `reserve_vials_count` e os campos novos, em `tests/api/routers/test_samples_router.py`
- [X] T019 [P] [US1] Contrato: etiquetas e visão cega trazem os campos novos e o corpo não contém as chaves `chemical_name`, `cas_number`, `reference_classification` nem `sds`, em `tests/api/routers/test_samples_access.py`
- [X] T020 [P] [US1] Unitário: regra de regime e faixa (presets, obrigatoriedade, mínimo ≤ máximo, limites iguais aceitos) em `tests/unit/core/test_sample_temperature.py`

### Implementation for User Story 1

- [X] T021 [US1] Schemas em `src/pivma/schemas.py`: `SampleSubstanceCreate` (gabarito obrigatório não vazio), `SampleSubstanceUpdate` (gabarito não nulo se enviado), `TemperatureRegime`, `GhsPictogram = Literal['GHS01'…'GHS09']` com validação de repetição, quantidade `> 0`, reserva `≥ 0`; `SampleSubstance`, `SampleLabel`, `BlindVial` com os campos novos
- [X] T022 [US1] Em `src/pivma/core/sample_service.py`: função pura `resolve_temperature_range(regime, min, max)` (research R10), aplicada no `create_substance` e no `update_substance` sobre o estado resultante; gravação e serialização dos campos novos; `list_labels` e `get_blind_vial` com os campos novos

**Checkpoint**: T011–T020 verdes.

---

## Phase 4: User Story 3 - Confirmar o recebimento de um lote em ordem (P1)

**Goal**: o laboratório lista os próprios frascos e registra cada um; o lote conclui no último frasco em ordem.

**Independent Test**: dois laboratórios, dois frascos cada; o Lab A registra os dois em ordem; execução do Lab A concluída, do Lab B em andamento.

### Tests for User Story 3

- [X] T023 [US3] Jornada (Jornada 1): do ambiente novo até a Etapa 3 pelo template 1; Thiago vê a tarefa de recebimento, lista os frascos (`pending`), abre a visão cega pelo código, registra o 1º em ordem (`received`, `in_progress`), registra o 2º e recebe `completed` com a mensagem de lote liberado; a tarefa some como `READY` e a atividade continua em andamento pelo Lab B, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`
- [X] T024 [P] [US3] Contrato: registro em ordem → `201`, `conforming: true`, `deviations: []`, frasco `received`, em `tests/api/routers/test_sample_receipt_router.py`
- [X] T025 [P] [US3] Contrato: registro do último frasco conclui a execução do laboratório (`COMPLETED`) e a tarefa dele; o outro laboratório segue `IN_PROGRESS`, em `tests/api/routers/test_sample_receipt_router.py`
- [X] T026 [P] [US3] Contrato: segundo registro do mesmo frasco → `409 vial_already_registered` e o primeiro não muda, em `tests/api/routers/test_sample_receipt_router.py`
- [X] T027 [P] [US3] Contrato: temperatura exatamente no limite da faixa → em ordem; substância sem faixa com qualquer temperatura e embalagem íntegra → em ordem, em `tests/api/routers/test_sample_receipt_router.py`
- [X] T028 [P] [US3] Contrato: registro com recebimento do laboratório dispensado pelo gestor, ou em processo arquivado → `409 invalid_transition`, em `tests/api/routers/test_sample_receipt_router.py`
- [X] T029 [P] [US3] Contrato: lista de frascos paginada (`per_page=1`, total e ordem por laboratório e código), em `tests/api/routers/test_sample_receipt_router.py`
- [X] T030 [P] [US3] Contrato: evento `SAMPLE_RECEIPT_REGISTERED` na trilha com `laboratory_id`, `blind_sample_code_id`, `receipt_id`, `conforming`, `deviations` e sem o código cego em texto, em `tests/api/routers/test_sample_receipt_router.py`
- [X] T031 [P] [US3] Concorrência: registros simultâneos do mesmo frasco → um `201` e um `409`; dos dois últimos frascos do lote → execução concluída uma vez (um `LABORATORY_RUN_COMPLETED`), em `tests/api/routers/test_sample_receipt_concurrency.py`

### Implementation for User Story 3

- [X] T032 [US3] Schemas em `src/pivma/schemas.py`: `SampleReceiptCreate` (`opened_at` não futuro, `temperature_celsius: float`, `package_state: Literal['intact','damaged','violated']`, `notes` opcional, `extra='forbid'`), `SampleReceiptPublic`, `ReceiptVial`, `ReceiptVialListResponse`, `SampleReceiptResult`
- [X] T033 [US3] `src/pivma/core/sample_receipt_service.py`: acesso (`sample_receipt` + laboratório efetivo do código; outro laboratório → `NotFoundError`), situação derivada (data-model.md), lista de frascos, `register_receipt` com lock do processo, avaliação de conformidade (FR-024), evento, checagem de lote completo e `_finish_laboratory_run`
- [X] T034 [US3] Router `src/pivma/routers/sample_receipt.py` (`GET /processes/{id}/sample-receipt/vials`, `POST /processes/{id}/sample-receipt/vials/{code}`) e registro em `src/pivma/__init__.py`; `IntegrityError` do índice único → `409 vial_already_registered`

**Checkpoint**: T023–T031 verdes.

---

## Phase 5: User Story 4 - Bloquear registro incompleto ou inválido (P1)

**Goal**: envio incompleto ou inválido é recusado com cada campo indicado.

**Independent Test**: enviar sem cada campo e com temperatura não numérica; recusa com `fields`; frasco continua `pending`.

### Tests for User Story 4

- [X] T035 [US4] Jornada (Jornada 3): Thiago envia sem temperatura e sem estado da embalagem, vê os dois campos apontados, confere o frasco ainda pendente, corrige e registra, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`
- [X] T036 [P] [US4] Contrato: sem `temperature_celsius` → `422` com o campo em `fields`, em `tests/api/routers/test_sample_receipt_validation.py`
- [X] T037 [P] [US4] Contrato: `temperature_celsius: "abc"` → `422` com o campo, em `tests/api/routers/test_sample_receipt_validation.py`
- [X] T038 [P] [US4] Contrato: sem `package_state` e com `package_state: "quebrado"` → `422` com o campo, em `tests/api/routers/test_sample_receipt_validation.py`
- [X] T039 [P] [US4] Contrato: sem `opened_at` e com `opened_at` no futuro → `422` com o campo, em `tests/api/routers/test_sample_receipt_validation.py`
- [X] T040 [P] [US4] Contrato: após qualquer recusa, nenhum registro nem evento foi gravado e o frasco segue `pending`, em `tests/api/routers/test_sample_receipt_validation.py`

### Implementation for User Story 4

- [X] T041 [US4] Validador de `opened_at` não futuro (com fuso) em `SampleReceiptCreate` em `src/pivma/schemas.py`; conferir que o handler de validação devolve `fields` para cada campo

**Checkpoint**: T035–T040 verdes.

---

## Phase 6: User Story 5 - Só o próprio laboratório vê e registra (P1)

**Goal**: isolamento e cegamento no recebimento e na visão cega.

**Independent Test**: Lab A tenta ler e registrar frasco do Lab B → `404`; respostas sem campos sigilosos.

### Tests for User Story 5

- [X] T042 [US5] Jornada: Thiago (Lab A) lista os frascos e não vê os do Lab B; tenta abrir e registrar pelo código um frasco do Lab B e recebe "não encontrado"; abre um frasco próprio e não vê nome, CAS, SDS nem gabarito, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`
- [X] T043 [P] [US5] Contrato: `GET /samples/vials/{code}` de frasco do Lab B pela pessoa do Lab A → `404`, igual a código inexistente, em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T044 [P] [US5] Contrato: `POST /sample-receipt/vials/{code}` de frasco do Lab B → `404` e nada gravado, em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T045 [P] [US5] Contrato: pessoa com designação revogada ou sem vínculo ativo com o laboratório (Spec 035) → lista e registro negados, em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T046 [P] [US5] Contrato: usuário sem cargo no processo → `404`; gestor e Grupo de Seleção no `POST` de registro → negado, em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T047 [P] [US5] Contrato: corpo das respostas do laboratório (lista, visão cega, registro) não contém `chemical_name`, `cas_number`, `reference_classification`, `sds` nem `justification`, em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T048 [P] [US5] Contrato: Grupo de Seleção continua lendo a visão cega e o QR de qualquer frasco; o laboratório não lê o QR (`404`), em `tests/api/routers/test_samples_access.py`

### Implementation for User Story 5

- [X] T049 [US5] `get_blind_vial` em `src/pivma/core/sample_service.py`: aceita o Grupo de Seleção (regra atual) ou pessoa com laboratório efetivo igual ao do código (`effective_laboratory_ids`); demais → `NotFoundError`, preservando o `403` atual de quem vê a atividade sem editar

**Checkpoint**: T042–T048 verdes.

---

## Phase 7: User Story 6 - Frasco avariado ou com desvio térmico (P1)

**Goal**: registro fora de ordem abre inconformidade, mantém o lote aberto e avisa o Grupo por tarefa e e-mail.

**Independent Test**: 21 °C com faixa 2–8 → sucesso com inconformidade, execução em andamento, tarefa e e-mail na fila sem identidade química.

### Tests for User Story 6

- [X] T050 [US6] Jornada (Jornadas 2 e 4): Thiago abre a visão do frasco (faixa 2–8), registra 21 °C com observação, recebe sucesso com `awaiting_decision` e a mensagem de segregação; Ricardo entra, vê a tarefa "Resolver problemas no recebimento de amostras" `READY`, lista as inconformidades e vê temperatura, faixa, observação e o laboratório; o e-mail está na fila, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`
- [X] T051 [P] [US6] Contrato: 21 °C com embalagem íntegra → `201`, `conforming: false`, `deviations: ['temperature_out_of_range']`, `laboratory_receipt_status: 'awaiting_decision'`, em `tests/api/routers/test_sample_nonconformity_router.py`
- [X] T052 [P] [US6] Contrato: `damaged` → `package_damaged`; `violated` → `package_violated`; 21 °C + `damaged` → os dois motivos, em `tests/api/routers/test_sample_nonconformity_router.py`
- [X] T053 [P] [US6] Contrato: com os demais frascos recebidos e um aguardando decisão, a execução do laboratório segue `IN_PROGRESS`, em `tests/api/routers/test_sample_nonconformity_router.py`
- [X] T054 [P] [US6] Contrato: a primeira inconformidade abre execução `IN_PROGRESS` de `sample_receipt_resolution` com uma tarefa `READY` de `sample_selection_group`; a segunda (outro laboratório) não abre outra tarefa, em `tests/api/routers/test_sample_nonconformity_router.py`
- [X] T055 [P] [US6] Notificação: com e-mail configurado, um `Notification` `sample_receipt_nonconformity_email` por pessoa do Grupo de Seleção, com assunto `('sample_receipt_nonconformity', id)`; payload decifrado sem nome químico, CAS nem gabarito; texto renderizado com código do processo, laboratório e código cego, em `tests/integration/notifications/test_sample_nonconformity_email.py`
- [X] T056 [P] [US6] Notificação: sem e-mail configurado, o registro dá `201`, a tarefa existe e nenhum `Notification` é criado, em `tests/integration/notifications/test_sample_nonconformity_email.py`
- [X] T057 [P] [US6] Contrato: lista de inconformidades do Grupo traz laboratório, código, substância, registro, faixa esperada, motivos e `status: OPEN`; filtro `status=open|resolved`; paginação, em `tests/api/routers/test_sample_nonconformity_router.py`
- [X] T058 [P] [US6] Contrato: lista de inconformidades por laboratório, gestor (`404`), admin e BraCVAM (`403`) → negada, em `tests/api/routers/test_sample_nonconformity_router.py`
- [X] T059 [P] [US6] Isolamento: a pessoa do Lab B não vê na lista de frascos, em `/tasks` nem na trilha nada da inconformidade do Lab A; eventos `SAMPLE_NONCONFORMITY_OPENED` e `SAMPLE_RECEIPT_RESOLUTION_OPENED` não aparecem para nenhum laboratório, em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T060 [P] [US6] Unitário: renderizador `sample_receipt_nonconformity_email` (assunto, texto, HTML escapado) em `tests/unit/notifications/test_renderers.py`

### Implementation for User Story 6

- [X] T061 [US6] Renderizador `sample_receipt_nonconformity_email` em `src/pivma/notifications/renderers.py` (payload: `process_code`, `process_title`, `laboratory_name`, `blind_code`, `deviations`)
- [X] T062 [US6] Em `src/pivma/core/sample_receipt_service.py`: abertura da inconformidade no registro fora de ordem; abertura ou reuso da execução de `sample_receipt_resolution` com tarefa (`SAMPLE_RECEIPT_RESOLUTION_OPENED`); `SAMPLE_NONCONFORMITY_OPENED`; e-mails por `enqueue_notification` só com `email_channel_available`; mensagens de resposta (contrato)
- [X] T063 [US6] Lista de inconformidades: serviço (acesso por edição de `sample_receipt_resolution`, filtro, paginação) e rota `GET /processes/{id}/sample-receipt/nonconformities` em `src/pivma/routers/sample_receipt.py`; schemas `NonconformityPublic`, `NonconformityListResponse`, filtros

**Checkpoint**: T050–T060 verdes.

---

## Phase 8: User Story 7 - Resolver: aceitar, reenviar ou desclassificar (P1)

**Goal**: decisão do Grupo por frasco, com justificativa, liberando ou reenviando ou dispensando o laboratório.

**Independent Test**: reenviar; código novo, reserva debitada, vínculo só para o Grupo, frasco novo pendente; registrar o frasco novo e ver o lote concluído.

### Tests for User Story 7

- [X] T064 [US7] Jornada (issue #71): problema → Ricardo reenvia com justificativa → etiqueta nova na lista de etiquetas, reserva debitada, tarefa do Grupo concluída → Thiago vê o frasco anterior `replaced` e um frasco novo `pending`, registra o novo em ordem e o recebimento conclui; o Lab B não foi afetado, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`
- [X] T065 [P] [US7] Contrato: decisão sem justificativa ou com justificativa em branco, e `decision` fora da lista → `422` com o campo, nada muda, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T066 [P] [US7] Contrato: `accept_with_caveat` do único frasco pendente conclui a execução do laboratório; o frasco fica `accepted_with_caveat`, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T067 [P] [US7] Contrato: `resend` com reserva 2 → reserva 1, código anterior inativo, código novo ativo com `replaces_code_id`, `replacement_code` na inconformidade, execução do laboratório `IN_PROGRESS` com o frasco novo `pending`, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T068 [P] [US7] Contrato: `resend` com reserva 0 → `409 no_reserve_vials`, inconformidade `OPEN`, nenhum código novo, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T069 [P] [US7] Contrato: lista do laboratório depois do reenvio não liga o código novo ao anterior (sem `replaces`, `replacement_code`, `justification`), em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T070 [P] [US7] Contrato: `disqualify` dispensa o laboratório na Etapa 3 (execução `WAIVED`, `LABORATORY_WAIVED` com a justificativa como motivo), encerra as outras inconformidades abertas dele como `disqualify` e não muda os outros laboratórios, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T071 [P] [US7] Contrato: `disqualify` com o laboratório já dispensado pelo gestor encerra as inconformidades sem erro, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T072 [P] [US7] Contrato: decidir inconformidade já decidida → `409 already_decided`; de outro processo → `404`, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T073 [P] [US7] Contrato: a última decisão conclui a tarefa e a execução de `sample_receipt_resolution`; nova inconformidade depois abre execução nova (número seguinte), em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T074 [P] [US7] Contrato: decisão pelo laboratório, gestor (`404`), admin e BraCVAM (`403`) → negada, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T075 [P] [US7] Contrato: eventos `SAMPLE_NONCONFORMITY_RESOLVED` e `SAMPLE_VIAL_RESENT` sem justificativa nem código em texto; decisão em processo arquivado → `409 invalid_transition`, em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T076 [P] [US7] Concorrência: duas decisões simultâneas na mesma inconformidade → uma vale, a outra `409 already_decided`; dois reenvios simultâneos (inconformidades diferentes, mesma substância) com reserva 1 → um `200`, um `409 no_reserve_vials`, em `tests/api/routers/test_sample_receipt_concurrency.py`

### Implementation for User Story 7

- [X] T077 [US7] Schemas `NonconformityDecisionRequest` (`decision: Literal['accept_with_caveat','resend','disqualify']`, `justification` não vazia após `strip`) em `src/pivma/schemas.py`
- [X] T078 [US7] Em `src/pivma/core/sample_receipt_service.py`: `decide_nonconformity` com lock do processo e da inconformidade; aceite (checagem de lote e `_finish_laboratory_run`); reenvio (débito, `unique_code`, exclusão lógica do código anterior, `replaces_code_id`); desclassificação (`waive_laboratory` na fase de `sample_receipt`, `already_waived` tolerado, encerramento das outras do laboratório); conclusão da execução de resolução quando não resta `OPEN`; eventos
- [X] T079 [US7] Rota `POST /processes/{id}/sample-receipt/nonconformities/{nc_id}/decision` em `src/pivma/routers/sample_receipt.py`

**Checkpoint**: T064–T076 verdes.

---

## Phase 9: User Story 2 - Sugerir dados pelo CAS (PubChem) (P2)

**Goal**: consulta que sugere nome e GHS sem gravar nada.

**Independent Test**: com PubChem simulado, CAS conhecido → sugestões; nada gravado; desconhecido → `404`; fora do ar → `503`.

### Tests for User Story 2

- [X] T080 [US2] Jornada: Ricardo digita o CAS, recebe as sugestões do PubChem simulado, confirma o nome, ajusta os pictogramas e cadastra; a substância criada tem os valores que ele enviou e a consulta sozinha não criou nada, em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_sample_lookup_journey.py`
- [X] T081 [P] [US2] Contrato: CAS conhecido → `200` com `pubchem_cid`, `chemical_name`, `iupac_name`, `ghs_hazard_pictograms`, `source_url`; contagem de substâncias igual antes e depois, em `tests/api/routers/test_sample_lookup.py`
- [X] T082 [P] [US2] Contrato: CAS inválido → `422 invalid_cas` e o transporte simulado não recebeu chamada, em `tests/api/routers/test_sample_lookup.py`
- [X] T083 [P] [US2] Contrato: CAS desconhecido (PubChem `404`) → `404 compound_not_found`, em `tests/api/routers/test_sample_lookup.py`
- [X] T084 [P] [US2] Contrato: PubChem `500`, JSON inesperado e tempo esgotado → `503 lookup_unavailable`, em `tests/api/routers/test_sample_lookup.py`
- [X] T085 [P] [US2] Contrato: composto sem seção GHS (PUG-View `404`) → `200` com `ghs_hazard_pictograms: []`, em `tests/api/routers/test_sample_lookup.py`
- [X] T086 [P] [US2] Contrato: laboratório, gestor (`404`), admin (`403`) → negados, em `tests/api/routers/test_sample_lookup.py`
- [X] T087 [P] [US2] Unitário: extração de pictogramas do primeiro bloco "Pictogram(s)" (fixture com dois blocos), em `tests/unit/core/test_pubchem_parse.py`

### Implementation for User Story 2

- [X] T088 [US2] `src/pivma/core/pubchem.py`: `lookup_by_cas(cas, settings, transport)` com as três chamadas de research R8, `CompoundNotFoundError`, `LookupUnavailableError`, extração de pictogramas
- [X] T089 [US2] Dependência `PubChemTransport` (padrão `None`) e rota `GET /processes/{id}/samples/lookup` em `src/pivma/routers/samples.py`, com o acesso de `_sample_activity` e validação de CAS antes da chamada; schema `SampleLookupResponse` em `src/pivma/schemas.py`

**Checkpoint**: T080–T087 verdes.

---

## Phase 10: User Story 8 - Fotos do registro (P3)

**Goal**: imagens no registro do frasco, vistas pelo laboratório e pelo Grupo.

**Independent Test**: anexar PNG, baixar como Lab A e Grupo; Lab B recebe `404`.

### Tests for User Story 8

- [X] T090 [US8] Jornada: Thiago registra o frasco trincado e anexa uma foto; Ricardo vê a foto na inconformidade e a baixa, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py`
- [X] T091 [P] [US8] Contrato: anexo PNG/JPG → `201` e aparece em `photos` do frasco; evento `SAMPLE_RECEIPT_PHOTO_ATTACHED`, em `tests/api/routers/test_sample_receipt_photos.py`
- [X] T092 [P] [US8] Contrato: extensão não permitida, arquivo vazio e acima do limite → erros de anexo da Spec 016, em `tests/api/routers/test_sample_receipt_photos.py`
- [X] T093 [P] [US8] Contrato: anexo em frasco sem registro → `404`; com recebimento concluído ou dispensado → `409 invalid_transition`, em `tests/api/routers/test_sample_receipt_photos.py`
- [X] T094 [P] [US8] Contrato: download pelo Lab A e pelo Grupo → `200`; pelo Lab B e pelo gestor → `404`, em `tests/api/routers/test_sample_receipt_photos.py`

### Implementation for User Story 8

- [X] T095 [US8] Em `src/pivma/core/sample_receipt_service.py` e `src/pivma/routers/sample_receipt.py`: `POST .../vials/{code}/photos` (Artifact `sample_receipt_photo`, research R9) e `GET .../photos/{photo_id}`; fotos na lista de frascos e na de inconformidades

**Checkpoint**: T090–T094 verdes.

---

## Phase 11: Polish & Cross-Cutting

- [X] T096 [P] Manual: `manual/referencia/rotas.md`, `erros.md`, `estados.md` (situação do frasco, execução de resolução), `eventos.md`, `templates.md`/`templates-yaml.md` (Etapa 3), `ambiente.md` (`PUBCHEM_*`)
- [X] T097 [P] Manual: `manual/explicacao/amostras-cegas.md` (campos novos, gabarito, reenvio), `notificacoes.md` (e-mail de inconformidade), `escopo.md` (#28, #71, #72 entregues; fora: #31, RF039, RF046)
- [X] T098 [P] Manual: guia `manual/guias/receber-amostras.md`, atualização de `manual/guias/definir-amostras-cegas.md` (consulta ao PubChem) e tutorial `manual/tutorial/recebimento-com-avaria.md`, com os índices e `mkdocs.yml`
- [X] T099 Rodar `poetry run ruff check`, `poetry run ruff format --check`, `poetry run pytest` e `poe docs-build`; corrigir falhas
- [X] T100 Atualizar `uv.lock`/`poetry.lock` só se alguma dependência mudar (não previsto)

---

## Phase 12: Jornadas do usuário (2026-10-04)

**Goal**: as quatro jornadas e a Lista de Ações enviadas pelo usuário, uma a
uma, com o backend que elas pedem (FR-043 a FR-046).

### Tests

- [X] T101 Jornada 1 (recebimento perfeito) em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py::test_jornada_1_recebimento_perfeito`
- [X] T102 Jornada 2 (recebimento com desvio, com pré-verificação e foto) em `...::test_jornada_2_recebimento_com_desvio`
- [X] T103 Jornada 3 (falhas humanas) em `...::test_jornada_3_protecao_contra_falhas_humanas`
- [X] T104 Jornada 4 (retaguarda do Grupo de Seleção, alerta, foto, reenvio) em `...::test_jornada_4_retaguarda_do_grupo_de_selecao`
- [X] T105 Lista de Ações 1 (privacidade, busca) em `...::test_privacidade_e_isolamento_do_laboratorio`
- [X] T106 [P] Contrato da pré-verificação (em ordem, desvio com faixa, nada gravado, `422` por campo, `404` outro laboratório, `409` já registrado) em `tests/api/routers/test_sample_receipt_check.py`
- [X] T107 [P] Contrato da busca e dos campos de manuseio na lista em `tests/api/routers/test_sample_receipt_check.py`
- [X] T108 [P] Texto do alerta na inconformidade em `tests/api/routers/test_sample_nonconformity_router.py`; tipo de desvio em `tests/unit/core/test_sample_temperature.py`

### Implementation

- [X] T109 `check_receipt` e `_pending_vial` em `src/pivma/core/sample_receipt_service.py`; rota `POST .../vials/{code}/check` em `src/pivma/routers/sample_receipt.py`; schema `SampleReceiptCheck`
- [X] T110 Campo `alert` em `NonconformityPublic` e `deviation_kind`
- [X] T111 `ReceiptVial` herda `VialSpecification` e ganha `lot` e `safe_handling_instructions`; busca `search` com `ReceiptVialFilters`
- [X] T112 Manual: guia `receber-amostras.md`, tutorial `recebimento-com-avaria.md`; `specs/040-sample-receipt-nonconformity/journeys.md`

## Phase 13: Orientação ao laboratório na decisão (2026-10-04)

**Goal**: fechar o ciclo da Jornada 4: o "parecer técnico orientador" de
Ricardo chega a Thiago pela plataforma e por e-mail (FR-047 a FR-049).

### Tests

- [X] T113 Jornada 4 estendida: Ricardo decide com orientação e Thiago a vê no frasco substituído, em `tests/integration/journeys/etapa_3_execucao_validacao/test_sample_receipt_journey.py::test_jornada_4_retaguarda_do_grupo_de_selecao`
- [X] T114 Jornada nova: Ricardo aceita com ressalva e orienta; Thiago recebe o e-mail, vê a orientação e o lote fecha, em `...::test_jornada_5_laboratorio_recebe_a_orientacao`
- [X] T115 [P] Orientação gravada e devolvida ao Grupo na inconformidade em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T116 [P] Orientação em branco conta como ausente em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T117 [P] Desclassificar aplica a orientação a todas as inconformidades encerradas juntas em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T118 [P] O laboratório vê a orientação no frasco decidido e nunca a justificativa em `tests/api/routers/test_sample_nonconformity_decision.py`
- [X] T119 [P] Outro laboratório não vê a orientação em `tests/api/routers/test_sample_receipt_isolation.py`
- [X] T120 [P] Um e-mail por pessoa do laboratório do frasco, com situação e orientação, sem justificativa, código novo nem identidade, em `tests/integration/notifications/test_sample_decision_email.py`
- [X] T121 [P] Outro laboratório e o Grupo de Seleção não recebem o e-mail da decisão em `tests/integration/notifications/test_sample_decision_email.py`
- [X] T122 [P] Sem e-mail configurado, a decisão é gravada e nenhum envio é pedido em `tests/integration/notifications/test_sample_decision_email.py`
- [X] T123 [P] Migração cria e remove a coluna `lab_guidance` em `tests/integration/migrations/`
- [X] T128 [P] Renderer do e-mail da decisão (situações, sem orientação, escape do HTML) em `tests/unit/notifications/test_sample_decision_email_renderer.py`

### Implementation

- [X] T124 Coluna `lab_guidance` em `SampleReceiptNonconformity` e migração
- [X] T125 `lab_guidance` em `NonconformityDecisionRequest`, `NonconformityPublic` e `ReceiptVial`
- [X] T126 `decide_nonconformity` grava a orientação e pede os e-mails; renderer `sample_receipt_decision_email`
- [X] T127 Manual (guia, tutorial, notificações, escopo), contrato, modelo de dados e `journeys.md`

## Notas da implementação

- T006 ficou em `tests/integration/bootstrap/test_template_phase_3.py`, junto
  dos demais testes da Etapa 3 nos templates.
- T041 (validador de `opened_at`) entrou junto com T032.
- T049 (visão cega pelo laboratório) entrou junto com T022, porque a mesma
  função serve as duas histórias.
- Os templates subiram de versão (3→4; dossiê 5→6) para que processos
  existentes não mudem; testes da Spec 031/036 que fixavam a ausência da
  Etapa 3 foram atualizados.
- T100: nenhuma dependência nova (`httpx` já vem de `httpx2`).
- Os blocos dos tutoriais `primeiro-processo`, `equipe-e-amostras` e
  `recebimento-com-avaria` foram executados contra uma API com banco
  descartável.

## Dependencies & Execution Order

- Setup (T001) → Foundational (T002–T010) → histórias.
- US1 (Phase 3) independe das demais.
- US3 (Phase 4) depende da Foundational; US4 e US5 dependem de US3 (mesmas rotas).
- US6 depende de US3; US7 depende de US6; US8 depende de US3 (e de US6 para a lista de inconformidades).
- US2 depende só da Foundational (T001) e pode ir em paralelo a US3–US8.
- Polish no fim.

## Parallel Example

```text
Phase 2: T002, T005, T006, T010 em paralelo (arquivos diferentes)
Phase 3: T012–T020 em paralelo; depois T021 → T022
Phase 9 inteira em paralelo às Phases 4–8
```

## Implementation Strategy

1. MVP: Setup + Foundational + US1 + US3 (cadastro e recebimento em ordem).
2. US4, US5 (validação e isolamento) antes de expor ao frontend.
3. US6 + US7 (o núcleo da #71).
4. US2 e US8.
5. Manual e suíte completa.
