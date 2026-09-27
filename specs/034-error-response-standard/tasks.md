---

description: "Task list — Spec 034: Formato único das respostas de erro"
---

# Tasks: Formato único das respostas de erro

**Input**: Design documents from `specs/034-error-response-standard/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [quickstart.md](quickstart.md)

**Tests**: Obrigatórios (AGENTS.md). Seguem `.agents/skills/fastapi-testing-methodology/`: cada tarefa de teste cobre um comportamento observável, e os testes vêm antes da implementação de cada história. Níveis de risco:
- **Crítico:** nenhum valor enviado nem detalhe interno na resposta, a senha sem expor a regra e o `404` de ocultação preservado. Camadas: unidade e API.
- **Alto:** formato em todos os status, status HTTP inalterados e códigos existentes preservados. Camada: API.
- **Médio:** mensagens em português e OpenAPI. Camadas: unidade e API.

**Organization**: Base comum → US1 (formato e códigos) → US2 (validação por campo) → US3 (documentação).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: user story da spec (US1…US3)
- Comandos com `poetry run`; testes isolados com `--no-cov`

## Convenções de teste desta feature

- Autenticação: `authenticate(client, user)` de `tests/api/routers/test_rbac_router.py`. Endpoints mutáveis exigem `Origin: https://testserver`.
- Asserção de formato: helper `_assert_error(response, status, code)` em `tests/api/test_error_contract.py`. Ele confere o status, que `response.json()` tem exatamente a chave `detail`, que `detail` é objeto com `code == code` e `message` texto não vazio, e que nenhuma chave `loc`, `input`, `msg` ou `type` aparece em `json.dumps(response.json())`.
- Erro `500`: `TestClient(app, raise_server_exceptions=False)` e uma rota de teste registrada só no teste, que levanta `RuntimeError('segredo interno')`.
- Mensagens em português: conferir contra uma lista de mensagens inglesas conhecidas (`'Not authenticated'`, `'Forbidden'`, `'User not found'`, `'Invalid credentials'`, `'Field required'`...) e contra o prefixo `'Value error'`.

---

## Phase 1: Setup

- [X] T001 Rodar `poetry run pytest -q` e `poetry run ruff check .` na branch `feat/034-error-response-standard` e anotar em `specs/034-error-response-standard/tasks.md` (Notes) quantos testes passaram e falharam.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `api_error`, códigos genéricos, tradução de validação e os schemas de erro.

### Tests (`tests/unit/core/test_errors.py`)

- [X] T002 [P] `test_api_error_builds_detail_object`: `api_error(404, 'not_found', 'Processo não encontrado.')` devolve `HTTPException` com `status_code == 404` e `detail == {'code': 'not_found', 'message': 'Processo não encontrado.'}`.
- [X] T003 `test_api_error_keeps_context`: `api_error(422, 'missing_sds', 'Há substâncias sem SDS.', substance_ids=['a'])` inclui `substance_ids` no `detail`.
- [X] T004 `test_generic_error_covers_every_status`: `generic_error(status)` devolve código e mensagem da tabela do data-model para 400, 401, 403, 404, 405, 409, 413, 422, 500 e 503; um status fora da tabela usa `http_<status>` e uma mensagem genérica em português.
- [X] T005 `test_field_errors_map_location_and_path`: `field_errors([{'loc': ('body', 'values', 'method_title'), 'type': 'missing', 'msg': 'Field required', 'input': {}}])` devolve `[{'location': 'body', 'field': 'values.method_title', 'code': 'missing', 'message': 'Campo obrigatório.'}]`.
- [X] T006 `test_field_errors_never_include_input`: para erros com `input` e `ctx` preenchidos, nenhum item tem as chaves `input`, `ctx` nem `url`, e o valor de `input` não aparece em `json.dumps` do resultado.
- [X] T007 `test_field_errors_translate_common_types`: `missing`, `string_too_short`, `string_too_long`, `greater_than_equal`, `less_than_equal`, `int_parsing`, `uuid_parsing`, `enum`, `literal_error`, `bool_parsing` e `value_error` (e-mail) têm mensagem em português. Limites vindos de `ctx` (ex.: `le=100`) aparecem na mensagem ("Deve ser menor ou igual a 100.").
- [X] T008 `test_field_errors_unknown_type_uses_generic_message`: tipo `'algo_novo'` resulta em `code: 'algo_novo'` e `message: 'Valor inválido.'`.
- [X] T009 `test_field_errors_value_error_uses_validator_message`: `type: 'value_error'` com `msg: 'Value error, Informe ao menos um campo.'` resulta em `message: 'Informe ao menos um campo.'` (o prefixo do Pydantic sai; a mensagem é do próprio validador do projeto).
- [X] T010 `test_field_errors_hide_password_rule`: qualquer erro cujo `loc` contenha `'password'` resulta em `code: 'invalid'` e `message: 'Senha inválida.'`, sem limites nem `ctx`.

