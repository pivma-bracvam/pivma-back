# Tasks: Atualização Administrativa de Usuários

**Input**: Design documents from `/specs/008-admin-user-update/`

**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [research.md](research.md), [contracts/users.openapi.yaml](contracts/users.openapi.yaml) e [quickstart.md](quickstart.md)

**Tests**: Cada tarefa de teste cobre um comportamento observável, seguindo a matriz de risco e o Definition of Done da skill `fastapi-testing-methodology`.

## Phase 1: Setup

- [X] T001 Confirmar a base de migração `7b4f5d6e8a90`, o router de usuários, o padrão de dependências protegidas e as fixtures existentes nos arquivos descritos em `plan.md`

## Phase 2: Foundational - Contrato de nome para novas contas

**Goal**: Fazer novos cadastros exigirem nome completo sem alterar a compatibilidade dos registros legados.

### Tests

- [X] T002 Testar que `POST /users` rejeita cadastro sem `full_name` com HTTP 422 em `tests/api/routers/test_user_router.py`
- [X] T003 Testar que `UserSchema` mantém `full_name` aparado e aceita o limite de 255 caracteres em `tests/unit/schemas/test_user_schemas.py`

### Implementation

- [X] T004 Tornar `full_name` obrigatório em `UserSchema`, preservando a coluna anulável e `UserPublic` anulável em `src/pivma/schemas.py`

**Checkpoint**: Novos cadastros exigem `full_name`; contas persistidas com `null` continuam representáveis.

## Phase 3: User Story 1 - Atualizar o nome de uma conta (Priority: P1) 🎯 MVP funcional

**Goal**: Permitir que uma pessoa autorizada preencha ou substitua o nome de uma conta.

**Independent Test**: Persistir uma conta legada, conceder `users.manage`, executar o PATCH com origem confiável e confirmar resposta, persistência e auditoria.

### Tests

- [X] T005 [P] [US1] Testar que `UserUpdate` remove espaços externos de `full_name` em `tests/unit/schemas/test_user_schemas.py`
- [X] T006 [US1] Testar que PATCH preenche `full_name` nulo e retorna HTTP 200 com o valor aparado em `tests/api/routers/test_user_update.py`
- [X] T007 [US1] Testar que PATCH substitui um `full_name` existente e retorna HTTP 200 em `tests/api/routers/test_user_update.py`
- [X] T008 [US1] Testar que PATCH atualiza `updated_at` e `updated_by` com o administrador autenticado em `tests/api/routers/test_user_update.py`
- [X] T009 [US1] Testar que PATCH preserva username, e-mail, hash, estado e permissões da conta em `tests/api/routers/test_user_update.py`

### Implementation

- [X] T010 [US1] Declarar `UserUpdate` com `full_name` obrigatório, aparado, limitado a 255 caracteres e `extra='forbid'` em `src/pivma/schemas.py`
- [X] T011 [US1] Adicionar `USERS_MANAGE = 'users.manage'` fora de `ADMINISTRATIVE_PERMISSIONS` em `src/pivma/core/authorization.py`
- [X] T012 [US1] Implementar `PATCH /users/{user_id}` com `CurrentUser`, `TrustedOrigin`, `require_permission(USERS_MANAGE)`, atualização de `full_name`, `set_update_audit` e resposta `UserPublic` em `src/pivma/routers/users.py`

**Checkpoint**: Administrador preenche ou substitui `full_name` de uma conta sem alterar outros dados.

## Phase 4: User Story 2 - Proteger e validar a atualização (Priority: P2)

**Goal**: Bloquear chamadas sem sessão, permissão, origem confiável ou payload válido.

**Independent Test**: Repetir o PATCH em cada fronteira de autorização, existência e validação e conferir que o valor anterior permanece intacto.

### Tests

- [X] T013 [P] [US2] Testar que PATCH sem sessão retorna HTTP 401 em `tests/api/routers/test_user_update.py`
- [X] T014 [P] [US2] Testar que PATCH sem `users.manage` retorna HTTP 403 e não altera a conta em `tests/api/routers/test_user_update.py`
- [X] T015 [P] [US2] Testar que PATCH com origem não confiável retorna HTTP 403 e não altera a conta em `tests/api/routers/test_user_update.py`
- [X] T016 [P] [US2] Testar que PATCH para UUID desconhecido retorna HTTP 404 em `tests/api/routers/test_user_update.py`
- [X] T017 [P] [US2] Testar que PATCH rejeita nome vazio, espaços, acima de 255 caracteres ou `null` com HTTP 422 em `tests/api/routers/test_user_update.py`
- [X] T018 [P] [US2] Testar que PATCH sem `full_name` retorna HTTP 422 em `tests/api/routers/test_user_update.py`
- [X] T019 [P] [US2] Testar que PATCH rejeita campos adicionais de usuário com HTTP 422 em `tests/api/routers/test_user_update.py`

### Implementation

