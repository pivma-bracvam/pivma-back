# Tasks: Autorização de Usuários e RBAC

**Input**: Design documents from `/specs/003-user-authorization-rbac/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/` e `quickstart.md`

**Tests**: A especificação exige cenários automatizados. Cada fase escreve os testes de risco antes da implementação e usa PostgreSQL real somente para consultas, constraints, migrações e concorrência.

**Organization**: As tarefas seguem as quatro histórias da especificação. US2 e US3 podem avançar em paralelo depois de US1; US4 consolida a rastreabilidade produzida por ambas.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode executar em paralelo porque usa arquivos distintos e não depende de tarefa incompleta.
- **[Story]**: Mapeia a tarefa para US1, US2, US3 ou US4.
- Cada tarefa informa os arquivos que deve criar, alterar ou validar.

## Phase 1: Setup

**Purpose**: Registrar a linha de base antes de alterar autenticação, modelos ou rotas.

- [ ] T001 Executar `poetry run pytest` e `poetry run ruff check`, conferir a saída e registrar qualquer falha preexistente antes de alterar `src/pivma/` e `tests/`

---

## Phase 2: Foundational

**Purpose**: Criar schema, catálogos e dependências compartilhadas que bloqueiam todas as histórias.

**CRITICAL**: Nenhuma história pode começar antes da conclusão desta fase.

- [ ] T002 [P] Criar testes de upgrade, nove perfis, três permissões, composição do Administrador e downgrade que preserva `users` em `tests/integration/migrations/test_rbac_migration.py`
- [ ] T003 [P] Criar testes PostgreSQL para unicidade parcial de nomes, composições e atribuições, além da consulta cumulativa com registros inativos, em `tests/integration/database/test_rbac_constraints.py`
- [X] T004 Implementar `AccessProfile`, `Permission`, `AccessProfilePermission`, `UserAccessProfile` e `RbacChange` com `AuditMixin`, relacionamentos sem cascade e índices do desenho em `src/pivma/core/database/models.py`, depois de T002 e T003
- [X] T005 Criar a revisão Alembic `user_authorization_rbac` em `migrations/versions/`, com schema, índices, UUIDs literais, seeds determinísticos e downgrade na ordem definida em `data-model.md`, depois de T004
- [X] T006 Criar `AccessProfileFactory` e `UserAccessProfileFactory` com FKs persistidas em `tests/factories/rbac_factory.py`, exportá-las em `tests/factories/__init__.py` e adicionar somente fixtures reutilizadas por mais de um módulo em `tests/conftest.py`
- [X] T007 [P] Extrair `get_current_user`, `CurrentUser` e validação de origem confiável para `src/pivma/dependencies.py`, adaptar `src/pivma/routers/auth.py` e preservar todos os contratos de `tests/api/routers/test_auth_router.py`
- [ ] T008 Executar `poetry run pytest tests/integration/migrations/test_rbac_migration.py tests/integration/database/test_rbac_constraints.py tests/api/routers/test_auth_router.py -q` e corrigir somente falhas ligadas a `src/pivma/core/database/models.py`, `migrations/versions/`, `src/pivma/dependencies.py` e `src/pivma/routers/auth.py`

**Checkpoint**: Banco, catálogos e autenticação compartilhada estão prontos.

---

## Phase 3: User Story 1 - Bloquear ações sem permissão (Priority: P1) 🎯 MVP

**Goal**: Autorizar uma ação pelo estado atual dos perfis e negar 401 ou 403 antes de consultar o alvo.

**Independent Test**: Atribuir Administrador por bootstrap, consultar o catálogo com essa conta e confirmar 401 sem sessão, 403 com conta sem `rbac.read` e 200 com a permissão ativa.

### Tests for User Story 1

