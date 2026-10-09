---

description: "Tarefas da Spec 041: template de coleta de dados"
---

# Tasks: Template de coleta de dados

**Input**: Design documents from `specs/041-collection-template/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md, quickstart.md

**Tests**: obrigatórios (AGENTS.md, constituição V, `testing-methodology`).
- Cada história começa pela jornada. Depois vêm os testes focados, um por
  comportamento observável, e só então a implementação.
- Nos testes focados, confira o `code` do erro, não a mensagem.
- Toda recusa confere também que nada mudou.
- Usuário com a permissão: `await catalog_manager(session)` da fábrica de
  T007. Não use a fixture `bracvam_user`: o banco de teste nasce com
  `create_all`, sem o catálogo de permissões, e o perfil BraCVAM só recebe
  as permissões que existem na tabela. A exceção é a T073: ela usa
  `bracvam_user` depois que um helper da fábrica cria a linha da permissão.
  Usuário sem a permissão: fixture `user`.
- Escritas pelo `client` precisam do cabeçalho `Origin` confiável, como nos
  testes de `tests/api/routers/test_institutional_router.py`.

**Regras de código** (`karpathy-guidelines`):
- Sem classe de repositório, sem camada genérica de validação, sem
  tratamento de `IntegrityError` (research R5).
- Funções do serviço recebem `session` e o ator e devolvem modelos. O router
  monta os esquemas.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Adicionar `"openpyxl (>=3.1.5,<4.0.0)"` em `dependencies` de `pyproject.toml`, rodar `poetry lock` e `uv lock` e confirmar `poetry run python -c "import openpyxl"` (research R8)

---

## Phase 2: Foundational

**Purpose**: modelos, migração, permissão e fábrica, usados por todas as histórias.

**⚠️ CRITICAL**: nenhuma história começa antes desta fase.

- [X] T002 [P] Teste de migração em `tests/integration/migrations/test_collection_template_migration.py`, no padrão de `test_form_templates_manage_migration.py`:
  - o upgrade cria `collection_templates` e `collection_template_columns`, com os checks e os índices únicos parciais de data-model.md;
  - cria `process_instances.collection_template_id`, nulo, com FK e o índice `ix_process_instances_collection_template_id`;
  - insere a permissão `collection_templates.manage` com o id `00000000-0000-0000-0000-00000000010e`, sem linha em `access_profile_permissions`;
  - um processo que já existia fica com o vínculo nulo;
  - o downgrade remove tudo.
- [X] T003 [P] Atualizar `tests/integration/bootstrap/test_bootstrap_system.py` (US6, cenário 4): o catálogo canônico contém `collection_templates.manage`; a lista explícita da BraCVAM a inclui; `_BRACVAM_PERMISSION_COUNT` acompanha a mudança.
- [X] T004 Modelos em `src/pivma/core/database/models.py`, depois de `FormField`, seguindo data-model.md:
  - `CollectionTemplate(AuditMixin)`, tabela `collection_templates`: `name String(255)`, `description Text nulo`, `min_experiments Integer`, `min_replicates Integer`; checks `ck_collection_templates_min_experiments` (`min_experiments >= 1`) e `ck_collection_templates_min_replicates` (`min_replicates >= 1`); sem relação ORM com as colunas (o serviço as consulta em `active_columns`).
  - `CollectionTemplateColumn(AuditMixin)`, tabela `collection_template_columns`:
    - campos: `collection_template_id` FK, `label String(255)`, `key String(64)`, `column_type String(16)`, `required Boolean` padrão `False`, `options JSONB nulo`, `position Integer`;
    - checks `ck_collection_template_columns_type` (`column_type IN ('text','integer','decimal','date','select')`) e `ck_collection_template_columns_position` (`position >= 1`);
    - índices únicos parciais `uq_collection_template_columns_key_active` `(collection_template_id, key)` e `uq_collection_template_columns_position_active` `(collection_template_id, position)`, ambos com `postgresql_where=deleted_at IS NULL`, como `uq_form_fields_key_active`.
  - `ProcessInstance.collection_template_id: Mapped[UUID | None]`, FK `collection_templates.id`, `nullable=True`, `default=None`, `index=True`.
- [X] T005 Migração `migrations/versions/<rev>_collection_templates.py` com `down_revision = 'b7c3e1f2a9d4'`:
  - espelha T004, com o índice nomeado `ix_process_instances_collection_template_id`;
  - insere a permissão `collection_templates.manage`, id `00000000-0000-0000-0000-00000000010e`, descrição "Gerir o catálogo de templates de coleta de dados (colunas, mínimos e arquivo-modelo).";
  - o downgrade apaga a permissão, a coluna e as tabelas;
  - docstring citando a Spec 041 e o motivo de não compor perfis (research R9).
- [X] T006 Permissão:
  - constante `COLLECTION_TEMPLATES_MANAGE = 'collection_templates.manage'` em `src/pivma/core/authorization.py`, ao lado de `FORM_TEMPLATES_MANAGE`;
  - em `src/pivma/bootstrap_system.py`, a mesma entrada (id e descrição de T005) em `CANONICAL_PERMISSIONS` e o código na lista `'bracvam'` de `PROFILE_PERMISSION_MAPPINGS`.
- [X] T007 Fábrica `tests/factories/collection_template_factory.py`:
  - `template_payload(**overrides)`, com nome, descrição, `min_experiments=3` e `min_replicates=2`;
  - `column_payload(**overrides)`, com chave única por chamada, rótulo e tipo `text`;
  - `async def catalog_manager(session)`, que devolve `await _make_rbac_user(session, system_key='bracvam', name='BraCVAM', codes=('collection_templates.manage',))`, importado de `tests.conftest`; a chamada cria a linha da permissão no banco de teste;
  - `async def grant_catalog_permission(session, user)`, que dá a um usuário existente um perfil personalizado (`system_key='collection_editor'`) só com `collection_templates.manage`, criando a linha da permissão se faltar, no mesmo molde de `_make_rbac_user`;
  - `async def collection_template(session, actor, *, columns=())`, que grava o template e as colunas direto pelos modelos de T004, com `set_creation_audit(actor.id)`, sem depender do serviço da US1;
  - `async def linked_process(session, template_id, *, complete_definition: bool)`, que usa `receipt_process(session, freeze=False)` de `tests/factories/sample_receipt_factory.py`, grava `process.collection_template_id` e, se pedido, chama `sample_service.complete_sample_definition`.

**Checkpoint**: `alembic upgrade head` aplica, T002 e T003 passam, suíte existente verde.

---

## Phase 3: User Story 1 - Montar um template de coleta e baixar o arquivo-modelo (P1) 🎯 MVP

**Goal**: Beatriz cria o template, adiciona colunas, consulta, lista e baixa o arquivo-modelo em CSV e Excel.

**Independent Test**: template com as seis colunas de tipos mistos; os dois arquivos trazem os nove cabeçalhos na ordem (SC-001).

### Tests for User Story 1

- [X] T008 [US1] Jornada `test_bracvam_monta_template_e_baixa_arquivo_modelo` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`. Docstring do módulo: "Spec 041" e a descrição em prosa de cada jornada do arquivo.
  - Estado inicial: `bootstrap_fresh_deploy`. O administrador concede o perfil BraCVAM a Beatriz pela rota pública de RBAC. Beatriz entra com `log_in`.
  - Passos, cada um conferindo o que Beatriz vê:
    1. cria o template "Ensaio de citotoxicidade" e vê `columns: []` e `locked: false`;
    2. adiciona as seis colunas da US1 sem posição e vê as posições 1 a 6;
    3. consulta o template e vê as colunas na ordem;
    4. baixa o CSV: decodificado com `utf-8-sig`, tem uma linha e nove cabeçalhos;
    5. baixa o Excel: lido com `openpyxl`, traz os mesmos nove na linha 1;
    6. lista o catálogo e encontra o template.
