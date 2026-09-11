# Tasks: Limpeza e Padronização do Contrato de Sessão Atual

**Feature**: `019-clean-auth-me-response`  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

---

## Phase 1: Setup & Contracts

**Purpose**: Sincronização e preparação dos contratos de interface formal

- [X] T001 Sincronizar a remoção de `allOf` e campos de primeiro nível em `specs/002-user-authentication/contracts/auth.openapi.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Estruturação do schema de dados no backend que bloqueia todas as histórias

**⚠️ CRITICAL**: Nenhuma alteração de router ou cliente pode ocorrer sem a atualização do DTO base.

- [X] T002 Redefinir `CurrentUserResponse` em `src/pivma/schemas.py` herdando de `BaseModel` com `model_config = ConfigDict(extra='forbid')`, contendo apenas `user: UserIdentity` e `access: CurrentUserAccess`

**Checkpoint**: DTO estrito e não redundante disponível para integração.

---

## Phase 3: User Story 1 - Consumo Estruturado da Identidade e Acesso da Sessão (Priority: P1) 🎯 MVP

**Goal**: Limpar o endpoint `GET /auth/me` e a suíte de testes de autenticação, removendo qualquer tolerância ou teste para chaves legadas na raiz.

**Independent Test**: Autenticar uma conta ativa, chamar `GET /auth/me` e verificar que a resposta contém exclusivamente `user` e `access`, com 0 campos na raiz.

### Tests for User Story 1 ⚠️

- [X] T003 [P] [US1] Atualizar testes de contrato em `tests/api/routers/test_auth_router.py` removendo asserções de `id`, `username`, `email` e `full_name` da raiz e validando a estrutura estrita `{ 'user': { ... }, 'access': { ... } }`

### Implementation for User Story 1

- [X] T004 [US1] Refatorar `read_current_user` em `src/pivma/routers/auth.py` para instanciar `CurrentUserResponse(user=identity, access=CurrentUserAccess(...))` sem descompactação `**identity.model_dump()`
- [X] T005 [US1] Executar testes de contrato de autenticação com `pytest tests/api/routers/test_auth_router.py` garantindo que todos passem e a quebra de compatibilidade seja aplicada

**Checkpoint**: User Story 1 concluída e testável de forma independente. O backend entrega unicamente a estrutura limpa e nova.

---

## Phase 4: User Story 2 - Atualização Consistente de Consumidores e Telas de Demonstração (Priority: P2)

**Goal**: Atualizar todas as interfaces de demonstração em `demos/` para consumir os dados do usuário a partir do nó encapsulado `user.user.*`.

**Independent Test**: Acessar as interfaces de demonstração e checar se o cabeçalho exibe as informações corretas do usuário logado.

### Implementation for User Story 2

- [X] T006 [P] [US2] Atualizar o consumo de sessão em `demos/ai-pipeline/app.js` para referenciar `user.user.full_name || user.user.username` e `user.user.username`
- [X] T007 [P] [US2] Atualizar o consumo de sessão em `demos/attachments/index.html` para referenciar `u.user.full_name || u.user.username` e `u.user.username`
- [X] T008 [P] [US2] Atualizar o consumo de sessão em `demos/forms/ai-config.html` para referenciar `u.user.full_name || u.user.username` e `u.user.username`
- [X] T009 [P] [US2] Atualizar o consumo de sessão em `demos/forms/index.html` para referenciar `user.user.full_name || user.user.username` e `user.user.username`
- [X] T010 [P] [US2] Atualizar o consumo de sessão em `demos/operational-index/app.js` para referenciar `user.user.full_name || user.user.username` e `user.user.username`
- [X] T011 [P] [US2] Atualizar o consumo de sessão em `demos/roadmap/index.html` para referenciar `user.user.full_name || user.user.username` e `user.user.username`
- [X] T012 [P] [US2] Atualizar o consumo de sessão em `demos/submission/index.html` para referenciar `user.user.full_name || user.user.username` e `user.user.username`
- [X] T013 [P] [US2] Atualizar o consumo de sessão em `demos/triage/index.html` para referenciar `user.user.full_name || user.user.username` e `user.user.username`
- [X] T014 [P] [US2] Atualizar o consumo de sessão em `demos/users/index.html` para referenciar `user.user.full_name || user.user.username` e `user.user.username`

**Checkpoint**: Todas as páginas de demonstração operam perfeitamente contra a nova resposta de `GET /auth/me`.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verificação de qualidade, formatação e validação de regressão

- [X] T015 Executar validação manual de contrato conforme roteiro em `specs/019-clean-auth-me-response/quickstart.md`
- [X] T016 [P] Executar lint e formatação de código com `poe lint` e `poe format`
- [X] T017 Executar a suíte de testes de integração com `poe test` ou `pytest tests/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup & Contracts (Phase 1)**: Não possui dependências — pode iniciar imediatamente.
- **Foundational (Phase 2)**: Depende de Phase 1 — BLOQUEIA a implementação das histórias de usuário.
- **User Story 1 (Phase 3)**: Depende da conclusão de Phase 2.
- **User Story 2 (Phase 4)**: Depende da conclusão de US1 (Phase 3).
- **Polish (Phase 5)**: Depende da conclusão de US1 e US2.

### Within Each User Story

- Testes de contrato (T003) são preparados para validar o novo formato.
- Refatoração do router (T004) implementa a entrega do modelo limpo.
- Execução dos testes (T005) confirma o sucesso da entrega de US1.
- As tarefas de migração das demos em US2 (T006 a T014) podem ser executadas em paralelo por operarem em arquivos independentes.

---

## Parallel Example: User Story 2

```bash
# Execução paralela de migração das páginas de demonstração:
Task: "T006 [P] [US2] Atualizar o consumo de sessão em demos/ai-pipeline/app.js"
Task: "T007 [P] [US2] Atualizar o consumo de sessão em demos/attachments/index.html"
Task: "T008 [P] [US2] Atualizar o consumo de sessão em demos/forms/ai-config.html"
Task: "T009 [P] [US2] Atualizar o consumo de sessão em demos/forms/index.html"
Task: "T010 [P] [US2] Atualizar o consumo de sessão em demos/operational-index/app.js"
Task: "T011 [P] [US2] Atualizar o consumo de sessão em demos/roadmap/index.html"
Task: "T012 [P] [US2] Atualizar o consumo de sessão em demos/submission/index.html"
Task: "T013 [P] [US2] Atualizar o consumo de sessão em demos/triage/index.html"
Task: "T014 [P] [US2] Atualizar o consumo de sessão em demos/users/index.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Concluir Phase 1 (Sincronização do Contrato OpenAPI).
2. Concluir Phase 2 (Redefinição do DTO `CurrentUserResponse`).
3. Concluir Phase 3 (Refatoração de `GET /auth/me` e testes de contrato).
4. **Validar MVP**: Confirmar que a API entrega exclusivamente `{ "user": { ... }, "access": { ... } }`.

### Entrega Incremental

1. MVP entregue (API e testes de contrato verdes).
2. Migrar páginas de demonstração (US2).
3. Rodar checagens de formatação, linter e suíte completa de testes (Polish).
