---
description: "Tarefas da Spec 039 — recuperação de senha por token temporário"
---

# Tasks: Recuperação de Senha por Token Temporário

**Input**: `specs/039-password-reset/` (plan.md, spec.md, research.md, data-model.md, contracts/password-reset.openapi.yaml, quickstart.md)

**Tests**: obrigatórios (issue #45, AGENTS.md e Constituição V). A granularidade segue a skill `fastapi-testing-methodology`, com um teste por comportamento observável. Login e credenciais têm risco **crítico** na matriz, então os testes cobrem unidade, API, segurança e concorrência. Os testes de cada história vêm antes da implementação e devem falhar antes do código. A exceção é a US2, explicada na própria fase.

**Organization**: tarefas agrupadas por história de usuário. Use a skill `andrej-karpathy-skills:karpathy-guidelines` em cada tarefa de código e `fastapi-testing-methodology` em cada tarefa de teste.

**Decisão já tomada**: o token nunca vai para log, em nenhum ambiente (spec, Clarifications 2026-10-02; `docs/observacoes-e-pendencias.md`). Nenhuma tarefa reabre esse ponto.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: US1, US2 ou US3, conforme `spec.md`

## Convenções para os testes desta feature

- **Arquivos**:
  - `tests/api/routers/test_password_reset.py`: API, ponta a ponta.
  - `tests/api/routers/test_password_reset_concurrency.py`: concorrência.
  - `tests/unit/core/test_password_reset_token.py`: geração e hash do token.
  - `tests/unit/schemas/test_user_schemas.py`: schemas.
  - `tests/unit/notifications/test_password_reset_email_renderer.py`: e-mail.
  - `tests/unit/core/test_settings.py`: configuração.
  - `tests/integration/migrations/test_password_reset_migration.py`: migração.
  - Os nomes trazem o domínio para evitar colisão de import (pitfall 1).
- **Fixtures e factories existentes**:
  - Use `client`, `session`, `user`, `other_user`, `deleted_user`, `use_settings` e `email_settings` de `tests/conftest.py`.
  - Para perfis e vínculos, use `UserAccessProfileFactory` (`tests/factories/rbac_factory.py`) e `UserInstitutionalAffiliationFactory` (`tests/factories/institutional_factory.py`).
  - A senha das contas de `UserFactory` é `'Factory-Passphrase-2026'`.
  - Fixtures assíncronas usam `@pytest_asyncio.fixture` (pitfall 4).
  - Nunca use `uuid4()` solto em FK (pitfall 2).
- **Configuração independente do `.env`**:
  - `Settings` lê o `.env`, e o quickstart manda pôr `NOTIFICATION_EMAIL_BACKEND` e `PASSWORD_RESET_URL_TEMPLATE` lá. Por isso todo teste desta feature passa as duas variáveis explicitamente, inclusive como `None`.
  - Com template: `reset_settings` = `use_settings(email_settings(PASSWORD_RESET_URL_TEMPLATE='https://front.test/redefinir-senha/{token}'))`.
  - Sem template: `use_settings(email_settings(PASSWORD_RESET_URL_TEMPLATE=None))`.
  - Sem canal: `use_settings(email_settings(NOTIFICATION_EMAIL_BACKEND=None, PASSWORD_RESET_URL_TEMPLATE='https://front.test/redefinir-senha/{token}'))`, como em `tests/api/routers/test_invites_router.py:578`.
- **Captura de logs**:
  - `setup_logging()` roda ao importar `pivma` (`src/pivma/__init__.py:29`) e marca `pivma.operational` com `propagate = False`. O `caplog` não vê esse logger.
  - A fixture `operational_log` liga um `logging.StreamHandler(io.StringIO())` com `Formatter('%(message)s')` direto em `logging.getLogger('pivma.operational')`, entrega o `StringIO` e remove o handler no teardown, no padrão de `capture_jsonl` em `tests/unit/test_structured_logging.py:16`. Cada linha é um JSON do structlog com `event` e `level`.
  - Testes de "nada vaza em log" conferem as duas fontes: `caplog.text` e `operational_log.getvalue()`.
- **Token como a pessoa o recebe**:
  - O helper `deliver_reset_token(session, settings)` roda `process_next(session, channel, settings)` com um `FakeEmailChannel` novo, pega `channel.sent[-1]` e extrai o token do link `https://front.test/redefinir-senha/` em `message.text`.
  - Nenhum teste lê o token bruto do banco, porque lá só existe o hash.
- **Erros**: confira `detail.code` e `detail.message` (formato da Spec 034). O 400 de token é sempre `{'code': 'invalid_reset_token', 'message': 'Link de redefinição inválido ou expirado.'}`.
- **"Senha inalterada"**: capture `user.password_hash` antes, faça `await session.refresh(user)` depois e compare.
- **Mensagem neutra**: `'Se o e-mail estiver cadastrado, as instruções foram enviadas.'`; compare o corpo inteiro com `==`.

---

## Phase 1: Setup

**Purpose**: registrar a linha de base antes de qualquer mudança.

- [X] T001 Executar `uv run pytest tests/api/routers/test_auth_router.py tests/api/routers/test_user_update.py tests/api/routers/test_error_contract.py tests/api/routers/test_error_openapi.py tests/unit/core/test_settings.py tests/unit/schemas/test_user_schemas.py tests/integration/notifications -q` e `uv run alembic heads`, e anotar a saída real como linha de base: todos os testes verdes e uma única head, que será o `PREVIOUS` da migração nova

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: tabela, migração e configuração usadas pelas três histórias.

### Tests (escrever primeiro e ver falhar)

- [X] T002 [P] Testar que `upgrade` até a nova revisão cria a tabela `password_reset_tokens` com as colunas `id`, `user_id`, `token_hash`, `expires_at`, `used_at` e as seis de auditoria, no padrão de `test_notifications_migration.py` (fixture `migration_database` reaproveitada de `test_secure_user_registration`; `PREVIOUS` = a head anotada em T001), em tests/integration/migrations/test_password_reset_migration.py
- [X] T003 Testar que, após o `upgrade`, `pg_indexes` contém `uq_password_reset_tokens_token_hash` como `UNIQUE` sobre `token_hash` em tests/integration/migrations/test_password_reset_migration.py
- [X] T004 Testar que, após o `upgrade`, `pg_indexes` contém `ix_password_reset_tokens_user_id` sobre `user_id` em tests/integration/migrations/test_password_reset_migration.py
- [X] T005 Testar que `downgrade` para `PREVIOUS` remove a tabela `password_reset_tokens` em tests/integration/migrations/test_password_reset_migration.py
- [X] T006 [P] Testar que `Settings()` rejeita `PASSWORD_RESET_URL_TEMPLATE` sem `{token}` e com `{token}` duas vezes (parametrizado, `monkeypatch.setenv`, `match='PASSWORD_RESET_URL_TEMPLATE'`), no padrão dos testes de `INVITE_URL_TEMPLATE`, em tests/unit/core/test_settings.py
- [X] T007 Testar que `Settings()` com `monkeypatch.setenv('PASSWORD_RESET_URL_TEMPLATE', 'https://app.example.com/redefinir-senha/{token}')` guarda o valor em tests/unit/core/test_settings.py
- [X] T008 Testar que, sem a variável, `PASSWORD_RESET_URL_TEMPLATE is None`, sem depender do `.env`: `monkeypatch.setenv` para `DATABASE_URL`, `JWT_SECRET_KEY` (32 bytes ou mais) e `AUTH_ALLOWED_ORIGINS`, `monkeypatch.delenv('PASSWORD_RESET_URL_TEMPLATE', raising=False)` e `Settings(_env_file=None)`, em tests/unit/core/test_settings.py

### Implementation

- [X] T009 Criar o modelo `PasswordResetToken(AuditMixin)` logo após `RoleAssignmentInvite` em src/pivma/core/database/models.py, conforme data-model.md:
  - `id` UUID com `insert_default=uuid4`/`default_factory=uuid4`;
  - `user_id` com `ForeignKey('users.id')`;
  - `token_hash` como `String(64)`;
  - `expires_at`;
  - `used_at` como `datetime | None`, `default=None`;
  - `__table_args__` com `Index('uq_password_reset_tokens_token_hash', 'token_hash', unique=True)` e `Index('ix_password_reset_tokens_user_id', 'user_id')`;
  - docstring curta citando a Spec 039 e o estado derivado.
- [X] T010 Gerar a revisão com `uv run alembic revision --autogenerate -m "password_reset_tokens"` em migrations/versions/:
  - conferir que `down_revision` é a head anotada em T001;
  - manter só a criação da tabela, das FKs (`user_id` e as três de auditoria, com os nomes `fk_password_reset_tokens_*` do `AuditMixin`) e dos dois índices;
  - remover qualquer outra diferença que o autogenerate trouxer;
  - escrever o `downgrade` simétrico.
  - Depois, preencher `REVISION` no teste, confirmar que `uv run alembic heads` devolve uma única head (a nova) e que T002–T005 estão verdes.
- [X] T011 Adicionar `PASSWORD_RESET_URL_TEMPLATE: str | None = Field(default=None)` logo após `INVITE_URL_TEMPLATE` em src/pivma/core/settings.py, com comentário de uma linha (Spec 039, link da página de redefinição com `{token}`).
  - O `field_validator` existente passa a ser `@field_validator('INVITE_URL_TEMPLATE', 'PASSWORD_RESET_URL_TEMPLATE')`, recebe `info: ValidationInfo` e usa `f'{info.field_name} must contain {{token}} exactly once'`.
  - Renomeie o método para `validate_url_template`.
  - Confirme T006–T008 e os testes existentes de `INVITE_URL_TEMPLATE` verdes.

**Checkpoint**: tabela migrada e configuração validada.

---

## Phase 3: User Story 1 - Pedir a recuperação de senha (Priority: P1) 🎯 MVP

**Goal**: `POST /auth/forgot-password` emite token de 30 minutos só como hash, invalida os anteriores e registra o e-mail com o link. Sem canal ou sem modelo de link, responde neutro sem emitir nada (FR-008), para que a história possa ser implantada sozinha sem responder 500.

**Independent Test**: com `reset_settings`, pedir com o e-mail de `user` e receber 200 com a mensagem neutra. Rodar o worker e conferir um e-mail para `user.email` com link e prazo.

### Tests for User Story 1 ⚠️ (escrever primeiro e ver falhar)

- [X] T012 [P] [US1] Testar que `generate_reset_token()` devolve uma string de 43 caracteres do alfabeto URL-safe (`[A-Za-z0-9_-]`) em tests/unit/core/test_password_reset_token.py
- [X] T013 [US1] Testar que duas chamadas de `generate_reset_token()` devolvem valores diferentes em tests/unit/core/test_password_reset_token.py
- [X] T014 [US1] Testar que `hash_reset_token('abc')` é igual a `hashlib.sha256(b'abc').hexdigest()` (64 caracteres hexadecimais) em tests/unit/core/test_password_reset_token.py
- [X] T015 [P] [US1] Testar que `ForgotPasswordRequest(email='  Maria@Exemplo.org  ')` guarda `'Maria@Exemplo.org'` (aparado, caixa preservada) em tests/unit/schemas/test_user_schemas.py
- [X] T016 [US1] Testar que `ForgotPasswordRequest(email='nao-e-email')` levanta `ValidationError` em tests/unit/schemas/test_user_schemas.py
- [X] T017 [US1] Testar que `ForgotPasswordRequest(email='a@b.org', username='x')` levanta `ValidationError` (`extra='forbid'`) em tests/unit/schemas/test_user_schemas.py
- [X] T018 [P] [US1] Testar que o renderizador `password_reset_email` devolve assunto com "Redefinição de senha" e "pi*VMA" em tests/unit/notifications/test_password_reset_email_renderer.py
- [X] T019 [US1] Testar que o texto e o HTML do renderizador contêm o `reset_url` do payload em tests/unit/notifications/test_password_reset_email_renderer.py
- [X] T020 [US1] Testar que o texto e o HTML contêm o prazo formatado `'01/10/2026 15:30 (UTC)'` para `expires_at='2026-10-01T15:30:00'` em tests/unit/notifications/test_password_reset_email_renderer.py
- [X] T021 [US1] Testar que o texto e o HTML avisam para ignorar a mensagem quando a pessoa não pediu a redefinição em tests/unit/notifications/test_password_reset_email_renderer.py
- [X] T022 [US1] Testar que um `reset_url` com `"` e `<` aparece escapado no HTML (`&quot;`, `&lt;`) em tests/unit/notifications/test_password_reset_email_renderer.py
- [X] T023 [P] [US1] Criar em tests/api/routers/test_password_reset.py:
  - as constantes `NEUTRAL_MESSAGE`, `INVALID_TOKEN_DETAIL`, `RESET_URL_PREFIX` e `NEW_PASSWORD`;
  - as fixtures `reset_settings` e `operational_log` (ver Convenções);
  - os helpers `forgot(client, email)`, `reset(client, token, new_password=NEW_PASSWORD)`, `async deliver_reset_token(session, settings)` e `async reset_tokens_of(session, user)` (lista de `PasswordResetToken` da conta, ordenada por `created_at`).
- [X] T024 [US1] Testar que `POST /auth/forgot-password` com `user.email` retorna 200 com corpo exatamente `{'message': NEUTRAL_MESSAGE}` em tests/api/routers/test_password_reset.py
- [X] T025 [US1] Testar que o pedido com `user.email` grava um `PasswordResetToken` da conta com `used_at is None` e `deleted_at is None` em tests/api/routers/test_password_reset.py
- [X] T026 [US1] Testar que o token gravado tem `expires_at` entre `antes + 30 min` e `depois + 30 min`, medindo `datetime.utcnow()` antes e depois da requisição, em tests/api/routers/test_password_reset.py
- [X] T027 [US1] Testar que o `token_hash` gravado é `hash_reset_token(token)` do token entregue por e-mail e que nenhuma coluna da linha contém o token bruto (FR-004, US1-4) em tests/api/routers/test_password_reset.py
- [X] T028 [US1] Testar que o pedido grava uma `Notification` com `kind='password_reset_email'`, `recipient=user.email`, `subject_type='password_reset'`, `subject_id=user.id` e `expires_at` igual ao do token em tests/api/routers/test_password_reset.py
- [X] T029 [US1] Testar que, após `deliver_reset_token`, a mensagem enviada tem `to == user.email` e o link `RESET_URL_PREFIX + token` no texto e no HTML em tests/api/routers/test_password_reset.py
- [X] T030 [US1] Testar que o pedido com `user.email.upper()` grava um token para `user` (US1-2) em tests/api/routers/test_password_reset.py
- [X] T031 [US1] Testar que um segundo pedido marca o primeiro token com `deleted_at` preenchido e deixa só o segundo com `deleted_at is None` (FR-005) em tests/api/routers/test_password_reset.py
- [X] T032 [US1] Testar que um segundo pedido, feito antes de o worker rodar, deixa a primeira notificação `cancelled` com `error_code='cancelled_resent'` em tests/api/routers/test_password_reset.py
- [X] T033 [US1] Testar que o token emitido e a notificação têm `created_by is None`, porque o pedido é anônimo (research R10), em tests/api/routers/test_password_reset.py
- [X] T034 [US1] Testar que o pedido para `user` não grava token nem notificação para `other_user` em tests/api/routers/test_password_reset.py
- [X] T035 [US1] Testar que, sem modelo de link (`email_settings(PASSWORD_RESET_URL_TEMPLATE=None)`), o pedido com `user.email` retorna 200 com corpo `{'message': NEUTRAL_MESSAGE}` (FR-008) em tests/api/routers/test_password_reset.py
- [X] T036 [US1] Testar que, sem modelo de link, o pedido com `user.email` não grava `PasswordResetToken` nem `Notification` em tests/api/routers/test_password_reset.py
- [X] T037 [US1] Testar que, sem canal de e-mail (`email_settings(NOTIFICATION_EMAIL_BACKEND=None, PASSWORD_RESET_URL_TEMPLATE=...)`), o pedido com `user.email` retorna 200 com corpo `{'message': NEUTRAL_MESSAGE}` em tests/api/routers/test_password_reset.py
- [X] T038 [US1] Testar que, sem canal de e-mail, o pedido com `user.email` não grava `PasswordResetToken` nem `Notification` em tests/api/routers/test_password_reset.py
- [X] T039 [US1] Testar que, sem modelo de link, `operational_log` recebe uma linha JSON com `event == 'password_reset_unavailable'` e `level == 'warning'`, cujo texto não contém `user.email`, em tests/api/routers/test_password_reset.py
- [X] T040 [US1] Testar que, sem canal de e-mail, `operational_log` recebe uma linha JSON com `event == 'password_reset_unavailable'` e `level == 'warning'`, cujo texto não contém `user.email`, em tests/api/routers/test_password_reset.py

### Implementation for User Story 1

- [X] T041 [P] [US1] Adicionar `PASSWORD_RESET_EMAIL = 'password_reset_email'` e `render_password_reset_email(payload)` em src/pivma/notifications/renderers.py, após o bloco do convite, com comentário de seção `# --- Redefinição de senha (Spec 039) ---`:
  - assunto `'Redefinição de senha na pi*VMA'`;
  - texto e HTML em português com o pedido recebido, o link, `Válido até: {_format_deadline(...)}` e o aviso para ignorar se a pessoa não pediu;
  - URL escapada com `escape(url, quote=True)`;
  - registrar com `RENDERERS[PASSWORD_RESET_EMAIL] = render_password_reset_email`.
  - Confirmar T018–T022 verdes.
- [X] T042 [P] [US1] Criar `ForgotPasswordRequest` (`extra='forbid'`, `email` com `json_schema_extra={'format': 'email'}` e o mesmo `validate_email_preserving_case` de `UserCreate`) e `ForgotPasswordResponse` (`message: str`) após `LoginResponse` em src/pivma/schemas.py. Confirmar T015–T017 verdes.
- [X] T043 [US1] Criar src/pivma/core/password_reset_service.py com:
  - docstring do módulo (Spec 039; só o hash é persistido; as funções não comitam);
  - constantes `TOKEN_TTL = timedelta(minutes=30)`, `SUBJECT_TYPE = 'password_reset'` e `NEUTRAL_MESSAGE`;
  - `generate_reset_token()` (`secrets.token_urlsafe(32)`) e `hash_reset_token(token)` (SHA-256 hex), que fazem T012–T014 passar.
- [X] T044 [US1] Implementar `async def request_password_reset(session, settings, email) -> None` em src/pivma/core/password_reset_service.py, nesta ordem:
  1. Se `not (email_channel_available(settings) and settings.PASSWORD_RESET_URL_TEMPLATE)`, chamar `get_operational_logger().warning('password_reset_unavailable')` e `return`, antes de qualquer consulta (research R7). O evento não leva e-mail nem token.
  2. Buscar `User` com `func.lower(User.email) == func.lower(email)` e `deleted_at IS NULL`, usando `.with_for_update()`. Sem conta, `return`. O índice `uq_users_email_ci` garante no máximo uma conta ativa.
  3. `now = datetime.utcnow()`.
  4. Marcar com `deleted_at = now` os tokens da conta com `used_at IS NULL`, `deleted_at IS NULL` e `expires_at > now`, num único `update(...)`.
  5. Chamar `cancel_pending_notifications(session, subject=(SUBJECT_TYPE, user.id), reason='cancelled_resent', actor_id=None)`.
  6. Gerar o token e adicionar `PasswordResetToken(user_id=user.id, token_hash=..., expires_at=now + TOKEN_TTL)`, sem `set_creation_audit`.
  7. Chamar `enqueue_notification(..., kind=PASSWORD_RESET_EMAIL, channel='email', recipient=user.email, payload={'reset_url': settings.PASSWORD_RESET_URL_TEMPLATE.replace('{token}', token), 'expires_at': expires_at.isoformat()}, actor_id=None, subject=(SUBJECT_TYPE, user.id), expires_at=expires_at)`.
  - Sem commit e sem log com e-mail, token ou link.
- [X] T045 [US1] Implementar `POST /auth/forgot-password` (`forgot_password`) em src/pivma/routers/auth.py:
  - `status_code=HTTPStatus.OK`, `response_model=ForgotPasswordResponse`, `operation_id='forgotPassword'`;
  - parâmetros `payload: ForgotPasswordRequest`, `session: Session`, `settings: SettingsDependency`;
  - chamar `request_password_reset`, depois `await session.commit()`, e retornar `ForgotPasswordResponse(message=NEUTRAL_MESSAGE)`;
  - sem `CurrentUser`/`TrustedOrigin`.
  - Confirmar T024–T040 verdes.
- [X] T046 [US1] Executar `uv run pytest tests/unit/core/test_password_reset_token.py tests/unit/schemas/test_user_schemas.py tests/unit/notifications/test_password_reset_email_renderer.py tests/api/routers/test_password_reset.py -q` e conferir a saída real

**Checkpoint**: MVP. O pedido emite o token, o e-mail chega com o link, e uma implantação sem configuração responde neutro sem erro.

---

## Phase 4: User Story 2 - Não revelar quais e-mails têm conta (Priority: P1)

**Goal**: a resposta e os efeitos visíveis não distinguem conta existente, inexistente ou excluída, nem entrada inválida de válida além do 422 de formato.

**Independent Test**: comparar o corpo e o status de `forgot` com `user.email`, com um e-mail sem conta e com `deleted_user.email`.

**Ordem dos testes**: o comportamento desta história já existe depois de T042 e T044: o filtro `deleted_at IS NULL` e o retorno antecipado sem conta. Por isso estes testes não falham ao serem escritos. Eles provam a não enumeração e protegem contra regressão. Se algum falhar, corrija só o serviço ou o schema.

### Tests for User Story 2

- [X] T047 [P] [US2] Testar que o pedido com `'ninguem@exemplo.org'` retorna 200 com corpo igual ao do pedido com `user.email` (US2-1, SC-002) em tests/api/routers/test_password_reset.py
- [X] T048 [US2] Testar que o pedido com `'ninguem@exemplo.org'` não grava `PasswordResetToken` nem `Notification` em tests/api/routers/test_password_reset.py
- [X] T049 [US2] Testar que o pedido com `deleted_user.email` retorna 200 com o corpo neutro (US2-2) em tests/api/routers/test_password_reset.py
- [X] T050 [US2] Testar que o pedido com `deleted_user.email` não grava token nem notificação em tests/api/routers/test_password_reset.py
- [X] T051 [US2] Testar que o pedido com `{'email': 'nao-e-email'}` retorna 422 com `detail.code == 'validation_error'` (US2-3) em tests/api/routers/test_password_reset.py
- [X] T052 [US2] Testar que o pedido sem o campo `email` retorna 422 em tests/api/routers/test_password_reset.py
- [X] T053 [US2] Testar que o pedido com `{'email': user.email, 'username': user.username}` retorna 422 em tests/api/routers/test_password_reset.py
- [X] T054 [US2] Testar que o pedido com campo extra `username` não grava token para `user` em tests/api/routers/test_password_reset.py

### Verification for User Story 2

- [X] T055 [US2] Executar `uv run pytest tests/api/routers/test_password_reset.py -q` e conferir na saída real que T047–T054 passam sem código novo

**Checkpoint**: o pedido não permite enumerar contas.

---

## Phase 5: User Story 3 - Redefinir a senha com o token (Priority: P1)

**Goal**: `POST /auth/reset-password` troca a senha com token válido, uma única vez, e recusa todos os demais com o mesmo 400.

**Independent Test**: obter o token por `deliver_reset_token`, redefinir e receber 204. O login com a senha nova dá 200, com a antiga dá 401, e reusar o token dá 400.

### Tests for User Story 3 ⚠️ (escrever primeiro e ver falhar)

- [X] T056 [P] [US3] Testar que `ResetPasswordRequest(token='t', new_password='NovaSenha-2026')` é aceito em tests/unit/schemas/test_user_schemas.py
- [X] T057 [US3] Testar que `ResetPasswordRequest` rejeita `new_password` com 7 caracteres em tests/unit/schemas/test_user_schemas.py
- [X] T058 [US3] Testar que `ResetPasswordRequest` rejeita `new_password` com 129 caracteres em tests/unit/schemas/test_user_schemas.py
- [X] T059 [US3] Testar que `ResetPasswordRequest` rejeita `new_password` com espaço interno em tests/unit/schemas/test_user_schemas.py
- [X] T060 [US3] Testar que `ResetPasswordRequest` rejeita `token=''` em tests/unit/schemas/test_user_schemas.py
- [X] T061 [US3] Testar que `ResetPasswordRequest` rejeita `token` com 129 caracteres em tests/unit/schemas/test_user_schemas.py
- [X] T062 [US3] Testar que `ResetPasswordRequest` rejeita campo extra `email` (`extra='forbid'`) em tests/unit/schemas/test_user_schemas.py
- [X] T063 [P] [US3] Testar que `POST /auth/reset-password` com token entregue e senha válida retorna 204 sem corpo (US3-1) em tests/api/routers/test_password_reset.py
- [X] T064 [US3] Testar que, após a redefinição, `verify_password(user.password_hash, NEW_PASSWORD)` é verdadeiro após `session.refresh(user)` em tests/api/routers/test_password_reset.py
- [X] T065 [US3] Testar que, após a redefinição, o token tem `used_at` preenchido (FR-013) em tests/api/routers/test_password_reset.py
- [X] T066 [US3] Testar que, após a redefinição, o token tem `updated_by == user.id` em tests/api/routers/test_password_reset.py
- [X] T067 [US3] Testar que, após a redefinição, a conta tem `updated_by == user.id` e `updated_at` preenchido e diferente do valor anterior, que pode ser `None` (FR-015) em tests/api/routers/test_password_reset.py
- [X] T068 [US3] Testar que, após a redefinição, `POST /auth/login` com `NEW_PASSWORD` retorna 200 (US3-2, FR-016) em tests/api/routers/test_password_reset.py
- [X] T069 [US3] Testar que, após a redefinição, `POST /auth/login` com `'Factory-Passphrase-2026'` retorna 401 em tests/api/routers/test_password_reset.py
- [X] T070 [US3] Testar que reusar o mesmo token retorna 400 com `detail == INVALID_TOKEN_DETAIL` (US3-3) em tests/api/routers/test_password_reset.py
- [X] T071 [US3] Testar que o reuso do token não muda `password_hash` em relação ao gravado na primeira redefinição em tests/api/routers/test_password_reset.py
- [X] T072 [US3] Testar que um token com `expires_at` movido para `datetime.utcnow() - timedelta(seconds=1)` e commitado retorna 400 com `INVALID_TOKEN_DETAIL` (US3-4) em tests/api/routers/test_password_reset.py
- [X] T073 [US3] Testar que o token expirado não muda `password_hash` em tests/api/routers/test_password_reset.py
- [X] T074 [US3] Testar que um token nunca emitido (`'x' * 43`) retorna 400 com `INVALID_TOKEN_DETAIL` (US3-5) em tests/api/routers/test_password_reset.py
- [X] T075 [US3] Testar que o token do primeiro pedido, depois de um segundo pedido, retorna 400 com `INVALID_TOKEN_DETAIL` (US3-6) em tests/api/routers/test_password_reset.py
- [X] T076 [US3] Testar que o token do segundo pedido, depois de o primeiro ser substituído, retorna 204 em tests/api/routers/test_password_reset.py
- [X] T077 [US3] Testar que um token válido de conta excluída depois da emissão (`user.deleted_at` preenchido e commitado) retorna 400 com `INVALID_TOKEN_DETAIL` em tests/api/routers/test_password_reset.py
- [X] T078 [US3] Testar que `new_password` com espaço retorna 422 com o campo mascarado (`code='invalid'`, `message='Senha inválida.'`) e sem o valor enviado no corpo da resposta (US3-7) em tests/api/routers/test_password_reset.py
- [X] T079 [US3] Testar que, após o 422 de senha inválida, o mesmo token ainda redefine com uma senha válida e retorna 204 em tests/api/routers/test_password_reset.py
- [X] T080 [US3] Testar que o corpo sem `token` retorna 422 em tests/api/routers/test_password_reset.py
- [X] T081 [US3] Testar que o corpo com campo extra `email` retorna 422 em tests/api/routers/test_password_reset.py
- [X] T082 [US3] Testar que o corpo com campo extra `email` e um token válido não muda `password_hash` em tests/api/routers/test_password_reset.py
- [X] T083 [US3] Testar que um cliente com sessão ativa de `user` (cookie `access_token` com `create_access_token(user.id, ...)`, como em `test_user_update.py`) redefine com o token entregue e recebe 204 (spec, Edge Cases: a sessão não interfere) em tests/api/routers/test_password_reset.py
- [X] T084 [P] [US3] Testar, no padrão de `test_user_concurrency.py` (sessões independentes via `app.dependency_overrides[get_session]`, `ThreadPoolExecutor`, dados commitados e limpos ao final), que duas redefinições simultâneas com o mesmo token resultam em exatamente um 204 e um 400 (FR-014) em tests/api/routers/test_password_reset_concurrency.py
- [X] T085 [US3] Testar, no mesmo arquivo, que após as duas requisições simultâneas o token tem `used_at` preenchido e a senha da conta corresponde à da requisição que recebeu 204 em tests/api/routers/test_password_reset_concurrency.py
- [X] T086 [US3] Testar, no mesmo padrão, que dois pedidos simultâneos de recuperação para a mesma conta deixam exatamente um token com `deleted_at is None` em tests/api/routers/test_password_reset_concurrency.py

### Implementation for User Story 3

- [X] T087 [P] [US3] Criar `ResetPasswordRequest` após `ForgotPasswordResponse` em src/pivma/schemas.py:
  - `extra='forbid'`;
  - `token` com `StringConstraints(min_length=1, max_length=128)`;
  - `new_password` com `StringConstraints(min_length=8, max_length=128)` e o mesmo `reject_password_whitespace` dos outros schemas.
  - Confirmar T056–T062 verdes.
- [X] T088 [US3] Implementar `async def reset_password(session, token, new_password_hash) -> bool` em src/pivma/core/password_reset_service.py:
  1. `now = datetime.utcnow()`.
  2. Buscar `PasswordResetToken` com `token_hash == hash_reset_token(token)`, `used_at IS NULL`, `deleted_at IS NULL` e `expires_at > now`, com `join(User)` em `User.deleted_at IS NULL` e `.with_for_update(of=PasswordResetToken)`.
  3. Sem resultado, `return False`.
  4. Senão:
     - carregar a conta com `session.get(User, row.user_id)`;
     - gravar `user.password_hash = new_password_hash` e `row.used_at = now`;
     - chamar `user.set_update_audit(user.id)` e `row.set_update_audit(user.id)`;
     - `return True`.
  - Sem commit.
- [X] T089 [US3] Implementar `POST /auth/reset-password` (`reset_password_with_token`) em src/pivma/routers/auth.py:
  - `status_code=HTTPStatus.NO_CONTENT`, `operation_id='resetPassword'`;
  - `responses` com 400 ("Token inválido, expirado, usado, substituído ou de conta inativa.") e 422;
  - parâmetros `payload: ResetPasswordRequest` e `session: Session`;
  - `new_hash = await run_in_threadpool(hash_password, payload.new_password)` (plan, "Hash antes da validação do token");
  - se `not await reset_password(session, payload.token, new_hash)`: `raise api_error(HTTPStatus.BAD_REQUEST, 'invalid_reset_token', 'Link de redefinição inválido ou expirado.')`;
  - senão, `await session.commit()`.
  - Sem `CurrentUser`/`TrustedOrigin`.
  - Confirmar T063–T086 verdes.

**Checkpoint**: fluxo completo de recuperação funcional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: segredo fora dos logs, escopo da alteração, contratos preservados, documentação e verificação final.

- [X] T090 [P] Testar, com `caplog.set_level(logging.DEBUG)` e a fixture `operational_log`, que o fluxo completo (pedido, `deliver_reset_token`, redefinição) não registra o token bruto em `caplog.text` nem em `operational_log.getvalue()` (FR-004, SC-006) em tests/api/routers/test_password_reset.py
- [X] T091 Testar, no mesmo cenário, que o link completo (`RESET_URL_PREFIX + token`) não aparece em `caplog.text` nem em `operational_log.getvalue()` em tests/api/routers/test_password_reset.py
- [X] T092 Testar, no mesmo cenário, que `NEW_PASSWORD` não aparece em `caplog.text` nem em `operational_log.getvalue()` em tests/api/routers/test_password_reset.py
- [X] T093 Testar que a redefinição deixa todas as colunas de `user` iguais, exceto `password_hash`, `updated_at` e `updated_by`, comparando `{c.key: getattr(user, c.key) for c in User.__table__.columns}` antes e depois. Isso cobre `username`, `email`, `full_name` e `deleted_at` (FR-017), em tests/api/routers/test_password_reset.py
- [X] T094 Testar que a redefinição não altera a linha de `UserAccessProfile` da conta, criada com `UserAccessProfileFactory` (mesmos `id`, `updated_at` e `deleted_at`). Cobre os perfis e permissões de FR-017, em tests/api/routers/test_password_reset.py
- [X] T095 Testar que a redefinição não altera a linha de `UserInstitutionalAffiliation` da conta, criada com `UserInstitutionalAffiliationFactory` (mesmos `id`, `updated_at` e `deleted_at`). Cobre os vínculos de FR-017, em tests/api/routers/test_password_reset.py
- [X] T096 Testar que o pedido de recuperação deixa todas as colunas de `user` iguais, com a mesma comparação de T093 sem exceções (FR-017), em tests/api/routers/test_password_reset.py
- [X] T097 Testar que a redefinição de `user` não altera `password_hash` de `other_user` em tests/api/routers/test_password_reset.py
- [X] T098 Testar que `client.get('/openapi.json')` expõe `POST /auth/forgot-password` com `operationId='forgotPassword'`, `POST /auth/reset-password` com `operationId='resetPassword'` e o 400 documentado em `resetPassword`, em tests/api/routers/test_password_reset.py
- [X] T099 [P] Atualizar README.md:
  - **Usuários e Autenticação**, novo item "Recuperação de senha":
    - as duas rotas e a mensagem neutra;
    - token de 30 minutos, de uso único;
    - um novo pedido invalida o anterior e cancela o e-mail pendente;
    - `400 invalid_reset_token` único; 204; 422 sem a regra da senha;
    - sem canal ou modelo, nada é emitido;
    - o token nunca vai para log; em desenvolvimento, o link é lido no Mailpit;
    - limites conhecidos: sessões abertas não são revogadas, não há limite de tentativas nem limpeza de tokens antigos.
  - **Tabela de variáveis**: `PASSWORD_RESET_URL_TEMPLATE`, com o exemplo `https://pivma.exemplo/redefinir-senha/{token}`.
  - **Notificações**: a linha de abertura passa a citar a recuperação de senha como segundo uso.
- [X] T100 [P] Adicionar `# PASSWORD_RESET_URL_TEMPLATE="http://localhost:3000/redefinir-senha/{token}"` logo após `INVITE_URL_TEMPLATE` em .env.example
- [X] T101 Executar `uv run pytest -q` (suíte completa) e conferir a saída real: nenhum teste existente com asserção alterada (SC-007)
- [X] T102 Executar `uv run ruff check src tests` e `uv run ruff format --check src tests` e corrigir o que for apontado nos arquivos desta feature
- [X] T103 Executar os passos de specs/039-password-reset/quickstart.md que dependem do compose (Mailpit), se o ambiente estiver disponível. Caso contrário, registrar no relatório final que a validação manual não foi executada.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende de T001, que fixa a head usada como `PREVIOUS`; bloqueia todas as histórias. T009 → T010 (a migração usa o modelo); T011 é independente.
- **US1 (Phase 3)**: depende da Phase 2.
- **US2 (Phase 4)**: depende de T042, T044 e T045, porque testa a mesma rota.
- **US3 (Phase 5)**: depende da Phase 2 e dos helpers T023 e da rota T045, porque os testes obtêm o token pelo pedido real.
- **Polish (Phase 6)**: depende das três histórias.

### Within Each Story

- Os testes vêm antes e devem falhar, salvo na US2 (ver a fase).
- Schema, renderizador e helpers do token vêm antes do serviço; o serviço vem antes da rota.
- A tarefa de implementação só termina com os testes da história verdes e a saída conferida.

### Parallel Opportunities

- Phase 2: T002 (migração) ∥ T006 (settings); T009 ∥ T011.
- US1: T012 ∥ T015 ∥ T018 ∥ T023 (arquivos distintos); T041 ∥ T042.
- US3: T056 ∥ T063 ∥ T084; T087 pode começar junto com os testes de API.
- Polish: T099 ∥ T100.
- Testes no mesmo arquivo (`test_password_reset.py`) não levam [P] entre si.

## Parallel Example: User Story 1

```bash
Task: "T012 Testar generate_reset_token em tests/unit/core/test_password_reset_token.py"
Task: "T015 Testar ForgotPasswordRequest em tests/unit/schemas/test_user_schemas.py"
Task: "T018 Testar assunto do renderizador em tests/unit/notifications/test_password_reset_email_renderer.py"
Task: "T023 Helpers e fixtures em tests/api/routers/test_password_reset.py"
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 e Phase 2.
2. Phase 3 (US1): o pedido emite o token, o e-mail chega e a implantação sem configuração responde neutro.
3. Validar com T046 antes de seguir.

### Incremental Delivery

1. US1: pedido, e-mail e ramo sem configuração.
2. US2: prova de não enumeração.
3. US3: redefinição, uso único e concorrência.
4. Polish: logs, escopo, contratos, README e suíte completa.

Todas as histórias são P1. A entrega só vai para PR com as três concluídas, porque um pedido sem redefinição deixaria a funcionalidade pela metade.

## Phase 7: Convergence

- [X] T104 Testar que o token substituído por um pedido mais recente não muda `password_hash` (capturar antes, `session.refresh(user)` depois) em tests/api/routers/test_password_reset.py per SC-003 (partial)
- [X] T105 Testar que o 422 de `new_password` com espaço não muda `password_hash` em tests/api/routers/test_password_reset.py per US3/AC7 (partial)
- [X] T106 Testar que o token de conta excluída depois da emissão não muda `password_hash` em tests/api/routers/test_password_reset.py per FR-011 (partial)

## Phase 8: Convergence

- [X] T107 Testar que o corpo sem `new_password` retorna 422 em tests/api/routers/test_password_reset.py per FR-009 (partial)