- [X] T009 [P] [US1] Contrato: `POST /collection-templates` responde 201 com `columns == []`, `locked is False` e `created_by` igual ao ator (US1, cenário 1), em `tests/api/routers/test_collection_templates_router.py`
- [X] T010 [P] [US1] Contrato: a primeira coluna sem `position` recebe 1, e a seguinte recebe a maior posição ativa + 1 (US1, cenário 2; FR-008). A linha da coluna no banco tem `created_by` igual ao ator; comentar que a leitura no banco é necessária porque a resposta não expõe a autoria da coluna (constituição II). Arquivo: `tests/api/routers/test_collection_templates_router.py`
- [X] T011 [P] [US1] Contrato: coluna com `position: 2` num template com as posições 1 e 5 é aceita, e a consulta devolve a ordem 1, 2, 5 (US1, cenário 7), em `tests/api/routers/test_collection_templates_router.py`
- [X] T012 [P] [US1] Contrato: `GET /collection-templates/{id}` traz nome, descrição, mínimos, `locked` e cada coluna com `id`, `key`, `label`, `type`, `required`, `options` e `position` (US1, cenário 3), em `tests/api/routers/test_collection_templates_router.py`
- [X] T013 [P] [US1] Contrato: `GET /collection-templates/{id}` com id inexistente responde 404 `not_found`, em `tests/api/routers/test_collection_templates_router.py`
- [X] T014 [P] [US1] Contrato: `POST /collection-templates/{id}/columns` com template inexistente responde 404 `not_found`, em `tests/api/routers/test_collection_templates_router.py`
- [X] T015 [P] [US1] Contrato: a listagem devolve o envelope `data`, `pagination`, `filters_applied` e `sort` com `{"by": "name", "order": "asc"}`, cada item com `locked`, sem `columns` (US1, cenário 8), em `tests/api/routers/test_collection_templates_router.py`
- [X] T016 [P] [US1] Contrato: a listagem ordena pelo nome sem distinção de caixa e, no empate, pelo `id` ("beta", "Alfa", "alfa" → "Alfa"/"alfa" por id, depois "beta"), em `tests/api/routers/test_collection_templates_router.py`
- [X] T017 [P] [US1] Contrato: com três templates, `per_page=2&page=2` devolve um item, `total_items=3`, `total_pages=2`, `has_prev=true` e `has_next=false`, em `tests/api/routers/test_collection_templates_router.py`
- [X] T018 [P] [US1] Contrato: `POST /collection-templates` com campo desconhecido responde 422 `validation_error`, `fields[].code == 'extra_forbidden'`, em `tests/api/routers/test_collection_templates_router.py`
- [X] T019 [P] [US1] Contrato: `POST /collection-templates` com `name` vazio responde 422 com `string_too_short`, e com 256 caracteres, 422 com `string_too_long`; 255 caracteres é aceito, em `tests/api/routers/test_collection_templates_router.py`
- [X] T020 [P] [US1] Unitário: o cabeçalho é `codigo_amostra`, `experimento`, `replica` e as chaves por `position` crescente, mesmo com as colunas fora de ordem na entrada e posições não contíguas, em `tests/unit/core/test_collection_template_file.py`
- [X] T021 [P] [US1] Unitário: sem colunas, o cabeçalho tem só as três fixas, em `tests/unit/core/test_collection_template_file.py`
- [X] T022 [P] [US1] Unitário: o CSV começa com `b'\xef\xbb\xbf'`, separa por `;` e tem uma única linha, em `tests/unit/core/test_collection_template_file.py`
- [X] T023 [P] [US1] Unitário: o `.xlsx`, lido com `openpyxl.load_workbook`, tem uma planilha `resultados`, o cabeçalho na linha 1, `max_row == 1` e nenhuma validação de dados (`ws.data_validations.dataValidation == []`), em `tests/unit/core/test_collection_template_file.py`
- [X] T024 [P] [US1] Contrato: `GET /collection-templates/{id}/file?format=csv` responde 200 com `content-type` `text/csv; charset=utf-8`, `content-disposition` `attachment; filename="template-coleta-<id>.csv"` e o cabeçalho esperado no corpo (US1, cenário 4; FR-016). Uma das colunas tem o rótulo `'Viab.; "(%)" ção'`, e o cabeçalho continua só com chaves técnicas (Edge Cases), em `tests/api/routers/test_collection_templates_router.py`
- [X] T025 [P] [US1] Contrato: `?format=xlsx` responde 200 com `content-type` `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, nome `.xlsx` e o cabeçalho esperado ao ler o corpo (US1, cenário 5), em `tests/api/routers/test_collection_templates_router.py`
- [X] T026 [P] [US1] Contrato: o arquivo de um template sem colunas tem só as três fixas (US1, cenário 6), em `tests/api/routers/test_collection_templates_router.py`
- [X] T027 [P] [US1] Contrato: `?format=pdf` responde 422 `validation_error` com `literal_error`, e sem `format`, 422 com `missing`, em `tests/api/routers/test_collection_templates_router.py`
- [X] T028 [P] [US1] Contrato: o arquivo de um template inexistente responde 404 `not_found`, em `tests/api/routers/test_collection_templates_router.py`

### Implementation for User Story 1

- [X] T029 [P] [US1] Esquemas em `src/pivma/schemas.py`, todos com `extra='forbid'` nas entradas, seguindo contracts/http-api.md:
  - `ColumnType = Literal['text', 'integer', 'decimal', 'date', 'select']`;
  - `CollectionTemplateCreate`: `name` com 1 a 255 caracteres; `description: str | None = None`; `min_experiments` e `min_replicates` com `Field(ge=1)`;
  - `CollectionTemplateColumnCreate`: `key` com `pattern=r'^[a-z][a-z0-9_]{0,63}$'`; `label` com 1 a 255; `type: ColumnType`; `required: bool = False`; `options: list[Annotated[str, Field(min_length=1, max_length=255)]] | None = None`; `position: int | None = Field(default=None, ge=1)`;
  - saídas `CollectionTemplateColumnPublic`, `CollectionTemplateSummary`, `CollectionTemplatePublic(CollectionTemplateSummary)` com `columns`, e `CollectionTemplateListResponse` no envelope das outras listagens, com `NoFilters` e `SortApplied`.
- [X] T030 [US1] Serviço `src/pivma/core/collection_template_service.py`:
  - constantes `RESERVED_COLUMN_KEYS = ('codigo_amostra', 'experimento', 'replica')`, `CSV_MEDIA_TYPE` e `XLSX_MEDIA_TYPE`;
  - sem exceções novas: o serviço levanta `NotFoundError` (404), `ConflictError(message, code=...)` (409) e `ValidationError(message, code=...)` (422) de `process_engine`, que já carregam o `code`;
  - `create_template(session, actor_id, data)`, com `set_creation_audit(actor_id)`;
  - `get_template(session, template_id)`, que levanta not found;
  - `active_columns(session, template_id)`, ordenadas por `position`;
  - `locked_template_ids(session, template_ids) -> set[UUID]`, consulta única com `skip_soft_delete_filter=True`, juntando `ProcessInstance` a `ActivityInstance` com `key == SAMPLE_ACTIVITY_KEY` e `status == 'COMPLETED'` (research R2);
  - `lock_template_row(session, template_id)`, `SELECT ... FOR UPDATE` com `populate_existing`, que levanta not found; é pública porque `sample_service` também a chama (T089), e a docstring cita FR-019 e research R4;
  - `add_column(session, template_id, actor_id, data)`: trava a linha e grava com `set_creation_audit(actor_id)`, com a posição padrão = maior posição ativa + 1, ou 1;
  - `file_header(columns)`, `render_csv(header) -> bytes` (`csv.writer` com `delimiter=';'`, codificado em `utf-8-sig`) e `render_xlsx(header) -> bytes` (`openpyxl`, planilha `resultados`).
- [X] T031 [US1] Router `src/pivma/routers/collection_templates.py`, prefixo `/collection-templates`, tag `collection-templates`:
  - `CatalogManager = Annotated[User, Depends(require_permission(COLLECTION_TEMPLATES_MANAGE))]` em todas as rotas e `TrustedOrigin` nas escritas, como `routers/institutional.py`;
  - rotas `GET ''` (com `paginate_query`, `order_by=(func.lower(name), id)`, e `locked_template_ids` uma vez por página), `POST ''`, `GET /{id}`, `POST /{id}/columns` e `GET /{id}/file` com `format: Literal['csv', 'xlsx']` obrigatório;
  - o arquivo sai num `Response` com o `Content-Disposition` de research R7;
  - as exceções do serviço viram `api_error`, com o `code` delas.
- [X] T032 [US1] Registrar o router em `src/pivma/__init__.py` com `app.include_router(collection_templates.router)`.

**Checkpoint**: T008 a T028 verdes.

---

## Phase 4: User Story 2 - Recusar coluna inválida (P1)

**Goal**: cada violação gera recusa com código próprio, sem gravar. Também entram aqui as rotas de alteração (FR-002, FR-009).

**Independent Test**: cada violação contra um template existente; as colunas ficam iguais às de antes (SC-002).

### Tests for User Story 2

- [X] T033 [US2] Jornada `test_bracvam_corrige_colunas_recusadas` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`. Estado inicial igual ao de T008, com Beatriz e um template com uma coluna `viabilidade`:
  1. Beatriz tenta repetir uma chave e vê `duplicate_key`;
  2. tenta usar `replica` e vê `reserved_key`;
  3. tenta `select` sem opções e vê `invalid_options`;
  4. depois de cada recusa, consulta o template e vê as mesmas colunas;
  5. corrige cada pedido e vê a coluna aceita.
