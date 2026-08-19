# Modelo de dados: Autorização de Usuários e RBAC

## Visão geral

O modelo acrescenta cinco tabelas. Quatro representam RBAC normalizado e uma preserva somente as mudanças concluídas desta feature. Todos os modelos seguem `AuditMixin`; nenhuma FK usa exclusão em cascata.

```text
users
  └──< user_access_profiles >── access_profiles
                                      └──< access_profile_permissions >── permissions

rbac_changes ── referencia logicamente a mudança concluída
```

## Perfil de acesso: `access_profiles`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | Chave primária imutável. |
| `system_key` | texto opcional, até 64 | Chave interna dos nove perfis oficiais; única quando preenchida e imutável. Perfis adicionais usam nulo. |
| `name` | texto, 3 a 64 | Remove espaços externos; nome ativo único sem distinção de caixa. |
| `description` | texto, 1 a 500 | Descreve atribuições e responsabilidades. |
| campos de `AuditMixin` | auditoria | `deleted_at IS NULL` indica perfil ativo. |

### Perfis oficiais semeados

| `system_key` | Nome protegido |
|---|---|
| `proponent` | Proponente |
| `management_group` | Grupo Gestor |
| `study_manager` | Gerente do Estudo |
| `participating_laboratory` | Laboratório Participante |
| `ad_hoc_evaluator` | Avaliador Ad Hoc |
| `reviewer` | Revisor |
| `specialist` | Especialista |
| `statistical_analyst` | Analista Estatístico |
| `administrator` | Administrador |

### Regras e transições

- A aplicação não altera `system_key` nem o nome de um perfil com essa chave.
- Um administrador pode alterar descrição e permissões de qualquer perfil oficial, sujeito à guarda do último administrador.
- Um administrador pode inativar perfil oficial ou adicional, exceto `administrator`.
- A inativação preenche `deleted_at` e `deleted_by`; o perfil e suas atribuições deixam de conceder acesso.
- A feature não reativa perfis. Um novo perfil adicional pode reutilizar o nome de um perfil adicional inativo. Nomes oficiais permanecem reservados.

### Constraint

```text
UNIQUE lower(name) WHERE deleted_at IS NULL
```

## Permissão: `permissions`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | Chave primária imutável. |
| `code` | texto, até 100 | Identificador estável, único e imutável. |
| `description` | texto, 1 a 500 | Capacidade protegida. |
| campos de `AuditMixin` | auditoria | Catálogo semeado usa autoria nula. A API desta feature não inativa permissões. |

### Catálogo inicial

| Código | Capacidade |
|---|---|
| `rbac.read` | Consultar permissões, perfis, acesso efetivo e mudanças persistidas. |
| `rbac.profiles.manage` | Criar, alterar, compor e inativar perfis. |
| `rbac.assignments.manage` | Conceder e retirar perfis de contas. |

Features futuras acrescentam permissões por migração aprovada. Nenhuma operação HTTP cria, altera ou remove o catálogo.

## Composição: `access_profile_permissions`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | Chave primária do ciclo de concessão. |
| `profile_id` | UUID | FK obrigatória para `access_profiles.id`. |
| `permission_id` | UUID | FK obrigatória para `permissions.id`. |
| campos de `AuditMixin` | auditoria | Criação registra concessão; exclusão lógica registra retirada. |

### Constraint

```text
UNIQUE (profile_id, permission_id) WHERE deleted_at IS NULL
```

A substituição da composição encerra os vínculos retirados e cria vínculos para as novas permissões na mesma transação. Códigos repetidos no pedido não são aceitos.

## Atribuição: `user_access_profiles`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | Chave primária do ciclo de atribuição. |
| `user_id` | UUID | FK obrigatória para `users.id`. A conta deve estar ativa na concessão e na avaliação. |
| `profile_id` | UUID | FK obrigatória para `access_profiles.id`. O perfil deve estar ativo na concessão e na avaliação. |
| campos de `AuditMixin` | auditoria | Criação registra concessão; exclusão lógica registra retirada. |

### Constraint

```text
UNIQUE (user_id, profile_id) WHERE deleted_at IS NULL
```

Uma retirada encerra o vínculo atual. Uma concessão posterior cria outro registro, preservando o ciclo anterior.

## Mudança de RBAC: `rbac_changes`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | Chave primária. |
| `action` | texto, até 64 | Tipo estável da mudança concluída. |
| `target_type` | texto, até 32 | `profile`, `profile_permissions` ou `assignment`. |
| `target_id` | UUID | Identificador do perfil ou da relação afetada; referência lógica, sem FK polimórfica. |
| campos de `AuditMixin` | auditoria | `created_by` e `created_at` representam responsável e momento. Atualização e exclusão não são usadas. |

### Ações iniciais

- `profile.created`
- `profile.updated`
- `profile.deactivated`
- `profile.permissions_replaced`
- `assignment.granted`
- `assignment.revoked`
- `bootstrap.admin_assigned`

A tabela não armazena valores anteriores ou posteriores, endereço de rede, retenção, recusas ou eventos de outros módulos. O bootstrap usa `created_by = NULL`; mudanças administrativas exigem conta autenticada.

A listagem usa um índice por `created_at DESC, id DESC` para manter paginação determinística sem varrer a tabela por ordem de inserção.

## Permissões efetivas

O backend calcula o conjunto distinto de `permissions.code` por estas condições:

1. a conta existe e `users.deleted_at IS NULL`;
2. a atribuição possui `user_access_profiles.deleted_at IS NULL`;
3. o perfil possui `access_profiles.deleted_at IS NULL`;
4. a composição possui `access_profile_permissions.deleted_at IS NULL`;
5. a permissão pertence ao catálogo.

O backend executa essa consulta em cada pedido protegido e não grava o resultado no JWT ou em cache compartilhado.

## Invariantes transacionais

- Toda mutação e seu `rbac_changes` confirmam ou revertem juntas.
- Mutações que possam retirar capacidade administrativa bloqueiam o perfil `administrator`, aplicam a mudança e verificam que ao menos uma conta ativa conserva as três permissões administrativas.
- O backend converte violações dos índices ativos em conflito público, sem deixar linhas parciais.
- Uma conta proibida recebe a negação antes da consulta do alvo. IDs existentes e inexistentes produzem a mesma resposta para essa conta.

## Migração

O upgrade cria as tabelas na ordem `access_profiles`, `permissions`, `access_profile_permissions`, `user_access_profiles` e `rbac_changes`; depois insere nove perfis, três permissões e as três composições do Administrador com UUIDs literais determinísticos.

O downgrade remove `rbac_changes`, `user_access_profiles`, `access_profile_permissions`, `permissions` e `access_profiles`. Ele preserva `users` e os contratos das features 001 e 002. O desenho usa texto com validação na aplicação, sem enum nativo do PostgreSQL.
