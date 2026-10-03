---
description: "Tarefas da Spec 038 — token de acesso no corpo da resposta de login"
---

# Tasks: Token de Acesso no Corpo da Resposta de Login

**Input**: `specs/038-login-token-body/` (plan.md, spec.md, research.md, data-model.md, contracts/auth-login.openapi.yaml, quickstart.md)

**Tests**: obrigatórios (AGENTS.md e Constituição V). Login é risco **crítico** na matriz da skill `fastapi-testing-methodology`, então cada ramo de autenticação e de origem tem teste de API próprio. A granularidade é um teste por comportamento observável. Os testes de cada história vêm antes da implementação e devem falhar antes do código, salvo onde a tarefa diz que o comportamento já existe e o teste serve de regressão.

**Organization**: tarefas agrupadas por história de usuário. Use a skill `andrej-karpathy-skills:karpathy-guidelines` em cada tarefa de código e `fastapi-testing-methodology` antes de escrever testes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: US1 a US5, conforme `spec.md`

## Convenções para os testes desta feature

- Arquivo único de teste: `tests/api/routers/test_auth_router.py`. Como todos os testes ficam nele, as tarefas de teste não levam `[P]` entre si.
- Reaproveite as fixtures `client`, `session`, `user`, `other_user`, `deleted_user` e as constantes `VALID_PASSWORD`, `JWT_SECRET_KEY` e `TRUSTED_ORIGIN`. Autentique por cookie com o helper `login(client, user.username)` e envie mutações com `update_me(client, payload, origin=...)`.
- Para Bearer, use o helper criado em T014: ele faz login, lê `access_token` do corpo, executa `client.cookies.clear()` e devolve `{'Authorization': f'Bearer {token}'}`. Sem limpar os cookies, o cookie gravado pelo login teria precedência e o teste não provaria o Bearer.
- Para provar "conta inalterada", use o helper `account_state(user)` antes da requisição e compare depois de `await session.refresh(user)`, como nos testes da Spec 037.
- Erros são conferidos por `detail.code` (formato da Spec 034).
- Os testes de erro do login já existentes (`test_login_rejects_incorrect_password_without_secret`, `test_login_rejects_unknown_identifier_with_same_response`, `test_login_rejects_deleted_user_with_same_response`) comparam o JSON inteiro e a ausência do cookie, então já provam FR-006 e SC-003. Eles não mudam.

---

## Phase 1: Setup

**Purpose**: registrar a linha de base antes de qualquer mudança.

- [X] T001 Rodar `poetry run pytest tests/api/routers/test_auth_router.py -q` e `poetry run ruff check src tests` e anotar o resultado como linha de base; qualquer falha prévia deve ser reportada antes de seguir (não corrigir nesta feature)

---

## Phase 2: Foundational

**Purpose**: esquema de segurança Bearer compartilhado por US2, US4 e US5.

- [X] T002 Declarar `bearer_token = HTTPBearer(auto_error=False)` ao lado de `access_token_cookie` em `src/pivma/dependencies.py`, importando `HTTPBearer` de `fastapi.security` (research.md, item 3). Ainda não usar o objeto; ele é ligado em T022 e T038

**Checkpoint**: suíte de T001 continua verde.

---

## Phase 3: User Story 1 - Obter o token no corpo do login (Priority: P1) 🎯 MVP

**Goal**: `POST /auth/login` responde `{"access_token", "token_type": "bearer", "expires_in": 28800}` com `Cache-Control: no-store`, mantendo o cookie.

**Independent Test**: login válido devolve os três campos, e `access_token` é igual ao cookie.

### Tests for User Story 1