- [X] T034 [P] [US2] Contrato: chave igual à de uma coluna ativa responde 409 `duplicate_key` e as colunas não mudam (US2, cenário 1), em `tests/api/routers/test_collection_template_validation.py`
- [X] T035 [P] [US2] Contrato: chave `codigo_amostra`, `experimento` ou `replica` responde 409 `reserved_key` (parametrizado nas três; US2, cenário 2), em `tests/api/routers/test_collection_template_validation.py`
- [X] T036 [P] [US2] Contrato: chave fora do formato responde 422 `validation_error` com `fields[].field == 'key'` e `code == 'string_pattern_mismatch'`, parametrizado em `'Viabilidade'`, `'1abc'`, `'_abc'`, `'com espaco'`, `'com-hifen'`, `'acao_ç'`, `''` e `'a' * 65` (US2, cenário 3), em `tests/api/routers/test_collection_template_validation.py`
- [X] T037 [P] [US2] Contrato: chave `'a' * 64` é aceita (limite de FR-006), em `tests/api/routers/test_collection_template_validation.py`
- [X] T038 [P] [US2] Contrato: `type: 'boolean'` responde 422 com `literal_error` no campo `type` (US2, cenário 4), em `tests/api/routers/test_collection_template_validation.py`
- [X] T039 [P] [US2] Contrato: `select` sem `options` e com `options: []` responde 422 `invalid_options` (US2, cenário 5), em `tests/api/routers/test_collection_template_validation.py`
- [X] T040 [P] [US2] Contrato: `text` com `options` responde 422 `invalid_options` (US2, cenário 6), em `tests/api/routers/test_collection_template_validation.py`
- [X] T041 [P] [US2] Contrato: `select` com opção repetida responde 422 `invalid_options`, em `tests/api/routers/test_collection_template_validation.py`
- [X] T042 [P] [US2] Contrato: `select` com opção `''` responde 422 com `string_too_short` em `options.0`, em `tests/api/routers/test_collection_template_validation.py`
- [X] T043 [P] [US2] Contrato: posição já ocupada por coluna ativa responde 409 `position_taken` (US2, cenário 7), em `tests/api/routers/test_collection_template_validation.py`
- [X] T044 [P] [US2] Contrato: `position` 0 e -1 responde 422 com `greater_than_equal` (US2, cenário 8), em `tests/api/routers/test_collection_template_validation.py`
- [X] T045 [P] [US2] Contrato: `label` vazio responde 422 com `string_too_short`, em `tests/api/routers/test_collection_template_validation.py`
- [X] T046 [P] [US2] Contrato: `PATCH` de coluna `select` para `text` sem enviar `options` responde 422 `invalid_options` (US2, cenário 9), em `tests/api/routers/test_collection_template_validation.py`
- [X] T047 [P] [US2] Contrato: `PATCH` de coluna `select` para `text` com `options: null` responde 200 com `options is None` (US2, cenário 9), em `tests/api/routers/test_collection_template_validation.py`
- [X] T048 [P] [US2] Contrato: `PATCH` de coluna com a chave de outra coluna ativa responde 409 `duplicate_key`; com a própria chave, 200, em `tests/api/routers/test_collection_template_validation.py`
- [X] T049 [P] [US2] Contrato: `PATCH` de coluna para a posição de outra coluna ativa responde 409 `position_taken`; para a própria posição, 200, em `tests/api/routers/test_collection_template_validation.py`
- [X] T050 [P] [US2] Contrato: `PATCH` de coluna com `key: null` responde 422 `validation_error`, em `tests/api/routers/test_collection_template_validation.py`
- [X] T051 [P] [US2] Contrato: `PATCH` de coluna inexistente, ou com o `id` de um template que não é o dela, responde 404 `not_found`, em `tests/api/routers/test_collection_template_validation.py`
- [X] T052 [P] [US2] Contrato: `PATCH` de coluna altera `label` e `required`, responde 200 e preenche `updated_by` (FR-009), em `tests/api/routers/test_collection_templates_router.py`
- [X] T053 [P] [US2] Contrato: `POST /collection-templates` com `min_experiments: 0` e `PATCH` com `min_replicates: 0` respondem 422 com `greater_than_equal` (US2, cenário 10), em `tests/api/routers/test_collection_template_validation.py`
- [X] T054 [P] [US2] Contrato: `PATCH /collection-templates/{id}` com `name` e `description` responde 200 com os valores novos e `updated_by` do ator; `description: null` limpa a descrição (FR-002), em `tests/api/routers/test_collection_templates_router.py`
- [X] T055 [P] [US2] Contrato: `PATCH /collection-templates/{id}` com `name: null` ou `min_experiments: null` responde 422, em `tests/api/routers/test_collection_template_validation.py`
- [X] T056 [P] [US2] Contrato: `PATCH /collection-templates/{id}` de template inexistente responde 404 `not_found`, em `tests/api/routers/test_collection_template_validation.py`

