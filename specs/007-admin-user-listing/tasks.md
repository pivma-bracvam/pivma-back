# Tasks: Listagem Administrativa de Usuários

**Input**: Artefatos aprovados em `/specs/007-admin-user-listing/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/users.openapi.yaml` e `quickstart.md`

**Tests**: A spec exige evidência automatizada. Cada tarefa de teste cobre um comportamento observável e usa o nível definido no plano: migração Alembic, API com PostgreSQL real, segurança/autorização ou unidade isolada da invariável.

**Organization**: As tarefas seguem as três histórias da spec. A fundação semeia `users.read`; US1 entrega a consulta básica; US2 acrescenta filtros e paginação completa; US3 comprova a proteção dos dados.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode avançar em paralelo porque usa arquivo distinto e não depende de tarefa incompleta.
- **[Story]**: Mapeia a tarefa para US1, US2 ou US3.
- Cada tarefa informa o arquivo que deve criar, alterar ou validar.

## Evidence Classification

- **CONFIRMADO**: `User.deleted_at` representa exclusão lógica; `require_permission` consulta permissões efetivas; `FilterPage` não possui limite máximo; o head Alembic aprovado no plano é `6f2c9a1d4e70`.
- **DECISÃO TÉCNICA REGISTRADA**: a migração semeia `users.read` no Administrador; `ADMINISTRATIVE_PERMISSIONS` permanece inalterado; a busca usa `icontains(autoescape=True)`; o filtro de perfil usa `EXISTS`; a rota permanece em `src/pivma/routers/users.py`.
- **INFERÊNCIA APROVADA NO PLANO**: os testes HTTP contra PostgreSQL cobrem a consulta no router sem justificar uma camada ou suíte de repository adicional.
- **PROPOSTA OPERACIONAL DAS TASKS**: reservar `7a3e1c9b4d82` como identificador da nova revisão Alembic para fornecer um caminho de arquivo executável e evitar nome indefinido durante a implementação.

---

## Phase 1: Setup

**Purpose**: Registrar a linha de base dos contratos que a feature deve preservar e confirmar as premissas operacionais da migração.

- [X] T001 Executar a regressão inicial com `poetry run pytest tests/api/routers/test_user_router.py tests/api/routers/test_auth_router.py tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_security.py tests/integration/test_rbac_bootstrap.py -q` e registrar falhas preexistentes antes de alterar `src/pivma/`, `migrations/versions/` ou `tests/`
- [X] T002 Executar pre-check operacional no working tree atual para confirmar que: (1) o único Alembic head continua sendo `6f2c9a1d4e70` (`PYTHONPATH=src poetry run alembic heads`), (2) a revision proposta `7a3e1c9b4d82` ainda está livre em `migrations/versions/`, (3) os UUIDs determinísticos `00000000-0000-0000-0000-000000000108` e `00000000-0000-0000-0000-000000000208` ainda estão livres no código, e (4) o estado anterior do catálogo/composição confirma a expectativa que resultará em 8 permissões e 8 composições após a feature (`tests/integration/migrations/test_rbac_migration.py`); se alguma premissa tiver mudado, ajustar somente os identificadores/head da nova migration e expectativas diretamente dependentes

---

## Phase 2: Foundational - Catálogo e invariável do RBAC

**Purpose**: Acrescentar `users.read` ao catálogo e ao Administrador sem ampliar a salvaguarda administrativa do RBAC.

**CRITICAL**: Esta fase bloqueia as três histórias porque a rota e suas fixtures precisam da permissão estável.

### Tests for the foundation

> Escrever cada teste e confirmar sua falha pelo comportamento ausente antes da implementação.

