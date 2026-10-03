---
description: "Tarefas da Spec 037 — autogestão de nome e senha da própria conta"
---

# Tasks: Autogestão de Nome e Senha da Própria Conta

**Input**: `specs/037-self-profile-update/` (plan.md, spec.md, research.md, data-model.md, contracts/auth-me.openapi.yaml, quickstart.md)

**Tests**: obrigatórios (AGENTS.md e Constituição V). Granularidade definida com a skill `fastapi-testing-methodology`: um teste por comportamento observável. A lógica do `model_validator` tem testes unitários e o comportamento HTTP tem testes de API. Os testes de cada história vêm antes da implementação dela e devem falhar antes do código.

**Organization**: tarefas agrupadas por história de usuário. Use a skill `andrej-karpathy-skills:karpathy-guidelines` em cada tarefa de código.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: US1, US2 ou US3, conforme `spec.md`

## Convenções para os testes desta feature

- Arquivos: `tests/api/routers/test_auth_router.py` (API), `tests/unit/schemas/test_user_schemas.py` (schema) e `tests/unit/core/test_errors.py` (formatador).
- Reaproveite as fixtures `client`, `session`, `user`, `other_user` e as constantes `VALID_PASSWORD` e `TRUSTED_ORIGIN` já existentes. Autentique com o helper `login(client, user.username)` do próprio arquivo.
- Fixtures assíncronas usam `@pytest_asyncio.fixture` (pitfall 4 da metodologia).
- Para provar "conta inalterada", capture `full_name`, `password_hash`, `updated_at` e `updated_by` antes da requisição, faça `await session.refresh(user)` depois e compare.
- Erros devem ser conferidos por `detail.code` e, quando houver, `detail.message` (formato da Spec 034).

---

## Phase 1: Setup

**Purpose**: registrar a linha de base antes de qualquer mudança.

- [X] T001 Executar `poetry run pytest tests/api/routers/test_auth_router.py tests/api/routers/test_user_update.py tests/api/routers/test_error_contract.py tests/unit/core/test_errors.py tests/unit/schemas/test_user_schemas.py -q` e anotar a saída real como linha de base (todos verdes antes da feature)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: fechar a lacuna de mascaramento de senha da Spec 034 (research.md, item 7) e preparar o helper de teste usado por todas as histórias.

- [X] T002 [P] Testar que `field_errors` mascara erro de `('body', 'current_password')` com `code='invalid'` e `message='Senha inválida.'`, sem a regra do `ctx`, em tests/unit/core/test_errors.py
- [X] T003 Testar que `field_errors` mascara erro de `('body', 'new_password')` com `code='invalid'` e `message='Senha inválida.'`, sem a regra do `ctx`, em tests/unit/core/test_errors.py
- [X] T004 Confirmar que T002 e T003 falham; então trocar a condição `if 'password' in path:` por `if any(str(part).endswith('password') for part in path):` em `_field_error` em src/pivma/core/errors.py e confirmar T002, T003 e o teste existente `test_field_errors_hide_password_rule` verdes
- [X] T005 [P] Adicionar o helper `update_me(client, payload, origin=TRUSTED_ORIGIN)` que envia `client.patch('/auth/me', json=payload, headers={'Origin': origin})` (sem o cabeçalho quando `origin is None`) em tests/api/routers/test_auth_router.py

**Checkpoint**: formatador cobre os novos campos de senha; helper disponível.

---

## Phase 3: User Story 1 - Atualizar o próprio nome completo (Priority: P1) 🎯 MVP

**Goal**: conta sem permissão administrativa altera o próprio `full_name` via `PATCH /auth/me`.

**Independent Test**: logar uma conta comum, enviar `{"full_name": "  Maria Silva  "}` e ver `Maria Silva` na resposta e em `GET /auth/me`.

### Tests for User Story 1 ⚠️ (escrever primeiro e ver falhar)