### Implementation

- [X] T011 Criar `src/pivma/core/errors.py`, sem depender do app:
  - `GENERIC_ERRORS: dict[int, tuple[str, str]]`, com os códigos e mensagens de "Códigos genéricos por status" do data-model;
  - `generic_error(status) -> tuple[str, str]`;
  - `api_error(status, code, message, **context) -> HTTPException`;
  - `VALIDATION_MESSAGES` (tipo do Pydantic → mensagem em português, com formatação a partir de `ctx` para limites);
  - `field_errors(errors) -> list[dict]` com as regras de T005–T010.
- [X] T012 Em `src/pivma/schemas.py`, seção "Erros", criar com `Field(description=...)` em todos os campos:
  - `FieldError`: `location: Literal['body', 'query', 'path', 'header', 'cookie']`, `field: str`, `code: str`, `message: str`;
  - `ErrorDetail`: `code: str`, `message: str`, `fields: list[FieldError] | None = None`, `model_config = ConfigDict(extra='allow')` para o contexto dos códigos específicos;
  - `ErrorResponse`: `detail: ErrorDetail`.
- [X] T013 Em `src/pivma/schemas.py`, traduzir para português as mensagens dos validadores Pydantic em inglês (`'At least one field is required'`, `'Update fields cannot be null'` e os demais que `grep -n "raise ValueError" src/pivma/schemas.py` apontar), porque elas passam a aparecer em `fields[].message` (T009).

**Checkpoint**: `poetry run pytest tests/unit/core/test_errors.py -q --no-cov` verde.

---

## Phase 3: User Story 1 - Decidir pelo código, não pelo texto (Priority: P1) 🎯 MVP

**Goal**: todo erro 4xx e 5xx no formato `{"detail": {code, message}}`, com códigos explícitos e mensagens em português.

**Independent Test**: um erro de cada classe responde no formato único com o código esperado.

### Tests (`tests/api/test_error_contract.py`)

- [X] T014 [P] [US1] `test_unauthenticated_uses_not_authenticated`: `GET /tasks` sem cookie → `_assert_error(401, 'not_authenticated')`.
- [X] T015 [US1] `test_untrusted_origin_uses_invalid_origin`: `POST /processes` autenticado sem `Origin` → `_assert_error(403, 'invalid_origin')`.
- [X] T016 [US1] `test_missing_permission_uses_forbidden`: `GET /users` sem `users.read` → `_assert_error(403, 'forbidden')`.
- [X] T017 [US1] `test_admin_route_uses_admin_only`: `GET /admin/logs/operational` como usuário comum → `_assert_error(403, 'admin_only')`.
- [X] T018 [US1] `test_invalid_credentials_code`: `POST /auth/login` com senha errada → `_assert_error(401, 'invalid_credentials')`.
- [X] T019 [US1] `test_hidden_resource_404_matches_missing`: `GET /processes/{id}` de um processo existente sem acesso e de um id inexistente → os dois `_assert_error(404, 'not_found')` com a mesma `message` (FR-009).
- [X] T020 [US1] `test_unknown_route_uses_not_found`: `GET /nao-existe` → `_assert_error(404, 'not_found')`.
- [X] T021 [US1] `test_wrong_method_uses_method_not_allowed`: `PUT /tasks` → `_assert_error(405, 'method_not_allowed')`.
- [X] T022 [US1] `test_business_rule_keeps_specific_code`: decidir a triagem fora de andamento → `_assert_error(409, 'invalid_transition')` (FR-005).
- [X] T023 [US1] `test_attachment_errors_keep_status_and_code`: anexo vazio → `_assert_error(400, 'empty_file')`; anexo acima do limite → `_assert_error(413, 'file_too_large')`.
- [X] T024 [US1] `test_unhandled_exception_uses_internal_error`: rota de teste que levanta `RuntimeError('segredo interno')` → `_assert_error(500, 'internal_error')`, e `'segredo interno'` não aparece na resposta.
- [X] T025 [US1] `test_ai_unavailable_code`: com o provedor de IA levantando `AIProviderError` na rota que responde `503` → `_assert_error(503, 'ai_unavailable')`.
- [X] T026 [US1] `test_self_deactivation_code`: `DELETE /users/{próprio id}` → `_assert_error(409, 'self_deactivation')`.
- [X] T027 [US1] `test_invite_codes`: aceite com e-mail diferente → `_assert_error(403, 'invite_email_mismatch')`; aceite de convite expirado → `_assert_error(409, 'invite_expired')`.
- [X] T028 [US1] `test_error_messages_are_portuguese`: nos casos de T014–T021, `message` não está na lista de mensagens inglesas conhecidas (ver Convenções).
- [X] T029 [US1] `test_status_codes_unchanged`: parametrizado com os pares (rota, cenário, status) de T014–T027, conferindo só o status (SC-005).