- [X] T003 Criar teste de migração que comprova o seed da permissão `users.read` com UUID `00000000-0000-0000-0000-000000000108` em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T004 Criar teste de migração que comprova a composição de `users.read` no perfil oficial Administrador com UUID `00000000-0000-0000-0000-000000000208` em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T005 Criar teste de migração que comprova `users.read` nas permissões efetivas de uma conta com atribuição Administrador preexistente em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T006 Criar teste de migração que comprova ausência de composição semeada de `users.read` em perfis não administrativos em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T007 Criar teste de downgrade que adiciona uma composição posterior para `users.read` e comprova a remoção segura da permissão em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T008 Criar teste de downgrade que comprova a preservação de uma conta preexistente em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T009 Criar teste de downgrade que comprova a preservação de um perfil de acesso preexistente em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T010 Criar teste de downgrade que comprova a preservação de uma atribuição de perfil preexistente em `tests/integration/migrations/test_admin_user_listing_migration.py`
- [X] T011 [P] Atualizar o teste agregado do head para esperar oito permissões e oito composições oficiais em `tests/integration/migrations/test_rbac_migration.py`
- [X] T012 [P] Criar teste unitário que comprova `USERS_READ not in ADMINISTRATIVE_PERMISSIONS` em `tests/unit/core/test_authorization.py`

### Implementation for the foundation

- [X] T013 Criar a revisão de dados `7a3e1c9b4d82`, sucessora de `6f2c9a1d4e70`, em `migrations/versions/7a3e1c9b4d82_admin_user_listing_permission.py`, inserindo os UUIDs `108`/`208` no upgrade e removendo todas as composições da nova permissão antes dela no downgrade
- [X] T014 [P] Adicionar `USERS_READ = "users.read"` em `src/pivma/core/authorization.py` sem modificar os três membros de `ADMINISTRATIVE_PERMISSIONS`
- [X] T015 Executar `poetry run pytest tests/integration/migrations/test_admin_user_listing_migration.py tests/integration/migrations/test_rbac_migration.py tests/unit/core/test_authorization.py -q` e corrigir somente a fundação em `migrations/versions/7a3e1c9b4d82_admin_user_listing_permission.py` e `src/pivma/core/authorization.py`

**Checkpoint**: O catálogo contém `users.read`, o Administrador a concede pelo cálculo existente e a invariável continua restrita às três permissões de RBAC.

---

## Phase 3: User Story 1 - Localizar uma conta ativa (Priority: P1) 🎯 MVP funcional

**Goal**: Uma pessoa com `users.read` consulta contas ativas e localiza o UUID de uma conta por username ou e-mail.

**Independent Test**: Criar contas ativas, autenticar uma conta com `users.read` e conferir a página padrão, a busca literal case-insensitive e o UUID devolvido.

### Tests for User Story 1

> Escrever cada teste e confirmar sua falha pelo comportamento ausente antes da implementação.

- [X] T016 [US1] Testar que `GET /users` autorizado sem parâmetros retorna HTTP 200 com `offset=0` e `limit=100` em `tests/api/routers/test_user_listing.py`
- [X] T017 [US1] Testar por parametrização que a omissão de `active` e `active=true` retornam somente contas ativas em `tests/api/routers/test_user_listing.py`
- [X] T018 [US1] Testar busca por substring de username com retorno do UUID esperado em `tests/api/routers/test_user_listing.py`
- [X] T019 [US1] Testar busca por substring de e-mail com retorno do UUID esperado em `tests/api/routers/test_user_listing.py`
- [X] T020 [US1] Testar equivalência das variações de caixa na busca por username em `tests/api/routers/test_user_listing.py`
- [X] T021 [US1] Testar equivalência das variações de caixa na busca por e-mail em `tests/api/routers/test_user_listing.py`
- [X] T022 [US1] Testar remoção de espaços externos de `search` em `tests/api/routers/test_user_listing.py`
- [X] T023 [US1] Testar por parametrização que `search` vazio ou composto por espaços produz o mesmo conjunto da busca ausente em `tests/api/routers/test_user_listing.py`
- [X] T024 [US1] Testar por parametrização que `%` e `_` são tratados como caracteres literais de `search` em `tests/api/routers/test_user_listing.py`
- [X] T025 [US1] Testar que busca sem correspondência retorna HTTP 200 com página vazia e metadados preservados em `tests/api/routers/test_user_listing.py`
- [X] T026 [US1] Testar que o UUID obtido na listagem identifica a mesma conta aceita por `GET /rbac/users/{user_id}/access` em `tests/api/routers/test_user_listing.py`

### Implementation for User Story 1