- [X] T006 [P] [US1] Testar que `SelfUserUpdate(full_name='  Maria Silva  ')` aceita o corpo e guarda `'Maria Silva'` em tests/unit/schemas/test_user_schemas.py
- [X] T007 [US1] Testar que `SelfUserUpdate()` sem campos levanta `ValidationError` com a mensagem "Informe o nome completo ou a nova senha." em tests/unit/schemas/test_user_schemas.py
- [X] T008 [US1] Testar que `SelfUserUpdate(full_name=None)` levanta `ValidationError` em tests/unit/schemas/test_user_schemas.py
- [X] T009 [US1] Testar que `SelfUserUpdate(full_name='   ')` levanta `ValidationError` em tests/unit/schemas/test_user_schemas.py
- [X] T010 [US1] Testar que `SelfUserUpdate(full_name='a' * 256)` levanta `ValidationError` em tests/unit/schemas/test_user_schemas.py
- [X] T011 [P] [US1] Testar que `PATCH /auth/me` com `{"full_name": "  Maria Silva  "}` de conta sem `users.manage` retorna 200 com corpo igual a `{id, username, email, full_name: "Maria Silva"}` da própria conta em tests/api/routers/test_auth_router.py
- [X] T012 [US1] Testar que, após o PATCH de nome, `await session.refresh(user)` mostra `user.full_name == 'Maria Silva'` em tests/api/routers/test_auth_router.py
- [X] T013 [US1] Testar que, após o PATCH de nome, `GET /auth/me` retorna `user.full_name == 'Maria Silva'` em tests/api/routers/test_auth_router.py
- [X] T014 [US1] Testar que o PATCH de nome grava `updated_by == user.id` e `updated_at is not None` (a conta da fixture começa com `updated_at = None`), como em `tests/api/routers/test_user_update.py`, em tests/api/routers/test_auth_router.py
- [X] T015 [US1] Testar que a resposta 200 do PATCH não contém as chaves `password`, `password_hash`, `current_password`, `new_password` nem `access_token` em tests/api/routers/test_auth_router.py

### Implementation for User Story 1

- [X] T016 [US1] Criar `SelfUserUpdate` logo após `UserUpdate` em src/pivma/schemas.py: `model_config = ConfigDict(extra='forbid')`, `full_name: FullNameValue = None` e `@model_validator(mode='after')` que levanta `ValueError('Informe o nome completo ou a nova senha.')` quando `full_name` não estiver em `model_fields_set` (T006–T010 verdes)
- [X] T017 [US1] Implementar `PATCH /auth/me` (`update_current_user`) em src/pivma/routers/auth.py: `operation_id='updateCurrentUser'`, `response_model=UserPublic`, `responses` com 401 e 403 no texto de `PATCH /users/{user_id}`; parâmetros `payload: SelfUserUpdate`, `current_user: CurrentUser`, `session: Session`, `_: TrustedOrigin`; atribuir `full_name` quando enviado, chamar `current_user.set_update_audit(current_user.id)`, `await session.commit()`, `await session.refresh(current_user)` e retornar `current_user`; importar `SelfUserUpdate` e `UserPublic` de `pivma.schemas`; sem `try/except` (research.md, item 5)
- [X] T018 [US1] Executar `poetry run pytest tests/api/routers/test_auth_router.py tests/unit/schemas/test_user_schemas.py -q` e confirmar T006–T015 verdes com a saída real

**Checkpoint**: MVP — autogestão do nome funcional e testável sozinha.

---

## Phase 4: User Story 2 - Trocar a própria senha mediante confirmação da senha atual (Priority: P1)

**Goal**: troca de senha com conferência da senha atual, atômica com o nome.

**Independent Test**: enviar `current_password` correta e `new_password` válida; o login aceita só a nova senha.

### Tests for User Story 2 ⚠️ (escrever primeiro e ver falhar)

