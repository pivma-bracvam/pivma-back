# Tasks: Base de notificações e envio do convite por e-mail

**Input**: Design documents from `specs/036-notification-email-invite/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: obrigatórios (`AGENTS.md`), planejados com `fastapi-testing-methodology`. Risco **alto**: transação + envio externo + dado sensível (token). Camadas: unidade, integração com banco e API. Cada tarefa de teste cobre um comportamento observável e vem antes da implementação correspondente.

**Organization**: a base de notificações (Phase 2) é pré-requisito do convite por e-mail. Os testes da base cobrem os cenários 1, 2 e 4 da US3 e ficam na Phase 2, antes da implementação. A Phase 5 (US3) fecha o provedor real (SMTP × Mailpit).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: história da spec (US1, US2, US3)

---

## Phase 1: Setup

- [X] T001 Adicionar a dependência `cryptography` em `pyproject.toml` (grupo principal) e atualizar `poetry.lock` com `poetry lock`
- [X] T002 [P] Adicionar ao `Settings` em `src/pivma/core/settings.py` as variáveis da tabela "Configuração nova" de `data-model.md`, com os padrões indicados: `NOTIFICATION_EMAIL_BACKEND: Literal['smtp', 'fake'] | None = None`, `SMTP_HOST: str | None = None`, `SMTP_PORT: int = 587`, `SMTP_USERNAME`/`SMTP_PASSWORD: str | None = None`, `SMTP_SECURITY: Literal['starttls', 'ssl', 'none'] = 'starttls'`, `SMTP_TIMEOUT_SECONDS: int = 15`, `NOTIFICATION_FROM_ADDRESS: str | None = None`, `NOTIFICATION_FROM_NAME: str = 'pi*VMA'`, `NOTIFICATION_ENCRYPTION_KEY: str | None = None`, `NOTIFICATION_MAX_ATTEMPTS: int = 5`, `NOTIFICATION_RETRY_BASE_SECONDS: int = 30`, `NOTIFICATION_RETRY_MAX_SECONDS: int = 900`, `NOTIFICATION_POLL_SECONDS: int = 5`, `INVITE_URL_TEMPLATE: str | None = None`; validador: `INVITE_URL_TEMPLATE`, quando definido, contém `{token}` exatamente uma vez
- [X] T003 [P] Documentar as variáveis novas em `.env.example`, comentadas, com exemplo de Mailpit (`SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_SECURITY=none`)
- [X] T004 [P] Adicionar ao `compose.yaml` o serviço `worker` (mesma imagem `pivma_api`, `command: python -m pivma.notifications.worker`, sem rodar migrações, `env_file: .env`, mesmo `DATABASE_URL` da `api`, `depends_on: db`) e o serviço `mailpit` (`axllent/mailpit`, portas `127.0.0.1:8025:8025` e `127.0.0.1:1025:1025`)

---

## Phase 2: Foundational (base de notificações)

**Purpose**: tabela, cifragem, canais, serviço e processo de envio. Bloqueia US1 e US2.

### Testes da base (escrever antes da implementação; devem falhar)

- [X] T005 [P] Teste de unidade em `tests/unit/core/test_settings.py`: `INVITE_URL_TEMPLATE` sem `{token}` ou com `{token}` duas vezes é recusado; com `{token}` uma vez é aceito; ausente é aceito
- [X] T006 [P] Teste de unidade em `tests/unit/notifications/test_notification_crypto.py`: cifrar e decifrar devolve o mesmo dicionário; o texto cifrado não contém o valor original; chave diferente levanta erro de decifragem
- [X] T007 [P] Teste de unidade em `tests/unit/notifications/test_notification_backoff.py`: intervalo da tentativa `n` é `min(BASE * 2^(n-1), MAX)` (casos n=1, n=3 e n alto que atinge o máximo)
- [X] T008 [P] Teste de unidade em `tests/unit/notifications/test_smtp_error_classification.py`: resposta SMTP 5xx, destinatário recusado e remetente recusado viram `PermanentDeliveryError`; resposta 4xx, falha de conexão, timeout e falha de autenticação viram `TemporaryDeliveryError` (um caso por tipo, com `smtplib` simulado)
- [X] T009 [P] Teste de integração em `tests/integration/notifications/test_notification_enqueue.py`: `enqueue_notification` seguido de rollback não deixa linha em `notifications` (FR-002)
- [X] T010 [P] Teste de integração em `tests/integration/notifications/test_notification_enqueue.py`: `enqueue_notification` seguido de commit grava `status = 'pending'`, `attempts = 0`, `next_attempt_at` preenchido e `payload_encrypted` sem o texto do conteúdo
- [X] T011 [P] Teste de integração em `tests/integration/notifications/test_notification_enqueue.py`: `enqueue_notification` com `kind` sem renderizador registrado levanta erro e não grava nada
- [X] T012 [P] Teste de integração em `tests/integration/notifications/test_notification_enqueue.py`: `enqueue_notification` com canal não configurado levanta `ChannelUnavailableError`
- [X] T013 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: `process_next` com `FakeEmailChannel` envia a mensagem renderizada, marca `sent`, preenche `sent_at`/`finished_at`, apaga `payload_encrypted` e devolve `True`; sem pendentes devolve `False`
- [X] T014 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: erro temporário incrementa `attempts`, mantém `pending`, adia `next_attempt_at` pelo intervalo de T007 e grava `error_code = 'smtp_temporary'` ou `'connection'`; envio com `next_attempt_at` no futuro não é processado
- [X] T015 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: erro temporário na tentativa `NOTIFICATION_MAX_ATTEMPTS` marca `failed` com `error_code = 'max_attempts'` e apaga o conteúdo
- [X] T016 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: erro permanente marca `failed` com `error_code = 'smtp_permanent'` na primeira tentativa
- [X] T017 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: envio com `expires_at` vencido vira `failed` com `error_code = 'expired'` sem chamar o canal
- [X] T018 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: conteúdo que não decifra (chave trocada) vira `failed` com `error_code = 'decrypt'` sem chamar o canal
- [X] T019 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: duas sessões chamando `process_next` ao mesmo tempo sobre um único envio pendente resultam em exatamente um envio pelo canal (SC-004)
- [X] T020 [P] Teste de integração em `tests/integration/notifications/test_notification_worker.py`: `error_detail` e os logs capturados (`caplog`/structlog) não contêm o conteúdo do envio em sucesso, erro temporário e erro permanente (FR-010)
- [X] T021 [P] Teste de integração em `tests/integration/notifications/test_notification_cancel.py`: `cancel_pending_notifications` marca só os envios `pending` do `subject` como `cancelled`, grava `error_code` com o motivo, apaga o conteúdo e não altera envios de outro `subject` nem envios já finais
- [X] T022 [P] Teste de integração em `tests/integration/notifications/test_notification_audit.py`: envio com `process_instance_id` grava `NOTIFICATION_SENT`, `NOTIFICATION_FAILED` e `NOTIFICATION_CANCELLED` com o contexto de `data-model.md` e sem destinatário nem conteúdo; envio sem `process_instance_id` não grava evento

### Implementação da base

- [X] T023 Criar o modelo `Notification` em `src/pivma/core/database/models.py` conforme `data-model.md`: `kind String(64)`, `channel String(16)`, `recipient String(320)`, `subject_type String(32)` nulo, `subject_id` UUID nulo, `process_instance_id` FK `process_instances.id` nulo, `payload_encrypted Text` nulo, `status String(16)` (`pending`, `sent`, `failed`, `cancelled`), `attempts Integer` padrão 0, `next_attempt_at`, `expires_at`/`last_attempt_at`/`sent_at`/`finished_at` nulos, `error_code String(32)` nulo, `error_detail String(500)` nulo; índices `ix_notifications_pending_due` em `(next_attempt_at)` com `WHERE status = 'pending' AND deleted_at IS NULL` e `ix_notifications_subject` em `(subject_type, subject_id)`
- [X] T024 Criar a migração Alembic da tabela `notifications` em `migrations/versions/<rev>_notifications.py`, encadeada na revisão atual (`alembic heads`)
- [X] T025 [P] Implementar `encrypt_payload`/`decrypt_payload` com Fernet em `src/pivma/notifications/crypto.py` (R3)
- [X] T026 [P] Implementar `OutgoingEmail`, `EmailChannel`, `PermanentDeliveryError`, `TemporaryDeliveryError`, `SmtpEmailChannel` (`smtplib` em `asyncio.to_thread`, `starttls`/`ssl`/`none`, timeout, classificação de R5) e `FakeEmailChannel` (lista `sent`, falhas programáveis) em `src/pivma/notifications/channels.py`, com `get_email_channel(settings)` que devolve `None` quando o canal não está disponível (R8)
- [X] T027 [P] Implementar o registro de renderizadores por `kind` em `src/pivma/notifications/renderers.py` (sem nenhum `kind` ainda; o de convite entra na US1)
- [X] T028 Implementar `enqueue_notification`, `cancel_pending_notifications`, `ChannelUnavailableError`, `retry_delay(attempt, settings)` e `latest_by_subject(session, subject_type, ids)` em `src/pivma/notifications/service.py`, conforme `contracts/notifications-module.md` (sem commit; auditoria de cancelamento de R11)
- [X] T029 Implementar `process_next` e o laço `main()` com `if __name__ == '__main__'` em `src/pivma/notifications/worker.py` (`FOR UPDATE SKIP LOCKED`, prazo, decifragem, envio, estados e auditoria de R11; laço tolera banco indisponível na partida e loga sem conteúdo)
- [X] T030 Criar `src/pivma/notifications/__init__.py` exportando a interface pública e as fixtures de teste `fake_email_channel` e `notification_settings` em `tests/conftest.py` (ou `tests/integration/notifications/conftest.py`)

**Checkpoint**: T005–T022 passam. A base funciona sem nenhum tipo de aviso de negócio.

---

## Phase 3: User Story 1 — Convite chega por e-mail sem cópia manual (P1) 🎯 MVP

**Goal**: criar ou reenviar convite com canal `email` registra um envio com o link, que o processo de envio entrega.

**Independent Test**: criar convite `email` via API, rodar `process_next` com `FakeEmailChannel` e conferir destinatário, link (`INVITE_URL_TEMPLATE` com o token devolvido), processo, papel e prazo.

### Testes da US1

- [X] T031 [P] [US1] Teste de unidade em `tests/unit/notifications/test_invite_email_renderer.py`: o renderizador `invite_email` produz assunto, texto e HTML com código e título do processo, papel, laboratório (quando houver), prazo e link; valores com `<script>` saem escapados no HTML
- [X] T032 [P] [US1] Teste de API em `tests/api/routers/test_invites_router.py`: `POST /processes/{id}/participants/invites` com `channel: "email"` responde `201`, traz `token` e `delivery.status = "pending"`, `delivery.attempts = 0`
- [X] T033 [P] [US1] Teste de integração em `tests/integration/notifications/test_invite_email_flow.py`: depois da criação, `process_next` envia para o e-mail do convite uma mensagem cujo link é `INVITE_URL_TEMPLATE` com o token da resposta, e `GET /invites/{token}` desse link responde `200`
- [X] T034 [P] [US1] Teste de API em `tests/api/routers/test_invites_router.py`: reenvio de convite `email` cancela o envio anterior (`error_code = 'cancelled_resent'`), registra um novo `pending`, e o novo envio leva o novo token; o token antigo responde `404` em `GET /invites/{token}`
- [X] T035 [P] [US1] Teste de API em `tests/api/routers/test_invites_router.py`: convite com `channel: "link"` (e sem `channel`) não registra envio e responde `delivery: null`, na criação, no reenvio e na listagem (SC-007)
- [X] T036 [P] [US1] Teste de API em `tests/api/routers/test_invites_router.py`: `channel: "email"` sem canal configurado responde `409` com `code = "channel_unavailable"` e não cria convite; idem com canal configurado e `INVITE_URL_TEMPLATE` ausente (FR-019)
- [X] T037 [P] [US1] Teste de API em `tests/api/routers/test_invites_router.py`: reenvio de convite `email` quando o canal deixou de estar configurado responde `409 channel_unavailable` e mantém token e prazo do convite
- [X] T038 [P] [US1] Teste de API em `tests/api/routers/test_invites_router.py`: quem não pode gerir o papel continua recebendo `403` ao criar convite `email` (autorização da Spec 028 inalterada)

### Implementação da US1

- [X] T039 [US1] Registrar o renderizador `invite_email` em `src/pivma/notifications/renderers.py` (português, texto simples e HTML com `html.escape`, R12)
- [X] T040 [US1] Em `src/pivma/schemas.py`: `InviteChannel = Literal['link', 'email']`; novo `InviteDeliveryPublic` (`status: Literal['pending', 'sent', 'failed', 'cancelled']`, `attempts: int`, `last_attempt_at`, `sent_at`, `error_code`); `InvitePublic.delivery: InviteDeliveryPublic | None`
- [X] T041 [US1] Em `src/pivma/core/invite_service.py`: `create_invite` e `resend_invite` recebem `settings` e, para `channel == 'email'`, verificam canal e `INVITE_URL_TEMPLATE` (senão `ChannelUnavailableError`), cancelam envios pendentes do convite no reenvio (`cancelled_resent`) e chamam `enqueue_notification` com `kind='invite_email'`, `subject=('role_assignment_invite', invite.id)`, `process_instance_id`, `expires_at = invite.expires_at` e o conteúdo cifrado de `data-model.md`
- [X] T042 [US1] Em `src/pivma/core/invite_service.py`: `invite_public_kwargs` e `invite_publics` preenchem `delivery` com `latest_by_subject` (uma consulta por página na listagem); `null` para canal `link`
- [X] T043 [US1] Em `src/pivma/routers/process_participants.py`: passar `settings` para criação e reenvio e converter `ChannelUnavailableError` em `409` com `code = "channel_unavailable"` pelo helper de erro da Spec 034

**Checkpoint**: US1 funciona ponta a ponta com o canal falso.

---

## Phase 4: User Story 2 — Falha de envio não trava o convite e fica visível (P1)

**Goal**: o convite nunca depende do envio; a situação do envio aparece na listagem; envios de convite revogado, aceito ou expirado não saem.

**Independent Test**: com `FakeEmailChannel` programado para falhar, criar convite `email`, rodar `process_next` várias vezes e conferir criação `201`, `attempts` subindo e `failed` ao fim na listagem.

### Testes da US2

- [X] T044 [P] [US2] Teste de integração em `tests/integration/notifications/test_invite_email_flow.py`: com o canal falhando de forma temporária, a criação responde `201` com token válido; após `NOTIFICATION_MAX_ATTEMPTS` chamadas a `process_next` (relógio avançado), a listagem mostra `delivery.status = "failed"`, `error_code = "max_attempts"`
- [X] T045 [P] [US2] Teste de integração em `tests/integration/notifications/test_invite_email_flow.py`: falha temporária seguida de sucesso antes do limite termina `sent` e a listagem mostra `sent_at`
- [X] T046 [P] [US2] Teste de API em `tests/api/routers/test_invites_router.py`: revogar convite `email` com envio pendente responde com `delivery.status = "cancelled"`; `process_next` em seguida não chama o canal
- [X] T047 [P] [US2] Teste de API em `tests/api/routers/test_invite_acceptance.py`: aceitar convite `email` com envio pendente cancela o envio (`error_code = 'cancelled_accepted'`)
- [X] T048 [P] [US2] Teste de integração em `tests/integration/notifications/test_invite_email_flow.py`: convite `email` cujo prazo venceu antes do envio termina `failed` com `error_code = "expired"`, sem chamar o canal
- [X] T049 [P] [US2] Teste de integração em `tests/integration/notifications/test_invite_email_flow.py`: depois de `sent`, `failed` e `cancelled`, a linha em `notifications` tem `payload_encrypted` nulo e nenhum campo do banco contém o token bruto (SC-005)
- [X] T050 [P] [US2] Teste de API em `tests/api/routers/test_invites_router.py`: a listagem só mostra `delivery` de convites que o usuário já pode ver (filtro por cargo da Spec 028 inalterado)

### Implementação da US2

- [X] T051 [US2] Em `src/pivma/core/invite_service.py`: `revoke_invite` chama `cancel_pending_notifications` com `cancelled_revoked`; `accept_invite` chama com `cancelled_accepted`

**Checkpoint**: US1 e US2 passam juntas; testes da Spec 028 continuam passando sem alteração.

---

## Phase 5: User Story 3 — Base reutilizável e provedor trocável (P2)

**Goal**: provar o envio real por SMTP e a troca de provedor só por configuração. Os cenários de transação e canal falso já foram cobertos em T009–T013.

**Independent Test**: com `NOTIFICATION_EMAIL_BACKEND=smtp` apontando para um Mailpit em contêiner, `process_next` entrega a mensagem e ela aparece na API HTTP do Mailpit.

### Testes da US3

- [ ] T052 [P] [US3] Teste de integração em `tests/integration/notifications/test_smtp_channel_mailpit.py`: `SmtpEmailChannel` com `SMTP_SECURITY=none` envia para um contêiner `axllent/mailpit` (`testcontainers` `DockerContainer`); a API HTTP do Mailpit mostra destinatário, remetente (`NOTIFICATION_FROM_NAME <NOTIFICATION_FROM_ADDRESS>`), assunto, texto e HTML
- [ ] T053 [P] [US3] Teste de integração em `tests/integration/notifications/test_smtp_channel_mailpit.py`: `SmtpEmailChannel` apontando para porta sem servidor levanta `TemporaryDeliveryError`
- [ ] T054 [P] [US3] Teste de unidade em `tests/unit/notifications/test_email_channel_selection.py`: `get_email_channel` devolve `SmtpEmailChannel` com `smtp`, `FakeEmailChannel` com `fake` e `None` sem backend, sem remetente, sem chave ou com `smtp` sem `SMTP_HOST`

### Implementação da US3

- [ ] T055 [US3] Ajustar o que T052–T054 apontarem em `src/pivma/notifications/channels.py` (cabeçalhos `From`, `To`, `Subject`, `Date`, `Message-ID`; corpo `multipart/alternative`)

---

## Phase 6: Polish & Cross-Cutting

- [ ] T056 [P] Atualizar `README.md`: seção de notificações (como pedir um envio, serviço `worker`, Mailpit, variáveis novas, geração da chave Fernet, efeito de trocar a chave com envios pendentes, limite de duplicidade em queda do processo) e contrato de `delivery` nos convites
- [ ] T057 [P] Atualizar `docs/` se a documentação de implantação citar os serviços do `compose.yaml`
- [ ] T058 Rodar `poetry run ruff check`, `poetry run ruff format --check` e a suíte completa (`poetry run pytest`), incluindo os testes da Spec 028 sem alteração
- [ ] T059 Executar o `quickstart.md` com `docker compose` (cenários 1 a 6) e registrar o resultado no PR

---

## Dependencies & Execution Order

- **Phase 1** → **Phase 2** → **Phase 3 (US1)** → **Phase 4 (US2)** → **Phase 6**.
- **Phase 5 (US3)** depende só da Phase 2 e pode correr em paralelo com US1/US2.
- Dentro de cada fase: testes primeiro (falhando), depois implementação.
- T023 → T024 (migração do modelo). T025–T027 em paralelo. T028 depende de T023 e T025. T029 depende de T026 e T028.
- T041 depende de T039 e T040. T042 depende de T028. T043 depende de T041.
- T051 depende de T028.

## Parallel Example: Phase 2 (testes)

```text
T005, T006, T007, T008  (unidade, arquivos diferentes)
T009–T012               (test_notification_enqueue.py, um arquivo; escrever juntos)
T013–T020               (test_notification_worker.py)
T021, T022              (cancel e audit, arquivos próprios)
```

## Parallel Example: US1 (testes)

```text
T031 (renderizador)  |  T032, T034–T038 (test_invites_router.py)  |  T033 (fluxo de integração)
```

## Implementation Strategy

1. **MVP**: Phases 1, 2 e 3. O convite sai por e-mail com o canal falso nos testes e com Mailpit em desenvolvimento.
2. **Robustez**: Phase 4 (falha visível, cancelamento, prazo, nada legível no banco).
3. **Provedor real**: Phase 5 (SMTP contra Mailpit em contêiner).
4. **Entrega**: Phase 6 (README, lint, suíte completa, quickstart).