- [X] T027 [US1] Criar `AdminUser` a partir de `UserPublic` e `AdminUserPage` a partir de `FilterPage` em `src/pivma/schemas.py`; configurar ambos para produzir schemas compatíveis com `additionalProperties: false` no contrato versionado, redeclarar somente `AdminUserPage.limit` como `Field(100, ge=1, le=100)`, adicionar `items: list[AdminUser]` e não modificar os schemas compartilhados
- [X] T028 [US1] Declarar `GET /users` com `operation_id="listUsers"`, `response_model=AdminUserPage`, sessão existente, `Depends(require_permission(USERS_READ))` e parâmetros FastAPI `search`, `active`, `profile_id`, `offset` e `limit` validados em `src/pivma/routers/users.py`
- [X] T029 [US1] Implementar o predicado padrão de conta ativa e a busca em username ou e-mail com `strip()`, `or_` e `icontains(autoescape=True)` em `src/pivma/routers/users.py`
- [X] T030 [US1] Aplicar ordem `lower(username), id`, depois `offset` e `limit`, e construir explicitamente `AdminUserPage` sem contagem total em `src/pivma/routers/users.py`
- [X] T031 [US1] Executar `poetry run pytest tests/api/routers/test_user_listing.py -q` e corrigir somente os comportamentos US1 em `src/pivma/schemas.py` e `src/pivma/routers/users.py`

**Checkpoint**: US1 localiza contas ativas por username ou e-mail e devolve uma página limitada com UUIDs reutilizáveis.

---

## Phase 4: User Story 2 - Refinar e paginar a listagem (Priority: P2)

**Goal**: A pessoa autorizada combina estado, perfil, busca e paginação sobre um conjunto ordenado sem duplicatas.

**Independent Test**: Preparar contas ativas e inativas com atribuições de perfil em estados distintos, combinar os parâmetros e comparar as páginas com o conjunto esperado.

### Tests for User Story 2

> Escrever cada teste e confirmar sua falha pelo comportamento ausente antes da implementação desta fase.

- [X] T032 [US2] Testar que `limit` restringe a quantidade de itens quando existem mais contas compatíveis em `tests/api/routers/test_user_listing.py`
- [X] T033 [US2] Testar por parametrização que os limites válidos 1 e 100 são aceitos em `tests/api/routers/test_user_listing.py`
- [X] T034 [US2] Testar que a concatenação de páginas sucessivas cobre cada conta compatível uma vez em `tests/api/routers/test_user_listing.py`
- [X] T035 [US2] Testar a ordenação crescente case-insensitive por username em `tests/api/routers/test_user_listing.py`
- [X] T036 [US2] Testar o desempate crescente por UUID entre usernames equivalentes em `tests/api/routers/test_user_listing.py`
- [X] T037 [US2] Testar que `active=false` retorna somente contas inativas com item `active=false` em `tests/api/routers/test_user_listing.py`
- [X] T038 [US2] Testar que `profile_id` retorna uma conta com atribuição ativa a perfil ativo em `tests/api/routers/test_user_listing.py`
- [X] T039 [US2] Testar que `profile_id` ignora uma atribuição encerrada em `tests/api/routers/test_user_listing.py`
- [X] T040 [US2] Testar que `profile_id` ignora um perfil inativo em `tests/api/routers/test_user_listing.py`
- [X] T041 [US2] Testar que `profile_id` válido e desconhecido retorna HTTP 200 com página vazia em `tests/api/routers/test_user_listing.py`
- [X] T042 [US2] Testar que relações históricas compatíveis não duplicam a conta filtrada por `profile_id` em `tests/api/routers/test_user_listing.py`
- [X] T043 [US2] Testar que a combinação de `search`, `active` e `profile_id` restringe o conjunto antes de `offset` e `limit` em `tests/api/routers/test_user_listing.py`
- [X] T044 [US2] Testar que `offset` válido além do último resultado retorna HTTP 200 com página vazia em `tests/api/routers/test_user_listing.py`
- [X] T045 [US2] Testar que `offset=-1` retorna HTTP 422 sem itens em `tests/api/routers/test_user_listing.py`
- [X] T046 [US2] Testar que `limit=0` retorna HTTP 422 sem itens em `tests/api/routers/test_user_listing.py`
- [X] T047 [US2] Testar que `limit=101` retorna HTTP 422 sem itens em `tests/api/routers/test_user_listing.py`
- [X] T048 [US2] Testar que valor inválido de `active` retorna HTTP 422 sem itens em `tests/api/routers/test_user_listing.py`
- [X] T049 [US2] Testar que UUID malformado em `profile_id` retorna HTTP 422 sem itens em `tests/api/routers/test_user_listing.py`