- [X] T019 [P] [US2] Testar que `SelfUserUpdate(current_password='atual', new_password='NovaSenha-2026')` é aceito em tests/unit/schemas/test_user_schemas.py
- [X] T020 [US2] Testar que `SelfUserUpdate(new_password='NovaSenha-2026')` levanta `ValidationError` com "Informe a senha atual para trocar a senha." em tests/unit/schemas/test_user_schemas.py
- [X] T021 [US2] Testar que `SelfUserUpdate(current_password='atual')` levanta `ValidationError` com "Informe a nova senha." em tests/unit/schemas/test_user_schemas.py
- [X] T022 [US2] Testar que `SelfUserUpdate(full_name='Maria', current_password='atual')` levanta `ValidationError` com "Informe a nova senha." em tests/unit/schemas/test_user_schemas.py
- [X] T023 [US2] Testar que `SelfUserUpdate(current_password='atual', new_password='a' * 7)` levanta `ValidationError` com `loc == ('new_password',)` em tests/unit/schemas/test_user_schemas.py
- [X] T024 [US2] Testar que `SelfUserUpdate(current_password='atual', new_password='a' * 129)` levanta `ValidationError` com `loc == ('new_password',)` em tests/unit/schemas/test_user_schemas.py
- [X] T025 [US2] Testar que `SelfUserUpdate(current_password='atual', new_password='Nova Senha-2026')` levanta `ValidationError` com `loc == ('new_password',)` e "Senha inválida." em tests/unit/schemas/test_user_schemas.py
- [X] T026 [US2] Testar que `SelfUserUpdate(current_password='x', new_password='NovaSenha-2026')` é aceito (senha atual de 1 caractere), para que a senha errada curta chegue à rota em tests/unit/schemas/test_user_schemas.py
- [X] T027 [US2] Testar que `SelfUserUpdate(current_password='', new_password='NovaSenha-2026')` levanta `ValidationError` com `loc == ('current_password',)` em tests/unit/schemas/test_user_schemas.py
- [X] T028 [US2] Testar que `SelfUserUpdate(current_password='a' * 129, new_password='NovaSenha-2026')` levanta `ValidationError` com `loc == ('current_password',)` em tests/unit/schemas/test_user_schemas.py
- [X] T029 [P] [US2] Testar que `PATCH /auth/me` com `current_password=VALID_PASSWORD` e `new_password` válida retorna 200 e `verify_password(user.password_hash, nova)` é verdadeiro após `session.refresh(user)` em tests/api/routers/test_auth_router.py
- [X] T030 [US2] Testar que, após a troca, `POST /auth/login` com a nova senha retorna 200 em tests/api/routers/test_auth_router.py
- [X] T031 [US2] Testar que, após a troca, `POST /auth/login` com `VALID_PASSWORD` retorna 401 `invalid_credentials` em tests/api/routers/test_auth_router.py
- [X] T032 [US2] Testar que a troca de senha grava `updated_by == user.id` e `updated_at is not None` em tests/api/routers/test_auth_router.py
- [X] T033 [US2] Testar que `current_password` incorreta retorna 400 com `detail == {'code': 'invalid_current_password', 'message': 'Senha atual incorreta.'}` em tests/api/routers/test_auth_router.py
- [X] T034 [US2] Testar que `current_password` incorreta mantém `password_hash`, `updated_at` e `updated_by` iguais aos anteriores em tests/api/routers/test_auth_router.py
- [X] T035 [US2] Testar que `full_name` com `current_password` incorreta retorna 400 e mantém o `full_name` anterior em tests/api/routers/test_auth_router.py
- [X] T036 [US2] Testar que `current_password='x'` incorreta retorna 400 `invalid_current_password`, não 422, em tests/api/routers/test_auth_router.py
- [X] T037 [US2] Testar que `new_password` sem `current_password` retorna 422 `validation_error` e mantém o `password_hash` em tests/api/routers/test_auth_router.py
- [X] T038 [US2] Testar que `new_password` com 7 caracteres retorna 422 com o item de `fields` igual a `{location: 'body', field: 'new_password', code: 'invalid', message: 'Senha inválida.'}` e mantém o `password_hash` em tests/api/routers/test_auth_router.py
- [X] T039 [US2] Testar que `full_name` com `current_password` correta e `new_password` válida retorna 200 e altera nome e senha na mesma requisição em tests/api/routers/test_auth_router.py

### Implementation for User Story 2

- [X] T040 [US2] Estender `SelfUserUpdate` em src/pivma/schemas.py: `current_password: Annotated[str, StringConstraints(min_length=1, max_length=128)] = None`, `new_password: Annotated[str, StringConstraints(min_length=8, max_length=128)] = None`, `@field_validator('new_password')` que rejeita espaço com `ValueError('Senha inválida.')`, e no `model_validator` as regras de data-model.md **nesta ordem**: (1) `current_password` sem `new_password` → "Informe a nova senha."; (2) `new_password` sem `current_password` → "Informe a senha atual para trocar a senha."; (3) sem `full_name` e sem `new_password` → "Informe o nome completo ou a nova senha." (research.md, item 3; T007 e T019–T028 verdes)
- [X] T041 [US2] Estender `update_current_user` em src/pivma/routers/auth.py: se `payload.new_password` estiver definido, conferir `await run_in_threadpool(verify_password, current_user.password_hash, payload.current_password)` **antes de qualquer atribuição**; se falso, `raise api_error(HTTPStatus.BAD_REQUEST, 'invalid_current_password', 'Senha atual incorreta.')`; se verdadeiro, `current_user.password_hash = await run_in_threadpool(hash_password, payload.new_password)`; importar `hash_password` de `pivma.core.security`; documentar 400 em `responses`
- [X] T042 [US2] Executar `poetry run pytest tests/api/routers/test_auth_router.py tests/unit/schemas/test_user_schemas.py -q` e confirmar T019–T039 verdes com a saída real