- [X] T003 [US1] Em `test_login_with_username_and_recognize_identity`, remover a asserção `assert response.content == b''`, que contradiz FR-001; o restante do teste fica igual, em `tests/api/routers/test_auth_router.py`
- [X] T004 [US1] Testar que o login válido responde um corpo cujas chaves são exatamente `{'access_token', 'token_type', 'expires_in'}` em `tests/api/routers/test_auth_router.py`
- [X] T005 [US1] Testar que o login válido responde `token_type == 'bearer'` em `tests/api/routers/test_auth_router.py`
- [X] T006 [US1] Testar que o login válido responde `expires_in == int(ACCESS_TOKEN_TTL.total_seconds())`, importando `ACCESS_TOKEN_TTL` de `pivma.core.security`, e que esse valor é `28800`, em `tests/api/routers/test_auth_router.py`
- [X] T007 [US1] Testar que `response.json()['access_token']` é igual a `response.cookies['access_token']` na mesma resposta de login em `tests/api/routers/test_auth_router.py`
- [X] T008 [US1] Testar que `decode_access_token(response.json()['access_token'], JWT_SECRET_KEY)`, importando `decode_access_token` de `pivma.core.security`, devolve `user.id`, provando que o corpo carrega um token válido da própria conta, em `tests/api/routers/test_auth_router.py`
- [X] T009 [US1] Testar que o JWT do corpo expira em `expires_in` segundos após a emissão: decodificar com `jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])` (importar `jwt`) e conferir `payload['exp'] - payload['iat'] == response.json()['expires_in']`, cobrindo FR-004 e o edge case "validade coerente", em `tests/api/routers/test_auth_router.py`
- [X] T010 [US1] Testar que o login válido responde com o cabeçalho `Cache-Control` igual a `no-store` em `tests/api/routers/test_auth_router.py`
- [X] T011 [US1] Rodar os testes T003 a T010 e confirmar que T004 a T010 falham pelo motivo esperado (corpo vazio, sem token para decodificar e ausência de `Cache-Control`)

### Implementation for User Story 1

- [X] T012 [P] [US1] Criar `class LoginResponse(BaseModel)` logo após `LoginCredentials` em `src/pivma/schemas.py`, com `access_token: str`, `token_type: Literal['bearer']` e `expires_in: int`, todos sem valor padrão para saírem como `required` no OpenAPI (research.md, item 1)
- [X] T013 [US1] Na rota `login` de `src/pivma/routers/auth.py`, trocar `response_class=Response` por `response_model=LoginResponse`, anotar o retorno como `-> LoginResponse`, calcular `expires_in = int(ACCESS_TOKEN_TTL.total_seconds())` uma vez e usá-lo no `max_age` do cookie, definir `response.headers['Cache-Control'] = 'no-store'` e retornar `LoginResponse(access_token=token, token_type='bearer', expires_in=expires_in)`. Os caminhos de erro 401 não mudam (depende de T012)

**Checkpoint**: T003 a T010 verdes; testes de erro do login e de cookie continuam verdes sem alteração.

---

## Phase 4: User Story 2 - Usar o token recebido como Bearer (Priority: P1)

**Goal**: o token do corpo autentica rotas protegidas via `Authorization: Bearer`, lido pelo esquema `HTTPBearer`.

**Independent Test**: login, limpar cookies, `GET /auth/me` com Bearer reconhece a conta.

### Tests for User Story 2

- [X] T014 [US2] Criar o helper `bearer_headers_after_login(client, user)` descrito nas convenções, logo após `login` em `tests/api/routers/test_auth_router.py` (depende de US1)
- [X] T015 [US2] Testar que `GET /auth/me` sem cookie e com o Bearer de T014 responde 200 com `json()['user']['id'] == str(user.id)` em `tests/api/routers/test_auth_router.py` (regressão: a leitura manual atual já aceita Bearer)
- [X] T016 [US2] Testar que `GET /auth/me` com o esquema em minúsculas (`Authorization: bearer <token>`) responde 200, comportamento novo do `HTTPBearer` conforme RFC 7235, em `tests/api/routers/test_auth_router.py`
- [X] T017 [US2] Testar que `GET /auth/me` sem cookie e com Bearer de assinatura adulterada responde 401 `not_authenticated`, reaproveitando a técnica de adulteração de `test_me_rejects_tampered_token`, em `tests/api/routers/test_auth_router.py`
- [X] T018 [US2] Testar que `GET /auth/me` sem cookie e com Bearer expirado (gerado com `create_access_token(..., now=datetime.now(UTC) - timedelta(hours=8, seconds=1))`) responde 401 `not_authenticated` em `tests/api/routers/test_auth_router.py`
- [X] T019 [US2] Testar que `GET /auth/me` com `Authorization: Basic dXNlcjpwYXNz` e sem cookie responde 401 `not_authenticated`, e não 403, garantindo `auto_error=False`, em `tests/api/routers/test_auth_router.py`
- [X] T020 [US2] Testar que `GET /auth/me` com cookie de `user` e `Authorization: Bearer` com token de `other_user` responde a identidade de `user`, provando a precedência do cookie, em `tests/api/routers/test_auth_router.py`
- [X] T021 [US2] Rodar T014 a T020 e confirmar que apenas T016 (esquema `bearer` em minúsculas) falha com o código atual, que exige o prefixo `Bearer ` exato, e que os demais já passam

