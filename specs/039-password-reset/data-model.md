# Data Model: Recuperação de Senha por Token Temporário

## PasswordResetToken (nova tabela `password_reset_tokens`)

Modelo em `src/pivma/core/database/models.py`, com `AuditMixin` e `@table_registry.mapped_as_dataclass`, no estilo de `RoleAssignmentInvite`.

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID, PK | `uuid4`, gerado na aplicação |
| `user_id` | UUID, FK `users.id`, NOT NULL | Conta dona do token |
| `token_hash` | `String(64)`, NOT NULL | SHA-256 hex do token bruto (research R1) |
| `expires_at` | `timestamp`, NOT NULL | Emissão + 30 minutos, UTC ingênuo (R5) |
| `used_at` | `timestamp`, NULL | Preenchido no uso aceito |
| `created_at`, `updated_at`, `deleted_at` | AuditMixin | `deleted_at` marca o token substituído por um pedido mais recente (R3) |
| `created_by`, `updated_by`, `deleted_by` | AuditMixin | `created_by` e `deleted_by` nulos (pedido anônimo); `updated_by = user_id` no uso (R10) |

**Índices**

- `uq_password_reset_tokens_token_hash`: único em `token_hash`, usado na busca do token.
- `ix_password_reset_tokens_user_id`: em `user_id`, usado para invalidar os tokens da conta.

O token bruto não tem coluna. Ele só existe no link do e-mail, guardado cifrado em `notifications.payload_encrypted` até o envio terminar.

## Estados

O estado é derivado dos campos, não gravado (mesmo princípio de `RoleAssignmentInvite.is_expired`).

| Estado | Condição |
|---|---|
| Válido | `used_at IS NULL` e `deleted_at IS NULL` e `expires_at > agora` e conta com `deleted_at IS NULL` |
| Usado | `used_at IS NOT NULL` |
| Substituído | `deleted_at IS NOT NULL` |
| Expirado | `expires_at <= agora` |

Transições:

```text
(emissão) ──► Válido ──(redefinição aceita)──► Usado
                 │
                 ├──(novo pedido da mesma conta)──► Substituído
                 └──(passa de 30 min)─────────────► Expirado (derivado)
```

Todos os estados não válidos recebem a mesma resposta: `400 invalid_reset_token`.

## User (existente, `users`)

Sem mudança de schema. A redefinição altera só `password_hash`, `updated_at` e `updated_by`.

## Notification (existente, `notifications`, Spec 036)

Sem mudança de schema. Cada pedido válido grava uma linha:

| Campo | Valor |
|---|---|
| `kind` | `password_reset_email` |
| `channel` | `email` |
| `recipient` | e-mail da conta, como está no cadastro |
| `subject_type` / `subject_id` | `password_reset` / `user.id` (research R6) |
| `expires_at` | o mesmo do token |
| `payload_encrypted` | `{reset_url, expires_at}` cifrado |
| `process_instance_id` | nulo; por isso não há `AuditEvent` |

## Configuração

| Variável | Regra |
|---|---|
| `PASSWORD_RESET_URL_TEMPLATE` | Opcional; quando presente, contém `{token}` exatamente uma vez. Ex.: `https://pivma.exemplo/redefinir-senha/{token}` |

## Migração

Nova revisão Alembic cujo `down_revision` é a head única da branch de destino (hoje `6eb1ae208b7d` nesta branch e `5af69c71be3c` em `origin/develop`):

- `upgrade` cria a tabela com as FKs (`user_id` e as de auditoria) e os dois índices;
- `downgrade` remove os índices e a tabela.

Não há dados a migrar.