**Checkpoint**: nome e senha funcionam juntos ou separadamente, com atomicidade.

---

## Phase 5: User Story 3 - Impedir alterações indevidas (Priority: P2)

**Goal**: comprovar que a rota só altera a conta da sessão e só os campos previstos.

**Independent Test**: repetir o PATCH sem sessão, sem origem confiável, com campos extras e com corpo inválido e conferir status e ausência de alteração.

**Nota**: as proteções vêm de `CurrentUser`, `TrustedOrigin`, `extra='forbid'` e do `model_validator` já implementados em US1/US2. Estes testes podem passar logo após escritos; isso é esperado e serve como guarda de regressão. Se algum falhar, corrigir na rota ou no schema, não no teste.

### Tests for User Story 3

- [X] T043 [P] [US3] Testar que `PATCH /auth/me` sem cookie de sessão retorna 401 `not_authenticated` e mantém o `full_name` e o `updated_at` de `user` em tests/api/routers/test_auth_router.py
- [X] T044 [US3] Testar que conta desativada depois do login recebe 401 `not_authenticated` no PATCH em tests/api/routers/test_auth_router.py
- [X] T045 [US3] Testar que PATCH sem cabeçalho `Origin` retorna 403 `invalid_origin` e mantém o `full_name` em tests/api/routers/test_auth_router.py
- [X] T046 [US3] Testar que PATCH com `Origin: https://attacker.example` retorna 403 `invalid_origin` e mantém o `full_name` em tests/api/routers/test_auth_router.py
- [X] T047 [US3] Testar que corpo com `username` retorna 422 `validation_error` e mantém `username` em tests/api/routers/test_auth_router.py
- [X] T048 [US3] Testar que corpo com `email` retorna 422 `validation_error` e mantém `email` em tests/api/routers/test_auth_router.py
- [X] T049 [US3] Testar que corpo com `password_hash` retorna 422 `validation_error` e mantém `password_hash` em tests/api/routers/test_auth_router.py
- [X] T050 [US3] Testar que corpo `{}` retorna 422 `validation_error` e mantém a conta em tests/api/routers/test_auth_router.py
- [X] T051 [US3] Testar que `{"full_name": null}` retorna 422 `validation_error` e mantém o `full_name` em tests/api/routers/test_auth_router.py
- [X] T052 [US3] Testar que `{"full_name": "   "}` retorna 422 `validation_error` e mantém o `full_name` em tests/api/routers/test_auth_router.py
- [X] T053 [US3] Testar que `{"current_password": VALID_PASSWORD}` sozinho retorna 422 `validation_error` e mantém a conta em tests/api/routers/test_auth_router.py
- [X] T054 [US3] Testar que `{"current_password": null, "new_password": "NovaSenha-2026"}` retorna 422 `validation_error` e mantém o `password_hash` em tests/api/routers/test_auth_router.py
- [X] T055 [US3] Testar que `{"current_password": VALID_PASSWORD, "new_password": null}` retorna 422 `validation_error` e mantém o `password_hash` em tests/api/routers/test_auth_router.py
- [X] T056 [US3] Testar que o PATCH bem-sucedido de `user` mantém `full_name`, `password_hash`, `updated_at` e `updated_by` de `other_user` em tests/api/routers/test_auth_router.py
- [X] T057 [US3] Testar que `/openapi.json` expõe `paths['/auth/me']['patch']` com `operationId == 'updateCurrentUser'` e respostas `200`, `400`, `401`, `403` e `422` em tests/api/routers/test_auth_router.py

### Implementation for User Story 3

- [X] T058 [US3] Executar `poetry run pytest tests/api/routers/test_auth_router.py -q`; corrigir src/pivma/routers/auth.py ou src/pivma/schemas.py apenas se algum de T043–T057 falhar, e registrar a saída real