- [ ] T009 [P] [US1] Criar testes unitários da decisão de permissão, união cumulativa, filtros de inatividade e recusa uniforme em `tests/unit/core/test_authorization.py`
- [ ] T010 [P] [US1] Criar testes de API para `GET /rbac/permissions`, cobrindo 401, 403, 200, ausência de dados protegidos e efeito no pedido seguinte após encerrar ou inativar a atribuição pela fixture, reutilizando o mesmo cookie, em `tests/api/routers/test_rbac_security.py`
- [ ] T011 [P] [US1] Criar testes do bootstrap para conta ativa, ausente, excluída, repetição idempotente e outra conta já Administrador em `tests/integration/test_rbac_bootstrap.py`

### Implementation for User Story 1

- [X] T012 [US1] Implementar os três códigos estáveis, consulta indexada de permissão efetiva e guarda compartilhada do Administrador em `src/pivma/core/authorization.py`
- [X] T013 [US1] Implementar `require_permission(code)` com 403 anterior à busca do alvo e registro operacional sem dados protegidos somente para essa recusa de permissão em `src/pivma/dependencies.py`
- [X] T014 [US1] Implementar o comando transacional one-shot `--user-id`, sua idempotência para a mesma conta e `bootstrap.admin_assigned` com autoria nula em `src/pivma/bootstrap_rbac.py`
- [X] T015 [US1] Implementar `PermissionPublic` em `src/pivma/schemas.py`, `GET /rbac/permissions` em `src/pivma/routers/rbac.py` e registrar o router e os métodos CORS usados pelo contrato em `src/pivma/__init__.py`
- [ ] T016 [US1] Executar `poetry run pytest tests/unit/core/test_authorization.py tests/integration/test_rbac_bootstrap.py tests/api/routers/test_rbac_security.py tests/api/routers/test_auth_router.py -q` e corrigir somente o incremento US1 nos arquivos citados nesta fase

**Checkpoint**: US1 fornece um caminho protegido completo e testável sem US2, US3 ou US4.

---

## Phase 4: User Story 2 - Administrar perfis e permissões (Priority: P2)

**Goal**: Consultar, criar, alterar, compor e inativar perfis com as proteções dos nomes oficiais e do último administrador.

**Independent Test**: Criar um perfil, substituir suas permissões, alterar sua descrição e inativá-lo; confirmar separação de capacidades, conflitos e efeito no pedido seguinte.

### Tests for User Story 2

- [X] T017 [P] [US2] Criar testes de schemas para trim, limites, campos extras, `permission_codes` únicos e PATCH com ao menos um campo em `tests/unit/schemas/test_rbac_schemas.py`
- [ ] T018 [P] [US2] Criar testes de API para listar, criar, alterar, substituir permissões e inativar perfis, incluindo origem, capacidades separadas, nomes oficiais, permissão desconhecida e conflitos de estado; comprovar o mesmo 403 para IDs existentes e inexistentes quando o ator não tem capacidade, em `tests/api/routers/test_rbac_router.py`
- [ ] T019 [P] [US2] Criar o teste de duas criações concorrentes com nomes equivalentes e uma única linha ativa em `tests/api/routers/test_rbac_concurrency.py`

### Implementation for User Story 2

- [X] T020 [P] [US2] Implementar `ProfileCreate`, `ProfileUpdate`, `ProfilePublic` e respostas de auditoria conforme `contracts/rbac.openapi.yaml` em `src/pivma/schemas.py`
- [X] T021 [P] [US2] Implementar consultas de perfil, substituição atômica da composição e verificação transacional do último administrador em `src/pivma/core/authorization.py`
- [X] T022 [US2] Implementar `GET/POST /rbac/profiles` e `PATCH/DELETE /rbac/profiles/{profile_id}`, com autorização anterior ao alvo, origem, soft delete, conflitos e `RbacChange` na mesma transação, em `src/pivma/routers/rbac.py`
- [ ] T023 [US2] Executar `poetry run pytest tests/unit/schemas/test_rbac_schemas.py tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_concurrency.py -q` e corrigir somente os comportamentos de perfil da US2