### Implementation for User Story 2

- [X] T057 [P] [US2] Esquemas em `src/pivma/schemas.py`:
  - `CollectionTemplateUpdate`: os campos de `CollectionTemplateCreate`, todos opcionais;
  - `CollectionTemplateColumnUpdate`: os campos da criação, todos opcionais;
  - um `model_validator` recusa `null` explícito em todo campo, exceto `description` e `options`, lendo `model_fields_set`.
- [X] T058 [US2] Regras em `src/pivma/core/collection_template_service.py`, conferidas sob `lock_template_row` e com a própria coluna excluída das checagens de unicidade:
  - `reserved_key` (409) se a chave está em `RESERVED_COLUMN_KEYS`;
  - `duplicate_key` (409) se outra coluna ativa usa a chave;
  - `position_taken` (409) se outra coluna ativa usa a posição;
  - `invalid_options` (422) se `select` não tem opções, se outro tipo tem opções ou se há opção repetida.

  `add_column` chama essas regras. `update_column(session, template_id, column_id, actor_id, changes)` aplica `changes` sobre o estado atual, valida o resultado e preenche `set_update_audit`. Uma coluna de outro template ou excluída gera not found. `update_template(session, template_id, actor_id, changes)` aplica os campos enviados.
- [X] T059 [US2] Rotas `PATCH /collection-templates/{id}` e `PATCH /collection-templates/{id}/columns/{column_id}` em `src/pivma/routers/collection_templates.py`, com `CatalogManager` e `TrustedOrigin`, passando `payload.model_dump(exclude_unset=True)` ao serviço.