- [X] T020 [US2] Criar a migração `8c5e7a1b9d02_user_management_permission.py` para semear `users.manage` e sua composição no Administrador, com downgrade seguro, em `migrations/versions/8c5e7a1b9d02_user_management_permission.py`

**Checkpoint**: A rota só altera contas em requests autenticados, autorizados, confiáveis e válidos.

## Phase 5: User Story 3 - Manter contratos e compatibilidade (Priority: P3)

**Goal**: Expor o novo valor nos endpoints existentes e manter os mocks legados utilizáveis.

**Independent Test**: Atualizar uma conta antiga e consultar cadastro, identidade e listagem, verificando a projeção pública e a ausência de credenciais.

### Tests

- [X] T021 [P] [US3] Testar que a migração cria `users.manage` e a composição no perfil Administrador em `tests/integration/migrations/test_user_management_permission_migration.py`
- [X] T022 [P] [US3] Testar que `users.manage` não entra em `ADMINISTRATIVE_PERMISSIONS` em `tests/unit/core/test_authorization.py`
- [X] T023 [US3] Testar que o OpenAPI do PATCH exige `full_name`, publica `users.manage` e declara 401/403/404/422 em `tests/api/routers/test_user_update.py`
- [X] T024 [US3] Testar que o novo `full_name` aparece em `GET /auth/me` e `GET /users` após o PATCH em `tests/api/routers/test_user_update.py`
- [X] T025 [US3] Testar que o downgrade remove a composição e a permissão `users.manage` em `tests/integration/migrations/test_user_management_permission_migration.py`

### Implementation

- [X] T026 [US3] Alinhar README, contratos OpenAPI de usuários, documentação do Spec Kit e quickstart ao PATCH, à permissão `users.manage` e à obrigatoriedade apenas para novos cadastros em `README.md`, `specs/001-secure-user-registration/contracts/users.openapi.yaml`, `specs/007-admin-user-listing/`, `specs/008-admin-user-update/`

**Checkpoint**: Contas antigas podem ser completadas, novos cadastros exigem nome e os endpoints públicos exibem o valor persistido.

## Phase 6: Polish & Validation

- [X] T027 Executar os testes focados de schema, cadastro, PATCH, autorização e migração e corrigir somente regressões desta feature
- [X] T028 Executar `poetry run pytest`, `poetry run ruff check` e `PYTHONPATH=src poetry run alembic check`, conferindo a saída direta e reportando violações preexistentes sem alterá-las

**Evidência de validação**: os testes focados passaram com 61 testes e a suíte completa passou com 405 testes. O lint direcionado aos arquivos da feature passou. O `poetry run ruff check` global ainda reporta 68 violações preexistentes fora do escopo; o `alembic upgrade head` foi aplicado com sucesso, `alembic heads` aponta `8c5e7a1b9d02` como head e `alembic check` continua reportando drift histórico do schema.

## Dependencies & Execution Order

### Phase Dependencies

- Setup T001 inicia a leitura da base.
- Phase 2 (T002-T004) define o contrato de novos cadastros.
- Phase 3 (T005-T012) depende do schema e entrega o MVP do PATCH.
- Phase 4 (T013-T020) fecha autorização, validação e permissão persistida.
- Phase 5 (T021-T026) alinha contratos e compatibilidade.
- Phase 6 (T027-T028) depende de todas as fases anteriores.

### User Story Dependency Graph

```text
T001 → T002-T004 → T005-T012 → T013-T020 → T021-T026 → T027-T028
```

### Parallel Opportunities

- T005 pode ser executada em paralelo com T002 e T003, desde que os arquivos de teste sejam serializados ao editar o mesmo módulo.
- T013-T019 são testes independentes de fronteiras e podem ser preparados em paralelo antes da implementação T012.
- T021, T022 e T023 podem ser preparados em paralelo em arquivos distintos.

## Implementation Strategy

### Smallest Complete Delivery

1. Fechar o contrato de `full_name` para novos cadastros.
2. Entregar o PATCH autorizado com auditoria e o preenchimento de contas legadas.
3. Adicionar a permissão persistida e provar as fronteiras de segurança.
4. Alinhar contratos e validar a suíte completa.

### Scope Guardrails

- Não alterar username, e-mail, senha, perfis, vínculos, designações ou estado ativo.
- Não criar edição pelo próprio usuário, atualização em lote ou `display_name`.
- Não reutilizar `users.read` para autorizar mutações.
- Não exigir preenchimento de contas antigas/mockadas.
- Não criar nova tabela de eventos nesta feature.

## Requirement Coverage

| Requirements | Tasks |
|---|---|
| FR-001 | T012 |
| FR-002 | T012-T019 |
| FR-003 | T011, T020, T022 |
| FR-004-FR-007 | T010, T017-T019 |
| FR-008 | T016 |
| FR-009-FR-010 | T008-T009, T012 |
| FR-011 | T002-T004 |
| FR-012 | T024, T026 |
| SC-001-SC-006 | T006-T009, T013-T025, T027-T028 |