### Implementation

- [X] T030 [US1] Criar `src/pivma/errors.py` com `register_error_handlers(app)`:
  - handler de `starlette.exceptions.HTTPException`: `detail` `dict` com `code` passa, completando `message` pelo genérico se faltar; `detail` `str` vira `{code, message}` com o código genérico do status e a própria mensagem; preserva `exc.headers`;
  - handler de `Exception`: `500` com `internal_error` e a mensagem genérica, registrando a exceção com `logger.exception`.

  Em `src/pivma/__init__.py`, chamar `register_error_handlers(app)` e remover `sanitize_password_validation_error` (a senha passa a ser tratada em T047).
- [X] T031 [US1] Em `src/pivma/core/process_engine.py`, `ProcessEngineError.__init__(self, message, *, code=None)` guarda `self.code`; `ValidationError` repassa `code`. Traduzir as mensagens em inglês levantadas no arquivo. Em `src/pivma/core/attachment_service.py`, conferir que `AttachmentError` já tem `code` e manter os códigos atuais.
- [X] T032 [US1] Em `src/pivma/dependencies.py`, trocar os erros por `api_error`: `not_authenticated` → `(401, 'not_authenticated', 'Sessão ausente ou expirada.')`, origem → `(403, 'invalid_origin', 'Origem da requisição não confiável.')`, permissão → `(403, 'forbidden', ...)`, admin → `(403, 'admin_only', 'Acesso restrito a administradores.')`. Preservar os `headers` que existirem.
- [X] T033 [P] [US1] `src/pivma/routers/auth.py`: `invalid_credentials` (401) e mensagens em português.
- [X] T034 [P] [US1] `src/pivma/routers/users.py`: `not_found` ("Usuário não encontrado."), `self_deactivation`, `last_administrator`, `duplicate` (cadastro) e as demais mensagens em português. Traduzir as mensagens de domínio usadas por ele em `src/pivma/core/authorization.py` (`'At least one administrator must remain'`, `'Another account already has Administrator'`, `'Active user not found'`, `'Permission not found'`).
- [X] T035 [P] [US1] `src/pivma/routers/rbac.py`: os helpers `conflict`/`not_found` passam a usar `api_error`; `inactive_entity` para perfil/usuário inativos; `duplicate` para nome reservado ou estado ativo em conflito; mensagens em português.
- [X] T036 [P] [US1] `src/pivma/routers/institutional.py`: helpers com `api_error`; `inactive_entity` para instituição/laboratório/afiliação inativos; `conflict` para "laboratório não pertence à instituição"; `not_found` em português.
- [X] T037 [P] [US1] `src/pivma/routers/processes.py`: `_retirement_http_error` e `_submission_http_error` com o `code` da exceção ou o genérico; `f'Erro ao instanciar processo: {e!s}'` vira `api_error(500, 'internal_error', ...)` com log da exceção (R4); templates não encontrados com `not_found`.
- [X] T038 [P] [US1] `src/pivma/routers/process_participants.py`: helpers `not_found`/`conflict`/`forbidden` com `api_error`; `process_closed` para "Processo encerrado não aceita..."; `duplicate` para designação e convite pendente duplicados; mensagens em português.
- [X] T039 [P] [US1] `src/pivma/routers/invites.py` e `src/pivma/core/invite_service.py`: `invite_email_mismatch` (403), `invite_expired` e `invite_not_pending` (409) via `code` nas exceções de domínio; `_not_found` com `api_error`.
- [X] T040 [P] [US1] `src/pivma/routers/forms.py`: `_attachment_http_error` com `api_error` (mantendo `_ATTACHMENT_ERROR_STATUS` e os códigos); `form_submitted` e `not_a_file_field` como estão; demais pontos com `api_error` e mensagens em português.
- [X] T041 [P] [US1] `src/pivma/routers/samples.py`: `_http_error` com `api_error`, mantendo `invalid_transition`, `invalid_cas`, `duplicate_cas`, `no_substances`, `missing_sds` (com `substance_ids`) e `no_laboratories`.
- [X] T042 [P] [US1] `src/pivma/routers/triage.py`, `src/pivma/routers/return_review.py`, `src/pivma/routers/pre_evaluation.py`, `src/pivma/routers/ai_evaluations.py` e `src/pivma/routers/tasks.py`: pontos de erro com `api_error`; `ai_unavailable` (503) em `pre_evaluation`; mensagens em português (inclusive as de `src/pivma/core/evaluation_service.py`, `pre_evaluation_service.py` e `return_review_service.py` que `grep` apontar em inglês).
- [X] T043 [US1] Ajustar ao formato novo (comparar `detail['code']`, ou `detail['message']` onde o teste confere o texto), sem mudar o que verificam, os 17 arquivos que comparam `detail`: `tests/api/routers/test_return_review.py`, `test_user_router.py`, `test_process_retirement.py`, `test_process_lifecycle.py`, `test_form_submission.py`, `test_rbac_security.py`, `test_user_listing_security.py`, `test_form_attachments.py`, `test_user_failures.py`, `test_user_update.py`, `test_institutional_security.py`, `test_process_submission_update.py`, `test_rbac_router.py`, `test_participant_security.py`, `test_participant_router.py`, `test_samples_router.py` e `test_auth_router.py`. Registrar em Notes as mensagens esperadas que mudaram.