### Implementation for User Story 2

- [X] T050 [US2] Completar o predicado de estado para usar `User.deleted_at.is_not(None)` quando `active=false` em `src/pivma/routers/users.py`
- [X] T051 [US2] Implementar o filtro `profile_id` com `EXISTS` correlacionado sobre `UserAccessProfile` e `AccessProfile`, exigindo atribuição ativa e perfil ativo sem `JOIN` externo ou `DISTINCT`, em `src/pivma/routers/users.py`
- [X] T052 [US2] Executar `poetry run pytest tests/api/routers/test_user_listing.py -q` e corrigir somente os comportamentos US2 em `src/pivma/routers/users.py`

**Checkpoint**: US2 combina todos os filtros antes da página e preserva ordem estável sem repetir contas.

---

## Phase 5: User Story 3 - Proteger dados administrativos (Priority: P3)

**Goal**: O backend expõe a coleção somente a identidades autenticadas com `users.read` e limita a resposta aos campos aprovados.

**Independent Test**: Repetir a consulta sem sessão, sem a permissão, com cada permissão administrativa de RBAC isolada e com `users.read`; conferir resposta, log e ausência de `RbacChange`.

**Implementation note**: T014 cria o código estável; T028 conecta a dependência existente à rota. Esta fase acrescenta a evidência de segurança separada, sem criar outro mecanismo de autorização.

### Tests for User Story 3

> Escrever os testes e confirmar que cada fronteira falha quando a proteção correspondente está ausente.

- [X] T053 [US3] Testar que requisição sem sessão recebe HTTP 401 sem conteúdo da coleção em `tests/api/routers/test_user_listing_security.py`
- [X] T054 [US3] Testar que conta autenticada sem `users.read` recebe HTTP 403 sem conteúdo da coleção em `tests/api/routers/test_user_listing_security.py`
- [X] T055 [US3] Testar por parametrização que cada permissão de `ADMINISTRATIVE_PERMISSIONS` isolada não concede `GET /users` em `tests/api/routers/test_user_listing_security.py`
- [X] T056 [US3] Testar que uma conta com `users.read` recebe HTTP 200 em `tests/api/routers/test_user_listing_security.py`
- [X] T057 [US3] Testar que a resposta 200 possui somente `offset`, `limit` e `items` no topo em `tests/api/routers/test_user_listing.py`
- [X] T058 [US3] Testar que cada item possui somente `id`, `username`, `email`, `active` e `profiles` em `tests/api/routers/test_user_listing.py`
- [X] T059 [US3] Testar que uma recusa por ausência de `users.read` gera um registro operacional em `pivma.dependencies` em `tests/api/routers/test_user_listing_security.py`
- [X] T060 [US3] Testar que uma recusa por ausência de `users.read` não cria `RbacChange` em `tests/api/routers/test_user_listing_security.py`
- [X] T061 [US3] Testar que uma leitura autorizada não cria `RbacChange` em `tests/api/routers/test_user_listing_security.py`
- [X] T062 [US3] Executar `poetry run pytest tests/api/routers/test_user_listing.py tests/api/routers/test_user_listing_security.py -q` e corrigir somente a integração de `USERS_READ` em `src/pivma/routers/users.py`

**Checkpoint**: A listagem exige autenticação e `users.read`, não vaza campos internos e não grava evento persistente de mudança RBAC.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirmar contrato, documentação, regressão e limite de escopo.