### Implementation for User Story 2

- [X] T022 [US2] Em `get_current_user` de `src/pivma/dependencies.py`, receber `bearer: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_token)]` e substituir a leitura manual de `request.headers.get('Authorization')` por `access_token = bearer.credentials` quando `access_token is None and bearer is not None`; manter depois o fallback do parâmetro de consulta `token`, que continua usando `request`. Importar `HTTPAuthorizationCredentials` de `fastapi.security` e remover só o código que esta troca deixar sem uso (depende de T002)

**Checkpoint**: T015 a T020 verdes e todos os testes atuais de `/auth/me` continuam verdes.

---

## Phase 5: User Story 3 - Navegador continua com sessão por cookie (Priority: P1)

**Goal**: nenhuma regressão no cookie `HttpOnly`.

**Independent Test**: atributos do cookie e `GET /auth/me` só com cookie, como antes.

### Tests for User Story 3

- [X] T023 [US3] Testar que o `Max-Age` do cookie de login é igual ao `expires_in` do corpo da mesma resposta (FR-005), extraindo o valor de `response.headers['set-cookie']`, em `tests/api/routers/test_auth_router.py`
- [X] T024 [US3] Confirmar, sem editar, que `test_login_sets_secure_cookie_for_eight_hours`, `test_login_with_username_and_recognize_identity` (fluxo só com cookie), os testes de logout por cookie (SC-004) e os três testes de erro do login `test_login_rejects_incorrect_password_without_secret`, `test_login_rejects_unknown_identifier_with_same_response` e `test_login_rejects_deleted_user_with_same_response` (FR-006, SC-003) passam após US1 e US2

### Implementation for User Story 3

Nenhuma. A história é garantida por T013 (mesmo `max_age`) e pelos testes acima.

**Checkpoint**: cookie inalterado e coerente com o corpo.

---

## Phase 6: User Story 4 - Executar mutações com Bearer (Priority: P1)

**Goal**: sem cookie e com Bearer, `require_trusted_origin` dispensa `Origin`; com cookie, a checagem continua.

**Independent Test**: login, limpar cookies, `PATCH /auth/me` com Bearer e sem `Origin` responde 200.

### Tests for User Story 4

- [X] T025 [US4] Testar que `PATCH /auth/me` sem cookie, com Bearer e sem `Origin` responde 200 com o `full_name` novo no corpo em `tests/api/routers/test_auth_router.py`
- [X] T026 [US4] Testar que a mutação de T025 persiste o `full_name` no banco, conferido com `await session.refresh(user)`, em `tests/api/routers/test_auth_router.py`
- [X] T027 [US4] Testar que `PATCH /auth/me` sem cookie, com Bearer e `Origin: https://attacker.example` responde 200, já que a dispensa não depende do valor de `Origin`, em `tests/api/routers/test_auth_router.py`
- [X] T028 [US4] Testar que `POST /auth/logout` sem cookie, com Bearer e sem `Origin` responde 204, provando a dispensa numa segunda rota com `TrustedOrigin`, em `tests/api/routers/test_auth_router.py`
- [X] T029 [US4] Testar que `PATCH /auth/me` com cookie e Bearer válidos e sem `Origin` responde 403 `invalid_origin` em `tests/api/routers/test_auth_router.py`
- [X] T030 [US4] Testar que a requisição de T029 não altera a conta (comparação com `account_state(user)`) em `tests/api/routers/test_auth_router.py`
- [X] T031 [US4] Testar que `PATCH /auth/me` com cookie e Bearer válidos e `Origin: https://attacker.example` responde 403 `invalid_origin` em `tests/api/routers/test_auth_router.py`
- [X] T032 [US4] Testar que `POST /auth/logout` com cookie e Bearer e sem `Origin` responde 403 `invalid_origin` e mantém o cookie no cliente em `tests/api/routers/test_auth_router.py`
- [X] T033 [US4] Testar que `PATCH /auth/me` sem cookie, com Bearer adulterado e sem `Origin` responde 401 `not_authenticated`, e não 403, em `tests/api/routers/test_auth_router.py`
- [X] T034 [US4] Testar que a requisição de T033 não altera a conta (comparação com `account_state(user)`) em `tests/api/routers/test_auth_router.py`
- [X] T035 [US4] Testar que `PATCH /auth/me?token=<token válido>` sem cookie, sem Bearer e sem `Origin` responde 403 `invalid_origin`, fixando que o parâmetro de consulta não ganha a dispensa (data-model.md, última linha da matriz), em `tests/api/routers/test_auth_router.py`
- [X] T036 [US4] Confirmar, sem editar, que `test_update_me_rejects_untrusted_origin` (cookie sem `Origin` e com origem não confiável) e `test_logout_rejects_missing_origin_without_removing_cookie` continuam passando
- [X] T037 [US4] Rodar T025 a T035 e confirmar que T025, T026, T027 e T028 falham com 403 `invalid_origin` antes da implementação, e que os demais já passam. CONFIRMADO no código: em `PATCH /auth/me` e no logout, `CurrentUser` é resolvido antes de `TrustedOrigin` (`routers/auth.py:203-205`, `233-234`), então o Bearer adulterado já dá 401 antes da checagem de `Origin`

