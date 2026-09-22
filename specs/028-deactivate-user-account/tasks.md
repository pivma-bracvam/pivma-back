---

description: "Tarefas executáveis para desativação lógica de contas de usuário"
---

# Tasks: Desativação de Conta de Usuário

**Input**: Artefatos de design em `specs/028-deactivate-user-account/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/users-deactivation.openapi.yaml` e `quickstart.md`

**Tests**: Obrigatórios. A operação é uma transação de alto risco e seus controles de autenticação são críticos. Cada tarefa de teste cobre um comportamento observável, usando a infraestrutura transacional existente; não criar schema por teste nem mocks para o banco.

**Organization**: As tarefas são agrupadas por história para preservar rastreabilidade e permitir validação incremental. Todos os cenários de API desta issue ficam em `tests/api/routers/test_user_router.py`, como definido pela issue.

## Phase 1: Setup (Shared Test Support)

**Purpose**: Preparar somente os auxiliares de teste reutilizados pelos cenários da feature.

- [X] T001 Adicionar helpers mínimos de autenticação, concessão de `users.manage` e leitura de usuário inativo em `tests/api/routers/test_user_router.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Não há infraestrutura, modelo, migração ou serviço compartilhado a criar. A feature reutiliza a sessão, `AuditMixin`, autenticação e invariante administrativa existentes.

**Checkpoint**: Os helpers de teste estão prontos; iniciar os casos da US1 antes da implementação da rota.

---

## Phase 3: User Story 1 - Desativar uma conta (Priority: P1) 🎯 MVP

**Goal**: Uma pessoa com `users.manage` desativa outra conta ativa sem removê-la fisicamente.

**Independent Test**: Com sessão autorizada e origem confiável, `DELETE /users/{user_id}` retorna 204; a conta fica inativa, aparece somente na listagem de inativas e mantém seu registro auditável.

### Tests for User Story 1

> Escrever estes testes primeiro e observar sua falha antes de implementar a rota.

- [X] T002 [US1] Testar que `DELETE /users/{user_id}` retorna 204 sem corpo para conta ativa em `tests/api/routers/test_user_router.py`
- [X] T003 [US1] Testar que a desativação preenche `deleted_at` na conta alvo em `tests/api/routers/test_user_router.py`
- [X] T004 [US1] Testar que a desativação preenche `deleted_by` com a pessoa autora em `tests/api/routers/test_user_router.py`
- [X] T005 [US1] Testar que a conta desativada não é retornada por `GET /users` em `tests/api/routers/test_user_router.py`
- [X] T006 [US1] Testar que a conta desativada é retornada por `GET /users?active=false` em `tests/api/routers/test_user_router.py`
- [X] T007 [US1] Testar bloqueio sem mutação de conta para requisição não autenticada em `DELETE /users/{user_id}` com HTTP 401 em `tests/api/routers/test_user_router.py`
- [X] T008 [US1] Testar bloqueio sem mutação de conta para sessão sem `users.manage` em `DELETE /users/{user_id}` com HTTP 403 em `tests/api/routers/test_user_router.py`
- [X] T009 [US1] Testar bloqueio sem mutação de conta para origem não confiável em `DELETE /users/{user_id}` com HTTP 403 em `tests/api/routers/test_user_router.py`
- [X] T010 [US1] Testar que UUID sem conta ativa não altera registros e retorna 404 em `DELETE /users/{user_id}` em `tests/api/routers/test_user_router.py`
- [X] T011 [US1] Testar que segunda desativação de conta inativa não altera auditoria e retorna 404 em `DELETE /users/{user_id}` em `tests/api/routers/test_user_router.py`

### Implementation for User Story 1

- [X] T012 [US1] Declarar `DELETE /users/{user_id}` com `UserManager`, `TrustedOrigin`, operação OpenAPI `deactivateUser` e respostas 204, 401, 403, 404 e 409 em `src/pivma/routers/users.py`
- [X] T013 [US1] Buscar a conta alvo ativa com `SELECT ... FOR UPDATE` e responder 404 quando ela não existir em `src/pivma/routers/users.py`
- [X] T014 [US1] Aplicar `set_deletion_audit(actor.id)`, confirmar a transação e retornar `Response(status_code=204)` em `src/pivma/routers/users.py`

**Checkpoint**: A US1 está pronta quando uma conta não administrativa é desativada com auditoria e as listagens preservam seus contratos.

---

## Phase 4: User Story 2 - Preservar o acesso administrativo (Priority: P2)

**Goal**: A rota não permite autodesativação nem deixa a plataforma sem uma conta administrativa ativa.

**Independent Test**: A autodesativação e a tentativa de remover a última conta administrativa retornam 409 sem desativar a alvo; duas remoções concorrentes preservam ao menos uma conta administrativa ativa.

### Tests for User Story 2

- [X] T015 [US2] Testar que autodesativação preserva a conta autora e retorna 409 em `tests/api/routers/test_user_router.py`
- [X] T016 [US2] Testar que tentativa contra a última conta administrativa preserva a conta alvo e retorna 409 em `tests/api/routers/test_user_router.py`
- [X] T017 [US2] Testar que a desativação de uma entre duas contas administrativas preserva outra conta administrativa ativa em `tests/api/routers/test_user_router.py`
- [X] T018 [US2] Testar com duas sessões independentes e barreira que desativações administrativas concorrentes retornam um 204 e um 409 em `tests/api/routers/test_user_router.py`
- [X] T019 [US2] Testar com duas sessões independentes que a concorrência administrativa deixa ao menos uma conta administrativa ativa em `tests/api/routers/test_user_router.py`

### Implementation for User Story 2

- [X] T020 [US2] Rejeitar autodesativação com HTTP 409 antes de alterar a conta alvo em `src/pivma/routers/users.py`
- [X] T021 [US2] Executar `ensure_administrator_remains` após o `flush`, fazer rollback em `ValueError` e responder 409 em `src/pivma/routers/users.py`

**Checkpoint**: A US2 está pronta quando todas as saídas de conflito preservam a conta alvo e a invariante administrativa, inclusive sob concorrência.

---

## Phase 5: User Story 3 - Revogar o uso de sessões existentes (Priority: P3)

**Goal**: Credenciais de uma conta desativada deixam de conceder acesso imediatamente.

**Independent Test**: Após a desativação pela rota da US1, a credencial emitida anteriormente recebe 401 em endpoint protegido e um novo login da conta também recebe 401.

### Tests for User Story 3

- [X] T022 [US3] Testar que um token emitido antes da desativação recebe 401 em `GET /auth/me` em `tests/api/routers/test_user_router.py`
- [X] T023 [US3] Testar que login de conta desativada recebe 401 em `POST /auth/login` em `tests/api/routers/test_user_router.py`

### Implementation for User Story 3

Não há código adicional: `get_current_user` e o login já filtram contas inativas. A US3 é comprovada pelos testes T022 e T023 depois da transição implementada na US1.

**Checkpoint**: A US3 está pronta quando os dois usos de credencial são rejeitados pelo controle de conta ativa já existente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificar a alteração completa e documentar somente o contrato entregue.

- [X] T024 Atualizar o contrato de `DELETE /users/{user_id}` no `README.md`
- [X] T025 [P] Executar `poetry run pytest -q tests/api/routers/test_user_router.py` para validar a feature em `tests/api/routers/test_user_router.py`
- [X] T026 [P] Executar `poetry run ruff check src/pivma/routers/users.py tests/api/routers/test_user_router.py` para verificar os arquivos alterados
- [X] T027 Executar `poetry run pytest -q` para validar regressões em `tests/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Inicia imediatamente.
- **Foundational (Phase 2)**: Não introduz bloqueio novo; confirma o reuso dos componentes existentes.
- **US1 (Phase 3)**: Depende de T001. É o MVP e fornece a transição de estado usada pelas histórias seguintes.
- **US2 (Phase 4)**: Depende de T013 e T014 para complementar a mesma rota com proteção transacional.
- **US3 (Phase 5)**: Depende da desativação concluída na US1; não adiciona mecanismo de sessão.
- **Polish (Phase 6)**: Depende de US1, US2 e US3.

