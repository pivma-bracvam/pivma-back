# Data Model: Desativação de Conta de Usuário

## Entidades existentes

### Conta de usuário (`users`)

| Campo | Uso nesta feature | Regra |
|---|---|---|
| `id` | Identifica a conta alvo e a pessoa autora. | A rota recebe UUID; a conta alvo deve estar ativa. |
| `deleted_at` | Representa o estado inativo. | `null` significa ativa; a desativação preenche o campo com o horário do banco. |
| `deleted_by` | Registra quem desativou a conta. | Recebe o `id` da pessoa autorizada. |
| demais campos | Dados preservados. | A feature não os altera. |

`User` herda `AuditMixin`. A transição usa o método existente `set_deletion_audit`; não há migração ou alteração de esquema.

## Relações e regras

| Relação ou regra | Tratamento |
|---|---|
| Conta autora → conta alvo | A autora deve ter `users.manage`, origem confiável e sessão ativa; não pode ser a própria conta alvo. |
| Conta → perfis e permissões | Os vínculos permanecem. A invariante considera apenas contas ativas e exige uma que possua todas as permissões administrativas. |
| Conta → credencial de sessão | Não há persistência de sessão a alterar. As consultas de autenticação deixam de encontrar a conta inativa. |
| Conta → listagem administrativa | A lista padrão busca ativas; `active=false` busca inativas com o filtro global explicitamente ignorado. |

## Transição de estado

```text
ativa (deleted_at = null)
  └─ DELETE autorizado e invariante preservada ─> inativa (deleted_at e deleted_by preenchidos)
```

Não existe transição de reativação nesta feature. Pedido para uma conta inativa recebe 404 e não altera os campos de auditoria.

## Atomicidade e concorrência

O endpoint bloqueia a linha da conta ativa. Após o `flush`, a checagem administrativa bloqueia o perfil administrativo compartilhado e avalia o estado que inclui a desativação pendente. Qualquer conflito desfaz a transação, incluindo os campos de auditoria.
