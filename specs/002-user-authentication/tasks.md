---

description: "Tarefas de implementação para autenticação de usuários"
---

# Tasks: Autenticação de Usuários

**Input**: Artefatos de projeto em `/specs/002-user-authentication/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/auth.openapi.yaml` e `quickstart.md`

**Tests**: A especificação e o repositório exigem testes para todo comportamento novo. Escreva os testes de cada história antes da implementação correspondente e confirme que falham pelo motivo esperado.

**Organization**: As tarefas seguem as histórias de usuário para manter rastreabilidade e permitir validação incremental.

## Phase 1: Setup

**Purpose**: Registrar a única dependência nova e a configuração pública exigida pela feature.

- [X] T001 [P] Adicionar `PyJWT >=2.13,<3.0` a `pyproject.toml` e atualizar `poetry.lock`.
- [X] T002 [P] Documentar `JWT_SECRET_KEY` e `AUTH_ALLOWED_ORIGINS` em `.env.example` sem incluir valores secretos e repassá-los ao serviço da API em `compose.yaml`.

---

## Phase 2: Foundational

**Purpose**: Preparar validação de configuração, emissão e leitura de JWT e a dependência que identifica uma conta ativa. Estas tarefas bloqueiam as histórias de usuário.

- [X] T003 Estender `Settings` em `src/pivma/core/settings.py` para exigir chave JWT de pelo menos 32 bytes e lista explícita de origens confiáveis.
- [X] T004 Escrever testes unitários de criação e validação de JWT em `tests/core/test_security.py`, incluindo assinatura HS256, claims obrigatórios, expiração e token adulterado.
- [X] T005 Implementar emissão e validação de JWT HS256 de até 8 horas em `src/pivma/core/security.py`, sem `jti`, refresh, rotação ou persistência.
- [X] T006 [P] Criar schemas de credenciais e identidade pública em `src/pivma/schemas.py`, sem incluir senha ou JWT em respostas.
- [X] T007 Criar a dependência de conta autenticada em `src/pivma/routers/auth.py`, buscando `sub` no cookie `access_token` e recusando token ausente, inválido, vencido ou associado a conta excluída.

**Checkpoint**: A aplicação consegue validar a configuração e transformar um cookie JWT válido em uma conta ativa, sem expor identidade por endpoint ainda.

---

## Phase 3: User Story 1 - Iniciar sessão (Priority: P1) 🎯 MVP

**Goal**: Permitir login por username ou e-mail e reconhecer a mesma conta em uma requisição posterior.

**Independent Test**: Criar uma conta, autenticar por username e por e-mail, chamar `GET /auth/me` com o cookie e confirmar a identidade. Credenciais incorretas, identificador inexistente e conta excluída devem retornar a mesma falha pública sem cookie.

### Tests for User Story 1

- [X] T008 [US1] Escrever testes de contrato para `POST /auth/login` e `GET /auth/me` em `tests/routers/test_auth.py`, cobrindo ambos os identificadores, falha pública uniforme, ausência de segredo e conta excluída.

### Implementation for User Story 1

- [X] T009 [US1] Implementar busca case-insensitive de conta ativa por username ou e-mail e verificação Argon2id em `src/pivma/routers/auth.py`.
- [X] T010 [US1] Implementar `POST /auth/login` e `GET /auth/me` em `src/pivma/routers/auth.py` conforme `contracts/auth.openapi.yaml`.
- [X] T011 [US1] Registrar o router de autenticação em `src/pivma/__init__.py` e executar `poetry run pytest tests/core/test_security.py tests/routers/test_auth.py` para validar a história.

**Checkpoint**: Login e reconhecimento de identidade funcionam para contas ativas sem conceder permissões ou acesso a recursos de domínio.

---

## Phase 4: User Story 2 - Preservar a sessão com segurança (Priority: P2)

**Goal**: Proteger o cookie, limitar a sessão a oito horas e remover o cookie apenas em logout com origem confiável.

**Independent Test**: Examinar o `Set-Cookie` do login, testar token adulterado ou vencido e chamar logout com origem confiável, ausente e externa. Após logout aceito, `GET /auth/me` deve retornar 401.

### Tests for User Story 2

- [X] T012 [US2] Estender `tests/routers/test_auth.py` com testes para atributos `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/` e expiração de 8 horas, token adulterado e vencido, logout e validação de `Origin`.

### Implementation for User Story 2

- [X] T013 [US2] Configurar o cookie `access_token` e implementar `POST /auth/logout` em `src/pivma/routers/auth.py`, exigindo origem configurada antes de remover o cookie e sem revogar token no servidor.
- [X] T014 [US2] Configurar CORS com a lista explícita de `AUTH_ALLOWED_ORIGINS` e credenciais em `src/pivma/__init__.py`, sem curingas para origem, método ou cabeçalho.
- [X] T015 [US2] Ajustar a configuração de testes HTTPS e origens confiáveis em `tests/conftest.py` e executar `poetry run pytest tests/core/test_security.py tests/routers/test_auth.py`.

**Checkpoint**: A sessão usa somente cookie seguro de oito horas; logout remove o cookie com proteção de origem e não introduz refresh nem revogação persistente.

---

## Phase 5: Polish and regression validation

**Purpose**: Confirmar contratos existentes, qualidade e o guia de validação.

- [X] T016 [P] Executar `poetry run pytest` e conferir a saída do Pytest para regressões em `tests/`.
- [X] T017 [P] Executar `poetry run ruff check` e corrigir somente problemas introduzidos em `src/pivma/`, `tests/`, `pyproject.toml`, `compose.yaml` e `.env.example`.
- [X] T018 Validar os cenários de `specs/002-user-authentication/quickstart.md` e alinhar os artefatos da feature se o contrato implementado divergir.

---

## Dependencies & Execution Order

```text
Setup (T001–T002)
    ↓
Foundation (T003–T007)
    ↓
US1: login e identidade (T008–T011)
    ↓
US2: cookie e logout protegido (T012–T015)
    ↓
Polish e regressão (T016–T018)
```

- US1 depende da fundação para assinar e validar o JWT.
- US2 depende de US1 porque modifica o cookie emitido pelo login e reutiliza a identidade autenticada.
- A etapa final depende das duas histórias.

## Parallel Opportunities

- T001 e T002 podem ocorrer em paralelo, pois alteram arquivos distintos.
- Após T003, T004 pode começar enquanto T002 é revisada; T005 depende de T004 para seguir testes primeiro.
- T016 e T017 podem rodar em paralelo após T015, se ambientes de trabalho isolados evitarem conflito nos artefatos gerados pelos testes.

## Implementation Strategy

### MVP first

1. Complete T001–T007.
2. Complete T008–T011.
3. Execute o teste independente de US1 e pare para revisão.

### Incremental delivery

1. Entregue US1 com login e `GET /auth/me`.
2. Acrescente US2 com os atributos de cookie, CORS e logout protegido.
3. Execute a suíte completa e o linter antes de concluir.

## Scope guardrails

- Não criar migrações, tabelas, refresh token, rotação, blacklist, revogação persistente, gerenciamento de sessões ou MFA.
- Não incluir perfis, permissões, vínculos institucionais ou laboratoriais, designação de participantes, recuperação ou troca de senha.
- Preservar `POST /users/` e a regra atual de reutilização de identificadores de conta excluída logicamente.
