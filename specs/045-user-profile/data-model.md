# Data Model: Perfil do Usuário

A feature não cria tabela nem coluna. As entidades abaixo são projeções de
leitura em `src/pivma/schemas.py`, todas com `extra='forbid'`.

## Origem dos dados

| Dado | Origem |
|---|---|
| Conta | `users`: `id`, `full_name`, `email`, `created_at`, `deleted_at` |
| Cargo global | `user_access_profiles.created_at` com `access_profiles.id` e `name`, ambos com `deleted_at` nulo |
| Cargo local | `assignments`: `id`, `process_instance_id`, `role_key`, `laboratory_id`, `assigned_at`, `revoked_at`, com `deleted_at` nulo |
| Processo | `process_instances`: `id`, `code`, `title`, `status`, com `deleted_at` nulo |
| Laboratório | `laboratory_refs` (laboratório e instituição, inclusive desativados) |

## UserProfile

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | |
| `full_name` | string ou null | igual a `UserPublic` |
| `email` | string (`format: email`) | dado sensível na visão futura de membros comuns |
| `active` | bool | `deleted_at` nulo |
| `created_at` | datetime | |
| `global_profiles` | lista de `GlobalProfileAssignment` | só as vigentes, em ordem de `assigned_at` e depois de `id` |

O perfil não tem `username`, `password_hash` nem outros campos de auditoria.

## GlobalProfileAssignment

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | id do perfil de acesso |
| `name` | string | nome do perfil |
| `assigned_at` | datetime | `user_access_profiles.created_at` da atribuição vigente |

## UserProcessRoles (item da listagem)

| Campo | Tipo | Regra |
|---|---|---|
| `process` | `UserProcessRef` | |
| `roles` | lista de `UserProcessRole` | só os cargos que atendem ao filtro, em ordem de `assigned_at` decrescente e depois de `id` crescente |

## UserProcessRef

Subclasse de `ProcessRef` (`id`, `code`, `title`) com `status`, o estado atual
do processo. `ProcessRef` não muda.

## UserProcessRole

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | id da designação |
| `role_key` | string | chave do cargo, como nas rotas de participantes |
| `laboratory` | `LaboratoryRef` ou null | só em cargo laboratorial |
| `assigned_at` | datetime | |
| `revoked_at` | datetime ou null | null nos cargos ativos |

## UserProcessRoleFilters

| Campo | Tipo | Regra |
|---|---|---|
| `active` | bool | padrão `true`: `true` traz os cargos não revogados; `false`, os revogados |

## UserProcessRoleListResponse

`ListPage[UserProcessRoles, UserProcessRoleFilters]`, com
`sort = {by: 'last_assigned_at', order: 'desc'}`. A paginação conta processos.
