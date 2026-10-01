# Data Model: Base de notificações e envio do convite por e-mail

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

## Nova tabela `notifications`

Um envio de mensagem para um destinatário por um canal. Herda `AuditMixin`
(`created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at`).

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | PK |
| `kind` | `String(64)` | Tipo de aviso. Nesta entrega: `invite_email` |
| `channel` | `String(16)` | Nesta entrega: `email` |
| `recipient` | `String(320)` | Endereço de destino |
| `subject_type` | `String(32)`, nulo | Objeto de negócio de origem. Aqui: `role_assignment_invite` |
| `subject_id` | UUID, nulo | Id do objeto de origem |
| `process_instance_id` | UUID FK `process_instances.id`, nulo | Processo para a trilha de auditoria |
| `payload_encrypted` | `Text`, nulo | Conteúdo cifrado (Fernet). Apagado no estado final (FR-009) |
| `status` | `String(16)` | `pending`, `sent`, `failed`, `cancelled` |
| `attempts` | `Integer`, padrão 0 | Tentativas já feitas |
| `next_attempt_at` | `DateTime` | Quando pode ser tentado. Na criação, agora |
| `expires_at` | `DateTime`, nulo | Depois disso não é mais enviado (prazo do convite) |
| `last_attempt_at` | `DateTime`, nulo | |
| `sent_at` | `DateTime`, nulo | |
| `finished_at` | `DateTime`, nulo | Momento em que chegou a `sent`, `failed` ou `cancelled` |
| `error_code` | `String(32)`, nulo | `smtp_permanent`, `smtp_temporary`, `connection`, `max_attempts`, `expired`, `decrypt`, `cancelled_resent`, `cancelled_revoked`, `cancelled_accepted` |
| `error_detail` | `String(500)`, nulo | Mensagem curta do erro, sem conteúdo do envio (FR-010) |

**Índices**

- `ix_notifications_pending_due` em `(next_attempt_at)` com
  `WHERE status = 'pending' AND deleted_at IS NULL`: busca do processo de envio.
- `ix_notifications_subject` em `(subject_type, subject_id)`: cancelamento e
  situação do envio no convite.

**Estados**

```text
pending ──envio aceito──────────────────────────► sent
pending ──erro temporário (tentativas < máx)────► pending (attempts+1, next_attempt_at adiante)
pending ──erro temporário (tentativas = máx)────► failed (max_attempts)
pending ──erro permanente───────────────────────► failed (smtp_permanent)
pending ──prazo vencido─────────────────────────► failed (expired)
pending ──reenvio / revogação / aceite──────────► cancelled
```

`sent`, `failed` e `cancelled` são finais: `payload_encrypted` vira nulo e
`finished_at` é preenchido. Nenhuma transição sai de um estado final.

## `role_assignment_invites` (Spec 028)

Sem coluna nova. `channel` passa a aceitar `email` além de `link` (validação
na camada de aplicação, como hoje). Convites existentes continuam `link`.

## Conteúdo cifrado do envio `invite_email`

JSON cifrado em `payload_encrypted`:

| Chave | Valor |
|---|---|
| `invite_url` | `INVITE_URL_TEMPLATE` com o token bruto |
| `process_code` | Código do processo |
| `process_title` | Título do processo |
| `role_key` | Papel do convite |
| `laboratory_name` | Nome do laboratório, ou nulo |
| `expires_at` | Prazo do convite (ISO 8601, UTC) |

## Configuração nova (`Settings`)

| Variável | Padrão | Uso |
|---|---|---|
| `NOTIFICATION_EMAIL_BACKEND` | vazio | `smtp`, `fake` ou vazio (canal não configurado) |
| `SMTP_HOST` | vazio | Obrigatório com `smtp` |
| `SMTP_PORT` | `587` | |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | vazio | Opcionais (Mailpit não exige) |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` ou `none` |
| `SMTP_TIMEOUT_SECONDS` | `15` | |
| `NOTIFICATION_FROM_ADDRESS` | vazio | Remetente; obrigatório para o canal |
| `NOTIFICATION_FROM_NAME` | `pi*VMA` | |
| `NOTIFICATION_ENCRYPTION_KEY` | vazio | Chave Fernet; obrigatória para o canal |
| `NOTIFICATION_MAX_ATTEMPTS` | `5` | |
| `NOTIFICATION_RETRY_BASE_SECONDS` | `30` | |
| `NOTIFICATION_RETRY_MAX_SECONDS` | `900` | |
| `NOTIFICATION_POLL_SECONDS` | `5` | Intervalo do processo de envio quando a fila está vazia |
| `INVITE_URL_TEMPLATE` | vazio | Endereço completo com `{token}`; obrigatório para convite por e-mail |

O canal de e-mail está **disponível** quando `NOTIFICATION_EMAIL_BACKEND`,
`NOTIFICATION_FROM_ADDRESS` e `NOTIFICATION_ENCRYPTION_KEY` estão definidos
(e `SMTP_HOST` com `smtp`). O convite por e-mail exige também
`INVITE_URL_TEMPLATE`.

## Eventos de auditoria novos

| `event_type` | Quem grava | `user_id` |
|---|---|---|
| `NOTIFICATION_SENT` | Processo de envio | nulo |
| `NOTIFICATION_FAILED` | Processo de envio | nulo |
| `NOTIFICATION_CANCELLED` | Quem cancela (reenvio, revogação, aceite) | ator |

Contexto: `notification_id`, `kind`, `channel`, `subject_type`, `subject_id`,
`attempts`, `error_code`. Sem destinatário nem conteúdo.