**Checkpoint**: T033 a T056 verdes; US1 continua verde.

---

## Phase 5: User Story 4 - Escolher o template de coleta ao criar o processo (P2)

**Goal**: o processo nasce com o vínculo, visível na consulta, na listagem e na trilha. Só quem tem a permissão informa o campo.

**Independent Test**: um processo com o campo e outro sem; recusas de template inexistente e de usuário sem a permissão.

### Tests for User Story 4

- [X] T060 [US4] Jornada `test_proponente_sem_permissao_e_bracvam_vinculam_template` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`. Estado inicial: `bootstrap_fresh_deploy`; o administrador concede o perfil BraCVAM a Beatriz pela rota pública de RBAC, e Beatriz cria um template.
  1. Paulo, recém-cadastrado, cria um processo sem o campo e vê `collection_template_id: null`;
  2. Paulo tenta com o campo e vê `forbidden`; sua listagem de processos segue com um só;
  3. Beatriz cria um processo com o template e vê o identificador na resposta, na consulta e na listagem;
  4. na trilha do processo, o `PROCESS_CREATED` traz o identificador.
- [X] T061 [P] [US4] Contrato: `catalog_manager` cria processo com `collection_template_id` existente, 201, e a resposta traz o identificador (US4, cenário 1), em `tests/api/routers/test_process_collection_template.py`
- [X] T062 [P] [US4] Contrato: `GET /processes/{id}` e `GET /processes` trazem o `collection_template_id` do processo vinculado e `null` no não vinculado (FR-023), em `tests/api/routers/test_process_collection_template.py`
- [X] T063 [P] [US4] Contrato: `user` cria processo sem o campo, 201 com `collection_template_id: null` (US4, cenário 2), em `tests/api/routers/test_process_collection_template.py`
- [X] T064 [P] [US4] Contrato: `catalog_manager` com `collection_template_id` inexistente recebe 404 `not_found` e a contagem de `ProcessInstance` não muda (US4, cenário 3), em `tests/api/routers/test_process_collection_template.py`
- [X] T065 [P] [US4] Contrato: `user` com `collection_template_id` existente recebe 403 `forbidden` e a contagem de `ProcessInstance` não muda (US4, cenário 4), em `tests/api/routers/test_process_collection_template.py`
- [X] T066 [P] [US4] Contrato: `user` com `collection_template_id` inexistente recebe 403 `forbidden`, não 404, porque a permissão vem antes (research R10), em `tests/api/routers/test_process_collection_template.py`
- [X] T067 [P] [US4] Contrato: com o campo, o `PROCESS_CREATED` traz `context_data['collection_template_id']`; sem o campo, o evento não tem a chave (FR-024), em `tests/api/routers/test_process_collection_template.py`
- [X] T068 [P] [US4] Contrato: um template travado (`linked_process(..., complete_definition=True)`) segue aceito na criação de processo novo, 201 (US3, cenário 6), em `tests/api/routers/test_process_collection_template.py`
- [X] T069 [P] [US4] Contrato: no `app.openapi()`, só o corpo de `POST /processes` tem a propriedade `collection_template_id`; nenhuma rota de processo a altera (US4, cenário 5; FR-025), em `tests/api/routers/test_process_collection_template.py`

### Implementation for User Story 4

- [X] T070 [P] [US4] Em `src/pivma/schemas.py`, `CreateProcessRequest.collection_template_id: UUID | None = None` e `ProcessInstanceDetail.collection_template_id: UUID | None = None`
- [X] T071 [P] [US4] Em `src/pivma/core/process_engine.py`, `instantiate_process` ganha o parâmetro `collection_template_id: UUID | None = None`. Ele grava o valor no `ProcessInstance` e o acrescenta como `str` ao `context_data` do `PROCESS_CREATED` só quando não é nulo.
- [X] T072 [US4] Em `src/pivma/routers/processes.py`, `create_process`:
  - com `body.collection_template_id` e sem `has_permission(session, current_user.id, COLLECTION_TEMPLATES_MANAGE)`, responde 403 `forbidden` antes de consultar o `template_key`;
  - depois do `template_key`, um template de coleta inexistente responde 404 `not_found` com "Template de coleta não encontrado.";
  - repassa o valor a `instantiate_process`;
  - preenche `collection_template_id` nos três `ProcessInstanceDetail(...)`: criar, listar e consultar.

**Checkpoint**: T060 a T069 verdes; os testes atuais de criação de processo passam sem alteração (SC-004).

---

## Phase 6: User Story 3 - Travar a estrutura depois que a Etapa 3 começa (P1)

**Goal**: depois da conclusão das amostras de um processo vinculado, nenhuma mudança estrutural entra, nem com operações simultâneas.

**Independent Test**: template vinculado, conclusão das amostras e cada alteração estrutural recusada; nome, descrição, consulta e download seguem aceitos.

### Tests for User Story 3

- [X] T073 [US3] Jornada `test_estrutura_trava_quando_a_definicao_das_amostras_conclui` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`.
  - Estado inicial: `study_team` de `tests/integration/journeys/sample_steps.py`, como em `test_sample_definition_journey.py`. Não usar `bootstrap_fresh_deploy`, porque `study_team` já carrega os templates.
  - Atores:
    - Beatriz é a fixture `bracvam_user`, a mesma que `open_sample_definition` usa para a triagem.
    - O proponente (`team.proponent`) recebe a permissão com `grant_catalog_permission(session, team.proponent)` da fábrica de T007. É estado inicial: o proponente já tem o perfil personalizado quando a jornada começa.
    - Esse helper cria a linha da permissão. A partir daí, Beatriz também tem a permissão, porque o perfil BraCVAM cobre toda permissão ativa, como em produção.
    - Com a permissão, o proponente pode informar o template ao criar o processo (FR-022).
  - Passos:
    1. Beatriz cria o template e vê `locked: false`;
    2. o proponente cria o processo com o template por meio de `open_sample_definition`, que ganha o parâmetro opcional `collection_template_id`, incluído no `POST /processes` quando informado; o processo segue até a definição das amostras;
    3. o Grupo de Seleção cadastra as substâncias com `register_substance` e conclui a definição;
    4. Beatriz consulta o template e vê `locked: true`;
    5. tenta adicionar uma coluna e vê `template_locked`;
    6. renomeia o template e baixa o CSV com sucesso.
