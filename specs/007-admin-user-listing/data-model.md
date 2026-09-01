# Modelo de dados: Listagem Administrativa de Usuários

## Visão geral

A feature não cria tabela nem modelo ORM. Ela lê `users` e, quando solicitado, verifica relações existentes do RBAC. A única mudança persistente é a ampliação do catálogo e da composição oficial por uma migração de dados.

```text
users
  └──< user_access_profiles >── access_profiles
                                      └──< access_profile_permissions >── permissions
```

## Conta de usuário: `users`

| Campo existente | Uso na listagem | Regra |
|---|---|---|
| `id` | Identificador público | Mesmo UUID usado nas operações `/rbac/users/{user_id}/...`. |
| `username` | Exibição, busca e ordenação | Busca de substring case-insensitive; ordem por `lower(username)`. |
| `email` | Exibição e busca | Busca de substring case-insensitive. |
| `password_hash` | Nenhum | Não integra o statement de resposta nem o schema público. |
| `deleted_at` | Filtro e estado derivado | Nulo representa `active=true`; preenchido representa `active=false`. |
| demais campos de auditoria | Nenhum | Não aparecem no item administrativo. |

### Estados observáveis

```text
deleted_at IS NULL     -> active = true
deleted_at IS NOT NULL -> active = false
```

A feature não altera esses estados. Reativação, inativação e atualização pertencem a outras features.

## Permissão: `permissions`

A migração acrescenta uma linha ao catálogo existente:

| Campo | Valor ou regra |
|---|---|
| `id` | `00000000-0000-0000-0000-000000000108` |
| `code` | `users.read` |
| `description` | Capacidade de consultar a listagem administrativa de contas. |
| auditoria | `created_at` fornecido pelo banco; autoria nula, conforme os seeds atuais. |

`users.read` não integra `ADMINISTRATIVE_PERMISSIONS`. O backend pode associá-la a qualquer perfil ativo pelo mecanismo de composição existente; a migração a concede somente ao perfil oficial Administrador.

## Composição oficial: `access_profile_permissions`

A migração acrescenta a composição:

| Campo | Valor ou regra |
|---|---|
| `id` | `00000000-0000-0000-0000-000000000208` |
| `profile_id` | UUID existente do perfil com `system_key = 'administrator'`: `00000000-0000-0000-0000-000000000009`. |
| `permission_id` | UUID de `users.read`. |
| `deleted_at` | Nulo no seed. |
| auditoria | `created_at` fornecido pelo banco; autoria nula. |

Uma conta com atribuição ativa ao perfil Administrador recebe `users.read` pelo cálculo de permissões efetivas existente. A migração não cria atribuição de perfil nem promove conta.

## Relação usada pelo filtro: `user_access_profiles`

O filtro `profile_id` considera uma conta quando todas as condições são verdadeiras:

1. `user_access_profiles.user_id = users.id`;
2. `user_access_profiles.profile_id = profile_id` informado;
3. `user_access_profiles.deleted_at IS NULL`;
4. o `access_profiles` correspondente possui `deleted_at IS NULL`.

Um perfil desconhecido, inativo ou ligado somente por atribuição encerrada não produz correspondência. O filtro usa existência correlacionada e não devolve a mesma conta mais de uma vez.

## Item administrativo de usuário

Projeção pública da API, sem persistência própria:

| Campo | Tipo | Origem |
|---|---|---|
| `id` | UUID | `users.id` |
| `username` | string | `users.username` |
| `email` | string com formato e-mail | `users.email` |
| `active` | boolean | `users.deleted_at IS NULL` |

O schema não aceita nem devolve senha, hash, tokens, sessões, permissões, perfis ou campos de auditoria.

## Página administrativa

| Campo | Tipo | Regra |
|---|---|---|
| `offset` | inteiro | Padrão 0; mínimo 0. |
| `limit` | inteiro | Padrão 100; entre 1 e 100. |
| `items` | lista de itens administrativos | No máximo `limit` itens; pode ficar vazia. |

A resposta não contém `total`, cursores ou links de navegação.

## Regras da consulta

O backend forma um único conjunto antes da página:

1. aplica o estado, com `active=true` como padrão;
2. aplica a busca textual quando o valor sem espaços externos não está vazio;
3. aplica a existência de perfil e atribuição ativos quando `profile_id` está presente;
4. ordena por `lower(username)` ascendente e `id` ascendente;
5. aplica `offset` e `limit` no PostgreSQL.

O backend não executa contagem total e não grava estado durante a consulta.

## Migração e downgrade

O upgrade sucede `6f2c9a1d4e70` e insere a permissão e a composição oficial. Ele preserva tabelas, índices, contas, perfis e atribuições existentes.

O downgrade remove primeiro todas as composições cujo `permission_id` pertence a `users.read`, inclusive composições criadas depois para perfis adicionais, e depois remove a permissão. Ele preserva contas, perfis e atribuições de perfil.