**Checkpoint**: US2 administra perfis sem depender das operações de atribuição da US3.

---

## Phase 5: User Story 3 - Atribuir perfis a contas (Priority: P3)

**Goal**: Conceder e retirar perfis de contas ativas e consultar a união das permissões atuais.

**Independent Test**: Conceder um perfil a uma conta, consultar acesso efetivo, retirar um de dois perfis equivalentes e confirmar que a permissão permanece até a retirada do último perfil que a concede.

### Tests for User Story 3

- [ ] T024 [US3] Criar testes de API para consulta de acesso, concessão, retirada, múltiplos perfis, conta ou perfil inativo, vínculo repetido e efeito com o mesmo cookie em `tests/api/routers/test_rbac_router.py`
- [ ] T025 [P] [US3] Criar testes PostgreSQL com sessões independentes para concessão duplicada e duas retiradas concorrentes que preservam um administrador efetivo em `tests/api/routers/test_rbac_concurrency.py`

### Implementation for User Story 3

- [X] T026 [US3] Implementar `ProfileSummary`, `UserAccess` e `ProfileAssignmentPublic` conforme o contrato em `src/pivma/schemas.py`
- [X] T027 [US3] Implementar `GET /rbac/users/{user_id}/access` e `POST/DELETE /rbac/users/{user_id}/profiles/{profile_id}`, com consulta cumulativa, locks, soft delete, conflitos e `RbacChange` atômico, em `src/pivma/routers/rbac.py`
- [ ] T028 [US3] Executar `poetry run pytest tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_concurrency.py tests/integration/database/test_rbac_constraints.py -q` e corrigir somente os comportamentos de atribuição da US3

**Checkpoint**: US2 e US3 funcionam separadamente sobre a autorização entregue por US1.

---

## Phase 6: User Story 4 - Rastrear mudanças de acesso (Priority: P4)

**Goal**: Consultar tipo, alvo, responsável e momento das mudanças concluídas, mantendo a recusa 403 de permissão fora da trilha persistente.

**Independent Test**: Executar cada mutação RBAC, consultar a página de mudanças e confirmar autoria e ordem; provocar uma recusa 403 de permissão e confirmar log operacional sem nova linha persistente.

### Tests for User Story 4

- [ ] T029 [P] [US4] Criar testes de API para `GET /rbac/changes`, paginação, ordem determinística, autoria e ações de perfil, composição e atribuição, incluindo `bootstrap.admin_assigned` com autoria nula, em `tests/api/routers/test_rbac_router.py`
- [ ] T030 [P] [US4] Criar teste de atomicidade entre estado e `RbacChange`, além de `caplog` para a recusa 403 de permissão sem persistência e para a ausência desse log RBAC em 401, origem inválida, 422 e 409, em `tests/integration/database/test_rbac_constraints.py` e `tests/api/routers/test_rbac_security.py`

### Implementation for User Story 4

- [X] T031 [US4] Implementar `RbacChange` e `RbacChangePage` de resposta conforme o contrato em `src/pivma/schemas.py`
- [X] T032 [US4] Implementar `GET /rbac/changes` com `offset`, `limit`, ordenação por momento e ID e permissão `rbac.read` em `src/pivma/routers/rbac.py`
- [X] T033 [US4] Revisar todas as mutações em `src/pivma/routers/rbac.py`, o bootstrap em `src/pivma/bootstrap_rbac.py` e a recusa 403 de permissão em `src/pivma/dependencies.py` para garantir commit ou rollback conjunto, autoria correta e ausência de evento persistente
- [ ] T034 [US4] Executar `poetry run pytest tests/api/routers/test_rbac_router.py tests/api/routers/test_rbac_security.py tests/integration/database/test_rbac_constraints.py -q` e corrigir somente a rastreabilidade da US4