**Checkpoint**: T014–T029 verdes e suíte completa verde.

---

## Phase 4: User Story 2 - Erros de validação apontam os campos (Priority: P1)

**Goal**: `422` de validação com `fields`, mensagens em português, sem valores enviados.

**Independent Test**: cadastro com dois campos inválidos responde `validation_error` com um item por campo, sem os valores.

### Tests (`tests/api/test_error_contract.py`)

- [X] T044 [P] [US2] `test_validation_lists_each_field`: `POST /users` com `email: 'nao-e-email'` e sem `full_name` → `_assert_error(422, 'validation_error')`, com `detail.fields` contendo um item `location: body, field: email` e um `field: full_name` (`code: missing`, `message: 'Campo obrigatório.'`).
- [X] T045 [US2] `test_validation_never_echoes_input`: no mesmo pedido, `'nao-e-email'` não aparece em `json.dumps(response.json())` (SC-003).
- [X] T046 [US2] `test_query_validation_points_to_parameter`: `GET /tasks?per_page=101` autenticado → item com `location: query`, `field: per_page`, `code: less_than_equal`.
- [X] T047 [US2] `test_password_validation_hides_rule`: `POST /users` com senha de 3 caracteres → item `field: password`, `code: invalid`, `message: 'Senha inválida.'`; a senha enviada e o número mínimo de caracteres não aparecem na resposta (FR-010).
- [X] T048 [US2] `test_form_values_errors_use_fields`: submissão de formulário com campo obrigatório vazio → `_assert_error(422, 'invalid_form_values')` com `fields[0] == {'location': 'body', 'field': 'values.<field_key>', 'code': <código do domínio>, 'message': <mensagem>}`, sem a chave `errors`.
- [X] T049 [US2] `test_domain_field_error_keeps_format`: CAS inválido em `POST /processes/{id}/samples` → `_assert_error(422, 'invalid_cas')`.
- [X] T050 [US2] `test_validation_messages_are_portuguese`: nenhum `fields[].message` de T044–T047 está na lista de mensagens inglesas nem começa com `'Value error'`.

### Implementation

- [X] T051 [US2] Em `src/pivma/errors.py`, handler de `RequestValidationError`: `422` com `{'code': 'validation_error', 'message': 'Dados inválidos.', 'fields': field_errors(exc.errors())}`.
- [X] T052 [US2] Em `src/pivma/routers/forms.py` (nos dois pontos de `invalid_form_values`), montar `api_error(422, 'invalid_form_values', 'Há campos do formulário com valores inválidos.', fields=[...])`, convertendo cada `{field_key, code, message}` de `ValidationError.errors` em `{'location': 'body', 'field': f'values.{field_key}', 'code', 'message'}`. Sem `errors`, usar `api_error(422, 'validation_error', str(e))`.
- [X] T053 [US2] Rodar `grep -rn "'errors'\]\|\[\"errors\"\]\|'loc'\|'msg'" tests` e ajustar ao formato novo os testes que leem a lista antiga de validação ou `errors` de `invalid_form_values`.