- [X] T074 [P] [US3] Contrato: template vinculado a processo sem a definição concluída aceita adicionar (201) e alterar (200) coluna e mostra `locked: false` (US3, cenário 1), em `tests/api/routers/test_collection_template_lock.py`
- [X] T075 [P] [US3] Contrato: com a definição concluída, adicionar coluna responde 409 `template_locked` e as colunas não mudam (US3, cenário 2), em `tests/api/routers/test_collection_template_lock.py`
- [X] T076 [P] [US3] Contrato: com o template travado, `PATCH` de coluna responde 409 `template_locked` e a coluna não muda (US3, cenário 2), em `tests/api/routers/test_collection_template_lock.py`
- [X] T077 [P] [US3] Contrato: com o template travado, `PATCH` com `min_experiments` diferente do atual responde 409 `template_locked` (US3, cenário 3), em `tests/api/routers/test_collection_template_lock.py`
- [X] T078 [P] [US3] Contrato: com o template travado, `PATCH` com o nome novo e os mínimos iguais aos atuais responde 200 (research R3), em `tests/api/routers/test_collection_template_lock.py`
- [X] T079 [P] [US3] Contrato: com o template travado, `PATCH` só de `name` e `description` responde 200 (US3, cenário 4), em `tests/api/routers/test_collection_template_lock.py`
- [X] T080 [P] [US3] Contrato: com o template travado, a consulta e a listagem mostram `locked: true` e o download CSV responde 200 (US3, cenário 5), em `tests/api/routers/test_collection_template_lock.py`
- [X] T081 [P] [US3] Contrato: depois da conclusão, com o processo em `CLOSED`, `CANCELLED` ou `ARCHIVED` (parametrizado), o template continua travado e adicionar coluna responde 409 `template_locked` (US3, cenário 7; FR-017). O teste grava o status direto na sessão. Comentar o motivo: as transições de ciclo de vida têm testes próprios, e o travamento depende só do vínculo e da conclusão. Arquivo: `tests/api/routers/test_collection_template_lock.py`
- [X] T082 [P] [US3] Contrato: depois da conclusão, um processo excluído com `delete_process` (status `CANCELLED` e `deleted_at` preenchido) mantém o template travado (US3, cenário 7; research R2), em `tests/api/routers/test_collection_template_lock.py`
- [X] T083 [P] [US3] Contrato: com o template travado, a listagem mostra `locked: true` só para ele, e outro template da mesma página mostra `false`, em `tests/api/routers/test_collection_template_lock.py`
- [X] T084 [US3] Concorrência em `tests/api/routers/test_collection_template_concurrency.py`, no padrão de `test_sample_receipt_concurrency.py` (engine real, sessões próprias, `_truncate`):
  - a permissão vem de `catalog_manager` numa sessão própria; o processo vem de `linked_process(..., complete_definition=False)`;
  - uma sessão trava a linha do template com `FOR UPDATE` e marca a `sample_definition` como `COMPLETED`, sem `commit`;
  - em paralelo, dispara `POST /collection-templates/{id}/columns` e espera, consultando `pg_stat_activity` por até 5 s, que ela apareça com `wait_event_type = 'Lock'`. O teste espera um estado observável, não um tempo fixo;
  - depois do `commit`, a requisição responde 409 `template_locked` e nenhuma coluna é gravada (US3, cenário 8; FR-019).
- [X] T085 [US3] Concorrência no mesmo arquivo de T084. Prova que `complete_sample_definition` toma a trava; sem ela, o teste falha no passo do `pg_stat_activity`:
  - uma sessão trava a linha do template com `lock_template_row` e grava uma coluna, sem `commit`;
  - em paralelo, dispara `POST /processes/{id}/samples/complete` como o Grupo de Seleção do processo vinculado;
  - a requisição aparece em `pg_stat_activity` com `wait_event_type = 'Lock'` antes do `commit`, com o mesmo limite de 5 s de T084;
  - depois do `commit`, a conclusão responde 200, a coluna existe e o template aparece travado (FR-019).
- [X] T086 [US3] Concorrência no mesmo arquivo de T084: duas criações simultâneas com a mesma chave respondem `{201, 409}`, e a 409 traz `duplicate_key`, sem 500 (Edge Cases)
- [X] T087 [US3] Concorrência no mesmo arquivo de T084: duas criações simultâneas sem `position` respondem 201 com posições distintas (Edge Cases)

### Implementation for User Story 3

- [X] T088 [US3] Em `src/pivma/core/collection_template_service.py`:
  - `_ensure_unlocked(session, template_id)` levanta `template_locked` (409) quando `template_id in await locked_template_ids(session, [template_id])`;
  - `add_column` e `update_column` a chamam depois de `lock_template_row`;
  - `update_template`, quando `min_experiments` ou `min_replicates` vem em `changes`, segue esta ordem:
    1. chama `lock_template_row`;
    2. compara os mínimos enviados com os valores relidos sob a trava;
    3. só quando algum difere, chama `_ensure_unlocked` (research R3).

    Sem mínimos em `changes`, não trava a linha.
- [X] T089 [US3] Em `src/pivma/core/sample_service.py`, `complete_sample_definition`: depois de carregar o processo e antes do `commit`, se `process.collection_template_id` não é nulo, chamar `collection_template_service.lock_template_row(session, process.collection_template_id)`.

**Checkpoint**: T073 a T087 verdes; US1 e US2 continuam verdes; os testes de amostras existentes seguem verdes.

---

## Phase 7: User Story 5 - Excluir uma coluna antes do travamento (P3)

**Goal**: a exclusão lógica tira a coluna da consulta e do arquivo e libera a chave e a posição.