**Checkpoint**: As quatro histórias e os 25 requisitos funcionais possuem evidência automatizada.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Confirmar regressão, contrato, documentação operacional e limite de escopo.

- [X] T035 [P] Documentar as seis rotas RBAC, as três permissões e o bootstrap one-shot em `README.md`, mantendo instituição, laboratório, processo, conflito de interesse e auditoria geral fora da entrega
- [X] T036 Conferir as respostas, status, campos e permissões implementados contra `specs/003-user-authorization-rbac/contracts/rbac.openapi.yaml` e ajustar somente `src/pivma/schemas.py`, `src/pivma/routers/rbac.py` e os testes de contrato relacionados
- [X] T037 Preparar a conta-alvo antes da validação manual cronometrada, medir somente a criação do perfil, a definição de permissões e a atribuição, e executar todos os comandos de `specs/003-user-authorization-rbac/quickstart.md`; depois executar `poetry run pytest` e `poetry run ruff check`, conferir as saídas e registrar o tempo e os resultados reais em `specs/003-user-authorization-rbac/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: inicia sem dependências.
- **Foundational (Phase 2)**: depende da linha de base e bloqueia todas as histórias.
- **US1 (Phase 3)**: depende da fundação e entrega o MVP de autorização.
- **US2 (Phase 4)**: depende de US1 para proteger a gestão de perfis.
- **US3 (Phase 5)**: depende de US1; pode executar em paralelo com US2 usando os perfis semeados.
- **US4 (Phase 6)**: depende de US2 e US3 porque consulta as mudanças produzidas por ambas.
- **Polish (Phase 7)**: depende das quatro histórias.

### User Story Dependency Graph

```text
Setup → Foundational → US1 ─┬─→ US2 ─┐
                            └─→ US3 ─┴─→ US4 → Polish
