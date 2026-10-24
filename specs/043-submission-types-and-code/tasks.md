---

description: "Tarefas da Spec 043: terminologia dos tipos e código da submissão"
---

# Tasks: Terminologia dos tipos e código da submissão

**Input**: Design documents from `specs/043-submission-types-and-code/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/process-templates.md, quickstart.md

**Tests**: obrigatórios (AGENTS.md, constituição V, `testing-methodology`).
- Cada história começa pela jornada. Depois vêm os testes focados, um por
  comportamento observável, e só então a implementação.
- As duas jornadas ficam no mesmo módulo,
  `tests/integration/journeys/etapa_1_submissao_triagem/test_submission_types_and_code.py`,
  uma função por história. A docstring do módulo descreve a persona
  (proponente recém-cadastrado), o estado inicial (deploy novo) e as duas
  jornadas em prosa, citando "Spec 043, US1" e "Spec 043, US2". O preparo
  usa `bootstrap_fresh_deploy`, `sign_up` e `log_in`; as chamadas usam
  `journey_client`. A jornada não consulta o banco.
- Nos testes focados, confira o `code` do erro (`not_found`), não a
  mensagem. Toda recusa confere também que nada mudou (nenhum
  `ProcessInstance` novo).
- Escritas pelo `client` nos testes de rota levam
  `ORIGIN = {'Origin': 'https://testserver'}`.
- Relógio: `monkeypatch.setattr('pivma.core.process_engine.utc_now', …)`
  com um `datetime` em UTC (research R4).
- Limpeza dos testes que fazem commit. Na Spec 043, dois testes gravam
  pelo gerador de código fora da transação do teste, com
  `AsyncSession(engine)`:
  `test_concurrent_process_creation_yields_distinct_crcodes` (T034) e
  `test_criacao_que_espera_outra_desfeita_recebe_o_numero_livre` (T035b).
  Fora da Spec 043, `test_sample_concurrency.py`
  e `test_per_laboratory_concurrency.py` também criam processos commitados
  (pelas fábricas) e apagam os usuários no fim: o `_purge` deles passa a
  apagar antes a linha do contador que referencia esses usuários (T041a).
  Os testes que apagam tudo com `TRUNCATE` já cobrem a tabela nova, e os
  que montam `ProcessInstance` com código explícito não tocam o contador.
  Nos dois testes do gerador que fazem commit (T034 e T035b):
  - o `finally` apaga, nesta ordem, os registros já apagados hoje e a linha
    de `process_code_sequences` do ano usado;
  - o `finally` roda mesmo quando a criação falha, e não depende da lista de
    processos criados para apagar o contador;
  - o teste começa apagando a linha do ano, caso uma execução anterior
    interrompida a tenha deixado.
  Os demais testes do gerador (T033, T035, T035a, T036 a T039) usam a
  fixture `session`, cujo rollback já desfaz o contador.
- O banco de testes vive num contêiner do Testcontainers, que remove tudo no
  fim da sessão. Nada do banco sobra na máquina.
- Nomes de teste descrevem o objetivo e o desfecho
  (`test_primeira_submissao_do_ano_recebe_o_numero_0001`).

**Regras de código** (`karpathy-guidelines`):
- Chaves de tipos e formulários não mudam (FR-002). Não renomear arquivos
  YAML (research R9).
- Nada de migração de dados: o preview é descartável e a produção começa
  vazia.
- Não subir `version` nos YAMLs (research R8).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Registrar o estado da máquina antes de qualquer execução, num arquivo do scratchpad da sessão (fora do repositório): `git status --porcelain --ignored` na raiz e `docker ps -a`, `docker volume ls` e `docker image ls` (base para T049)
- [X] T002 Adicionar `tzdata` às dependências de produção em `pyproject.toml` e atualizar `poetry.lock` e `uv.lock` (research R4)

---

## Phase 2: Foundational

Coluna e tabela novas, usadas pelas duas histórias.

### Testes da fundação

- [X] T003 Teste de migração em `tests/integration/migrations/test_submission_types_and_code_migration.py`, no padrão de `test_decision_rejected_points_migration.py` (`PREVIOUS = 'a3d5f7b9c1e2'`): o upgrade cria `process_templates.display_order` como `INTEGER NULL` e preserva as linhas existentes com o valor nulo
- [X] T004 No mesmo arquivo: o upgrade cria `process_code_sequences` com `year INTEGER` chave primária, `last_value INTEGER NOT NULL` e as colunas do `AuditMixin`; o downgrade remove a tabela e a coluna

### Implementação da fundação

- [X] T005 Em `src/pivma/core/database/models.py`: `ProcessTemplate.display_order: Mapped[int | None]` (default `None`) e o modelo `ProcessCodeSequence(AuditMixin)` com `__tablename__ = 'process_code_sequences'`, `year` chave primária e `last_value` não nulo (data-model.md)
- [X] T006 Migração `migrations/versions/<rev>_submission_types_and_code.py` com `down_revision = 'a3d5f7b9c1e2'`, upgrade e downgrade conforme T003 e T004

**Checkpoint**: `poetry run pytest tests/integration/migrations/test_submission_types_and_code_migration.py` passa.

---

## Phase 3: User Story 1 - Proponente escolhe entre os quatro tipos com os nomes novos (Priority: P1) 🎯 MVP

**Goal**: a lista de tipos traz os quatro tipos mantidos, na ordem do BraCVAM, com nomes e descrições novos; a Prova de Conceito sai do sistema.

**Independent Test**: num deploy novo, um usuário lista os tipos e recebe os quatro na ordem e com os textos da tabela; criar submissão com `proof_of_concept` falha com 404.

### Tests for User Story 1

- [X] T007 [US1] Jornada `test_proponente_ve_os_tipos_na_ordem_do_bracvam_e_cria_submissao` em `tests/integration/journeys/etapa_1_submissao_triagem/test_submission_types_and_code.py`. Passos: (1) deploy novo; usuário se cadastra e entra; (2) lista `GET /processes/templates` e vê exatamente `pre_validated_method`, `validated_method_dossier`, `scope_extension`, `me_too_validation`, nessa ordem, com os nomes e descrições da tabela de Clarifications e `pagination.total_items == 4`; (3) abre o formulário do primeiro tipo (`GET /processes/templates/pre_validated_method/forms/submission_pre_validated_v1`) e vê o nome "Formulário de Submissão - Método Novo"; (4) cria a submissão com `pre_validated_method` e recebe 201 com a tarefa `proposal_submission` em `READY`; (5) tenta criar com `proof_of_concept` e recebe 404; (6) `GET /processes` mostra só a submissão do passo 4
- [X] T008 [P] [US1] Teste de rota em `tests/api/routers/test_process_router.py`: substituir as 5 chaves esperadas pelas 4 mantidas e conferir a ordem de `data` e `sort == {'by': 'display_order', 'order': 'asc'}`; o detalhe de `pre_validated_method` passa a ter `name == 'Método Novo'`
- [X] T009 [P] [US1] Teste de rota em `tests/api/routers/test_process_router.py`: nenhum nome ou descrição da listagem contém "Fitness", "Me-Too", "Peer-Review" nem "Validation-Ready" (SC-001)
- [X] T010 [P] [US1] Teste de rota em `tests/api/routers/test_process_router.py`: um template criado direto no banco sem `display_order` aparece depois dos quatro tipos (edge case)
- [X] T011 [P] [US1] Teste de rota em `tests/api/routers/test_process_router.py`: dois templates criados no banco com o mesmo `display_order` saem ordenados pela chave (edge case, paginação estável)
- [X] T012 [P] [US1] Teste de rota em `tests/api/routers/test_process_router.py`: `GET /processes/templates/proof_of_concept` responde 404 `not_found`
- [X] T013 [P] [US1] Teste de rota em `tests/api/routers/test_process_router.py`: `POST /processes` com `template_key: 'proof_of_concept'` responde 404 `not_found` e nenhum `ProcessInstance` é criado (FR-005)
- [X] T014 [P] [US1] Teste de bootstrap em `tests/integration/bootstrap/test_submission_types_bootstrap.py` (novo): grava antes, com `sync_template_from_dict`, um dicionário mínimo montado no próprio teste (o YAML da Prova de Conceito não existe mais depois de T024): `process_template` com `key: proof_of_concept` e uma fase sem atividades, mais o formulário `submission_proof_of_concept_v1` com um campo; depois de `bootstrap_all_templates`, o template fica com `is_active = False` e `deleted_at` preenchido (FR-004)
- [X] T015 [P] [US1] No mesmo arquivo: depois de `bootstrap_all_templates`, o formulário `submission_proof_of_concept_v1` fica com `deleted_at` preenchido (FR-004)
- [X] T016 [P] [US1] No mesmo arquivo: depois de `bootstrap_all_templates`, os quatro tipos têm `display_order` 1 a 4 na ordem da tabela (data-model.md)
- [X] T017 [P] [US1] Teste unitário em `tests/unit/core/test_template_loader.py`: a validação de ordem recusa YAML sem `display_order`, com 0, com número negativo, com texto e com booleano, levantando `ValidationError` cuja mensagem cita a chave do tipo; aceita 1 (FR-003a)
- [X] T018 [P] [US1] Teste de bootstrap em `tests/integration/bootstrap/test_submission_types_bootstrap.py`: com `monkeypatch` em `pivma.bootstrap_process_templates.load_yaml_template` devolvendo um dos YAMLs sem `display_order`, `bootstrap_all_templates` num banco vazio levanta `ValidationError` que cita a chave do tipo, e nenhum `ProcessTemplate` fica gravado, nem dos YAMLs lidos antes dele (FR-003a, edge case)
- [X] T019 [P] [US1] Em `tests/unit/core/test_template_loader.py`, `test_bootstrap_all_templates_loads_official_processes`: trocar os nomes antigos pelos da tabela, retirar a tupla da Prova de Conceito e conferir os nomes novos dos formulários "Formulário de Submissão - <nome do tipo>" (FR-001, FR-001a)

### Implementation for User Story 1

- [X] T020 [P] [US1] `src/pivma/templates_data/01_pre_validated_method.yaml`: `name: "Método Novo"`, descrição da tabela, `display_order: 1`, formulário `submission_pre_validated_v1` com `name: "Formulário de Submissão - Método Novo"`
- [X] T021 [P] [US1] `src/pivma/templates_data/04_validated_method_dossier.yaml`: `name: "Método Novo – Dossiê Completo"`, descrição da tabela, `display_order: 2`, formulário `submission_validated_dossier_v1` com `name: "Formulário de Submissão - Método Novo – Dossiê Completo"`
- [X] T022 [P] [US1] `src/pivma/templates_data/02_scope_extension.yaml`: `name: "Extensão do Domínio de Aplicação"`, descrição da tabela (sem "Fitness for Purpose"), `display_order: 3`, formulário `submission_scope_extension_v1` com `name: "Formulário de Submissão - Extensão do Domínio de Aplicação"`
- [X] T023 [P] [US1] `src/pivma/templates_data/03_me_too_validation.yaml`: `name: "Método Similar"`, descrição da tabela, `display_order: 4`, formulário `submission_me_too_v1` com `name: "Formulário de Submissão - Método Similar"`
- [X] T024 [US1] Apagar `src/pivma/templates_data/05_proof_of_concept.yaml`
- [X] T025 [US1] Em `src/pivma/bootstrap_process_templates.py`: função de validação da ordem ("inteiro maior ou igual a 1", recusa `bool`); `bootstrap_all_templates` lê todos os YAMLs e valida a ordem de cada um numa primeira passada, e só depois chama `sync_template_from_dict` para cada um, de modo que um YAML inválido não deixa nenhum template gravado; `_sync_process_template_and_version` grava `pt_data.get('display_order')` na criação e na atualização (research R2)
- [X] T026 [US1] Em `src/pivma/routers/processes.py`, `list_templates`: `order_by=(ProcessTemplate.display_order.asc().nulls_last(), ProcessTemplate.key)` e `SortApplied(by='display_order', order='asc')` (research R1)

### Testes existentes afetados pela remoção (US1)

- [X] T027 [P] [US1] Retirar `proof_of_concept` das listas de chaves em `tests/api/routers/test_sample_activity_unlock.py` e `tests/api/routers/test_activity_type_extension.py`; trocar "Método Pré-Validado" por "Método Novo" nas docstrings de `tests/integration/journeys/etapa_1_submissao_triagem/test_pre_validated_method_triage.py` e `test_return_review_via_triage.py`
- [X] T028 [P] [US1] Retirar `proof_of_concept` dos mapas chave → arquivo/versão em `tests/integration/bootstrap/test_template_phase_2.py` e `tests/integration/bootstrap/test_template_phase_3.py`
- [X] T029 [P] [US1] Retirar `proof_of_concept` de `CANONICAL_TEMPLATE_KEYS` em `tests/integration/database/test_activity_access_columns.py`
- [X] T030 [P] [US1] Retirar o caso parametrizado da Prova de Conceito em `tests/api/routers/test_form_submission.py`
- [X] T031 [P] [US1] Em `tests/unit/core/test_first_deploy_forms.py`: apagar `test_preliminary_form_covers_all_nine_sections` e retirar `submission_proof_of_concept_v1` de `test_triage_form_deactivated_and_submission_forms_active`
- [X] T031a [P] [US1] Em `tests/api/routers/test_listing_processes.py`: `test_templates_envelope_ordered_by_name` passa a `test_templates_envelope_ordered_by_display_order` e confere `sort == {'by': 'display_order', 'order': 'asc'}` (achado na suíte completa; a ordem dos itens já é coberta por T008)

**Checkpoint**: a jornada de T007 e os testes T008 a T019 passam; `grep -rn proof_of_concept src tests` só encontra os testes que provam a ausência.

---

## Phase 4: User Story 2 - Submissão recebe um código sequencial legível (Priority: P2)

**Goal**: o código da submissão segue `VAL-<ano>-<n:04d>`, com sequência anual no horário de Brasília, sem repetir e sem pular número.

**Independent Test**: criar submissões em sequência, em paralelo, com falha no meio e em anos diferentes, e conferir os códigos.

### Tests for User Story 2

- [X] T032 [US2] Jornada `test_proponente_recebe_codigos_sequenciais_do_ano` no mesmo módulo de T007. Passos: (1) deploy novo; usuário se cadastra e entra; (2) cria a primeira submissão e vê `code == f'VAL-{ano}-0001'`, com o ano de Brasília calculado no teste; (3) cria a segunda e vê `VAL-{ano}-0002`; (4) `GET /processes` mostra as duas com esses códigos
- [X] T033 [P] [US2] Teste de integração em `tests/integration/database/test_process_code_generation.py`: num banco sem linha do ano, a primeira `instantiate_process` gera `VAL-<ano>-0001` e a segunda `VAL-<ano>-0002` (FR-006, FR-007)
- [X] T034 [P] [US2] No mesmo arquivo, ajustar `test_concurrent_process_creation_yields_distinct_crcodes`: os dois códigos são `{VAL-<ano>-0001, VAL-<ano>-0002}`, com o ano de Brasília; a limpeza apaga também a linha de `process_code_sequences` (FR-008)
- [X] T035 [P] [US2] No mesmo arquivo, estender `test_failed_instantiation_rolls_back_all_process_records`: depois da falha, não existe linha de `process_code_sequences` e a criação seguinte, sem falha, gera `VAL-<ano>-0001` (FR-009)
- [X] T035a [P] [US2] No mesmo arquivo, `test_falha_com_contador_existente_nao_consome_numero`: com a linha do ano já criada por `VAL-<ano>-0001`, uma criação que falha não consome número e a seguinte recebe `VAL-<ano>-0002` (FR-009)
- [X] T035b [P] [US2] No mesmo arquivo, `test_criacao_que_espera_outra_desfeita_recebe_o_numero_livre`, nos casos sem linha do ano e com `last_value = 5`: a segunda conexão fica parada na trava da primeira (`pg_stat_activity` com `wait_event_type = 'Lock'`); a primeira faz rollback e a segunda recebe `VAL-<ano>-0001` ou `VAL-<ano>-0006` (FR-008, FR-009). Limpeza como em T034, apagando também o usuário
- [X] T036 [P] [US2] No mesmo arquivo: com o relógio em 2026, gera `VAL-2026-0001`; com o relógio em 2027, a criação seguinte gera `VAL-2027-0001` (FR-007)
- [X] T037 [P] [US2] No mesmo arquivo: com o relógio em `2027-01-01T01:00Z` (22h de 31/12/2026 em Brasília), o código usa 2026 (FR-006, cenário 7)
- [X] T038 [P] [US2] No mesmo arquivo: com a linha do ano em `last_value = 9999`, a criação gera `VAL-<ano>-10000` (cenário 6)
- [X] T039 [P] [US2] No mesmo arquivo: a linha de `process_code_sequences` guarda em `created_by` quem criou o primeiro processo do ano e em `updated_by` quem criou o seguinte (constituição II)

### Implementation for User Story 2

- [X] T040 [US2] Em `src/pivma/core/process_engine.py`, `generate_process_code(session, creator_user_id)`: ano por `utc_now().astimezone(ZoneInfo('America/Sao_Paulo')).year`; upsert `insert(ProcessCodeSequence).values(year=…, last_value=1, created_by=creator).on_conflict_do_update(index_elements=['year'], set_={'last_value': ProcessCodeSequence.last_value + 1, 'updated_by': creator}).returning(ProcessCodeSequence.last_value)`; retorna `f'VAL-{year}-{n:04d}'`. Retirar o import de `secrets` se ficar sem uso (research R3, R4, R5)
- [X] T041 [US2] Em `src/pivma/core/process_engine.py`, `instantiate_process`: passar `creator_user_id` para `generate_process_code`
- [X] T041a [US2] Em `tests/integration/database/test_sample_concurrency.py` e `tests/integration/database/test_per_laboratory_concurrency.py`, `_purge` apaga a linha de `process_code_sequences` criada ou atualizada pelos usuários do teste antes de apagar os usuários (achado na suíte completa: violação de chave estrangeira)

**Checkpoint**: a jornada de T032 e os testes T033 a T039, com T035a e T035b, passam.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T042 [P] `src/pivma/templates_data/README.md`: documentar `process_template.display_order` (obrigatório, inteiro ≥ 1, define a ordem de `GET /processes/templates`) e retirar o exemplo do `05_proof_of_concept.yaml`; o manual inclui este arquivo em `manual/referencia/templates-yaml.md`
- [X] T043 [P] `manual/referencia/templates.md`: tabela com os quatro tipos na ordem nova, nomes novos e nomes dos formulários; sem a Prova de Conceito; a listagem ordena por `display_order`
- [X] T044 [P] `manual/guias/enviar-uma-proposta.md`: trocar o exemplo `proof_of_concept` por `pre_validated_method` e explicar o formato do código (`VAL-<ano>-<n>`, sequência anual no horário de Brasília)
- [X] T045 [P] `manual/explicacao/escopo.md`: registrar os quatro tipos de submissão e o formato do código, no estado atual
- [X] T046 Conferir SC-005: `grep -rn "proof_of_concept\|Prova de Conceito" src tests manual README.md` só encontra os testes que provam a ausência (`test_submission_types_bootstrap.py`, a jornada de T007 e os testes de 404 em `test_process_router.py`)
- [X] T047 Rodar `poe lint`, `poe test` e `poe docs-build` e relatar o resultado real
- [X] T048 Rodar `poe test` duas vezes seguidas e conferir que a segunda passa, para provar que nenhum teste deixa estado para o seguinte
- [X] T049 Depois do commit, limpar a máquina comparando com a base de T001: remover arquivos e pastas novos no repositório que não estão no commit (incluindo `.specify/feature.json`) e contêineres, volumes e imagens Docker criados durante o trabalho; apagar o arquivo de base e o scratchpad da sessão. Não tocar no que já existia antes (por exemplo `.venv/`, `.env`, `htmlcov/`, `site/`, `.coverage`), que é do usuário; relatar o que foi removido e o que ficou

---

## Dependencies & Execution Order

### Phase Dependencies

- T001 vem antes de tudo. T002 não bloqueia US1; precisa estar pronto antes de US2.
- T049 é a última tarefa, depois do commit.
- Foundational (T003 a T006) bloqueia as duas histórias.
- US1 e US2 são independentes entre si depois da fundação.
- Polish depende das duas histórias.

### Within Each User Story

- Jornada e testes focados antes da implementação; eles falham primeiro.
- US1: YAMLs (T020 a T024) antes do bootstrap (T025); a rota (T026) depende só da fundação.
- US2: T040 antes de T041.

### Parallel Opportunities

- T008 a T019 tocam arquivos diferentes ou casos independentes no mesmo arquivo.
- T020 a T023: um YAML cada.
- T027 a T031: arquivos de teste diferentes.
- T033 a T039: casos independentes em `test_process_code_generation.py`.
- T042 a T045: páginas diferentes.

## Parallel Example: User Story 1

```text
T020 01_pre_validated_method.yaml
T021 04_validated_method_dossier.yaml
T022 02_scope_extension.yaml
T023 03_me_too_validation.yaml
```

## Implementation Strategy

### MVP

Fundação + US1: o BraCVAM já vê os tipos certos na ordem certa.

### Incremental Delivery

1. Setup e fundação.
2. US1 → testes verdes → demonstrável.
3. US2 → testes verdes.
4. Polish: documentação e suíte completa.

## Notes

- Rastreabilidade: T007 a T031 → FR-001 a FR-005, FR-010; T032 a T041 → FR-006 a FR-009; T042 a T045 → FR-011.
- Não editar `specs/015-first-deploy-baseline/`: é histórico.