**Checkpoint**: T044–T050 verdes e suíte completa verde.

---

## Phase 5: User Story 3 - Códigos documentados (Priority: P2)

### Tests (`tests/api/test_error_openapi.py`)

- [X] T054 [P] [US3] `test_error_schemas_documented`: `ErrorResponse`, `ErrorDetail` e `FieldError` existem em `app.openapi()['components']['schemas']`, com `description` em todos os campos.
- [X] T055 [US3] `test_validation_responses_point_to_error_response`: toda resposta `422` em `paths` referencia `#/components/schemas/ErrorResponse`, e `HTTPValidationError`/`ValidationError` não estão nos componentes.
- [X] T056 [US3] `test_openapi_is_cached`: duas chamadas a `app.openapi()` devolvem o mesmo objeto.

### Implementation

- [X] T057 [US3] Em `src/pivma/errors.py`, `install_openapi(app)`: substitui `app.openapi` por uma função que gera o schema original uma vez, troca as referências a `HTTPValidationError` por `ErrorResponse` nas respostas `422`, garante `ErrorResponse`/`ErrorDetail`/`FieldError` nos componentes (a partir de `ErrorResponse.model_json_schema(ref_template=...)`), remove `HTTPValidationError` e `ValidationError` e guarda o resultado em `app.openapi_schema`. Chamar em `src/pivma/__init__.py`.
- [X] T058 [US3] Conferir que os testes de contrato OpenAPI existentes (`tests/api/routers/test_user_listing.py::test_list_users_openapi_matches_versioned_contract`, `test_auth_router.py`, `test_tasks_openapi.py`, `test_references_openapi.py`) continuam verdes, e ajustar só o que comparar respostas `422`.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T059 [P] Atualizar `README.md`, "Convenções de Erro": formato `{"detail": {code, message, fields}}`, tabela dos códigos genéricos por status, códigos específicos, `fields` com `location`/`field`/`code`/`message`, mensagens em português, garantia de nunca repetir valores enviados; e a nota de que o frontend deve decidir pelo `code`.
- [X] T060 Rodar `poetry run pytest -q` com cobertura e `poetry run ruff check . && poetry run ruff format --check .`; comparar com T001 e registrar em Notes a cobertura de `src/pivma/core/errors.py` e `src/pivma/errors.py`.
- [ ] T061 Executar `specs/034-error-response-standard/quickstart.md` numa API local e registrar em Notes; se não for possível, registrar o motivo.
- [X] T062 Registrar em Notes as mudanças de contrato para o changelog único (Specs 032–034): o formato, os códigos genéricos, os códigos novos, `fields` na validação e em `invalid_form_values` (antes `errors`), e as mensagens em português.

---

## Dependencies & Execution Order

- **Setup → Foundational**: bloqueiam tudo.
- **US1**: depende da Foundational. T031 (`code` nas exceções) antes de T037–T042. T033–T042 são arquivos diferentes e podem correr em paralelo.
- **US2**: depende da Foundational e de T030 (arquivo `errors.py`). Independe das trocas de roteadores da US1, exceto `forms.py` (T040 antes de T052).
- **US3**: depende de T012 (schemas) e T030.
- **Polish**: depende de todas.

### Parallel Opportunities

- T002 (unidade) com T014 (API).
- T033–T042: um arquivo cada.
- T044 e T054 em paralelo.

## Parallel Example: User Story 1

```text
T033 auth.py       T037 processes.py             T041 samples.py
T034 users.py      T038 process_participants.py  T042 triage/return_review/pre_evaluation/ai_evaluations/tasks
T035 rbac.py       T039 invites.py
T036 institutional.py  T040 forms.py
```

## Implementation Strategy

### MVP First

A base comum mais os handlers (T030) já colocam 100% dos erros no formato, com códigos genéricos. É o mínimo para o frontend. T031–T042 acrescentam os códigos específicos e as mensagens em português.

### Incremental Delivery

1. Base comum e handlers: formato garantido.
2. Códigos específicos e mensagens, arquivo a arquivo.
3. Validação por campo.
4. OpenAPI.
5. README e notas; em seguida, o changelog único das Specs 032–034.