### Implementation for User Story 4

- [X] T038 [US4] Em `require_trusted_origin` de `src/pivma/dependencies.py`, receber `access_token: Annotated[str | None, Security(access_token_cookie)]` e `bearer: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_token)]`, e retornar antes da checagem de `Origin` quando `access_token is None and bearer is not None`; o restante da função não muda. Adicionar uma linha de comentário dizendo que CSRF depende de credencial anexada automaticamente pelo navegador, o que só acontece com o cookie (research.md, item 4) (depende de T002 e T022)

**Checkpoint**: T025 a T036 verdes; nenhum teste de origem por cookie em outros routers quebrou (`poetry run pytest tests/api -q`).

---

## Phase 7: User Story 5 - Contrato do login documentado (Priority: P2)

**Goal**: OpenAPI mostra `LoginResponse` e o esquema `HTTPBearer`.

**Independent Test**: `/openapi.json` traz o schema e os dois esquemas de segurança.

### Tests for User Story 5

- [X] T039 [US5] Testar que a resposta 200 de `POST /auth/login` no OpenAPI referencia `#/components/schemas/LoginResponse` em `tests/api/routers/test_auth_router.py`
- [X] T040 [US5] Testar que o schema `LoginResponse` tem `required == ['access_token', 'token_type', 'expires_in']` em `tests/api/routers/test_auth_router.py`
- [X] T041 [US5] Testar que `LoginResponse.properties.token_type` declara `const: 'bearer'` em `tests/api/routers/test_auth_router.py`
- [X] T042 [US5] Testar que `LoginResponse.properties.expires_in` tem `type: 'integer'` em `tests/api/routers/test_auth_router.py`
- [X] T043 [US5] Testar que `components.securitySchemes.HTTPBearer == {'type': 'http', 'scheme': 'bearer'}` em `tests/api/routers/test_auth_router.py`
- [X] T044 [US5] Testar que a `security` de `GET /auth/me` contém `{'APIKeyCookie': []}` e `{'HTTPBearer': []}` em `tests/api/routers/test_auth_router.py`
- [X] T045 [US5] Testar que a `security` de `PATCH /auth/me` contém `{'APIKeyCookie': []}` e `{'HTTPBearer': []}` em `tests/api/routers/test_auth_router.py`
- [X] T046 [US5] Testar que `GET /auth/me` não declara `Authorization` como parâmetro de cabeçalho no OpenAPI, no mesmo estilo da checagem de `access_token` em `test_openapi_declares_access_token_as_cookie_security_scheme`, em `tests/api/routers/test_auth_router.py`

### Implementation for User Story 5

Nenhuma. O OpenAPI é gerado por T012, T013 e T022. Se algum teste falhar, corrigir na tarefa de origem, sem montar o schema à mão.

