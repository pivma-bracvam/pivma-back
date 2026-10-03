# Implementation Plan: Recuperação de Senha por Token Temporário

**Branch**: `feat/auth-credentials-management` (issues #43, #44 e #45) | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

A feature adiciona duas rotas públicas ao router `auth`:

- `POST /auth/forgot-password` sempre responde a mesma mensagem neutra. Quando há conta ativa e canal de e-mail configurado, emite um token de 30 minutos, invalida os anteriores e registra o envio do link pela base de notificações da Spec 036.
- `POST /auth/reset-password` troca a senha com um token válido e o marca como usado. Para qualquer token recusado, responde 400 com o mesmo código.

Entram:

- uma tabela `password_reset_tokens` com migração;
- um módulo de serviço com duas funções;
- um renderizador de e-mail;
- uma variável de configuração;
- três schemas.

Não entra nenhuma dependência, classe nem camada nova. A base de notificações, a política de senha, o formato de erro e o hash Argon2 são reaproveitados sem alteração.

## Evidence Classification

- **CONFIRMADO** (commit `c25f31a`): não existe fluxo de recuperação. Os itens abaixo já existem:
  - `enqueue_notification`, `cancel_pending_notifications` e `email_channel_available` (Spec 036);
  - o padrão de token do convite (`secrets.token_urlsafe(32)` + SHA-256, Spec 028);
  - `hash_password` (Argon2id), `api_error` e `field_errors`, que mascara campos `*password` e nunca ecoa a entrada (Spec 034).
- **CONFIRMADO**: nesta branch, a head do Alembic é `6eb1ae208b7d` (notificações). Em `origin/develop`, a head é `5af69c71be3c` (merge de notificações e execução por laboratório). A revisão nova aponta para a head única da branch de destino no momento da implementação.
- **CONFIRMADO**: em desenvolvimento, os e-mails caem no Mailpit do compose; nos testes, no `FakeEmailChannel`.
- **DECISÃO DA SPEC**: validade de 30 minutos, só e-mail, 204 na redefinição, um novo pedido invalida os anteriores, sem canal não emite token.
- **DECISÃO CONFIRMADA PELO USUÁRIO (2026-10-02)**: o token nunca vai para log, em nenhum ambiente. Isso diverge da issue #45, que o admitia em desenvolvimento. A divergência está registrada em `docs/observacoes-e-pendencias.md` e será citada na descrição da PR.
- **INFERÊNCIA**: a recuperação de acesso faz parte do RF001 (cadastro e autenticação).
- **FORA DE ESCOPO**: rate limit, revogação de sessões, limpeza de tokens antigos, igualar o tempo de resposta.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**:
- FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono e Alembic.
- Do projeto: `pivma.core.security` (Argon2id) e `pivma.notifications` (Spec 036).
- Nenhuma dependência nova.

**Storage**: PostgreSQL. Uma tabela nova, `password_reset_tokens`; as tabelas `users` e `notifications` ficam sem mudança de schema.

**Testing**: Pytest com `TestClient`, sessão assíncrona, Testcontainers, Factory Boy, `FakeEmailChannel` e `process_next` do worker.

**Target Platform**: API web (Linux/Docker) mais o worker de notificações.

**Project Type**: backend monolítico (web-service).

**Performance Goals**:
- Pedido: no máximo uma consulta com bloqueio da conta, um `UPDATE` de invalidação, um cancelamento de envios e dois `INSERT`, em um commit.
- Redefinição: uma consulta com bloqueio do token, um hash Argon2 em threadpool e um commit.

**Constraints**:
- O token bruto nunca é persistido, registrado em log nem devolvido em resposta.
- A resposta do pedido é idêntica com ou sem conta.
- O 400 é único para todos os motivos.
- Atomicidade: o token e o envio são gravados juntos; a senha e o `used_at`, também.
- Uso único sob concorrência.
- Os contratos existentes ficam inalterados.

**Scale/Scope**: duas rotas, uma tabela, um módulo de serviço, um renderizador, uma variável de ambiente, testes focados e README.

## Constitution Check

*GATE: avaliado antes da pesquisa e reavaliado após o desenho.*

- **I. Requisitos e evidência**: PASS. As afirmações estão classificadas. A divergência com a issue sobre logs está registrada na spec (Clarifications, FR-004 e Assumptions) e foi confirmada pelo usuário.
- **II. Rastreabilidade e auditoria**: PASS.
  - O token usa `AuditMixin`.
  - A redefinição grava `updated_by = user.id` na conta e no token.
  - O pedido anônimo não é atribuído a ninguém (research R10).
  - A notificação segue a trilha da Spec 036.
- **III. Segurança**: PASS.
  - Token de 256 bits; só o hash é persistido.
  - Resposta neutra; 400 único.
  - Bloqueio de linha contra uso duplo.
  - A regra e o valor da senha não aparecem no 422.
  - O link vai cifrado no envio e é apagado ao terminar.
  - O token trafega no corpo, não na URL.
  - Sem sessão envolvida, então sem CSRF a mitigar.
- **IV. IA**: PASS. Não se aplica.
- **V. Mudanças pequenas e verificáveis**: PASS.
  - Escopo restrito à issue.
  - Sem refatorar o convite: a geração do token se repete em duas linhas, em vez de virar um utilitário compartilhado (research R1).
  - O único ajuste em código existente é o validador de `{token}` em `settings.py`, que passa a cobrir também a variável nova.
  - Cada comportamento tem teste.

**Reavaliação pós-desenho**: PASS em todos os princípios. O desenho só acrescentou o que a issue pede (tabela, rotas, envio, testes), mais a variável do link exigida pela Spec 036.

## Project Structure

### Documentation (this feature)

```text
specs/039-password-reset/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/password-reset.openapi.yaml
├── checklists/requirements.md
└── tasks.md              # gerado por /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── core/database/models.py            # PasswordResetToken
├── core/password_reset_service.py     # novo: request_password_reset, reset_password
├── core/settings.py                   # PASSWORD_RESET_URL_TEMPLATE + validador
├── notifications/renderers.py         # PASSWORD_RESET_EMAIL + render_password_reset_email
├── routers/auth.py                    # POST /auth/forgot-password e /auth/reset-password
└── schemas.py                         # ForgotPasswordRequest/Response, ResetPasswordRequest
migrations/versions/<rev>_password_reset_tokens.py
tests/
├── api/routers/test_password_reset.py                         # comportamento HTTP de ponta a ponta
├── api/routers/test_password_reset_concurrency.py             # uso único e pedidos simultâneos
├── unit/core/test_password_reset_token.py                     # geração e hash do token
├── unit/schemas/test_user_schemas.py                          # regras dos dois schemas
├── unit/notifications/test_password_reset_email_renderer.py   # conteúdo e escape do e-mail
├── unit/core/test_settings.py                                 # validação do modelo de link
└── integration/migrations/test_password_reset_migration.py    # upgrade/downgrade
README.md        # Usuários e Autenticação, tabela de variáveis, Notificações
.env.example     # PASSWORD_RESET_URL_TEMPLATE comentada
```

**Structure Decision**: segue a organização atual. O modelo fica em `models.py`, a regra em `core/*_service.py` (como `invite_service`), as rotas de autenticação em `routers/auth.py` e o renderizador junto do convite.

## Implementation Sequence

1. **Modelo e migração** (teste de migração primeiro): `PasswordResetToken` conforme [data-model.md](data-model.md). A revisão nova tem como `down_revision` a head única da branch de destino (`uv run alembic heads` devolve uma só linha). O teste confere a tabela e os índices após o `upgrade` e a remoção após o `downgrade`.
2. **Configuração**: `PASSWORD_RESET_URL_TEMPLATE: str | None` em `Settings`, logo após `INVITE_URL_TEMPLATE`. O `field_validator` existente passa a receber os dois nomes, e a mensagem de erro usa `info.field_name`. Os testes de validação entram em `test_settings.py`.
3. **Renderizador**: `PASSWORD_RESET_EMAIL = 'password_reset_email'` e `render_password_reset_email(payload)`, no estilo de `render_invite_email`. Reaproveita `_format_deadline` e escapa a URL no HTML. Os testes unitários escritos antes conferem o assunto, o link nos dois formatos, o prazo e o escape.
4. **Schemas** em `schemas.py`, testes unitários primeiro:
   - `ForgotPasswordRequest`: `email` aparado e validado como em `UserCreate`, `extra='forbid'`.
   - `ForgotPasswordResponse`: `message`.
   - `ResetPasswordRequest`: `token` de 1 a 128 caracteres, `new_password` com a política e o validador de espaço, `extra='forbid'`.
5. **Serviço** `core/password_reset_service.py`, sem commit:
   - Constantes `TOKEN_TTL = timedelta(minutes=30)`, `SUBJECT_TYPE = 'password_reset'` e a mensagem neutra.
   - `request_password_reset(session, settings, email) -> None`:
     1. Sem canal ou sem modelo: `get_operational_logger().warning('password_reset_unavailable')` e retorno.
     2. Busca a conta ativa por `lower(email)` com `with_for_update()`. Sem conta, retorna.
     3. Invalida os tokens válidos da conta (`deleted_at = now`).
     4. Cancela os envios pendentes de `('password_reset', user.id)`.
     5. Gera o token e grava o hash com `expires_at = now + TOKEN_TTL`.
     6. Registra o envio com `enqueue_notification` (payload `{reset_url, expires_at}`, `actor_id=None`, `subject`, `expires_at`).
   - `reset_password(session, token, new_password_hash) -> bool`:
     1. Busca o token pelo hash com `used_at IS NULL`, `deleted_at IS NULL`, `expires_at > now` e a conta com `deleted_at IS NULL`, usando `with_for_update()`.
     2. Se não houver token válido, retorna `False`.
     3. Senão, grava `password_hash`, `used_at` e a auditoria de atualização dos dois registros e retorna `True`.
   - O hash Argon2 é calculado no router, em threadpool, antes de chamar o serviço, para que o serviço continue síncrono em relação à CPU e simples de testar.
6. **Rotas** em `auth.py`:
   - `forgot_password`: chama o serviço, faz `commit` e devolve a mensagem neutra.
   - `reset_password`: calcula o hash em threadpool. Se o serviço devolver `False`, responde `api_error(400, 'invalid_reset_token', 'Link de redefinição inválido ou expirado.')`. Senão, faz `commit` e responde 204.
   - `responses` documentam 400 e 422, como em `PATCH /auth/me`.
   - Sem `CurrentUser` nem `TrustedOrigin` (research R8).
7. **README e `.env.example`**:
   - Na seção "Usuários e Autenticação": as duas rotas, a mensagem neutra, os 30 minutos, a invalidação, o 400 único, o 204, sessões não revogadas e a ausência de rate limit.
   - Na tabela de variáveis: `PASSWORD_RESET_URL_TEMPLATE`.
   - Na seção "Notificações": a recuperação de senha como segundo uso.
   - No `.env.example`: a variável comentada.
8. **Verificação**: testes focados, suíte completa, `ruff check` e `ruff format --check`, sempre conferindo a saída real.

**Hash antes da validação do token**: calcular o hash antes de saber se o token é válido custa um Argon2 em toda chamada, inclusive nas recusadas. Isso é aceitável e uniformiza o tempo entre token válido e recusado. A alternativa, validar, calcular o hash e revalidar, exigiria duas consultas ou manter o bloqueio durante o Argon2. Calcular antes e bloquear só no final é mais simples e mantém a transação curta.

## Test Strategy

As tarefas de teste serão detalhadas em `/speckit-tasks` com a skill `fastapi-testing-methodology`, um teste por comportamento. Testes de API usam `use_settings(email_settings(PASSWORD_RESET_URL_TEMPLATE='https://front.test/redefinir-senha/{token}'))`.

- **Ponta a ponta sem atalho**: o teste obtém o token como a pessoa obteria. Pede a recuperação, roda `process_next` com `FakeEmailChannel` e extrai o token do link em `message.text`. Nada lê o token do banco, porque lá só existe o hash.
- **US1**:
  - Conta ativa: 200, mensagem neutra, um token com hash de 64 caracteres e diferente do bruto, `expires_at` em cerca de 30 minutos.
  - E-mail com outra caixa: mesmo efeito.
  - Segundo pedido: o primeiro token vira 400, o segundo funciona, e o envio pendente anterior fica `cancelled`.
- **US2**:
  - E-mail inexistente e conta excluída: corpo idêntico ao da conta ativa, nenhum token e nenhuma notificação.
  - E-mail inválido ou campo extra: 422.
  - Esses testes passam ao serem escritos, porque o filtro da US1 já atende; eles provam a não enumeração.
- **Sem canal ou sem modelo** (entra na US1, para que ela seja implantável sozinha): 200 idêntico, nenhum token, evento `password_reset_unavailable` no log operacional. Os testes passam as duas variáveis explicitamente, inclusive como `None`, para não depender do `.env`.
- **US3**:
  - Redefinição válida: 204, login novo aceito e antigo recusado, `used_at` e `updated_by` preenchidos.
  - Token reutilizado, expirado (`expires_at` movido para o passado no banco), desconhecido, substituído e de conta excluída depois da emissão: todos 400 com o mesmo `detail`, e `password_hash` inalterado.
  - Senha fora da política: 422 sem regra nem valor no corpo; o token continua funcionando.
  - Campo extra ou ausente: 422.
- **Concorrência** (no padrão de `test_user_concurrency.py`, com sessões independentes): duas redefinições simultâneas com o mesmo token resultam em um 204 e um 400.
- **Segredo fora dos logs** (SC-006): o fluxo completo (pedido, worker, redefinição) não registra o token bruto, o link nem a senha nova. A verificação usa duas capturas:
  - `caplog` em nível DEBUG, para os loggers que propagam até a raiz;
  - um handler ligado direto em `pivma.operational`, porque `setup_logging()` desliga a propagação desse logger e o `caplog` não o vê. O padrão é o de `capture_jsonl` em `tests/unit/test_structured_logging.py`.
- **Isolamento** (FR-017): outra conta não é afetada; as colunas da conta, menos senha e auditoria de atualização, e as linhas de perfil e vínculo ficam inalteradas.
- **Sessão ativa**: uma pessoa com sessão aberta também redefine com o token (spec, Edge Cases).
- **Unitários**: schemas, renderizador e validação de `PASSWORD_RESET_URL_TEMPLATE`.
- **Migração**: `upgrade`/`downgrade` no padrão de `test_notifications_migration.py`.
- **Regressão** (SC-007): `test_auth_router.py`, `test_user_update.py`, os testes de notificações e a suíte completa continuam verdes sem mudar asserções existentes.

## Traceability

| Requirement | Design / Implementation | Evidence |
|---|---|---|
| FR-001, FR-009 | Rotas em `auth.py`; `ForgotPasswordRequest`/`ResetPasswordRequest` com `extra='forbid'` | Testes 422 de formato e campos extras |
| FR-002 | Mensagem neutra única no serviço/rota | Comparação de status e corpo entre conta ativa, inexistente, excluída e sem canal |
| FR-003 | `token_urlsafe(32)`, `TOKEN_TTL`, busca por `lower(email)` | Teste de `expires_at` e de e-mail com outra caixa |
| FR-004 | Só `token_hash` na tabela; nenhum log com token | Inspeção do banco; teste com `caplog` e captura de `pivma.operational` |
| FR-005 | Invalidação por `deleted_at` + `FOR UPDATE` na conta | Teste de token substituído |
| FR-006 | `enqueue_notification` na mesma sessão, um commit | Notificação com `kind`, `recipient`, `subject` e `expires_at` |
| FR-007 | `PASSWORD_RESET_URL_TEMPLATE` com `{token}` | Link extraído do e-mail; teste de settings |
| FR-008 | Checagem de `email_channel_available` e do modelo antes da consulta | Teste sem canal/modelo |
| FR-010 | Restrições e validador de `new_password` | Testes 422 de senha curta, longa e com espaço |
| FR-011, FR-012 | Consulta com todas as condições; `api_error(400, 'invalid_reset_token', ...)` | Testes 400 dos cinco motivos com `detail` idêntico |
| FR-013 | Senha e `used_at` na mesma transação | Estado conferido após sucesso e após recusa |
| FR-014 | `with_for_update()` no token | Teste de concorrência |
| FR-015 | `set_update_audit(user.id)`; 204 | Teste de `updated_by`/`updated_at` |
| FR-016 | `hash_password` sobre `new_password` | Login novo aceito, antigo recusado |
| FR-017 | Sem dependência de sessão; só `password_hash` muda | Asserções de campos inalterados |
| FR-018 | Nenhuma rota existente alterada | Suíte de auth e usuários verde |

## Risks and Controls

| Risk | Control |
|---|---|
| Enumeração de contas pela resposta | Corpo e status idênticos; teste comparando os casos |
| Token vazado em log | Nenhum `logger` recebe token, link ou e-mail; teste com `caplog` e captura de `pivma.operational`; token no corpo da requisição, não na URL |
| Uso duplo por requisições simultâneas | `SELECT ... FOR UPDATE` no token; teste de concorrência |
| Dois tokens válidos por pedidos simultâneos | `SELECT ... FOR UPDATE` na conta antes de invalidar |
| E-mail antigo entregue com link já invalidado | `cancel_pending_notifications` por conta; `expires_at` no envio |
| Token gravado sem envio, ou envio sem token | Mesma transação; `enqueue_notification` não comita |
| Regra ou valor da senha no 422 | `field_errors` já mascara `*password`; teste do corpo |
| Hash Argon2 bloquear o loop | `run_in_threadpool` |

## Known Limits (documentados, não débito oculto)

- Sem limite de tentativas ou pedidos. É a mesma lacuna do login, a ser especificada à parte.
- Sessões anteriores continuam válidas após a redefinição (mesma limitação da Spec 037).
- Tokens usados, expirados ou substituídos permanecem no banco; não há limpeza.
- O tempo de resposta pode variar pouco entre conta existente e inexistente, porque o envio ocorre fora da requisição.
- Geração de token repetida em `invite_service` e `password_reset_service`. Unificar exigiria tocar o convite, fora do escopo.

## Complexity Tracking

Não há violação a justificar. A tabela nova é pedida pela issue; o módulo de serviço segue o padrão `core/*_service.py`; não há classe, repositório, dependência nem configuração além do modelo de link.