**Independent Test**: excluir, conferir a consulta e o arquivo, recriar com a mesma chave e posição.

### Tests for User Story 5

- [X] T090 [US5] Jornada `test_bracvam_exclui_coluna_e_reaproveita_a_chave` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`. Estado inicial igual ao de T008, com Beatriz e um template que tem a coluna `lote_reagente`:
  1. Beatriz exclui `lote_reagente` e vê 204;
  2. a consulta e o CSV não trazem mais a coluna;
  3. Beatriz recria uma coluna com a mesma chave e posição e vê 201.
- [X] T091 [P] [US5] Contrato: `DELETE /collection-templates/{id}/columns/{column_id}` responde 204, e a coluna some da consulta e do arquivo (US5, cenário 1), em `tests/api/routers/test_collection_templates_router.py`
- [X] T092 [P] [US5] Contrato: depois da exclusão, a linha no banco tem `deleted_at` e `deleted_by` do ator. Comentar que o efeito não é observável pela API (FR-010). Arquivo: `tests/api/routers/test_collection_templates_router.py`
- [X] T093 [P] [US5] Contrato: depois da exclusão, criar coluna com a mesma chave e a mesma posição responde 201 (US5, cenário 2), em `tests/api/routers/test_collection_templates_router.py`
- [X] T094 [P] [US5] Contrato: `DELETE` de coluna já excluída, inexistente ou de outro template responde 404 `not_found`, e `PATCH` de coluna excluída também (US5, cenário 3), em `tests/api/routers/test_collection_templates_router.py`
- [X] T095 [P] [US5] Contrato: `DELETE` de coluna de template vinculado sem a definição concluída responde 204 (US3, cenário 1), em `tests/api/routers/test_collection_template_lock.py`
- [X] T096 [P] [US5] Contrato: `DELETE` de coluna de template travado responde 409 `template_locked` e a coluna continua ativa (US3, cenário 2), em `tests/api/routers/test_collection_template_lock.py`

### Implementation for User Story 5

- [X] T097 [US5] `delete_column(session, template_id, column_id, actor_id)` em `src/pivma/core/collection_template_service.py`: chama `lock_template_row` e `_ensure_unlocked`, carrega a coluna ativa do template (ou not found) e chama `set_deletion_audit(actor_id)`. Rota `DELETE /collection-templates/{id}/columns/{column_id}`, 204, com `CatalogManager` e `TrustedOrigin`, em `src/pivma/routers/collection_templates.py`.

**Checkpoint**: T090 a T096 verdes.

---

## Phase 8: User Story 6 - Restringir a gestão do catálogo (P1)

**Goal**: só quem tem `collection_templates.manage` usa o catálogo. Admin e BraCVAM a recebem de fábrica.

**Independent Test**: cada rota com usuário sem a permissão, sem sessão e sem origem confiável.

A implementação já veio em T006, T031, T059 e T097. Esta fase prova os limites.

### Tests for User Story 6

- [X] T098 [US6] Jornada `test_acesso_ao_catalogo_depende_da_permissao` em `tests/integration/journeys/etapa_2_planejamento_preparacao/test_collection_template_journey.py`. Estado inicial: `bootstrap_fresh_deploy`; Paulo se cadastra com `sign_up` e entra com `log_in`:
  1. Paulo, recém-cadastrado, tenta listar o catálogo e criar um template e vê `forbidden`;
  2. o administrador concede o perfil BraCVAM a Paulo;
  3. Paulo entra de novo, cria o template e o vê na listagem.
- [X] T099 [P] [US6] Contrato: `user` em `POST /collection-templates` recebe 403 `forbidden` e não há template no banco, em `tests/api/routers/test_collection_template_security.py`
- [X] T100 [P] [US6] Contrato: `user` em `PATCH /collection-templates/{id}` recebe 403 `forbidden` e o nome não muda, em `tests/api/routers/test_collection_template_security.py`
- [X] T101 [P] [US6] Contrato: `user` em `POST /collection-templates/{id}/columns` recebe 403 `forbidden` e não há coluna nova, em `tests/api/routers/test_collection_template_security.py`
- [X] T102 [P] [US6] Contrato: `user` em `PATCH .../columns/{column_id}` recebe 403 `forbidden` e a coluna não muda, em `tests/api/routers/test_collection_template_security.py`
- [X] T103 [P] [US6] Contrato: `user` em `DELETE .../columns/{column_id}` recebe 403 `forbidden` e a coluna continua ativa, em `tests/api/routers/test_collection_template_security.py`
- [X] T104 [P] [US6] Contrato: `user` em `GET /collection-templates`, `GET /collection-templates/{id}` e `GET .../file?format=csv` recebe 403 `forbidden` (US6, cenário 2), em `tests/api/routers/test_collection_template_security.py`
- [X] T105 [P] [US6] Contrato: sem sessão, cada uma das 8 rotas responde 401 `not_authenticated` (parametrizado por rota; US6, cenário 3), em `tests/api/routers/test_collection_template_security.py`
- [X] T106 [P] [US6] Contrato: `catalog_manager` sem `Origin` confiável recebe 403 `invalid_origin` em cada uma das 5 escritas e nada é gravado (FR-029), em `tests/api/routers/test_collection_template_security.py`
- [X] T107 [P] [US6] Contrato: um usuário com perfil personalizado (`system_key="form_editor"`) que só tem `form_templates.manage`, criado com `_make_rbac_user` de `tests/conftest.py`, recebe 403 em `POST /collection-templates`, em `tests/api/routers/test_collection_template_security.py`
- [X] T108 [P] [US6] Contrato: um usuário com perfil personalizado (`system_key="collection_editor"`, fora de Admin e BraCVAM) que só tem `collection_templates.manage` cria template (201) e o lista (200), em `tests/api/routers/test_collection_template_security.py`

**Checkpoint**: T098 a T108 verdes.

---

## Phase 9: Polish & Cross-Cutting Concerns

Textos do manual passam pela skill `stop-slop` e descrevem só o estado atual.

- [X] T109 [P] `manual/referencia/rotas.md`: seção "Templates de coleta" com as 8 rotas, a permissão, os corpos e as respostas de contracts/http-api.md; em `POST /processes`, `GET /processes` e `GET /processes/{id}`, o campo `collection_template_id` e o 403
- [X] T110 [P] `manual/referencia/erros.md`: `duplicate_key`, `reserved_key`, `position_taken`, `template_locked` e `invalid_options`, com status e quando ocorrem
- [X] T111 [P] `manual/referencia/eventos.md`: `collection_template_id` opcional no `context_data` de `PROCESS_CREATED`
- [X] T112 [P] `manual/referencia/perfis-permissoes-cargos.md`: `collection_templates.manage`, quem a recebe e o que libera, inclusive o campo em `POST /processes`
- [X] T113 [P] `manual/explicacao/escopo.md`: o template de coleta como entregue; fora do escopo, as colunas derivadas, os ensaios fracassados, a reordenação, a exclusão do template e o acesso do laboratório ao arquivo-modelo (#30)
- [X] T114 [P] Guia novo `manual/guias/montar-template-de-coleta.md` com:
  - criar o template, adicionar colunas e baixar o arquivo;
  - quando o template trava, explicando o travamento e o glossário "template de coleta" e "arquivo-modelo";
  - links para `rotas.md` e `erros.md`.
  
  Mais a entrada em `manual/guias/index.md` e em `nav` de `mkdocs.yml`, depois de "Definir amostras cegas".
- [X] T115 Rodar `poe lint`, `poe test` e `poe docs-build` e corrigir o que falhar. Informar só os resultados que rodaram de fato.
- [X] T116 Seguir `specs/041-collection-template/quickstart.md`, passos 1 a 9, e registrar no PR o que foi conferido.

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (T001) → Foundational (T002–T007) → histórias → Polish.
- A ordem das histórias é US1 → US2 → US4 → US3 → US5 → US6.
  - A US1 cria o serviço, o router e os esquemas, e as outras histórias os estendem.
  - A US4 vem antes da US3 porque a jornada da US3 (T073) cria o processo com `collection_template_id`, campo que só existe depois de T070–T072.
  - A US6 tem prioridade P1, mas fica por último: as rotas e a permissão já existem desde T006, T031, T059 e T097, e a fase só prova os limites.

### Within Each User Story

- A jornada e os testes focados vêm antes e falham antes da implementação.
- Esquemas → serviço → router.
- T007 depende de T004 (modelos).
- T089 depende de T030 (`lock_template_row`) e de T088.
- T097 depende de T088 e T089.

### Parallel Opportunities

- T002 e T003 em paralelo. T004 → T005 e T004 → T007 em sequência.
- Os testes `[P]` de cada história usam arquivos de teste independentes do código. Escreva-os em paralelo, mas tarefas `[P]` no mesmo arquivo exigem edição coordenada.
- T029 em paralelo com os testes da US1. T070 e T071 em paralelo.
- T109 a T114 em paralelo.

---

## Parallel Example: User Story 1

```bash
Task: "T020-T023 unitários de arquivo-modelo em tests/unit/core/test_collection_template_file.py"
Task: "T009-T019 contratos de criação, consulta e listagem em tests/api/routers/test_collection_templates_router.py"
Task: "T029 esquemas em src/pivma/schemas.py"
```

---

## Implementation Strategy

### MVP

1. Setup e Foundational.
2. US1: catálogo e arquivo-modelo, com a permissão já aplicada.
3. Validar com T008 e SC-001.

### Incremental Delivery

1. US2: regras e alterações.
2. US4: o vínculo no processo.
3. US3: o travamento e a concorrência, que é o risco crítico da issue.
4. US5: a exclusão de coluna.
5. US6: os limites de acesso.
6. Polish e o PR para `develop`.

---

## Notes

- Rastreabilidade: cada teste cita a história e o cenário, ou o FR, no nome ou na docstring.
- Nada de colunas derivadas, ensaios fracassados, reordenação, exclusão do template ou histórico de mudanças (FR-030, research R12).
- Commit só quando o usuário pedir.

---

## Phase 10: Convergence

Achados da revisão externa da entrega, aceitos pelo usuário em 2026-10-09.

- [X] T117 CRITICAL: exigir `TrustedOrigin` nas seis rotas de escrita de `src/pivma/routers/processes.py`, com teste em `tests/api/routers/test_process_trusted_origin.py` (sem `Origin`, `Origin` estranha, nada criado, Bearer dispensado) per Constitution III, research R11 (contradicts)
- [X] T118 Limitar mínimos e `position` a 2147483647 em `src/pivma/schemas.py` e recusar a posição automática acima disso com `position_taken` em `src/pivma/core/collection_template_service.py`, com testes de borda em `tests/api/routers/test_collection_template_validation.py` per FR-001, FR-008 (partial)
- [X] T119 Responder 404 para coluna inexistente antes de `template_locked` em `update_column` e `delete_column` de `src/pivma/core/collection_template_service.py`, com teste de `PATCH` e `DELETE` em `tests/api/routers/test_collection_template_lock.py` per contracts/http-api.md (contradicts)
- [X] T120 Exigir `TrustedOrigin` em `save_form_draft` e `submit_form` de `src/pivma/routers/forms.py`, com o caso no teste de `tests/api/routers/test_process_trusted_origin.py` per Constitution III, research R11 (contradicts)
- [X] T121 Trocar o código da posição automática acima de 2147483647 de `position_taken` para `position_limit_reached` em `src/pivma/core/collection_template_service.py`, que substitui o código de T118, com o teste em `tests/api/routers/test_collection_template_validation.py` per research R6 (contradicts)
- [X] T122 No downgrade da migração `e8a4c2f61b37`, remover as associações ativas e excluídas de `collection_templates.manage` em `access_profile_permissions` antes de remover a permissão, para que rollback após o bootstrap não viole a FK. Estender `tests/integration/migrations/test_collection_template_migration.py` para executar a composição canônica antes do downgrade e verificar que as associações também foram removidas.