**Checkpoint**: T039 a T046 verdes; `test_openapi_declares_access_token_as_cookie_security_scheme` continua verde.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T047 [P] Atualizar `README.md` (FR-012): o login devolve `access_token`, `token_type` e `expires_in` no corpo para clientes fora do navegador; esses clientes usam `Authorization: Bearer`; mutações só com Bearer dispensam `Origin`; o frontend web continua usando apenas o cookie e não deve guardar o token do corpo; e corrigir `SameSite=Lax` para `SameSite=Strict`
- [X] T048 Revisar o diff de `src/pivma/dependencies.py`, `src/pivma/routers/auth.py` e `src/pivma/schemas.py` com a skill `andrej-karpathy-skills:karpathy-guidelines`: sem import órfão, sem código fora do escopo, `?token=` intacto
- [X] T049 Rodar `poetry run pytest -q` completo e confirmar que nenhuma suíte fora de `test_auth_router.py` regrediu
- [X] T050 Rodar `poetry run ruff check src tests` e `poetry run ruff format --check src tests` sem avisos
- [ ] T051 Executar a validação manual de `specs/038-login-token-body/quickstart.md` (passos 1 a 6) com a API local, se houver ambiente disponível; caso contrário, registrar que ficou pendente. **Pendente**: nenhuma API local do pivma estava rodando durante a implementação; os passos 1 a 5 têm equivalente automatizado na suíte, e o passo 6 (clique em "Authorize" no `/docs`) depende de execução manual

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependência.
- **Foundational (Phase 2)**: depois do Setup; bloqueia US2, US4 e US5.
- **US1 (Phase 3)**: depende só do Setup. É o MVP.
- **US2 (Phase 4)**: depende de US1 (o helper Bearer usa o token do corpo) e de T002.
- **US3 (Phase 5)**: depende de US1 (T023 compara cookie e corpo) e deve rodar depois de US2 (T024 confirma ausência de regressão).
- **US4 (Phase 6)**: depende de US2 (T038 reusa `bearer_token` e o helper T014).
- **US5 (Phase 7)**: depende de US1 e US2, que produzem o schema e o esquema de segurança.
- **Polish (Phase 8)**: depois de todas as histórias.

### Within Each User Story

- Testes antes da implementação, e confirmar a falha esperada antes de codar.
- `schemas.py` antes de `routers/auth.py`; `dependencies.py` em T022 antes de T038 (mesmo arquivo, sequencial).

### Parallel Opportunities

- T012 (`schemas.py`) pode ser escrito em paralelo aos testes T003 a T010 (`test_auth_router.py`).
- T047 (`README.md`) pode ser escrito em paralelo a T048.
- Os demais itens tocam `tests/api/routers/test_auth_router.py` ou `src/pivma/dependencies.py` e são sequenciais.

---

## Parallel Example: User Story 1

```bash
# Arquivos diferentes, sem dependência entre si:
Task: "T012 [P] [US1] Criar LoginResponse em src/pivma/schemas.py"
Task: "T004–T010 [US1] Testes do corpo e do Cache-Control em tests/api/routers/test_auth_router.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 e Phase 2.
2. Phase 3 (US1): o token sai no corpo com `Cache-Control: no-store`.
3. Parar e validar: clientes de API já conseguem ler o token (e a leitura manual atual do Bearer já autentica leituras).

### Incremental Delivery

1. US1 → token no corpo.
2. US2 → Bearer via `HTTPBearer`, com casos de erro e precedência do cookie cobertos.
3. US3 → regressão do cookie.
4. US4 → mutações com Bearer.
5. US5 → contrato OpenAPI.
6. Polish → README, revisão, suíte completa e Ruff.

Por decisão do usuário, tudo fica na branch atual `feat/auth-credentials-management`, sem branch própria.

---

## Notes

- 51 tarefas: 34 testes novos ou ajustados (1 ajuste e 33 novos), 1 helper de teste, 2 confirmações de regressão sem edição, 3 execuções de falha esperada, 5 de implementação de código, 1 de README e 5 de setup e verificação.
- Fora do escopo e sem tarefa (research.md, item 6): remoção do parâmetro `?token=` e revogação de token Bearer no logout.
- Marque cada tarefa como `[X]` ao concluir.