- [X] T063 [P] Documentar `GET /users`, seus parâmetros, a projeção administrativa e a permissão `users.read` na seção de Gestão de Usuários de `README.md`
- [X] T064 Conferir o OpenAPI gerado para `GET /users` contra `specs/007-admin-user-listing/contracts/users.openapi.yaml`, com atenção a `AdminUserPage.limit` entre 1 e 100, ajustando somente `src/pivma/schemas.py`, `src/pivma/routers/users.py` ou o teste de contrato em `tests/api/routers/test_user_listing.py`
- [X] T065 Executar `poetry run pytest tests/api/routers/test_user_router.py -q` e confirmar a regressão do cadastro em `tests/api/routers/test_user_router.py`
- [X] T066 Executar `poetry run pytest tests/api/routers/test_auth_router.py -q` e confirmar a regressão da autenticação em `tests/api/routers/test_auth_router.py`
- [X] T067 Executar `poetry run pytest tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_security.py -q` e confirmar a regressão dos contratos HTTP do RBAC nesses arquivos
- [X] T068 Executar `poetry run pytest tests/integration/test_rbac_bootstrap.py -q` e confirmar a regressão da composição do Administrador em `tests/integration/test_rbac_bootstrap.py`
- [X] T069 Executar `poetry run pytest tests/integration/migrations/test_admin_user_listing_migration.py tests/unit/core/test_authorization.py tests/api/routers/test_user_listing.py tests/api/routers/test_user_listing_security.py -q` e conferir a saída dos testes novos
- [X] T070 Executar `poetry run pytest`, conferir a saída direta do Pytest e corrigir somente regressões causadas por `src/pivma/core/authorization.py`, `src/pivma/routers/users.py`, `src/pivma/schemas.py`, `migrations/versions/7a3e1c9b4d82_admin_user_listing_permission.py`, `tests/integration/migrations/test_admin_user_listing_migration.py`, `tests/integration/migrations/test_rbac_migration.py`, `tests/unit/core/test_authorization.py`, `tests/api/routers/test_user_listing.py` ou `tests/api/routers/test_user_listing_security.py`
- [X] T071 Executar `poetry run ruff check` e corrigir somente violações introduzidas em `src/pivma/core/authorization.py`, `src/pivma/routers/users.py`, `src/pivma/schemas.py`, `migrations/versions/7a3e1c9b4d82_admin_user_listing_permission.py`, `tests/integration/migrations/test_admin_user_listing_migration.py`, `tests/integration/migrations/test_rbac_migration.py`, `tests/unit/core/test_authorization.py`, `tests/api/routers/test_user_listing.py` ou `tests/api/routers/test_user_listing_security.py`
- [X] T072 Executar `PYTHONPATH=src poetry run alembic check` e confirmar que o head contém apenas a revisão de dados planejada em `migrations/versions/7a3e1c9b4d82_admin_user_listing_permission.py`
- [X] T073 Executar a validação manual cronometrada de localização e cópia do UUID descrita em `specs/007-admin-user-listing/quickstart.md`, registrando o tempo e o resultado real nesse arquivo

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: inicia sem dependências.
- **Foundational (Phase 2)**: depende da linha de base e bloqueia todas as histórias.
- **US1 (Phase 3)**: depende da fundação e cria schema, rota, busca e página básica.
- **US2 (Phase 4)**: depende de US1 porque amplia a mesma consulta em `src/pivma/routers/users.py`.
- **US3 (Phase 5)**: depende de US1 para testar a rota e pode começar junto ao fechamento de US2 depois que T028 existir.
- **Polish (Phase 6)**: depende das três histórias.

### User Story Dependency Graph

```text
Setup → Foundational → US1 ─┬─→ US2 ─┐
                            └─→ US3 ─┴─→ Polish
```

### Within Each Phase

- Escrever os testes da fase antes da implementação correspondente.
- Confirmar que cada teste novo falha pelo comportamento ausente, sem aceitar falha de fixture ou import como evidência funcional.
- Criar o schema antes de declarar o `response_model` que o consome.
- Aplicar filtros e ordenação no PostgreSQL antes de `offset` e `limit`.
- Executar o conjunto focado no checkpoint antes de seguir.

### Parallel Opportunities

- T011 e T012 podem avançar em paralelo com os testes do novo arquivo de migração; T014 pode avançar junto a T013 após os testes.
- T053 a T056 e T059 a T061 usam o arquivo de segurança.
- T063 pode avançar em paralelo com a conferência técnica T064 depois que as histórias estiverem concluídas.
- US3 pode preparar seus testes enquanto US2 conclui o filtro no router, mas alterações simultâneas em `src/pivma/routers/users.py` devem ser serializadas.

---

## Parallel Examples

### Foundation