Um PR único na `develop`.

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- Commit após cada grupo; mensagens `feat(errors): ...` / `test(errors): ...`.
- **Linha de base (T001)**: 1184 passaram, 1 pulado; `ruff check .` limpo.
- **Handlers antes dos roteadores**: com T030 (handlers globais), 12 dos 16 testes de contrato já passavam; os demais dependiam dos códigos específicos (T033–T042). O handler de `RequestValidationError` (T051) e os `fields` de formulário (T052) entraram junto com os roteadores; T044–T050 confirmaram o comportamento.
- **T013**: mensagens de validadores traduzidas: `'Invalid password'`, `'At least one field is required'`, `'Update fields cannot be null'`, `'permission_codes must be unique'`, `'laboratory_id is required for laboratory roles'`, `'laboratory_id is not allowed for this role'`.
- **T014–T029** ficaram em `tests/api/routers/test_error_contract.py` (e não em `tests/api/`), junto dos demais testes de API. `POST /processes` não exige origem confiável; o cenário de `invalid_origin` usa `DELETE /users/{id}` com `users.manage`.
- **`value_error` de e-mail**: o Pydantic não usa o prefixo `'Value error, '` nesse caso; a mensagem vira `'E-mail inválido.'`. Os demais `value_error` sem prefixo usam `'Valor inválido.'`.
- **T031**: `ProcessEngineError` ganhou `code` opcional. Com isso, `getattr(exc, 'code', padrão)` passou a devolver `None`; `samples.py` usa `exc.code or 'invalid_transition'`.
- **T034/T035**: `ensure_administrator_remains` levanta `LastAdministratorError(ValueError)`, para os roteadores de usuários e RBAC darem `last_administrator` sem comparar texto.
- **T037**: três mensagens de template não encontrado repetiam a chave enviada na URL (FR-004) e passaram a ser fixas. `f'Erro ao instanciar processo: {e!s}'` virou mensagem fixa, com o detalhe no log. Código existente não listado na spec: `invalid_submission_values` (mantido, `errors` → `fields`).
- **T040/T052**: `invalid_form_values` e `invalid_submission_values` usam `form_field_errors` (`field: values.<chave>`).
- **T043**: 13 arquivos de teste ajustados (os 17 previstos; 4 já comparavam `detail.code`). `tests/api/routers/test_user_router.py` foi editado à mão, sem `ruff format` (o arquivo tem diferença de formatação antiga da versão local do ruff).
- **Mensagens em inglês remanescentes** ficam fora das respostas: CLI `bootstrap_rbac`, `'Invalid subject'` (JWT, convertido em `not_authenticated`) e validação de configuração.
- **T061**: não executada. O roteiro exige uma API local; os seis passos são cobertos por T014, T020, T044–T047 e T055.
- **T062 — mudanças de contrato para o changelog único (Specs 032–034)**:
  - Todo erro: `{"detail": {"code", "message"}}`; mensagens em português. **Quebra** para quem lia `detail` como texto.
  - Validação: `detail.fields` com `location`, `field`, `code`, `message`, no lugar da lista `loc`/`msg`/`type`/`input`. Senha: `code: invalid`, sem regra.
  - `invalid_form_values`/`invalid_submission_values`: `errors` vira `fields` (`field: values.<chave>`), e o objeto ganha `message`.
  - Rota inexistente, método não permitido e erro inesperado no mesmo formato (`not_found`, `method_not_allowed`, `internal_error`).
  - Códigos genéricos por status e códigos novos (`invalid_credentials`, `invalid_origin`, `admin_only`, `invite_email_mismatch`, `invite_expired`, `invite_not_pending`, `self_deactivation`, `last_administrator`, `inactive_entity`, `process_closed`, `duplicate`, `ai_unavailable`). Status HTTP inalterados.
  - Swagger: `ErrorResponse` nas respostas `422`.
- **T060**: suíte final com `--cov`: **1239 passaram, 1 pulado, 0 falhas** (55 a mais que a linha de base). Cobertura total 93%; `core/errors.py` 91% (sem cobertura: caminhos defensivos de `generic_error`/`_message` com `ctx` incompleto) e `errors.py` 98%. `ruff check .` limpo. `ruff format --check` acusa só `src/pivma/core/invite_service.py` (trecho não alterado, `_role_assignment_activity_is_completed`) e `tests/api/routers/test_user_router.py`, os mesmos casos antigos de versão do ruff.