### User Story Dependencies

- **US1 (P1)**: Independente depois de T001.
- **US2 (P2)**: Estende o endpoint da US1 para aplicar a invariante administrativa.
- **US3 (P3)**: Revalida o estado da conta no fluxo de autenticação já entregue após a transição da US1.

### Within Each User Story

- Implementar testes antes do código correspondente.
- Em US1, concluir T012 → T013 → T014.
- Em US2, concluir T020 antes de T021.
- Não executar T021 fora da transação da rota e não substituir a invariante existente.

## Parallel Opportunities

Os casos de teste não recebem marcador `[P]` porque todos alteram o mesmo módulo `tests/api/routers/test_user_router.py`. Após a implementação, T025 e T026 podem ser executadas em paralelo; T027 é a verificação final da suíte.

## Implementation Strategy

### MVP First

1. Concluir T001 a T014.
2. Executar a validação focada da US1.
3. Demonstrar a desativação auditável e a visibilidade correta nas listagens.

### Incremental Delivery

1. US1 entrega a desativação de conta ativa.
2. US2 protege a invariante administrativa sem criar mecanismo paralelo.
3. US3 comprova a revogação pelo controle de conta ativa existente.
4. Atualizar README e executar verificações finais.

## Format Validation

Todas as 27 tarefas seguem o formato obrigatório: checkbox, ID sequencial, marcador `[P]` apenas quando paralelo, rótulo de história nas fases de história e caminho de arquivo explícito.