```text
T003-T010: testes da revisão em tests/integration/migrations/test_admin_user_listing_migration.py
T011: contagem agregada em tests/integration/migrations/test_rbac_migration.py
T012: invariável isolada em tests/unit/core/test_authorization.py
```

### User Story 3

```text
T053-T056 e T059-T061: fronteiras em tests/api/routers/test_user_listing_security.py
T057-T058: projeção pública em tests/api/routers/test_user_listing.py
```

---

## Implementation Strategy

### Smallest Complete Delivery

1. Concluir Setup e Foundational.
2. Concluir US1 para obter a consulta básica protegida.
3. Concluir US2 para satisfazer os filtros e a paginação aprovados.
4. Concluir US3 para fechar a evidência de segurança antes de publicar a rota.
5. Executar Polish e registrar os resultados reais.

US1 representa o primeiro incremento funcional, mas a entrega publicável inclui US2 e US3 porque filtros, limites e autorização fazem parte do contrato aprovado.

### Scope Guardrails

- Manter o acesso ao banco em `src/pivma/routers/users.py`; não criar repository ou service.
- Reutilizar `require_permission`, `UserPublic`, `FilterPage`, factories e fixtures existentes.
- Não modificar `FilterPage`, `ADMINISTRATIVE_PERMISSIONS`, cadastro, autenticação ou operações RBAC.
- Não criar tabela, modelo ORM, índice, dependência, filtro contextual, ordenação configurável ou auditoria persistente de leitura.
- Usar SQL direto somente em `tests/integration/migrations/test_admin_user_listing_migration.py`.

---

## Requirement Coverage

| Requisitos | Tarefas principais |
|---|---|
| FR-001 a FR-008 | T003-T006, T012-T015, T028, T053-T056, T059-T062 |
| FR-009 a FR-013 | T016, T027-T030, T032-T036, T044-T047 |
| FR-014 a FR-015 | T018-T024, T029 |
| FR-016 | T017, T037, T050 |
| FR-017 a FR-021 | T038-T043, T048-T051 |
| FR-022 a FR-025 | T026-T027, T030, T057-T058, T064 |
| FR-026 a FR-027 | T065-T072 e os guardrails de escopo |
| FR-028 | T059-T061 |
| SC-001 | T018-T021, T026 |
| SC-002 | T053-T055 |
| SC-003 | T016, T032-T033, T046-T047 |
| SC-004 | T034-T036, T042 |
| SC-005 | T020-T021 |
| SC-006 | T017, T037-T043 |
| SC-007 | T057-T058, T064 |
| SC-008 | T073 |
| SC-009 | T001, T002, T065-T070 |
| SC-010 | T004-T006 |
| SC-011 | T059-T061 |

## Notes

- Reutilizar `UserFactory`, `AccessProfileFactory`, `UserAccessProfileFactory`, `client`, `session` e o helper de cookie já adotado nos testes de RBAC.
- Informar um `password_hash` barato à `UserFactory` nos cenários com muitas contas; a listagem não verifica senha.
- Usar `pytest.mark.parametrize` somente para entradas equivalentes do mesmo comportamento, conforme indicado nas tarefas.
- Não criar teste unitário para schemas declarativos ou construção SQL sem componente isolado.
- Conferir a saída de `poetry run pytest`; `poetry test` ignora o código de falha do Pytest e não comprova sucesso.

---

## Phase 7: Convergence

- [X] T074 Alinhar o OpenAPI gerado de `GET /users` ao contrato em `contracts/users.openapi.yaml`: declarar `offset`, `limit` e `items` como obrigatórios em `AdminUserPage`, publicar `x-required-permission: users.read` e as respostas 401/403; adicionar teste de contrato correspondente (plan: contrato OpenAPI; T064)

---

## Phase 8: Exibição dos cargos globais

**Purpose**: Tornar o nome dos perfis globais disponível nas duas consultas de usuário sem expor
permissões, atribuições históricas ou dados de autenticação.