**Checkpoint**: todas as histórias funcionam e os limites estão cobertos.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T059 [P] Atualizar a seção "Usuários e Autenticação" de README.md com um item "Autogestão da conta": `PATCH /auth/me` exige sessão e origem confiável; aceita `full_name`, `current_password` e `new_password`; nova senha exige a atual; 400 `invalid_current_password`, 401, 403 e 422; a sessão atual continua válida após a troca
- [X] T060 Executar os comandos de testes focados de specs/037-self-profile-update/quickstart.md e conferir a saída
- [X] T061 Executar `poetry run pytest` (suíte completa) e conferir a saída; nenhum teste existente pode ter asserção alterada (SC-007)
- [X] T062 Executar `poetry run ruff check src tests` e `poetry run ruff format --check src tests` e corrigir apenas o que esta feature introduziu
- [X] T063 Conferir com `git diff --stat` e `git diff tests/` que os testes existentes só receberam acréscimos (nenhuma linha de teste existente removida ou alterada) e que só mudaram src/pivma/core/errors.py, src/pivma/schemas.py, src/pivma/routers/auth.py, tests/api/routers/test_auth_router.py, tests/unit/schemas/test_user_schemas.py, tests/unit/core/test_errors.py, README.md e specs/037-self-profile-update/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende de T001. T004 bloqueia os testes de 422 de senha de US2 (T038). T005 bloqueia todos os testes de API.
- **US1 (Phase 3)**: depende da Phase 2. Cria o schema e a rota.
- **US2 (Phase 4)**: depende de US1 (estende o mesmo schema e a mesma rota).
- **US3 (Phase 5)**: depende de US1 e US2 (T051–T055 usam as regras do schema completo).
- **Polish (Phase 6)**: depende de todas as histórias.

### Within Each User Story

- Testes antes da implementação, falhando primeiro (exceto US3, ver nota da fase).
- Schema antes da rota.
- Executar os testes da história antes de passar para a próxima.

### Parallel Opportunities

- T002 e T005 (arquivos diferentes).
- Em cada história, o primeiro teste unitário de schema e o primeiro teste de API podem ser escritos em paralelo (T006 ∥ T011; T019 ∥ T029). Os demais testes de um mesmo arquivo são sequenciais.
- T059 (README) pode ser feito em paralelo com T060.

---

## Parallel Example: User Story 1

```bash
# Arquivos diferentes, sem dependência entre si:
Task: "T006 Testar SelfUserUpdate aceita e apara full_name em tests/unit/schemas/test_user_schemas.py"
Task: "T011 Testar PATCH /auth/me retorna 200 com UserPublic em tests/api/routers/test_auth_router.py"
```

## Parallel Example: User Story 2

```bash
Task: "T019 Testar SelfUserUpdate aceita current_password + new_password em tests/unit/schemas/test_user_schemas.py"
Task: "T029 Testar troca de senha válida grava hash verificável em tests/api/routers/test_auth_router.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 e Phase 2.
2. Phase 3 (nome).
3. Parar e validar T006–T015.

### Incremental Delivery

1. Base → US1 (nome) → validar.
2. US2 (senha) → validar.
3. US3 (limites) → validar.
4. Polish: README, suíte completa, lint.

---

## Notes

- Sem migração, dependência ou camada nova (plan.md, Complexity Tracking).
- Não fazer commit, push ou PR sem pedido explícito; staging seletivo, nunca `git add .`/`-A`.
- Não tocar em `docs/guia-prototipo 2.md` nem `docs/plano-de-trabalho-fase-ii 2.md`.
- Nunca declarar testes verdes sem executar e conferir a saída.

## Phase 7: Convergence

- [X] T064 Confirmar com a pessoa usuária a origem dos arquivos não versionados `src/pivma/core/errors 2.py` e `tests/unit/core/test_errors 2.py` (cópias anteriores à feature, com a máscara antiga `'password' in path`, sendo a segunda coletada pelo pytest) e removê-los se forem cópias acidentais per plan: Project Structure (unrequested)
- [X] T065 Testar que `PATCH /auth/me` com `{"full_name": "Maria Silva", field: <id de outra conta>}`, parametrizado com `id` e `user_id`, retorna 422 `extra_forbidden` no campo e mantém as duas contas inalteradas em tests/api/routers/test_auth_router.py per FR-002 (partial)
- [X] T066 Testar que `PATCH /auth/me` com `new_password` igual à `current_password` retorna 200 e o login seguinte com essa senha continua funcionando em tests/api/routers/test_auth_router.py per Spec Edge Cases (partial)
