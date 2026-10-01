# Implementation Plan: Base de notificações e envio do convite por e-mail

**Branch**: `feat/036-notification-email-invite` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/036-notification-email-invite/spec.md`

## Summary

Criar uma base de notificações reutilizável e usá-la para enviar o convite de
designação (Spec 028) por e-mail. O código de negócio grava um pedido de envio
na tabela `notifications`, na mesma transação da operação. Um processo
separado (`python -m pivma.notifications.worker`) busca os pendentes com
`FOR UPDATE SKIP LOCKED`, envia por SMTP e registra o resultado, com novas
tentativas e prazo. O conteúdo do envio fica cifrado (Fernet) e é apagado ao
fim. O canal é escolhido por configuração, com um canal falso para testes. O
convite passa a aceitar `channel = "email"` e mostra a situação do envio.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2,
pydantic-settings. **Nova**: `cryptography` (Fernet, R3). SMTP pela
biblioteca padrão (`smtplib`, `email`), R4.

**Storage**: PostgreSQL (pgvector/pg17). Nova tabela `notifications`.

**Testing**: pytest, pytest-asyncio, testcontainers (Postgres e Mailpit),
factory-boy.

**Target Platform**: Linux, contêiner Docker. Um serviço novo (`worker`) com a
mesma imagem da API; `mailpit` só em desenvolvimento.

**Project Type**: web-service (backend; o frontend é outro repositório)

**Performance Goals**: mensagem entregue em até 1 minuto com o provedor
disponível (SC-001). Polling de 5 s.

**Constraints**: token bruto do convite nunca legível no banco nem em logs
(FR-009, FR-010); criação do convite nunca depende do envio (FR-016);
nenhuma regra da Spec 028 muda (FR-020).

**Scale/Scope**: dezenas a centenas de mensagens por dia. Um tipo de aviso
(`invite_email`) e um canal (`email`) nesta entrega.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` continua sendo o template sem preencher. Os
gates são os de `AGENTS.md`:

| Gate | Situação |
|---|---|
| Fonte de requisito rastreável | ✅ Issue #49 (reescrita em 2026-10-01 com o usuário), Spec 028 FR-006/FR-007; clarificação de FR-018 registrada na spec |
| Conflito de requisito resolvido com o usuário antes de implementar | ✅ Nenhum marcador aberto. O Plano de Trabalho não tem requisito de notificação; a entrega vem da issue e da Spec 028 |
| Preservar autorização, auditoria, isolamento e cegamento | ✅ Autorização das rotas de convite inalterada; `delivery` só aparece para quem já vê o convite. Auditoria ganha três eventos. Nenhum dado cego envolvido |
| Mudança cirúrgica, sem abstração preventiva | ✅ Uma tabela, um canal, um tipo de aviso. A interface de canal tem duas implementações reais (SMTP e falsa), exigidas pela spec (FR-007, FR-008). Sem motor de templates nem biblioteca de fila (R1, R12) |
| Testes por `$fastapi-testing-methodology`, granularizados por risco | ⏭ Aplicado no `/speckit-tasks` |
| README atualizado após a implementação | ⏭ Tarefa final (variáveis novas, serviço `worker`, Mailpit) |

**Re-check pós-design**: sem violações. Pontos de atenção:

- **Dependência nova (`cryptography`)**: necessária para cumprir FR-009 sem
  mudar a geração de tokens da Spec 028 (R3).
- **Implantação**: a AWS passa a rodar o serviço `worker`. Sem ele, convites
  por e-mail ficam pendentes e expiram como `failed`.
- **Duplicidade em queda do processo** (R2): limite documentado, não coberto
  por FR-006.
- **Chave de cifragem**: trocar `NOTIFICATION_ENCRYPTION_KEY` com envios
  pendentes faz esses envios falharem (`error_code = "decrypt"`). Registrar no
  README.

## Project Structure

### Documentation (this feature)

```text
specs/036-notification-email-invite/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-api.md
│   └── notifications-module.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/pivma/
├── notifications/                 # NOVO pacote (padrão de src/pivma/ai/)
│   ├── __init__.py
│   ├── channels.py                # OutgoingEmail, EmailChannel, SmtpEmailChannel, FakeEmailChannel, erros
│   ├── crypto.py                  # cifrar/decifrar conteúdo (Fernet)
│   ├── renderers.py               # renderizador por kind (invite_email)
│   ├── service.py                 # enqueue_notification, cancel_pending_notifications, situação por subject
│   └── worker.py                  # process_next + laço (__main__)
├── core/
│   ├── database/models.py         # + Notification
│   ├── invite_service.py          # enfileirar no create/resend; cancelar no resend/revoke/accept; delivery
│   └── settings.py                # + variáveis da tabela em data-model.md
├── routers/process_participants.py  # 409 channel_unavailable
├── schemas.py                     # InviteChannel + 'email'; InviteDeliveryPublic; InvitePublic.delivery
└── dependencies.py                # canal de e-mail por configuração, se a API precisar

migrations/versions/<rev>_notifications.py   # NOVO

compose.yaml                       # + serviços worker e mailpit
.env.example                       # + variáveis novas
pyproject.toml / poetry.lock       # + cryptography

tests/
├── unit/notifications/            # backoff, classificação de erro, cifragem, renderizador, settings
├── integration/notifications/     # enqueue/transação, process_next, concorrência, prazo, cancelamento, auditoria, SMTP x Mailpit
└── api/routers/                   # convites com canal email, 409, delivery, link inalterado
```

**Structure Decision**: pacote próprio `src/pivma/notifications/`, ao lado de
`src/pivma/ai/`, porque é infraestrutura usada por vários domínios e tem um
ponto de entrada próprio (o processo de envio). A integração com o convite fica
em `core/invite_service.py`, onde já moram as regras da Spec 028.

## Complexity Tracking

Sem violações a justificar.
