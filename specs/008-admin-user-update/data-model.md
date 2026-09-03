# Data Model: Atualização Administrativa de Usuários

## Entidades existentes

### User

A feature não cria uma tabela nova. Ela atualiza uma conta existente na tabela `users`.

| Campo | Regra nesta feature |
|---|---|
| `id` | Identificador recebido no caminho `/users/{user_id}`; não pode ser alterado. |
| `username` | Somente leitura nesta feature. |
| `email` | Somente leitura nesta feature. |
| `password_hash` | Somente leitura nesta feature. |
| `full_name` | Valor aparado entre 1 e 255 caracteres no PATCH; continua anulável para contas legadas/mockadas. |
| `updated_at` | Atualizado quando o PATCH é concluído. |
| `updated_by` | Recebe o UUID da pessoa administradora que executou a alteração. |
| `deleted_at` | Não é alterado pelo PATCH. |

Uma conta antiga pode iniciar com `full_name = null` e receber um valor válido posteriormente. A operação não permite limpar um nome já preenchido.

### Permission

| Campo | Regra nesta feature |
|---|---|
| `code` | Novo valor estável `users.manage`. |
| `description` | Descreve a capacidade de atualizar dados administrativos de usuários. |

### AccessProfilePermission

A migração cria uma composição entre `users.manage` e o perfil oficial Administrador. A permissão não entra em `ADMINISTRATIVE_PERMISSIONS`, pois não participa da salvaguarda que mantém a administração do RBAC.

## Request model

`UserUpdate` aceita somente:

| Campo | Obrigatório | Regra |
|---|---|---|
| `full_name` | Sim | String aparada, com 1 a 255 caracteres; `null` não é permitido. |

Campos desconhecidos retornam HTTP 422.

## Response model

O PATCH devolve `UserPublic`, contendo `id`, `username`, `email` e `full_name`. A resposta não contém senha, hash, tokens, perfis ou dados de autorização.

## State transitions

```text
legacy full_name = null --PATCH válido--> full_name aparado
full_name preenchido --PATCH válido--> novo full_name aparado
qualquer estado --PATCH inválido/negado--> estado inalterado
```

## Migration

A revisão `8c5e7a1b9d02_user_management_permission.py` sucede `7b4f5d6e8a90`, insere `users.manage` e sua composição no perfil Administrador. O downgrade remove as composições ligadas à permissão antes de remover a permissão. Nenhuma linha de `users` é atualizada pela migração.