```

### Within Each User Story

- Escrever os testes da fase e confirmar que falham pelo comportamento ausente.
- Implementar schemas ou regras centrais antes dos endpoints que os consomem.
- Confirmar estado e `RbacChange` na mesma transação.
- Executar o conjunto focado antes de seguir para outra história.

### Parallel Opportunities

- T002 e T003 podem avançar em paralelo. T004 inicia após ambos, T005 após T004, e T007 continua independente desses arquivos.
- T009, T010 e T011 podem avançar em paralelo na US1.
- T017, T018 e T019 podem avançar em paralelo; T020 e T021 também podem.
- US2 e US3 podem avançar em paralelo depois de US1, desde que uma pessoa coordene os arquivos compartilhados `src/pivma/schemas.py`, `src/pivma/routers/rbac.py` e os testes de router.
- T029 e T030 podem avançar em paralelo na US4.

---

## Parallel Examples

### User Story 1

```text
T009: testes unitários em tests/unit/core/test_authorization.py
T010: testes de segurança em tests/api/routers/test_rbac_security.py
T011: testes de bootstrap em tests/integration/test_rbac_bootstrap.py
```

### User Story 2

```text
T017: schemas em tests/unit/schemas/test_rbac_schemas.py
T018: contratos de perfil em tests/api/routers/test_rbac_router.py
T019: concorrência de nomes em tests/api/routers/test_rbac_concurrency.py
```

### User Story 3

```text
T024: contratos de atribuição em tests/api/routers/test_rbac_router.py
T025: concorrência em tests/api/routers/test_rbac_concurrency.py
```

### User Story 4

```text
T029: contrato da trilha em tests/api/routers/test_rbac_router.py
T030: atomicidade e recusa em tests/integration/database/test_rbac_constraints.py e tests/api/routers/test_rbac_security.py
```

---

## Implementation Strategy

### MVP First

1. Concluir Setup e Foundational.
2. Concluir US1.
3. Parar e validar 401, 403, 200, revogação no pedido seguinte e bootstrap.
4. Revisar o incremento antes de iniciar administração de perfis ou atribuições.

### Incremental Delivery

1. US1 entrega autorização global reutilizável.
2. US2 acrescenta gestão de perfis.
3. US3 acrescenta atribuições e acesso efetivo.
4. US4 expõe a rastreabilidade já gravada pelas mutações.
5. Polish confirma contrato, documentação, regressão e escopo.

## Notes

- Não adicionar dependências, service, repository, cache, hierarquia, negação explícita ou mecanismo genérico de policies.
- Reutilizar `auth_token` nos testes de autorização; login real continua coberto pela feature 002.
- Usar sessões independentes somente nos três testes de concorrência; os demais testes reutilizam savepoints existentes.
- Usar entidades persistidas por Factory Boy nas FKs de autoria; não usar UUID aleatório como atalho.
- Conferir a saída de `poetry run pytest`; `poetry test` não serve como prova isolada por usar `ignore_fail = true`.

## Requirement Coverage

| Requisitos | Tarefas principais |
|---|---|
| FR-001 a FR-004, FR-016, FR-017 e FR-020 | T009 a T016, T018, T024 e T027 |
| FR-005 a FR-007 e FR-012 | T002, T005, T011, T012, T014, T015, T017, T018 e T036 |
| FR-008 a FR-011 | T003 a T005, T017 a T023 |
| FR-013 a FR-015 e FR-019 | T003 a T005, T018, T021, T022 e T024 a T027 |
| FR-018 e FR-025 | T013, T022, T027 e T029 a T034 |
| FR-021 a FR-024 | T001, T007, T008, T011, T014, T016, T035 a T037 |
| SC-001 | T009, T010, T018 e T024 |
| SC-002 | T009, T010 e T024 |
| SC-003 | T010, T018 e T024 |
| SC-004 | T037 e a validação manual cronometrada em `quickstart.md` |
| SC-005 | T002, T003, T009 e T024 |
| SC-006 | T003, T019 e T025 |
| SC-007 | T011, T022, T027, T029, T030 e T033 |
| SC-008 | T018, T021, T025 e T027 |
| SC-009 | T001, T007, T008, T016 e T037 |
| SC-010 | T018 |
| SC-011 | T011 e T014 |
| SC-012 | T013, T030 e T033 |

## Phase 8: Convergence

- [X] T038 Converter `IntegrityError` durante `flush()` nas criações de perfil e atribuição em rollback e HTTP 409, incluindo pedidos concorrentes, em `src/pivma/routers/rbac.py` e testes de concorrência, por FR-010, FR-015 e SC-006 (partial)
- [X] T039 Implementar e executar a matriz aprovada de testes RBAC de migração, constraints, autorização, rotas, bootstrap, auditoria e concorrência, com seeds reutilizáveis para o schema criado por testes, por SC-001 a SC-003, SC-005 a SC-008 e SC-010 a SC-012 (missing)
- [X] T040 Executar os grupos focados, a validação manual cronometrada de SC-004 e os comandos de `quickstart.md`; registrar somente resultados e tempo reais, por plan: validação e SC-004 (partial)
- [X] T041 Revisar e justificar ou remover a configuração `extra='ignore'` em `src/pivma/core/settings.py`, pois ela não integra o escopo aprovado do RBAC (unrequested)

## Phase 9: Convergence

- [X] T042 Completar os testes RBAC de API, auditoria e concorrência no PostgreSQL real: 403/200 sem vazamento, separação das três permissões, revogação no mesmo cookie, `GET /rbac/changes`, `caplog` e preservação do último administrador, por SC-001 a SC-003, SC-006 a SC-008 e SC-010 a SC-012 (partial)
- [X] T043 Validar os nove nomes oficiais, contas com zero e múltiplos perfis e permissão compartilhada, e executar a validação manual cronometrada de SC-004 com registro de tempo real no quickstart, por SC-004 e SC-005 (partial)