- [X] T075 [P] Testar que `GET /auth/me` retorna `access.profiles` com `id`, `name` e `active` para perfis globais ativos em `tests/api/routers/test_auth_router.py`
- [X] T076 [P] Testar que `GET /users` retorna `items[].profiles` com o resumo dos perfis globais ativos em `tests/api/routers/test_user_listing.py`
- [X] T077 Implementar o schema compartilhado de resumo de perfil, adicionar `profiles` aos contratos de `CurrentUserAccess` e `AdminUser` e carregar os perfis ativos em lote na listagem em `src/pivma/schemas.py`, `src/pivma/core/authorization.py`, `src/pivma/routers/auth.py` e `src/pivma/routers/users.py`
- [X] T078 Alinhar os contratos OpenAPI, a documentação e os testes ao caminho canônico sem barra final (`/users`) e aos campos `profiles` em `specs/002-user-authentication/contracts/auth.openapi.yaml`, `specs/007-admin-user-listing/contracts/users.openapi.yaml`, `README.md` e `tests/`

---

## Phase 9: Atributo de nome completo e compatibilidade legada

**Purpose**: Persistir e expor `full_name` nas respostas de usuário, exigindo o campo em novos
cadastros e preservando contas antigas que ainda não o possuem.

### Tests

- [X] T079 Testar que `UserSchema` remove espaços externos de `full_name` em `tests/unit/schemas/test_user_schemas.py`
- [X] T080 Testar que `UserSchema` rejeita `full_name` vazio, composto por espaços ou acima de 255 caracteres em `tests/unit/schemas/test_user_schemas.py`
- [X] T081 Testar que `POST /users` rejeita HTTP 422 quando `full_name` é omitido em `tests/api/routers/test_user_router.py`
- [X] T082 Testar que `POST /users` retorna `full_name` aparado quando o campo é informado em `tests/api/routers/test_user_router.py`
- [X] T083 Testar que `GET /auth/me` retorna `full_name` na identidade externa e em `user` em `tests/api/routers/test_auth_router.py`
- [X] T084 Testar que `GET /users` retorna `full_name` no item administrativo em `tests/api/routers/test_user_listing.py`
- [X] T085 Testar que o upgrade cria `users.full_name` como coluna anulável e preserva `null` para conta legada em `tests/integration/migrations/test_user_full_name_migration.py`
- [X] T086 Testar que o downgrade remove a coluna `users.full_name` em `tests/integration/migrations/test_user_full_name_migration.py`

### Implementation

- [X] T087 Adicionar `User.full_name` como coluna `String(255)` anulável com valor padrão `None` em `src/pivma/core/database/models.py` e declarar o campo obrigatório aparado em `UserSchema` e anulável em `UserPublic` em `src/pivma/schemas.py`
- [X] T088 Propagar `full_name` no cadastro e na projeção de `GET /users` em `src/pivma/routers/users.py`, mantendo `GET /auth/me` coberto pelo schema compartilhado
- [X] T089 Preencher `full_name` das contas de demonstração a partir dos dados existentes em `src/pivma/seed_demo.py`
- [X] T090 Criar a migração incremental sucessora de `7a3e1c9b4d82` para adicionar e remover `users.full_name` em `migrations/versions/7b4f5d6e8a90_user_full_name.py`
- [X] T091 Alinhar os contratos OpenAPI, o modelo de dados, o quickstart e o README ao campo obrigatório em novos cadastros e anulável no legado em `specs/002-user-authentication/contracts/auth.openapi.yaml`, `specs/007-admin-user-listing/contracts/users.openapi.yaml`, `specs/007-admin-user-listing/data-model.md`, `specs/007-admin-user-listing/quickstart.md` e `README.md`

### Validation

- [X] T092 Executar os testes focados de schema, cadastro, autenticação, listagem e migração e corrigir somente os arquivos desta fase
- [X] T093 Executar `poetry run pytest`, `poetry run ruff check` e `PYTHONPATH=src poetry run alembic check`, conferindo a saída direta e corrigindo somente regressões causadas por esta fase

**Evidência de validação**: os testes focados passaram (93 testes) e a suíte completa passou (381 testes). O Ruff passou nos arquivos desta fase; a execução global ainda reporta violações preexistentes em outros arquivos.

**Checkpoint**: `full_name` é exigido em novos cadastros, pode completar contas legadas via PATCH e aparece em `POST /users`, `GET /auth/me` e `GET /users`; contas antigas sem valor retornam `null`.
